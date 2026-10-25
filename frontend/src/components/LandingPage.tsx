import React from 'react';
import {
  ShieldCheck,
  LogIn,
  ArrowRight,
  FileSpreadsheet,
  BellOff,
  FileWarning,
  HelpCircle,
  ScanSearch,
  Landmark,
  BellRing,
  Link2,
  Undo2,
  FileLock2,
  Building2,
  UserCheck,
  BadgeCheck,
  CircleDot,
} from 'lucide-react';
import { DEMO_ACCOUNTS } from '../api';

interface LandingPageProps {
  onSignIn: (prefillEmail?: string) => void;
}

const GAPS = [
  { icon: FileSpreadsheet, title: 'Scattered records', text: 'FDRs live in Excel sheets, emails and scanned files, with no single record per institution or per deposit.' },
  { icon: BellOff, title: 'Missed maturity dates', text: 'Nobody is reminded before an FDR matures, so the security can quietly lapse.' },
  { icon: FileWarning, title: 'Hard to tell real from fake', text: 'An edited PDF looks like a genuine one, and checking with the bank means manual follow-up.' },
  { icon: HelpCircle, title: 'Refunds in the dark', text: 'Release and refund requests are tracked over phone and email, with no clear status.' },
];

const FEATURES = [
  { icon: ScanSearch, title: 'Checked at the point of entry', text: 'The uploaded FDR is read automatically and compared with the typed details before submission.' },
  { icon: Landmark, title: 'Declared vs bank-verified', text: 'Banks confirm each deposit independently. Every field shows whether it is only declared or bank-verified.' },
  { icon: BadgeCheck, title: 'Fraud signals, human decisions', text: '20 explainable rules flag duplicates, re-used documents and altered amounts. An officer makes the final call.' },
  { icon: BellRing, title: 'Reminders that escalate', text: 'Alerts at 90, 60, 30 and 7 days. Unresolved cases move up to senior officers automatically.' },
  { icon: Link2, title: 'One history per institution', text: 'Renewals are linked to the deposit they replace, so the full security history stays unbroken across years.' },
  { icon: Undo2, title: 'Guarded release', text: 'Release is checked against open cases and needs two different officials. Institutions track it step by step.' },
];

const STEPS = [
  { title: 'Submit', text: 'Institution uploads the FDR and lien letter; details are pre-filled and cross-checked.' },
  { title: 'Verify', text: 'Officer reviews flags and confirms the deposit with the bank.' },
  { title: 'Approve', text: 'Approving authority signs off and the deposit becomes active.' },
  { title: 'Monitor', text: 'Reminders and escalation run until the deposit is renewed.' },
  { title: 'Release', text: 'Pre-checked, two-person approval and an auto-generated discharge letter.' },
];

const ROLES = [
  { icon: Building2, title: 'Institutions', text: 'Submit, renew and track FDRs; see deadlines and what is needed.' },
  { icon: UserCheck, title: 'AICTE officials', text: 'Scrutiny officers, regional officers and approving authorities.' },
  { icon: Landmark, title: 'Bank nodal officers', text: 'Confirm deposits without seeing what was declared.' },
  { icon: FileLock2, title: 'Auditors', text: 'Read-only access to a tamper-evident audit trail.' },
];

const ROLE_LABEL: Record<string, string> = {
  INSTITUTION: 'Institution',
  SCRUTINY_OFFICER: 'Scrutiny Officer',
  REGIONAL_OFFICER: 'Regional Officer',
  APPROVING_AUTHORITY: 'Approving Authority',
  BANK: 'Bank',
  ADMIN: 'Admin',
  AUDITOR: 'Auditor',
};

export const LandingPage: React.FC<LandingPageProps> = ({ onSignIn }) => {
  return (
    <div className="min-h-screen flex flex-col bg-[#FAF7F2] text-[#0F172A]">
      {/* Government strip */}
      <div className="bg-[#0F2547] text-white text-[11px] sm:text-xs">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-1.5 flex flex-wrap items-center justify-between gap-2">
          <span className="font-semibold">भारत सरकार | Government of India • Ministry of Education</span>
          <span className="font-mono text-amber-300">SIH26265</span>
        </div>
      </div>
      <div className="aicte-rainbow-bar w-full" />

      {/* Top bar */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <a href="#top" className="flex items-center gap-2.5">
            <span className="w-9 h-9 rounded-lg bg-[#0F2547] flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-amber-300" />
            </span>
            <span>
              <span className="block font-display font-extrabold leading-tight">SecureDeposit</span>
              <span className="block text-[11px] text-slate-500 leading-tight">AICTE Security Deposit &amp; FDR Portal</span>
            </span>
          </a>
          <nav className="hidden md:flex items-center gap-6 text-sm text-slate-600">
            <a href="#problem" className="hover:text-[#1D4ED8]">The problem</a>
            <a href="#features" className="hover:text-[#1D4ED8]">Features</a>
            <a href="#how" className="hover:text-[#1D4ED8]">How it works</a>
            <a href="#demo" className="hover:text-[#1D4ED8]">Demo access</a>
          </nav>
          <button
            type="button"
            onClick={() => onSignIn()}
            className="inline-flex items-center gap-2 rounded-lg bg-[#0F2547] hover:bg-[#1E3A8A] text-white text-sm font-semibold px-4 py-2 transition-colors"
          >
            <LogIn className="w-4 h-4" /> Sign in
          </button>
        </div>
      </header>

      <main id="main-content" className="flex-1">
        {/* Hero */}
        <section id="top" className="bg-gradient-to-br from-[#0F2547] to-[#1E3A8A] text-white">
          <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-14 lg:py-20 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-7">
              <p className="text-xs font-bold uppercase tracking-wider text-amber-300">For the AICTE Regulation Bureau</p>
              <h1 className="mt-3 text-3xl sm:text-4xl lg:text-5xl font-display font-extrabold leading-tight">
                Every security deposit, tracked from submission to release.
              </h1>
              <p className="mt-5 text-base sm:text-lg text-blue-100 leading-relaxed max-w-2xl">
                One portal for the Fixed Deposit Receipts that technical institutions lodge with AICTE. It verifies
                each one with the bank, watches every maturity date, and keeps a record that cannot be quietly altered.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => onSignIn()}
                  className="inline-flex items-center gap-2 rounded-lg bg-amber-400 hover:bg-amber-300 text-[#0F2547] font-bold px-5 py-3 transition-colors"
                >
                  Sign in to the portal <ArrowRight className="w-4 h-4" />
                </button>
                <a
                  href="#how"
                  className="inline-flex items-center gap-2 rounded-lg border border-white/30 hover:bg-white/10 text-white font-semibold px-5 py-3 transition-colors"
                >
                  How it works
                </a>
              </div>
            </div>

            {/* Illustrative record card */}
            <div className="lg:col-span-5">
              <div className="rounded-2xl bg-white text-slate-900 shadow-xl p-5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-slate-500">Example record</span>
                  <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">ACTIVE</span>
                </div>
                <p className="mt-2 font-display font-bold">FDR 40112233445 • ₹25,00,000</p>
                <p className="text-xs text-slate-500">State Bank of India • matures 16-10-2029</p>
                <table className="mt-4 w-full text-xs">
                  <thead>
                    <tr className="text-left text-slate-500">
                      <th className="font-semibold pb-1.5">Field</th>
                      <th className="font-semibold pb-1.5">Declared</th>
                      <th className="font-semibold pb-1.5 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {[
                      ['Amount', '25,00,000', 'Bank-verified', 'bg-emerald-100 text-emerald-800'],
                      ['Maturity date', '16-10-2029', 'Bank-verified', 'bg-emerald-100 text-emerald-800'],
                      ['Lien to AICTE', 'Yes', 'Bank-verified', 'bg-emerald-100 text-emerald-800'],
                      ['Depositor', 'Demo Institute', 'Declared', 'bg-slate-100 text-slate-700'],
                    ].map(([f, v, b, c]) => (
                      <tr key={f}>
                        <td className="py-1.5 text-slate-600">{f}</td>
                        <td className="py-1.5 font-mono">{v}</td>
                        <td className="py-1.5 text-right">
                          <span className={`px-1.5 py-0.5 rounded font-semibold ${c}`}>{b}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-4 flex items-center gap-2 text-[11px] text-slate-500">
                  <CircleDot className="w-3 h-3 text-amber-500" /> Next reminder: 90 days before maturity
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Problem */}
        <section id="problem" className="max-w-[1200px] mx-auto px-4 sm:px-6 py-14">
          <h2 className="text-2xl sm:text-3xl font-display font-extrabold">The problem today</h2>
          <p className="mt-2 text-slate-600 max-w-3xl">
            Institutions give AICTE security deposits as part of approval. Managing them by hand leaves four gaps.
          </p>
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {GAPS.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-2xl bg-white border border-slate-200 p-5">
                <Icon className="w-5 h-5 text-red-600" />
                <h3 className="mt-3 font-display font-bold">{title}</h3>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section id="features" className="bg-white border-y border-slate-200">
          <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-14">
            <h2 className="text-2xl sm:text-3xl font-display font-extrabold">What SecureDeposit does</h2>
            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <div key={title} className="rounded-2xl border border-slate-200 p-5">
                  <span className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
                    <Icon className="w-5 h-5 text-[#1D4ED8]" />
                  </span>
                  <h3 className="mt-3 font-display font-bold">{title}</h3>
                  <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="max-w-[1200px] mx-auto px-4 sm:px-6 py-14">
          <h2 className="text-2xl sm:text-3xl font-display font-extrabold">How it works</h2>
          <ol className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {STEPS.map((s, i) => (
              <li key={s.title} className="rounded-2xl bg-white border border-slate-200 p-5">
                <span className="w-8 h-8 rounded-full bg-[#0F2547] text-white text-sm font-bold flex items-center justify-center">
                  {i + 1}
                </span>
                <h3 className="mt-3 font-display font-bold">{s.title}</h3>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{s.text}</p>
              </li>
            ))}
          </ol>

          <h3 className="mt-14 text-xl font-display font-extrabold">Who uses it</h3>
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {ROLES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-2xl bg-white border border-slate-200 p-5">
                <Icon className="w-5 h-5 text-amber-600" />
                <h4 className="mt-3 font-display font-bold">{title}</h4>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Demo access */}
        <section id="demo" className="bg-white border-t border-slate-200">
          <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-14">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-2xl sm:text-3xl font-display font-extrabold">Demo access</h2>
                <p className="mt-2 text-slate-600">
                  For judges and testing. All accounts use the password{' '}
                  <code className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800">Password@123</code>.
                </p>
              </div>
            </div>
            <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-600">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Role</th>
                    <th className="px-4 py-2.5 font-semibold">Account</th>
                    <th className="px-4 py-2.5 font-semibold hidden md:table-cell">Email</th>
                    <th className="px-4 py-2.5" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {DEMO_ACCOUNTS.map((acc) => (
                    <tr key={acc.email}>
                      <td className="px-4 py-2.5">
                        <span className={`inline-block text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded border ${acc.badgeColor}`}>
                          {ROLE_LABEL[acc.role] || acc.role}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-800">{acc.label}</td>
                      <td className="px-4 py-2.5 font-mono text-xs text-slate-500 hidden md:table-cell">{acc.email}</td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          type="button"
                          onClick={() => onSignIn(acc.email)}
                          className="inline-flex items-center gap-1 text-sm font-semibold text-[#1D4ED8] hover:underline whitespace-nowrap"
                        >
                          Sign in as <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-[#0F2547] text-slate-300 text-xs">
        <div className="aicte-rainbow-bar w-full" />
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-5 flex flex-wrap justify-between gap-2">
          <span>All India Council for Technical Education • Ministry of Education, Government of India</span>
          <span className="font-mono text-slate-400">Prototype with synthetic data. Not an official AICTE system.</span>
        </div>
      </footer>
    </div>
  );
};
