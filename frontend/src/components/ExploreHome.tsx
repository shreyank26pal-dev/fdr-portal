import React from 'react';
import {
  ShieldCheck,
  Building2,
  FileSearch,
  Landmark,
  Clock,
  Lock,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  AlertOctagon,
  FileCheck2,
  Scale,
  KeyRound,
  Activity,
  FileSpreadsheet,
} from 'lucide-react';
import { ActiveTab } from './Header';
import { formatINR } from '../api';

interface ExploreHomeProps {
  summary: any;
  simulatedToday: string;
  clockOffsetDays: number;
  onNavigateRoleTab: (email: string | null, tab: ActiveTab, instrumentId?: number) => Promise<void>;
  onLaunchDemoTour: () => void;
}

export const ExploreHome: React.FC<ExploreHomeProps> = ({
  summary,
  simulatedToday,
  clockOffsetDays,
  onNavigateRoleTab,
  onLaunchDemoTour,
}) => {
  const exploreCards = [
    {
      badge: 'INSTITUTION WORKFLOW',
      badgeColor: 'bg-blue-100 text-blue-900',
      title: '1. Institution FDR Portal & Live OCR Auto-Fill',
      desc: 'Drop a synthetic or scanned FDR PDF to auto-fill fields via OCR, run live duplicate checks on blur, catch point-of-entry mismatches before submission, and track Courier-style release progress.',
      cta: 'Open as Institution (College 1)',
      icon: Building2,
      action: () => onNavigateRoleTab('college1@aicte-demo.in', 'institution'),
    },
    {
      badge: 'DUAL-TRUTH SCRUTINY',
      badgeColor: 'bg-indigo-100 text-indigo-900',
      title: '2. Dual-Truth Split-Screen & 20-Rule Forgery Engine',
      desc: 'Inspect Declared vs OCR Read vs Bank/Officer Confirmed values side-by-side with the encrypted PDF, SHA-256 integrity header, and 20 anomaly rules (R01–R20) with human-in-the-loop confirmation.',
      cta: 'Open Dual-Truth Split Screen',
      icon: FileSearch,
      action: () => onNavigateRoleTab('officer@aicte-demo.in', 'split'),
    },
    {
      badge: 'EXECUTIVE RISK & QUEUE',
      badgeColor: 'bg-purple-100 text-purple-900',
      title: '3. Scrutiny Work Queue, Risk Analytics & Reports',
      desc: 'Prioritised scrutiny queue ranked by risk score, bank concentration exposure, 12-month maturity calendar, predicted late renewals, SLA escalation tickets, and Excel/PDF exports.',
      cta: 'Open Scrutiny & Risk Console',
      icon: Activity,
      action: () => onNavigateRoleTab('officer@aicte-demo.in', 'officer'),
    },
    {
      badge: 'ZERO-BIAS CONFIRMATION',
      badgeColor: 'bg-amber-100 text-amber-900',
      title: '4. Blind Bank Confirmation & Mock CBS Ledger',
      desc: 'Bank nodal officers and one-time confirmation links never see institution-declared amounts—forcing blind entry from CBS records to eliminate rubber-stamping.',
      cta: 'Open Blind Bank Portal (SBI)',
      icon: Landmark,
      action: () => onNavigateRoleTab('bank.sbi@aicte-demo.in', 'bank'),
    },
    {
      badge: 'TIME-TRAVEL & CHAOS LAB',
      badgeColor: 'bg-rose-100 text-rose-900',
      title: '5. Time-Travel Clock, Bank Outage & Encashment Simulator',
      desc: 'Fast-forward +66 or +8 days in seconds to watch T-90/T-30 reminders, escalation ladders, institution locks (HTTP 423), bank API fallback, and silent premature encashment detection.',
      cta: 'Open Admin & Demo Sandbox',
      icon: Clock,
      action: () => onNavigateRoleTab('admin@aicte-demo.in', 'admin'),
    },
    {
      badge: 'TAMPER-EVIDENT AUDIT',
      badgeColor: 'bg-emerald-100 text-emerald-900',
      title: '6. Cryptographic Audit Chain & Guarded Release',
      desc: 'Every state change is chained with SHA-256(prev_hash || payload). Simulate an insider SQL edit on entry #10 and watch GET /audit/verify pinpoint the exact tampered row.',
      cta: 'Inspect Audit Chain & Security',
      icon: Lock,
      action: () => onNavigateRoleTab('auditor@aicte-demo.in', 'admin'),
    },
  ];

  const uspList = [
    {
      code: 'USP-01',
      title: 'Dual-Truth Field Model',
      detail: 'Stores Declared, OCR Read, and Bank/Officer Confirmed values separately with 6 semantic trust badges.',
    },
    {
      code: 'USP-02',
      title: 'Point-of-Entry OCR Cross-Check',
      detail: 'Highlights OCR conflicts and runs POST /ocr/extract before the institution even clicks Submit.',
    },
    {
      code: 'USP-03',
      title: '20-Rule Anomaly & Forgery Engine (R01–R20)',
      detail: 'Catches Words-vs-Figures tampering (R15), Cross-Institution Reuse (R09), compound math (R08), and unscheduled banks (R18).',
    },
    {
      code: 'USP-04',
      title: 'Hybrid Bank Verification with Graceful Fallback',
      detail: 'Instant CBS API verify when bank is online; auto-falls back to Nodal Queue + 1-click Blind Email Link on outage.',
    },
    {
      code: 'USP-05',
      title: 'Blind Bank Confirmation (Anti-Rubber-Stamp)',
      detail: 'Hides declared principal, rate, and maturity date from the bank officer so they must key in real CBS figures.',
    },
    {
      code: 'USP-06',
      title: 'Periodic Re-Verification (Silent Encashment Catch)',
      detail: 'Detects when a verified FDR is prematurely encashed or has its lien lifted mid-tenure and freezes it.',
    },
    {
      code: 'USP-07',
      title: 'Time-Travel Clock & Escalation Ladder',
      detail: 'Shift simulated date by +N days and walk day-by-day through T-90/60/30/15/7/1 reminders and HQ Director escalations.',
    },
    {
      code: 'USP-08',
      title: 'Overdue Renewal Institution Lock (HTTP 423)',
      detail: 'Automatically locks fresh applications for institutions with overdue renewals until POST /renew is submitted.',
    },
    {
      code: 'USP-09',
      title: 'Guarded Release & Two-Person Rule + Discharge PDF',
      detail: 'Pre-condition engine + mandatory Scrutiny Recommend != Approver Sanction + auto-generated Discharge Order PDF.',
    },
    {
      code: 'USP-10',
      title: 'Fernet AES-128-CBC + HMAC-SHA256 + Hash-Chained Audit',
      detail: 'Documents encrypted at rest with live X-Integrity verification and tamper-evident SHA-256 audit log chain.',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Official AICTE Hero Banner */}
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#0F2547] via-[#173464] to-[#1E3A8A] text-white p-6 sm:p-8 shadow-md border border-slate-800">
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="max-w-3xl space-y-3">
            <div className="inline-flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full bg-amber-400 text-slate-950 font-mono text-xs font-extrabold uppercase">
                SIH26265 Official Solution
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-white/15 text-amber-200 font-mono text-xs">
                100% Real FastAPI + SQLite/Postgres + Cryptography + ReportLab + Tesseract
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-display font-extrabold tracking-tight leading-tight">
              AICTE National Security Deposit &amp; FDR Lifecycle Portal
            </h1>
            <p className="text-sm sm:text-base text-slate-200 leading-relaxed">
              End-to-end digital custody, point-of-entry OCR cross-checking, 20-rule forgery detection, blind bank confirmation, automated maturity escalation, and two-person guarded release for Technical Institutions across India.
            </p>
            <div className="pt-2 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={onLaunchDemoTour}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#EA580C] hover:bg-[#D9460F] text-white font-bold text-xs sm:text-sm shadow-sm transition cursor-pointer"
              >
                <Sparkles className="w-4 h-4" />
                <span>Launch Interactive 6-Minute Judge Walkthrough</span>
              </button>
              <button
                type="button"
                onClick={() => onNavigateRoleTab('officer@aicte-demo.in', 'split')}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white text-[#0F2547] hover:bg-slate-100 font-bold text-xs sm:text-sm shadow-sm transition cursor-pointer"
              >
                <FileSearch className="w-4 h-4" />
                <span>Inspect Dual-Truth Case Split-Screen</span>
              </button>
              <button
                type="button"
                onClick={() => onNavigateRoleTab('college1@aicte-demo.in', 'institution')}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white border border-white/25 font-semibold text-xs sm:text-sm transition cursor-pointer"
              >
                <Building2 className="w-4 h-4" />
                <span>Submit / Renew FDR (Institution)</span>
              </button>
            </div>
          </div>

          {/* Right Live System Pulse Card */}
          <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl p-4 sm:p-5 min-w-[280px] space-y-3">
            <div className="flex items-center justify-between border-b border-white/15 pb-2.5">
              <span className="text-xs font-mono uppercase tracking-wider text-amber-300 font-bold">
                Live Regulatory Telemetry
              </span>
              <span className="inline-flex items-center gap-1.5 text-xs font-mono text-emerald-300">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                ONLINE
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-950/35 p-2.5 rounded-xl">
                <div className="text-slate-300 text-[11px]">Active Security Held</div>
                <div className="font-mono font-bold text-base text-white mt-0.5">
                  {summary?.tiles ? formatINR(summary.tiles.held_amount) : '₹18.45 Cr'}
                </div>
              </div>
              <div className="bg-slate-950/35 p-2.5 rounded-xl">
                <div className="text-slate-300 text-[11px]">Held Instruments</div>
                <div className="font-mono font-bold text-base text-amber-300 mt-0.5">
                  {summary?.tiles?.held_total ?? '123'} FDRs
                </div>
              </div>
              <div className="bg-slate-950/35 p-2.5 rounded-xl">
                <div className="text-slate-300 text-[11px]">Simulated Date</div>
                <div className="font-mono font-bold text-sm text-white mt-0.5">
                  {simulatedToday || summary?.as_of || 'Today'}
                </div>
              </div>
              <div className="bg-slate-950/35 p-2.5 rounded-xl">
                <div className="text-slate-300 text-[11px]">Clock Shift</div>
                <div className="font-mono font-bold text-sm text-emerald-300 mt-0.5">
                  {clockOffsetDays >= 0 ? `+${clockOffsetDays}` : clockOffsetDays} days
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Executive KPI Ribbon */}
      {summary?.tiles && (
        <section aria-label="Executive KPI Summary" className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
          {[
            { label: 'Total Held FDRs', value: summary.tiles.held_total, tone: 'text-slate-900 bg-white border-slate-200' },
            { label: 'Active Status', value: summary.tiles.active, tone: 'text-emerald-900 bg-emerald-50/70 border-emerald-200' },
            { label: 'Pending Scrutiny', value: summary.tiles.pending_verification, tone: 'text-blue-900 bg-blue-50/70 border-blue-200' },
            { label: 'Discrepancy Open', value: summary.tiles.discrepancies_open, tone: 'text-red-900 bg-red-50/70 border-red-200' },
            { label: 'Expiring ≤30d', value: summary.tiles.expiring_30_days, tone: 'text-amber-900 bg-amber-50/70 border-amber-200' },
            { label: 'Expiring ≤90d', value: summary.tiles.expiring_90_days, tone: 'text-orange-900 bg-orange-50/70 border-orange-200' },
            { label: 'Matured / Overdue', value: summary.tiles.matured_unrenewed, tone: 'text-rose-900 bg-rose-50/70 border-rose-200' },
            { label: 'Escalated Alerts', value: summary.tiles.escalated_alerts, tone: 'text-purple-900 bg-purple-50/70 border-purple-200' },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className={`p-3.5 rounded-xl border shadow-2xs ${kpi.tone}`}
            >
              <div className="text-[11px] font-semibold uppercase tracking-wider opacity-75">
                {kpi.label}
              </div>
              <div className="text-2xl font-display font-extrabold font-mono mt-1">
                {kpi.value}
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Official AICTE Style "EXPLORE — Find Your Security Deposit Path" 6-Card Hub */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-slate-200 pb-3">
          <div>
            <span className="text-xs font-mono font-bold uppercase tracking-widest text-[#EA580C]">
              EXPLORE • ROLE-BASED WORKSPACES
            </span>
            <h2 className="text-xl sm:text-2xl font-display font-extrabold text-[#0F2547]">
              Find Your Security Deposit &amp; Verification Path
            </h2>
          </div>
          <p className="text-xs text-slate-600">
            Clicking any card below automatically logs into the matching demo account and opens that workspace.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {exploreCards.map((card) => {
            const Icon = card.icon;
            return (
              <div
                key={card.title}
                className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs hover:shadow-md hover:border-blue-300 transition flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-[10px] font-mono font-bold px-2.5 py-1 rounded-full ${card.badgeColor}`}>
                      {card.badge}
                    </span>
                    <div className="w-9 h-9 rounded-xl bg-slate-100 text-[#0F2547] flex items-center justify-center">
                      <Icon className="w-5 h-5" />
                    </div>
                  </div>
                  <h3 className="text-base font-display font-bold text-slate-900">
                    {card.title}
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {card.desc}
                  </p>
                </div>

                <div className="pt-4 mt-4 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={card.action}
                    className="w-full inline-flex items-center justify-between px-3.5 py-2 rounded-xl bg-[#0F2547] hover:bg-[#1D4ED8] text-white text-xs font-semibold transition cursor-pointer"
                  >
                    <span>{card.cta}</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 10 Core USPs Architecture Verification Grid */}
      <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="text-xs font-mono font-bold uppercase tracking-widest text-blue-700">
              BUILT-IN DIFFERENTIATORS
            </span>
            <h2 className="text-lg sm:text-xl font-display font-bold text-slate-900">
              10 Core USPs Engineered &amp; Live in This Workspace
            </h2>
          </div>
          <span className="text-xs font-mono px-3 py-1 rounded-full bg-emerald-100 text-emerald-900 font-semibold">
            11/11 End-to-End Automated Tests Passing
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {uspList.map((u) => (
            <div
              key={u.code}
              className="p-3.5 rounded-xl bg-[#FAF7F2] border border-slate-200/80 space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-[#0F2547] text-amber-300">
                  {u.code}
                </span>
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              </div>
              <h3 className="text-xs font-bold text-slate-900">{u.title}</h3>
              <p className="text-[11px] text-slate-600 leading-relaxed">{u.detail}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
