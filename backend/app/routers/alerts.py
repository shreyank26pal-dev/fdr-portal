from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import AlertStatus, AlertType, Role
from app.models import Alert, Notification, User
from app.schemas import ActionNoteIn, AlertOut, NotificationOut, RejectIn
from app.security import get_current_user
from app.services import alerts, clock

router = APIRouter(tags=["Alerts & notifications"])


@router.get("/alerts", response_model=list[AlertOut], summary="My alert queue (escalation tickets)")
def list_alerts(status: AlertStatus | None = None, alert_type: AlertType | None = None, include_resolved: bool = False,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = alerts.visible_query(user)
    if status:
        q = q.where(Alert.status == status)
    elif not include_resolved:
        q = q.where(Alert.status != AlertStatus.RESOLVED)
    if alert_type:
        q = q.where(Alert.alert_type == alert_type)
    return db.execute(q.order_by(Alert.level.desc(), Alert.created_at)).scalars().all()


def _get(db: Session, alert_id: int, user: User) -> Alert:
    a = db.execute(alerts.visible_query(user).where(Alert.id == alert_id)).scalar()
    if a is None:
        # assignees of earlier levels can still view it
        a = db.get(Alert, alert_id)
        if a is None or (user.role == Role.INSTITUTION and a.institution_id != user.institution_id):
            raise HTTPException(404, "Alert not found")
    return a


@router.get("/alerts/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get(db, alert_id, user)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut,
             summary="Acknowledge (does NOT stop escalation - only resolving does)")
def ack(alert_id: int, body: ActionNoteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == Role.INSTITUTION:
        raise HTTPException(403, "Institutions act on the instrument, not the alert")
    a = alerts.acknowledge(db, _get(db, alert_id, user), user, body.note)
    db.commit()
    return a


@router.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve(alert_id: int, body: RejectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == Role.INSTITUTION:
        raise HTTPException(403, "Institutions act on the instrument, not the alert")
    a = alerts.resolve(db, _get(db, alert_id, user), user, body.note)
    db.commit()
    return a


@router.get("/notifications", response_model=list[NotificationOut], summary="My in-app notifications (bell)")
def my_notifications(unread_only: bool = False, limit: int = 50, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == user.id, Notification.channel == "IN_APP")
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    return db.execute(q.order_by(Notification.id.desc()).limit(limit)).scalars().all()


@router.get("/notifications/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.execute(select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.channel == "IN_APP", Notification.read_at.is_(None))).scalar()
    return {"unread": n}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "Not found")
    n.read_at = clock.now()
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
               .values(read_at=clock.now()))
    db.commit()
    return {"ok": True}
