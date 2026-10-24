"""Pydantic request/response schemas (they also drive the Swagger docs at /docs)."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.enums import (
    AlertStatus,
    AlertType,
    DiscrepancyReason,
    DocType,
    FlagStatus,
    InstrumentStatus,
    OcrStatus,
    Purpose,
    RefundStatus,
    ReleaseGround,
    Role,
    Severity,
    TrustLevel,
    VerificationStatus,
)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------- auth ------------------------------------- #
class LoginIn(BaseModel):
    email: EmailStr
    password: str
    otp: str | None = Field(None, description="Required only if MFA is enabled for the account")


class InstitutionOut(ORM):
    id: int
    aicte_id: str
    name: str
    institution_type: str | None = None
    state: str
    district: str | None = None
    region: str
    email: str | None = None
    phone: str | None = None


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: Role
    phone: str | None = None
    institution_id: int | None = None
    region: str | None = None
    bank_id: int | None = None
    mfa_enabled: bool
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MfaVerifyIn(BaseModel):
    otp: str


# ----------------------------- instruments -------------------------------- #
class InstrumentIn(BaseModel):
    fdr_number: str | None = Field(None, max_length=40)
    bank_name: str | None = None
    branch: str | None = None
    ifsc: str | None = Field(None, max_length=11)
    depositor_name: str | None = None
    amount: Decimal | None = Field(None, ge=0)
    issue_date: date | None = None
    maturity_date: date | None = None
    lien_marked: bool | None = None
    lien_in_favour_of: str | None = None
    purpose: Purpose | None = None

    @field_validator("ifsc", "fdr_number")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v


class DuplicateCheckIn(BaseModel):
    fdr_number: str
    ifsc: str | None = None
    bank_name: str | None = None


class InstrumentOut(ORM):
    id: int
    ack_number: str | None
    institution_id: int
    fdr_number: str | None
    bank_name: str | None
    branch: str | None
    ifsc: str | None
    depositor_name: str | None
    amount: Decimal | None
    issue_date: date | None
    maturity_date: date | None
    lien_marked: bool
    lien_in_favour_of: str | None
    purpose: Purpose
    status: InstrumentStatus
    verification_status: VerificationStatus
    trust_level: TrustLevel
    risk_score: int
    replaces_instrument_id: int | None
    submitted_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InstrumentListItem(InstrumentOut):
    institution_name: str | None = None
    institution_aicte_id: str | None = None
    region: str | None = None
    days_to_maturity: int | None = None
    open_flags: int = 0


class Page(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class ActionNoteIn(BaseModel):
    note: str | None = None


class RejectIn(BaseModel):
    note: str = Field(..., min_length=3)


class DiscrepancyIn(BaseModel):
    reason_code: DiscrepancyReason
    note: str = Field(..., min_length=3)
    flag_ids: list[int] = Field(default_factory=list, description="Flags to confirm as part of this discrepancy")


class ObservationIn(BaseModel):
    note: str = Field(..., min_length=2)
    reason_code: DiscrepancyReason | None = None
    visible_to_institution: bool = True


class FlagDecisionIn(BaseModel):
    decision: FlagStatus = Field(..., description="CONFIRMED or DISMISSED")
    note: str = Field(..., min_length=3, description="Mandatory reason - the human makes the final call")


class ConfirmedValuesIn(BaseModel):
    fdr_number: str | None = None
    ifsc: str | None = None
    bank_name: str | None = None
    depositor_name: str | None = None
    amount: Decimal | None = None
    issue_date: date | None = None
    maturity_date: date | None = None
    lien_marked: bool | None = None


class ManualVerifyIn(ConfirmedValuesIn):
    document_id: int | None = Field(None, description="Uploaded BANK_CONFIRMATION document")
    remarks: str | None = None


class BankResponseIn(ConfirmedValuesIn):
    found: bool = True
    bank_status: str = Field("ACTIVE", description="ACTIVE | CLOSED | ENCASHED")
    remarks: str | None = None


class DocumentOut(ORM):
    id: int
    instrument_id: int | None
    refund_request_id: int | None
    doc_type: DocType
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    encrypted: bool
    is_superseded: bool
    uploaded_at: datetime
    ocr_status: OcrStatus
    ocr_engine: str | None
    ocr_confidence: float | None


class FlagOut(ORM):
    id: int
    instrument_id: int
    rule_id: str
    code: str
    title: str
    severity: Severity
    status: FlagStatus
    officer_message: str
    institution_message: str
    evidence: dict | None
    is_auto: bool
    resolution_note: str | None
    resolved_at: datetime | None
    created_at: datetime


class EventOut(ORM):
    id: int
    action: str
    from_status: str | None
    to_status: str | None
    actor_id: int | None
    actor_role: str
    note: str | None
    data: dict | None
    created_at: datetime


# ------------------------------- refunds ---------------------------------- #
class RefundIn(BaseModel):
    instrument_id: int
    ground: ReleaseGround
    reason_text: str | None = None


class RefundOut(ORM):
    id: int
    ref_number: str | None
    instrument_id: int
    institution_id: int
    ground: ReleaseGround
    reason_text: str | None
    status: RefundStatus
    precondition_results: list | None
    recommended_by: int | None
    approved_by: int | None
    discharge_document_id: int | None
    created_at: datetime
    updated_at: datetime


# ------------------------------- alerts ----------------------------------- #
class AlertOut(ORM):
    id: int
    alert_type: AlertType
    title: str
    message: str
    severity: Severity
    level: int
    assigned_role: Role
    region: str | None
    status: AlertStatus
    instrument_id: int | None
    institution_id: int | None
    refund_request_id: int | None
    due_date: date | None
    escalate_at: datetime | None
    history: list | None
    created_at: datetime
    resolved_at: datetime | None
    resolution_note: str | None


class NotificationOut(ORM):
    id: int
    channel: str
    title: str
    body: str
    link: str | None
    category: str | None
    status: str
    read_at: datetime | None
    created_at: datetime


# -------------------------------- admin ----------------------------------- #
class UserCreateIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(..., min_length=8)
    role: Role
    phone: str | None = None
    institution_id: int | None = None
    region: str | None = None
    bank_id: int | None = None


class UserUpdateIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: Role | None = None
    region: str | None = None
    institution_id: int | None = None
    bank_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8)


class InstitutionIn(BaseModel):
    aicte_id: str
    name: str
    institution_type: str | None = None
    state: str
    district: str | None = None
    region: str
    email: str | None = None
    phone: str | None = None


class BankIn(BaseModel):
    name: str
    short_code: str
    ifsc_prefix: str = Field(..., min_length=4, max_length=4)
    nodal_officer_email: str | None = None
    api_enabled: bool = True
    api_available: bool = True


class BankOut(ORM):
    id: int
    name: str
    short_code: str
    ifsc_prefix: str
    nodal_officer_email: str | None
    api_enabled: bool
    api_available: bool


class ConfigUpdateIn(BaseModel):
    value: Any


class HolidayIn(BaseModel):
    day: date
    name: str


class ComplianceCaseIn(BaseModel):
    institution_id: int
    title: str
    description: str | None = None


class AdvanceClockIn(BaseModel):
    days: int = Field(..., ge=-3650, le=3650)
    run_jobs: bool = True


class MockLedgerUpdateIn(BaseModel):
    status: str | None = Field(None, description="ACTIVE | CLOSED | ENCASHED")
    lien_marked: bool | None = None
    amount: Decimal | None = None
    maturity_date: date | None = None
