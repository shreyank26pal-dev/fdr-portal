import React, { useEffect, useState } from 'react';
import {
  apiFetch,
  getToken,
  initUserInvalidSync,
  loginWithCredentials,
  setToken,
  SESSION_EXPIRED_EVENT,
  DEMO_ACCOUNTS,
} from './api';
import { BankMaster, User } from './types';
import { ActiveTab, Header } from './components/Header';
import { DemoTourBar } from './components/DemoTourBar';
import { ExploreHome } from './components/ExploreHome';
import { InstitutionPortal } from './components/InstitutionPortal';
import { CaseSplitView } from './components/CaseSplitView';
import { OfficerConsole } from './components/OfficerConsole';
import { BankConfirmPortal } from './components/BankConfirmPortal';
import { AdminAuditConsole } from './components/AdminAuditConsole';
import { LoginPage } from './components/LoginPage';
import { LandingPage } from './components/LandingPage';
import type { Role } from './types';

const landingTabFor = (role: Role): ActiveTab => {
  if (role === 'INSTITUTION') return 'institution';
  if (role === 'BANK') return 'bank';
  if (role === 'ADMIN') return 'admin';
  if (role === 'SCRUTINY_OFFICER' || role === 'REGIONAL_OFFICER' || role === 'APPROVING_AUTHORITY' || role === 'AUDITOR') return 'officer';
  return 'explore';
};

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('explore');
  const [simulatedToday, setSimulatedToday] = useState<string>('');
  const [clockOffsetDays, setClockOffsetDays] = useState<number>(0);
  const [summary, setSummary] = useState<any | null>(null);
  const [banks, setBanks] = useState<BankMaster[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [switchingAccount, setSwitchingAccount] = useState<boolean>(false);
  const [showDemoTour, setShowDemoTour] = useState<boolean>(false);
  const [selectedInstrumentId, setSelectedInstrumentId] = useState<number | null>(null);
  const [activeBlindToken, setActiveBlindToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState<boolean>(false);
  const [loginNotice, setLoginNotice] = useState<string | null>(null);
  const [authView, setAuthView] = useState<'landing' | 'login'>('landing');
  const [prefillEmail, setPrefillEmail] = useState<string | undefined>(undefined);

  const refreshGlobalTelemetry = async () => {
    try {
      const health = await apiFetch('/health');
      if (health?.simulated_today) setSimulatedToday(health.simulated_today);
      if (typeof health?.clock_offset_days === 'number') {
        setClockOffsetDays(health.clock_offset_days);
      }
    } catch {
      // ignore
    }

    if (!getToken()) return;
    try {
      const [meUser, bankList, notifs] = await Promise.all([
        apiFetch<any>('/auth/me'),
        apiFetch<BankMaster[]>('/banks').catch(() => []),
        apiFetch<any[]>('/notifications').catch(() => []),
      ]);
      // /auth/me returns { user, institution, bank, simulated_today, ... }
      setUser((meUser?.user ?? meUser) as User);
      if (bankList?.length) setBanks(bankList);
      setNotifications(notifs || []);

      const dash = await apiFetch('/dashboard/summary').catch(() => null);
      if (dash) setSummary(dash);
    } catch {
      // token invalid or expired -> show the login page
      setToken(null);
      setUser(null);
    }
  };

  useEffect(() => {
    initUserInvalidSync();

    // Check if URL is /bank-confirm/:token
    const path = window.location.pathname;
    if (path.startsWith('/bank-confirm/')) {
      const tokenPart = path.replace('/bank-confirm/', '').trim();
      if (tokenPart) {
        setActiveBlindToken(tokenPart);
        setActiveTab('bank');
      }
    }

    (async () => {
      await refreshGlobalTelemetry();
      setAuthChecked(true);
    })();

    const onExpired = () => {
      setUser(null);
      setAuthView('login');
      setLoginNotice('Your session has expired. Please sign in again.');
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  const handleLoggedIn = async (u: User) => {
    setUser(u);
    setLoginNotice(null);
    setSelectedInstrumentId(null);
    if (!activeBlindToken) setActiveTab(landingTabFor(u.role));
    await refreshGlobalTelemetry();
  };

  const handleLogout = () => {
    // JWTs are stateless: signing out discards the token on this device
    setToken(null);
    setUser(null);
    setSummary(null);
    setNotifications([]);
    setSelectedInstrumentId(null);
    setShowDemoTour(false);
    setActiveTab('explore');
    setPrefillEmail(undefined);
    setLoginNotice(null);
    setAuthView('landing');
  };

  const handleSwitchAccount = async (email: string) => {
    setSwitchingAccount(true);
    try {
      const data = await loginWithCredentials(email, 'Password@123');
      setUser(data.user);
      // a case opened by the previous role may not be visible to the new one
      setSelectedInstrumentId(null);
      await refreshGlobalTelemetry();
    } finally {
      setSwitchingAccount(false);
    }
  };

  const handleNavigateRoleTab = async (
    email: string | null,
    tab: ActiveTab,
    instrumentId?: number
  ) => {
    if (email && user?.email !== email) {
      await handleSwitchAccount(email);
    }
    if (instrumentId) {
      setSelectedInstrumentId(instrumentId);
    }
    setActiveTab(tab);
  };

  const handleMarkAllRead = async () => {
    try {
      await apiFetch('/notifications/read-all', { method: 'POST' });
      const notifs = await apiFetch<any[]>('/notifications').catch(() => []);
      setNotifications(notifs || []);
    } catch {
      // ignore
    }
  };

  const handleInspectInstrument = (id: number) => {
    setSelectedInstrumentId(id);
    setActiveTab('split');
  };

  const handleOpenBlindLinkToken = (token: string) => {
    setActiveBlindToken(token);
    setActiveTab('bank');
  };

  if (!authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FAF7F2] text-slate-500 text-sm">
        Loading SecureDeposit…
      </div>
    );
  }

  // Bank nodal officer opening a one-time link: public page, no sign-in
  if (!user && activeBlindToken) {
    return (
      <div className="min-h-screen flex flex-col bg-[#FAF7F2] text-[#0F172A]">
        <div className="bg-[#0F2547] text-white text-xs px-4 sm:px-6 py-2 font-semibold">
          SecureDeposit • AICTE FDR confirmation for bank nodal officers
        </div>
        <div className="aicte-rainbow-bar w-full" />
        <main id="main-content" className="flex-1 max-w-[1100px] w-full mx-auto px-4 sm:px-6 py-6">
          <BankConfirmPortal
            user={null}
            banks={banks}
            activeBlindToken={activeBlindToken}
            setActiveBlindToken={setActiveBlindToken}
            onSwitchAccount={handleSwitchAccount}
            onInspectInstrument={handleInspectInstrument}
            onRefreshGlobal={refreshGlobalTelemetry}
          />
        </main>
      </div>
    );
  }

  if (!user && authView === 'landing') {
    return (
      <LandingPage
        onSignIn={(email) => {
          setPrefillEmail(email);
          setLoginNotice(null);
          setAuthView('login');
          window.scrollTo(0, 0);
        }}
      />
    );
  }

  if (!user) {
    const demo = prefillEmail ? DEMO_ACCOUNTS.find((a) => a.email === prefillEmail) : undefined;
    return (
      <LoginPage
        key={prefillEmail || 'blank'}
        onLoggedIn={handleLoggedIn}
        notice={loginNotice}
        onBack={() => {
          setLoginNotice(null);
          setAuthView('landing');
        }}
        initialEmail={prefillEmail}
        initialPassword={demo?.password}
      />
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF7F2] text-[#0F172A]">
      <Header
        onLogout={handleLogout}
        user={user}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        simulatedToday={simulatedToday}
        clockOffsetDays={clockOffsetDays}
        notifications={notifications}
        onMarkAllRead={handleMarkAllRead}
        onSwitchAccount={handleSwitchAccount}
        switchingAccount={switchingAccount}
        showDemoTour={showDemoTour}
        setShowDemoTour={setShowDemoTour}
        selectedInstrumentId={selectedInstrumentId}
      />

      {showDemoTour && (
        <DemoTourBar
          onClose={() => setShowDemoTour(false)}
          onRunScene={(email, tab) => handleNavigateRoleTab(email, tab)}
        />
      )}

      <main
        id="main-content"
        className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 py-6"
      >
        {activeTab === 'explore' && (
          <ExploreHome
            summary={summary}
            simulatedToday={simulatedToday}
            clockOffsetDays={clockOffsetDays}
            onNavigateRoleTab={handleNavigateRoleTab}
            onLaunchDemoTour={() => setShowDemoTour(true)}
          />
        )}

        {activeTab === 'institution' && (
          <InstitutionPortal
            user={user}
            banks={banks}
            onSwitchAccount={handleSwitchAccount}
            onInspectInstrument={handleInspectInstrument}
            onRefreshGlobal={refreshGlobalTelemetry}
          />
        )}

        {activeTab === 'split' && (
          <CaseSplitView
            user={user}
            selectedInstrumentId={selectedInstrumentId}
            onSelectInstrumentId={setSelectedInstrumentId}
            onSwitchAccount={handleSwitchAccount}
            onOpenBlindLinkToken={handleOpenBlindLinkToken}
            onRefreshGlobal={refreshGlobalTelemetry}
          />
        )}

        {activeTab === 'officer' && (
          <OfficerConsole
            user={user}
            onInspectInstrument={handleInspectInstrument}
            onSwitchAccount={handleSwitchAccount}
            onRefreshGlobal={refreshGlobalTelemetry}
          />
        )}

        {activeTab === 'bank' && (
          <BankConfirmPortal
            user={user}
            banks={banks}
            activeBlindToken={activeBlindToken}
            setActiveBlindToken={setActiveBlindToken}
            onSwitchAccount={handleSwitchAccount}
            onInspectInstrument={handleInspectInstrument}
            onRefreshGlobal={refreshGlobalTelemetry}
          />
        )}

        {activeTab === 'admin' && (
          <AdminAuditConsole
            user={user}
            simulatedToday={simulatedToday}
            clockOffsetDays={clockOffsetDays}
            onSwitchAccount={handleSwitchAccount}
            onRefreshGlobal={refreshGlobalTelemetry}
            onInspectInstrument={handleInspectInstrument}
          />
        )}
      </main>

      <footer className="bg-[#0F2547] text-slate-300 text-xs border-t border-slate-800 mt-12">
        <div className="aicte-rainbow-bar w-full" />
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="font-display font-bold text-white">
              SecureDeposit — AICTE Security Deposit &amp; FDR Lifecycle Management Portal (SIH26265)
            </span>
            <p className="text-[11px] text-slate-400 mt-0.5">
              All India Council for Technical Education (AICTE) • Ministry of Education, Government of India
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 font-mono text-[11px]">
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="px-2.5 py-1 rounded bg-white/10 hover:bg-white/20 text-amber-300"
            >
              FastAPI Swagger (/docs) ↗
            </a>
            <a
              href="http://127.0.0.1:8000/health"
              target="_blank"
              rel="noreferrer"
              className="px-2.5 py-1 rounded bg-white/10 hover:bg-white/20 text-emerald-300"
            >
              System Health (/health) ↗
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};
export default App;
