import React, { useEffect, useState } from 'react';
import {
  Clock,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Scale,
  RefreshCw,
  FastForward,
  RotateCcw,
  Zap,
  Lock,
  CheckCircle2,
  AlertOctagon,
} from 'lucide-react';
import { apiFetch } from '../api';
import { User } from '../types';

interface AdminAuditConsoleProps {
  user: User | null;
  simulatedToday: string;
  clockOffsetDays: number;
  onSwitchAccount: (email: string) => Promise<void>;
  onRefreshGlobal: () => void;
  onInspectInstrument: (id: number) => void;
}

export const AdminAuditConsole: React.FC<AdminAuditConsoleProps> = ({
  user,
  simulatedToday,
  clockOffsetDays,
  onSwitchAccount,
  onRefreshGlobal,
  onInspectInstrument,
}) => {
  const [subTab, setSubTab] = useState<'sandbox' | 'audit' | 'rules' | 'cases'>('sandbox');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  // Time-travel events
  const [customDays, setCustomDays] = useState('30');
  const [clockEvents, setClockEvents] = useState<any[]>([]);

  // Audit chain state
  const [auditVerify, setAuditVerify] = useState<any | null>(null);
  const [auditEntries, setAuditEntries] = useState<any[]>([]);

  // Rules & config state
  const [configs, setConfigs] = useState<any[]>([]);
  const [rulesCatalogue, setRulesCatalogue] = useState<any[]>([]);

  // Compliance cases state
  const [cases, setCases] = useState<any[]>([]);

  const loadAuditData = async () => {
    try {
      const [v, list] = await Promise.all([
        apiFetch('/audit/verify'),
        apiFetch<any[]>('/audit?page_size=40'),
      ]);
      setAuditVerify(v);
      setAuditEntries(Array.isArray(list) ? list : (list as any)?.items || []);
    } catch {
      // ignore
    }
  };

  const loadRulesAndConfig = async () => {
    try {
      const r = await apiFetch('/meta/rules');
      setRulesCatalogue(r || []);
      if (user?.role === 'ADMIN') {
        const c = await apiFetch('/admin/config');
        setConfigs(c || []);
      }
    } catch {
      // ignore
    }
  };

  const loadComplianceCases = async () => {
    try {
      const data = await apiFetch('/compliance-cases');
      setCases(data || []);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadAuditData();
    loadRulesAndConfig();
    loadComplianceCases();
  }, [user?.email, subTab]);

  const ensureAdminThen = async (fn: () => Promise<void>) => {
    setError(null);
    setBanner(null);
    if (user?.role !== 'ADMIN') {
      await onSwitchAccount('admin@aicte-demo.in');
    }
    await fn();
  };

  const handleShiftClock = async (days: number) => {
    await ensureAdminThen(async () => {
      setBusy(`Shifting simulated clock by +${days} days and running daily scheduler...`);
      try {
        const res = await apiFetch('/admin/demo/clock', {
          method: 'POST',
          body: JSON.stringify({ days, run_jobs: true }),
        });
        setClockEvents(res.events || []);
        onRefreshGlobal();
        setBanner(
          `Clock shifted to ${res.today} (offset +${res.offset_days}d). ${
            (res.events || []).length
          } active event days recorded!`
        );
      } catch (e: any) {
        setError(e.message);
      } finally {
        setBusy(null);
      }
    });
  };

  const handleResetClock = async () => {
    await ensureAdminThen(async () => {
      setBusy('Resetting clock offset to 0...');
      try {
        const res = await apiFetch('/admin/demo/clock/reset', { method: 'POST' });
        setClockEvents([]);
        onRefreshGlobal();
        setBanner(`Clock reset to real today (${res.today}).`);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setBusy(null);
      }
    });
  };

  const handleSimulatePrematureEncashment = async () => {
    await ensureAdminThen(async () => {
      setBusy('Simulating premature encashment at Bank CBS & running re-verification job...');
      try {
        const records = await apiFetch<any[]>('/mock-bank/v1/records');
        const target = records.find((r) => r.status === 'ACTIVE') || records[0];
        if (!target) throw new Error('No CBS record available');

        await apiFetch(`/mock-bank/v1/records/${target.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            status: 'ENCASHED',
            lien_marked: false,
          }),
        });

        const jobRes = await apiFetch('/admin/jobs/run?force_reverify=true', {
          method: 'POST',
        });
        onRefreshGlobal();
        setBanner(
          `Simulated silent premature encashment on CBS Record #${target.id} (${target.fdr_number})! Re-verification caught ${
            jobRes?.reverification?.changed?.length || 1
          } encashed/altered FDR(s) and opened CRITICAL alert!`
        );
      } catch (e: any) {
        setError(e.message);
      } finally {
        setBusy(null);
      }
    });
  };

  const handleTamperAudit = async () => {
    await ensureAdminThen(async () => {
      setBusy('Simulating insider SQL tampering on audit_log row #10...');
      try {
        await apiFetch('/admin/demo/tamper-audit/10', { method: 'POST' });
        await loadAuditData();
        setSubTab('audit');
        setBanner(
          'Tampered with audit_log entry #10 via raw SQL! Notice how GET /api/v1/admin/audit/verify immediately pinpoints Broken Entry #10 below.'
        );
      } catch (e: any) {
        setError(e.message);
      } finally {
        setBusy(null);
      }
    });
  };

  const handleRestoreAudit = async () => {
    await ensureAdminThen(async () => {
      setBusy('Restoring audit_log row #10 to original value...');
      try {
        await apiFetch('/admin/demo/tamper-audit/10/restore', { method: 'POST' });
        await loadAuditData();
        setBanner('Restored audit_log row #10! Hash chain integrity is 100% VALID again.');
      } catch (e: any) {
        setError(e.message);
      } finally {
        setBusy(null);
      }
    });
  };

  const handleReseedGoldenDataset = async () => {
    await ensureAdminThen(async () => {
      setBusy('Re-seeding entire database to golden demo state (takes ~15s)...');
      try {
        await apiFetch('/admin/demo/reseed', { method: 'POST' });
        setClockEvents([]);
        await loadAuditData();
        await loadComplianceCases();
        onRefreshGlobal();
        setBanner(
          'Golden Demo Dataset Restored! All 40 institutions, 123 FDRs, and hash-chained audit logs are back to their initial state.'
        );
      } catch (e: any) {
        setError(e.message);
      } finally {
        setBusy(null);
      }
    });
  };

  const handleCloseComplianceCase = async (caseId: number) => {
    await ensureAdminThen(async () => {
      setBusy(`Closing compliance case #${caseId}...`);
      try {
        await apiFetch(`/compliance-cases/${caseId}/close`, {
          method: 'POST',
          body: JSON.stringify({
            note: 'Cleared by AICTE Standing Hearing Committee.',
          }),
        });
        await loadComplianceCases();
        onRefreshGlobal();
        setBanner(
          `Compliance Case #${caseId} CLOSED! Institution 8 can now submit a Release / Refund request without being blocked.`
        );
      } catch (e: any) {
        setError(e.message);
      } finally {
        setBusy(null);
      }
    });
  };

  const handleOverrideRuleSeverity = async (ruleId: string, newSeverity: string) => {
    await ensureAdminThen(async () => {
      try {
        const currentCfg = configs.find((c) => c.key === 'rule_overrides')?.value || {};
        const updated = {
          ...currentCfg,
          [ruleId]: { enabled: true, severity: newSeverity },
        };
        await apiFetch('/admin/config/rule_overrides', {
          method: 'PUT',
          body: JSON.stringify({ value: updated }),
        });
        await loadRulesAndConfig();
        setBanner(`Updated Rule ${ruleId} live severity override to ${newSeverity} (no code redeploy needed).`);
      } catch (e: any) {
        setError(e.message);
      }
    });
  };

  return (
    <div className="space-y-6">
      {/* Header & Sub-Tabs */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          {[
            { id: 'sandbox', label: 'Time-Travel Clock & Chaos Lab', icon: Clock },
            { id: 'audit', label: 'Cryptographic SHA-256 Audit Chain', icon: Lock },
            { id: 'rules', label: '20-Rule Engine & Live Config', icon: Sliders },
            { id: 'cases', label: 'Compliance & Vigilance Cases', icon: Scale },
          ].map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setSubTab(t.id as any)}
                className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold cursor-pointer ${
                  subTab === t.id
                    ? 'bg-[#0F2547] text-white shadow-xs'
                    : 'bg-slate-50 text-slate-700 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 text-xs">
          <button
            type="button"
            onClick={() => onSwitchAccount('admin@aicte-demo.in')}
            className={`px-3 py-1.5 rounded-lg font-bold border cursor-pointer ${
              user?.role === 'ADMIN'
                ? 'bg-[#0F2547] text-white border-[#0F2547]'
                : 'bg-slate-50 text-slate-700 border-slate-300'
            }`}
          >
            Act as ADMIN
          </button>
          <button
            type="button"
            onClick={() => onSwitchAccount('auditor@aicte-demo.in')}
            className={`px-3 py-1.5 rounded-lg font-bold border cursor-pointer ${
              user?.role === 'AUDITOR'
                ? 'bg-emerald-800 text-white border-emerald-800'
                : 'bg-slate-50 text-slate-700 border-slate-300'
            }`}
          >
            Act as AUDITOR (Read-Only)
          </button>
        </div>
      </div>

      {busy && (
        <div className="p-4 rounded-xl bg-blue-50 border border-blue-300 text-blue-950 text-xs font-mono font-bold animate-pulse">
          ⏳ {busy}
        </div>
      )}

      {error && (
        <div role="alert" className="p-3.5 rounded-xl bg-red-50 border border-red-300 text-red-900 text-xs font-semibold">
          ❌ {error}
        </div>
      )}

      {banner && (
        <div role="status" className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs font-semibold">
          ✅ {banner}
        </div>
      )}

      {/* SUB-TAB 1: TIME-TRAVEL CLOCK & CHAOS LAB */}
      {subTab === 'sandbox' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Card 1: Time-Travel Clock */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-bold text-[#EA580C] uppercase">
                  USP-07 • TIME-TRAVEL SIMULATOR
                </span>
                <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded bg-amber-100 text-amber-900">
                  {simulatedToday} (+{clockOffsetDays}d)
                </span>
              </div>
              <h2 className="text-base font-display font-bold text-slate-900">
                Fast-Forward Maturity, T-90/30 Reminders &amp; Escalation Ladder
              </h2>
              <p className="text-xs text-slate-600 leading-relaxed">
                Steps day-by-day through <code className="font-mono">monitor.run_all()</code> so reminders, escalations, and overdue locks fire in the exact real-world sequence.
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => handleShiftClock(66)}
                  disabled={!!busy}
                  className="p-2.5 rounded-xl bg-[#0F2547] hover:bg-blue-800 text-white font-bold cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <FastForward className="w-3.5 h-3.5 text-amber-300" />
                  <span>+66 Days (T-30 Due)</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleShiftClock(8)}
                  disabled={!!busy}
                  className="p-2.5 rounded-xl bg-indigo-700 hover:bg-indigo-800 text-white font-bold cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <FastForward className="w-3.5 h-3.5" />
                  <span>+8 Days (Escalate L2)</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleShiftClock(30)}
                  disabled={!!busy}
                  className="p-2.5 rounded-xl bg-rose-700 hover:bg-rose-800 text-white font-bold cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <FastForward className="w-3.5 h-3.5" />
                  <span>+30 Days (Expire &amp; Lock)</span>
                </button>
                <button
                  type="button"
                  onClick={handleResetClock}
                  disabled={!!busy}
                  className="p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold border border-slate-300 cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset Clock (0d)</span>
                </button>
              </div>
              <div className="flex gap-2 pt-1">
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={customDays}
                  onChange={(e) => setCustomDays(e.target.value)}
                  className="w-24 px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-mono"
                />
                <button
                  type="button"
                  onClick={() => handleShiftClock(Number(customDays) || 15)}
                  disabled={!!busy}
                  className="flex-1 py-1.5 px-3 rounded-lg bg-slate-800 text-white text-xs font-semibold cursor-pointer"
                >
                  Advance Custom Days
                </button>
              </div>
            </div>

            {/* Card 2: Silent Premature Encashment Catch */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-4 flex flex-col justify-between">
              <div className="space-y-2">
                <span className="text-[11px] font-mono font-bold text-rose-700 uppercase">
                  USP-06 • PERIODIC BANK RE-VERIFICATION
                </span>
                <h2 className="text-base font-display font-bold text-slate-900">
                  Simulate Silent Mid-Tenure Premature Encashment
                </h2>
                <p className="text-xs text-slate-600 leading-relaxed">
                  What if a college gets its FDR verified and approved, and 6 months later quietly breaks the FD at the bank? Clicking below marks an active CBS record as <code>ENCASHED</code> and runs <code>force_reverify=true</code> to catch it live!
                </p>
              </div>
              <button
                type="button"
                onClick={handleSimulatePrematureEncashment}
                disabled={!!busy}
                className="w-full py-3 px-4 rounded-xl bg-rose-700 hover:bg-rose-800 text-white text-xs font-bold shadow-xs cursor-pointer flex items-center justify-center gap-2"
              >
                <Zap className="w-4 h-4 text-amber-300" />
                <span>Simulate Silent Encashment &amp; Run Catch Job</span>
              </button>
            </div>

            {/* Card 3: Insider SQL Audit Tamper & Golden Reseed */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-4 flex flex-col justify-between">
              <div className="space-y-2">
                <span className="text-[11px] font-mono font-bold text-emerald-700 uppercase">
                  USP-10 • CRYPTOGRAPHIC AUDIT TAMPER TEST
                </span>
                <h2 className="text-base font-display font-bold text-slate-900">
                  Simulate Rogue Insider SQL Edit on Audit Row #10
                </h2>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Executes a raw SQL <code>UPDATE audit_log WHERE id=10</code> bypassing the app, then runs SHA-256 chain verification to prove tamper detection.
                </p>
              </div>
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={handleTamperAudit}
                    disabled={!!busy}
                    className="py-2.5 px-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold cursor-pointer"
                  >
                    1. Tamper Row #10
                  </button>
                  <button
                    type="button"
                    onClick={handleRestoreAudit}
                    disabled={!!busy}
                    className="py-2.5 px-3 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold cursor-pointer"
                  >
                    2. Restore Row #10
                  </button>
                </div>
                <button
                  type="button"
                  onClick={handleReseedGoldenDataset}
                  disabled={!!busy}
                  className="w-full py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 text-xs font-bold cursor-pointer"
                >
                  🔄 Reset Entire Database to Golden Demo Seed
                </button>
              </div>
            </div>
          </div>

          {/* Time-Travel Event Log Output */}
          {clockEvents.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
              <h3 className="text-sm font-display font-bold text-slate-900">
                Time-Travel Daily Scheduler Execution Log ({clockEvents.length} Active Event Days)
              </h3>
              <div className="max-h-72 overflow-y-auto space-y-2 font-mono text-xs">
                {clockEvents.map((ev, i) => (
                  <div key={i} className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="font-bold text-[#0F2547]">📅 Simulated Date: {ev.date}</div>
                    <div className="text-slate-700 mt-1">
                      Transitions: {ev.transitions?.length || 0} • Reminders Sent: {ev.reminders?.length || 0} • Escalations:{' '}
                      {ev.escalations?.length || 0} • Alerts Opened: {ev.alerts_opened || 0}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 2: CRYPTOGRAPHIC HASH-CHAINED AUDIT LEDGER */}
      {subTab === 'audit' && (
        <div className="space-y-5">
          {auditVerify && (
            <div
              className={`p-5 rounded-2xl border-2 flex flex-wrap items-center justify-between gap-4 ${
                auditVerify.valid
                  ? 'bg-emerald-50 border-emerald-500 text-emerald-950'
                  : 'bg-red-50 border-red-600 text-red-950'
              }`}
            >
              <div className="flex items-start gap-3">
                {auditVerify.valid ? (
                  <ShieldCheck className="w-8 h-8 text-emerald-700 shrink-0" />
                ) : (
                  <AlertOctagon className="w-8 h-8 text-red-700 shrink-0" />
                )}
                <div>
                  <div className="font-mono text-xs font-extrabold uppercase">
                    GET /api/v1/admin/audit/verify • SHA-256(prev_hash || canonical_payload)
                  </div>
                  <h2 className="text-lg font-display font-extrabold">
                    {auditVerify.valid
                      ? `Cryptographic Hash Chain INTACT — All ${auditVerify.checked} Entries Verified`
                      : `🚨 TAMPERING DETECTED AT AUDIT ENTRY #${auditVerify.broken_at_id}!`}
                  </h2>
                  {!auditVerify.valid && (
                    <p className="text-xs font-mono mt-1">
                      Reason: {auditVerify.reason} (Expected hash mismatch due to unauthorized SQL modification)
                    </p>
                  )}
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleTamperAudit}
                  className="px-3.5 py-2 rounded-xl bg-amber-500 text-slate-950 text-xs font-bold cursor-pointer"
                >
                  Simulate SQL Tamper (#10)
                </button>
                <button
                  type="button"
                  onClick={handleRestoreAudit}
                  className="px-3.5 py-2 rounded-xl bg-emerald-700 text-white text-xs font-bold cursor-pointer"
                >
                  Restore Row (#10)
                </button>
              </div>
            </div>
          )}

          <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
            <h3 className="text-base font-display font-bold text-slate-900">
              Append-Only Hash-Chained Audit Log ({auditEntries.length} Recent Entries)
            </h3>
            <div className="table-wrapper rounded-xl border border-slate-200">
              <table className="text-xs text-left font-mono">
                <thead className="bg-slate-100 text-slate-700 text-[11px] uppercase">
                  <tr>
                    <th className="p-2.5">ID</th>
                    <th className="p-2.5">Action</th>
                    <th className="p-2.5">Actor</th>
                    <th className="p-2.5">Entity</th>
                    <th className="p-2.5">Prev Hash</th>
                    <th className="p-2.5">Entry SHA-256 Hash</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {auditEntries.map((a) => (
                    <tr
                      key={a.id}
                      className={
                        auditVerify?.broken_at_id === a.id
                          ? 'bg-red-100 text-red-950 font-bold'
                          : 'hover:bg-slate-50'
                      }
                    >
                      <th scope="row" className="p-2.5">
                        #{a.id}
                      </th>
                      <td className="p-2.5 font-bold text-[#0F2547]">{a.action}</td>
                      <td className="p-2.5">
                        {a.actor_email || 'system'} ({a.actor_role || 'AUTO'})
                      </td>
                      <td className="p-2.5">
                        {a.entity_type} #{a.entity_id || '—'}
                      </td>
                      <td className="p-2.5 text-slate-500">{a.prev_hash?.slice(0, 14)}...</td>
                      <td className="p-2.5 text-emerald-800">{(a.hash || a.entry_hash)?.slice(0, 18)}...</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 3: 20-RULE ENGINE CATALOGUE & LIVE OVERRIDES */}
      {subTab === 'rules' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
          <div>
            <span className="text-xs font-mono font-bold text-blue-700 uppercase">
              ZERO-REDEPLOY RULE GOVERNANCE (`/api/v1/meta/rules` &amp; `/api/v1/admin/config`)
            </span>
            <h2 className="text-lg font-display font-bold text-slate-900">
              20 Statutory &amp; Forgery Detection Rules (R01–R20) with Live Severity Overrides
            </h2>
          </div>

          <div className="table-wrapper rounded-xl border border-slate-200">
            <table className="text-xs text-left">
              <thead className="bg-slate-100 text-slate-700 font-mono text-[11px] uppercase">
                <tr>
                  <th className="p-2.5">Rule ID</th>
                  <th className="p-2.5">Code</th>
                  <th className="p-2.5">Description</th>
                  <th className="p-2.5">Default Severity</th>
                  <th className="p-2.5">Live Admin Override</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {rulesCatalogue.map((r) => (
                  <tr key={r.rule_id} className="hover:bg-slate-50">
                    <th scope="row" className="p-2.5 font-mono font-bold text-[#0F2547]">
                      {r.rule_id}
                    </th>
                    <td className="p-2.5 font-mono font-semibold">{r.code}</td>
                    <td className="p-2.5 text-slate-700">{r.description}</td>
                    <td className="p-2.5 font-mono">
                      <span className="px-2 py-0.5 rounded bg-slate-100 font-bold">
                        {r.default_severity}
                      </span>
                    </td>
                    <td className="p-2.5">
                      <select
                        aria-label={`Override severity for ${r.rule_id}`}
                        value={r.override?.severity || r.default_severity}
                        onChange={(e) => handleOverrideRuleSeverity(r.rule_id, e.target.value)}
                        className="px-2 py-1 rounded border border-slate-300 text-xs font-mono bg-white"
                      >
                        <option value="INFO">INFO</option>
                        <option value="LOW">LOW</option>
                        <option value="MEDIUM">MEDIUM</option>
                        <option value="HIGH">HIGH</option>
                        <option value="CRITICAL">CRITICAL</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SUB-TAB 4: COMPLIANCE & VIGILANCE CASES */}
      {subTab === 'cases' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
          <div>
            <span className="text-xs font-mono font-bold text-rose-700 uppercase">
              RELEASE BLOCKER ENGINE (`/api/v1/compliance-cases`)
            </span>
            <h2 className="text-lg font-display font-bold text-slate-900">
              Institutional Compliance, Court &amp; Vigilance Cases ({cases.length})
            </h2>
            <p className="text-xs text-slate-600">
              Any <code>OPEN</code> case automatically blocks Security Deposit release for that institution. Close a case below to unblock release immediately!
            </p>
          </div>

          <div className="space-y-3">
            {cases.map((c) => (
              <div
                key={c.id}
                className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-slate-900">
                      Case #{c.id} • Institution #{c.institution_id}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded font-mono font-bold ${
                        c.status === 'OPEN'
                          ? 'bg-red-100 text-red-900'
                          : 'bg-emerald-100 text-emerald-900'
                      }`}
                    >
                      {c.status}
                    </span>
                  </div>
                  <div className="font-bold text-slate-900">{c.title}</div>
                  {c.description && <p className="text-slate-600">{c.description}</p>}
                </div>

                {c.status === 'OPEN' && (
                  <button
                    type="button"
                    onClick={() => handleCloseComplianceCase(c.id)}
                    className="px-4 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold cursor-pointer"
                  >
                    Close Compliance Case &amp; Unblock Release
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
