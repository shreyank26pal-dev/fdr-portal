"""SQLAlchemy data model.

Key design rule: an instrument stores what the institution DECLARED on its own
columns, and what was independently CONFIRMED (OCR / bank / officer) per field
in `field_checks`. The two are never merged.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import (
    AlertStatus,
    AlertType,
    BankRecordStatus,
    CaseStatus,
    DeliveryStatus,
    DocType,
    FieldTrust,
    FlagStatus,
    InstrumentStatus,
    NotificationChannel,
    OcrStatus,
    Purpose,
    RefundStatus,
    ReleaseGround,
    Role,
    Severity,
    TrustLevel,
    VerificationChannel,
    VerificationRequestStatus,
    VerificationStatus,
)
from app.services import clock


def E(enum_cls):
    return SAEnum(enum_cls, native_enum=False, length=40, validate_strings=True)


def _now() -> datetime:
    return clock.now()


TS = DateTime(timezone=True)


# --------------------------------------------------------------------------- #
# Masters
# --------------------------------------------------------------------------- #
class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    aicte_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    institution_type: Mapped[str | None] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(60))
    district: Mapped[str | None] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(40), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)

    instruments: Mapped[list[Instrument]] = relationship(back_populates="institution")
    users: Mapped[list[User]] = relationship(back_populates="institution")


class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    short_code: Mapped[str] = mapped_column(String(20), unique=True)
    ifsc_prefix: Mapped[str] = mapped_column(String(4), unique=True, index=True)
    nodal_officer_email: Mapped[str | None] = mapped_column(String(255))
    api_enabled: Mapped[bool] = mapped_column(Boolean, default=True)    # bank offers verification API
    api_available: Mapped[bool] = mapped_column(Boolean, default=True)  # toggle to simulate an outage
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(E(Role), index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), index=True)
    region: Mapped[str | None] = mapped_column(String(40))  # for REGIONAL_OFFICER
    bank_id: Mapped[int | None] = mapped_column(ForeignKey("banks.id"))  # for BANK users
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)

    institution: Mapped[Institution | None] = relationship(back_populates="users")
    bank: Mapped[Bank | None] = relationship()


# --------------------------------------------------------------------------- #
# Instrument (FDR / security deposit)
# --------------------------------------------------------------------------- #
class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ack_number: Mapped[str | None] = mapped_column(String(40), unique=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    bank_id: Mapped[int | None] = mapped_column(ForeignKey("banks.id"), index=True)

    # ---- DECLARED by the institution ----
    fdr_number: Mapped[str | None] = mapped_column(String(40), index=True)
    bank_name: Mapped[str | None] = mapped_column(String(120))
    branch: Mapped[str | None] = mapped_column(String(120))
    ifsc: Mapped[str | None] = mapped_column(String(11), index=True)
    depositor_name: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    issue_date: Mapped[date | None] = mapped_column(Date)
    maturity_date: Mapped[date | None] = mapped_column(Date, index=True)
    lien_marked: Mapped[bool] = mapped_column(Boolean, default=False)
    lien_in_favour_of: Mapped[str | None] = mapped_column(String(255))
    purpose: Mapped[Purpose] = mapped_column(E(Purpose), default=Purpose.EXTENSION_OF_APPROVAL)

    # ---- workflow ----
    status: Mapped[InstrumentStatus] = mapped_column(E(InstrumentStatus), default=InstrumentStatus.DRAFT, index=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        E(VerificationStatus), default=VerificationStatus.NOT_STARTED, index=True
    )
    trust_level: Mapped[TrustLevel] = mapped_column(E(TrustLevel), default=TrustLevel.SELF_DECLARED)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    replaces_instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"), index=True)

    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(TS)
    verified_at: Mapped[datetime | None] = mapped_column(TS)
    approved_at: Mapped[datetime | None] = mapped_column(TS)
    last_bank_check_at: Mapped[datetime | None] = mapped_column(TS)
    closed_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)
    updated_at: Mapped[datetime] = mapped_column(TS, default=_now, onupdate=_now)
    version: Mapped[int] = mapped_column(Integer, default=1)

    institution: Mapped[Institution] = relationship(back_populates="instruments")
    bank: Mapped[Bank | None] = relationship()
    documents: Mapped[list[Document]] = relationship(
        back_populates="instrument", foreign_keys="Document.instrument_id", order_by="Document.id"
    )
    flags: Mapped[list[Flag]] = relationship(back_populates="instrument", order_by="Flag.id")
    events: Mapped[list[FdrEvent]] = relationship(back_populates="instrument", order_by="FdrEvent.id")
    field_checks: Mapped[list[FieldCheck]] = relationship(back_populates="instrument", order_by="FieldCheck.id")
    replaces: Mapped[Instrument | None] = relationship(remote_side="Instrument.id")


class FieldCheck(Base):
    """Per-field 'declared vs confirmed' record. One row per (instrument, field)."""
    __tablename__ = "field_checks"
    __table_args__ = (UniqueConstraint("instrument_id", "field_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(40))
    declared_value: Mapped[str | None] = mapped_column(String(255))
    ocr_value: Mapped[str | None] = mapped_column(String(255))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    confirmed_value: Mapped[str | None] = mapped_column(String(255))
    confirmed_channel: Mapped[VerificationChannel | None] = mapped_column(E(VerificationChannel))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(TS)
    trust: Mapped[FieldTrust] = mapped_column(E(FieldTrust), default=FieldTrust.DECLARED)
    updated_at: Mapped[datetime] = mapped_column(TS, default=_now, onupdate=_now)

    instrument: Mapped[Instrument] = relationship(back_populates="field_checks")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"), index=True)
    refund_request_id: Mapped[int | None] = mapped_column(ForeignKey("refund_requests.id"), index=True)
    doc_type: Mapped[DocType] = mapped_column(E(DocType))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(255))
    encrypted: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superseded: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(TS, default=_now)

    ocr_status: Mapped[OcrStatus] = mapped_column(E(OcrStatus), default=OcrStatus.NOT_RUN)
    ocr_engine: Mapped[str | None] = mapped_column(String(40))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_fields: Mapped[dict | None] = mapped_column(JSON)

    instrument: Mapped[Instrument | None] = relationship(back_populates="documents", foreign_keys=[instrument_id])


class Flag(Base):
    """A discrepancy / anomaly. The system only FLAGS; a human decides."""
    __tablename__ = "flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[Severity] = mapped_column(E(Severity))
    status: Mapped[FlagStatus] = mapped_column(E(FlagStatus), default=FlagStatus.OPEN, index=True)
    officer_message: Mapped[str] = mapped_column(Text)        # technical explanation + evidence
    institution_message: Mapped[str] = mapped_column(Text)    # plain-language "what to fix"
    evidence: Mapped[dict | None] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(255))     # rule + key evidence, to avoid duplicates
    is_auto: Mapped[bool] = mapped_column(Boolean, default=True)
    raised_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(TS)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)

    instrument: Mapped[Instrument] = relationship(back_populates="flags")


class Observation(Base):
    """Officer scrutiny notes."""
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason_code: Mapped[str | None] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text)
    visible_to_institution: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)


class FdrEvent(Base):
    """Lifecycle timeline: every status change / significant action on an instrument."""
    __tablename__ = "fdr_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    action: Mapped[str] = mapped_column(String(60))
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str | None] = mapped_column(String(40))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(40))  # role or SYSTEM
    note: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)

    instrument: Mapped[Instrument] = relationship(back_populates="events")


class AuditLog(Base):
    """Append-only, hash-chained audit log. hash = sha256(canonical(entry) + prev_hash)."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(TS)
    actor_id: Mapped[int | None] = mapped_column(Integer)
    actor_email: Mapped[str | None] = mapped_column(String(255))
    actor_role: Mapped[str] = mapped_column(String(40))
    ip: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(40), index=True)
    institution_id: Mapped[int | None] = mapped_column(Integer, index=True)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
class VerificationRequest(Base):
    """Chain of custody for every bank verification attempt."""
    __tablename__ = "verification_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    bank_id: Mapped[int | None] = mapped_column(ForeignKey("banks.id"), index=True)
    channel: Mapped[VerificationChannel] = mapped_column(E(VerificationChannel))
    status: Mapped[VerificationRequestStatus] = mapped_column(
        E(VerificationRequestStatus), default=VerificationRequestStatus.PENDING, index=True
    )
    result: Mapped[VerificationStatus | None] = mapped_column(E(VerificationStatus))
    source_name: Mapped[str] = mapped_column(String(120))
    endpoint: Mapped[str | None] = mapped_column(String(255))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(TS)
    request_payload: Mapped[dict | None] = mapped_column(JSON)
    response_payload: Mapped[dict | None] = mapped_column(JSON)
    comparison: Mapped[dict | None] = mapped_column(JSON)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    responded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(TS, default=_now)
    responded_at: Mapped[datetime | None] = mapped_column(TS)


class BankLedgerRecord(Base):
    """The SIMULATED bank's own core-banking record (the 'other side' of the truth)."""
    __tablename__ = "mock_bank_ledger"
    __table_args__ = (UniqueConstraint("fdr_number", "ifsc"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id"), index=True)
    fdr_number: Mapped[str] = mapped_column(String(40), index=True)
    ifsc: Mapped[str] = mapped_column(String(11))
    depositor_name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    issue_date: Mapped[date] = mapped_column(Date)
    maturity_date: Mapped[date] = mapped_column(Date)
    lien_marked: Mapped[bool] = mapped_column(Boolean, default=True)
    lien_holder: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[BankRecordStatus] = mapped_column(E(BankRecordStatus), default=BankRecordStatus.ACTIVE)
    updated_at: Mapped[datetime] = mapped_column(TS, default=_now, onupdate=_now)

    bank: Mapped[Bank] = relationship()


# --------------------------------------------------------------------------- #
# Alerts, reminders, notifications
# --------------------------------------------------------------------------- #
class Alert(Base):
    """An escalation ticket. Moves up the ladder automatically until resolved."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_type: Mapped[AlertType] = mapped_column(E(AlertType), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(120), unique=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"), index=True)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), index=True)
    refund_request_id: Mapped[int | None] = mapped_column(ForeignKey("refund_requests.id"))
    region: Mapped[str | None] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(E(Severity), default=Severity.MEDIUM)
    level: Mapped[int] = mapped_column(Integer, default=1)
    assigned_role: Mapped[Role] = mapped_column(E(Role), index=True)
    status: Mapped[AlertStatus] = mapped_column(E(AlertStatus), default=AlertStatus.OPEN, index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    escalate_at: Mapped[datetime | None] = mapped_column(TS)
    history: Mapped[list | None] = mapped_column(JSON)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(TS)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(TS)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)


class ReminderLog(Base):
    """Which maturity reminder (T-90/60/30/7/0/+7...) was sent for which instrument."""
    __tablename__ = "reminder_log"
    __table_args__ = (UniqueConstraint("instrument_id", "offset_days"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    offset_days: Mapped[int] = mapped_column(Integer)
    scheduled_for: Mapped[date] = mapped_column(Date)
    sent_at: Mapped[datetime] = mapped_column(TS, default=_now)
    recipients: Mapped[list | None] = mapped_column(JSON)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), index=True)
    channel: Mapped[NotificationChannel] = mapped_column(E(NotificationChannel))
    recipient: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[DeliveryStatus] = mapped_column(E(DeliveryStatus))
    error: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now, index=True)


# --------------------------------------------------------------------------- #
# Release / refund
# --------------------------------------------------------------------------- #
class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref_number: Mapped[str | None] = mapped_column(String(40), unique=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    ground: Mapped[ReleaseGround] = mapped_column(E(ReleaseGround))
    reason_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RefundStatus] = mapped_column(E(RefundStatus), default=RefundStatus.REQUESTED, index=True)
    instrument_status_before: Mapped[str | None] = mapped_column(String(40))
    precondition_results: Mapped[list | None] = mapped_column(JSON)
    last_precheck_at: Mapped[datetime | None] = mapped_column(TS)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    recommended_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    recommended_at: Mapped[datetime | None] = mapped_column(TS)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(TS)
    processed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    processed_at: Mapped[datetime | None] = mapped_column(TS)
    discharge_document_id: Mapped[int | None] = mapped_column(Integer)
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)
    updated_at: Mapped[datetime] = mapped_column(TS, default=_now, onupdate=_now)

    instrument: Mapped[Instrument] = relationship()
    events: Mapped[list[RefundEvent]] = relationship(order_by="RefundEvent.id")


class RefundEvent(Base):
    __tablename__ = "refund_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    refund_request_id: Mapped[int] = mapped_column(ForeignKey("refund_requests.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(40))
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)


class ComplianceCase(Base):
    """Open compliance cases / enquiries block release of security."""
    __tablename__ = "compliance_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CaseStatus] = mapped_column(E(CaseStatus), default=CaseStatus.OPEN)
    opened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TS, default=_now)
    closed_at: Mapped[datetime | None] = mapped_column(TS)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | int | str | bool | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(TS, default=_now, onupdate=_now)


class Holiday(Base):
    __tablename__ = "holidays"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
