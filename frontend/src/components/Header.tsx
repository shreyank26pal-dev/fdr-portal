import React, { useRef, useState } from 'react';
import {
  LogOut,
  ShieldCheck,
  Bell,
  Clock,
  HelpCircle,
  AlertTriangle,
  UserCheck,
  Compass,
  Building2,
  FileSearch,
  Landmark,
  Settings,
  Sparkles,
  CheckCheck,
  ChevronDown,
  Lock,
  Columns,
} from 'lucide-react';
import { DEMO_ACCOUNTS, openLightDismissDialog } from '../api';
import { User } from '../types';

export type ActiveTab =
  | 'explore'
  | 'institution'
  | 'officer'
  | 'split'
  | 'bank'
  | 'admin';

interface HeaderProps {
  user: User | null;
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  simulatedToday: string;
  clockOffsetDays: number;
  notifications: any[];
  onMarkAllRead: () => void;
  onSwitchAccount: (email: string) => Promise<void>;
  switchingAccount: boolean;
  showDemoTour: boolean;
  setShowDemoTour: (v: boolean) => void;
  selectedInstrumentId: number | null;
  onLogout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  activeTab,
  setActiveTab,
  simulatedToday,
  clockOffsetDays,
  notifications,
  onMarkAllRead,
  onSwitchAccount,
  switchingAccount,
  showDemoTour,
  setShowDemoTour,
  selectedInstrumentId,
  onLogout,
}) => {
  const noteDialogRef = useRef<HTMLDialogElement>(null);
  const helpDialogRef = useRef<HTMLDialogElement>(null);
  const [showNotifPopover, setShowNotifPopover] = useState(false);
  const [lang, setLang] = useState<'en' | 'hi'>(() => {
    return (localStorage.getItem('securedeposit_lang') as 'en' | 'hi') || 'en';
  });

  const handleToggleLang = (newLang: 'en' | 'hi') => {
    setLang(newLang);
    localStorage.setItem('securedeposit_lang', newLang);
  };

  const unreadCount = notifications.filter((n) => !n.read_at && !n.is_read).length;

  return (
    <header className="sticky top-0 z-40 bg-white shadow-sm border-b border-slate-200">
      {/* Official AICTE 4-Color Rainbow Top Strip */}
      <div className="aicte-rainbow-bar w-full" />

      {/* Row 1: Government of India Utility Strip */}
      <div className="bg-[#0F2547] text-white text-xs">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-1.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <span
              className="inline-flex items-center gap-1.5 font-semibold tracking-wide"
              aria-label="Government of India, Ministry of Education"
            >
              <span className="inline-flex flex-col w-4 h-3 rounded-[2px] overflow-hidden border border-white/30">
                <span className="bg-[#FF9933] h-1 w-full" />
                <span className="bg-white h-1 w-full" />
                <span className="bg-[#138808] h-1 w-full" />
              </span>
              <span>{lang === 'hi' ? 'भारत सरकार • शिक्षा मंत्रालय (AICTE)' : 'भारत सरकार | Government of India • Ministry of Education (AICTE)'}</span>
            </span>
            <span className="hidden md:inline-block text-slate-400">|</span>
            <span className="hidden md:inline-block font-mono text-[11px] text-amber-300">
              Smart India Hackathon Problem Statement SIH26265
            </span>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Bilingual NEP 2020 / Bhashini Toggle */}
            <div className="inline-flex rounded-full bg-white/10 p-0.5 border border-white/20 text-[11px] font-semibold">
              <button
                type="button"
                onClick={() => handleToggleLang('en')}
                className={`px-2 py-0.5 rounded-full transition cursor-pointer ${
                  lang === 'en' ? 'bg-amber-400 text-slate-950 font-bold' : 'text-slate-200 hover:text-white'
                }`}
                title="English"
              >
                EN
              </button>
              <button
                type="button"
                onClick={() => handleToggleLang('hi')}
                className={`px-2 py-0.5 rounded-full transition cursor-pointer ${
                  lang === 'hi' ? 'bg-amber-400 text-slate-950 font-bold' : 'text-slate-200 hover:text-white'
                }`}
                title="हिन्दी (NEP 2020 / Bhashini)"
              >
                हिन्दी
              </button>
            </div>

            {/* Simulated Today / Time-Travel Pill */}
            <button
              type="button"
              onClick={() => setActiveTab('admin')}
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-mono text-[11px] border transition cursor-pointer ${
                clockOffsetDays !== 0
                  ? 'bg-amber-400/20 text-amber-200 border-amber-400/50 font-semibold'
                  : 'bg-white/10 text-slate-200 border-white/15 hover:bg-white/20'
              }`}
              title="Click to open Time-Travel Clock & Demo Controls"
            >
              <Clock className="w-3.5 h-3.5 text-amber-300" />
              <span>{lang === 'hi' ? 'अनुकरणीय तिथि:' : 'Simulated Today:'} {simulatedToday || 'Loading...'}</span>
              {clockOffsetDays !== 0 && (
                <span className="bg-amber-400 text-slate-950 px-1.5 py-0.2 rounded font-bold">
                  +{clockOffsetDays}d
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => openLightDismissDialog(noteDialogRef.current)}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded bg-[#EA580C] hover:bg-[#D9460F] text-white font-semibold transition cursor-pointer"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>{lang === 'hi' ? 'महत्वपूर्ण सूचना' : 'Important Note'}</span>
            </button>

            <button
              type="button"
              onClick={() => openLightDismissDialog(helpDialogRef.current)}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white transition cursor-pointer"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{lang === 'hi' ? 'सहायता' : 'Helpline & Support'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Row 2: Main Brand & Navigation Bar */}
      <div className="bg-white">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 py-2.5 flex flex-wrap items-center justify-between gap-3">
          {/* Brand Logo */}
          <div
            onClick={() => setActiveTab('explore')}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-[#0F2547] via-[#1E3A8A] to-[#1D4ED8] flex items-center justify-center text-white shadow-sm group-hover:scale-[1.02] transition">
              <ShieldCheck className="w-6 h-6 text-amber-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-display font-extrabold text-lg sm:text-xl tracking-tight text-[#0F2547]">
                  SecureDeposit
                </span>
                <span className="text-[11px] font-mono font-bold uppercase px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300">
                  {lang === 'hi' ? 'एआईसीटीई सुरक्षा जमा पोर्टल' : 'AICTE FDR Portal'}
                </span>
              </div>
              <p className="text-xs text-slate-600">
                {lang === 'hi'
                  ? 'अखिल भारतीय तकनीकी शिक्षा परिषद • सुरक्षा जमा एवं एफडीआर जीवनचक्र प्रणाली'
                  : 'All India Council for Technical Education • Security Deposit & FDR Lifecycle System'}
              </p>
            </div>
          </div>

          {/* Primary Navigation Pills */}
          <nav
            aria-label="Primary Portal Navigation"
            className="flex flex-wrap items-center gap-1 bg-slate-100/90 p-1 rounded-xl border border-slate-200"
          >
            <button
              type="button"
              onClick={() => setActiveTab('explore')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'explore'
                  ? 'bg-[#0F2547] text-white shadow-xs'
                  : 'text-slate-700 hover:bg-white'
              }`}
            >
              <Compass className="w-3.5 h-3.5" />
              <span>{lang === 'hi' ? 'अन्वेषण हब' : 'Explore Hub'}</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('institution')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'institution'
                  ? 'bg-[#0F2547] text-white shadow-xs'
                  : 'text-slate-700 hover:bg-white'
              }`}
            >
              <Building2 className="w-3.5 h-3.5" />
              <span>{lang === 'hi' ? 'संस्थान पोर्टल' : 'Institution Portal'}</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('officer')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'officer'
                  ? 'bg-[#0F2547] text-white shadow-xs'
                  : 'text-slate-700 hover:bg-white'
              }`}
            >
              <FileSearch className="w-3.5 h-3.5" />
              <span>{lang === 'hi' ? 'जांच एवं जोखिम' : 'Scrutiny & Risk Console'}</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('split')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'split'
                  ? 'bg-[#0F2547] text-white shadow-xs'
                  : 'text-slate-700 hover:bg-white'
              }`}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>
                {lang === 'hi' ? 'द्वैत-सत्य विभाजन' : 'Dual-Truth Split View'}
                {selectedInstrumentId ? ` (#${selectedInstrumentId})` : ''}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('bank')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'bank'
                  ? 'bg-[#0F2547] text-white shadow-xs'
                  : 'text-slate-700 hover:bg-white'
              }`}
            >
              <Landmark className="w-3.5 h-3.5" />
              <span>{lang === 'hi' ? 'बैंक सत्यापन' : 'Blind Bank Portal'}</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('admin')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                activeTab === 'admin'
                  ? 'bg-[#0F2547] text-white shadow-xs'
                  : 'text-slate-700 hover:bg-white'
              }`}
            >
              <Settings className="w-3.5 h-3.5" />
              <span>{lang === 'hi' ? 'प्रशासन एवं ऑडिट' : 'Admin, Demo & Audit'}</span>
            </button>
          </nav>

          {/* Right Controls: Guided Tour + Notifications + 1-Click Role Switcher */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowDemoTour(!showDemoTour)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition cursor-pointer ${
                showDemoTour
                  ? 'bg-amber-500 text-slate-950 border-amber-600 shadow-xs'
                  : 'bg-amber-50 text-amber-900 border-amber-300 hover:bg-amber-100'
              }`}
              title="Launch Interactive 7-Scene Hackathon Walkthrough"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>6-Min Demo Tour</span>
            </button>

            {/* Notification Bell */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowNotifPopover(!showNotifPopover)}
                aria-label="Open notifications"
                className="relative p-2 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 cursor-pointer"
              >
                <Bell className="w-4 h-4" />
                {unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-600 text-white text-[10px] font-mono font-bold px-1.5 rounded-full">
                    {unreadCount}
                  </span>
                )}
              </button>

              {showNotifPopover && (
                <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-xl shadow-xl border border-slate-200 z-50 overflow-hidden">
                  <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-800">
                      Portal &amp; Simulated Email Notifications ({notifications.length})
                    </span>
                    <button
                      type="button"
                      onClick={onMarkAllRead}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-700 hover:underline cursor-pointer"
                    >
                      <CheckCheck className="w-3.5 h-3.5" />
                      Mark all read
                    </button>
                  </div>
                  <div className="max-h-72 overflow-y-auto divide-y divide-slate-100">
                    {notifications.length === 0 ? (
                      <p className="p-4 text-xs text-slate-500 text-center">
                        No notifications for this account yet.
                      </p>
                    ) : (
                      notifications.slice(0, 15).map((n) => (
                        <div
                          key={n.id}
                          className={`p-3 text-xs ${
                            n.read_at || n.is_read ? 'bg-white' : 'bg-blue-50/50'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2 mb-0.5">
                            <span className="font-semibold text-slate-900">
                              {n.title || n.subject}
                            </span>
                            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                              {n.channel}
                            </span>
                          </div>
                          <p className="text-slate-600 leading-relaxed">{n.body}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {onLogout && (
              <button
                type="button"
                onClick={onLogout}
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-red-50 hover:border-red-300 hover:text-red-700 text-slate-700 transition-colors"
                title="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" /> Sign out
              </button>
            )}

            {/* 1-Click Role Switcher */}
            <div className="relative flex items-center">
              <label htmlFor="role-switcher-select" className="sr-only">
                Switch active demo role account
              </label>
              <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-300 rounded-lg px-2.5 py-1">
                <UserCheck className="w-3.5 h-3.5 text-[#1D4ED8] shrink-0" />
                <select
                  id="role-switcher-select"
                  value={user?.email || 'officer@aicte-demo.in'}
                  disabled={switchingAccount}
                  onChange={(e) => onSwitchAccount(e.target.value)}
                  className="text-xs font-semibold text-slate-800 bg-transparent focus:outline-none pr-4 cursor-pointer max-w-[210px] truncate"
                >
                  {DEMO_ACCOUNTS.map((acc) => (
                    <option key={acc.email} value={acc.email}>
                      [{acc.role}] {acc.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-3 h-3 text-slate-500 pointer-events-none -ml-3" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Row 3: Slim AICTE Policy Updates & Active Role Context Strip */}
      <div className="bg-[#FFF8ED] border-t border-amber-200/80 px-4 sm:px-6 py-1.5 text-xs">
        <div className="max-w-[1440px] mx-auto flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-amber-950 truncate">
            <span className="inline-block px-2 py-0.5 rounded bg-amber-600 text-white font-bold text-[10px] uppercase tracking-wider shrink-0">
              AICTE Mandate
            </span>
            <span className="truncate font-medium">
              Approval Process Handbook: Joint FDR in favour of &ldquo;Member Secretary, AICTE&rdquo; with unconditional Bank Lien &amp; Dual-Truth CBS/Nodal verification.
            </span>
          </div>
          {user && (
            <div className="flex items-center gap-2 text-[11px] font-mono text-slate-700 shrink-0">
              <span>Active Session:</span>
              <span className="font-bold text-[#0F2547]">{user.full_name}</span>
              <span className="px-2 py-0.5 rounded-full bg-[#0F2547] text-white font-bold">
                {user.role}
              </span>
              {user.role === 'AUDITOR' && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 font-semibold">
                  <Lock className="w-3 h-3" /> Read-Only Enforced
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Modern Web Guidance: Light-Dismiss Dialog 1 — Important Note */}
      <dialog
        ref={noteDialogRef}
        closedby="any"
        aria-labelledby="important-note-title"
        className="m-auto rounded-2xl max-w-xl w-full p-0 bg-white shadow-2xl border border-slate-200 text-slate-900"
      >
        <div className="p-6">
          <div className="flex items-center gap-2.5 text-amber-700 mb-3">
            <AlertTriangle className="w-6 h-6 shrink-0" />
            <h2 id="important-note-title" className="text-lg font-display font-bold text-slate-900">
              Important Regulatory Note — AICTE Security Deposit FDRs
            </h2>
          </div>
          <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
            <p>
              <strong>1. Joint Holder &amp; Unconditional Lien:</strong> Every Fixed Deposit Receipt (FDR) submitted for New Institute Approval, Increase in Intake, or New Programme must be jointly held with <strong>Member Secretary, AICTE</strong> and accompanied by an official Bank Lien Letter.
            </p>
            <p>
              <strong>2. Point-of-Entry OCR &amp; 20-Rule Forgery Engine:</strong> Uploaded PDFs/scans are parsed immediately via OCR and cross-checked against 20 statutory and anomaly rules (including Rule <code>R15</code> Words-vs-Figures mismatch and Rule <code>R09</code> Cross-Institution Duplicate FDR detection).
            </p>
            <p>
              <strong>3. Guarded Release &amp; Two-Person Rule:</strong> Security Deposits cannot be released until maturity/tenure completion, zero open compliance/court cases, Scrutiny Officer recommendation, and Approving Authority sanction (strict separation of duties).
            </p>
          </div>
          <form method="dialog" className="mt-6 flex justify-end">
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-[#0F2547] text-white text-xs font-semibold hover:bg-slate-800 cursor-pointer"
            >
              Understood &amp; Close (or click outside / Esc)
            </button>
          </form>
        </div>
      </dialog>

      {/* Modern Web Guidance: Light-Dismiss Dialog 2 — Helpline & Support */}
      <dialog
        ref={helpDialogRef}
        closedby="any"
        aria-labelledby="helpline-dialog-title"
        className="m-auto rounded-2xl max-w-lg w-full p-0 bg-white shadow-2xl border border-slate-200 text-slate-900"
      >
        <div className="p-6">
          <div className="flex items-center gap-2.5 text-[#0F2547] mb-3">
            <HelpCircle className="w-6 h-6 shrink-0" />
            <h2 id="helpline-dialog-title" className="text-lg font-display font-bold">
              AICTE e-Governance FDR Cell — Helpline &amp; Demo Credentials
            </h2>
          </div>
          <div className="space-y-3 text-xs text-slate-700">
            <p className="text-sm">
              All demo accounts use password <code className="px-1.5 py-0.5 rounded bg-slate-100 font-bold">Password@123</code>. You can switch between any role with 1 click using the top-right Role Switcher dropdown:
            </p>
            <ul className="space-y-1.5 bg-slate-50 p-3 rounded-xl border border-slate-200 font-mono">
              <li>• college1@aicte-demo.in (INSTITUTION — Pune)</li>
              <li>• college5@aicte-demo.in (INSTITUTION — Locked HTTP 423)</li>
              <li>• college8@aicte-demo.in (INSTITUTION — Open Compliance Case)</li>
              <li>• officer@aicte-demo.in (SCRUTINY_OFFICER)</li>
              <li>• approver@aicte-demo.in (APPROVING_AUTHORITY)</li>
              <li>• ro.western@aicte-demo.in (REGIONAL_OFFICER)</li>
              <li>• bank.sbi@aicte-demo.in / bank.canara@aicte-demo.in (BANK)</li>
              <li>• admin@aicte-demo.in (ADMIN) / auditor@aicte-demo.in (AUDITOR)</li>
            </ul>
            <p className="text-slate-500">
              AICTE Headquarters: Nelson Mandela Marg, Vasant Kunj, New Delhi - 110070
            </p>
          </div>
          <form method="dialog" className="mt-5 flex justify-end">
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-[#0F2547] text-white text-xs font-semibold hover:bg-slate-800 cursor-pointer"
            >
              Close
            </button>
          </form>
        </div>
      </dialog>
    </header>
  );
};
