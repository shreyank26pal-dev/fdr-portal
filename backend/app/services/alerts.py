"""Escalation tickets with a configurable ladder.

An alert starts at the level configured for its type, and if it is not RESOLVED
by `escalate_at` it automatically moves up one level (e.g. Regional Officer ->
Approving Authority -> Bureau Admin/Head). Acknowledging does NOT stop the
clock - only resolving does.
"""
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AlertStatus, AlertType, Role, Severity
from app.models import Alert, Institution, User
from app.services import audit, clock, config_service, notifications


def _ladder(db: Session) -> list[dict[str, Any]]:
    return sorted(config_service.get(db, "escalation_ladder"), key=lambda x: x["level"])


def _step(db: Session, level: int) -> dict[str, Any] | None:
    for s in _ladder(db):
        if s["level"] == level:
            return s
    return None


def _escalate_at(db: Session, level: int):
    step = _step(db, level)
    hours = step.get("escalate_after_hours") if step else None
    return clock.now() + timedelta(hours=hours) if hours else None


def open_alert(
    db: Session, alert_type: AlertType, dedupe_key: str, title: str, message: str, *,
    instrument_id: int | None = None, institution_id: int | None = None, refund_request_id: int | None = None,
    severity: Severity = Severity.MEDIUM, due_date=None,
) -> Alert | None:
    """Create an alert unless one with the same dedupe_key exists. Returns the new alert or None."""
    if db.execute(select(Alert.id).where(Alert.dedupe_key == dedupe_key)).scalar():
        return None
    start = config_service.get(db, "alert_start").get(alert_type.value, {"level": 1, "role": "SCRUTINY_OFFICER"})
    region = None
    if institution_id:
        inst = db.get(Institution, institution_id)
        region = inst.region if inst else None
    now = clock.now()
    alert = Alert(
        alert_type=alert_type, dedupe_key=dedupe_key, title=title, message=message,
        instrument_id=instrument_id, institution_id=institution_id, refund_request_id=refund_request_id,
        region=region, severity=severity, level=start["level"], assigned_role=Role(start["role"]),
        status=AlertStatus.OPEN, due_date=due_date, escalate_at=_escalate_at(db, start["level"]),
        history=[{"at": now.isoformat(), "event": "OPENED", "level": start["level"], "role": start["role"]}],
        created_at=now,
    )
    db.add(alert)
    db.flush()
    _notify_assignees(db, alert, f"New alert: {title}")
    audit.record(db, None, "ALERT_OPENED", "alert", alert.id,
                 after={"type": alert_type.value, "level": alert.level, "role": alert.assigned_role.value,
                        "instrument_id": instrument_id}, institution_id=institution_id)
    return alert


def _notify_assignees(db: Session, alert: Alert, title: str) -> list[str]:
    link = f"/alerts/{alert.id}"
    region = alert.region if alert.assigned_role == Role.REGIONAL_OFFICER else None
    return notifications.notify_role(db, alert.assigned_role, title, alert.message, link=link,
                                     region=region, category="ALERT")


def run_escalations(db: Session) -> list[dict[str, Any]]:
    now = clock.now()
    due = db.execute(
        select(Alert).where(Alert.status != AlertStatus.RESOLVED, Alert.escalate_at.is_not(None), Alert.escalate_at <= now)
    ).scalars().all()
    changes = []
    for a in due:
        nxt = _step(db, a.level + 1)
        if nxt is None:
            a.escalate_at = None
            continue
        old_level, old_role = a.level, a.assigned_role
        a.level = nxt["level"]
        a.assigned_role = Role(nxt["role"])
        a.status = AlertStatus.OPEN
        a.escalate_at = _escalate_at(db, a.level)
        a.history = (a.history or []) + [{
            "at": now.isoformat(), "event": "ESCALATED", "from_level": old_level, "from_role": old_role.value,
            "level": a.level, "role": a.assigned_role.value, "reason": "Not resolved within the configured time",
        }]
        if a.severity in (Severity.LOW, Severity.MEDIUM):
            a.severity = Severity.HIGH
        _notify_assignees(db, a, f"ESCALATED (level {a.level}): {a.title}")
        audit.record(db, None, "ALERT_ESCALATED", "alert", a.id,
                     before={"level": old_level, "role": old_role.value},
                     after={"level": a.level, "role": a.assigned_role.value}, institution_id=a.institution_id)
        changes.append({"alert_id": a.id, "from_level": old_level, "to_level": a.level, "to_role": a.assigned_role.value})
    return changes


def acknowledge(db: Session, alert: Alert, user: User, note: str | None) -> Alert:
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = user.id
    alert.acknowledged_at = clock.now()
    alert.history = (alert.history or []) + [{"at": clock.now().isoformat(), "event": "ACKNOWLEDGED", "by": user.email, "note": note}]
    audit.record(db, user, "ALERT_ACKNOWLEDGED", "alert", alert.id, after={"note": note}, institution_id=alert.institution_id)
    return alert


def resolve(db: Session, alert: Alert, user: User | None, note: str) -> Alert:
    if alert.status == AlertStatus.RESOLVED:
        return alert
    alert.status = AlertStatus.RESOLVED
    alert.resolved_by = user.id if user else None
    alert.resolved_at = clock.now()
    alert.resolution_note = note
    alert.escalate_at = None
    alert.history = (alert.history or []) + [{"at": clock.now().isoformat(), "event": "RESOLVED",
                                               "by": user.email if user else "system", "note": note}]
    audit.record(db, user, "ALERT_RESOLVED", "alert", alert.id, after={"note": note}, institution_id=alert.institution_id)
    return alert


def resolve_for_instrument(db: Session, instrument_id: int, types: tuple[AlertType, ...], note: str) -> int:
    alerts = db.execute(
        select(Alert).where(Alert.instrument_id == instrument_id, Alert.alert_type.in_(types),
                            Alert.status != AlertStatus.RESOLVED)
    ).scalars().all()
    for a in alerts:
        resolve(db, a, None, note)
    return len(alerts)


def visible_query(user: User):
    q = select(Alert)
    if user.role in (Role.ADMIN, Role.AUDITOR):
        return q
    if user.role == Role.REGIONAL_OFFICER:
        return q.where(Alert.assigned_role == Role.REGIONAL_OFFICER, Alert.region == user.region)
    if user.role == Role.INSTITUTION:
        return q.where(Alert.institution_id == user.institution_id)
    return q.where(Alert.assigned_role == user.role)
