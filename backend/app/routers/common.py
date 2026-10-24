"""Shared helpers for routers: loading with access checks, serialization, scoping."""
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import FlagStatus, Role
from app.models import Institution, Instrument, Observation, User, VerificationRequest
from app.schemas import DocumentOut, EventOut, FlagOut, InstrumentListItem
from app.security import ensure_can_view
from app.services import clock, fields, lifecycle, monitor, renewals, rules


def get_instrument(db: Session, instrument_id: int, user: User) -> Instrument:
    inst = db.get(Instrument, instrument_id)
    if inst is None:
        raise HTTPException(404, "Instrument not found")
    ensure_can_view(user, inst)
    return inst


def scope_institution_ids(db: Session, user: User) -> list[int] | None:
    """None = all institutions."""
    if user.role == Role.INSTITUTION:
        return [user.institution_id] if user.institution_id else []
    if user.role == Role.REGIONAL_OFFICER:
        return list(db.execute(select(Institution.id).where(Institution.region == user.region)).scalars())
    if user.role == Role.BANK:
        ids = db.execute(select(Instrument.institution_id).where(Instrument.bank_id == user.bank_id).distinct()).scalars()
        return list(ids)
    return None


def list_item(inst: Instrument) -> dict[str, Any]:
    d = InstrumentListItem.model_validate(inst).model_dump()
    d["institution_name"] = inst.institution.name if inst.institution else None
    d["institution_aicte_id"] = inst.institution.aicte_id if inst.institution else None
    d["region"] = inst.institution.region if inst.institution else None
    d["days_to_maturity"] = (inst.maturity_date - clock.today()).days if inst.maturity_date else None
    d["open_flags"] = sum(1 for f in inst.flags if f.status in (FlagStatus.OPEN, FlagStatus.CONFIRMED))
    d["status_label"] = lifecycle.STATUS_LABEL[inst.status]
    return d


def flag_view(f, user: User) -> dict[str, Any]:
    d = FlagOut.model_validate(f).model_dump()
    if user.role == Role.INSTITUTION:
        # institutions see plain language only, not internal evidence / other institutions' ids
        d.pop("officer_message", None)
        d.pop("evidence", None)
        d["message"] = f.institution_message
    return d


def detail(db: Session, inst: Instrument, user: User) -> dict[str, Any]:
    is_inst = user.role == Role.INSTITUTION
    flags = [flag_view(f, user) for f in inst.flags if not (is_inst and f.status == FlagStatus.DISMISSED)]
    open_titles = [f.title for f in inst.flags if f.status in (FlagStatus.OPEN, FlagStatus.CONFIRMED)]
    obs_q = select(Observation).where(Observation.instrument_id == inst.id).order_by(Observation.id)
    if is_inst:
        obs_q = obs_q.where(Observation.visible_to_institution.is_(True))
    observations = [{"id": o.id, "note": o.note, "reason_code": o.reason_code, "created_at": o.created_at,
                     "visible_to_institution": o.visible_to_institution} for o in db.execute(obs_q).scalars()]
    renewal = monitor.pending_renewal(db, inst)
    action = lifecycle.pending_action(inst, open_titles)
    if renewal is not None and inst.status in lifecycle.RELEASABLE:
        action = {"owner": "AICTE", "text": f"Renewal #{renewal.id} submitted ({renewal.status.value}). Lock lifted."}
    vreqs = db.execute(select(VerificationRequest).where(VerificationRequest.instrument_id == inst.id)
                       .order_by(VerificationRequest.id.desc())).scalars().all()
    return {
        "instrument": list_item(inst),
        "institution": {"id": inst.institution.id, "aicte_id": inst.institution.aicte_id,
                        "name": inst.institution.name, "region": inst.institution.region,
                        "state": inst.institution.state},
        "fields": fields.field_view(inst),
        "pending_action": action,
        "allowed_actions": lifecycle.allowed_actions(user, inst),
        "flags": flags,
        "observations": observations,
        "documents": [DocumentOut.model_validate(d).model_dump() for d in inst.documents],
        "missing_documents": rules.missing_documents(db, inst),
        "timeline": [EventOut.model_validate(e).model_dump() for e in inst.events],
        "verification_requests": [
            {"id": v.id, "channel": v.channel.value, "status": v.status.value,
             "result": v.result.value if v.result else None, "source_name": v.source_name,
             "is_simulated": v.is_simulated, "requested_at": v.requested_at, "responded_at": v.responded_at,
             **({} if is_inst else {"comparison": v.comparison, "endpoint": v.endpoint})}
            for v in vreqs
        ],
        "lineage": [{"id": i.id, "fdr_number": i.fdr_number, "status": i.status.value, "amount": i.amount,
                     "issue_date": i.issue_date, "maturity_date": i.maturity_date, "ack_number": i.ack_number}
                    for i in renewals.lineage(db, inst)],
        "pending_renewal_id": renewal.id if renewal else None,
    }
