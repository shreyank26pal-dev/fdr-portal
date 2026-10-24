"""Rule-based discrepancy & anomaly engine.

* Every rule is data-driven (thresholds come from system_config, any rule can be
  disabled or re-weighted via `rule_overrides` without a code change).
* Every flag carries: rule id, severity, evidence, an officer-facing reason and
  a plain-language institution-facing message.
* The engine ONLY FLAGS. Flags never change an instrument's status; an officer
  confirms or dismisses each one (with a mandatory note).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.enums import (
    SEVERITY_WEIGHT,
    DocType,
    FieldTrust,
    FlagStatus,
    InstrumentStatus,
    OcrStatus,
    Severity,
    VerificationRequestStatus,
    VerificationStatus,
)
from app.models import Bank, Document, Flag, Instrument, VerificationRequest
from app.services import clock, config_service
from app.services.fields import LABELS
from app.services.ocr import norm_id, values_match

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


@dataclass
class RuleMeta:
    code: str
    severity: Severity
    description: str


RULES: dict[str, RuleMeta] = {
    "R01": RuleMeta("MISSING_FIELD", Severity.MEDIUM, "A mandatory field is empty"),
    "R02": RuleMeta("MATURITY_BEFORE_ISSUE", Severity.HIGH, "Maturity date is on/before the issue date"),
    "R03": RuleMeta("FUTURE_ISSUE_DATE", Severity.HIGH, "Issue date is in the future"),
    "R04": RuleMeta("SHORT_VALIDITY", Severity.MEDIUM, "Tenure shorter than the prescribed minimum"),
    "R05": RuleMeta("LOW_AMOUNT", Severity.HIGH, "Amount below the prescribed slab for the purpose"),
    "R06": RuleMeta("LIEN_NOT_MARKED", Severity.HIGH, "Lien not marked in favour of AICTE"),
    "R07": RuleMeta("IFSC_INVALID", Severity.MEDIUM, "IFSC does not follow the RBI format"),
    "R08": RuleMeta("IFSC_BANK_MISMATCH", Severity.HIGH, "IFSC belongs to a different bank than declared"),
    "R09": RuleMeta("DUPLICATE_FDR_OTHER_INSTITUTION", Severity.CRITICAL, "Same FDR number + bank already registered by another institution"),
    "R10": RuleMeta("DUPLICATE_FDR_SAME_INSTITUTION", Severity.MEDIUM, "Same FDR registered twice by this institution"),
    "R11": RuleMeta("DUPLICATE_DOCUMENT", Severity.CRITICAL, "Identical document file already used for another instrument"),
    "R12": RuleMeta("MISSING_DOCUMENT", Severity.MEDIUM, "A required document is not uploaded"),
    "R13": RuleMeta("OCR_MISMATCH", Severity.HIGH, "Typed value differs from the value read on the uploaded document"),
    "R14": RuleMeta("OCR_LOW_CONFIDENCE", Severity.LOW, "Document could not be read reliably - manual check needed"),
    "R15": RuleMeta("AMOUNT_WORDS_MISMATCH", Severity.HIGH, "Amount in words differs from amount in figures on the document"),
    "R16": RuleMeta("BANK_FIELD_MISMATCH", Severity.CRITICAL, "Bank-confirmed value differs from declared value"),
    "R17": RuleMeta("BANK_RECORD_NOT_FOUND", Severity.CRITICAL, "Bank has no record of this FDR"),
    "R18": RuleMeta("BANK_LIEN_ABSENT", Severity.HIGH, "Bank reports no lien in favour of AICTE"),
    "R19": RuleMeta("NEAR_MATURITY_AT_SUBMISSION", Severity.LOW, "FDR submitted very close to its maturity date"),
    "R20": RuleMeta("BANK_RECORD_CLOSED", Severity.CRITICAL, "Bank reports the FDR as closed / prematurely encashed"),
}


@dataclass
class FlagSpec:
    rule_id: str
    code: str
    title: str
    severity: Severity
    officer_message: str
    institution_message: str
    evidence: dict[str, Any]
    fingerprint: str


def _fmt_amt(v: Any) -> str:
    try:
        return f"Rs {Decimal(str(v)):,.2f}"
    except Exception:  # noqa: BLE001
        return str(v)


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)


def _chain_ids(db: Session, inst: Instrument) -> set[int]:
    """All instrument ids linked to inst through renewals (ancestors + descendants)."""
    ids = {inst.id}
    cur = inst
    while cur and cur.replaces_instrument_id:
        ids.add(cur.replaces_instrument_id)
        cur = db.get(Instrument, cur.replaces_instrument_id)
    frontier = [inst.id]
    while frontier:
        children = db.execute(select(Instrument.id).where(Instrument.replaces_instrument_id.in_(frontier))).scalars().all()
        frontier = [c for c in children if c not in ids]
        ids.update(frontier)
    return ids


def resolve_bank(db: Session, bank_name: str | None, ifsc: str | None) -> Bank | None:
    if ifsc and len(ifsc) >= 4:
        b = db.execute(select(Bank).where(Bank.ifsc_prefix == ifsc[:4].upper())).scalar()
        if b:
            return b
    if bank_name:
        return db.execute(select(Bank).where(Bank.name.ilike(bank_name.strip()))).scalar()
    return None


def find_duplicates(
    db: Session, fdr_number: str | None, ifsc: str | None, bank_name: str | None,
    exclude_ids: set[int] | None = None,
) -> list[Instrument]:
    if not fdr_number:
        return []
    key = norm_id(fdr_number)
    q = select(Instrument).where(Instrument.status != InstrumentStatus.REJECTED)
    conds = []
    if ifsc:
        conds.append(Instrument.ifsc == ifsc.upper())
    if bank_name:
        conds.append(Instrument.bank_name.ilike(bank_name))
    bank = resolve_bank(db, bank_name, ifsc)
    if bank:
        conds.append(Instrument.bank_id == bank.id)
    if conds:
        q = q.where(or_(*conds))
    out = []
    for other in db.execute(q).scalars():
        if exclude_ids and other.id in exclude_ids:
            continue
        if norm_id(other.fdr_number) == key:
            out.append(other)
    return out


MANDATORY_FIELDS = ("fdr_number", "bank_name", "ifsc", "amount", "issue_date", "maturity_date")


def missing_fields(inst: Instrument) -> list[str]:
    return [f for f in MANDATORY_FIELDS if getattr(inst, f) in (None, "")]


def missing_documents(db: Session, inst: Instrument, cfg: dict | None = None) -> list[str]:
    cfg = cfg or config_service.all_config(db)
    req = cfg["required_documents"]
    needed = req.get(inst.purpose.value, req.get("default", []))
    have = {d.doc_type.value for d in inst.documents if not d.is_superseded}
    if DocType.RENEWAL_FDR.value in have:
        have.add(DocType.FDR_SCAN.value)
    return [t for t in needed if t not in have]


def _latest_doc(inst: Instrument, types: tuple[DocType, ...]) -> Document | None:
    docs = [d for d in inst.documents if d.doc_type in types and not d.is_superseded]
    return docs[-1] if docs else None


def evaluate(db: Session, inst: Instrument) -> list[FlagSpec]:
    cfg = config_service.all_config(db)
    overrides = cfg.get("rule_overrides") or {}
    today = clock.today()
    out: list[FlagSpec] = []

    def add(rule_id: str, title: str, officer: str, institution: str, evidence: dict | None = None, key: str = "") -> None:
        meta = RULES[rule_id]
        ov = overrides.get(rule_id, {})
        if ov.get("enabled") is False:
            return
        sev = Severity(ov.get("severity", meta.severity.value))
        out.append(FlagSpec(rule_id, meta.code, title, sev, officer, institution, evidence or {}, f"{rule_id}:{key}"))

    drafting = inst.status == InstrumentStatus.DRAFT  # completeness is shown as a checklist while drafting

    # --- R01 mandatory fields
    for f in (missing_fields(inst) if not drafting else []):
        add("R01", f"{LABELS[f]} is missing", f"Mandatory field '{f}' is empty.",
            f"Please fill in the {LABELS[f]}.", {"field": f}, f)

    # --- dates
    if inst.issue_date and inst.maturity_date:
        if inst.maturity_date <= inst.issue_date:
            add("R02", "Maturity date is before issue date",
                f"maturity_date {inst.maturity_date} <= issue_date {inst.issue_date}.",
                "The maturity date must be after the issue date. Please check both dates.",
                {"issue_date": str(inst.issue_date), "maturity_date": str(inst.maturity_date)})
        else:
            months = _months_between(inst.issue_date, inst.maturity_date)
            min_m = int(cfg["min_validity_months"])
            if months < min_m:
                add("R04", f"Tenure {months} months is below the required {min_m}",
                    f"Tenure is {months} months; minimum is {min_m}.",
                    f"The FDR must be valid for at least {min_m} months from its issue date.",
                    {"tenure_months": months, "required": min_m})
    if inst.issue_date and inst.issue_date > today:
        add("R03", "Issue date is in the future", f"issue_date {inst.issue_date} > today {today}.",
            "The issue date cannot be a future date.", {"issue_date": str(inst.issue_date)})
    if inst.maturity_date and inst.status in (InstrumentStatus.DRAFT, InstrumentStatus.SUBMITTED, InstrumentStatus.UNDER_SCRUTINY):
        days_left = (inst.maturity_date - today).days
        lim = int(cfg["min_remaining_validity_days_at_submission"])
        if 0 <= days_left < lim:
            add("R19", f"Only {days_left} days left to maturity",
                f"Submitted with {days_left} days remaining (< {lim}). Renewal will be needed almost immediately.",
                f"This FDR matures in {days_left} days. Consider submitting a renewed FDR instead.",
                {"days_left": days_left})

    # --- amount slab
    if inst.amount is not None:
        slabs = cfg["min_amount_by_purpose"]
        need = Decimal(str(slabs.get(inst.purpose.value, slabs.get("OTHER", 0))))
        if Decimal(inst.amount) < need:
            add("R05", f"Amount {_fmt_amt(inst.amount)} is below the prescribed {_fmt_amt(need)}",
                f"Purpose {inst.purpose.value} requires at least {_fmt_amt(need)}; declared {_fmt_amt(inst.amount)}.",
                f"The deposit must be at least {_fmt_amt(need)} for {inst.purpose.value.replace('_', ' ').title()}.",
                {"declared": str(inst.amount), "required": str(need), "purpose": inst.purpose.value})

    # --- lien
    kws = [k.upper() for k in cfg["lien_holder_keywords"]]
    holder = (inst.lien_in_favour_of or "").upper()
    if not inst.lien_marked or not any(k in holder for k in kws):
        add("R06", "Lien not marked in favour of AICTE",
            f"lien_marked={inst.lien_marked}, lien_in_favour_of='{inst.lien_in_favour_of}'.",
            "The FDR must carry a lien in favour of AICTE. Upload the bank's lien-marking letter.",
            {"lien_marked": inst.lien_marked, "lien_in_favour_of": inst.lien_in_favour_of})

    # --- IFSC
    if inst.ifsc:
        if not IFSC_RE.match(inst.ifsc.upper()):
            add("R07", f"IFSC '{inst.ifsc}' is not valid", "IFSC must be 4 letters + 0 + 6 alphanumerics.",
                "Please check the IFSC code printed on the FDR.", {"ifsc": inst.ifsc})
        elif inst.bank_name:
            by_ifsc = resolve_bank(db, None, inst.ifsc)
            if by_ifsc and by_ifsc.name.lower() != inst.bank_name.strip().lower():
                add("R08", f"IFSC belongs to {by_ifsc.name}, not {inst.bank_name}",
                    f"IFSC prefix {inst.ifsc[:4]} maps to {by_ifsc.name}; declared bank is {inst.bank_name}.",
                    "The IFSC code does not belong to the bank you selected.",
                    {"ifsc": inst.ifsc, "ifsc_bank": by_ifsc.name, "declared_bank": inst.bank_name})

    # --- duplicates (R09 / R10)
    chain = _chain_ids(db, inst)
    for other in find_duplicates(db, inst.fdr_number, inst.ifsc, inst.bank_name, exclude_ids=chain):
        if other.institution_id != inst.institution_id:
            add("R09", f"FDR {inst.fdr_number} is also registered by another institution",
                f"Instrument #{other.id} ({other.ack_number or 'draft'}) of institution "
                f"{other.institution.name if other.institution else other.institution_id} has the same FDR number and bank.",
                "This FDR number is already registered with AICTE under another institution. The case is under scrutiny.",
                {"other_instrument_id": other.id, "other_institution_id": other.institution_id}, str(other.id))
        else:
            add("R10", f"FDR {inst.fdr_number} is registered twice",
                f"Instrument #{other.id} of the same institution has the same FDR number and bank.",
                "You have already registered this FDR. Use 'Renew' on the existing record instead of a new entry.",
                {"other_instrument_id": other.id}, str(other.id))

    # --- duplicate document hashes (R11)
    for doc in inst.documents:
        if doc.is_superseded or doc.doc_type not in (DocType.FDR_SCAN, DocType.RENEWAL_FDR, DocType.LIEN_LETTER):
            continue
        dups = db.execute(
            select(Document).where(
                and_(Document.sha256 == doc.sha256, Document.id != doc.id, Document.instrument_id.is_not(None),
                     Document.instrument_id.not_in(chain))
            )
        ).scalars().all()
        for d in dups:
            other_inst = db.get(Instrument, d.instrument_id)
            if other_inst is None or other_inst.status == InstrumentStatus.REJECTED:
                continue
            cross = other_inst.institution_id != inst.institution_id
            add("R11", "Same document file already submitted" + (" by another institution" if cross else ""),
                f"Document #{doc.id} ({doc.original_filename}) has the same SHA-256 as document #{d.id} "
                f"on instrument #{other_inst.id} (institution {other_inst.institution_id}).",
                "This exact file has already been submitted for a different FDR. Upload the correct original document.",
                {"document_id": doc.id, "sha256": doc.sha256, "other_document_id": d.id,
                 "other_instrument_id": other_inst.id, "cross_institution": cross}, f"{doc.id}:{d.id}")

    # --- required documents (R12)
    for t in (missing_documents(db, inst, cfg) if not drafting else []):
        add("R12", f"{t.replace('_', ' ').title()} not uploaded", f"Required document {t} missing.",
            f"Please upload the {t.replace('_', ' ').lower()}.", {"doc_type": t}, t)

    # --- OCR (R13, R14, R15)
    scan = _latest_doc(inst, (DocType.FDR_SCAN, DocType.RENEWAL_FDR))
    if scan is not None:
        if scan.ocr_status in (OcrStatus.LOW_CONFIDENCE, OcrStatus.UNAVAILABLE, OcrStatus.FAILED):
            add("R14", "FDR scan could not be read reliably",
                f"OCR status {scan.ocr_status.value}, engine {scan.ocr_engine}, confidence {scan.ocr_confidence}.",
                "We could not read your FDR scan clearly. An officer will check it manually; a clearer scan speeds this up.",
                {"document_id": scan.id, "ocr_status": scan.ocr_status.value, "confidence": scan.ocr_confidence},
                str(scan.id))
        for fc in inst.field_checks:
            if fc.trust == FieldTrust.OCR_CONFLICT:
                add("R13", f"{LABELS[fc.field_name]} differs from the uploaded document",
                    f"Declared '{fc.declared_value}' but document reads '{fc.ocr_value}' (confidence {fc.ocr_confidence}).",
                    f"The {LABELS[fc.field_name]} you typed ({fc.declared_value}) does not match the uploaded FDR "
                    f"({fc.ocr_value}). Please correct it.",
                    {"field": fc.field_name, "declared": fc.declared_value, "document": fc.ocr_value,
                     "document_id": scan.id, "confidence": fc.ocr_confidence}, fc.field_name)
        words = (scan.ocr_fields or {}).get("_amount_in_words")
        figures = ((scan.ocr_fields or {}).get("amount") or {}).get("value") or (str(inst.amount) if inst.amount else None)
        if words and figures and not values_match("amount", words["value"], figures):
            add("R15", "Amount in words does not match amount in figures",
                f"Document says '{words['text']}' (= {_fmt_amt(words['value'])}) but figures read {_fmt_amt(figures)}.",
                "The amount written in words on the FDR does not match the amount in figures. "
                "Please upload a correct document from the bank.",
                {"words": words, "figures": figures, "document_id": scan.id})

    # --- bank confirmation (R16, R17, R18, R20)
    for fc in inst.field_checks:
        if fc.trust == FieldTrust.MISMATCH:
            if fc.field_name == "lien_marked" and fc.confirmed_value == "false":
                add("R18", "Bank reports no lien in favour of AICTE",
                    "Bank-confirmed lien_marked=false.",
                    "Your bank reports that no lien is marked in favour of AICTE. Please get the lien marked.",
                    {"declared": fc.declared_value, "bank": fc.confirmed_value})
                continue
            add("R16", f"Bank confirms a different {LABELS[fc.field_name].lower()}",
                f"Declared '{fc.declared_value}', bank confirms '{fc.confirmed_value}' via {fc.confirmed_channel}.",
                f"The bank's record of the {LABELS[fc.field_name].lower()} does not match what was submitted.",
                {"field": fc.field_name, "declared": fc.declared_value, "bank": fc.confirmed_value,
                 "channel": fc.confirmed_channel.value if fc.confirmed_channel else None}, fc.field_name)
    if inst.verification_status == VerificationStatus.NOT_FOUND:
        add("R17", "Bank has no record of this FDR",
            "Bank verification returned NOT_FOUND for this FDR number + IFSC.",
            "The bank could not find this FDR. Please verify the FDR number and IFSC with your bank.", {})
    last = db.execute(
        select(VerificationRequest).where(
            VerificationRequest.instrument_id == inst.id,
            VerificationRequest.status == VerificationRequestStatus.RESPONDED,
        ).order_by(VerificationRequest.id.desc()).limit(1)
    ).scalar()
    if last and (last.response_payload or {}).get("bank_status") in ("CLOSED", "ENCASHED"):
        st = last.response_payload["bank_status"]
        add("R20", f"Bank reports this FDR as {st}",
            f"Verification #{last.id} on {last.responded_at:%d-%m-%Y}: bank status {st}. Security may no longer exist.",
            f"Your bank reports this FDR as {st.lower()}. A valid security must be maintained - contact AICTE immediately.",
            {"verification_request_id": last.id, "bank_status": st}, st)
    return out


def apply(db: Session, inst: Instrument) -> dict[str, Any]:
    """Run all rules and sync auto-flags. Returns summary of changes."""
    db.flush()
    db.refresh(inst)
    specs = evaluate(db, inst)
    by_fp = {f.fingerprint: f for f in inst.flags if f.is_auto}
    now = clock.now()
    seen, new, reopened, cleared = set(), [], [], []
    for s in specs:
        seen.add(s.fingerprint)
        existing = by_fp.get(s.fingerprint)
        if existing is None:
            fl = Flag(
                instrument_id=inst.id, rule_id=s.rule_id, code=s.code, title=s.title, severity=s.severity,
                officer_message=s.officer_message, institution_message=s.institution_message,
                evidence=s.evidence, fingerprint=s.fingerprint, is_auto=True, created_at=now,
            )
            db.add(fl)
            inst.flags.append(fl)
            new.append(s.rule_id)
        elif existing.status == FlagStatus.RESOLVED:
            existing.status = FlagStatus.OPEN
            existing.resolved_at = existing.resolved_by = existing.resolution_note = None
            existing.title, existing.severity = s.title, s.severity
            existing.officer_message, existing.institution_message, existing.evidence = s.officer_message, s.institution_message, s.evidence
            reopened.append(s.rule_id)
        elif existing.status == FlagStatus.OPEN:
            existing.title, existing.severity = s.title, s.severity
            existing.officer_message, existing.institution_message, existing.evidence = s.officer_message, s.institution_message, s.evidence
    for fp, fl in by_fp.items():
        if fp not in seen and fl.status in (FlagStatus.OPEN, FlagStatus.CONFIRMED):
            fl.status = FlagStatus.RESOLVED
            fl.resolved_at = now
            fl.resolution_note = "Auto-cleared: the condition is no longer present."
            cleared.append(fl.rule_id)
    inst.risk_score = compute_risk(inst)
    db.flush()
    return {"new": new, "reopened": reopened, "auto_cleared": cleared, "risk_score": inst.risk_score}


def compute_risk(inst: Instrument) -> int:
    score = sum(SEVERITY_WEIGHT[f.severity] for f in inst.flags if f.status in (FlagStatus.OPEN, FlagStatus.CONFIRMED))
    return min(100, score)


def blocking_flags(inst: Instrument) -> list[Flag]:
    return [f for f in inst.flags if f.status in (FlagStatus.OPEN, FlagStatus.CONFIRMED)
            and f.severity in (Severity.HIGH, Severity.CRITICAL)]
