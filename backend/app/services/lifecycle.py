"""Instrument state machine + lifecycle timeline (fdr_events) + audit."""
from typing import Any

from fastapi import HTTPException, status as http
from sqlalchemy.orm import Session

from app.enums import InstrumentStatus as S, Role
from app.models import FdrEvent, Instrument, User
from app.services import audit, clock

OFFICERS = {Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER, Role.ADMIN}
APPROVERS = {Role.APPROVING_AUTHORITY, Role.ADMIN}
SYSTEM = "SYSTEM"

RELEASABLE = {S.ACTIVE, S.EXPIRING_SOON, S.ACTION_REQUIRED, S.MATURED, S.OVERDUE}

# action -> (allowed from-states, to-state (None = given by caller), allowed roles or SYSTEM)
TRANSITIONS: dict[str, tuple[set[S], S | None, set[Role] | str]] = {
    "submit": ({S.DRAFT, S.DISCREPANCY_RAISED}, S.SUBMITTED, {Role.INSTITUTION}),
    "pickup": ({S.SUBMITTED}, S.UNDER_SCRUTINY, OFFICERS),
    "raise_discrepancy": ({S.SUBMITTED, S.UNDER_SCRUTINY, S.VERIFIED}, S.DISCREPANCY_RAISED, OFFICERS | APPROVERS),
    "mark_verified": ({S.UNDER_SCRUTINY}, S.VERIFIED, OFFICERS),
    "send_back": ({S.VERIFIED}, S.UNDER_SCRUTINY, APPROVERS),
    "approve": ({S.VERIFIED}, S.ACTIVE, APPROVERS),
    "reject": ({S.SUBMITTED, S.UNDER_SCRUTINY, S.VERIFIED, S.DISCREPANCY_RAISED}, S.REJECTED, APPROVERS),
    "request_release": (RELEASABLE, S.RELEASE_REQUESTED, SYSTEM),
    "approve_release": ({S.RELEASE_REQUESTED}, S.RELEASE_APPROVED, SYSTEM),
    "complete_release": ({S.RELEASE_APPROVED}, S.RELEASED, SYSTEM),
    "revert_release": ({S.RELEASE_REQUESTED, S.RELEASE_APPROVED}, None, SYSTEM),
    "mark_renewed": (RELEASABLE, S.RENEWED, SYSTEM),
    "monitor": (RELEASABLE | {S.ACTIVE}, None, SYSTEM),
}

# Human-facing actions the frontend can render as buttons
USER_ACTIONS = ["submit", "pickup", "raise_discrepancy", "mark_verified", "send_back", "approve", "reject"]

STATUS_LABEL = {
    S.DRAFT: "Draft",
    S.SUBMITTED: "Submitted",
    S.UNDER_SCRUTINY: "Under scrutiny",
    S.DISCREPANCY_RAISED: "Discrepancy raised",
    S.VERIFIED: "Verified",
    S.ACTIVE: "Active",
    S.EXPIRING_SOON: "Approaching maturity",
    S.ACTION_REQUIRED: "Action required - renewal due",
    S.MATURED: "Matured",
    S.OVERDUE: "Overdue",
    S.RENEWED: "Renewed (closed)",
    S.RELEASE_REQUESTED: "Release requested",
    S.RELEASE_APPROVED: "Release approved",
    S.RELEASED: "Released (closed)",
    S.REJECTED: "Rejected",
}

SNAPSHOT_FIELDS = [
    "status", "verification_status", "trust_level", "fdr_number", "bank_name", "ifsc", "amount",
    "issue_date", "maturity_date", "lien_marked", "lien_in_favour_of", "risk_score",
]


def _role_name(actor: User | None) -> str:
    return actor.role.value if actor else SYSTEM


def log_event(
    db: Session, inst: Instrument, action: str, actor: User | None, note: str | None = None,
    data: dict[str, Any] | None = None, from_status: str | None = None, to_status: str | None = None,
    audit_before: Any = None, audit_after: Any = None,
) -> FdrEvent:
    ev = FdrEvent(
        instrument_id=inst.id, action=action,
        from_status=from_status or inst.status.value, to_status=to_status or inst.status.value,
        actor_id=actor.id if actor else None, actor_role=_role_name(actor), note=note,
        data=audit._clean(data), created_at=clock.now(),
    )
    db.add(ev)
    audit.record(
        db, actor, f"INSTRUMENT_{action.upper()}", "instrument", inst.id,
        before=audit_before, after=audit_after if audit_after is not None else ({"note": note, **(data or {})} if (note or data) else None),
        institution_id=inst.institution_id,
    )
    return ev


def transition(
    db: Session, inst: Instrument, action: str, actor: User | None, note: str | None = None,
    data: dict[str, Any] | None = None, to_status: S | None = None,
) -> Instrument:
    if action not in TRANSITIONS:
        raise ValueError(f"unknown action {action}")
    from_states, target, roles = TRANSITIONS[action]
    if roles != SYSTEM and actor is not None and actor.role not in roles:
        raise HTTPException(http.HTTP_403_FORBIDDEN, f"{actor.role.value} cannot perform '{action}'")
    if inst.status not in from_states:
        raise HTTPException(
            http.HTTP_409_CONFLICT,
            f"Cannot '{action}' an instrument in status {inst.status.value}",
        )
    new_status = to_status or target
    if new_status is None:
        raise ValueError("to_status required")
    before = audit.snapshot(inst, SNAPSHOT_FIELDS)
    old = inst.status
    inst.status = new_status
    inst.version = (inst.version or 1) + 1
    now = clock.now()
    if new_status == S.SUBMITTED:
        inst.submitted_at = now
    elif new_status == S.VERIFIED:
        inst.verified_at = now
    elif new_status == S.ACTIVE and old == S.VERIFIED:
        inst.approved_at = now
    if new_status in (S.RENEWED, S.RELEASED, S.REJECTED):
        inst.closed_at = now
    log_event(
        db, inst, action, actor, note, data, from_status=old.value, to_status=new_status.value,
        audit_before=before, audit_after=audit.snapshot(inst, SNAPSHOT_FIELDS) | {"note": note},
    )
    return inst


def allowed_actions(user: User, inst: Instrument) -> list[str]:
    out = []
    for name in USER_ACTIONS:
        from_states, _t, roles = TRANSITIONS[name]
        if roles == SYSTEM or user.role not in roles or inst.status not in from_states:
            continue
        if user.role == Role.INSTITUTION and inst.institution_id != user.institution_id:
            continue
        out.append(name)
    # non-transition actions
    if user.role in OFFICERS and inst.status in ({S.SUBMITTED, S.UNDER_SCRUTINY, S.VERIFIED} | RELEASABLE):
        out += ["verify_with_bank", "manual_verify"]
    if user.role == Role.INSTITUTION and inst.institution_id == user.institution_id:
        if inst.status in (S.DRAFT, S.DISCREPANCY_RAISED):
            out += ["edit", "upload_document"]
        if inst.status in RELEASABLE:
            out += ["renew", "request_release"]
    return out


def pending_action(inst: Instrument, open_flag_titles: list[str] | None = None) -> dict[str, str]:
    """Identical 'what happens next' text shown to BOTH institution and officer."""
    m = inst.maturity_date.strftime("%d-%m-%Y") if inst.maturity_date else "-"
    st = inst.status
    if st == S.DRAFT:
        return {"owner": "INSTITUTION", "text": "Complete the details, upload the FDR scan and lien letter, then submit."}
    if st == S.SUBMITTED:
        return {"owner": "AICTE", "text": "Waiting for a scrutiny officer to pick up the case."}
    if st == S.UNDER_SCRUTINY:
        return {"owner": "AICTE", "text": "Officer is scrutinising the record and verifying it with the bank."}
    if st == S.DISCREPANCY_RAISED:
        reasons = "; ".join(open_flag_titles or []) or "see officer observations"
        return {"owner": "INSTITUTION", "text": f"Fix the discrepancies and re-submit: {reasons}."}
    if st == S.VERIFIED:
        return {"owner": "AICTE", "text": "Verified. Awaiting sign-off by the Approving Authority."}
    if st == S.ACTIVE:
        return {"owner": "NONE", "text": f"Active security. Matures on {m}."}
    if st == S.EXPIRING_SOON:
        return {"owner": "INSTITUTION", "text": f"Matures on {m}. Arrange renewal with your bank in advance."}
    if st == S.ACTION_REQUIRED:
        return {"owner": "INSTITUTION", "text": f"Upload the renewed / replacement FDR before {m}. New submissions are locked until then."}
    if st == S.MATURED:
        return {"owner": "INSTITUTION", "text": f"Matured on {m}. Upload renewal proof immediately."}
    if st == S.OVERDUE:
        return {"owner": "INSTITUTION", "text": f"Overdue since {m}. Case escalated to the Approving Authority."}
    if st == S.RELEASE_REQUESTED:
        return {"owner": "AICTE", "text": "Release request under review."}
    if st == S.RELEASE_APPROVED:
        return {"owner": "AICTE", "text": "Release sanctioned. Discharge letter to the bank being issued."}
    if st == S.RENEWED:
        return {"owner": "NONE", "text": "Closed - replaced by a renewed instrument."}
    if st == S.RELEASED:
        return {"owner": "NONE", "text": "Closed - security released to the institution."}
    return {"owner": "NONE", "text": "Closed - rejected."}
