"""Renewal / replacement chaining and the institution 'action required' lock."""
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AlertType, InstrumentStatus as S
from app.models import Instrument, User
from app.services import alerts, config_service, fields, lifecycle, monitor

LOCKING = (S.ACTION_REQUIRED, S.MATURED, S.OVERDUE)


def lock_reasons(db: Session, institution_id: int) -> list[dict[str, Any]]:
    """Instruments that lock the institution until renewal proof is uploaded."""
    if not config_service.get(db, "lock_institution_on_action_required"):
        return []
    rows = db.execute(
        select(Instrument).where(Instrument.institution_id == institution_id, Instrument.status.in_(LOCKING))
    ).scalars().all()
    out = []
    for inst in rows:
        if monitor.pending_renewal(db, inst) is None:
            out.append({
                "instrument_id": inst.id, "fdr_number": inst.fdr_number, "status": inst.status.value,
                "maturity_date": inst.maturity_date,
                "message": f"Upload renewal for FDR {inst.fdr_number} (matures {inst.maturity_date:%d-%m-%Y}).",
            })
    return out


def ensure_not_locked(db: Session, institution_id: int, allow_instrument_id: int | None = None) -> None:
    reasons = [r for r in lock_reasons(db, institution_id) if r["instrument_id"] != allow_instrument_id]
    if reasons:
        raise HTTPException(
            status_code=423,
            detail={"message": "Your institution has FDRs awaiting renewal. Upload renewal proof first.",
                    "pending_renewals": [{k: (str(v) if k == "maturity_date" else v) for k, v in r.items()} for r in reasons]},
        )


def start_renewal(db: Session, old: Instrument, user: User, data: dict[str, Any]) -> Instrument:
    if old.status not in lifecycle.RELEASABLE:
        raise HTTPException(409, f"Cannot renew an instrument in status {old.status.value}")
    existing = db.execute(
        select(Instrument).where(Instrument.replaces_instrument_id == old.id, Instrument.status != S.REJECTED)
    ).scalar()
    if existing:
        raise HTTPException(409, f"A renewal (#{existing.id}) already exists for this instrument")
    new = Instrument(
        institution_id=old.institution_id, replaces_instrument_id=old.id, purpose=old.purpose,
        bank_name=data.get("bank_name") or old.bank_name, branch=data.get("branch") or old.branch,
        ifsc=(data.get("ifsc") or old.ifsc), depositor_name=data.get("depositor_name") or old.depositor_name,
        fdr_number=data.get("fdr_number"), amount=data.get("amount"), issue_date=data.get("issue_date"),
        maturity_date=data.get("maturity_date"), lien_marked=bool(data.get("lien_marked", False)),
        lien_in_favour_of=data.get("lien_in_favour_of"), status=S.DRAFT, created_by=user.id,
    )
    from app.services.rules import resolve_bank

    bank = resolve_bank(db, new.bank_name, new.ifsc)
    new.bank_id = bank.id if bank else None
    db.add(new)
    db.flush()
    fields.sync_declared(db, new)
    lifecycle.log_event(db, new, "created_as_renewal", user, note=f"Renewal of instrument #{old.id}",
                        data={"replaces_instrument_id": old.id})
    lifecycle.log_event(db, old, "renewal_started", user, note=f"Renewal draft #{new.id} created",
                        data={"renewal_instrument_id": new.id})
    return new


def on_renewal_submitted(db: Session, new: Instrument) -> None:
    if not new.replaces_instrument_id:
        return
    old = db.get(Instrument, new.replaces_instrument_id)
    alerts.resolve_for_instrument(db, old.id, (AlertType.ACTION_REQUIRED, AlertType.OVERDUE),
                                  f"Renewal proof submitted (instrument #{new.id})")
    lifecycle.log_event(db, old, "renewal_submitted", None, note=f"Renewal #{new.id} submitted - lock lifted",
                        data={"renewal_instrument_id": new.id})


def on_renewal_approved(db: Session, new: Instrument, actor: User) -> None:
    if not new.replaces_instrument_id:
        return
    old = db.get(Instrument, new.replaces_instrument_id)
    if old.status in lifecycle.RELEASABLE:
        lifecycle.transition(db, old, "mark_renewed", actor, note=f"Replaced by instrument #{new.id}",
                             data={"renewed_by_instrument_id": new.id})
    alerts.resolve_for_instrument(db, old.id, tuple(AlertType), f"Renewed by instrument #{new.id}")


def lineage(db: Session, inst: Instrument) -> list[Instrument]:
    """Full renewal chain, oldest first (one unbroken security history per institution)."""
    root = inst
    while root.replaces_instrument_id:
        root = db.get(Instrument, root.replaces_instrument_id)
    chain = [root]
    cur = root
    while True:
        nxt = db.execute(select(Instrument).where(Instrument.replaces_instrument_id == cur.id)
                         .order_by(Instrument.id.desc())).scalar()
        if nxt is None:
            break
        chain.append(nxt)
        cur = nxt
    return chain
