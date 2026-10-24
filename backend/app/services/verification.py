"""Bank verification hub - API first, never blocked.

Route 1  BANK_API         : bank's verification API (simulated AA sandbox in the prototype).
Route 2  BANK_EMAIL_LINK  : if the bank has no API or it is down, the bank nodal officer gets a
                            secure one-time link and fills the values BLIND (they never see what
                            the institution declared, so they cannot just rubber-stamp it).
Route 3  BANK_PORTAL      : a BANK-role user answers the same request from their login.
Route 4  MANUAL_UPLOAD    : officer uploads the bank's written confirmation and records the values.

Every attempt is stored in verification_requests (source, endpoint, payloads, timestamps) =
chain of custody. A source being down is recorded as SOURCE_UNAVAILABLE, never as 'fake'.
"""
import hashlib
import secrets
from datetime import timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import (
    Role,
    TrustLevel,
    VerificationChannel,
    VerificationRequestStatus,
    VerificationStatus,
)
from app.models import Bank, Instrument, User, VerificationRequest
from app.services import clock, fields, lifecycle, mock_bank, notifications, rules

TOKEN_TTL_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _bank_of(db: Session, inst: Instrument) -> Bank | None:
    if inst.bank_id:
        return db.get(Bank, inst.bank_id)
    return rules.resolve_bank(db, inst.bank_name, inst.ifsc)


def _fetch(db: Session, inst: Instrument) -> tuple[dict[str, Any], str, bool]:
    """Returns (payload, endpoint, is_simulated). Raises SourceUnavailable."""
    if settings.BANK_API_BASE_URL:
        url = settings.BANK_API_BASE_URL.rstrip("/") + "/v1/fdr/verify"
        try:
            r = httpx.post(url, json={"fdr_number": inst.fdr_number, "ifsc": inst.ifsc},
                           headers={"X-Api-Key": settings.MOCK_BANK_API_KEY}, timeout=10)
        except httpx.HTTPError as exc:
            raise mock_bank.SourceUnavailable(str(exc)) from exc
        if r.status_code == 503:
            raise mock_bank.SourceUnavailable(r.text)
        r.raise_for_status()
        return r.json(), url, bool(r.json().get("simulated"))
    return mock_bank.lookup(db, inst.fdr_number or "", inst.ifsc or ""), "/api/v1/mock-bank/v1/fdr/verify (in-process sandbox)", True


def _finalize(
    db: Session, inst: Instrument, vr: VerificationRequest, confirmed: dict[str, Any] | None,
    channel: VerificationChannel, actor: User | None, trust_on_success: TrustLevel,
) -> VerificationRequest:
    now = clock.now()
    prev_status = inst.verification_status
    if confirmed is None:
        result = VerificationStatus.NOT_FOUND
        comparison: list[dict[str, Any]] = []
    else:
        bank_status = confirmed.pop("_bank_status", "ACTIVE")
        vr.response_payload = {**(vr.response_payload or {}), "bank_status": bank_status}
        comparison = fields.apply_confirmation(db, inst, confirmed, channel, actor)
        all_match = all(r["match"] for r in comparison)
        result = VerificationStatus.VERIFIED if (all_match and bank_status == "ACTIVE") else VerificationStatus.MISMATCH
    vr.result = result
    vr.comparison = {"fields": comparison}
    vr.status = VerificationRequestStatus.RESPONDED
    vr.responded_at = now
    inst.verification_status = result
    inst.last_bank_check_at = now
    if result == VerificationStatus.VERIFIED:
        inst.trust_level = trust_on_success
    elif inst.trust_level != TrustLevel.SELF_DECLARED and result in (VerificationStatus.MISMATCH, VerificationStatus.NOT_FOUND):
        inst.trust_level = TrustLevel.SELF_DECLARED  # previously confirmed, now contradicted
    lifecycle.log_event(
        db, inst, "bank_verification", actor,
        note=f"{channel.value}: {result.value}",
        data={"verification_request_id": vr.id, "channel": channel.value, "result": result.value,
              "source": vr.source_name, "simulated": vr.is_simulated,
              "mismatches": [r["field"] for r in comparison if not r["match"]]},
    )
    rules.apply(db, inst)
    vr.response_payload = {**(vr.response_payload or {}), "previous_verification_status": prev_status.value}
    return vr


def verify_via_api(db: Session, inst: Instrument, actor: User | None, auto_fallback: bool = True) -> VerificationRequest:
    if not inst.fdr_number or not inst.ifsc:
        raise HTTPException(422, "FDR number and IFSC are required for bank verification")
    bank = _bank_of(db, inst)
    if bank is None:
        vr = VerificationRequest(
            instrument_id=inst.id, channel=VerificationChannel.BANK_API, status=VerificationRequestStatus.FAILED,
            result=VerificationStatus.MANUAL_REVIEW, source_name="unknown bank", is_simulated=True,
            request_payload={"fdr_number": inst.fdr_number, "ifsc": inst.ifsc}, requested_by=actor.id if actor else None,
            response_payload={"error": "Bank not in bank master; use manual verification"},
        )
        db.add(vr)
        inst.verification_status = VerificationStatus.MANUAL_REVIEW
        db.flush()
        lifecycle.log_event(db, inst, "bank_verification", actor, note="Bank not in master - manual review",
                            data={"verification_request_id": vr.id})
        return vr
    if not bank.api_enabled:
        return send_email_link(db, inst, actor, bank, reason="Bank has no verification API")

    vr = VerificationRequest(
        instrument_id=inst.id, bank_id=bank.id, channel=VerificationChannel.BANK_API,
        source_name=f"{bank.name} - {mock_bank.SOURCE_LABEL}" if not settings.BANK_API_BASE_URL else bank.name,
        request_payload={"fdr_number": inst.fdr_number, "ifsc": inst.ifsc, "consent_ref": f"AICTE-CONSENT-{inst.id}"},
        requested_by=actor.id if actor else None,
    )
    db.add(vr)
    db.flush()
    try:
        payload, endpoint, simulated = _fetch(db, inst)
    except mock_bank.SourceUnavailable as exc:
        vr.endpoint = "bank API"
        vr.status = VerificationRequestStatus.FAILED
        vr.result = VerificationStatus.SOURCE_UNAVAILABLE
        vr.response_payload = {"error": str(exc)}
        vr.responded_at = clock.now()
        inst.verification_status = VerificationStatus.SOURCE_UNAVAILABLE
        lifecycle.log_event(db, inst, "bank_verification", actor,
                            note="Bank API unavailable - source down is NOT treated as a bad FDR",
                            data={"verification_request_id": vr.id, "result": "SOURCE_UNAVAILABLE"})
        if auto_fallback:
            return send_email_link(db, inst, actor, bank, reason="Bank API unavailable")
        return vr
    vr.endpoint = endpoint
    vr.is_simulated = simulated
    vr.response_payload = payload
    confirmed = mock_bank.to_confirmed(payload) if payload.get("found") else None
    return _finalize(db, inst, vr, confirmed, VerificationChannel.BANK_API, actor, TrustLevel.BANK_CONFIRMED)


def send_email_link(db: Session, inst: Instrument, actor: User | None, bank: Bank, reason: str) -> VerificationRequest:
    token = secrets.token_urlsafe(32)
    vr = VerificationRequest(
        instrument_id=inst.id, bank_id=bank.id, channel=VerificationChannel.BANK_EMAIL_LINK,
        source_name=f"{bank.name} nodal officer", endpoint=bank.nodal_officer_email, is_simulated=False,
        token_hash=_hash_token(token), token_expires_at=clock.now() + timedelta(days=TOKEN_TTL_DAYS),
        request_payload={"fdr_number": inst.fdr_number, "ifsc": inst.ifsc, "reason": reason, "blind": True},
        requested_by=actor.id if actor else None,
    )
    db.add(vr)
    db.flush()
    inst.verification_status = VerificationStatus.SENT_TO_BANK
    link = f"{settings.FRONTEND_BASE_URL}/bank-confirm/{token}"
    if bank.nodal_officer_email:
        notifications.send_external_email(
            db, bank.nodal_officer_email,
            f"[AICTE] FDR confirmation request {inst.fdr_number}",
            (f"AICTE requests confirmation of Fixed Deposit {inst.fdr_number} (IFSC {inst.ifsc}).\n"
             f"Please open this one-time secure link and enter the values as per your records:\n{link}\n"
             f"API alternative: POST {settings.PUBLIC_BASE_URL}/api/v1/bank-link/{token}\n"
             f"The link expires in {TOKEN_TTL_DAYS} days."),
            category="BANK_VERIFICATION",
        )
    for bank_user in db.execute(select(User).where(User.role == Role.BANK, User.bank_id == bank.id, User.is_active)).scalars():
        notifications.notify_user(db, bank_user, "New FDR confirmation request",
                                  f"Please confirm FDR {inst.fdr_number} (IFSC {inst.ifsc}).",
                                  link="/bank/requests", category="BANK_VERIFICATION", email=False)
    lifecycle.log_event(db, inst, "bank_verification_requested", actor,
                        note=f"Secure confirmation link sent to {bank.name} nodal officer ({reason})",
                        data={"verification_request_id": vr.id, "channel": "BANK_EMAIL_LINK"})
    vr._plain_token = token  # type: ignore[attr-defined]  # returned once to caller in DEMO_MODE
    return vr


def get_by_token(db: Session, token: str) -> VerificationRequest:
    vr = db.execute(select(VerificationRequest).where(VerificationRequest.token_hash == _hash_token(token))).scalar()
    if vr is None:
        raise HTTPException(404, "Invalid link")
    if vr.status != VerificationRequestStatus.PENDING:
        raise HTTPException(410, "This link has already been used")
    if vr.token_expires_at and vr.token_expires_at < clock.now():
        vr.status = VerificationRequestStatus.EXPIRED
        db.commit()
        raise HTTPException(410, "This link has expired")
    return vr


def respond(
    db: Session, vr: VerificationRequest, found: bool, values: dict[str, Any], responder: User | None,
    channel: VerificationChannel, bank_status: str = "ACTIVE", remarks: str | None = None,
) -> VerificationRequest:
    inst = db.get(Instrument, vr.instrument_id)
    vr.responded_by = responder.id if responder else None
    vr.channel = channel
    vr.response_payload = {"found": found, "values": values, "remarks": remarks, "bank_status": bank_status}
    confirmed = None
    if found:
        confirmed = {k: v for k, v in values.items() if v is not None} | {"_bank_status": bank_status}
    return _finalize(db, inst, vr, confirmed, channel, responder, TrustLevel.BANK_CONFIRMED)


def manual_verify(
    db: Session, inst: Instrument, officer: User, values: dict[str, Any], document_id: int | None,
    remarks: str | None,
) -> VerificationRequest:
    vr = VerificationRequest(
        instrument_id=inst.id, bank_id=inst.bank_id, channel=VerificationChannel.MANUAL_UPLOAD,
        source_name="Officer - written bank confirmation", is_simulated=False,
        request_payload={"document_id": document_id}, requested_by=officer.id,
        response_payload={"values": values, "remarks": remarks}, responded_by=officer.id,
    )
    db.add(vr)
    db.flush()
    confirmed = {k: v for k, v in values.items() if v is not None} | {"_bank_status": "ACTIVE"}
    return _finalize(db, inst, vr, confirmed, VerificationChannel.MANUAL_UPLOAD, officer, TrustLevel.OFFICER_VERIFIED)


def serialize(vr: VerificationRequest, include_token: bool = False) -> dict[str, Any]:
    d = {
        "id": vr.id, "instrument_id": vr.instrument_id, "bank_id": vr.bank_id, "channel": vr.channel.value,
        "status": vr.status.value, "result": vr.result.value if vr.result else None,
        "source_name": vr.source_name, "endpoint": vr.endpoint, "is_simulated": vr.is_simulated,
        "request_payload": vr.request_payload, "response_payload": vr.response_payload,
        "comparison": vr.comparison, "requested_at": vr.requested_at, "responded_at": vr.responded_at,
        "token_expires_at": vr.token_expires_at,
    }
    token = getattr(vr, "_plain_token", None)
    if include_token and token:
        d["demo_confirmation_token"] = token
        d["demo_confirmation_link"] = f"{settings.FRONTEND_BASE_URL}/bank-confirm/{token}"
    return d
