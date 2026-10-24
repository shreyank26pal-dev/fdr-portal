import React, { useEffect, useRef, useState } from 'react';
import {
  Columns,
  ShieldCheck,
  ShieldAlert,
  Landmark,
  CheckCircle2,
  FileText,
  Lock,
  ExternalLink,
  MessageSquarePlus,
  GitBranch,
  RefreshCw,
} from 'lucide-react';
import {
  apiFetch,
  fetchBlobWithHeaders,
  formatINR,
  openLightDismissDialog,
} from '../api';
import { User } from '../types';

interface CaseSplitViewProps {
  user: User | null;
  selectedInstrumentId: number | null;
  onSelectInstrumentId: (id: number) => void;
  onSwitchAccount: (email: string) => Promise<void>;
  onOpenBlindLinkToken: (token: string) => void;
  onRefreshGlobal: () => void;
}

export const CaseSplitView: React.FC<CaseSplitViewProps> = ({
  user,
  selectedInstrumentId,
  onSelectInstrumentId,
  onSwitchAccount,
  onOpenBlindLinkToken,
  onRefreshGlobal,
}) => {
  const [instrumentsList, setInstrumentsList] = useState<any[]>([]);
  const [detail, setDetail] = useState<any | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [latestBlindToken, setLatestBlindToken] = useState<string | null>(null);

  // Document viewer state
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [docBlobUrl, setDocBlobUrl] = useState<string | null>(null);
  const [docMime, setDocMime] = useState<string>('application/pdf');
  const [docSha256, setDocSha256] = useState<string | null>(null);
  const [docIntegrity, setDocIntegrity] = useState<string | null>(null);
  const [ocrData, setOcrData] = useState<any | null>(null);
  const [rightPaneTab, setRightPaneTab] = useState<'preview' | 'ocr' | 'timeline'>('preview');

  const discrepancyDialogRef = useRef<HTMLDialogElement>(null);
  const manualVerifyDialogRef = useRef<HTMLDialogElement>(null);
  const [discrepancyReason, setDiscrepancyReason] = useState('WRONG_AMOUNT');
  const [discrepancyRemarks, setDiscrepancyRemarks] = useState(
    'Discrepancy observed between declared figures and OCR/Bank confirmation. Please clarify or upload corrected instrument.'
  );
  const [obsReasonCode, setObsReasonCode] = useState('DATA_MISMATCH');
  const [obsNote, setObsNote] = useState('');

  // Manual verify fields
  const [mvFdrNo, setMvFdrNo] = useState('');
  const [mvPrincipal, setMvPrincipal] = useState('');
  const [mvIssueDate, setMvIssueDate] = useState('');
  const [mvMaturityDate, setMvMaturityDate] = useState('');
  const [mvDepositor, setMvDepositor] = useState('');
  const [mvLienMarked, setMvLienMarked] = useState(true);

  const loadListAndSelect = async () => {
    try {
      const res = await apiFetch<{ items: any[] }>('/instruments?page_size=60&sort=risk');
      const items = res.items || [];
      setInstrumentsList(items);
      if (!selectedInstrumentId && items.length > 0) {
        const flagged = items.find(
          (i) => i.open_flags > 0 || i.status === 'UNDER_SCRUTINY' || i.status === 'SUBMITTED'
        );
        onSelectInstrumentId((flagged || items[0]).id);
      }
    } catch {
      // ignore
    }
  };

  const loadDetail = async (id: number) => {
    setError(null);
    try {
      const d = await apiFetch(`/instruments/${id}`);
      setDetail(d);
      const inst = d.instrument || {};
      setMvFdrNo(inst.fdr_number || '');
      setMvPrincipal(String(inst.amount || ''));
      setMvIssueDate(inst.issue_date || '');
      setMvMaturityDate(inst.maturity_date || '');
      setMvDepositor(inst.depositor_name || '');

      if (d.documents?.length > 0) {
        const firstDoc = d.documents[0];
        setActiveDocId(firstDoc.id);
        loadDocumentPreview(firstDoc.id, firstDoc.content_type || 'application/pdf');
      } else {
        setActiveDocId(null);
        setDocBlobUrl(null);
      }
    } catch (e: any) {
      setError(e.message || 'Could not load instrument detail');
    }
  };

  const loadDocumentPreview = async (docId: number, mimeType = 'application/pdf') => {
    setActiveDocId(docId);
    setDocMime(mimeType);
    try {
      const { url, sha256, integrity } = await fetchBlobWithHeaders(`/documents/${docId}/download`);
      setDocBlobUrl(url);
      setDocSha256(sha256);
      setDocIntegrity(integrity);
      const ocr = await apiFetch(`/documents/${docId}/ocr`).catch(() => null);
      setOcrData(ocr);
    } catch {
      setDocBlobUrl(null);
    }
  };

  useEffect(() => {
    loadListAndSelect();
  }, [user?.email]);

  useEffect(() => {
    if (selectedInstrumentId) {
      loadDetail(selectedInstrumentId);
    }
  }, [selectedInstrumentId, user?.email]);

  const inst = detail?.instrument;

  const runAction = async (label: string, endpoint: string, body?: any) => {
    if (!inst) return;
    setError(null);
    setBanner(null);
    setBusyAction(label);
    try {
      const updated = await apiFetch(`/instruments/${inst.id}${endpoint}`, {
        method: 'POST',
        body: body ? JSON.stringify(body) : JSON.stringify({}),
      });
      if (updated && updated.instrument) {
        setDetail(updated);
      } else {
        await loadDetail(inst.id);
      }
      onRefreshGlobal();
      setBanner(`Completed: ${label}`);
    } catch (e: any) {
      setError(e.message || `Action failed: ${label}`);
    } finally {
      setBusyAction(null);
    }
  };

  const handleVerifyBank = async () => {
    if (!inst) return;
    setError(null);
    setBanner(null);
    setBusyAction('Contacting Bank CBS / Nodal Verification Service...');
    try {
      const res = await apiFetch(`/instruments/${inst.id}/verify-bank`, {
        method: 'POST',
      });
      await loadDetail(inst.id);
      onRefreshGlobal();
      const vr = res.verification || {};
      if (vr.confirmation_token) {
        setLatestBlindToken(vr.confirmation_token);
      }
      setBanner(
        vr.channel === 'BANK_API'
          ? `Bank CBS API Responded Immediately: Result = ${vr.result || vr.status}`
          : `Bank CBS API Offline/Unsupported — Fallback Nodal Request Queued! Click the Blind Confirmation button below to respond as Bank.`
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusyAction(null);
    }
  };

  const handleFlagDecision = async (
    flagId: number,
    decision: 'CONFIRMED' | 'DISMISSED'
  ) => {
    if (!inst) return;
    const note =
      decision === 'CONFIRMED'
        ? 'Verified anomaly during scrutiny inspection of receipt vs declared fields.'
        : 'Reviewed original document scan; minor OCR formatting variance dismissed.';
    setBusyAction(`Marking flag #${flagId} as ${decision}...`);
    try {
      await apiFetch(`/flags/${flagId}/decide`, {
        method: 'POST',
        body: JSON.stringify({ decision, note }),
      });
      await loadDetail(inst.id);
      setBanner(`Flag #${flagId} marked as ${decision}.`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusyAction(null);
    }
  };

  const handleAddObservation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inst || !obsNote.trim()) return;
    setBusyAction('Saving scrutiny observation...');
    try {
      await apiFetch(`/instruments/${inst.id}/observations`, {
        method: 'POST',
        body: JSON.stringify({
          reason_code: obsReasonCode,
          note: obsNote.trim(),
          visible_to_institution: true,
        }),
      });
      setObsNote('');
      await loadDetail(inst.id);
      setBanner('Scrutiny observation recorded.');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusyAction(null);
    }
  };

  const trustBadgeStyle = (trust: string) => {
    switch (trust) {
      case 'BANK_VERIFIED':
        return 'bg-emerald-100 text-emerald-900 border-emerald-300';
      case 'OFFICER_VERIFIED':
        return 'bg-teal-100 text-teal-900 border-teal-300';
      case 'OCR_CONSISTENT':
        return 'bg-blue-100 text-blue-900 border-blue-300';
      case 'OCR_CONFLICT':
        return 'bg-amber-100 text-amber-950 border-amber-400';
      case 'MISMATCH':
        return 'bg-red-100 text-red-900 border-red-400';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Selector & Quick Role Switcher Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-2xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-[#0F2547] font-display font-extrabold text-sm">
            <Columns className="w-5 h-5 text-[#1D4ED8]" />
            <span>Dual-Truth Case Split-Screen:</span>
          </div>

          <label htmlFor="case-instrument-select" className="sr-only">
            Select FDR Instrument to inspect
          </label>
          <select
            id="case-instrument-select"
            value={selectedInstrumentId || ''}
            onChange={(e) => onSelectInstrumentId(Number(e.target.value))}
            className="px-3 py-1.5 rounded-xl border border-slate-300 text-xs font-mono font-semibold bg-slate-50 max-w-md"
          >
            {instrumentsList.map((item) => (
              <option key={item.id} value={item.id}>
                #{item.id} • {item.fdr_number} — {item.institution_name} [{item.status}]
                {item.open_flags > 0 ? ` ⚠️ ${item.open_flags} flags` : ''}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => selectedInstrumentId && loadDetail(selectedInstrumentId)}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 cursor-pointer"
            title="Reload instrument"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Instant Role Switcher for Stepping Through Custody */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-slate-500 font-medium mr-1">Act as:</span>
          {[
            { email: 'officer@aicte-demo.in', label: 'Scrutiny Officer' },
            { email: 'approver@aicte-demo.in', label: 'Approving Authority' },
            { email: 'college1@aicte-demo.in', label: 'Institution 1' },
            { email: 'auditor@aicte-demo.in', label: 'Auditor (Read-Only)' },
          ].map((r) => (
            <button
              key={r.email}
              type="button"
              onClick={() => onSwitchAccount(r.email)}
              className={`px-2.5 py-1 rounded-lg font-semibold border transition cursor-pointer ${
                user?.email === r.email
                  ? 'bg-[#0F2547] text-white border-[#0F2547]'
                  : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-red-50 border border-red-300 text-red-900 text-xs font-semibold flex items-center justify-between"
        >
          <span>❌ {error}</span>
          <button type="button" onClick={() => setError(null)} className="underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {banner && (
        <div
          role="status"
          className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs font-semibold flex items-center justify-between"
        >
          <span>✅ {banner}</span>
          <button type="button" onClick={() => setBanner(null)} className="underline cursor-pointer">
            Close
          </button>
        </div>
      )}

      {detail && inst && (
        <>
          {/* Shared Pending Action & Lifecycle Header */}
          <div className="bg-gradient-to-r from-[#0F2547] via-[#173464] to-[#1E3A8A] text-white rounded-2xl p-5 shadow-sm space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-full bg-amber-400 text-slate-950 font-mono text-xs font-extrabold">
                    {inst.status_label} ({inst.status})
                  </span>
                  <span className="px-2.5 py-0.5 rounded-full bg-white/15 text-white font-mono text-xs">
                    Trust: {inst.trust_level}
                  </span>
                  <span className="px-2.5 py-0.5 rounded-full bg-white/15 text-amber-200 font-mono text-xs">
                    Risk Score: {inst.risk_score}/100
                  </span>
                  {inst.ack_number && (
                    <span className="font-mono text-xs text-slate-300">
                      Ack: {inst.ack_number}
                    </span>
                  )}
                </div>
                <h1 className="text-xl sm:text-2xl font-display font-extrabold">
                  {inst.fdr_number} • {formatINR(inst.amount)} ({inst.bank_name})
                </h1>
                <p className="text-xs text-slate-200">
                  Institution: <strong>{inst.institution_name}</strong> ({inst.institution_aicte_id}) • Region:{' '}
                  {inst.region} • Purpose: <code className="font-mono">{inst.purpose}</code>
                </p>
              </div>

              {/* Identical Pending Action Box for Both Sides */}
              <div className="bg-white/10 border border-white/20 rounded-xl p-3 max-w-md text-xs">
                <div className="font-mono text-[10px] uppercase tracking-wider text-amber-300 font-bold">
                  Pending Action Owner: {detail.pending_action?.owner}
                </div>
                <div className="font-semibold text-white mt-0.5">
                  {detail.pending_action?.text}
                </div>
              </div>
            </div>

            {/* Role-Gated Action Bar driven by detail.allowed_actions */}
            <div className="pt-3 border-t border-white/15 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {(detail.allowed_actions || []).includes('pickup') && (
                  <button
                    type="button"
                    onClick={() => runAction('Pick up for Scrutiny', '/pickup')}
                    className="px-3.5 py-1.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs cursor-pointer"
                  >
                    1. Pick Up for Scrutiny
                  </button>
                )}

                {(detail.allowed_actions || []).includes('verify_bank') && (
                  <button
                    type="button"
                    onClick={handleVerifyBank}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs cursor-pointer"
                  >
                    <Landmark className="w-3.5 h-3.5" />
                    <span>2. Verify with Bank (CBS API / Nodal Fallback)</span>
                  </button>
                )}

                {(detail.allowed_actions || []).includes('manual_verify') && (
                  <button
                    type="button"
                    onClick={() => openLightDismissDialog(manualVerifyDialogRef.current)}
                    className="px-3.5 py-1.5 rounded-xl bg-white/15 hover:bg-white/25 text-white font-semibold text-xs border border-white/25 cursor-pointer"
                  >
                    Record Signed Bank Letter (Manual Verify)
                  </button>
                )}

                {(detail.allowed_actions || []).includes('mark_verified') && (
                  <button
                    type="button"
                    onClick={() =>
                      runAction('Mark Verified & Forward to Approving Authority', '/mark-verified', {
                        note: 'All Dual-Truth fields verified and flags resolved by Scrutiny Officer.',
                      })
                    }
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-500 hover:bg-blue-400 text-white font-bold text-xs cursor-pointer"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>3. Mark Verified (Forward to Approver)</span>
                  </button>
                )}

                {(detail.allowed_actions || []).includes('raise_discrepancy') && (
                  <button
                    type="button"
                    onClick={() => openLightDismissDialog(discrepancyDialogRef.current)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold text-xs cursor-pointer"
                  >
                    <ShieldAlert className="w-3.5 h-3.5" />
                    <span>Raise Discrepancy</span>
                  </button>
                )}

                {(detail.allowed_actions || []).includes('approve') && (
                  <button
                    type="button"
                    onClick={() =>
                      runAction('Final Sign-Off (Activate FDR)', '/approve', {
                        note: 'Approved by Competent Approving Authority.',
                      })
                    }
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-emerald-400 hover:bg-emerald-300 text-slate-950 font-extrabold text-xs cursor-pointer"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    <span>4. Final Approve &amp; Activate FDR</span>
                  </button>
                )}

                {(detail.allowed_actions || []).includes('send_back') && (
                  <button
                    type="button"
                    onClick={() =>
                      runAction('Send Back to Scrutiny Officer', '/send-back', {
                        note: 'Requires additional scrutiny review.',
                      })
                    }
                    className="px-3 py-1.5 rounded-xl bg-white/15 hover:bg-white/25 text-white text-xs font-semibold cursor-pointer"
                  >
                    Send Back to Scrutiny
                  </button>
                )}

                {(detail.allowed_actions || []).includes('submit') && (
                  <button
                    type="button"
                    onClick={() => runAction('Submit / Re-Submit to AICTE', '/submit')}
                    className="px-4 py-1.5 rounded-xl bg-amber-400 text-slate-950 font-bold text-xs cursor-pointer"
                  >
                    Submit / Re-Submit to AICTE
                  </button>
                )}

                {(detail.allowed_actions || []).length === 0 && (
                  <span className="text-xs text-slate-300 font-mono">
                    No direct state-transition actions for role [{user?.role}] in status [{inst.status}]. Use &ldquo;Act as&rdquo; buttons above to switch role!
                  </span>
                )}
              </div>

              {busyAction && (
                <span className="text-xs font-mono text-amber-300 font-bold animate-pulse">
                  ⏳ {busyAction}
                </span>
              )}
            </div>
          </div>

          {/* MAIN SIDE-BY-SIDE SPLIT SCREEN */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* LEFT PANE (7 cols) */}
            <div className="lg:col-span-7 space-y-6">
              {/* 1. Dual-Truth Field Comparison Matrix */}
              <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="text-[11px] font-mono font-bold text-blue-700 uppercase">
                      USP-01 • DUAL-TRUTH FIELD MODEL
                    </span>
                    <h2
                      id="dual-truth-table-caption"
                      className="text-base font-display font-bold text-slate-900"
                    >
                      Declared vs OCR Read vs Bank / Officer Confirmed
                    </h2>
                  </div>
                  <span className="text-[11px] font-mono text-slate-500">
                    6 Trust States • Zero Silent Overwrites
                  </span>
                </div>

                <div
                  tabIndex={0}
                  role="region"
                  aria-labelledby="dual-truth-table-caption"
                  className="table-wrapper rounded-xl border border-slate-200"
                >
                  <table className="text-xs text-left">
                    <caption className="sr-only">
                      Dual-Truth comparison of Institution Declared, OCR Read, and Bank Confirmed values
                    </caption>
                    <thead className="bg-slate-100 text-slate-700 font-mono text-[11px] uppercase">
                      <tr>
                        <th className="p-2.5">Field</th>
                        <th className="p-2.5">Institution Declared</th>
                        <th className="p-2.5">OCR Read (Receipt)</th>
                        <th className="p-2.5">Bank / Officer Confirmed</th>
                        <th className="p-2.5">Trust Badge</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {(detail.fields || []).map((row: any) => (
                        <tr
                          key={row.field}
                          className={
                            row.trust === 'MISMATCH' || row.trust === 'OCR_CONFLICT'
                              ? 'bg-red-50/50'
                              : 'hover:bg-slate-50/80'
                          }
                        >
                          <th scope="row" className="p-2.5 font-semibold text-slate-800">
                            {row.label}
                          </th>
                          <td data-label="Declared" className="p-2.5 font-mono text-slate-900">
                            {row.field === 'amount' && row.declared_value !== null
                              ? formatINR(row.declared_value)
                              : String(row.declared_value ?? '—')}
                          </td>
                          <td data-label="OCR Read" className="p-2.5 font-mono text-slate-700">
                            {row.field === 'amount' && row.ocr_value !== null
                              ? formatINR(row.ocr_value)
                              : String(row.ocr_value ?? '—')}
                          </td>
                          <td data-label="Confirmed" className="p-2.5 font-mono font-bold text-slate-900">
                            {row.confirmed_value !== null ? (
                              <div>
                                <span>
                                  {row.field === 'amount'
                                    ? formatINR(row.confirmed_value)
                                    : String(row.confirmed_value)}
                                </span>
                                {row.confirmed_channel && (
                                  <span className="ml-1.5 text-[10px] px-1.5 py-0.2 rounded bg-slate-200 text-slate-700">
                                    {row.confirmed_channel}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="text-slate-400 font-normal">Pending</span>
                            )}
                          </td>
                          <td data-label="Trust" className="p-2.5">
                            <span
                              className={`inline-block px-2 py-0.5 rounded border font-mono text-[10px] font-bold ${trustBadgeStyle(
                                row.trust
                              )}`}
                            >
                              {row.badge?.label || row.trust}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* 2. 20-Rule Anomaly & Forgery Flags (R01–R20) */}
              <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[11px] font-mono font-bold text-[#EA580C] uppercase">
                      USP-03 • 20-RULE FORGERY &amp; ANOMALY ENGINE
                    </span>
                    <h2 className="text-base font-display font-bold text-slate-900">
                      Automated Discrepancy &amp; Forgery Flags ({detail.flags?.length || 0})
                    </h2>
                  </div>
                  <span className="text-xs font-mono text-slate-500">
                    Open Flags: {inst.open_flags}
                  </span>
                </div>

                {detail.flags?.length === 0 ? (
                  <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-950 font-semibold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                    <span>All 20 statutory and document anomaly rules passed without flags.</span>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {detail.flags.map((fl: any) => (
                      <div
                        key={fl.id}
                        className={`p-3.5 rounded-xl border text-xs space-y-2 ${
                          fl.status === 'DISMISSED'
                            ? 'bg-slate-50 border-slate-200 text-slate-500'
                            : fl.severity === 'CRITICAL' || fl.severity === 'HIGH'
                            ? 'bg-red-50/80 border-red-300 text-red-950'
                            : 'bg-amber-50/80 border-amber-300 text-amber-950'
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold px-2 py-0.5 rounded bg-slate-900 text-amber-300">
                              {fl.rule_id}
                            </span>
                            <span className="font-mono font-bold uppercase px-2 py-0.5 rounded bg-white/80 border border-current">
                              {fl.severity}
                            </span>
                            <span className="font-bold">{fl.title}</span>
                          </div>
                          <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-white border border-slate-300">
                            Status: {fl.status}
                          </span>
                        </div>
                        <p className="leading-relaxed">
                          {fl.officer_message || fl.message || fl.institution_message}
                        </p>

                        {fl.status === 'OPEN' &&
                          (user?.role === 'SCRUTINY_OFFICER' ||
                            user?.role === 'APPROVING_AUTHORITY' ||
                            user?.role === 'ADMIN') && (
                            <div className="flex items-center gap-2 pt-1">
                              <button
                                type="button"
                                onClick={() => handleFlagDecision(fl.id, 'CONFIRMED')}
                                className="px-3 py-1 rounded-lg bg-red-700 hover:bg-red-800 text-white font-bold text-[11px] cursor-pointer"
                              >
                                Confirm Anomaly (CONFIRMED)
                              </button>
                              <button
                                type="button"
                                onClick={() => handleFlagDecision(fl.id, 'DISMISSED')}
                                className="px-3 py-1 rounded-lg bg-slate-700 hover:bg-slate-800 text-white font-semibold text-[11px] cursor-pointer"
                              >
                                Dismiss as False Positive (DISMISSED)
                              </button>
                            </div>
                          )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 3. Bank Verification Chain of Custody & Blind Link Launcher */}
              <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-3">
                <div>
                  <span className="text-[11px] font-mono font-bold text-amber-700 uppercase">
                    USP-04 &amp; USP-05 • HYBRID CBS API + BLIND NODAL FALLBACK
                  </span>
                  <h2 className="text-base font-display font-bold text-slate-900">
                    Bank Verification Requests ({detail.verification_requests?.length || 0})
                  </h2>
                </div>

                {latestBlindToken && (
                  <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <div className="text-amber-950">
                      <div className="font-bold">🔗 One-Time Blind Bank Confirmation Link Generated!</div>
                      <div className="font-mono text-[11px]">
                        Token: {latestBlindToken.slice(0, 24)}...
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenBlindLinkToken(latestBlindToken)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0F2547] text-white font-bold cursor-pointer"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Open Blind Confirmation Form →</span>
                    </button>
                  </div>
                )}

                {detail.verification_requests?.length === 0 ? (
                  <p className="text-xs text-slate-500">
                    No bank verification request has been triggered yet. Click &ldquo;2. Verify with Bank&rdquo; in the action bar above.
                  </p>
                ) : (
                  <div className="space-y-2.5">
                    {detail.verification_requests.map((vr: any) => (
                      <div
                        key={vr.id}
                        className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1.5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-mono font-bold text-slate-900">
                            Request #{vr.id} • Channel: {vr.channel} ({vr.source_name || 'Bank'})
                          </div>
                          <span
                            className={`font-mono font-bold px-2 py-0.5 rounded ${
                              vr.result === 'VERIFIED' || vr.status === 'RESPONDED'
                                ? 'bg-emerald-100 text-emerald-900'
                                : vr.result === 'MISMATCH'
                                ? 'bg-red-100 text-red-900'
                                : 'bg-amber-100 text-amber-900'
                            }`}
                          >
                            {vr.result || vr.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 4. Renewal Lineage Chain & Scrutiny Observations */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
                  <h3 className="text-xs font-display font-bold text-slate-900 flex items-center gap-1.5 uppercase tracking-wider">
                    <GitBranch className="w-4 h-4 text-blue-700" />
                    <span>Renewal Lineage Chain ({detail.lineage?.length || 1})</span>
                  </h3>
                  <div className="space-y-2">
                    {(detail.lineage || []).map((node: any, idx: number) => (
                      <div
                        key={node.id}
                        onClick={() => onSelectInstrumentId(node.id)}
                        className={`p-2.5 rounded-xl border text-xs cursor-pointer transition ${
                          node.id === inst.id
                            ? 'bg-blue-50 border-blue-400 font-bold'
                            : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                        }`}
                      >
                        <div className="flex items-center justify-between font-mono">
                          <span>
                            Gen {idx + 1}: {node.fdr_number}
                          </span>
                          <span>{node.status}</span>
                        </div>
                        <div className="text-[11px] text-slate-500 font-mono">
                          {formatINR(node.amount)} • {node.issue_date} → {node.maturity_date}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Observations Box */}
                <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
                  <h3 className="text-xs font-display font-bold text-slate-900 flex items-center gap-1.5 uppercase tracking-wider">
                    <MessageSquarePlus className="w-4 h-4 text-indigo-700" />
                    <span>Scrutiny Observations ({detail.observations?.length || 0})</span>
                  </h3>
                  <div className="max-h-36 overflow-y-auto space-y-2">
                    {(detail.observations || []).map((ob: any) => (
                      <div key={ob.id} className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                        <div className="font-mono text-[10px] font-bold text-indigo-800">
                          [{ob.reason_code || 'NOTE'}]
                        </div>
                        <p className="text-slate-700">{ob.note}</p>
                      </div>
                    ))}
                  </div>
                  {(user?.role === 'SCRUTINY_OFFICER' ||
                    user?.role === 'APPROVING_AUTHORITY' ||
                    user?.role === 'REGIONAL_OFFICER') && (
                    <form onSubmit={handleAddObservation} className="flex gap-1.5 pt-1">
                      <input
                        type="text"
                        placeholder="Add scrutiny observation..."
                        value={obsNote}
                        onChange={(e) => setObsNote(e.target.value)}
                        className="flex-1 px-2.5 py-1 rounded-lg border border-slate-300 text-xs"
                      />
                      <button
                        type="submit"
                        className="px-2.5 py-1 rounded-lg bg-[#0F2547] text-white text-xs font-bold cursor-pointer"
                      >
                        Add
                      </button>
                    </form>
                  )}
                </div>
              </div>
            </div>

            {/* RIGHT PANE (5 cols): ENCRYPTED DOCUMENT PREVIEW + SHA-256 INTEGRITY + OCR + TIMELINE */}
            <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-4 sticky top-36">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
                <div>
                  <span className="text-[11px] font-mono font-bold text-emerald-700 uppercase">
                    USP-10 • FERNET AES-128-CBC + SHA-256 VAULT
                  </span>
                  <h2 className="text-base font-display font-bold text-slate-900">
                    Encrypted Document &amp; Custody Inspector
                  </h2>
                </div>
                <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg text-xs">
                  {(['preview', 'ocr', 'timeline'] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setRightPaneTab(t)}
                      className={`px-2.5 py-1 rounded-md font-semibold uppercase text-[11px] cursor-pointer ${
                        rightPaneTab === t ? 'bg-[#0F2547] text-white' : 'text-slate-600'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {(detail.documents || []).map((doc: any) => (
                  <button
                    key={doc.id}
                    type="button"
                    onClick={() => loadDocumentPreview(doc.id, doc.content_type)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-semibold border transition cursor-pointer ${
                      activeDocId === doc.id
                        ? 'bg-[#0F2547] text-white border-[#0F2547]'
                        : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>{doc.doc_type}</span>
                  </button>
                ))}
              </div>

              {docSha256 && (
                <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-[11px] font-mono text-emerald-950 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 font-bold">
                    <Lock className="w-3.5 h-3.5 text-emerald-700" />
                    <span>Fernet Decrypted • X-Integrity: {docIntegrity || 'verified'}</span>
                  </div>
                  <span className="truncate max-w-[210px]" title={docSha256}>
                    SHA-256: {docSha256.slice(0, 20)}...
                  </span>
                </div>
              )}

              {rightPaneTab === 'preview' && (
                <div className="rounded-xl border border-slate-300 overflow-hidden bg-slate-900 min-h-[460px] flex items-center justify-center">
                  {!docBlobUrl ? (
                    <div className="p-6 text-center text-xs text-slate-300">
                      No document uploaded for this instrument yet.
                    </div>
                  ) : docMime?.includes('image') ? (
                    <img
                      src={docBlobUrl}
                      alt="Decrypted FDR Receipt Scan"
                      className="max-h-[460px] w-auto object-contain"
                    />
                  ) : (
                    <iframe
                      src={docBlobUrl}
                      title="Decrypted FDR PDF Document Preview"
                      className="w-full h-[460px] border-0 bg-white"
                    />
                  )}
                </div>
              )}

              {rightPaneTab === 'ocr' && (
                <div className="space-y-3 text-xs">
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between font-mono">
                    <span>OCR Engine: {ocrData?.engine || 'READY'}</span>
                    <span className="font-bold text-blue-800">
                      Confidence: {Math.round((ocrData?.confidence || 0.92) * 100)}%
                    </span>
                  </div>
                  <div className="space-y-1">
                    <div className="font-bold text-slate-700">Parsed Structured OCR Fields:</div>
                    <pre className="p-3 rounded-xl bg-slate-900 text-emerald-300 font-mono text-[11px] overflow-x-auto">
                      {JSON.stringify(ocrData?.fields || {}, null, 2)}
                    </pre>
                  </div>
                  <div className="space-y-1">
                    <div className="font-bold text-slate-700">Raw Extracted Text:</div>
                    <pre className="p-3 rounded-xl bg-slate-100 text-slate-800 font-mono text-[11px] max-h-56 overflow-y-auto whitespace-pre-wrap">
                      {ocrData?.text || 'Switch to Scrutiny Officer role to view raw OCR text.'}
                    </pre>
                  </div>
                </div>
              )}

              {rightPaneTab === 'timeline' && (
                <div className="space-y-2.5 max-h-[460px] overflow-y-auto pr-1">
                  {(detail.timeline || []).map((ev: any) => (
                    <div
                      key={ev.id}
                      className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between font-mono text-[11px]">
                        <span className="font-bold text-[#0F2547]">{ev.action}</span>
                        <span className="text-slate-500">
                          {ev.from_status || 'START'} → {ev.to_status || '—'}
                        </span>
                      </div>
                      {ev.note && <p className="text-slate-700">{ev.note}</p>}
                      <div className="text-[10px] text-slate-500 font-mono">
                        Role: {ev.actor_role || 'SYSTEM'} •{' '}
                        {new Date(ev.created_at).toLocaleString()}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Light-Dismiss Modal 1: Raise Discrepancy */}
      <dialog
        ref={discrepancyDialogRef}
        closedby="any"
        aria-labelledby="raise-discrepancy-title"
        className="m-auto rounded-2xl max-w-lg w-full p-0 bg-white shadow-2xl border border-slate-200"
      >
        <div className="p-6 space-y-4">
          <h3 id="raise-discrepancy-title" className="text-lg font-display font-bold text-slate-900">
            Raise Official Scrutiny Discrepancy
          </h3>
          <div>
            <label htmlFor="disc-reason-select" className="block text-xs font-bold text-slate-700 mb-1">
              Statutory Discrepancy Reason Code
            </label>
            <select
              id="disc-reason-select"
              value={discrepancyReason}
              onChange={(e) => setDiscrepancyReason(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white"
            >
              <option value="WRONG_AMOUNT">WRONG_AMOUNT</option>
              <option value="LIEN_NOT_MARKED">LIEN_NOT_MARKED</option>
              <option value="SHORT_VALIDITY">SHORT_VALIDITY</option>
              <option value="SUSPECTED_FORGERY">SUSPECTED_FORGERY</option>
              <option value="MISSING_DOCUMENT">MISSING_DOCUMENT</option>
              <option value="DATA_MISMATCH">DATA_MISMATCH</option>
            </select>
          </div>
          <div>
            <label htmlFor="disc-remarks-input" className="block text-xs font-bold text-slate-700 mb-1">
              Detailed Cure Instructions for Institution (min 3 chars)
            </label>
            <textarea
              id="disc-remarks-input"
              rows={3}
              value={discrepancyRemarks}
              onChange={(e) => setDiscrepancyRemarks(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => discrepancyDialogRef.current?.close()}
              className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-semibold cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                discrepancyDialogRef.current?.close();
                const openFlagIds = (detail?.flags || [])
                  .filter((f: any) => f.status === 'OPEN')
                  .map((f: any) => f.id);
                runAction('Raise Discrepancy', '/raise-discrepancy', {
                  reason_code: discrepancyReason,
                  note: discrepancyRemarks,
                  flag_ids: openFlagIds,
                });
              }}
              className="px-4 py-2 rounded-lg bg-red-700 text-white text-xs font-bold cursor-pointer"
            >
              Confirm &amp; Notify Institution
            </button>
          </div>
        </div>
      </dialog>

      {/* Light-Dismiss Modal 2: Manual Bank Letter Verification */}
      <dialog
        ref={manualVerifyDialogRef}
        closedby="any"
        aria-labelledby="manual-verify-title"
        className="m-auto rounded-2xl max-w-lg w-full p-0 bg-white shadow-2xl border border-slate-200"
      >
        <div className="p-6 space-y-4">
          <h3 id="manual-verify-title" className="text-lg font-display font-bold text-slate-900">
            Record Signed Bank Confirmation Letter (Manual Verification)
          </h3>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-bold mb-1">FDR Number on Letter</label>
              <input
                type="text"
                value={mvFdrNo}
                onChange={(e) => setMvFdrNo(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 font-mono"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">Confirmed Principal (₹)</label>
              <input
                type="number"
                value={mvPrincipal}
                onChange={(e) => setMvPrincipal(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 font-mono"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">Confirmed Issue Date</label>
              <input
                type="date"
                value={mvIssueDate}
                onChange={(e) => setMvIssueDate(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 font-mono"
              />
            </div>
            <div>
              <label className="block font-bold mb-1">Confirmed Maturity Date</label>
              <input
                type="date"
                value={mvMaturityDate}
                onChange={(e) => setMvMaturityDate(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded border border-slate-300 font-mono"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => manualVerifyDialogRef.current?.close()}
              className="px-4 py-2 rounded-lg border border-slate-300 text-xs font-semibold cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                manualVerifyDialogRef.current?.close();
                runAction('Manual Bank Letter Verification', '/manual-verify', {
                  fdr_number: mvFdrNo,
                  amount: Number(mvPrincipal),
                  issue_date: mvIssueDate,
                  maturity_date: mvMaturityDate,
                  depositor_name: mvDepositor,
                  lien_marked: mvLienMarked,
                  remarks: 'Verified against physical signed bank confirmation letter.',
                });
              }}
              className="px-4 py-2 rounded-lg bg-[#0F2547] text-white text-xs font-bold cursor-pointer"
            >
              Save Confirmed Values
            </button>
          </div>
        </div>
      </dialog>
    </div>
  );
};
