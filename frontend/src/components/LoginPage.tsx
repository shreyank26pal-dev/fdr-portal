import React, { useRef, useState } from 'react';
import {
  ShieldCheck,
  Mail,
  KeyRound,
  Eye,
  EyeOff,
  LogIn,
  Loader2,
  AlertTriangle,
  Smartphone,
  Info,
  ArrowLeft,
  Sparkles,
} from 'lucide-react';
import { DEMO_ACCOUNTS, loginWithCredentials } from '../api';
import { User } from '../types';

interface LoginPageProps {
  onLoggedIn: (user: User) => void;
  notice?: string | null;
  onBack?: () => void;
  initialEmail?: string;
  initialPassword?: string;
}

function friendlyError(err: any): { text: string; mfa: boolean } {
  const msg: string = err?.message || 'Sign-in failed';
  if (msg.includes('mfa_required')) return { text: 'Enter the 6-digit code from your authenticator app.', mfa: true };
  if (err?.status === 423) return { text: 'This account is locked after repeated failed attempts. Contact the administrator.', mfa: false };
  if (err?.status === 401) return { text: msg === 'Invalid OTP' ? 'That code is not valid. Try the latest one.' : 'Email or password is incorrect.', mfa: false };
  if (err?.status === 422) return { text: 'Enter a valid email address.', mfa: false };
  if (!err?.status) return { text: 'Cannot reach the server. Check that the backend is running.', mfa: false };
  return { text: msg, mfa: false };
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoggedIn, notice, onBack, initialEmail, initialPassword }) => {
  const [email, setEmail] = useState(initialEmail || '');
  const [password, setPassword] = useState(initialPassword || '');
  const [otp, setOtp] = useState('');
  const [needOtp, setNeedOtp] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const otpRef = useRef<HTMLInputElement>(null);

  const onSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await loginWithCredentials(email.trim().toLowerCase(), password, needOtp ? otp : undefined);
      onLoggedIn(data.user);
    } catch (err: any) {
      const f = friendlyError(err);
      setError(f.text);
      if (f.mfa) {
        setNeedOtp(true);
        setTimeout(() => otpRef.current?.focus(), 50);
      }
    } finally {
      setBusy(false);
    }
  };

  const inputCls =
    'w-full rounded-lg border border-slate-300 bg-white py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1D4ED8] focus:border-[#1D4ED8]';

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF7F2] text-[#0F172A]">
      <div className="aicte-rainbow-bar w-full" />

      <main id="main-content" className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          <div className="flex flex-col items-center text-center mb-6">
            <div className="w-12 h-12 rounded-xl bg-[#0F2547] flex items-center justify-center">
              <ShieldCheck className="w-7 h-7 text-amber-300" />
            </div>
            <h1 className="mt-3 text-2xl font-display font-extrabold">SecureDeposit</h1>
            <p className="text-sm text-slate-500">AICTE Security Deposit &amp; FDR Portal</p>
          </div>

          <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-display font-bold">Sign in</h2>

            {notice && (
              <div role="status" className="mt-4 flex gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <Info className="w-4 h-4 mt-0.5 shrink-0" /> {notice}
              </div>
            )}

            {/* Quick Demo Fill Buttons for Judges / Testing */}
            <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-slate-700 mb-2">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Quick Demo Sign-In (1-Click):
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { label: 'Scrutiny Officer', email: 'officer@aicte-demo.in' },
                  { label: 'Institution', email: 'college1@aicte-demo.in' },
                  { label: 'Approver', email: 'approver@aicte-demo.in' },
                  { label: 'Bank (SBI)', email: 'bank.sbi@aicte-demo.in' },
                  { label: 'Admin', email: 'admin@aicte-demo.in' },
                ].map((demo) => (
                  <button
                    key={demo.email}
                    type="button"
                    onClick={() => {
                      setEmail(demo.email);
                      setPassword('Password@123');
                      setError(null);
                    }}
                    className={`px-2 py-1 rounded text-[11px] font-medium border transition-colors ${
                      email === demo.email
                        ? 'bg-[#0F2547] text-white border-[#0F2547]'
                        : 'bg-white hover:bg-slate-100 text-slate-700 border-slate-300'
                    }`}
                  >
                    {demo.label}
                  </button>
                ))}
              </div>
            </div>

            <form onSubmit={onSubmit} className="mt-4 space-y-4" noValidate>
              <div>
                <label htmlFor="login-email" className="block text-sm font-semibold text-slate-700 mb-1.5">Email</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="login-email"
                    type="email"
                    autoComplete="username"
                    autoFocus
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={`${inputCls} pl-9 pr-3`}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="login-password" className="block text-sm font-semibold text-slate-700 mb-1.5">Password</label>
                <div className="relative">
                  <KeyRound className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="login-password"
                    type={showPw ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={`${inputCls} pl-9 pr-10`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    aria-label={showPw ? 'Hide password' : 'Show password'}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded text-slate-500 hover:text-slate-800"
                  >
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Demo password for all accounts: <code className="font-mono font-semibold text-slate-700 bg-slate-100 px-1 py-0.5 rounded">Password@123</code>
                </p>
              </div>

              {needOtp && (
                <div>
                  <label htmlFor="login-otp" className="block text-sm font-semibold text-slate-700 mb-1.5">Authenticator code</label>
                  <div className="relative">
                    <Smartphone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      id="login-otp"
                      ref={otpRef}
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      value={otp}
                      onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                      placeholder="6-digit code"
                      className={`${inputCls} pl-9 pr-3 font-mono tracking-[0.3em]`}
                    />
                  </div>
                </div>
              )}

              {error && (
                <div role="alert" className="flex gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> {error}
                </div>
              )}

              <button
                type="submit"
                disabled={busy || !email || !password || (needOtp && otp.length < 6)}
                className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-[#0F2547] hover:bg-[#1E3A8A] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 text-sm transition-colors"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogIn className="w-4 h-4" />}
                {busy ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
          </div>

          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="mt-4 w-full inline-flex items-center justify-center gap-1.5 text-sm text-slate-600 hover:text-[#1D4ED8]"
            >
              <ArrowLeft className="w-4 h-4" /> Back to home
            </button>
          )}
          <p className="mt-6 text-center text-xs text-slate-500">
            All India Council for Technical Education • Ministry of Education
          </p>
        </div>
      </main>
    </div>
  );
};
