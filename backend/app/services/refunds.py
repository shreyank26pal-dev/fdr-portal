"""Guarded release / refund workflow.

* A pre-condition engine screens every request BEFORE a human looks at it.
* Two-person rule: an officer RECOMMENDS, a different Approving Authority APPROVES.
* Release is never automatic - every step is an explicit human action.
* Courier-style tracker for the institution.
"""
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import (
    HELD_STATUSES,
    REFUND_OPEN_STATUSES,
    AlertType,
    CaseStatus,
    DocType,
    InstrumentStatus as S,
    RefundStatus as R,
    ReleaseGround,
    Role,
    TrustLevel,
)
from app.models import BankLedgerRecord, ComplianceCase, Document, Instrument, RefundEvent, RefundRequest, User
from app.services import alerts, audit, clock, config_service, letters, lifecycle, notifications, rules, storage
from app.services.ocr import norm_id

OFFICERS = (Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER, Role.ADMIN)
APPROVERS = (Role.APPROVING_AUTHORITY, Role.ADMIN)


def _event(db: Session, rr: RefundRequest, to: R, actor: User | None, remarks: str | None) -> None:
    frm = rr.status.value if rr.status else None
    rr.status = to
    rr.updated_at = clock.now()
    db.add(RefundEvent(refund_request_id=rr.id, from_status=frm, to_status=to.value,
                       actor_id=actor.id if actor else None, actor_role=actor.role.value if actor else "SYSTEM",
                       remarks=remarks, created_at=clock.now()))
    audit.record(db, actor, f"REFUND_{to.value}", "refund_request", rr.id,
                 before={"status": frm}, after={"status": to.value, "remarks": remarks},
                 institution_id=rr.institution_id)
    notifications.notify_institution(
        db, rr.institution_id, f"Release request {rr.ref_number}: {to.value.replace('_', ' ').title()}",
        remarks or f"Your release request is now {to.value.replace('_', ' ').lower()}.",
        link=f"/refunds/{rr.id}", category="REFUND",
    )


def preconditions(db: Session, rr: RefundRequest) -> list[dict[str, Any]]:
    inst = db.get(Instrument, rr.instrument_id)
    checks: list[dict[str, Any]] = []

    def chk(code: str, label: str, passed: bool, detail: str, blocking: bool = True) -> None:
        checks.append({"code": code, "label": label, "passed": bool(passed), "detail": detail, "blocking": blocking})

    eligible = inst.status in lifecycle.RELEASABLE or inst.status in (S.RELEASE_REQUESTED, S.RELEASE_APPROVED)
    chk("INSTRUMENT_ELIGIBLE", "Instrument is held by AICTE and eligible for release", eligible,
        f"Current status: {inst.status.value}")
    chk("BANK_CONFIRMED", "Instrument has been independently confirmed (bank / officer)",
        inst.trust_level in (TrustLevel.BANK_CONFIRMED, TrustLevel.OFFICER_VERIFIED),
        f"Trust level: {inst.trust_level.value}")
    open_cases = db.execute(select(ComplianceCase).where(
        ComplianceCase.institution_id == rr.institution_id, ComplianceCase.status == CaseStatus.OPEN)).scalars().all()
    chk("NO_OPEN_COMPLIANCE_CASE", "No open compliance case / enquiry against the institution", not open_cases,
        "; ".join(c.title for c in open_cases) or "None open")
    blockers = rules.blocking_flags(inst)
    chk("NO_OPEN_DISCREPANCY", "No unresolved high-severity discrepancy on the instrument", not blockers,
        "; ".join(f.title for f in blockers) or "None")
    required = config_service.get(db, "release_required_documents")
    have = {d.doc_type.value for d in db.execute(select(Document).where(Document.refund_request_id == rr.id)).scalars()}
    missing = [t for t in required if t not in have]
    chk("DOCUMENTS_UPLOADED", "Required documents uploaded (" + ", ".join(required) + ")", not missing,
        "Missing: " + ", ".join(missing) if missing else "All uploaded")
    others = db.execute(select(func.count(RefundRequest.id)).where(
        RefundRequest.instrument_id == rr.instrument_id, RefundRequest.id != rr.id,
        RefundRequest.status.in_(REFUND_OPEN_STATUSES))).scalar()
    chk("SINGLE_ACTIVE_REQUEST", "No other open release request for this instrument", others == 0, f"{others} other open")

    if rr.ground == ReleaseGround.REPLACED_BY_RENEWAL:
        repl = db.execute(select(Instrument).where(Instrument.replaces_instrument_id == inst.id,
                                                   Instrument.status.in_(HELD_STATUSES))).scalar()
        chk("REPLACEMENT_ACTIVE", "Replacement instrument is active", repl is not None,
            f"Replacement #{repl.id}" if repl else "No active replacement found")
    if rr.ground == ReleaseGround.EXCESS_DEPOSIT:
        held = db.execute(select(func.coalesce(func.sum(Instrument.amount), 0)).where(
            Instrument.institution_id == rr.institution_id, Instrument.status.in_(HELD_STATUSES))).scalar()
        slabs = config_service.get(db, "min_amount_by_purpose")
        need = Decimal(str(slabs.get(inst.purpose.value, 0)))
        remaining = Decimal(held) - Decimal(inst.amount or 0)
        chk("MIN_SECURITY_MAINTAINED", "Minimum prescribed security remains after release", remaining >= need,
            f"Held Rs {Decimal(held):,.0f}; after release Rs {remaining:,.0f}; required Rs {need:,.0f}")
    return checks


def _run_precheck(db: Session, rr: RefundRequest) -> bool:
    rr.precondition_results = preconditions(db, rr)
    rr.last_precheck_at = clock.now()
    return all(c["passed"] for c in rr.precondition_results if c["blocking"])


def create(db: Session, inst: Instrument, user: User, ground: ReleaseGround, reason: str | None) -> RefundRequest:
    if inst.institution_id != user.institution_id:
        raise HTTPException(404, "Instrument not found")
    if inst.status not in lifecycle.RELEASABLE:
        raise HTTPException(409, f"Release cannot be requested for status {inst.status.value}")
    rr = RefundRequest(instrument_id=inst.id, institution_id=inst.institution_id, ground=ground,
                       reason_text=reason, requested_by=user.id, instrument_status_before=inst.status.value,
                       created_at=clock.now())
    db.add(rr)
    db.flush()
    rr.ref_number = f"AICTE/REL/{clock.today().year}/{rr.id:05d}"
    rr.status = None  # type: ignore[assignment]
    _event(db, rr, R.REQUESTED, user, "Release request submitted")
    lifecycle.transition(db, inst, "request_release", user, note=f"Release request {rr.ref_number}",
                         data={"refund_request_id": rr.id, "ground": ground.value})
    if not _run_precheck(db, rr):
        _event(db, rr, R.BLOCKED, None, "Pre-conditions not met: " + "; ".join(
            c["label"] for c in rr.precondition_results if not c["passed"] and c["blocking"]))
    return rr


def recheck(db: Session, rr: RefundRequest, actor: User) -> RefundRequest:
    ok = _run_precheck(db, rr)
    if rr.status == R.BLOCKED and ok:
        _event(db, rr, R.REQUESTED, actor, "All pre-conditions now satisfied")
    elif rr.status in (R.REQUESTED, R.UNDER_REVIEW, R.RECOMMENDED) and not ok:
        _event(db, rr, R.BLOCKED, actor, "Pre-conditions no longer satisfied")
    return rr


def _require(rr: RefundRequest, allowed: tuple[R, ...], action: str) -> None:
    if rr.status not in allowed:
        raise HTTPException(409, f"Cannot {action} a request in status {rr.status.value}")


def start_review(db: Session, rr: RefundRequest, officer: User, remarks: str | None) -> RefundRequest:
    _require(rr, (R.REQUESTED,), "start review of")
    rr.reviewer_id = officer.id
    _event(db, rr, R.UNDER_REVIEW, officer, remarks or "Officer has started scrutiny")
    return rr


def recommend(db: Session, rr: RefundRequest, officer: User, remarks: str | None) -> RefundRequest:
    _require(rr, (R.UNDER_REVIEW,), "recommend")
    if not _run_precheck(db, rr):
        raise HTTPException(409, {"message": "Pre-conditions failing", "checks": rr.precondition_results})
    rr.recommended_by = officer.id
    rr.recommended_at = clock.now()
    _event(db, rr, R.RECOMMENDED, officer, remarks or "Recommended for release")
    return rr


def approve(db: Session, rr: RefundRequest, approver: User, remarks: str | None) -> RefundRequest:
    _require(rr, (R.RECOMMENDED,), "approve")
    if approver.id == rr.recommended_by:
        raise HTTPException(409, "Two-person rule: the recommending officer cannot also approve")
    if not _run_precheck(db, rr):
        raise HTTPException(409, {"message": "Pre-conditions failing", "checks": rr.precondition_results})
    rr.approved_by = approver.id
    rr.approved_at = clock.now()
    _event(db, rr, R.APPROVED, approver, remarks or "Release sanctioned by competent authority")
    inst = db.get(Instrument, rr.instrument_id)
    lifecycle.transition(db, inst, "approve_release", approver, note=f"Release sanctioned ({rr.ref_number})")
    return rr


def process(db: Session, rr: RefundRequest, officer: User, remarks: str | None) -> RefundRequest:
    """Issue the discharge letter and close the instrument."""
    _require(rr, (R.APPROVED,), "process")
    inst = db.get(Instrument, rr.instrument_id)
    pdf = letters.discharge_letter(db, rr, inst)
    key, digest = storage.save(pdf)
    doc = Document(institution_id=rr.institution_id, instrument_id=inst.id, refund_request_id=rr.id,
                   doc_type=DocType.DISCHARGE_LETTER, original_filename=f"discharge_{rr.ref_number.replace('/', '_')}.pdf",
                   content_type="application/pdf", size_bytes=len(pdf), sha256=digest, storage_key=key,
                   uploaded_by=officer.id)
    db.add(doc)
    db.flush()
    rr.discharge_document_id = doc.id
    rr.processed_by = officer.id
    rr.processed_at = clock.now()
    _event(db, rr, R.PROCESSED, officer, remarks or "Discharge letter issued to the bank. Lien to be removed.")
    lifecycle.transition(db, inst, "complete_release", officer, note=f"Released ({rr.ref_number})",
                         data={"discharge_document_id": doc.id})
    # Simulated bank side: lien removed on receipt of discharge letter
    rec = db.execute(select(BankLedgerRecord).where(BankLedgerRecord.ifsc == (inst.ifsc or ""))).scalars().all()
    for r in rec:
        if norm_id(r.fdr_number) == norm_id(inst.fdr_number):
            r.lien_marked = False
            r.lien_holder = None
    alerts.resolve_for_instrument(db, inst.id, tuple(AlertType), f"Released ({rr.ref_number})")
    return rr


def reject(db: Session, rr: RefundRequest, user: User, remarks: str) -> RefundRequest:
    _require(rr, (R.REQUESTED, R.BLOCKED, R.UNDER_REVIEW, R.RECOMMENDED), "reject")
    _event(db, rr, R.REJECTED, user, remarks)
    _revert_instrument(db, rr, user, f"Release request {rr.ref_number} rejected")
    return rr


def withdraw(db: Session, rr: RefundRequest, user: User) -> RefundRequest:
    _require(rr, (R.REQUESTED, R.BLOCKED, R.UNDER_REVIEW), "withdraw")
    _event(db, rr, R.WITHDRAWN, user, "Withdrawn by institution")
    _revert_instrument(db, rr, user, f"Release request {rr.ref_number} withdrawn")
    return rr


def _revert_instrument(db: Session, rr: RefundRequest, user: User, note: str) -> None:
    inst = db.get(Instrument, rr.instrument_id)
    if inst.status in (S.RELEASE_REQUESTED, S.RELEASE_APPROVED):
        back = S(rr.instrument_status_before) if rr.instrument_status_before else S.ACTIVE
        lifecycle.transition(db, inst, "revert_release", user, note=note, to_status=back)
    alerts.resolve_for_instrument(db, inst.id, (AlertType.REFUND_PENDING,), note)


STEPS = [
    ("REQUESTED", "Requested"),
    ("UNDER_REVIEW", "Under review"),
    ("RECOMMENDED", "Recommended by officer"),
    ("APPROVED", "Approved by competent authority"),
    ("PROCESSED", "Processed - discharge letter issued"),
]


def tracker(rr: RefundRequest) -> dict[str, Any]:
    """Courier-style tracking view."""
    reached: dict[str, Any] = {}
    for ev in rr.events:
        if ev.to_status not in reached:
            reached[ev.to_status] = {"at": ev.created_at, "remarks": ev.remarks, "by_role": ev.actor_role}
    order = [s for s, _ in STEPS]
    cur_idx = order.index(rr.status.value) if rr.status.value in order else None
    steps = []
    for i, (code, label) in enumerate(STEPS):
        info = reached.get(code)
        if rr.status in (R.REJECTED, R.WITHDRAWN):
            state = "done" if info else "cancelled"
        elif cur_idx is not None and i < cur_idx:
            state = "done"
        elif cur_idx is not None and i == cur_idx:
            state = "done" if code == "PROCESSED" else "current"
        else:
            state = "pending"
        steps.append({"code": code, "label": label, "state": state,
                      "at": info["at"] if info else None, "remarks": info["remarks"] if info else None})
    return {
        "ref_number": rr.ref_number, "status": rr.status.value,
        "is_blocked": rr.status == R.BLOCKED, "is_closed": rr.status in (R.PROCESSED, R.REJECTED, R.WITHDRAWN),
        "steps": steps, "preconditions": rr.precondition_results,
        "history": [{"from": e.from_status, "to": e.to_status, "at": e.created_at, "by_role": e.actor_role,
                     "remarks": e.remarks} for e in rr.events],
    }
