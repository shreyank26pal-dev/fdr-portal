"""Automated validity & maturity state machine + reminders + SLA alerts + continuous re-verification.

Runs daily (00:30 IST) and escalations hourly. In DEMO_MODE the admin can
advance the clock and run these on demand.
"""
import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import (
    MONITORED_STATUSES,
    REFUND_OPEN_STATUSES,
    AlertType,
    InstrumentStatus as S,
    Role,
    Severity,
    VerificationStatus,
)
from app.models import Bank, FdrEvent, Holiday, Instrument, RefundRequest, ReminderLog
from app.services import alerts, clock, config_service, lifecycle, notifications

log = logging.getLogger("monitor")

RANK = {S.ACTIVE: 0, S.EXPIRING_SOON: 1, S.ACTION_REQUIRED: 2, S.MATURED: 3, S.OVERDUE: 4}


def _holidays(db: Session) -> set[date]:
    return set(db.execute(select(Holiday.day)).scalars().all())


def working_day_on_or_before(d: date, holidays: set[date]) -> date:
    """Holiday/weekend aware: a reminder never lands on a day nobody can act."""
    while d.weekday() >= 5 or d in holidays:
        d -= timedelta(days=1)
    return d


def pending_renewal(db: Session, inst: Instrument) -> Instrument | None:
    return db.execute(
        select(Instrument).where(
            Instrument.replaces_instrument_id == inst.id,
            Instrument.status.not_in([S.DRAFT, S.REJECTED]),
        )
    ).scalar()


def _fmt(d: date | None) -> str:
    return d.strftime("%d-%m-%Y") if d else "-"


def _target_status(days_left: int, cfg: dict[str, Any], renewal: bool) -> S:
    grace = int(cfg["overdue_grace_days"])
    if days_left <= -grace:
        t = S.OVERDUE
    elif days_left <= 0:
        t = S.MATURED
    elif days_left <= int(cfg["action_required_days_before"]):
        t = S.ACTION_REQUIRED
    elif days_left <= int(cfg["expiring_soon_window_days"]):
        t = S.EXPIRING_SOON
    else:
        t = S.ACTIVE
    if renewal:  # renewal already submitted: no lock / no overdue penalty while it is scrutinised
        if t == S.ACTION_REQUIRED:
            t = S.EXPIRING_SOON
        elif t == S.OVERDUE:
            t = S.MATURED
    return t


def _amount(inst: Instrument) -> str:
    return f"Rs {inst.amount:,.0f}" if inst.amount is not None else "Rs -"


def check_instrument(db: Session, inst: Instrument, cfg: dict[str, Any], today: date, holidays: set[date]) -> dict[str, Any]:
    out: dict[str, Any] = {"id": inst.id}
    if not inst.maturity_date:
        return out
    days_left = (inst.maturity_date - today).days
    renewal = pending_renewal(db, inst)
    target = _target_status(days_left, cfg, renewal is not None)
    name = inst.institution.name if inst.institution else f"Institution {inst.institution_id}"
    label = f"FDR {inst.fdr_number} ({inst.bank_name}, {_amount(inst)})"

    if RANK[target] > RANK.get(inst.status, 0):
        old = inst.status
        lifecycle.transition(db, inst, "monitor", None, to_status=target,
                             note=f"Automatic: {days_left} days to maturity", data={"days_left": days_left})
        out["transition"] = f"{old.value}->{target.value}"
        if target == S.ACTION_REQUIRED:
            alerts.open_alert(
                db, AlertType.ACTION_REQUIRED, f"ACTION_REQUIRED:{inst.id}",
                f"Renewal due: {name}",
                f"{label} of {name} matures on {_fmt(inst.maturity_date)} and no renewal proof has been uploaded.",
                instrument_id=inst.id, institution_id=inst.institution_id, severity=Severity.MEDIUM,
                due_date=inst.maturity_date,
            )
            notifications.notify_institution(
                db, inst.institution_id, "ACTION REQUIRED: upload renewed FDR",
                f"{label} matures on {_fmt(inst.maturity_date)}. Upload the renewed / replacement FDR. "
                f"New submissions on the portal are locked until you do.",
                link=f"/instruments/{inst.id}", category="ACTION_REQUIRED", sms=True,
            )
        elif target == S.MATURED:
            notifications.notify_institution(
                db, inst.institution_id, "FDR matured",
                f"{label} matured on {_fmt(inst.maturity_date)}." + ("" if renewal else " Upload renewal proof immediately."),
                link=f"/instruments/{inst.id}", category="MATURITY", sms=True,
            )
        elif target == S.OVERDUE:
            alerts.open_alert(
                db, AlertType.OVERDUE, f"OVERDUE:{inst.id}", f"Overdue security: {name}",
                f"{label} of {name} matured on {_fmt(inst.maturity_date)}; no renewal after "
                f"{cfg['overdue_grace_days']} days grace. AICTE security may be lapsed.",
                instrument_id=inst.id, institution_id=inst.institution_id, severity=Severity.HIGH,
                due_date=inst.maturity_date,
            )

    # ----- reminder ladder (most recent due offset only; never re-sent) -----
    if renewal is None:
        offsets = sorted(int(o) for o in cfg["reminder_offsets_days"])
        due = [o for o in offsets if today >= working_day_on_or_before(inst.maturity_date - timedelta(days=o), holidays)]
        if due:
            o = min(due)
            exists = db.execute(select(ReminderLog.id).where(ReminderLog.instrument_id == inst.id,
                                                             ReminderLog.offset_days == o)).scalar()
            if not exists:
                when = f"in {o} days" if o > 0 else ("today" if o == 0 else f"{-o} days ago")
                title = f"T{'-' if o >= 0 else '+'}{abs(o)} reminder: FDR matures {when}"
                body = f"{label} of {name} matures on {_fmt(inst.maturity_date)} ({when})."
                rec = notifications.notify_institution(db, inst.institution_id, title, body,
                                                       link=f"/instruments/{inst.id}", category="REMINDER",
                                                       sms=o <= 7)
                region = inst.institution.region if inst.institution else None
                rec += notifications.notify_role(db, Role.REGIONAL_OFFICER, f"[Copy] {title}", body,
                                                 link=f"/instruments/{inst.id}", region=region,
                                                 category="REMINDER", email=False)
                db.add(ReminderLog(instrument_id=inst.id, offset_days=o,
                                   scheduled_for=inst.maturity_date - timedelta(days=o), recipients=rec,
                                   sent_at=clock.now()))
                lifecycle.log_event(db, inst, "reminder_sent", None, note=title,
                                    data={"offset_days": o, "recipients": rec})
                out["reminder"] = o
    return out


def run_daily(db: Session) -> dict[str, Any]:
    cfg = config_service.all_config(db)
    today = clock.today()
    holidays = _holidays(db)
    summary: dict[str, Any] = {"date": today.isoformat(), "transitions": [], "reminders": 0, "alerts_opened": 0}

    insts = db.execute(select(Instrument).where(Instrument.status.in_(MONITORED_STATUSES))).scalars().all()
    for inst in insts:
        r = check_instrument(db, inst, cfg, today, holidays)
        if "transition" in r:
            summary["transitions"].append({"instrument_id": inst.id, "change": r["transition"]})
        if "reminder" in r:
            summary["reminders"] += 1

    now = clock.now()
    # ----- verification SLA -----
    sla = timedelta(hours=int(cfg["verification_sla_hours"]))
    pending = db.execute(select(Instrument).where(Instrument.status.in_([S.SUBMITTED, S.UNDER_SCRUTINY]))).scalars().all()
    for inst in pending:
        if inst.submitted_at and inst.submitted_at + sla <= now:
            a = alerts.open_alert(
                db, AlertType.VERIFICATION_PENDING, f"VERIFICATION_PENDING:{inst.id}:{inst.submitted_at:%Y%m%d%H%M}",
                f"Verification pending > {cfg['verification_sla_hours']}h",
                f"FDR {inst.fdr_number} ({inst.ack_number}) submitted on {inst.submitted_at:%d-%m-%Y} is not yet verified.",
                instrument_id=inst.id, institution_id=inst.institution_id,
            )
            summary["alerts_opened"] += bool(a)

    # ----- institution not answering a discrepancy -----
    disc_days = int(cfg["discrepancy_response_days"])
    for inst in db.execute(select(Instrument).where(Instrument.status == S.DISCREPANCY_RAISED)).scalars():
        last = db.execute(select(FdrEvent).where(FdrEvent.instrument_id == inst.id,
                                                 FdrEvent.to_status == S.DISCREPANCY_RAISED.value)
                          .order_by(FdrEvent.id.desc()).limit(1)).scalar()
        if last and last.created_at + timedelta(days=disc_days) <= now:
            a = alerts.open_alert(
                db, AlertType.DISCREPANCY_PENDING, f"DISCREPANCY_PENDING:{inst.id}:{last.id}",
                "Institution has not answered a discrepancy",
                f"Discrepancy on FDR {inst.fdr_number} raised on {last.created_at:%d-%m-%Y} is unanswered for {disc_days}+ days.",
                instrument_id=inst.id, institution_id=inst.institution_id,
            )
            summary["alerts_opened"] += bool(a)

    # ----- refund SLA -----
    rsla = timedelta(hours=int(cfg["refund_sla_hours"]))
    for rr in db.execute(select(RefundRequest).where(RefundRequest.status.in_(REFUND_OPEN_STATUSES))).scalars():
        if rr.created_at + rsla <= now:
            a = alerts.open_alert(
                db, AlertType.REFUND_PENDING, f"REFUND_PENDING:{rr.id}",
                f"Release request {rr.ref_number} pending",
                f"Release request {rr.ref_number} raised on {rr.created_at:%d-%m-%Y} is still {rr.status.value}.",
                instrument_id=rr.instrument_id, institution_id=rr.institution_id, refund_request_id=rr.id,
            )
            summary["alerts_opened"] += bool(a)
    db.flush()
    return summary


def run_reverification(db: Session, force: bool = False) -> dict[str, Any]:
    """Continuous re-verification of held FDRs against the bank (catches premature encashment)."""
    from app.services import verification

    interval = timedelta(days=int(config_service.get(db, "reverification_interval_days")))
    now = clock.now()
    held = db.execute(
        select(Instrument).join(Bank, Instrument.bank_id == Bank.id).where(
            Instrument.status.in_(MONITORED_STATUSES), Bank.api_enabled.is_(True), Bank.api_available.is_(True),
            Instrument.verification_status == VerificationStatus.VERIFIED,
        )
    ).scalars().all()
    checked, changed = 0, []
    for inst in held:
        if not force and inst.last_bank_check_at and inst.last_bank_check_at + interval > now:
            continue
        checked += 1
        vr = verification.verify_via_api(db, inst, None, auto_fallback=False)
        if vr.result != VerificationStatus.VERIFIED:
            bank_status = (vr.response_payload or {}).get("bank_status")
            alerts.open_alert(
                db, AlertType.BANK_STATUS_CHANGED, f"BANK_STATUS_CHANGED:{inst.id}:{vr.id}",
                f"Bank record changed for FDR {inst.fdr_number}",
                f"Periodic re-verification of {inst.fdr_number} ({inst.institution.name}) returned "
                f"{vr.result.value if vr.result else '-'}{f' / bank status {bank_status}' if bank_status else ''}. "
                f"The security may have been encashed or the lien removed.",
                instrument_id=inst.id, institution_id=inst.institution_id, severity=Severity.CRITICAL,
            )
            changed.append({"instrument_id": inst.id, "result": vr.result.value if vr.result else None,
                            "bank_status": bank_status})
    return {"checked": checked, "changed": changed}


def run_all(db: Session, reverify_force: bool = False) -> dict[str, Any]:
    daily = run_daily(db)
    rever = run_reverification(db, force=reverify_force)
    esc = alerts.run_escalations(db)
    db.commit()
    return {"daily": daily, "reverification": rever, "escalations": esc}


# --------------------------------------------------------------------------- #
# APScheduler wiring
# --------------------------------------------------------------------------- #
_scheduler = None


def start_scheduler() -> None:
    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.config import settings
    from app.database import SessionLocal

    def _daily():
        with SessionLocal() as db:
            run_daily(db)
            run_reverification(db)
            db.commit()

    def _escalate():
        with SessionLocal() as db:
            alerts.run_escalations(db)
            db.commit()

    _scheduler = BackgroundScheduler(timezone=settings.SCHEDULER_TZ)
    _scheduler.add_job(_daily, "cron", hour=0, minute=30, id="daily_monitor", replace_existing=True)
    _scheduler.add_job(_escalate, "interval", hours=1, id="escalations", replace_existing=True)
    _scheduler.start()
    log.info("scheduler started")


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
