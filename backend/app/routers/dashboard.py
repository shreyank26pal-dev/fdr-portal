from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import AICTE_ROLES, Role
from app.models import AuditLog, User
from app.routers.common import scope_institution_ids
from app.security import get_current_user, require_roles
from app.services import analytics, audit, clock, reports

router = APIRouter(tags=["Dashboard, reports & audit"])

AICTE = AICTE_ROLES


@router.get("/dashboard/summary", summary="Tiles: active, expiring 30d, unverified, pending refunds, escalations...")
def dash_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analytics.summary(db, scope_institution_ids(db, user))


@router.get("/dashboard/by-bank", summary="Held deposits by bank (chart)")
def dash_by_bank(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analytics.by_bank(db, scope_institution_ids(db, user))


@router.get("/dashboard/by-region", summary="Held deposits by AICTE region (chart)")
def dash_by_region(user: User = Depends(require_roles(*AICTE)), db: Session = Depends(get_db)):
    return analytics.by_region(db, scope_institution_ids(db, user))


@router.get("/dashboard/maturity-projection",
            summary="Financial volume maturing per month / fiscal quarter (workload planning)")
def dash_projection(months: int = Query(12, ge=1, le=36), user: User = Depends(require_roles(*AICTE)),
                    db: Session = Depends(get_db)):
    return analytics.maturity_projection(db, months, scope_institution_ids(db, user))


@router.get("/dashboard/renewal-heatmap",
            summary="Heatmap: which institutions consistently delay renewals (avg days late per fiscal quarter)")
def dash_heatmap(quarters: int = Query(6, ge=1, le=16), user: User = Depends(require_roles(*AICTE)),
                 db: Session = Depends(get_db)):
    data = analytics.renewal_heatmap(db, quarters)
    ids = scope_institution_ids(db, user)
    if ids is not None:
        data["rows"] = [r for r in data["rows"] if r["institution_id"] in ids]
    return data


@router.get("/dashboard/predicted-late-renewals",
            summary="Heuristic early-warning list: upcoming maturities at institutions with a history of delay")
def dash_predicted(horizon_days: int = Query(120, ge=7, le=365), user: User = Depends(require_roles(*AICTE)),
                   db: Session = Depends(get_db)):
    rows = analytics.predicted_late_renewals(db, horizon_days)
    ids = scope_institution_ids(db, user)
    if ids is not None:
        rows = [r for r in rows if r["institution_id"] in ids]
    return {"method": "Heuristic score = late-renewal ratio x 60 + min(avg delay days, 40). Not an ML model.",
            "rows": rows}


@router.get("/dashboard/verification-ageing")
def dash_ageing(user: User = Depends(require_roles(*AICTE)), db: Session = Depends(get_db)):
    return analytics.verification_ageing(db)


# ------------------------------- reports ---------------------------------- #
@router.get("/reports", summary="Available reports")
def list_reports(user: User = Depends(get_current_user)):
    return [{"name": k, "description": v[0], "formats": ["json", "xlsx", "pdf"]} for k, v in reports.REPORTS.items()]


@router.get("/reports/{name}", summary="Run a report: format=json | xlsx | pdf")
def run_report(name: str, format: Literal["json", "xlsx", "pdf"] = "json", days: int = 90,
               institution_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if name not in reports.REPORTS:
        raise HTTPException(404, "Unknown report")
    if user.role == Role.BANK:
        raise HTTPException(403, "Not available for bank users")
    ids = scope_institution_ids(db, user)
    if user.role == Role.INSTITUTION:
        institution_id = user.institution_id
    rep = reports.REPORTS[name][1](db, days=days, institution_id=institution_id, inst_ids=ids)
    audit.record(db, user, "REPORT_EXPORTED", "report", name, after={"format": format, "rows": len(rep.rows)})
    db.commit()
    if format == "json":
        return rep.as_json()
    fname = f"{name}_{clock.today():%Y%m%d}.{format}"
    if format == "xlsx":
        return Response(rep.as_xlsx(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})
    return Response(rep.as_pdf(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# -------------------------------- audit ----------------------------------- #
@router.get("/audit", summary="Browse the hash-chained audit log")
def audit_log(entity_type: str | None = None, entity_id: str | None = None, institution_id: int | None = None,
              action: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, le=500),
              user: User = Depends(require_roles(Role.ADMIN, Role.AUDITOR, Role.APPROVING_AUTHORITY,
                                                 Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER)),
              db: Session = Depends(get_db)):
    q = select(AuditLog)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    if institution_id:
        q = q.where(AuditLog.institution_id == institution_id)
    if action:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))
    ids = scope_institution_ids(db, user)
    if ids is not None:
        q = q.where(AuditLog.institution_id.in_(ids))
    rows = db.execute(q.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return [{"id": r.id, "ts": r.ts, "actor_email": r.actor_email, "actor_role": r.actor_role, "ip": r.ip,
             "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
             "institution_id": r.institution_id, "before": r.before, "after": r.after,
             "prev_hash": r.prev_hash, "hash": r.hash} for r in rows]


@router.get("/audit/verify", summary="Re-compute the whole hash chain; reports the first tampered entry if any")
def audit_verify(user: User = Depends(require_roles(Role.ADMIN, Role.AUDITOR, Role.APPROVING_AUTHORITY)),
                 db: Session = Depends(get_db)):
    return audit.verify_chain(db)


@router.get("/audit/instrument/{instrument_id}", summary="Audit trail of one instrument")
def audit_instrument(instrument_id: int, user: User = Depends(require_roles(*AICTE)), db: Session = Depends(get_db)):
    rows = db.execute(select(AuditLog).where(AuditLog.entity_type == "instrument",
                                             AuditLog.entity_id == str(instrument_id)).order_by(AuditLog.id)).scalars()
    return [{"id": r.id, "ts": r.ts, "actor_email": r.actor_email, "actor_role": r.actor_role, "action": r.action,
             "before": r.before, "after": r.after, "hash": r.hash, "prev_hash": r.prev_hash} for r in rows]
