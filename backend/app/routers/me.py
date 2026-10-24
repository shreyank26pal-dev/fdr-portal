"""College self-service view: my FDRs, deadlines, 'documents needed' checklist, action strip."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import CLOSED_STATUSES, REFUND_OPEN_STATUSES, FlagStatus, InstrumentStatus as S, Role
from app.models import Instrument, RefundRequest, User
from app.routers.common import list_item
from app.security import require_roles
from app.services import analytics, clock, lifecycle, monitor, refunds, renewals, rules

router = APIRouter(prefix="/me", tags=["Institution self-service"])


@router.get("/overview", summary="Everything a college needs on one screen")
def overview(user: User = Depends(require_roles(Role.INSTITUTION)), db: Session = Depends(get_db)):
    today = clock.today()
    insts = db.execute(select(Instrument).where(Instrument.institution_id == user.institution_id)
                       .order_by(Instrument.maturity_date)).scalars().all()
    lock = renewals.lock_reasons(db, user.institution_id)

    action_strip, checklist, deadlines = [], [], []
    for i in insts:
        if i.status in CLOSED_STATUSES:
            continue
        open_flags = [f for f in i.flags if f.status in (FlagStatus.OPEN, FlagStatus.CONFIRMED)]
        pa = lifecycle.pending_action(i, [f.title for f in open_flags])
        renewal = monitor.pending_renewal(db, i)
        if renewal is not None and i.status in lifecycle.RELEASABLE:
            pa = {"owner": "AICTE", "text": f"Renewal #{renewal.id} submitted ({renewal.status.value})."}
        if pa["owner"] == "INSTITUTION":
            action_strip.append({"instrument_id": i.id, "fdr_number": i.fdr_number, "status": i.status.value,
                                 "text": pa["text"], "due_date": i.maturity_date if i.status in (
                                     S.EXPIRING_SOON, S.ACTION_REQUIRED, S.MATURED, S.OVERDUE) else None})
        items = []
        for t in rules.missing_documents(db, i):
            items.append({"type": "DOCUMENT", "doc_type": t, "label": f"Upload {t.replace('_', ' ').lower()}", "done": False})
        for d in i.documents:
            if not d.is_superseded and d.doc_type.value in ("FDR_SCAN", "LIEN_LETTER", "RENEWAL_FDR"):
                items.append({"type": "DOCUMENT", "doc_type": d.doc_type.value,
                              "label": f"{d.doc_type.value.replace('_', ' ').title()} uploaded", "done": True})
        if i.status in (S.DRAFT, S.DISCREPANCY_RAISED):
            for f in open_flags:
                items.append({"type": "FIX", "label": f.institution_message, "done": False, "rule_id": f.rule_id})
        if i.status in (S.ACTION_REQUIRED, S.MATURED, S.OVERDUE) and renewal is None:
            items.append({"type": "RENEWAL", "label": "Upload renewed / replacement FDR", "done": False})
        if items:
            checklist.append({"instrument_id": i.id, "fdr_number": i.fdr_number, "status": i.status.value, "items": items})
        if i.maturity_date and i.status in lifecycle.RELEASABLE:
            deadlines.append({"instrument_id": i.id, "fdr_number": i.fdr_number, "maturity_date": i.maturity_date,
                              "days_left": (i.maturity_date - today).days, "status": i.status.value,
                              "renewal_due_by": i.maturity_date, "amount": i.amount})

    rrs = db.execute(select(RefundRequest).where(RefundRequest.institution_id == user.institution_id)
                     .order_by(RefundRequest.id.desc())).scalars().all()
    summ = analytics.summary(db, [user.institution_id])["tiles"]
    return {
        "institution": {"id": user.institution.id, "name": user.institution.name, "aicte_id": user.institution.aicte_id,
                        "region": user.institution.region},
        "today": today,
        "locked": bool(lock),
        "lock_reasons": lock,
        "totals": {"held_count": summ["held_total"], "held_amount": summ["held_amount"],
                   "pending_verification": summ["pending_verification"], "action_required": summ["action_required"]},
        "action_required": action_strip,
        "documents_needed": checklist,
        "upcoming_deadlines": sorted(deadlines, key=lambda d: d["maturity_date"])[:10],
        "instruments": [list_item(i) | {"pending_action": lifecycle.pending_action(i)} for i in insts],
        "refunds": [{"id": r.id, "ref_number": r.ref_number, "status": r.status.value, "fdr_number": r.instrument.fdr_number,
                     "open": r.status in REFUND_OPEN_STATUSES, "tracker": refunds.tracker(r)} for r in rrs],
    }
