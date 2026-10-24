"""Tamper-evident, hash-chained audit log.

Every entry stores the SHA-256 of the previous entry. hash = SHA256(prev_hash || canonical_json(entry)).
Editing or deleting any historical row breaks every hash after it, and
`verify_chain()` pinpoints the first broken link.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.context import request_ip
from app.database import is_postgres
from app.models import AuditLog, User
from app.services import clock

GENESIS = "0" * 64
_LOCK_KEY = 7_420_265  # advisory lock id, keeps the chain linear under concurrency


def _clean(value: Any) -> Any:
    """Make a value JSON-stable (Decimals, dates, enums -> str)."""
    if value is None:
        return None
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _canonical(entry: dict[str, Any]) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str)


def _entry_dict(row: AuditLog) -> dict[str, Any]:
    dt = row.ts if row.ts.tzinfo else row.ts.replace(tzinfo=timezone.utc)
    ts = dt.astimezone(timezone.utc).isoformat(timespec="microseconds")
    return {
        "ts": ts,
        "actor_id": row.actor_id,
        "actor_email": row.actor_email,
        "actor_role": row.actor_role,
        "ip": row.ip,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "institution_id": row.institution_id,
        "before": row.before,
        "after": row.after,
    }


def compute_hash(prev_hash: str, entry: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(entry)).encode("utf-8")).hexdigest()


def record(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    before: Any = None,
    after: Any = None,
    institution_id: int | None = None,
) -> AuditLog:
    """Append one entry to the chain. Caller commits."""
    if is_postgres():
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
    db.flush()
    prev = db.execute(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)).scalar()
    prev_hash = prev or GENESIS

    ts: datetime = clock.now()
    row = AuditLog(
        ts=ts,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else "system",
        actor_role=(actor.role.value if actor else "SYSTEM"),
        ip=request_ip.get(),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        institution_id=institution_id,
        before=_clean(before),
        after=_clean(after),
        prev_hash=prev_hash,
        hash="",
    )
    row.hash = compute_hash(prev_hash, _entry_dict(row))
    db.add(row)
    db.flush()
    return row


def verify_chain(db: Session, limit: int | None = None) -> dict[str, Any]:
    """Re-compute every hash. Returns first broken link if any."""
    prev_hash = GENESIS
    checked = 0
    q = select(AuditLog).order_by(AuditLog.id)
    for row in db.execute(q).scalars().yield_per(500):
        checked += 1
        if row.prev_hash != prev_hash:
            return {
                "valid": False,
                "checked": checked,
                "broken_at_id": row.id,
                "reason": "prev_hash does not match the hash of the previous entry (row deleted or re-ordered)",
            }
        expected = compute_hash(prev_hash, _entry_dict(row))
        if expected != row.hash:
            return {
                "valid": False,
                "checked": checked,
                "broken_at_id": row.id,
                "reason": "entry content was modified after it was written",
                "expected_hash": expected,
                "stored_hash": row.hash,
            }
        prev_hash = row.hash
        if limit and checked >= limit:
            break
    return {"valid": True, "checked": checked, "head_hash": prev_hash}


def snapshot(obj: Any, fields: list[str]) -> dict[str, Any]:
    return {f: getattr(obj, f, None) for f in fields}
