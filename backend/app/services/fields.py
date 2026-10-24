"""Dual-truth per field: DECLARED vs OCR vs BANK/OFFICER CONFIRMED, with a badge each."""
from typing import Any

from sqlalchemy.orm import Session

from app.enums import FieldTrust, VerificationChannel
from app.models import FieldCheck, Instrument, User
from app.services import clock
from app.services.ocr import norm_value, values_match

TRACKED_FIELDS = ["fdr_number", "bank_name", "ifsc", "amount", "issue_date", "maturity_date", "lien_marked", "depositor_name"]

LABELS = {
    "fdr_number": "FDR number",
    "bank_name": "Issuing bank",
    "ifsc": "IFSC",
    "amount": "Amount (INR)",
    "issue_date": "Issue date",
    "maturity_date": "Maturity date",
    "lien_marked": "Lien marked in favour of AICTE",
    "depositor_name": "Depositor name",
}

BADGE = {
    FieldTrust.DECLARED: {"label": "Declared", "color": "grey"},
    FieldTrust.OCR_CONSISTENT: {"label": "Matches document", "color": "blue"},
    FieldTrust.OCR_CONFLICT: {"label": "Differs from document", "color": "orange"},
    FieldTrust.BANK_VERIFIED: {"label": "Bank-verified", "color": "green"},
    FieldTrust.OFFICER_VERIFIED: {"label": "Officer-verified", "color": "teal"},
    FieldTrust.MISMATCH: {"label": "Bank mismatch", "color": "red"},
}


def declared(inst: Instrument, name: str) -> str | None:
    v = getattr(inst, name, None)
    if v is None:
        return None
    if name == "lien_marked":
        return "true" if v else "false"
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _get_or_create(db: Session, inst: Instrument, name: str) -> FieldCheck:
    for fc in inst.field_checks:
        if fc.field_name == name:
            return fc
    fc = FieldCheck(instrument_id=inst.id, field_name=name, trust=FieldTrust.DECLARED)
    db.add(fc)
    inst.field_checks.append(fc)
    return fc


def _recompute(fc: FieldCheck) -> None:
    if fc.confirmed_value is not None:
        ok = values_match(fc.field_name, fc.declared_value, fc.confirmed_value)
        if not ok:
            fc.trust = FieldTrust.MISMATCH
        elif fc.confirmed_channel == VerificationChannel.MANUAL_UPLOAD:
            fc.trust = FieldTrust.OFFICER_VERIFIED
        else:
            fc.trust = FieldTrust.BANK_VERIFIED
    elif fc.ocr_value is not None and fc.declared_value is not None:
        fc.trust = FieldTrust.OCR_CONSISTENT if values_match(fc.field_name, fc.declared_value, fc.ocr_value) else FieldTrust.OCR_CONFLICT
    else:
        fc.trust = FieldTrust.DECLARED


def sync_declared(db: Session, inst: Instrument) -> None:
    for name in TRACKED_FIELDS:
        fc = _get_or_create(db, inst, name)
        fc.declared_value = declared(inst, name)
        _recompute(fc)


def apply_ocr(db: Session, inst: Instrument, ocr_fields: dict[str, dict[str, Any]]) -> None:
    for name in TRACKED_FIELDS:
        fc = _get_or_create(db, inst, name)
        f = ocr_fields.get(name)
        fc.ocr_value = str(f["value"]).lower() if (f and name == "lien_marked") else (str(f["value"]) if f else None)
        fc.ocr_confidence = f["confidence"] if f else None
        fc.declared_value = declared(inst, name)
        _recompute(fc)


def apply_confirmation(
    db: Session, inst: Instrument, confirmed: dict[str, Any], channel: VerificationChannel, user: User | None
) -> list[dict[str, Any]]:
    """Store independently confirmed values. Returns comparison rows."""
    rows = []
    now = clock.now()
    for name in TRACKED_FIELDS:
        if name not in confirmed or confirmed[name] is None:
            continue
        fc = _get_or_create(db, inst, name)
        val = confirmed[name]
        fc.confirmed_value = ("true" if val else "false") if isinstance(val, bool) else str(val)
        fc.confirmed_channel = channel
        fc.confirmed_by = user.id if user else None
        fc.confirmed_at = now
        fc.declared_value = declared(inst, name)
        _recompute(fc)
        rows.append({
            "field": name, "declared": fc.declared_value, "confirmed": fc.confirmed_value,
            "match": fc.trust != FieldTrust.MISMATCH,
        })
    return rows


def field_view(inst: Instrument) -> list[dict[str, Any]]:
    by_name = {fc.field_name: fc for fc in inst.field_checks}
    out = []
    for name in TRACKED_FIELDS:
        fc = by_name.get(name)
        trust = fc.trust if fc else FieldTrust.DECLARED
        out.append({
            "field": name,
            "label": LABELS[name],
            "declared_value": declared(inst, name),
            "ocr_value": fc.ocr_value if fc else None,
            "ocr_confidence": fc.ocr_confidence if fc else None,
            "confirmed_value": fc.confirmed_value if fc else None,
            "confirmed_channel": fc.confirmed_channel.value if fc and fc.confirmed_channel else None,
            "confirmed_at": fc.confirmed_at if fc else None,
            "trust": trust.value,
            "badge": BADGE[trust],
        })
    return out


def normalized(name: str, v: Any) -> str | None:
    return norm_value(name, v)
