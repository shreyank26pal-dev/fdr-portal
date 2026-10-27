import React, { useEffect, useState } from 'react';
import {
  Building2,
  FilePlus2,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Lock,
  RefreshCw,
  Upload,
  ArrowRight,
  Download,
  Eye,
  PackageCheck,
  Award,
  FileText,
  Fingerprint,
  ShieldCheck,
  ExternalLink,
  Printer,
  X,
  Check,
} from 'lucide-react';
import {
  apiFetch,
  fetchBlobWithHeaders,
  formatINR,
  loadSampleAsFile,
} from '../api';
import { BankMaster, User } from '../types';

interface InstitutionPortalProps {
  user: User | null;
  banks: BankMaster[];
  onSwitchAccount: (email: string) => Promise<void>;
  onInspectInstrument: (id: number) => void;
  onRefreshGlobal: () => void;
}

export const InstitutionPortal: React.FC<InstitutionPortalProps> = ({
  user,
  banks,
  onSwitchAccount,
  onInspectInstrument,
  onRefreshGlobal,
}) => {
  const [overview, setOverview] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bannerMsg, setBannerMsg] = useState<string | null>(null);

  const [subTab, setSubTab] = useState<'dashboard' | 'wizard' | 'release'>('dashboard');
  const [renewingFrom, setRenewingFrom] = useState<any | null>(null);

  // Wizard state matching InstrumentIn schema
  const [fdrNumber, setFdrNumber] = useState('SBI00991100');
  const [bankName, setBankName] = useState('State Bank of India');
  const [branchName, setBranchName] = useState('Pune Main Branch');
  const [ifscCode, setIfscCode] = useState('SBIN0004321');
  const [principalAmount, setPrincipalAmount] = useState('2500000');
  const [depositorName, setDepositorName] = useState('Aaranya Institute of Technology');
  const [issueDate, setIssueDate] = useState('2026-01-15');
  const [maturityDate, setMaturityDate] = useState('2034-01-15');
  const [lienMarked, setLienMarked] = useState(true);
  const [lienInFavourOf, setLienInFavourOf] = useState('Member Secretary, AICTE');
  const [purpose, setPurpose] = useState('NEW_APPROVAL');

  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [lienFile, setLienFile] = useState<File | null>(null);
  const [ocrPreview, setOcrPreview] = useState<any | null>(null);
  const [dupCheckResult, setDupCheckResult] = useState<any | null>(null);
  const [createdCase, setCreatedCase] = useState<any | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  // Release / Refund state
  const [selectedRefundFdrId, setSelectedRefundFdrId] = useState<number | ''>('');
  const [releaseGround, setReleaseGround] = useState('EXCESS_DEPOSIT');
  const [releaseRemarks, setReleaseRemarks] = useState(
    'Extra intake deposit eligible for formal AICTE discharge while maintaining statutory minimum security.'
  );
  const [refundDetail, setRefundDetail] = useState<any | null>(null);

  // India Stack & Certificate state
  const [showDigiLockerModal, setShowDigiLockerModal] = useState(false);
  const [digiLockerLoading, setDigiLockerLoading] = useState(false);
  const [digiLockerVerified, setDigiLockerVerified] = useState(false);
  const [digiLockerDocId, setDigiLockerDocId] = useState<string | null>(null);

  const [showAadhaarModal, setShowAadhaarModal] = useState(false);
  const [aadhaarOtp, setAadhaarOtp] = useState('');
  const [aadhaarOtpSent, setAadhaarOtpSent] = useState(false);
  const [aadhaarSigned, setAadhaarSigned] = useState(false);
  const [aadhaarSignHash, setAadhaarSignHash] = useState<string | null>(null);
  const [aadhaarConsent, setAadhaarConsent] = useState(false);
  const [aadhaarError, setAadhaarError] = useState<string | null>(null);

  const [showCertificateModal, setShowCertificateModal] = useState(false);

  const loadOverview = async () => {
    setError(null);
    try {
      const data = await apiFetch('/me/overview');
      setOverview(data);
      if (data?.institution?.name) {
        setDepositorName(data.institution.name);
      }
      if (data?.instruments?.length && !selectedRefundFdrId) {
        const candidate =
          data.instruments.find(
            (i: any) =>
              i.purpose === 'INCREASE_IN_INTAKE' ||
              i.status === 'ACTIVE' ||
              i.status === 'EXPIRING_SOON'
          ) || data.instruments[0];
        if (candidate) setSelectedRefundFdrId(candidate.id);
      }
      if (data?.refunds?.length && !refundDetail) {
        const firstRefund = await apiFetch(`/refunds/${data.refunds[0].id}`).catch(() => null);
        if (firstRefund) setRefundDetail(firstRefund);
      }
    } catch (e: any) {
      setError(e.message || 'Could not load institution overview');
    }
  };

  useEffect(() => {
    if (user?.role === 'INSTITUTION') {
      loadOverview();
    }
  }, [user?.email, user?.role]);

  const handleLoadSampleScenario = async (
    scenario: 'clean' | 'tampered_words' | 'duplicate'
  ) => {
    setError(null);
    setBannerMsg(null);
    setCreatedCase(null);
    setBusyAction('Loading synthetic PDF & running OCR (/api/v1/ocr/extract)...');
    try {
      const filename =
        scenario === 'clean'
          ? 'fdr_demo_correct.pdf'
          : scenario === 'tampered_words'
          ? 'fdr_demo_tampered_words.pdf'
          : 'fdr_demo_duplicate_number.pdf';

      const rFile = await loadSampleAsFile(filename);
      const lFile = await loadSampleAsFile('lien_letter_demo.pdf');
      setReceiptFile(rFile);
      setLienFile(lFile);

      const fd = new FormData();
      fd.append('file', rFile);
      const ocrData = await apiFetch('/ocr/extract', {
        method: 'POST',
        body: fd,
      });
      setOcrPreview(ocrData);

      const pf = ocrData.prefill || {};
      if (pf.fdr_number) setFdrNumber(pf.fdr_number);
      if (pf.bank_name) setBankName(pf.bank_name);
      if (pf.ifsc) setIfscCode(pf.ifsc);
      if (pf.amount) setPrincipalAmount(String(pf.amount));
      if (pf.issue_date) setIssueDate(pf.issue_date);
      if (pf.maturity_date) setMaturityDate(pf.maturity_date);
      if (pf.depositor_name) setDepositorName(pf.depositor_name);
      if (typeof pf.lien_marked === 'boolean') setLienMarked(pf.lien_marked);

      if (scenario === 'clean') {
        setDupCheckResult(null);
        setBannerMsg(
          `Loaded '${filename}' (${pf.fdr_number}) & auto-filled form via OCR (${Math.round(
            (ocrData.ocr?.confidence || 0.95) * 100
          )}% confidence). Matches SBI CBS record! Click Step 2 below to create draft & cross-check.`
        );
      } else if (scenario === 'tampered_words') {
        setDupCheckResult(null);
        setBannerMsg(
          `Loaded Tampered Receipt '${filename}' (${pf.fdr_number}): Figures claim ${formatINR(
            pf.amount
          )} while words on PDF state '${
            ocrData.ocr?.amount_in_words || 'Two Lakh Fifty Thousand'
          }'. Click Step 2 below to watch Rule R15 fire immediately!`
        );
      } else {
        const dup = await apiFetch('/instruments/check-duplicate', {
          method: 'POST',
          body: JSON.stringify({ fdr_number: pf.fdr_number, ifsc: pf.ifsc }),
        });
        setDupCheckResult(dup);
        setBannerMsg(
          `Loaded Duplicate Receipt '${filename}' (${pf.fdr_number}). Pre-save duplicate check flagged cross-institution reuse (Rule R09)!`
        );
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load sample scenario');
    } finally {
      setBusyAction(null);
    }
  };

  const handleManualFileOcr = async (file: File) => {
    setReceiptFile(file);
    setBusyAction('Extracting fields via OCR...');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const ocrData = await apiFetch('/ocr/extract', {
        method: 'POST',
        body: fd,
      });
      setOcrPreview(ocrData);
      const pf = ocrData.prefill || {};
      if (pf.fdr_number) setFdrNumber(pf.fdr_number);
      if (pf.bank_name) setBankName(pf.bank_name);
      if (pf.ifsc) setIfscCode(pf.ifsc);
      if (pf.amount) setPrincipalAmount(String(pf.amount));
      if (pf.issue_date) setIssueDate(pf.issue_date);
      if (pf.maturity_date) setMaturityDate(pf.maturity_date);
      if (pf.depositor_name) setDepositorName(pf.depositor_name);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusyAction(null);
    }
  };

  const handleCheckDuplicateBlur = async () => {
    if (!fdrNumber.trim()) return;
    try {
      const res = await apiFetch('/instruments/check-duplicate', {
        method: 'POST',
        body: JSON.stringify({
          fdr_number: fdrNumber.trim(),
          ifsc: ifscCode.trim(),
          bank_name: bankName.trim(),
        }),
      });
      setDupCheckResult(res);
    } catch {
      // ignore
    }
  };

  const handleDigiLockerImport = async () => {
    setDigiLockerLoading(true);
    setError(null);
    try {
      // Simulate real-time DigiLocker PKI fetch & decryption delay
      await new Promise((r) => setTimeout(r, 600));

      const rFile = await loadSampleAsFile('fdr_demo_correct.pdf');
      const lFile = await loadSampleAsFile('lien_letter_demo.pdf');

      setReceiptFile(rFile);
      setLienFile(lFile);

      setFdrNumber('SBI00991100');
      setBankName('State Bank of India');
      setBranchName('Pune Main Branch');
      setIfscCode('SBIN0004321');
      setPrincipalAmount('2500000');
      setIssueDate('2026-01-15');
      setMaturityDate('2034-01-15');
      setLienMarked(true);
      setLienInFavourOf('Member Secretary, AICTE');

      setDigiLockerVerified(true);
      setDigiLockerDocId('DL-SBI-FDR-2026-991100');
      setShowDigiLockerModal(false);
      setDupCheckResult(null);

      setBannerMsg(
        'DigiLocker Import Verified! Successfully pulled digital FDR Certificate & Lien Confirmation directly from State Bank of India with PKI certificate chain.'
      );
    } catch (e: any) {
      setError(e.message || 'DigiLocker fetch failed');
    } finally {
      setDigiLockerLoading(false);
    }
  };

  const handleVerifyAadhaarOtp = () => {
    if (!aadhaarConsent) {
      setAadhaarError('Please check the consent box to proceed with legal eSign.');
      return;
    }
    if (aadhaarOtp.trim() !== '123456') {
      setAadhaarError('Invalid OTP! Please enter demo OTP: 123456');
      return;
    }
    setAadhaarError(null);
    setAadhaarSigned(true);
    setAadhaarSignHash('SHA256: 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069');
    setShowAadhaarModal(false);
    setBannerMsg(
      'Statutory Undertaking digitally eSigned via Aadhaar OTP (Dr. Rajesh Sharma, Signatory Ref: XXXX-8921). Ready for submission!'
    );
  };

  const handleCreateDraftAndUploadDocs = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBannerMsg(null);
    setBusyAction('Creating FDR draft, encrypting PDFs & running 20-Rule Point-of-Entry Cross-Check...');
    try {
      const payload = {
        fdr_number: fdrNumber.trim(),
        bank_name: bankName.trim(),
        branch: branchName.trim(),
        ifsc: ifscCode.trim().toUpperCase(),
        depositor_name: depositorName.trim(),
        amount: Number(principalAmount),
        issue_date: issueDate,
        maturity_date: maturityDate,
        lien_marked: lienMarked,
        lien_in_favour_of: lienInFavourOf.trim(),
        purpose,
      };

      const endpoint = renewingFrom
        ? `/instruments/${renewingFrom.id}/renew`
        : '/instruments';

      const created = await apiFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const instId = created.instrument.id;

      // Upload FDR_SCAN
      const rFile = receiptFile || (await loadSampleAsFile('fdr_demo_correct.pdf'));
      const fd1 = new FormData();
      fd1.append('doc_type', renewingFrom ? 'RENEWAL_FDR' : 'FDR_SCAN');
      fd1.append('file', rFile);
      await apiFetch(`/instruments/${instId}/documents`, {
        method: 'POST',
        body: fd1,
      });

      // Upload LIEN_LETTER
      const lFile = lienFile || (await loadSampleAsFile('lien_letter_demo.pdf'));
      const fd2 = new FormData();
      fd2.append('doc_type', 'LIEN_LETTER');
      fd2.append('file', lFile);
      await apiFetch(`/instruments/${instId}/documents`, {
        method: 'POST',
        body: fd2,
      });

      const fullDetail = await apiFetch(`/instruments/${instId}`);
      setCreatedCase(fullDetail);
      await loadOverview();
      onRefreshGlobal();
      setBannerMsg(
        renewingFrom
          ? `Renewal Draft #${instId} created & linked to old FDR #${renewingFrom.fdr_number}. Click Step 3 (Submit) to lift the Institution Lock!`
          : `Draft FDR #${instId} saved and cross-checked against uploaded PDFs! Inspect the Dual-Truth table below before clicking Step 3 (Submit).`
      );
    } catch (e: any) {
      setError(e.message || 'Failed to create FDR draft');
    } finally {
      setBusyAction(null);
    }
  };

  const handleFinalSubmit = async () => {
    if (!createdCase?.instrument?.id) return;
    setError(null);
    setBusyAction('Submitting FDR to AICTE Scrutiny Queue...');
    try {
      const submitted = await apiFetch(
        `/instruments/${createdCase.instrument.id}/submit`,
        { method: 'POST' }
      );
      setCreatedCase(submitted);
      setRenewingFrom(null);
      await loadOverview();
      onRefreshGlobal();
      setBannerMsg(
        `Submitted! Official Acknowledgement No: ${submitted.instrument.ack_number}. You can now inspect it in the Dual-Truth Split-Screen.`
      );
    } catch (e: any) {
      setError(e.message || 'Submission failed');
    } finally {
      setBusyAction(null);
    }
  };

  const handleUploadUndertakingAndRequestRefund = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRefundFdrId) return;
    setError(null);
    setBannerMsg(null);
    setBusyAction('Creating Release Request, Uploading Undertaking PDF & Running Pre-Condition Engine...');
    try {
      // 1. Create Refund Request
      const createdRefund = await apiFetch('/refunds', {
        method: 'POST',
        body: JSON.stringify({
          instrument_id: Number(selectedRefundFdrId),
          ground: releaseGround,
          reason_text: releaseRemarks,
        }),
      });

      // 2. Upload UNDERTAKING document to the refund request (which auto-rechecks preconditions!)
      const uFile = await loadSampleAsFile('undertaking_demo.pdf');
      const fd = new FormData();
      fd.append('doc_type', 'UNDERTAKING');
      fd.append('file', uFile);
      const updatedRefund = await apiFetch(`/refunds/${createdRefund.id}/documents`, {
        method: 'POST',
        body: fd,
      });

      setRefundDetail(updatedRefund);
      await loadOverview();
      onRefreshGlobal();
      setBannerMsg(
        `Release Request ${updatedRefund.ref_number} submitted! Current Status: ${updatedRefund.status}.`
      );
    } catch (e: any) {
      setError(e.message || 'Release request could not be created');
    } finally {
      setBusyAction(null);
    }
  };

  const handleInspectRefundTracker = async (refundId: number) => {
    try {
      const data = await apiFetch(`/refunds/${refundId}`);
      setRefundDetail(data);
      setSubTab('release');
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleDownloadDischargePdf = async (docId: number) => {
    try {
      const { url, filename } = await fetchBlobWithHeaders(`/documents/${docId}/download`);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || `discharge_letter_${docId}.pdf`;
      a.click();
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (user?.role !== 'INSTITUTION') {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="space-y-1">
          <span className="text-xs font-mono font-bold uppercase text-[#EA580C]">
            INSTITUTION SELF-SERVICE PORTAL
          </span>
          <h2 className="text-xl font-display font-bold text-[#0F2547]">
            Switch to a Demo Institution Account to Use the Institution Workspace
          </h2>
          <p className="text-xs text-slate-600">
            You are currently signed in as <strong>{user?.email}</strong> ({user?.role}). Click any of the 3 demo institutions below to switch instantly:
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          <button
            type="button"
            onClick={() => onSwitchAccount('college1@aicte-demo.in')}
            className="p-4 rounded-xl border border-blue-200 bg-blue-50/60 hover:bg-blue-100/70 text-left space-y-1 transition cursor-pointer"
          >
            <div className="font-mono text-xs font-bold text-blue-900">college1@aicte-demo.in</div>
            <div className="font-display font-bold text-sm text-slate-900">
              Institution 1 — Pune (Healthy + Maturing + Extra Intake FDR)
            </div>
            <p className="text-xs text-slate-600">
              Has active FDRs, a maturing FDR (~95d) for time-travel, and an extra intake FDR eligible for release.
            </p>
          </button>

          <button
            type="button"
            onClick={() => onSwitchAccount('college5@aicte-demo.in')}
            className="p-4 rounded-xl border border-red-200 bg-red-50/60 hover:bg-red-100/70 text-left space-y-1 transition cursor-pointer"
          >
            <div className="font-mono text-xs font-bold text-red-900">college5@aicte-demo.in</div>
            <div className="font-display font-bold text-sm text-slate-900">
              Institution 5 — Locked Due to Overdue Renewal (HTTP 423)
            </div>
            <p className="text-xs text-slate-600">
              Demonstrates automatic lock blocking new applications until the overdue FDR is renewed.
            </p>
          </button>

          <button
            type="button"
            onClick={() => onSwitchAccount('college8@aicte-demo.in')}
            className="p-4 rounded-xl border border-amber-200 bg-amber-50/60 hover:bg-amber-100/70 text-left space-y-1 transition cursor-pointer"
          >
            <div className="font-mono text-xs font-bold text-amber-900">college8@aicte-demo.in</div>
            <div className="font-display font-bold text-sm text-slate-900">
              Institution 8 — Open Compliance Case Blocks Release
            </div>
            <p className="text-xs text-slate-600">
              Demonstrates Guarded Release Pre-Condition Engine blocking refund due to an open compliance case.
            </p>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Institution Header & Quick 3-College Switcher */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-[#0F2547] text-amber-300 font-mono text-xs font-bold">
              {overview?.institution?.aicte_id || 'AICTE-INST'}
            </span>
            <span className="text-xs font-mono text-slate-500">
              {overview?.institution?.region} Region • Held Security:{' '}
              <strong>{formatINR(overview?.totals?.held_amount || 0)}</strong> ({overview?.totals?.held_count || 0} FDRs)
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-display font-extrabold text-[#0F2547]">
            {overview?.institution?.name || user.full_name}
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowCertificateModal(true)}
            className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-50 text-amber-900 border border-amber-300 hover:bg-amber-100 flex items-center gap-1.5 shadow-2xs transition cursor-pointer"
          >
            <Award className="w-4 h-4 text-amber-600" />
            <span>AICTE Deposit Certificate</span>
          </button>

          <span className="text-xs font-semibold text-slate-500 mr-1">Demo Scenarios:</span>
          {[
            { email: 'college1@aicte-demo.in', label: 'College 1 (Normal)' },
            { email: 'college5@aicte-demo.in', label: 'College 5 (Locked 423)' },
            { email: 'college8@aicte-demo.in', label: 'College 8 (Compliance Block)' },
          ].map((c) => (
            <button
              key={c.email}
              type="button"
              onClick={() => onSwitchAccount(c.email)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition cursor-pointer ${
                user.email === c.email
                  ? 'bg-[#0F2547] text-white border-[#0F2547]'
                  : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Overdue Renewal Institution Lock Banner (HTTP 423) */}
      {overview?.locked && (
        <div
          role="alert"
          className="rounded-2xl border-2 border-red-600 bg-red-50 p-5 text-red-950 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4"
        >
          <div className="flex items-start gap-3">
            <Lock className="w-7 h-7 text-red-700 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-red-700 text-white font-mono text-[11px] font-bold">
                  HTTP 423 LOCKED
                </span>
                <h2 className="text-base font-display font-extrabold">
                  Institution Portal Locked — Overdue FDR Renewal Pending
                </h2>
              </div>
              <p className="text-xs text-red-900">
                Fresh FDR applications are blocked until the overdue instrument is renewed via{' '}
                <code className="font-mono font-bold">POST /api/v1/instruments/&#123;id&#125;/renew</code>:
              </p>
              <ul className="list-disc list-inside text-xs font-semibold space-y-0.5">
                {(overview.lock_reasons || []).map((r: any, idx: number) => (
                  <li key={idx}>
                    {typeof r === 'string'
                      ? r
                      : `FDR ${r.fdr_number || '#' + r.instrument_id} (${r.status}): ${r.reason || 'Renewal overdue'}`}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {overview.instruments?.find((i: any) =>
            ['ACTION_REQUIRED', 'MATURED', 'OVERDUE'].includes(i.status)
          ) && (
            <button
              type="button"
              onClick={() => {
                const overdue = overview.instruments.find((i: any) =>
                  ['ACTION_REQUIRED', 'MATURED', 'OVERDUE'].includes(i.status)
                );
                setRenewingFrom(overdue);
                setFdrNumber(`${overdue.fdr_number}R`);
                setPrincipalAmount(String(overdue.amount || 1500000));
                setBankName(overdue.bank_name || 'State Bank of India');
                setIfscCode(overdue.ifsc || 'SBIN0004321');
                setSubTab('wizard');
              }}
              className="px-4 py-2.5 rounded-xl bg-red-700 hover:bg-red-800 text-white font-bold text-xs shrink-0 cursor-pointer shadow-xs"
            >
              Renew Overdue FDR Now &amp; Unlock Portal →
            </button>
          )}
        </div>
      )}

      {/* Sub-navigation Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
        <button
          type="button"
          onClick={() => setSubTab('dashboard')}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
            subTab === 'dashboard'
              ? 'bg-[#0F2547] text-white shadow-xs'
              : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          <Building2 className="w-4 h-4" />
          <span>My FDR Portfolio &amp; Action Required</span>
        </button>

        <button
          type="button"
          onClick={() => setSubTab('wizard')}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
            subTab === 'wizard'
              ? 'bg-[#0F2547] text-white shadow-xs'
              : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          <FilePlus2 className="w-4 h-4" />
          <span>
            {renewingFrom
              ? `Renew Overdue FDR (#${renewingFrom.fdr_number})`
              : 'Submit New FDR (Live OCR & 20-Rule Check)'}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setSubTab('release')}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
            subTab === 'release'
              ? 'bg-[#0F2547] text-white shadow-xs'
              : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          <PackageCheck className="w-4 h-4" />
          <span>Release / Refund Request &amp; 5-Step Courier Tracker</span>
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="p-4 rounded-xl bg-red-50 border border-red-300 text-red-900 text-xs font-semibold flex items-center justify-between"
        >
          <span>❌ {error}</span>
          <button type="button" onClick={() => setError(null)} className="underline ml-4 cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {bannerMsg && (
        <div
          role="status"
          className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs font-semibold flex items-center justify-between"
        >
          <span>✅ {bannerMsg}</span>
          <button type="button" onClick={() => setBannerMsg(null)} className="underline ml-4 cursor-pointer">
            Close
          </button>
        </div>
      )}

      {/* TAB 1: INSTITUTION DASHBOARD */}
      {subTab === 'dashboard' && overview && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-display font-bold text-slate-900 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-[#EA580C]" />
                  <span>Action Required From Your Institution ({overview.action_required?.length || 0})</span>
                </h2>
                <button
                  type="button"
                  onClick={loadOverview}
                  className="inline-flex items-center gap-1 text-xs text-blue-700 font-semibold hover:underline cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" /> Refresh
                </button>
              </div>
              {overview.action_required?.length === 0 ? (
                <p className="text-xs text-slate-500 py-3">
                  No pending actions from your institution right now. All submitted instruments are with AICTE or active.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {overview.action_required.map((item: any) => (
                    <div
                      key={item.instrument_id}
                      className="p-3.5 rounded-xl bg-amber-50/80 border border-amber-200 flex flex-wrap items-center justify-between gap-3"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-slate-900">
                            {item.fdr_number}
                          </span>
                          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-200/80 text-amber-950 font-semibold">
                            {item.status}
                          </span>
                        </div>
                        <p className="text-xs text-slate-700">{item.text}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {['ACTION_REQUIRED', 'MATURED', 'OVERDUE'].includes(item.status) && (
                          <button
                            type="button"
                            onClick={() => {
                              const full = overview.instruments.find(
                                (x: any) => x.id === item.instrument_id
                              );
                              if (full) {
                                setRenewingFrom(full);
                                setFdrNumber(`${full.fdr_number}R`);
                                setPrincipalAmount(String(full.amount || 1500000));
                                setSubTab('wizard');
                              }
                            }}
                            className="px-3 py-1.5 rounded-lg bg-[#EA580C] text-white text-xs font-bold cursor-pointer"
                          >
                            Renew FDR
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => onInspectInstrument(item.instrument_id)}
                          className="px-3 py-1.5 rounded-lg bg-[#0F2547] text-white text-xs font-semibold cursor-pointer"
                        >
                          Open Split-Screen →
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Upcoming Deadlines */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
              <div>
                <h2 className="text-sm font-display font-bold text-slate-900 mb-2">
                  Upcoming Maturity Deadlines
                </h2>
                {overview.upcoming_deadlines?.length === 0 ? (
                  <p className="text-xs text-slate-500">No active FDRs listed.</p>
                ) : (
                  <div className="space-y-2">
                    {overview.upcoming_deadlines?.map((d: any) => (
                      <div
                        key={d.instrument_id}
                        className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs"
                      >
                        <div>
                          <div className="font-mono font-bold text-slate-900">{d.fdr_number}</div>
                          <div className="text-slate-500">Matures: {d.maturity_date}</div>
                        </div>
                        <span
                          className={`font-mono font-bold px-2 py-0.5 rounded ${
                            d.days_left <= 30
                              ? 'bg-red-100 text-red-900'
                              : 'bg-amber-100 text-amber-900'
                          }`}
                        >
                          {d.days_left}d left
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Responsive Table for Institution's Instruments */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2
                id="inst-instruments-table-caption"
                className="text-base font-display font-bold text-slate-900"
              >
                My Registered FDR Instruments ({overview.instruments?.length || 0})
              </h2>
              <button
                type="button"
                onClick={() => {
                  setRenewingFrom(null);
                  setSubTab('wizard');
                }}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#0F2547] hover:bg-blue-800 text-white text-xs font-bold cursor-pointer"
              >
                <FilePlus2 className="w-4 h-4" />
                <span>+ New FDR Submission</span>
              </button>
            </div>

            <div
              tabIndex={0}
              role="region"
              aria-labelledby="inst-instruments-table-caption"
              className="table-wrapper rounded-xl border border-slate-200"
            >
              <table className="text-xs text-left">
                <caption className="sr-only">
                  Registered Fixed Deposit Receipts for your institution
                </caption>
                <thead className="bg-slate-100 text-slate-700 uppercase font-mono text-[11px]">
                  <tr>
                    <th className="p-3">FDR Number</th>
                    <th className="p-3">Bank &amp; IFSC</th>
                    <th className="p-3">Principal</th>
                    <th className="p-3">Purpose</th>
                    <th className="p-3">Maturity</th>
                    <th className="p-3">Status &amp; Trust</th>
                    <th className="p-3">Next Step</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {(overview.instruments || []).map((inst: any) => (
                    <tr key={inst.id} className="hover:bg-slate-50/80">
                      <th scope="row" className="p-3 font-mono font-bold text-slate-900">
                        <div>{inst.fdr_number}</div>
                        <div className="text-[10px] font-normal text-slate-500">
                          {inst.ack_number || `Draft #${inst.id}`}
                        </div>
                      </th>
                      <td data-label="Bank" className="p-3">
                        <div className="font-semibold text-slate-800">{inst.bank_name}</div>
                        <div className="font-mono text-[11px] text-slate-500">{inst.ifsc}</div>
                      </td>
                      <td data-label="Principal" className="p-3 font-mono font-bold text-slate-900">
                        {formatINR(inst.amount)}
                      </td>
                      <td data-label="Purpose" className="p-3">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-800">
                          {inst.purpose}
                        </span>
                      </td>
                      <td data-label="Maturity" className="p-3 font-mono">
                        <div>{inst.maturity_date}</div>
                        <div className="text-[11px] text-slate-500">
                          {inst.days_to_maturity} days
                        </div>
                      </td>
                      <td data-label="Status" className="p-3">
                        <span className="inline-block px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-100 text-blue-900">
                          {inst.status_label || inst.status}
                        </span>
                        <div className="text-[10px] font-mono text-slate-500 mt-0.5">
                          Trust: {inst.trust_level} • Flags: {inst.open_flags}
                        </div>
                      </td>
                      <td data-label="Next Step" className="p-3 text-slate-600 max-w-xs">
                        <span className="font-semibold text-slate-800">
                          [{inst.pending_action?.owner}]
                        </span>{' '}
                        {inst.pending_action?.text}
                      </td>
                      <td data-label="Actions" className="p-3 text-right space-x-1.5 whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => onInspectInstrument(inst.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[#0F2547] text-white font-semibold hover:bg-blue-800 cursor-pointer"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Split-Screen</span>
                        </button>
                        {['ACTION_REQUIRED', 'MATURED', 'OVERDUE'].includes(inst.status) && (
                          <button
                            type="button"
                            onClick={() => {
                              setRenewingFrom(inst);
                              setFdrNumber(`${inst.fdr_number}R`);
                              setPrincipalAmount(String(inst.amount || 1500000));
                              setSubTab('wizard');
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[#EA580C] text-white font-semibold cursor-pointer"
                          >
                            <span>Renew</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: NEW FDR / RENEWAL WIZARD */}
      {subTab === 'wizard' && (
        <div className="space-y-6">
          <div className="bg-gradient-to-r from-[#0F2547] to-[#1E3A8A] text-white rounded-2xl p-5 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-300" />
                <h2 className="text-base font-display font-bold">
                  1-Click Synthetic Demo PDF Loader + Live OCR Auto-Fill (`POST /api/v1/ocr/extract`)
                </h2>
              </div>
              {renewingFrom && (
                <span className="px-3 py-1 rounded-full bg-amber-400 text-slate-950 font-mono text-xs font-extrabold">
                  Renewing Overdue FDR #{renewingFrom.fdr_number}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-200">
              Load any of the 3 backend-generated synthetic PDFs with 1 click (or upload your own PDF/PNG below) to test clean OCR auto-fill, Words-vs-Figures forgery detection (Rule R15), or Cross-Institution Duplicate detection (Rule R09):
            </p>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <button
                type="button"
                onClick={() => handleLoadSampleScenario('clean')}
                className="p-3.5 rounded-xl bg-white/10 hover:bg-white/20 border border-white/20 text-left space-y-1 transition cursor-pointer"
              >
                <div className="font-mono text-xs font-bold text-emerald-300">
                  1. Clean Valid Receipt
                </div>
                <p className="text-[11px] text-slate-200">
                  Matches SBI CBS record (₹25,00,000, SBIN0004321). OCR auto-fill + Bank API → 100% Bank-verified!
                </p>
              </button>

              <button
                type="button"
                onClick={() => handleLoadSampleScenario('tampered_words')}
                className="p-3.5 rounded-xl bg-white/10 hover:bg-white/20 border border-amber-300/40 text-left space-y-1 transition cursor-pointer"
              >
                <div className="font-mono text-xs font-bold text-amber-300">
                  2. Tampered Words (R15)
                </div>
                <p className="text-[11px] text-slate-200">
                  Figures say ₹25,00,000 while words on PDF read &ldquo;Two Lakh Fifty Thousand&rdquo; → triggers R15!
                </p>
              </button>

              <button
                type="button"
                onClick={() => handleLoadSampleScenario('duplicate')}
                className="p-3.5 rounded-xl bg-white/10 hover:bg-white/20 border border-rose-300/40 text-left space-y-1 transition cursor-pointer"
              >
                <div className="font-mono text-xs font-bold text-rose-300">
                  3. Cross-Inst. Dup (R09)
                </div>
                <p className="text-[11px] text-slate-200">
                  Reuses an FDR number already registered under another college — caught on blur &amp; upload!
                </p>
              </button>

              <button
                type="button"
                onClick={() => setShowDigiLockerModal(true)}
                className="p-3.5 rounded-xl bg-blue-500/25 hover:bg-blue-500/35 border border-cyan-400/60 text-left space-y-1 transition cursor-pointer"
              >
                <div className="font-mono text-xs font-bold text-cyan-300 flex items-center justify-between">
                  <span>4. DigiLocker Import</span>
                  <span className="px-1.5 py-0.5 rounded bg-cyan-400/30 text-cyan-100 text-[9px] font-bold">
                    India Stack
                  </span>
                </div>
                <p className="text-[11px] text-slate-200">
                  Pull digitally-signed FDR receipt and lien letter directly from DigiLocker repository!
                </p>
              </button>
            </div>
          </div>

          <form
            onSubmit={handleCreateDraftAndUploadDocs}
            className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs space-y-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
              <div>
                <h3 className="text-base font-display font-bold text-slate-900">
                  {renewingFrom
                    ? `Step 1: Enter Renewal FDR Particulars (Linked to Old FDR #${renewingFrom.fdr_number})`
                    : 'Step 1: Security Deposit FDR Particulars & Receipt Upload'}
                </h3>
                <p className="text-xs text-slate-500">
                  Format hints are placed above each input so browser autocomplete popovers never obscure requirements.
                </p>
              </div>
              {busyAction && (
                <span className="text-xs font-mono font-bold text-blue-700 animate-pulse">
                  ⏳ {busyAction}
                </span>
              )}
            </div>

            {dupCheckResult?.duplicate && (
              <div
                role="alert"
                className="p-3.5 rounded-xl bg-red-50 border border-red-300 text-red-900 text-xs font-semibold"
              >
                🚨 <strong>Duplicate FDR Detected (Rule R09):</strong> {dupCheckResult.message}{' '}
                {dupCheckResult.other_institution
                  ? '(Registered under another AICTE institution!)'
                  : ''}
              </div>
            )}

            {digiLockerVerified && (
              <div className="p-3.5 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 text-blue-950 text-xs flex flex-wrap items-center justify-between gap-2 shadow-2xs">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-blue-700 text-white flex items-center justify-center font-bold text-xs shadow-2xs">
                    DL
                  </div>
                  <div>
                    <div className="font-bold flex items-center gap-1.5 text-blue-900">
                      <ShieldCheck className="w-4 h-4 text-blue-700" />
                      Digital Documents Imported via DigiLocker (India Stack)
                    </div>
                    <div className="text-[11px] text-slate-600 font-mono">
                      Certificate ID: {digiLockerDocId || 'DL-SBI-FDR-2026-991100'} • Issuer: State Bank of India • URI: in.gov.digilocker.sbi/fdr
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-mono text-[10px] font-bold">
                    ✓ PKI Verified
                  </span>
                  <button
                    type="button"
                    onClick={() => setDigiLockerVerified(false)}
                    className="text-xs text-slate-500 hover:text-slate-800 underline cursor-pointer"
                  >
                    Clear
                  </button>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="field">
                <label htmlFor="fdr-number-input" className="block text-xs font-bold text-slate-800">
                  FDR Receipt Number *
                </label>
                <span id="fdr-number-hint" className="hint">
                  Format: Alphanumeric receipt number (min 6 chars)
                </span>
                <input
                  id="fdr-number-input"
                  type="text"
                  required
                  minLength={6}
                  value={fdrNumber}
                  onChange={(e) => setFdrNumber(e.target.value)}
                  onBlur={handleCheckDuplicateBlur}
                  aria-describedby="fdr-number-hint"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono"
                />
                <div className="error-msg">Please enter a valid FDR receipt number (min 6 chars).</div>
              </div>

              <div className="field">
                <label htmlFor="bank-select" className="block text-xs font-bold text-slate-800">
                  Issuing Scheduled Bank *
                </label>
                <span id="bank-hint" className="hint">
                  Select an RBI Scheduled Commercial Bank
                </span>
                <select
                  id="bank-select"
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  aria-describedby="bank-hint"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white"
                >
                  {banks.length > 0 ? (
                    banks.map((b) => (
                      <option key={b.id} value={b.name}>
                        {b.name} ({b.short_code})
                      </option>
                    ))
                  ) : (
                    <option value="State Bank of India">State Bank of India (SBI)</option>
                  )}
                </select>
              </div>

              <div className="field">
                <label htmlFor="ifsc-input" className="block text-xs font-bold text-slate-800">
                  Bank Branch IFSC Code *
                </label>
                <span id="ifsc-hint" className="hint">
                  Format: 11-character RBI IFSC (e.g. SBIN0004321)
                </span>
                <input
                  id="ifsc-input"
                  type="text"
                  required
                  pattern="^[A-Z]{4}0[A-Z0-9]{6}$"
                  value={ifscCode}
                  onChange={(e) => setIfscCode(e.target.value.toUpperCase())}
                  aria-describedby="ifsc-hint"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono"
                />
                <div className="error-msg">
                  IFSC must match 4 uppercase letters + 0 + 6 alphanumeric characters.
                </div>
              </div>

              <div className="field">
                <label htmlFor="principal-input" className="block text-xs font-bold text-slate-800">
                  Principal Amount (in Figures ₹) *
                </label>
                <span id="principal-hint" className="hint">
                  Try changing 2500000 to 250000 to test Point-of-Entry OCR Conflict!
                </span>
                <input
                  id="principal-input"
                  type="number"
                  required
                  min={50000}
                  value={principalAmount}
                  onChange={(e) => setPrincipalAmount(e.target.value)}
                  aria-describedby="principal-hint"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono font-bold"
                />
                <div className="error-msg">Principal amount must be at least ₹50,000.</div>
              </div>

              <div className="field">
                <label htmlFor="issue-date-input" className="block text-xs font-bold text-slate-800">
                  FDR Issue Date *
                </label>
                <span className="hint">Format: YYYY-MM-DD</span>
                <input
                  id="issue-date-input"
                  type="date"
                  required
                  value={issueDate}
                  onChange={(e) => setIssueDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono"
                />
              </div>

              <div className="field">
                <label htmlFor="maturity-date-input" className="block text-xs font-bold text-slate-800">
                  FDR Maturity Date *
                </label>
                <span className="hint">Standard AICTE lock-in: 8 years</span>
                <input
                  id="maturity-date-input"
                  type="date"
                  required
                  value={maturityDate}
                  onChange={(e) => setMaturityDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono"
                />
              </div>

              <div className="field">
                <label htmlFor="depositor-input" className="block text-xs font-bold text-slate-800">
                  Depositor Institution Name *
                </label>
                <span className="hint">Must match institution name on FDR receipt</span>
                <input
                  id="depositor-input"
                  type="text"
                  required
                  value={depositorName}
                  onChange={(e) => setDepositorName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs"
                />
              </div>

              <div className="field">
                <label htmlFor="purpose-select" className="block text-xs font-bold text-slate-800">
                  Regulatory Purpose *
                </label>
                <span className="hint">Determines statutory minimum deposit (Rule R01)</span>
                <select
                  id="purpose-select"
                  value={purpose}
                  onChange={(e) => setPurpose(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white"
                >
                  <option value="NEW_APPROVAL">NEW_APPROVAL</option>
                  <option value="EXTENSION_OF_APPROVAL">EXTENSION_OF_APPROVAL</option>
                  <option value="INCREASE_IN_INTAKE">INCREASE_IN_INTAKE</option>
                  <option value="NEW_COURSE">NEW_COURSE</option>
                </select>
              </div>

              <div className="field">
                <label htmlFor="file-upload-input" className="block text-xs font-bold text-slate-800">
                  Or Upload Custom FDR PDF / Scan
                </label>
                <span className="hint">Runs live OCR extraction on selection</span>
                <input
                  id="file-upload-input"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleManualFileOcr(f);
                  }}
                  className="w-full text-xs text-slate-600 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-800"
                />
              </div>
            </div>

            <div className="pt-3 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-slate-600">
                Selected Receipt:{' '}
                <code className="font-mono font-bold text-slate-900">
                  {receiptFile?.name || 'fdr_demo_correct.pdf (auto)'}
                </code>{' '}
                + Lien Letter:{' '}
                <code className="font-mono font-bold text-slate-900">
                  {lienFile?.name || 'lien_letter_demo.pdf (auto)'}
                </code>
              </div>
              <button
                type="submit"
                disabled={!!busyAction}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#0F2547] hover:bg-blue-800 text-white text-xs font-bold shadow-xs cursor-pointer"
              >
                <Upload className="w-4 h-4" />
                <span>
                  Step 2: Save Draft, Encrypt PDFs &amp; Run Point-of-Entry Cross-Check
                </span>
              </button>
            </div>
          </form>

          {/* Point-of-Entry Dual-Truth Cross-Check Preview */}
          {createdCase && (
            <div className="bg-white rounded-2xl border-2 border-blue-600 p-6 shadow-md space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <span className="px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-900 font-mono text-xs font-bold">
                    USP-02 • POINT-OF-ENTRY OCR &amp; 20-RULE CROSS-CHECK
                  </span>
                  <h3 className="text-lg font-display font-extrabold text-slate-900 mt-1">
                    Pre-Submission Verification Preview — Instrument #{createdCase.instrument?.id} ({createdCase.instrument?.status_label})
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  {createdCase.instrument?.status === 'DRAFT' && (
                    <button
                      type="button"
                      onClick={handleFinalSubmit}
                      disabled={!!busyAction}
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold shadow-sm cursor-pointer"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Step 3: Confirm &amp; Final Submit to AICTE</span>
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onInspectInstrument(createdCase.instrument.id)}
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-[#0F2547] text-white text-xs font-bold cursor-pointer"
                  >
                    <span>Open Full Split-Screen</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {createdCase.flags?.length > 0 ? (
                <div className="space-y-2">
                  <div className="text-xs font-bold text-red-800 uppercase tracking-wider">
                    🚨 {createdCase.flags.length} Anomaly / Discrepancy Rule(s) Triggered Prior to Submission:
                  </div>
                  {createdCase.flags.map((fl: any) => (
                    <div
                      key={fl.id}
                      className="p-3 rounded-xl bg-red-50 border border-red-300 text-xs text-red-950 flex flex-wrap items-center justify-between gap-2"
                    >
                      <div>
                        <span className="font-mono font-bold px-2 py-0.5 rounded bg-red-700 text-white mr-2">
                          {fl.rule_id} • {fl.severity}
                        </span>
                        <span className="font-bold">{fl.title}:</span>{' '}
                        {fl.message || fl.institution_message || fl.officer_message}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-semibold">
                  ✅ All 20 Statutory &amp; Anomaly Rules Passed! Zero conflicts between declared form values and OCR-extracted PDF text.
                </div>
              )}

              <div className="table-wrapper rounded-xl border border-slate-200">
                <table className="text-xs text-left">
                  <thead className="bg-slate-100 text-slate-700 font-mono text-[11px] uppercase">
                    <tr>
                      <th className="p-2.5">Field</th>
                      <th className="p-2.5">Institution Declared</th>
                      <th className="p-2.5">OCR Read From Receipt</th>
                      <th className="p-2.5">Point-of-Entry Trust Badge</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {(createdCase.fields || []).map((row: any) => (
                      <tr key={row.field}>
                        <th scope="row" className="p-2.5 font-semibold text-slate-800">
                          {row.label}
                        </th>
                        <td className="p-2.5 font-mono">{String(row.declared_value ?? '—')}</td>
                        <td className="p-2.5 font-mono">{String(row.ocr_value ?? '—')}</td>
                        <td className="p-2.5">
                          <span
                            className={`inline-block px-2 py-0.5 rounded font-mono text-[11px] font-bold ${
                              row.trust === 'OCR_CONFLICT' || row.trust === 'MISMATCH'
                                ? 'bg-red-100 text-red-900'
                                : row.trust === 'OCR_CONSISTENT'
                                ? 'bg-blue-100 text-blue-900'
                                : 'bg-slate-100 text-slate-700'
                            }`}
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
          )}
        </div>
      )}

      {/* TAB 3: RELEASE / REFUND REQUEST & COURIER-STYLE 5-STEP TRACKER */}
      {subTab === 'release' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <form
            onSubmit={handleUploadUndertakingAndRequestRefund}
            className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs space-y-4"
          >
            <div>
              <span className="text-xs font-mono font-bold text-[#EA580C] uppercase">
                USP-09 • GUARDED RELEASE ENGINE
              </span>
              <h2 className="text-lg font-display font-bold text-slate-900">
                Submit Security Deposit Release / Refund Request
              </h2>
              <p className="text-xs text-slate-600 mt-1">
                Automatically attaches your signed <code>UNDERTAKING</code> PDF and runs the Pre-Condition Engine (checks active/eligible status, excess-deposit ground, zero open flags, and zero open compliance cases).
              </p>
            </div>

            <div>
              <label htmlFor="refund-fdr-select" className="block text-xs font-bold text-slate-800 mb-1">
                Select FDR Instrument to Release *
              </label>
              <select
                id="refund-fdr-select"
                value={selectedRefundFdrId}
                onChange={(e) => setSelectedRefundFdrId(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs font-mono bg-white"
              >
                {(overview?.instruments || []).map((inst: any) => (
                  <option key={inst.id} value={inst.id}>
                    #{inst.id} • {inst.fdr_number} ({formatINR(inst.amount)}) — {inst.purpose} [{inst.status}]
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="ground-select" className="block text-xs font-bold text-slate-800 mb-1">
                Statutory Release Ground *
              </label>
              <select
                id="ground-select"
                value={releaseGround}
                onChange={(e) => setReleaseGround(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white"
              >
                <option value="EXCESS_DEPOSIT">
                  EXCESS_DEPOSIT (Extra Intake / Excess Deposit Release)
                </option>
                <option value="CLOSURE_COMPLETED">
                  CLOSURE_COMPLETED (Official Institute Closure Completed)
                </option>
                <option value="APPROVAL_WITHDRAWN">
                  APPROVAL_WITHDRAWN (Approval Withdrawn)
                </option>
                <option value="PROGRAMME_DISCONTINUED">
                  PROGRAMME_DISCONTINUED (Programme Discontinued)
                </option>
                <option value="REPLACED_BY_RENEWAL">
                  REPLACED_BY_RENEWAL (Replaced by Active Renewal FDR)
                </option>
              </select>
            </div>

            <div>
              <label htmlFor="remarks-input" className="block text-xs font-bold text-slate-800 mb-1">
                Institution Justification / Remarks
              </label>
              <textarea
                id="remarks-input"
                rows={2}
                value={releaseRemarks}
                onChange={(e) => setReleaseRemarks(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs"
              />
            </div>

            {/* India Stack: Aadhaar eSign Section for Statutory Undertaking */}
            <div className="p-4 rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50/70 to-indigo-50/40 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Fingerprint className="w-4 h-4 text-blue-700" />
                  <span className="text-xs font-bold text-slate-900">
                    India Stack: Statutory Undertaking eSign (Aadhaar OTP)
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-100 text-blue-800">
                  IT Act Sec 3A
                </span>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                As per AICTE APH regulations, the institution head must execute a verified statutory undertaking certifying zero pending fee litigation or student dues prior to FDR lien discharge.
              </p>

              {aadhaarSigned ? (
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-300 text-emerald-950 space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold flex items-center gap-1.5 text-emerald-800">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" />
                      Legally eSigned via Aadhaar OTP (Simulated India Stack)
                    </span>
                    <button
                      type="button"
                      onClick={() => setAadhaarSigned(false)}
                      className="text-[11px] text-slate-500 hover:text-slate-800 underline cursor-pointer"
                    >
                      Reset eSign
                    </button>
                  </div>
                  <div className="text-[11px] text-emerald-900 font-mono">
                    Signatory: {overview?.institution?.name || 'Principal / Authorized Head'} (Aadhaar: XXXX-XXXX-8921)
                  </div>
                  <div className="text-[10px] text-emerald-700 font-mono truncate">
                    Digital Digest: {aadhaarSignHash || 'SHA256: 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069'}
                  </div>
                  <div className="text-[10px] text-slate-500">
                    eSign Gateway: C-DAC / NSDL e-Gov eSign Provider • Certified Legal Evidence Stamp
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <span className="text-xs text-amber-800 font-medium flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    Undertaking requires digital authentication
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setAadhaarOtp('');
                      setAadhaarOtpSent(false);
                      setAadhaarError(null);
                      setAadhaarConsent(false);
                      setShowAadhaarModal(true);
                    }}
                    className="px-3 py-1.5 rounded-lg bg-[#0F2547] hover:bg-blue-900 text-white text-xs font-bold flex items-center gap-1.5 shadow-2xs transition cursor-pointer"
                  >
                    <Fingerprint className="w-3.5 h-3.5 text-amber-300" />
                    eSign via Aadhaar OTP
                  </button>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={!!busyAction || !selectedRefundFdrId}
              className="w-full py-2.5 px-4 rounded-xl bg-[#0F2547] hover:bg-blue-800 text-white text-xs font-bold cursor-pointer"
            >
              {busyAction ||
                (aadhaarSigned
                  ? 'Submit Release Request with eSigned Undertaking'
                  : 'Submit Release Request & Upload Undertaking PDF')}
            </button>

            {overview?.refunds?.length > 0 && (
              <div className="pt-4 border-t border-slate-200 space-y-2">
                <div className="text-xs font-bold text-slate-700">
                  Your Submitted Release Requests ({overview.refunds.length}):
                </div>
                {overview.refunds.map((r: any) => (
                  <div
                    key={r.id}
                    className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs"
                  >
                    <div>
                      <span className="font-mono font-bold text-slate-900">
                        {r.ref_number || `Request #${r.id}`} ({r.fdr_number})
                      </span>
                      <span className="ml-2 px-2 py-0.5 rounded bg-blue-100 text-blue-900 font-mono text-[10px] font-bold">
                        {r.status}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleInspectRefundTracker(r.id)}
                      className="text-blue-700 font-semibold hover:underline cursor-pointer"
                    >
                      View 5-Step Tracker →
                    </button>
                  </div>
                ))}
              </div>
            )}
          </form>

          {/* Right Column: Courier-Style 5-Step Release Tracker */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs space-y-5">
            <div>
              <span className="text-xs font-mono font-bold text-emerald-700 uppercase">
                LIVE COURIER-STYLE TRACKER
              </span>
              <h2 className="text-lg font-display font-bold text-slate-900">
                5-Step Guarded Release &amp; Pre-Condition Verification
              </h2>
            </div>

            {!refundDetail ? (
              <p className="text-xs text-slate-500 py-8 text-center">
                Submit a release request on the left or click &ldquo;View 5-Step Tracker&rdquo; on an existing request to inspect live pre-condition checks and courier steps.
              </p>
            ) : (
              <div className="space-y-5">
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-mono text-xs font-bold text-slate-900">
                      {refundDetail.ref_number || `Refund #${refundDetail.id}`} • {refundDetail.instrument?.fdr_number}
                    </div>
                    <div className="text-xs text-slate-600">
                      Amount: <strong>{formatINR(refundDetail.instrument?.amount)}</strong> • Ground:{' '}
                      <code>{refundDetail.ground}</code>
                    </div>
                  </div>
                  {refundDetail.discharge_document_id && (
                    <button
                      type="button"
                      onClick={() =>
                        handleDownloadDischargePdf(refundDetail.discharge_document_id)
                      }
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-700 text-white text-xs font-bold cursor-pointer"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download Discharge Letter PDF</span>
                    </button>
                  )}
                </div>

                {/* 5-Step Courier Progress Bar */}
                <div className="space-y-2.5">
                  <div className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Courier-Style 5-Step Custody Progression:
                  </div>
                  {(refundDetail.tracker?.steps || []).map((step: any, i: number) => (
                    <div
                      key={step.code}
                      className={`p-3 rounded-xl border flex items-center justify-between text-xs ${
                        step.state === 'done'
                          ? 'bg-emerald-50/70 border-emerald-300 text-emerald-950'
                          : step.state === 'current'
                          ? 'bg-blue-50 border-blue-400 text-blue-950 font-bold'
                          : 'bg-slate-50 border-slate-200 text-slate-500'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="w-6 h-6 rounded-full bg-white border border-current flex items-center justify-center font-mono text-[11px] font-bold">
                          {i + 1}
                        </span>
                        <span>{step.label}</span>
                      </div>
                      <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded bg-white/80">
                        {step.state}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Pre-condition Engine Checklist */}
                <div className="space-y-2">
                  <div className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Automated Pre-Condition Engine Checks:
                  </div>
                  {(refundDetail.precondition_results || refundDetail.tracker?.preconditions || []).map((chk: any) => (
                    <div
                      key={chk.code}
                      className={`p-2.5 rounded-xl border text-xs flex items-start justify-between gap-2 ${
                        chk.passed
                          ? 'bg-emerald-50/40 border-emerald-200 text-emerald-950'
                          : 'bg-red-50 border-red-300 text-red-950'
                      }`}
                    >
                      <div>
                        <span className="font-bold">{chk.passed ? '✅' : '❌'} {chk.label}:</span>{' '}
                        <span>{chk.detail}</span>
                      </div>
                      <span className="font-mono text-[10px] font-bold">{chk.code}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {/* DIGILOCKER IMPORT MODAL (INDIA STACK) */}
      {showDigiLockerModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-2xl w-full overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
            {/* Header */}
            <div className="bg-[#0b3c60] text-white p-5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-white text-[#0b3c60] font-black text-sm flex items-center justify-center shadow-sm">
                  DL
                </div>
                <div>
                  <div className="text-base font-display font-extrabold flex items-center gap-2">
                    DigiLocker • National Digital Locker System
                  </div>
                  <div className="text-xs text-blue-200">
                    Towards Paperless Governance • Ministry of Electronics &amp; IT (MeitY)
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowDigiLockerModal(false)}
                className="p-1 rounded-lg hover:bg-white/10 text-white/80 hover:text-white transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Profile Bar */}
            <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex flex-wrap items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-700">Authenticated Signatory:</span>
                <span className="font-bold text-slate-900">{overview?.institution?.name || 'Dr. Rajesh Sharma (Principal)'}</span>
              </div>
              <div className="text-slate-500 font-mono">
                Aadhaar Linked: <strong>XXXXXXXX8921</strong> (UIDAI Verified)
              </div>
            </div>

            {/* Body: Available Verified Banking Documents */}
            <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
              <div>
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Issued Documents in DigiLocker Vault (Bank Repository)
                </span>
                <p className="text-xs text-slate-500">
                  The following tamper-evident instruments were issued by State Bank of India directly into your institutional DigiLocker account:
                </p>
              </div>

              {/* Doc 1 */}
              <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/40 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-0.5">
                    <span className="inline-block px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-mono text-[10px] font-bold">
                      FDR_RECEIPT • PKI-SIGNED
                    </span>
                    <h4 className="font-display font-bold text-sm text-slate-900">
                      State Bank of India — Term Deposit Receipt (FDR #SBI00991100)
                    </h4>
                    <p className="text-xs text-slate-600 font-mono">
                      Doc URI: in.gov.digilocker.sbi/fdr/991100 • Issued: 15 Jan 2026
                    </p>
                  </div>
                  <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold">
                    ₹25,00,000
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs pt-2 border-t border-blue-200/60 text-slate-600">
                  <div>Branch: <strong className="text-slate-800">Pune Main (SBIN0004321)</strong></div>
                  <div>Tenure: <strong className="text-slate-800">8 Years (2026-2034)</strong></div>
                  <div>Lien: <strong className="text-emerald-700">Joint to AICTE</strong></div>
                </div>
              </div>

              {/* Doc 2 */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-0.5">
                    <span className="inline-block px-2 py-0.5 rounded bg-slate-200 text-slate-800 font-mono text-[10px] font-bold">
                      LIEN_LETTER • DIGITAL_SEAL
                    </span>
                    <h4 className="font-display font-bold text-sm text-slate-900">
                      SBI Official Lien Marking Confirmation &amp; Non-Encashment Undertaking
                    </h4>
                    <p className="text-xs text-slate-600 font-mono">
                      Doc URI: in.gov.digilocker.sbi/lien/44321 • Signatory: Chief Manager, SBI
                    </p>
                  </div>
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                </div>
                <p className="text-xs text-slate-600">
                  Irrevocable lien marked in favour of Member Secretary, AICTE. No premature withdrawal without prior written NOC from AICTE.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  <strong>India Stack Benefit:</strong> Pulling from DigiLocker eliminates paper scanning, delivers 100% digital trust, and bypasses physical courier overhead.
                </span>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowDigiLockerModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-200 transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={digiLockerLoading}
                onClick={handleDigiLockerImport}
                className="px-5 py-2.5 rounded-xl bg-[#0b3c60] hover:bg-[#082b46] text-white text-xs font-bold flex items-center gap-2 shadow-sm transition cursor-pointer disabled:opacity-60"
              >
                {digiLockerLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Verifying Digital Signatures...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    <span>Fetch &amp; Auto-Populate from DigiLocker</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AADHAAR ESIGN MODAL (INDIA STACK) */}
      {showAadhaarModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-lg w-full overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
            {/* Tricolor stripe */}
            <div className="h-1.5 w-full bg-gradient-to-r from-orange-500 via-white to-green-600" />

            {/* Header */}
            <div className="p-5 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-orange-50 border border-orange-200 text-orange-700 flex items-center justify-center">
                  <Fingerprint className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-base text-slate-900">
                    Aadhaar eSign Gateway (India Stack)
                  </h3>
                  <p className="text-xs text-slate-500">
                    C-DAC / NSDL e-Gov Electronic Signature Service
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowAadhaarModal(false)}
                className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4">
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                <div className="text-slate-500 font-mono text-[11px]">Authorized Signatory</div>
                <div className="font-bold text-slate-900">
                  {overview?.institution?.name ? `Authorized Head (${overview.institution.name})` : 'Dr. Rajesh Sharma, Principal'}
                </div>
                <div className="text-slate-600 font-mono">
                  Aadhaar VID / UID: <strong>XXXXXXXX8921</strong>
                </div>
              </div>

              <div className="space-y-1 text-xs text-slate-600 bg-blue-50/60 p-3 rounded-xl border border-blue-100">
                <div className="font-bold text-blue-900">Statutory Declaration to be Signed:</div>
                <p className="italic leading-relaxed text-[11px] text-slate-700">
                  &ldquo;I hereby solemnly affirm under oath that all educational program regulations are satisfied, zero fee claims or student litigations are pending against FDR #{overview?.instruments?.find((i: any) => i.id === selectedRefundFdrId)?.fdr_number || 'selected'}, and this discharge is executed with full institutional liability.&rdquo;
                </p>
              </div>

              {!aadhaarOtpSent ? (
                <div className="space-y-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setAadhaarOtpSent(true)}
                    className="w-full py-2.5 px-4 rounded-xl bg-orange-600 hover:bg-orange-700 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-2xs transition cursor-pointer"
                  >
                    <span>Send One-Time Password (OTP) to Aadhaar Mobile</span>
                  </button>
                  <p className="text-[11px] text-slate-500 text-center">
                    OTP will be dispatched to UIDAI registered mobile number ending in <strong>****4321</strong>.
                  </p>
                </div>
              ) : (
                <div className="space-y-4 pt-2">
                  <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center justify-between">
                    <span>✅ OTP dispatched to registered mobile.</span>
                    <span className="font-mono font-bold text-emerald-800">Demo OTP: 123456</span>
                  </div>

                  <div>
                    <label htmlFor="aadhaar-otp-input" className="block text-xs font-bold text-slate-800 mb-1">
                      Enter 6-Digit Aadhaar OTP *
                    </label>
                    <input
                      id="aadhaar-otp-input"
                      type="text"
                      maxLength={6}
                      placeholder="123456"
                      value={aadhaarOtp}
                      onChange={(e) => setAadhaarOtp(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 font-mono text-center tracking-widest text-lg font-bold text-slate-900 focus:outline-none focus:border-orange-500"
                    />
                  </div>

                  <label className="flex items-start gap-2 text-xs text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={aadhaarConsent}
                      onChange={(e) => setAadhaarConsent(e.target.checked)}
                      className="mt-0.5 rounded border-slate-300 text-orange-600 focus:ring-orange-500"
                    />
                    <span>
                      I hereby give voluntary consent to authenticate using my Aadhaar credentials to generate an electronic signature under Section 3A of the Information Technology Act, 2000.
                    </span>
                  </label>

                  {aadhaarError && (
                    <div className="text-xs text-red-600 font-semibold">
                      {aadhaarError}
                    </div>
                  )}

                  <div className="flex items-center gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setAadhaarOtpSent(false)}
                      className="px-3 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition cursor-pointer"
                    >
                      Resend OTP
                    </button>
                    <button
                      type="button"
                      onClick={handleVerifyAadhaarOtp}
                      className="flex-1 py-2.5 px-4 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition cursor-pointer"
                    >
                      <ShieldCheck className="w-4 h-4" />
                      <span>Verify &amp; Apply Legal eSign</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* AICTE STATUTORY COMPLIANCE CERTIFICATE MODAL */}
      {showCertificateModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-3xl w-full my-8 overflow-hidden flex flex-col">
            {/* Modal Controls Bar (hidden during print) */}
            <div className="bg-slate-900 text-white px-6 py-3.5 flex items-center justify-between print:hidden">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-amber-400" />
                <span className="font-display font-bold text-sm">
                  Official AICTE Security Deposit Compliance Certificate
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow-sm transition cursor-pointer"
                >
                  <Printer className="w-4 h-4" />
                  <span>Print / Save as PDF</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowCertificateModal(false)}
                  className="p-1 rounded-lg hover:bg-white/10 text-white/80 hover:text-white transition cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Printable Certificate Parchment */}
            <div className="p-8 sm:p-12 bg-amber-50/15 border-8 border-double border-[#0F2547] text-slate-900 space-y-6 relative print:p-0 print:border-4">
              {/* Watermark effect */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03] select-none">
                <Building2 className="w-96 h-96 text-[#0F2547]" />
              </div>

              {/* Certificate Header */}
              <div className="text-center space-y-1.5 border-b-2 border-[#0F2547]/30 pb-5">
                <div className="font-serif text-xs font-bold text-slate-600 tracking-widest uppercase">
                  Government of India • Ministry of Education
                </div>
                <h2 className="text-xl sm:text-2xl font-serif font-black tracking-wide text-[#0F2547] uppercase">
                  अखिल भारतीय तकनीकी शिक्षा परिषद
                </h2>
                <h3 className="text-base sm:text-lg font-serif font-bold text-slate-800 tracking-wider">
                  ALL INDIA COUNCIL FOR TECHNICAL EDUCATION
                </h3>
                <p className="text-xs text-slate-600 font-serif">
                  (A Statutory Body of the Government of India) • Nelson Mandela Marg, Vasant Kunj, New Delhi - 110070
                </p>
                <div className="flex flex-wrap items-center justify-between text-xs font-mono text-slate-600 pt-3">
                  <span>Ref: AICTE/APH-2026/SEC-DEP/{overview?.institution?.aicte_id || 'AICTE-1001'}</span>
                  <span>Issued Date: 25 October 2026</span>
                </div>
              </div>

              {/* Title */}
              <div className="text-center space-y-1">
                <span className="inline-block px-3 py-1 rounded bg-[#0F2547] text-amber-300 font-serif text-xs font-bold tracking-widest uppercase shadow-2xs">
                  Statutory Certificate
                </span>
                <h4 className="text-lg sm:text-xl font-serif font-bold text-[#0F2547] tracking-wide uppercase pt-1">
                  SECURITY DEPOSIT COMPLIANCE CERTIFICATE
                </h4>
                <p className="text-xs italic text-slate-600">
                  Issued under Regulation 4(3) of AICTE (Grant of Approvals for Technical Institutions) Regulations
                </p>
              </div>

              {/* Body */}
              <p className="text-xs sm:text-sm text-slate-800 leading-relaxed font-serif text-justify">
                This is to officially certify that the technical institution named{' '}
                <strong className="text-[#0F2547] font-sans font-bold">
                  {overview?.institution?.name || 'Aaranya Institute of Technology'}
                </strong>
                , bearing Permanent Institute ID{' '}
                <strong className="font-mono text-slate-900">{overview?.institution?.aicte_id || 'AICTE-INST'}</strong>,
                situated in the{' '}
                <strong className="text-slate-900">{overview?.institution?.region || 'Western'} Region</strong>, has
                duly executed, pledged, and maintained the requisite statutory Fixed Deposit Receipts (FDR) / Joint
                Encumbrance in favour of{' '}
                <strong className="text-[#0F2547]">Member Secretary, AICTE</strong>. The encumbrance details have been
                digitally verified with the designated scheduled commercial banks in accordance with the norms set
                forth in the AICTE Approval Process Handbook (APH).
              </p>

              {/* Statutory Metric Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center bg-white/80 p-4 rounded-xl border border-slate-300 shadow-2xs">
                <div className="p-2 border-r border-slate-200">
                  <div className="text-[10px] font-mono text-slate-500 uppercase">Certified Held Security</div>
                  <div className="text-base font-bold text-[#0F2547]">
                    {formatINR(overview?.totals?.held_amount || 2500000)}
                  </div>
                </div>
                <div className="p-2 sm:border-r border-slate-200">
                  <div className="text-[10px] font-mono text-slate-500 uppercase">Active FDR Instruments</div>
                  <div className="text-base font-bold text-slate-900">
                    {overview?.totals?.held_count || 1} Instrument(s)
                  </div>
                </div>
                <div className="p-2 border-r border-slate-200">
                  <div className="text-[10px] font-mono text-slate-500 uppercase">Lien Status</div>
                  <div className="text-xs font-bold text-emerald-700 mt-1">
                    Joint Lien Pledged
                  </div>
                </div>
                <div className="p-2">
                  <div className="text-[10px] font-mono text-slate-500 uppercase">Compliance Standing</div>
                  <div className={`text-xs font-bold mt-1 ${overview?.locked ? 'text-red-700' : 'text-emerald-700'}`}>
                    {overview?.locked ? 'Overdue Renewal' : 'Good Standing'}
                  </div>
                </div>
              </div>

              {/* Active Instruments Table */}
              {overview?.instruments?.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-[11px] font-mono font-bold text-slate-700 uppercase tracking-wider">
                    Schedule of Covered Fixed Deposit Instruments:
                  </div>
                  <div className="overflow-x-auto border border-slate-200 rounded-lg">
                    <table className="w-full text-[11px] text-left">
                      <thead className="bg-[#0F2547] text-white font-mono text-[10px]">
                        <tr>
                          <th className="p-2">FDR Number</th>
                          <th className="p-2">Bank &amp; Branch</th>
                          <th className="p-2">Amount</th>
                          <th className="p-2">Maturity Date</th>
                          <th className="p-2">Lien Holder</th>
                          <th className="p-2">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 bg-white">
                        {overview.instruments.slice(0, 4).map((inst: any) => (
                          <tr key={inst.id}>
                            <td className="p-2 font-mono font-bold text-slate-900">{inst.fdr_number}</td>
                            <td className="p-2">{inst.bank_name}</td>
                            <td className="p-2 font-bold">{formatINR(inst.amount)}</td>
                            <td className="p-2 font-mono">{inst.maturity_date}</td>
                            <td className="p-2 text-slate-600">{inst.lien_in_favour_of || 'Member Secretary, AICTE'}</td>
                            <td className="p-2">
                              <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-800 font-mono text-[10px] font-bold">
                                {inst.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Certificate Footer & Signatures */}
              <div className="pt-6 border-t-2 border-[#0F2547]/30 flex flex-wrap items-end justify-between gap-6">
                <div className="space-y-1">
                  <div className="w-20 h-20 bg-slate-100 border border-slate-300 rounded p-1 flex items-center justify-center">
                    {/* Simulated QR Code SVG */}
                    <svg viewBox="0 0 24 24" className="w-16 h-16 text-[#0F2547]" fill="currentColor">
                      <path d="M2 2h8v8H2V2zm2 2v4h4V4H4zm10-2h8v8h-8V2zm2 2v4h4V4h-4zM2 14h8v8H2v-8zm2 2v4h4v-4H4zm14 0h4v4h-4v-4zm-4 4h4v4h-4v-4zm0-4h4v-4h-4v4zm4-6h-4v2h4V10z" />
                    </svg>
                  </div>
                  <div className="text-[9px] font-mono text-slate-500 max-w-[200px]">
                    Central Registry Verification Digest:
                    <span className="block truncate text-slate-700">SHA256: e4b7c19a8206d4e823f990a82b4512e039478f79</span>
                  </div>
                </div>

                <div className="text-center space-y-1">
                  <div className="w-24 h-24 rounded-full border-2 border-dashed border-[#0F2547] mx-auto flex items-center justify-center text-[10px] font-bold text-[#0F2547] uppercase leading-tight p-2 bg-amber-50">
                    AICTE Central Regulatory Bureau Seal
                  </div>
                  <div className="text-[10px] font-mono text-slate-500">Verified &amp; Sealed</div>
                </div>

                <div className="text-right space-y-1">
                  <div className="font-serif italic text-sm text-[#0F2547] font-bold pb-2">
                    Prof. Rajive Kumar
                  </div>
                  <div className="text-xs font-bold text-slate-900">Member Secretary</div>
                  <div className="text-[11px] text-slate-600">
                    All India Council for Technical Education
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
