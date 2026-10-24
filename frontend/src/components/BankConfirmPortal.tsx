import React, { useEffect, useState } from 'react';
import {
  EyeOff,
  KeyRound,
  Database,
  Wifi,
  WifiOff,
  Sparkles,
} from 'lucide-react';
import { apiFetch, formatINR } from '../api';
import { BankMaster, User } from '../types';

interface BankConfirmPortalProps {
  user: User | null;
  banks: BankMaster[];
  activeBlindToken: string | null;
  setActiveBlindToken: (t: string | null) => void;
  onSwitchAccount: (email: string) => Promise<void>;
  onInspectInstrument: (id: number) => void;
  onRefreshGlobal: () => void;
}

export const BankConfirmPortal: React.FC<BankConfirmPortalProps> = ({
  user,
  banks,
  activeBlindToken,
  setActiveBlindToken,
  onSwitchAccount,
  onRefreshGlobal,
}) => {
  const [subTab, setSubTab] = useState<'nodal' | 'token' | 'cbs'>('nodal');
  const [requests, setRequests] = useState<any[]>([]);
  const [cbsRecords, setCbsRecords] = useState<any[]>([]);
  const [tokenInfo, setTokenInfo] = useState<any | null>(null);
  const [selectedReq, setSelectedReq] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  // Blind response form fields matching BankResponseIn
  const [foundInBank, setFoundInBank] = useState(true);
  const [principalAmount, setPrincipalAmount] = useState('2500000');
  const [issueDate, setIssueDate] = useState('2026-01-15');
  const [maturityDate, setMaturityDate] = useState('2034-01-15');
  const [depositorName, setDepositorName] = useState('Aaranya Institute of Technology');
  const [lienMarked, setLienMarked] = useState(true);
  const [bankStatus, setBankStatus] = useState('ACTIVE');
  const [remarks, setRemarks] = useState('Confirmed against Core Banking System (CBS) master record.');

  const loadBankQueue = async () => {
    setError(null);
    try {
      const data = await apiFetch('/bank/requests');
      setRequests(data || []);
      if (data?.length > 0 && !selectedReq) {
        const pending = data.find((r: any) => r.status === 'PENDING') || data[0];
        setSelectedReq(pending);
      }
    } catch {
      // ignore if not BANK role
    }
  };

  const loadCbsLedger = async () => {
    try {
      const data = await apiFetch('/mock-bank/v1/records');
      setCbsRecords(data || []);
    } catch {
      // ignore
    }
  };

  const loadTokenDetails = async (token: string) => {
    setError(null);
    try {
      const data = await apiFetch(`/bank-link/${token}`);
      setTokenInfo(data);
      setSubTab('token');
    } catch (e: any) {
      setError(e.message || 'Invalid or expired one-time confirmation token');
    }
  };

  useEffect(() => {
    if (activeBlindToken) {
      loadTokenDetails(activeBlindToken);
    }
  }, [activeBlindToken]);

  useEffect(() => {
    if (user?.role === 'BANK' || user?.role === 'ADMIN') {
      loadBankQueue();
      loadCbsLedger();
    }
  }, [user?.email, user?.role]);

  const handlePrefillFromMockCbs = async (fdrNumber: string) => {
    try {
      let recs = cbsRecords;
      if (recs.length === 0) {
        recs = await apiFetch('/mock-bank/v1/records');
        setCbsRecords(recs);
      }
      const match = recs.find((r: any) => r.fdr_number === fdrNumber);
      if (match) {
        setFoundInBank(true);
        setPrincipalAmount(String(match.amount));
        setIssueDate(match.issue_date);
        setMaturityDate(match.maturity_date);
        setDepositorName(match.depositor || '');
        setLienMarked(match.lien_marked);
        setBankStatus(match.status || 'ACTIVE');
        setBanner(`Looked up ${fdrNumber} in Mock CBS Ledger (${formatINR(match.amount)}).`);
      } else {
        setBanner(`No CBS record found for ${fdrNumber}; keeping default test values.`);
      }
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleSubmitNodalResponse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReq) return;
    setError(null);
    setBanner(null);
    try {
      const res = await apiFetch(`/bank/requests/${selectedReq.id}/respond`, {
        method: 'POST',
        body: JSON.stringify({
          found: foundInBank,
          fdr_number: selectedReq.fdr_number,
          ifsc: selectedReq.ifsc,
          depositor_name: depositorName,
          amount: Number(principalAmount),
          issue_date: issueDate,
          maturity_date: maturityDate,
          lien_marked: lienMarked,
          bank_status: bankStatus,
          remarks,
        }),
      });
      await loadBankQueue();
      onRefreshGlobal();
      setBanner(
        `Blind Bank Confirmation submitted for Request #${selectedReq.id}! Verification Outcome: ${res.result || 'RECORDED'}`
      );
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleSubmitTokenResponse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBlindToken) return;
    setError(null);
    setBanner(null);
    try {
      const res = await apiFetch(`/bank-link/${activeBlindToken}`, {
        method: 'POST',
        body: JSON.stringify({
          found: foundInBank,
          fdr_number: tokenInfo?.fdr_number,
          ifsc: tokenInfo?.ifsc,
          depositor_name: depositorName,
          amount: Number(principalAmount),
          issue_date: issueDate,
          maturity_date: maturityDate,
          lien_marked: lienMarked,
          bank_status: bankStatus,
          remarks: 'Confirmed via One-Time Blind Nodal Confirmation Link.',
        }),
      });
      onRefreshGlobal();
      setBanner(
        `One-Time Blind Link Confirmation completed! Result: ${res.result}. ${res.message}`
      );
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleToggleBankAvailability = async (bankId: number, available: boolean) => {
    try {
      if (user?.role !== 'ADMIN') {
        await onSwitchAccount('admin@aicte-demo.in');
      }
      await apiFetch(`/mock-bank/v1/banks/${bankId}/availability?available=${available}`, {
        method: 'POST',
      });
      setBanner(
        `Bank #${bankId} Simulated CBS API is now ${
          available ? 'ONLINE (Instant CBS Verification)' : 'OFFLINE (Forces Graceful Fallback to Blind Nodal Link)'
        }!`
      );
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 font-mono text-xs font-bold">
            USP-05 • ANTI-RUBBER-STAMP BLIND CONFIRMATION
          </span>
          <h1 className="text-xl font-display font-extrabold text-[#0F2547] mt-1">
            Bank Nodal Confirmation Portal &amp; Mock CBS Ledger
          </h1>
          <p className="text-xs text-slate-600">
            Institution-declared amounts and dates are strictly hidden from bank officers so they must enter real CBS figures blind.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {[
            { email: 'bank.sbi@aicte-demo.in', label: 'SBI Nodal Officer' },
            { email: 'bank.canara@aicte-demo.in', label: 'Canara Bank Nodal' },
            { email: 'admin@aicte-demo.in', label: 'Admin (All Banks & CBS)' },
          ].map((b) => (
            <button
              key={b.email}
              type="button"
              onClick={() => onSwitchAccount(b.email)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border cursor-pointer ${
                user?.email === b.email
                  ? 'bg-[#0F2547] text-white border-[#0F2547]'
                  : 'bg-slate-50 text-slate-700 border-slate-300'
              }`}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>

      {/* Sub-navigation */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
        <button
          type="button"
          onClick={() => setSubTab('nodal')}
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold cursor-pointer ${
            subTab === 'nodal' ? 'bg-[#0F2547] text-white' : 'bg-white border border-slate-200 text-slate-700'
          }`}
        >
          <EyeOff className="w-4 h-4" />
          <span>Logged-in Bank Nodal Queue ({requests.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setSubTab('token')}
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold cursor-pointer ${
            subTab === 'token' ? 'bg-[#0F2547] text-white' : 'bg-white border border-slate-200 text-slate-700'
          }`}
        >
          <KeyRound className="w-4 h-4" />
          <span>One-Time Blind Email Link (`/bank-link/:token`)</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setSubTab('cbs');
            loadCbsLedger();
          }}
          className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold cursor-pointer ${
            subTab === 'cbs' ? 'bg-[#0F2547] text-white' : 'bg-white border border-slate-200 text-slate-700'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Mock Bank Core Ledger &amp; Outage Toggle</span>
        </button>
      </div>

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

      {/* SUB-TAB 1: LOGGED-IN BANK NODAL QUEUE */}
      {subTab === 'nodal' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
            <h2 className="text-base font-display font-bold text-slate-900">
              Incoming Blind Verification Requests ({requests.length})
            </h2>
            {user?.role !== 'BANK' ? (
              <p className="text-xs text-slate-500">
                Click <strong>SBI Nodal Officer</strong> or <strong>Canara Bank Nodal</strong> at the top right to view that bank&apos;s queue.
              </p>
            ) : requests.length === 0 ? (
              <p className="text-xs text-slate-500">No verification requests queued for this bank.</p>
            ) : (
              <div className="space-y-2.5 max-h-[500px] overflow-y-auto">
                {requests.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => setSelectedReq(r)}
                    className={`p-3.5 rounded-xl border text-xs cursor-pointer transition space-y-1 ${
                      selectedReq?.id === r.id
                        ? 'bg-blue-50 border-blue-400'
                        : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex items-center justify-between font-mono">
                      <span className="font-bold text-[#0F2547]">
                        Req #{r.id} • {r.fdr_number}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded font-bold ${
                          r.status === 'PENDING'
                            ? 'bg-amber-100 text-amber-900'
                            : 'bg-emerald-100 text-emerald-900'
                        }`}
                      >
                        {r.result || r.status}
                      </span>
                    </div>
                    <div className="font-semibold text-slate-800">{r.institution}</div>
                    <div className="text-[11px] font-mono text-slate-500">
                      IFSC: {r.ifsc} • Channel: {r.channel}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
            {!selectedReq ? (
              <p className="text-xs text-slate-500 py-8 text-center">
                Select a verification request on the left to key in blind CBS figures.
              </p>
            ) : (
              <form onSubmit={handleSubmitNodalResponse} className="space-y-4">
                <div className="p-4 rounded-xl bg-amber-50 border border-amber-300 text-xs text-amber-950 flex flex-wrap items-center justify-between gap-2">
                  <div className="space-y-0.5">
                    <div className="font-bold flex items-center gap-1.5">
                      <EyeOff className="w-4 h-4 text-amber-800" />
                      <span>Blind Entry Mode Active for {selectedReq.fdr_number}</span>
                    </div>
                    <p className="text-[11px]">
                      Notice that AICTE does <strong>not</strong> reveal the institution&apos;s declared principal or maturity date. Enter figures from your CBS below:
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handlePrefillFromMockCbs(selectedReq.fdr_number)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#0F2547] text-amber-300 font-bold text-xs cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Lookup in Mock CBS Ledger</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">
                      Principal Amount in Bank CBS (₹) *
                    </label>
                    <input
                      type="number"
                      required
                      value={principalAmount}
                      onChange={(e) => setPrincipalAmount(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 font-mono font-bold"
                    />
                  </div>
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">
                      Depositor Name in Bank CBS *
                    </label>
                    <input
                      type="text"
                      required
                      value={depositorName}
                      onChange={(e) => setDepositorName(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300"
                    />
                  </div>
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Issue Date *</label>
                    <input
                      type="date"
                      required
                      value={issueDate}
                      onChange={(e) => setIssueDate(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Maturity Date *</label>
                    <input
                      type="date"
                      required
                      value={maturityDate}
                      onChange={(e) => setMaturityDate(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">CBS Account Status *</label>
                    <select
                      value={bankStatus}
                      onChange={(e) => setBankStatus(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white font-mono"
                    >
                      <option value="ACTIVE">ACTIVE (Lien Intact)</option>
                      <option value="ENCASHED">ENCASHED (Prematurely Closed!)</option>
                      <option value="CLOSED">CLOSED</option>
                    </select>
                  </div>
                  <div className="flex items-center pt-5">
                    <label className="inline-flex items-center gap-2 font-bold cursor-pointer">
                      <input
                        type="checkbox"
                        checked={lienMarked}
                        onChange={(e) => setLienMarked(e.target.checked)}
                      />
                      <span>AICTE Lien Marked in CBS</span>
                    </label>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="submit"
                    className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold cursor-pointer"
                  >
                    Submit Official Blind Bank Confirmation
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* SUB-TAB 2: ONE-TIME BLIND CONFIRMATION LINK */}
      {subTab === 'token' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 max-w-2xl mx-auto space-y-4">
          <div>
            <span className="text-xs font-mono font-bold text-amber-700 uppercase">
              NO-LOGIN ONE-TIME SIGNED TOKEN (`/api/v1/bank-link/:token`)
            </span>
            <h2 className="text-lg font-display font-bold text-slate-900">
              Simulated Email One-Time Blind Bank Confirmation Link
            </h2>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Paste confirmation_token here..."
              value={activeBlindToken || ''}
              onChange={(e) => setActiveBlindToken(e.target.value)}
              className="flex-1 px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono"
            />
            <button
              type="button"
              onClick={() => activeBlindToken && loadTokenDetails(activeBlindToken)}
              className="px-4 py-2 rounded-lg bg-[#0F2547] text-white text-xs font-bold cursor-pointer"
            >
              Load Token
            </button>
          </div>

          {tokenInfo && (
            <form onSubmit={handleSubmitTokenResponse} className="space-y-4 pt-2 border-t border-slate-200">
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1 font-mono">
                <div className="font-bold text-slate-900">
                  FDR Number: {tokenInfo.fdr_number} • Bank: {tokenInfo.bank}
                </div>
                <div>
                  IFSC: {tokenInfo.ifsc} • Institution: {tokenInfo.institution}
                </div>
                <div className="text-amber-800 font-bold">
                  {tokenInfo.note}
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => handlePrefillFromMockCbs(tokenInfo.fdr_number)}
                  className="px-3 py-1.5 rounded-lg bg-amber-100 text-amber-950 text-xs font-bold cursor-pointer"
                >
                  Auto-Fill from Mock CBS Record ({tokenInfo.fdr_number})
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block font-bold mb-1">Principal Amount (₹)</label>
                  <input
                    type="number"
                    value={principalAmount}
                    onChange={(e) => setPrincipalAmount(e.target.value)}
                    className="w-full px-3 py-2 rounded border border-slate-300 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Depositor Name</label>
                  <input
                    type="text"
                    value={depositorName}
                    onChange={(e) => setDepositorName(e.target.value)}
                    className="w-full px-3 py-2 rounded border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Issue Date</label>
                  <input
                    type="date"
                    value={issueDate}
                    onChange={(e) => setIssueDate(e.target.value)}
                    className="w-full px-3 py-2 rounded border border-slate-300 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-bold mb-1">Maturity Date</label>
                  <input
                    type="date"
                    value={maturityDate}
                    onChange={(e) => setMaturityDate(e.target.value)}
                    className="w-full px-3 py-2 rounded border border-slate-300 font-mono"
                  />
                </div>
              </div>
              <button
                type="submit"
                className="w-full py-2.5 rounded-xl bg-emerald-700 text-white text-xs font-bold cursor-pointer"
              >
                Submit One-Time Blind Bank Confirmation
              </button>
            </form>
          )}
        </div>
      )}

      {/* SUB-TAB 3: MOCK CBS LEDGER & OUTAGE TOGGLE */}
      {subTab === 'cbs' && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
            <h2 className="text-base font-display font-bold text-slate-900">
              Simulated Bank CBS API Availability (Graceful Fallback Demo)
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {banks.slice(0, 4).map((b) => (
                <div key={b.id} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
                  <div className="font-bold text-slate-900">
                    {b.name} ({b.short_code})
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleToggleBankAvailability(b.id, true)}
                      className="flex-1 inline-flex items-center justify-center gap-1 py-1.5 rounded-lg bg-emerald-700 text-white font-semibold cursor-pointer"
                    >
                      <Wifi className="w-3.5 h-3.5" /> Set Online
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleBankAvailability(b.id, false)}
                      className="flex-1 inline-flex items-center justify-center gap-1 py-1.5 rounded-lg bg-rose-700 text-white font-semibold cursor-pointer"
                    >
                      <WifiOff className="w-3.5 h-3.5" /> Set Offline
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
            <h2 className="text-base font-display font-bold text-slate-900">
              Mock Bank Core Banking System (CBS) Ground-Truth Records ({cbsRecords.length})
            </h2>
            <div className="table-wrapper rounded-xl border border-slate-200">
              <table className="text-xs text-left">
                <thead className="bg-slate-100 text-slate-700 font-mono text-[11px] uppercase">
                  <tr>
                    <th className="p-2.5">CBS ID</th>
                    <th className="p-2.5">FDR Number</th>
                    <th className="p-2.5">Bank &amp; IFSC</th>
                    <th className="p-2.5">Principal</th>
                    <th className="p-2.5">Maturity</th>
                    <th className="p-2.5">Lien Marked</th>
                    <th className="p-2.5">Status at Bank</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {cbsRecords.slice(0, 30).map((rec) => (
                    <tr key={rec.id} className="hover:bg-slate-50 font-mono">
                      <td className="p-2.5">#{rec.id}</td>
                      <th scope="row" className="p-2.5 font-bold text-slate-900">
                        {rec.fdr_number}
                      </th>
                      <td className="p-2.5">
                        {rec.bank} ({rec.ifsc})
                      </td>
                      <td className="p-2.5 font-bold">{formatINR(rec.amount)}</td>
                      <td className="p-2.5">{rec.maturity_date}</td>
                      <td className="p-2.5">{rec.lien_marked ? 'YES' : 'NO'}</td>
                      <td className="p-2.5">
                        <span
                          className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                            rec.status === 'ACTIVE'
                              ? 'bg-emerald-100 text-emerald-900'
                              : 'bg-red-100 text-red-900'
                          }`}
                        >
                          {rec.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
