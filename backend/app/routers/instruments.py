from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.enums import (
    AlertType,
    DocType,
    FlagStatus,
    InstrumentStatus as S,
    Role,
    Severity,
    TrustLevel,
    VerificationStatus,
)
from app.models import Flag, Institution, Instrument, Observation, User
from app.routers.common import detail, get_instrument, list_item, scope_institution_ids
from app.schemas import (
    ActionNoteIn,
    DiscrepancyIn,
    DocumentOut,
    DuplicateCheckIn,
    InstrumentIn,
    ManualVerifyIn,
    ObservationIn,
    RejectIn,
)
from app.security import get_current_user, require_roles
from app.services import (
    alerts,
    audit,
    clock,
    config_service,
    documents,
    fields,
    lifecycle,
    monitor,
    notifications,
    renewals,
    rules,
    storage,
    verification,
)

router = APIRouter(prefix="/instruments", tags=["Instruments (FDR lifecycle)"])

OFFICER = (Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER, Role.ADMIN)
APPROVER = (Role.APPROVING_AUTHORITY, Role.ADMIN)


# --------------------------------------------------------------------------- #
# Listing / search
# --------------------------------------------------------------------------- #
@router.get("", summary="Search & list instruments (scoped to the caller's role)")
def list_instruments(
    status: list[S] | None = Query(None),
    q: str | None = Query(None, description="FDR no / ack no / institution name / AICTE id"),
    institution_id: int | None = None,
    bank_name: str | None = None,
    region: str | None = None,
    verification_status: VerificationStatus | None = None,
    trust_level: TrustLevel | None = None,
    maturing_within_days: int | None = None,
    min_risk: int | None = None,
    has_open_flags: bool | None = None,
    sort: Literal["risk", "maturity", "oldest", "newest", "amount"] = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Instrument).join(Institution, Institution.id == Instrument.institution_id)
    ids = scope_institution_ids(db, user)
    if ids is not None:
        query = query.where(Instrument.institution_id.in_(ids))
    if user.role == Role.BANK:
        query = query.where(Instrument.bank_id == user.bank_id)
    if status:
        query = query.where(Instrument.status.in_(status))
    if institution_id:
        query = query.where(Instrument.institution_id == institution_id)
    if bank_name:
        query = query.where(Instrument.bank_name.ilike(f"%{bank_name}%"))
    if region:
        query = query.where(Institution.region == region)
    if verification_status:
        query = query.where(Instrument.verification_status == verification_status)
    if trust_level:
        query = query.where(Instrument.trust_level == trust_level)
    if maturing_within_days is not None:
        t = clock.today()
        query = query.where(Instrument.maturity_date.between(t, t + timedelta(days=maturing_within_days)))
    if min_risk is not None:
        query = query.where(Instrument.risk_score >= min_risk)
    if has_open_flags:
        sub = select(Flag.instrument_id).where(Flag.status.in_([FlagStatus.OPEN, FlagStatus.CONFIRMED]))
        query = query.where(Instrument.id.in_(sub))
    if q:
        like = f"%{q}%"
        query = query.where(or_(Instrument.fdr_number.ilike(like), Instrument.ack_number.ilike(like),
                                Institution.name.ilike(like), Institution.aicte_id.ilike(like)))
    order = {
        "risk": [Instrument.risk_score.desc(), Instrument.submitted_at.asc()],
        "maturity": [Instrument.maturity_date.asc()],
        "oldest": [Instrument.submitted_at.asc().nulls_last()],
        "newest": [Instrument.id.desc()],
        "amount": [Instrument.amount.desc().nulls_last()],
    }[sort]
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
    rows = db.execute(query.order_by(*order).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {"items": [list_item(i) for i in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/work-queue", summary="Officer work queue - highest risk first, then oldest")
def work_queue(user: User = Depends(require_roles(*OFFICER, Role.APPROVING_AUTHORITY)), db: Session = Depends(get_db)):
    statuses = [S.VERIFIED] if user.role == Role.APPROVING_AUTHORITY else [S.SUBMITTED, S.UNDER_SCRUTINY]
    query = select(Instrument).where(Instrument.status.in_(statuses))
    ids = scope_institution_ids(db, user)
    if ids is not None:
        query = query.where(Instrument.institution_id.in_(ids))
    rows = db.execute(query.order_by(Instrument.risk_score.desc(), Instrument.submitted_at.asc())).scalars().all()
    out = []
    for i in rows:
        d = list_item(i)
        d["flag_chips"] = [{"rule_id": f.rule_id, "title": f.title, "severity": f.severity.value}
                           for f in i.flags if f.status in (FlagStatus.OPEN, FlagStatus.CONFIRMED)]
        d["age_days"] = (clock.now() - i.submitted_at).days if i.submitted_at else None
        out.append(d)
    return out


@router.post("/check-duplicate", summary="Pre-save duplicate check (FDR number + bank)")
def check_duplicate(body: DuplicateCheckIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = rules.find_duplicates(db, body.fdr_number, body.ifsc, body.bank_name)
    if user.role == Role.INSTITUTION:
        return {
            "duplicate": bool(matches),
            "same_institution": any(m.institution_id == user.institution_id for m in matches),
            "other_institution": any(m.institution_id != user.institution_id for m in matches),
            "message": ("This FDR is already registered with AICTE." if matches else "No duplicate found."),
        }
    return {"duplicate": bool(matches), "matches": [list_item(m) for m in matches]}


# --------------------------------------------------------------------------- #
# Create / edit (institution)
# --------------------------------------------------------------------------- #
def _apply_body(db: Session, inst: Instrument, body: InstrumentIn) -> dict:
    changes = {}
    for k, v in body.model_dump(exclude_unset=True).items():
        old = getattr(inst, k)
        if old != v:
            changes[k] = {"from": old, "to": v}
            setattr(inst, k, v)
    if "bank_name" in changes or "ifsc" in changes:
        bank = rules.resolve_bank(db, inst.bank_name, inst.ifsc)
        inst.bank_id = bank.id if bank else None
    return changes


@router.post("", status_code=201, summary="Create a draft FDR record (institution)")
def create_instrument(body: InstrumentIn, user: User = Depends(require_roles(Role.INSTITUTION)),
                      db: Session = Depends(get_db)):
    renewals.ensure_not_locked(db, user.institution_id)
    inst = Instrument(institution_id=user.institution_id, created_by=user.id, status=S.DRAFT,
                      lien_marked=False, purpose=body.purpose or "EXTENSION_OF_APPROVAL")
    db.add(inst)
    db.flush()
    _apply_body(db, inst, body)
    fields.sync_declared(db, inst)
    lifecycle.log_event(db, inst, "created", user, note="Draft created",
                        audit_after=audit.snapshot(inst, lifecycle.SNAPSHOT_FIELDS))
    summary = rules.apply(db, inst)
    db.commit()
    return {**detail(db, inst, user), "rule_summary": summary}


@router.get("/{instrument_id}", summary="Full case view: dual-truth fields, flags, documents, timeline, lineage")
def get_one(instrument_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return detail(db, get_instrument(db, instrument_id, user), user)


@router.patch("/{instrument_id}", summary="Edit declared values (only DRAFT / DISCREPANCY_RAISED)")
def update_instrument(instrument_id: int, body: InstrumentIn, user: User = Depends(require_roles(Role.INSTITUTION)),
                      db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    if inst.status not in (S.DRAFT, S.DISCREPANCY_RAISED):
        raise HTTPException(409, f"Cannot edit in status {inst.status.value}")
    changes = _apply_body(db, inst, body)
    if changes:
        fields.sync_declared(db, inst)
        inst.version += 1
        lifecycle.log_event(db, inst, "edited", user, note=f"Edited: {', '.join(changes)}",
                            audit_before={k: v["from"] for k, v in changes.items()},
                            audit_after={k: v["to"] for k, v in changes.items()})
    summary = rules.apply(db, inst)
    db.commit()
    return {**detail(db, inst, user), "rule_summary": summary}


@router.post("/{instrument_id}/documents", status_code=201,
             summary="Upload a document (encrypted at rest). FDR scans are OCR'd and cross-checked instantly.")
async def upload_document(
    instrument_id: int,
    file: UploadFile = File(...),
    doc_type: DocType = Form(DocType.FDR_SCAN),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inst = get_instrument(db, instrument_id, user)
    if user.role == Role.INSTITUTION:
        if inst.status not in (S.DRAFT, S.DISCREPANCY_RAISED):
            raise HTTPException(409, "Documents can only be added while the record is a draft or under discrepancy")
    elif user.role in OFFICER:
        if doc_type != DocType.BANK_CONFIRMATION:
            raise HTTPException(403, "Officers may only upload BANK_CONFIRMATION documents")
    else:
        raise HTTPException(403, "Not allowed")
    data = await file.read()
    try:
        doc, result = documents.upload(db, user=user, institution_id=inst.institution_id, data=data,
                                       filename=file.filename or "upload", doc_type=doc_type, instrument=inst)
    except storage.UploadRejected as exc:
        raise HTTPException(415, str(exc))
    db.commit()
    resp = {"document": DocumentOut.model_validate(doc).model_dump(), "ocr": None, "cross_check": None}
    if result is not None:
        resp["ocr"] = result.to_dict()
        resp["cross_check"] = documents.cross_check(inst, result)
        resp["mismatches"] = [r for r in resp["cross_check"] if r["status"] == "MISMATCH"]
    resp["flags"] = [{"rule_id": f.rule_id, "title": f.title, "severity": f.severity.value,
                      "message": f.institution_message if user.role == Role.INSTITUTION else f.officer_message}
                     for f in inst.flags if f.status in (FlagStatus.OPEN, FlagStatus.CONFIRMED)]
    return resp


@router.post("/{instrument_id}/submit", summary="Submit for scrutiny (completeness check + acknowledgement number)")
def submit(instrument_id: int, user: User = Depends(require_roles(Role.INSTITUTION)), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    if not inst.replaces_instrument_id:
        renewals.ensure_not_locked(db, inst.institution_id)
    problems = [{"rule_id": "R01", "message": f"Please fill in the {fields.LABELS[f]}."} for f in rules.missing_fields(inst)]
    problems += [{"rule_id": "R12", "message": f"Please upload the {t.replace('_', ' ').lower()}."}
                 for t in rules.missing_documents(db, inst)]
    if inst.issue_date and inst.maturity_date and inst.maturity_date <= inst.issue_date:
        problems.append({"rule_id": "R02", "message": "The maturity date must be after the issue date."})
    if problems:
        raise HTTPException(422, {"message": "Record is incomplete", "problems": problems})
    first = inst.ack_number is None
    lifecycle.transition(db, inst, "submit", user, note="Submitted by institution" if first else "Re-submitted after discrepancy")
    if first:
        inst.ack_number = f"AICTE/SD/{clock.today().year}/{inst.id:06d}"
    renewals.on_renewal_submitted(db, inst)
    rules.apply(db, inst)
    notifications.notify_institution(db, inst.institution_id, f"FDR submitted - Ack {inst.ack_number}",
                                     f"FDR {inst.fdr_number} has been submitted. Acknowledgement: {inst.ack_number}.",
                                     link=f"/instruments/{inst.id}", category="SUBMISSION", sms=True)
    notifications.notify_role(db, Role.SCRUTINY_OFFICER, "New FDR submission",
                              f"{inst.institution.name}: FDR {inst.fdr_number} (risk {inst.risk_score}).",
                              link=f"/instruments/{inst.id}", category="SUBMISSION", email=False)
    db.commit()
    return detail(db, inst, user)


# --------------------------------------------------------------------------- #
# Officer scrutiny & verification
# --------------------------------------------------------------------------- #
@router.post("/{instrument_id}/pickup", summary="Officer picks up the case")
def pickup(instrument_id: int, user: User = Depends(require_roles(*OFFICER)), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    inst.assigned_officer_id = user.id
    lifecycle.transition(db, inst, "pickup", user, note=f"Picked up by {user.full_name}")
    db.commit()
    return detail(db, inst, user)


@router.post("/{instrument_id}/verify-bank",
             summary="Verify with the bank: API first (simulated AA sandbox), auto-fallback to secure email link")
def verify_bank(instrument_id: int, user: User = Depends(require_roles(*OFFICER)), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    vr = verification.verify_via_api(db, inst, user)
    db.commit()
    return {"verification": verification.serialize(vr, include_token=settings.DEMO_MODE), **detail(db, inst, user)}


@router.post("/{instrument_id}/manual-verify",
             summary="Record values from a written bank confirmation (OFFICER_VERIFIED)")
def manual_verify(instrument_id: int, body: ManualVerifyIn, user: User = Depends(require_roles(*OFFICER)),
                  db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    if body.document_id is not None and not any(d.id == body.document_id and d.doc_type == DocType.BANK_CONFIRMATION
                                                for d in inst.documents):
        raise HTTPException(422, "document_id must be a BANK_CONFIRMATION document of this instrument")
    values = body.model_dump(exclude={"document_id", "remarks"}, exclude_none=True)
    vr = verification.manual_verify(db, inst, user, values, body.document_id, body.remarks)
    db.commit()
    return {"verification": verification.serialize(vr), **detail(db, inst, user)}


@router.post("/{instrument_id}/observations", status_code=201, summary="Add an officer scrutiny observation")
def add_observation(instrument_id: int, body: ObservationIn, user: User = Depends(require_roles(*OFFICER, *APPROVER)),
                    db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    obs = Observation(instrument_id=inst.id, author_id=user.id, note=body.note,
                      reason_code=body.reason_code.value if body.reason_code else None,
                      visible_to_institution=body.visible_to_institution, created_at=clock.now())
    db.add(obs)
    lifecycle.log_event(db, inst, "observation_added", user, note=body.note)
    db.commit()
    return {"id": obs.id}


@router.post("/{instrument_id}/raise-discrepancy", summary="Return the case to the institution with reasons")
def raise_discrepancy(instrument_id: int, body: DiscrepancyIn, user: User = Depends(require_roles(*OFFICER, *APPROVER)),
                      db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    now = clock.now()
    confirmed = []
    for f in inst.flags:
        if f.id in body.flag_ids and f.status == FlagStatus.OPEN:
            f.status = FlagStatus.CONFIRMED
            f.resolved_by, f.resolution_note = user.id, f"Confirmed in discrepancy: {body.note}"
            confirmed.append(f.title)
    manual = Flag(instrument_id=inst.id, rule_id="MANUAL", code=body.reason_code.value,
                  title=body.reason_code.value.replace("_", " ").title(), severity=Severity.HIGH,
                  status=FlagStatus.CONFIRMED, officer_message=body.note, institution_message=body.note,
                  evidence={"confirmed_flags": confirmed}, fingerprint=f"MANUAL:{now.timestamp()}",
                  is_auto=False, raised_by=user.id, created_at=now)
    db.add(manual)
    db.add(Observation(instrument_id=inst.id, author_id=user.id, reason_code=body.reason_code.value,
                       note=body.note, visible_to_institution=True, created_at=now))
    lifecycle.transition(db, inst, "raise_discrepancy", user, note=body.note,
                         data={"reason_code": body.reason_code.value, "confirmed_flags": confirmed})
    inst.risk_score = rules.compute_risk(inst)
    notifications.notify_institution(
        db, inst.institution_id, f"Discrepancy in FDR {inst.fdr_number}",
        f"Reason: {body.reason_code.value.replace('_', ' ').title()}. {body.note}"
        + (f" Also: {'; '.join(confirmed)}." if confirmed else "") + " Please correct and re-submit.",
        link=f"/instruments/{inst.id}", category="DISCREPANCY", sms=True,
    )
    db.commit()
    return detail(db, inst, user)


@router.post("/{instrument_id}/mark-verified", summary="Officer certifies scrutiny complete (human decision)")
def mark_verified(instrument_id: int, body: ActionNoteIn, user: User = Depends(require_roles(*OFFICER)),
                  db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    undecided = [f for f in inst.flags if f.status == FlagStatus.OPEN and f.severity != Severity.INFO]
    if undecided:
        raise HTTPException(409, {"message": "Decide every open flag first (confirm or dismiss with a reason)",
                                  "open_flags": [{"id": f.id, "title": f.title} for f in undecided]})
    confirmed_hi = [f for f in inst.flags if f.status == FlagStatus.CONFIRMED and f.severity in (Severity.HIGH, Severity.CRITICAL)]
    if confirmed_hi:
        raise HTTPException(409, "Confirmed high-severity discrepancies exist - raise a discrepancy instead")
    if inst.trust_level == TrustLevel.SELF_DECLARED and not (body.note and len(body.note) >= 10):
        raise HTTPException(422, "Record is not bank/officer confirmed. Verify with the bank, or give a justification (>=10 chars) to proceed.")
    lifecycle.transition(db, inst, "mark_verified", user, note=body.note,
                         data={"trust_level": inst.trust_level.value, "override": inst.trust_level == TrustLevel.SELF_DECLARED})
    alerts.resolve_for_instrument(db, inst.id, (AlertType.VERIFICATION_PENDING,), "Verified by officer")
    notifications.notify_role(db, Role.APPROVING_AUTHORITY, "FDR awaiting approval",
                              f"{inst.institution.name}: FDR {inst.fdr_number}", link=f"/instruments/{inst.id}",
                              category="APPROVAL", email=False)
    db.commit()
    return detail(db, inst, user)


@router.post("/{instrument_id}/send-back", summary="Approver sends the case back to scrutiny")
def send_back(instrument_id: int, body: RejectIn, user: User = Depends(require_roles(*APPROVER)), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    lifecycle.transition(db, inst, "send_back", user, note=body.note)
    db.commit()
    return detail(db, inst, user)


@router.post("/{instrument_id}/approve", summary="Approving Authority signs off -> ACTIVE")
def approve(instrument_id: int, body: ActionNoteIn, user: User = Depends(require_roles(*APPROVER)),
            db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    lifecycle.transition(db, inst, "approve", user, note=body.note or "Approved")
    renewals.on_renewal_approved(db, inst, user)
    # place the instrument in the right monitoring state right away (e.g. already inside T-90)
    monitor.check_instrument(db, inst, config_service.all_config(db), clock.today(), monitor._holidays(db))
    notifications.notify_institution(db, inst.institution_id, f"FDR {inst.fdr_number} approved",
                                     f"Your FDR ({inst.ack_number}) is now an active security with AICTE.",
                                     link=f"/instruments/{inst.id}", category="APPROVAL")
    db.commit()
    return detail(db, inst, user)


@router.post("/{instrument_id}/reject", summary="Reject the submission")
def reject(instrument_id: int, body: RejectIn, user: User = Depends(require_roles(*APPROVER)), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    lifecycle.transition(db, inst, "reject", user, note=body.note)
    alerts.resolve_for_instrument(db, inst.id, tuple(AlertType), "Rejected")
    notifications.notify_institution(db, inst.institution_id, f"FDR {inst.fdr_number} rejected", body.note,
                                     link=f"/instruments/{inst.id}", category="APPROVAL")
    db.commit()
    return detail(db, inst, user)


# --------------------------------------------------------------------------- #
# Renewal
# --------------------------------------------------------------------------- #
@router.post("/{instrument_id}/renew", status_code=201,
             summary="Start a renewal / replacement linked to this instrument (returns the new draft)")
def renew(instrument_id: int, body: InstrumentIn, user: User = Depends(require_roles(Role.INSTITUTION)),
          db: Session = Depends(get_db)):
    old = get_instrument(db, instrument_id, user)
    new = renewals.start_renewal(db, old, user, body.model_dump(exclude_unset=True))
    rules.apply(db, new)
    db.commit()
    return detail(db, new, user)


@router.get("/{instrument_id}/timeline", summary="Lifecycle timeline (fdr_events)")
def timeline(instrument_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    return detail(db, inst, user)["timeline"]


@router.get("/{instrument_id}/fields", summary="Declared vs confirmed, per field, with badges")
def field_badges(instrument_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    return {"trust_level": inst.trust_level.value, "fields": fields.field_view(inst)}


@router.post("/{instrument_id}/recheck", summary="Re-run the discrepancy engine")
def recheck(instrument_id: int, user: User = Depends(require_roles(*OFFICER, Role.INSTITUTION)), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    summary = rules.apply(db, inst)
    db.commit()
    return summary
