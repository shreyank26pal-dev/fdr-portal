"""In-app + email + (simulated) SMS notifications.

Every message is stored in `notifications` (one row per channel) so the frontend
can show a bell, and so there is a 'who was told, when' trail.
"""
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import DeliveryStatus, NotificationChannel, Role
from app.models import Institution, Notification, User

log = logging.getLogger("notifications")


def _send_email(to: str, subject: str, body: str) -> tuple[DeliveryStatus, str | None]:
    if not settings.SMTP_HOST:
        return DeliveryStatus.SIMULATED, None
    try:
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as s:
            if settings.SMTP_STARTTLS:
                s.starttls()
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        return DeliveryStatus.SENT, None
    except Exception as exc:  # noqa: BLE001
        log.warning("email to %s failed: %s", to, exc)
        return DeliveryStatus.FAILED, str(exc)


def _send_sms(phone: str, body: str) -> tuple[DeliveryStatus, str | None]:
    # Prototype: SMS gateway is simulated and logged. Plug a real provider here.
    log.info("[SIMULATED SMS] to %s: %s", phone, body[:140])
    return DeliveryStatus.SIMULATED, None


def notify_user(
    db: Session,
    user: User,
    title: str,
    body: str,
    link: str | None = None,
    category: str | None = None,
    email: bool = True,
    sms: bool = False,
) -> None:
    db.add(Notification(
        user_id=user.id, institution_id=user.institution_id, channel=NotificationChannel.IN_APP,
        recipient=user.email, title=title, body=body, link=link, category=category,
        status=DeliveryStatus.SENT,
    ))
    if email and user.email:
        st, err = _send_email(user.email, f"[SecureDeposit] {title}", f"{body}\n\n{settings.FRONTEND_BASE_URL}{link or ''}")
        db.add(Notification(
            user_id=user.id, institution_id=user.institution_id, channel=NotificationChannel.EMAIL,
            recipient=user.email, title=title, body=body, link=link, category=category, status=st, error=err,
        ))
    if sms and user.phone:
        st, err = _send_sms(user.phone, f"{title}: {body}")
        db.add(Notification(
            user_id=user.id, institution_id=user.institution_id, channel=NotificationChannel.SMS,
            recipient=user.phone, title=title, body=body, link=link, category=category, status=st, error=err,
        ))


def notify_institution(
    db: Session, institution_id: int, title: str, body: str, link: str | None = None,
    category: str | None = None, sms: bool = False,
) -> list[str]:
    users = db.execute(
        select(User).where(User.institution_id == institution_id, User.role == Role.INSTITUTION, User.is_active)
    ).scalars().all()
    for u in users:
        notify_user(db, u, title, body, link, category, email=True, sms=sms)
    recipients = [u.email for u in users]
    if not users:
        inst = db.get(Institution, institution_id)
        if inst and inst.email:
            st, err = _send_email(inst.email, f"[SecureDeposit] {title}", body)
            db.add(Notification(institution_id=institution_id, channel=NotificationChannel.EMAIL,
                                recipient=inst.email, title=title, body=body, link=link,
                                category=category, status=st, error=err))
            recipients.append(inst.email)
    return recipients


def notify_role(
    db: Session, role: Role, title: str, body: str, link: str | None = None,
    region: str | None = None, category: str | None = None, email: bool = True,
) -> list[str]:
    q = select(User).where(User.role == role, User.is_active)
    if role == Role.REGIONAL_OFFICER and region:
        q = q.where(User.region == region)
    users = db.execute(q).scalars().all()
    for u in users:
        notify_user(db, u, title, body, link, category, email=email)
    return [u.email for u in users]


def send_external_email(db: Session, to: str, subject: str, body: str, category: str | None = None) -> DeliveryStatus:
    """Email to a non-user (e.g. bank nodal officer)."""
    st, err = _send_email(to, subject, body)
    db.add(Notification(channel=NotificationChannel.EMAIL, recipient=to, title=subject, body=body,
                        category=category, status=st, error=err))
    return st
