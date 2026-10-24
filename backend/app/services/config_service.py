"""Admin-configurable business rules. Nothing below is hard-coded in the engines."""
from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.models import SystemConfig

DEFAULT_CONFIG: dict[str, dict[str, Any]] = {
    "reminder_offsets_days": {
        "value": [90, 60, 30, 7, 0, -7],
        "description": "Maturity reminder ladder in days before maturity (negative = after maturity).",
    },
    "expiring_soon_window_days": {
        "value": 90,
        "description": "Instrument enters EXPIRING_SOON this many days before maturity.",
    },
    "action_required_days_before": {
        "value": 30,
        "description": "At T-N the instrument becomes ACTION_REQUIRED, the institution is locked and a ticket opens for the regional officer.",
    },
    "overdue_grace_days": {
        "value": 15,
        "description": "Days after maturity without renewal before the case becomes OVERDUE and escalates to the Approving Authority.",
    },
    "lock_institution_on_action_required": {
        "value": True,
        "description": "Block new submissions / release requests while a renewal is pending.",
    },
    "escalation_ladder": {
        "value": [
            {"level": 1, "role": "REGIONAL_OFFICER", "escalate_after_hours": 168},
            {"level": 2, "role": "APPROVING_AUTHORITY", "escalate_after_hours": 168},
            {"level": 3, "role": "ADMIN", "escalate_after_hours": None},
        ],
        "description": "Unresolved alerts move up one level after the configured hours.",
    },
    "alert_start": {
        "value": {
            "ACTION_REQUIRED": {"level": 1, "role": "REGIONAL_OFFICER"},
            "OVERDUE": {"level": 2, "role": "APPROVING_AUTHORITY"},
            "VERIFICATION_PENDING": {"level": 1, "role": "SCRUTINY_OFFICER"},
            "DISCREPANCY_PENDING": {"level": 1, "role": "SCRUTINY_OFFICER"},
            "REFUND_PENDING": {"level": 1, "role": "SCRUTINY_OFFICER"},
            "BANK_STATUS_CHANGED": {"level": 2, "role": "APPROVING_AUTHORITY"},
        },
        "description": "Where each alert type enters the escalation ladder.",
    },
    "verification_sla_hours": {
        "value": 72,
        "description": "Submitted instruments not verified within this time raise a VERIFICATION_PENDING alert.",
    },
    "discrepancy_response_days": {
        "value": 15,
        "description": "Institution must answer a discrepancy within this many days.",
    },
    "refund_sla_hours": {
        "value": 120,
        "description": "Open release requests older than this raise a REFUND_PENDING alert.",
    },
    "min_amount_by_purpose": {
        "value": {
            "NEW_APPROVAL": 1000000,
            "EXTENSION_OF_APPROVAL": 500000,
            "INCREASE_IN_INTAKE": 500000,
            "NEW_COURSE": 500000,
            "CLOSURE_UNDERTAKING": 500000,
            "OTHER": 100000,
        },
        "description": "Prescribed minimum security amount (INR) per purpose. Demo values - replace with Handbook slabs.",
    },
    "min_validity_months": {
        "value": 12,
        "description": "Minimum period between issue and maturity.",
    },
    "min_remaining_validity_days_at_submission": {
        "value": 90,
        "description": "Advisory flag when an FDR is submitted this close to maturity.",
    },
    "lien_holder_keywords": {
        "value": ["AICTE", "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION"],
        "description": "Lien must be marked in favour of one of these.",
    },
    "required_documents": {
        "value": {"default": ["FDR_SCAN", "LIEN_LETTER"]},
        "description": "Document checklist per purpose (key = purpose or 'default').",
    },
    "release_required_documents": {
        "value": ["UNDERTAKING"],
        "description": "Documents required on a release / refund request.",
    },
    "ocr_min_confidence": {
        "value": 0.6,
        "description": "Below this, OCR output is not trusted and the document goes to manual review.",
    },
    "rule_overrides": {
        "value": {},
        "description": "Per-rule overrides, e.g. {\"R14\": {\"enabled\": false}} or {\"R05\": {\"severity\": \"MEDIUM\"}}.",
    },
    "reverification_interval_days": {
        "value": 30,
        "description": "Continuous re-verification: held FDRs are re-checked with the bank this often to catch premature encashment / lien removal.",
    },
    "clock_offset_days": {
        "value": 0,
        "description": "DEMO ONLY: simulated clock offset.",
    },
}


def seed_defaults(db: Session) -> None:
    existing = {c.key for c in db.query(SystemConfig.key).all()}
    for key, spec in DEFAULT_CONFIG.items():
        if key not in existing:
            db.add(SystemConfig(key=key, value=deepcopy(spec["value"]), description=spec["description"]))
    db.commit()


def get(db: Session, key: str) -> Any:
    row = db.get(SystemConfig, key)
    if row is None:
        return deepcopy(DEFAULT_CONFIG[key]["value"])
    return row.value


def all_config(db: Session) -> dict[str, Any]:
    out = {k: deepcopy(v["value"]) for k, v in DEFAULT_CONFIG.items()}
    for row in db.query(SystemConfig).all():
        out[row.key] = row.value
    return out


def set_value(db: Session, key: str, value: Any, user_id: int | None) -> SystemConfig:
    if key not in DEFAULT_CONFIG:
        raise KeyError(key)
    row = db.get(SystemConfig, key)
    if row is None:
        row = SystemConfig(key=key, description=DEFAULT_CONFIG[key]["description"])
        db.add(row)
    row.value = value
    row.updated_by = user_id
    return row
