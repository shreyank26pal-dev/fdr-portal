import React, { useEffect, useState } from 'react';
import {
  FileSearch,
  Activity,
  BellRing,
  PackageCheck,
  FileSpreadsheet,
  Eye,
  Download,
  Filter,
} from 'lucide-react';
import {
  apiFetch,
  fetchBlobWithHeaders,
  formatINR,
} from '../api';
import { User } from '../types';

interface OfficerConsoleProps {
  user: User | null;
  onInspectInstrument: (id: number) => void;
  onSwitchAccount: (email: string) => Promise<void>;
  onRefreshGlobal: () => void;
}

export const OfficerConsole: React.FC<OfficerConsoleProps> = ({
  user,
  onInspectInstrument,
  onSwitchAccount,
  onRefreshGlobal,
}) => {
  const [subTab, setSubTab] = useState<'queue' | 'analytics' | 'refunds' | 'alerts' | 'reports'>('queue');
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const [workQueue, setWorkQueue] = useState<any[]>([]);
  const [instruments, setInstruments] = useState<any[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterRegion, setFilterRegion] = useState<string>('');
  const [filterBankName, setFilterBankName] = useState<string>('');
  const [filterFlagged, setFilterFlagged] = useState<boolean>(false);
  const [searchQ, setSearchQ] = useState<string>('');

  const [byBank, setByBank] = useState<any[]>([]);
  const [byRegion, setByRegion] = useState<any[]>([]);
  const [lateRenewals, setLateRenewals] = useState<any[]>([]);
  const [heatmap, setHeatmap] = useState<any | null>(null);

  const [refunds, setRefunds] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);

  const [selectedReport, setSelectedReport] = useState<string>('maturity-schedule');
  const [reportPreview, setReportPreview] = useState<any | null>(null);

  const loadQueueAndSearch = async () => {
    try {
      const params = new URLSearchParams();
      params.set('page_size', '50');
      if (filterStatus) params.set('status', filterStatus);
      if (filterRegion) params.set('region', filterRegion);
      if (filterBankName) params.set('bank_name', filterBankName);
      if (filterFlagged) params.set('has_open_flags', 'true');
      if (searchQ.trim()) params.set('q', searchQ.trim());

      const [listRes, wqRes] = await Promise.all([
        apiFetch<{ items: any[] }>(`/instruments?${params.toString()}`),
        apiFetch<any[]>('/instruments/work-queue').catch(() => []),
      ]);
      setInstruments(listRes.items || []);
      setWorkQueue(wqRes || []);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadAnalytics = async () => {
    try {
      const [b, r, l, hm] = await Promise.all([
        apiFetch('/dashboard/by-bank'),
        apiFetch('/dashboard/by-region').catch(() => []),
        apiFetch('/dashboard/predicted-late-renewals').catch(() => ({ rows: [] })),
        apiFetch('/dashboard/renewal-heatmap').catch(() => null),
      ]);
      setByBank(b || []);
      setByRegion(r || []);
      setLateRenewals(l?.rows || []);
      setHeatmap(hm);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadRefunds = async () => {
    try {
      const data = await apiFetch('/refunds');
      setRefunds(data || []);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadAlerts = async () => {
    try {
      const data = await apiFetch('/alerts');
      setAlerts(data || []);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadReportPreview = async (name: string) => {
    setSelectedReport(name);
    try {
      const data = await apiFetch(`/reports/${name}?format=json`);
      setReportPreview(data);
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => {
    if (subTab === 'queue') loadQueueAndSearch();
    if (subTab === 'analytics') loadAnalytics();
    if (subTab === 'refunds') loadRefunds();
    if (subTab === 'alerts') loadAlerts();
    if (subTab === 'reports') loadReportPreview(selectedReport);
  }, [subTab, user?.email, filterStatus, filterRegion, filterBankName, filterFlagged]);

  const handleRefundStep = async (
    refundId: number,
    action: 'start-review' | 'recommend' | 'approve' | 'process',
    label: string
  ) => {
    setError(null);
    setBanner(null);
    try {
      await apiFetch(`/refunds/${refundId}/${action}`, {
        method: 'POST',
        body: JSON.stringify({
          note: `${label} approved after verifying all statutory pre-conditions.`,
        }),
      });
      await loadRefunds();
      onRefreshGlobal();
      setBanner(`Refund #${refundId}: ${label} completed!`);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleDownloadBinary = async (path: string, fallbackName: string) => {
    try {
      const { url, filename } = await fetchBlobWithHeaders(path);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || fallbackName;
      a.click();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleAlertAction = async (alertId: number, action: 'acknowledge' | 'resolve') => {
    try {
      await apiFetch(`/alerts/${alertId}/${action}`, {
        method: 'POST',
        body: JSON.stringify({
          note: `${action === 'acknowledge' ? 'Acknowledged' : 'Resolved'} by ${user?.full_name || 'Officer'}.`,
        }),
      });
      await loadAlerts();
      onRefreshGlobal();
      setBanner(`Alert #${alertId} marked as ${action}d.`);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const totalHeldBankAmount = byBank.reduce((acc, x) => acc + (x.amount || 0), 0) || 1;

  return (
    <div className="space-y-6">
      {/* Top Role Bar & Sub-Navigation */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-2xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {[
            { id: 'queue', label: 'Scrutiny Work Queue & Search', icon: FileSearch },
            { id: 'analytics', label: 'Executive Risk & Bank Concentration', icon: Activity },
            { id: 'refunds', label: 'Guarded Release Queue (Two-Person Rule)', icon: PackageCheck },
            { id: 'alerts', label: 'SLA Escalation Tickets & Alerts', icon: BellRing },
            { id: 'reports', label: 'Official Reports (JSON / XLSX / PDF)', icon: FileSpreadsheet },
          ].map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setSubTab(t.id as any)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
                  subTab === t.id
                    ? 'bg-[#0F2547] text-white shadow-xs'
                    : 'bg-slate-50 text-slate-700 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-slate-500">Role:</span>
          {[
            { email: 'officer@aicte-demo.in', label: 'Scrutiny Officer' },
            { email: 'approver@aicte-demo.in', label: 'Approving Authority' },
            { email: 'ro.western@aicte-demo.in', label: 'Regional Officer' },
          ].map((r) => (
            <button
              key={r.email}
              type="button"
              onClick={() => onSwitchAccount(r.email)}
              className={`px-2.5 py-1 rounded-lg font-semibold border cursor-pointer ${
                user?.email === r.email
                  ? 'bg-[#0F2547] text-white border-[#0F2547]'
                  : 'bg-slate-50 text-slate-700 border-slate-300'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div role="alert" className="p-3.5 rounded-xl bg-red-50 border border-red-300 text-red-900 text-xs font-semibold flex justify-between">
          <span>❌ {error}</span>
          <button type="button" onClick={() => setError(null)} className="underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {banner && (
        <div role="status" className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs font-semibold flex justify-between">
          <span>✅ {banner}</span>
          <button type="button" onClick={() => setBanner(null)} className="underline cursor-pointer">
            Close
          </button>
        </div>
      )}

      {/* SUB-TAB 1: PRIORITISED WORK QUEUE & MASTER SEARCH */}
      {subTab === 'queue' && (
        <div className="space-y-6">
          {workQueue.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[11px] font-mono font-bold text-[#EA580C] uppercase">
                    RISK-RANKED SCRUTINY QUEUE
                  </span>
                  <h2 className="text-base font-display font-bold text-slate-900">
                    Prioritised Officer Work Queue ({workQueue.length} Pending Action)
                  </h2>
                </div>
                <span className="text-xs font-mono text-slate-500">
                  Sorted by Risk Score &amp; SLA Wait Days
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {workQueue.slice(0, 6).map((wq) => (
                  <div
                    key={wq.id}
                    className="p-3.5 rounded-xl bg-[#FAF7F2] border border-slate-200 flex flex-col justify-between gap-2"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-[#0F2547]">
                          #{wq.id} • {wq.fdr_number}
                        </span>
                        <span
                          className={`font-mono text-[10px] font-bold px-2 py-0.5 rounded ${
                            wq.risk_score >= 40
                              ? 'bg-red-100 text-red-900'
                              : 'bg-amber-100 text-amber-900'
                          }`}
                        >
                          Risk: {wq.risk_score} • Age: {wq.age_days ?? 0}d
                        </span>
                      </div>
                      <div className="text-xs font-bold text-slate-900 truncate">
                        {wq.institution_name}
                      </div>
                      <div className="text-[11px] text-slate-600 font-mono">
                        {formatINR(wq.amount)} • {wq.bank_name} • {wq.status}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onInspectInstrument(wq.id)}
                      className="w-full mt-1 py-1.5 px-3 rounded-lg bg-[#0F2547] hover:bg-blue-800 text-white text-xs font-semibold cursor-pointer"
                    >
                      Inspect in Dual-Truth Split-Screen →
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Master Search & Filter Bar */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2
                id="master-instruments-table-caption"
                className="text-base font-display font-bold text-slate-900 flex items-center gap-2"
              >
                <Filter className="w-4 h-4 text-blue-700" />
                <span>All FDR Instruments Register ({instruments.length})</span>
              </h2>

              <div className="flex flex-wrap items-center gap-2 text-xs">
                <input
                  type="search"
                  placeholder="Search FDR no, college, AICTE ID..."
                  value={searchQ}
                  onChange={(e) => setSearchQ(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && loadQueueAndSearch()}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs w-56"
                />
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  aria-label="Filter by status"
                  className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white"
                >
                  <option value="">All Statuses</option>
                  <option value="SUBMITTED">SUBMITTED</option>
                  <option value="UNDER_SCRUTINY">UNDER_SCRUTINY</option>
                  <option value="DISCREPANCY_RAISED">DISCREPANCY_RAISED</option>
                  <option value="VERIFIED">VERIFIED</option>
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="EXPIRING_SOON">EXPIRING_SOON</option>
                  <option value="ACTION_REQUIRED">ACTION_REQUIRED</option>
                  <option value="OVERDUE">OVERDUE</option>
                  <option value="RELEASED">RELEASED</option>
                </select>
                <select
                  value={filterRegion}
                  onChange={(e) => setFilterRegion(e.target.value)}
                  aria-label="Filter by region"
                  className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white"
                >
                  <option value="">All Regions</option>
                  <option value="WESTERN">WESTERN</option>
                  <option value="NORTHERN">NORTHERN</option>
                  <option value="SOUTHERN">SOUTHERN</option>
                  <option value="EASTERN">EASTERN</option>
                  <option value="CENTRAL">CENTRAL</option>
                </select>
                <label className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-300 bg-slate-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={filterFlagged}
                    onChange={(e) => setFilterFlagged(e.target.checked)}
                  />
                  <span className="font-semibold text-red-800">Flagged Only</span>
                </label>
                {filterBankName && (
                  <button
                    type="button"
                    onClick={() => setFilterBankName('')}
                    className="px-2.5 py-1.5 rounded-lg bg-blue-100 text-blue-900 font-mono font-bold cursor-pointer"
                  >
                    Bank: {filterBankName} ✕
                  </button>
                )}
              </div>
            </div>

            <div
              tabIndex={0}
              role="region"
              aria-labelledby="master-instruments-table-caption"
              className="table-wrapper rounded-xl border border-slate-200"
            >
              <table className="text-xs text-left">
                <caption className="sr-only">Master register of AICTE FDR instruments</caption>
                <thead className="bg-slate-100 text-slate-700 font-mono text-[11px] uppercase">
                  <tr>
                    <th className="p-3">FDR Number</th>
                    <th className="p-3">Institution &amp; Region</th>
                    <th className="p-3">Bank</th>
                    <th className="p-3">Principal</th>
                    <th className="p-3">Status &amp; Trust</th>
                    <th className="p-3">Risk &amp; Flags</th>
                    <th className="p-3">Maturity</th>
                    <th className="p-3 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {instruments.map((inst) => (
                    <tr key={inst.id} className="hover:bg-slate-50">
                      <th scope="row" className="p-3 font-mono font-bold text-slate-900">
                        <div>{inst.fdr_number}</div>
                        <div className="text-[10px] font-normal text-slate-500">#{inst.id}</div>
                      </th>
                      <td data-label="Institution" className="p-3">
                        <div className="font-semibold text-slate-900">{inst.institution_name}</div>
                        <div className="text-[11px] font-mono text-slate-500">
                          {inst.institution_aicte_id} • {inst.region}
                        </div>
                      </td>
                      <td data-label="Bank" className="p-3">
                        <div>{inst.bank_name}</div>
                        <div className="font-mono text-[10px] text-slate-500">{inst.ifsc}</div>
                      </td>
                      <td data-label="Principal" className="p-3 font-mono font-bold">
                        {formatINR(inst.amount)}
                      </td>
                      <td data-label="Status" className="p-3">
                        <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-900 font-bold text-[11px]">
                          {inst.status}
                        </span>
                        <div className="text-[10px] font-mono text-slate-500 mt-0.5">
                          {inst.trust_level}
                        </div>
                      </td>
                      <td data-label="Risk" className="p-3 font-mono">
                        <span
                          className={`px-2 py-0.5 rounded font-bold text-[11px] ${
                            inst.open_flags > 0
                              ? 'bg-red-100 text-red-900'
                              : 'bg-emerald-100 text-emerald-900'
                          }`}
                        >
                          Risk {inst.risk_score} • {inst.open_flags} Flags
                        </span>
                      </td>
                      <td data-label="Maturity" className="p-3 font-mono">
                        <div>{inst.maturity_date}</div>
                        <div className="text-[10px] text-slate-500">{inst.days_to_maturity}d</div>
                      </td>
                      <td data-label="Inspect" className="p-3 text-right">
                        <button
                          type="button"
                          onClick={() => onInspectInstrument(inst.id)}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#0F2547] text-white font-semibold hover:bg-blue-800 cursor-pointer"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Split-Screen</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: EXECUTIVE RISK & BANK CONCENTRATION ANALYTICS */}
      {subTab === 'analytics' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
              <div>
                <span className="text-[11px] font-mono font-bold text-blue-700 uppercase">
                  BANK CONCENTRATION RISK (CLICK ANY ROW TO FILTER)
                </span>
                <h3 className="text-base font-display font-bold text-slate-900">
                  Security Deposit Exposure by Issuing Bank
                </h3>
              </div>
              <div className="space-y-2.5">
                {byBank.map((b) => {
                  const pct = Math.round(((b.amount || 0) / totalHeldBankAmount) * 100);
                  return (
                    <div
                      key={b.bank}
                      onClick={() => {
                        setFilterBankName(b.bank);
                        setSubTab('queue');
                      }}
                      className="p-3 rounded-xl bg-slate-50 hover:bg-blue-50/60 border border-slate-200 cursor-pointer transition space-y-1.5"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-slate-900">{b.bank}</span>
                        <span className="font-mono font-bold text-[#0F2547]">
                          {formatINR(b.amount)} ({pct}%)
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-slate-200 overflow-hidden">
                        <div
                          className="h-full bg-[#1D4ED8]"
                          style={{ width: `${Math.min(100, Math.max(5, pct))}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[11px] font-mono text-slate-500">
                        <span>{b.count} Held FDRs</span>
                        <span>Click to drill down →</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
                <h3 className="text-base font-display font-bold text-slate-900">
                  Regional Directorate Breakdown
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {byRegion.map((r) => (
                    <div
                      key={r.region}
                      onClick={() => {
                        setFilterRegion(r.region);
                        setSubTab('queue');
                      }}
                      className="p-3.5 rounded-xl bg-[#FAF7F2] border border-slate-200 hover:border-blue-400 cursor-pointer text-xs space-y-1"
                    >
                      <div className="font-display font-bold text-sm text-[#0F2547]">
                        {r.region} Region
                      </div>
                      <div className="font-mono font-bold text-slate-900">
                        {formatINR(r.amount)}
                      </div>
                      <div className="text-[11px] text-slate-600 font-mono">
                        {r.count} Held FDRs
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
                <h3 className="text-base font-display font-bold text-slate-900">
                  Predictive Late-Renewal Watchlist ({lateRenewals.length})
                </h3>
                <div className="space-y-2 max-h-56 overflow-y-auto">
                  {lateRenewals.slice(0, 8).map((lr: any) => (
                    <div
                      key={lr.instrument_id}
                      onClick={() => onInspectInstrument(lr.instrument_id)}
                      className="p-2.5 rounded-xl bg-amber-50/70 border border-amber-200 flex items-center justify-between text-xs cursor-pointer"
                    >
                      <div>
                        <div className="font-bold text-slate-900">{lr.institution}</div>
                        <div className="font-mono text-[11px] text-slate-600">
                          {lr.fdr_number} • Matures {lr.maturity_date} ({lr.basis})
                        </div>
                      </div>
                      <span className="font-mono font-bold px-2 py-0.5 rounded bg-amber-200 text-amber-950">
                        Score {lr.risk_score}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 3: GUARDED RELEASE / REFUND QUEUE (TWO-PERSON RULE) */}
      {subTab === 'refunds' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-xs font-mono font-bold text-emerald-700 uppercase">
                USP-09 • TWO-PERSON RULE (SCRUTINY RECOMMEND ≠ APPROVER SANCTION)
              </span>
              <h2 className="text-lg font-display font-bold text-slate-900">
                Guarded Security Deposit Release / Refund Queue ({refunds.length})
              </h2>
            </div>
            <p className="text-xs text-slate-600">
              Switch between <strong>Scrutiny Officer</strong> (Recommend) and <strong>Approving Authority</strong> (Approve &amp; Process) using the Role pills above.
            </p>
          </div>

          <div className="space-y-3">
            {refunds.map((rf) => (
              <div
                key={rf.id}
                className="p-4 rounded-2xl bg-[#FAF7F2] border border-slate-200 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-[#0F2547]">
                        {rf.ref_number || `Refund #${rf.id}`} • {rf.instrument?.fdr_number}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-900 font-mono text-xs font-bold">
                        {rf.status}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded font-mono text-[11px] font-bold ${
                          !rf.tracker?.is_blocked
                            ? 'bg-emerald-100 text-emerald-900'
                            : 'bg-red-100 text-red-900'
                        }`}
                      >
                        {!rf.tracker?.is_blocked ? 'PRE-CONDITIONS PASSED' : 'BLOCKED BY PRE-CONDITIONS'}
                      </span>
                    </div>
                    <div className="text-xs text-slate-700 mt-1">
                      Institution: <strong>{rf.institution_name}</strong> • Amount:{' '}
                      <strong className="font-mono">{formatINR(rf.instrument?.amount)}</strong> • Ground:{' '}
                      <code className="font-mono">{rf.ground}</code>
                    </div>
                  </div>

                  {/* Role-Based Two-Person Action Buttons */}
                  <div className="flex flex-wrap items-center gap-2">
                    {rf.status === 'REQUESTED' && (
                      <button
                        type="button"
                        onClick={() => handleRefundStep(rf.id, 'start-review', 'Start Scrutiny Review')}
                        className="px-3 py-1.5 rounded-xl bg-amber-500 text-slate-950 font-bold text-xs cursor-pointer"
                      >
                        1. Start Scrutiny Review
                      </button>
                    )}

                    {(rf.status === 'REQUESTED' || rf.status === 'UNDER_REVIEW') && (
                      <button
                        type="button"
                        onClick={() => handleRefundStep(rf.id, 'recommend', 'Scrutiny Recommendation')}
                        className="px-3 py-1.5 rounded-xl bg-blue-700 text-white font-bold text-xs cursor-pointer"
                      >
                        2. Recommend Release (Scrutiny Officer)
                      </button>
                    )}

                    {rf.status === 'RECOMMENDED' && (
                      <button
                        type="button"
                        onClick={() => handleRefundStep(rf.id, 'approve', 'Approving Authority Sanction')}
                        className="px-3 py-1.5 rounded-xl bg-purple-700 text-white font-bold text-xs cursor-pointer"
                      >
                        3. Sanction Release (Approving Authority)
                      </button>
                    )}

                    {rf.status === 'APPROVED' && (
                      <button
                        type="button"
                        onClick={() => handleRefundStep(rf.id, 'process', 'Process & Generate Discharge Order PDF')}
                        className="px-3.5 py-1.5 rounded-xl bg-emerald-700 text-white font-bold text-xs cursor-pointer"
                      >
                        4. Process &amp; Issue Discharge Order PDF
                      </button>
                    )}

                    {rf.discharge_document_id && (
                      <button
                        type="button"
                        onClick={() =>
                          handleDownloadBinary(
                            `/documents/${rf.discharge_document_id}/download`,
                            `AICTE_Discharge_Order_${rf.id}.pdf`
                          )
                        }
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0F2547] text-amber-300 font-bold text-xs cursor-pointer"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Download Official Discharge PDF</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Courier 5-step pills */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {(rf.tracker?.steps || []).map((st: any, idx: number) => (
                    <div
                      key={st.code}
                      className={`p-2 rounded-lg border text-[11px] font-mono ${
                        st.state === 'done'
                          ? 'bg-emerald-50 border-emerald-300 text-emerald-900 font-bold'
                          : st.state === 'current'
                          ? 'bg-blue-50 border-blue-400 text-blue-900 font-bold'
                          : 'bg-white border-slate-200 text-slate-400'
                      }`}
                    >
                      {idx + 1}. {st.label} ({st.state})
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SUB-TAB 4: ESCALATION ALERTS & SLA TICKETS */}
      {subTab === 'alerts' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-4">
          <div>
            <span className="text-xs font-mono font-bold text-rose-700 uppercase">
              USP-07 • MULTI-LEVEL ESCALATION LADDER (L1 INSTITUTION → L2 SCRUTINY → L3 RO → L4 HQ DIRECTOR)
            </span>
            <h2 className="text-lg font-display font-bold text-slate-900">
              Active Maturity, Overdue &amp; Encashment Escalation Tickets ({alerts.length})
            </h2>
          </div>

          <div className="space-y-2.5">
            {alerts.map((al) => (
              <div
                key={al.id}
                className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1 max-w-3xl">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-bold px-2 py-0.5 rounded bg-slate-900 text-amber-300">
                      Level {al.level} → {al.assigned_role}
                    </span>
                    <span className="font-mono font-bold px-2 py-0.5 rounded bg-red-100 text-red-900">
                      {al.severity} • {al.alert_type}
                    </span>
                    <span className="font-mono text-slate-500">Status: {al.status}</span>
                  </div>
                  <div className="font-bold text-slate-900">{al.title}</div>
                  <p className="text-slate-600">{al.message}</p>
                </div>

                <div className="flex items-center gap-2">
                  {al.instrument_id && (
                    <button
                      type="button"
                      onClick={() => onInspectInstrument(al.instrument_id)}
                      className="px-3 py-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-900 font-semibold cursor-pointer"
                    >
                      Open FDR #{al.instrument_id}
                    </button>
                  )}
                  {al.status === 'OPEN' && (
                    <button
                      type="button"
                      onClick={() => handleAlertAction(al.id, 'acknowledge')}
                      className="px-3 py-1.5 rounded-lg bg-blue-700 text-white font-semibold cursor-pointer"
                    >
                      Acknowledge
                    </button>
                  )}
                  {al.status !== 'RESOLVED' && (
                    <button
                      type="button"
                      onClick={() => handleAlertAction(al.id, 'resolve')}
                      className="px-3 py-1.5 rounded-lg bg-emerald-700 text-white font-semibold cursor-pointer"
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SUB-TAB 5: EXPORTABLE MANAGEMENT REPORTS (JSON / XLSX / PDF) */}
      {subTab === 'reports' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="text-xs font-mono font-bold text-blue-700 uppercase">
                OFFICIAL REGULATORY EXPORTS (OPENPYXL .XLSX &amp; REPORTLAB .PDF)
              </span>
              <h2 className="text-lg font-display font-bold text-slate-900">
                AICTE Statutory &amp; Vigilance Management Reports
              </h2>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={selectedReport}
                onChange={(e) => loadReportPreview(e.target.value)}
                aria-label="Select management report"
                className="px-3 py-2 rounded-xl border border-slate-300 text-xs font-bold bg-slate-50"
              >
                <option value="maturity-schedule">1. Upcoming Maturities Schedule (maturity-schedule)</option>
                <option value="pending-verification">2. Pending Verification Ageing (pending-verification)</option>
                <option value="pending-refunds">3. Open Release Requests &amp; Pre-conditions (pending-refunds)</option>
                <option value="release-register">4. Processed Release Register (release-register)</option>
                <option value="bank-summary">5. Bank-Wise Exposure Summary (bank-summary)</option>
                <option value="region-summary">6. Regional Directorate Exposure (region-summary)</option>
                <option value="missing-documents">7. Missing Statutory Documents (missing-documents)</option>
                <option value="audit-extract">8. Hash-Chained Audit Trail Extract (audit-extract)</option>
              </select>

              <button
                type="button"
                onClick={() =>
                  handleDownloadBinary(
                    `/reports/${selectedReport}?format=xlsx`,
                    `AICTE_${selectedReport}.xlsx`
                  )
                }
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download Excel (.xlsx)</span>
              </button>

              <button
                type="button"
                onClick={() =>
                  handleDownloadBinary(
                    `/reports/${selectedReport}?format=pdf`,
                    `AICTE_${selectedReport}.pdf`
                  )
                }
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#0F2547] hover:bg-blue-900 text-white text-xs font-bold cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download Official PDF (.pdf)</span>
              </button>
            </div>
          </div>

          {reportPreview && (
            <div className="table-wrapper rounded-xl border border-slate-200">
              <table className="text-xs text-left">
                <thead className="bg-slate-100 text-slate-700 font-mono text-[11px] uppercase">
                  <tr>
                    {(reportPreview.columns || []).map((h: string) => (
                      <th key={h} className="p-2.5">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {(reportPreview.rows || []).slice(0, 30).map((r: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      {(reportPreview.columns || []).map((col: string) => (
                        <td key={col} className="p-2.5 font-mono">
                          {String(r[col] ?? '—')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
