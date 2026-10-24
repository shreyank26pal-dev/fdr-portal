export type Role =
  | 'INSTITUTION'
  | 'SCRUTINY_OFFICER'
  | 'APPROVING_AUTHORITY'
  | 'REGIONAL_OFFICER'
  | 'BANK'
  | 'ADMIN'
  | 'AUDITOR';

export type InstrumentStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'UNDER_SCRUTINY'
  | 'DISCREPANCY_RAISED'
  | 'VERIFIED'
  | 'ACTIVE'
  | 'RENEWAL_DUE'
  | 'EXPIRED'
  | 'RELEASE_ELIGIBLE'
  | 'RELEASE_REQUESTED'
  | 'RELEASED'
  | 'REJECTED';

export type FieldTrust =
  | 'DECLARED'
  | 'OCR_CONSISTENT'
  | 'OCR_CONFLICT'
  | 'BANK_VERIFIED'
  | 'OFFICER_VERIFIED'
  | 'MISMATCH';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  institution_id: number | null;
  region: string | null;
  bank_id: number | null;
  is_active: boolean;
}

export interface DemoAccountPreset {
  email: string;
  password: string;
  role: Role;
  label: string;
  subtitle: string;
  badgeColor: string;
}

export interface BankMaster {
  id: number;
  name: string;
  short_code: string;
  ifsc_prefix: string;
  nodal_email: string;
  supports_api: boolean;
  is_scheduled: boolean;
}

export interface InstitutionOut {
  id: number;
  aicte_id: string;
  name: string;
  state: string;
  region: string;
  city: string;
  category: string;
  contact_email: string;
  contact_phone: string | null;
  approval_Since_year?: number;
  approval_since_year?: number;
}

export interface FieldComparisonRow {
  field: string;
  label: string;
  declared: string | number | null;
  ocr: string | number | null;
  confirmed: string | number | null;
  confirmed_source: string | null;
  trust: FieldTrust;
  badge: {
    label: string;
    tone: 'neutral' | 'info' | 'warning' | 'success' | 'danger';
  };
  match: boolean | null;
}

export interface DiscrepancyFlagOut {
  id: number;
  rule_id: string;
  code: string;
  severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  field_name: string | null;
  declared_value: string | null;
  detected_value: string | null;
  details: string;
  status: 'OPEN' | 'CONFIRMED' | 'DISMISSED';
  decided_by_id: number | null;
  decision_reason: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface ObservationOut {
  id: number;
  author_id: number;
  author_name: string | null;
  author_role: string | null;
  section: string;
  note: string;
  visible_to_institution: boolean;
  created_at: string;
}

export interface DocumentOut {
  id: number;
  doc_type: 'FDR_RECEIPT' | 'LIEN_LETTER' | 'BANK_CONFIRMATION' | 'UNDERTAKING' | 'RELEASE_ORDER' | 'OTHER';
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  encrypted: boolean;
  ocr_status: string;
  ocr_confidence: number | null;
  ocr_fields: Record<string, any> | null;
  uploaded_at: string;
}

export interface VerificationRequestOut {
  id: number;
  channel: string;
  status: string;
  requested_at: string;
  responded_at: string | null;
  response_payload: Record<string, any> | null;
  mismatch_fields: string[] | null;
  notes: string | null;
  demo_confirmation_url: string | null;
  demo_confirmation_token: string | null;
}

export interface EventOut {
  id: number;
  from_status: string | null;
  to_status: string;
  action: string;
  actor_name: string | null;
  actor_role: string | null;
  note: string | null;
  created_at: string;
}

export interface LineageNode {
  id: number;
  fdr_number: string;
  status: InstrumentStatus;
  amount: number;
  issue_date: string;
  maturity_date: string;
}

export interface PendingAction {
  who: string;
  message: string;
  cta: string | null;
  deadline?: string | null;
}

export interface InstrumentSummary {
  id: number;
  acknowledgement_no: string | null;
  institution_id: number;
  institution_name: string;
  institution_aicte_id: string;
  region: string;
  fdr_number: string;
  bank_id: number;
  bank_name: string;
  branch_name: string;
  ifsc_code: string;
  principal_amount: number;
  maturity_amount: number | null;
  interest_rate: number;
  issue_date: string;
  maturity_date: string;
  tenure_months: number;
  Joint_holder_name?: string;
  joint_holder_name: string;
  purpose: string;
  academic_year: string;
  programme: string;
  auto_renewal: boolean;
  status: InstrumentStatus;
  status_label: string;
  verification_status: string;
  trust_level: string;
  risk_score: number;
  open_flags_count: number;
  days_to_maturity: number;
  pending_action: PendingAction;
  submitted_at: string | null;
  updated_at: string;
}

export interface InstrumentDetail extends InstrumentSummary {
  amount_in_words_declared: string | null;
  lien_marked_declared: boolean;
  lien_reference_declared: string | null;
  discrepancy_reason: string | null;
  discrepancy_remarks: string | null;
  discrepancy_due_date: string | null;
  rejection_reason: string | null;
  renewed_from_id: number | null;
  field_comparison: FieldComparisonRow[];
  documents: DocumentOut[];
  flags: DiscrepancyFlagOut[];
  observations: ObservationOut[];
  verification_requests: VerificationRequestOut[];
  events: EventOut[];
  lineage: LineageNode[];
  allowed_actions: string[];
}

export interface DemoSample {
  filename: string;
  size_bytes: number;
  label: string;
  doc_type: string;
  description: string;
}
