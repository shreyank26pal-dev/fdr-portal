"""Risk dashboard + predictive analytics for AICTE officials."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import (
    CLOSED_STATUSES,
    HELD_STATUSES,
    PIPELINE_STATUSES,
    REFUND_OPEN_STATUSES,
    AlertStatus,
    FlagStatus,
    InstrumentStatus as S,
    TrustLevel,
)
from app.models import Alert, Flag, Institution, Instrument, RefundRequest
from app.services import clock, config_service


def fiscal_quarter(d: date) -> tuple[int, int]:
    """Indian FY: Q1 = Apr-Jun. Returns (fy_start_year, quarter)."""
    fy = d.year if d.month >= 4 else d.year - 1
    q = ((d.month - 4) % 12) // 3 + 1
    return fy, q


def fq_label(fy: int, q: int) -> str:
    return f"FY{str(fy)[2:]}-{str(fy + 1)[2:]} Q{q}"


def fq_range(fy: int, q: int) -> tuple[date, date]:
    start_month = 4 + (q - 1) * 3
    y = fy if start_month <= 12 else fy + 1
    m = start_month if start_month <= 12 else start_month - 12
    start = date(y, m, 1)
    end_m, end_y = (m + 3, y) if m + 3 <= 12 else (m + 3 - 12, y + 1)
    return start, date(end_y, end_m, 1) - timedelta(days=1)


def scoped(q, institution_ids: list[int] | None):
    return q.where(Instrument.institution_id.in_(institution_ids)) if institution_ids is not None else q


def summary(db: Session, institution_ids: list[int] | None = None) -> dict[str, Any]:
    today = clock.today()

    def count(*conds) -> int:
        return db.execute(scoped(select(func.count(Instrument.id)).where(*conds), institution_ids)).scalar() or 0

    def total(*conds) -> float:
        v = db.execute(scoped(select(func.coalesce(func.sum(Instrument.amount), 0)).where(*conds), institution_ids)).scalar()
        return float(v or 0)

    by_status = dict(db.execute(scoped(select(Instrument.status, func.count()).group_by(Instrument.status), institution_ids)).all())
    held = Instrument.status.in_(HELD_STATUSES)
    tiles = {
        "active": count(Instrument.status == S.ACTIVE),
        "held_total": count(held),
        "held_amount": total(held),
        "expiring_30_days": count(held, Instrument.maturity_date.between(today, today + timedelta(days=30))),
        "expiring_30_days_amount": total(held, Instrument.maturity_date.between(today, today + timedelta(days=30))),
        "expiring_90_days": count(held, Instrument.maturity_date.between(today, today + timedelta(days=90))),
        "action_required": count(Instrument.status == S.ACTION_REQUIRED),
        "matured_unrenewed": count(Instrument.status.in_([S.MATURED, S.OVERDUE])),
        "overdue": count(Instrument.status == S.OVERDUE),
        "pending_verification": count(Instrument.status.in_([S.SUBMITTED, S.UNDER_SCRUTINY])),
        "awaiting_approval": count(Instrument.status == S.VERIFIED),
        "discrepancies_open": count(Instrument.status == S.DISCREPANCY_RAISED),
        "unverified_held": count(held, Instrument.trust_level == TrustLevel.SELF_DECLARED),
        "renewed": count(Instrument.status == S.RENEWED),
        "released": count(Instrument.status == S.RELEASED),
        "high_risk": count(Instrument.risk_score >= 50, Instrument.status.not_in(CLOSED_STATUSES)),
    }
    rq = select(func.count(RefundRequest.id)).where(RefundRequest.status.in_(REFUND_OPEN_STATUSES))
    if institution_ids is not None:
        rq = rq.where(RefundRequest.institution_id.in_(institution_ids))
    tiles["refunds_pending"] = db.execute(rq).scalar() or 0
    aq = select(func.count(Alert.id)).where(Alert.status != AlertStatus.RESOLVED, Alert.level >= 2)
    if institution_ids is not None:
        aq = aq.where(Alert.institution_id.in_(institution_ids))
    tiles["escalated_alerts"] = db.execute(aq).scalar() or 0
    fq = select(func.count(Flag.id)).join(Instrument).where(Flag.status == FlagStatus.OPEN)
    tiles["open_flags"] = db.execute(scoped(fq, institution_ids)).scalar() or 0
    return {"as_of": today, "tiles": tiles, "by_status": {k.value: v for k, v in by_status.items()}}


def by_bank(db: Session, institution_ids: list[int] | None = None) -> list[dict[str, Any]]:
    q = scoped(select(Instrument.bank_name, func.count(Instrument.id), func.coalesce(func.sum(Instrument.amount), 0))
               .where(Instrument.status.in_(HELD_STATUSES)).group_by(Instrument.bank_name), institution_ids)
    return sorted([{"bank": b or "Unknown", "count": c, "amount": float(a)} for b, c, a in db.execute(q).all()],
                  key=lambda r: -r["amount"])


def by_region(db: Session, institution_ids: list[int] | None = None) -> list[dict[str, Any]]:
    q = scoped(select(Institution.region, func.count(Instrument.id), func.coalesce(func.sum(Instrument.amount), 0))
               .join(Institution, Institution.id == Instrument.institution_id)
               .where(Instrument.status.in_(HELD_STATUSES)).group_by(Institution.region), institution_ids)
    return sorted([{"region": r, "count": c, "amount": float(a)} for r, c, a in db.execute(q).all()],
                  key=lambda r: -r["amount"])


def maturity_projection(db: Session, months: int = 12, institution_ids: list[int] | None = None) -> dict[str, Any]:
    """Financial volume maturing per month and per fiscal quarter (workload planning)."""
    today = clock.today()
    end = today + timedelta(days=months * 31)
    q = scoped(select(Instrument.maturity_date, Instrument.amount).where(
        Instrument.status.in_(HELD_STATUSES), Instrument.maturity_date.between(today, end)), institution_ids)
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "amount": 0.0})
    quarterly: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for d, amt in db.execute(q).all():
        mk = d.strftime("%Y-%m")
        monthly[mk]["count"] += 1
        monthly[mk]["amount"] += float(amt or 0)
        qk = fq_label(*fiscal_quarter(d))
        quarterly[qk]["count"] += 1
        quarterly[qk]["amount"] += float(amt or 0)
    cur_fy, cur_q = fiscal_quarter(today)
    cq_start, cq_end = fq_range(cur_fy, cur_q)
    cur = db.execute(scoped(select(func.count(Instrument.id), func.coalesce(func.sum(Instrument.amount), 0)).where(
        Instrument.status.in_(HELD_STATUSES), Instrument.maturity_date.between(today, cq_end)), institution_ids)).one()
    return {
        "current_fiscal_quarter": {"label": fq_label(cur_fy, cur_q), "from": cq_start, "to": cq_end,
                                   "remaining_count": cur[0], "remaining_amount": float(cur[1])},
        "monthly": [{"month": k, **v} for k, v in sorted(monthly.items())],
        "quarterly": [{"quarter": k, **v} for k, v in sorted(quarterly.items())],
    }


def _renewal_delays(db: Session) -> list[dict[str, Any]]:
    """For each renewal event: how many days after the T-N deadline the renewal was submitted.

    Also counts currently overdue / action-required instruments as live delays.
    """
    action_days = int(config_service.get(db, "action_required_days_before"))
    today = clock.today()
    out = []
    renewals = db.execute(select(Instrument).where(Instrument.replaces_instrument_id.is_not(None),
                                                   Instrument.submitted_at.is_not(None))).scalars().all()
    for new in renewals:
        old = db.get(Instrument, new.replaces_instrument_id)
        if not old or not old.maturity_date:
            continue
        deadline = old.maturity_date - timedelta(days=action_days)
        delay = (new.submitted_at.date() - deadline).days
        out.append({"institution_id": old.institution_id, "maturity_date": old.maturity_date,
                    "delay_days": max(0, delay), "late": delay > 0, "live": False})
    live = db.execute(select(Instrument).where(Instrument.status.in_([S.ACTION_REQUIRED, S.MATURED, S.OVERDUE]))).scalars()
    for inst in live:
        from app.services.monitor import pending_renewal

        if pending_renewal(db, inst) is not None:
            continue
        deadline = inst.maturity_date - timedelta(days=action_days)
        delay = (today - deadline).days
        if delay > 0:
            out.append({"institution_id": inst.institution_id, "maturity_date": inst.maturity_date,
                        "delay_days": delay, "late": True, "live": True})
    return out


def renewal_heatmap(db: Session, quarters: int = 6) -> dict[str, Any]:
    """Institutions x fiscal quarters -> average renewal delay (days). Darker = consistently late."""
    delays = _renewal_delays(db)
    today = clock.today()
    fy, q = fiscal_quarter(today)
    cols = []
    for _ in range(quarters):
        cols.append((fy, q))
        q -= 1
        if q == 0:
            fy, q = fy - 1, 4
    cols.reverse()
    col_labels = [fq_label(*c) for c in cols]
    cells: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for d in delays:
        lbl = fq_label(*fiscal_quarter(d["maturity_date"]))
        if lbl in col_labels:
            cells[d["institution_id"]][lbl].append(d["delay_days"])
    rows = []
    for inst_id, per_q in cells.items():
        inst = db.get(Institution, inst_id)
        all_delays = [x for v in per_q.values() for x in v]
        late = sum(1 for x in all_delays if x > 0)
        rows.append({
            "institution_id": inst_id, "aicte_id": inst.aicte_id, "name": inst.name, "region": inst.region,
            "cells": {lbl: (round(sum(per_q[lbl]) / len(per_q[lbl]), 1) if per_q.get(lbl) else None) for lbl in col_labels},
            "late_renewals": late, "total_renewals": len(all_delays),
            "avg_delay_days": round(sum(all_delays) / len(all_delays), 1) if all_delays else 0,
        })
    rows.sort(key=lambda r: (-r["late_renewals"], -r["avg_delay_days"]))
    return {"quarters": col_labels, "rows": rows,
            "legend": "Cell = average days the renewal came after the T-30 deadline (0 = on time, null = no renewal due)."}


def predicted_late_renewals(db: Session, horizon_days: int = 120) -> list[dict[str, Any]]:
    """Heuristic (clearly labelled, not ML): institutions with a history of late renewals that have
    FDRs maturing soon. Score = late ratio * 60 + min(avg delay, 40)."""
    delays = _renewal_delays(db)
    hist: dict[int, list[int]] = defaultdict(list)
    for d in delays:
        hist[d["institution_id"]].append(d["delay_days"])
    today = clock.today()
    upcoming = db.execute(select(Instrument).where(
        Instrument.status.in_(HELD_STATUSES), Instrument.maturity_date.between(today, today + timedelta(days=horizon_days))
    ).order_by(Instrument.maturity_date)).scalars().all()
    out = []
    for inst in upcoming:
        h = hist.get(inst.institution_id, [])
        if not h:
            continue
        late_ratio = sum(1 for x in h if x > 0) / len(h)
        avg = sum(h) / len(h)
        score = round(late_ratio * 60 + min(avg, 40))
        if score < 20:
            continue
        out.append({
            "instrument_id": inst.id, "fdr_number": inst.fdr_number, "institution_id": inst.institution_id,
            "institution": inst.institution.name, "maturity_date": inst.maturity_date,
            "amount": float(inst.amount or 0), "risk_score": score,
            "basis": f"{sum(1 for x in h if x > 0)}/{len(h)} past renewals late, avg {avg:.0f} days",
        })
    return sorted(out, key=lambda r: -r["risk_score"])


def verification_ageing(db: Session) -> list[dict[str, Any]]:
    now = clock.now()
    buckets = {"0-3 days": 0, "4-7 days": 0, "8-15 days": 0, "15+ days": 0}
    for (sub,) in db.execute(select(Instrument.submitted_at).where(Instrument.status.in_(PIPELINE_STATUSES))).all():
        if not sub:
            continue
        d = (now - sub).days
        k = "0-3 days" if d <= 3 else "4-7 days" if d <= 7 else "8-15 days" if d <= 15 else "15+ days"
        buckets[k] += 1
    return [{"bucket": k, "count": v} for k, v in buckets.items()]


def to_float(v: Any) -> float:
    return float(v) if isinstance(v, (Decimal, int, float)) else 0.0
