"""All enumerations used by the data model. Stored as strings in the DB."""
from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover
        return self.value


class Role(StrEnum):
    INSTITUTION = "INSTITUTION"                  # college / institute user
    SCRUTINY_OFFICER = "SCRUTINY_OFFICER"        # AICTE Regulation Bureau dealing hand / finance officer
    REGIONAL_OFFICER = "REGIONAL_OFFICER"        # AICTE regional office (jurisdiction = region)
    APPROVING_AUTHORITY = "APPROVING_AUTHORITY"  # senior official, sanctions approval / release
    BANK = "BANK"                                # bank nodal officer (confirms FDRs)
    ADMIN = "ADMIN"                              # bureau admin / bureau head
    AUDITOR = "AUDITOR"                          # read-only


OFFICER_ROLES = (Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER, Role.APPROVING_AUTHORITY, Role.ADMIN)
AICTE_ROLES = OFFICER_ROLES + (Role.AUDITOR,)


class InstrumentStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_SCRUTINY = "UNDER_SCRUTINY"
    DISCREPANCY_RAISED = "DISCREPANCY_RAISED"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    EXPIRING_SOON = "EXPIRING_SOON"        # inside reminder window (default T-90)
    ACTION_REQUIRED = "ACTION_REQUIRED"    # T-30: institution must upload renewal proof, ticket opened
    MATURED = "MATURED"
    OVERDUE = "OVERDUE"                    # matured + grace period crossed without action
    RENEWED = "RENEWED"                    # closed, replaced by a newer instrument
    RELEASE_REQUESTED = "RELEASE_REQUESTED"
    RELEASE_APPROVED = "RELEASE_APPROVED"
    RELEASED = "RELEASED"                  # closed, discharged to institution
    REJECTED = "REJECTED"


# Statuses where AICTE holds a live, valid security
HELD_STATUSES = (
    InstrumentStatus.ACTIVE,
    InstrumentStatus.EXPIRING_SOON,
    InstrumentStatus.ACTION_REQUIRED,
    InstrumentStatus.MATURED,
    InstrumentStatus.OVERDUE,
    InstrumentStatus.RELEASE_REQUESTED,
    InstrumentStatus.RELEASE_APPROVED,
)
# Statuses watched by the maturity monitor
MONITORED_STATUSES = (
    InstrumentStatus.ACTIVE,
    InstrumentStatus.EXPIRING_SOON,
    InstrumentStatus.ACTION_REQUIRED,
    InstrumentStatus.MATURED,
    InstrumentStatus.OVERDUE,
)
CLOSED_STATUSES = (InstrumentStatus.RENEWED, InstrumentStatus.RELEASED, InstrumentStatus.REJECTED)
PIPELINE_STATUSES = (
    InstrumentStatus.SUBMITTED,
    InstrumentStatus.UNDER_SCRUTINY,
    InstrumentStatus.DISCREPANCY_RAISED,
    InstrumentStatus.VERIFIED,
)


class VerificationStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SENT_TO_BANK = "SENT_TO_BANK"
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    NOT_FOUND = "NOT_FOUND"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class TrustLevel(StrEnum):
    """Overall trust of the instrument record (claimed vs confirmed)."""
    SELF_DECLARED = "SELF_DECLARED"
    BANK_CONFIRMED = "BANK_CONFIRMED"      # confirmed by bank API or bank nodal officer
    OFFICER_VERIFIED = "OFFICER_VERIFIED"  # officer uploaded a written bank confirmation


class FieldTrust(StrEnum):
    """Badge shown next to every single field."""
    DECLARED = "DECLARED"                  # only the institution says so
    OCR_CONSISTENT = "OCR_CONSISTENT"      # declared value matches what OCR read on the document
    OCR_CONFLICT = "OCR_CONFLICT"          # declared value differs from the document
    BANK_VERIFIED = "BANK_VERIFIED"        # independently confirmed by the bank
    OFFICER_VERIFIED = "OFFICER_VERIFIED"  # confirmed by officer from bank letter
    MISMATCH = "MISMATCH"                  # bank says something different


class VerificationChannel(StrEnum):
    BANK_API = "BANK_API"
    BANK_EMAIL_LINK = "BANK_EMAIL_LINK"
    BANK_PORTAL = "BANK_PORTAL"
    MANUAL_UPLOAD = "MANUAL_UPLOAD"


class VerificationRequestStatus(StrEnum):
    PENDING = "PENDING"
    RESPONDED = "RESPONDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class DocType(StrEnum):
    FDR_SCAN = "FDR_SCAN"
    LIEN_LETTER = "LIEN_LETTER"
    RENEWAL_FDR = "RENEWAL_FDR"
    BANK_CONFIRMATION = "BANK_CONFIRMATION"
    UNDERTAKING = "UNDERTAKING"
    DISCHARGE_LETTER = "DISCHARGE_LETTER"
    OTHER = "OTHER"


class OcrStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    DONE = "DONE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class Purpose(StrEnum):
    NEW_APPROVAL = "NEW_APPROVAL"
    EXTENSION_OF_APPROVAL = "EXTENSION_OF_APPROVAL"
    INCREASE_IN_INTAKE = "INCREASE_IN_INTAKE"
    NEW_COURSE = "NEW_COURSE"
    CLOSURE_UNDERTAKING = "CLOSURE_UNDERTAKING"
    OTHER = "OTHER"


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


SEVERITY_WEIGHT = {
    Severity.INFO: 0,
    Severity.LOW: 5,
    Severity.MEDIUM: 15,
    Severity.HIGH: 30,
    Severity.CRITICAL: 50,
}


class FlagStatus(StrEnum):
    OPEN = "OPEN"            # raised, waiting for a human decision
    CONFIRMED = "CONFIRMED"  # officer agrees it is a real problem
    DISMISSED = "DISMISSED"  # officer marked false positive (reason mandatory)
    RESOLVED = "RESOLVED"    # problem no longer present (fixed / auto-cleared)


class DiscrepancyReason(StrEnum):
    WRONG_AMOUNT = "WRONG_AMOUNT"
    LIEN_NOT_MARKED = "LIEN_NOT_MARKED"
    SHORT_VALIDITY = "SHORT_VALIDITY"
    ILLEGIBLE = "ILLEGIBLE"
    SUSPECTED_FORGERY = "SUSPECTED_FORGERY"
    MISSING_DOCUMENT = "MISSING_DOCUMENT"
    DATA_MISMATCH = "DATA_MISMATCH"
    OTHER = "OTHER"


class AlertType(StrEnum):
    ACTION_REQUIRED = "ACTION_REQUIRED"          # T-30 renewal ticket
    OVERDUE = "OVERDUE"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    DISCREPANCY_PENDING = "DISCREPANCY_PENDING"
    REFUND_PENDING = "REFUND_PENDING"
    BANK_STATUS_CHANGED = "BANK_STATUS_CHANGED"  # continuous re-verification found encashment / lien removal


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"


class DeliveryStatus(StrEnum):
    SENT = "SENT"
    SIMULATED = "SIMULATED"
    FAILED = "FAILED"


class RefundStatus(StrEnum):
    REQUESTED = "REQUESTED"
    BLOCKED = "BLOCKED"            # pre-conditions failing
    UNDER_REVIEW = "UNDER_REVIEW"
    RECOMMENDED = "RECOMMENDED"    # officer recommends, approver must sanction
    APPROVED = "APPROVED"
    PROCESSED = "PROCESSED"        # discharge letter issued, FDR released
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


REFUND_OPEN_STATUSES = (
    RefundStatus.REQUESTED,
    RefundStatus.BLOCKED,
    RefundStatus.UNDER_REVIEW,
    RefundStatus.RECOMMENDED,
    RefundStatus.APPROVED,
)


class ReleaseGround(StrEnum):
    APPROVAL_WITHDRAWN = "APPROVAL_WITHDRAWN"
    CLOSURE_COMPLETED = "CLOSURE_COMPLETED"
    EXCESS_DEPOSIT = "EXCESS_DEPOSIT"
    PROGRAMME_DISCONTINUED = "PROGRAMME_DISCONTINUED"
    REPLACED_BY_RENEWAL = "REPLACED_BY_RENEWAL"
    OTHER = "OTHER"


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class BankRecordStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ENCASHED = "ENCASHED"
