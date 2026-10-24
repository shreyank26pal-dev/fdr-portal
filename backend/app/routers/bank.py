"""Bank-facing endpoints.

1. /mock-bank/v1/...   SIMULATED bank core API (Account-Aggregator style) - the sandbox the hub calls.
2. /bank-link/{token}  One-time secure link for bank nodal officers (no login, blind confirmation).
3. /bank/requests      Logged-in BANK users answer confirmation requests for their bank.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.enums import BankRecordStatus, Role, VerificationChannel, VerificationRequestStatus
from app.models import Bank, BankLedgerRecord, Institution, Instrument, User, VerificationRequest
from app.schemas import BankResponseIn, MockLedgerUpdateIn
from app.security import require_roles
from app.services import audit, mock_bank, verification

router = APIRouter(tags=["Bank verification"])


# ------------------------- 1. simulated bank API --------------------------- #
class SandboxQuery(BaseModel):
    fdr_number: str
    ifsc: str


@router.post("/mock-bank/v1/fdr/verify",
             summary="[SIMULATED] Bank term-deposit lookup in Account-Aggregator-like format (X-Api-Key required)")
def sandbox_verify(body: SandboxQuery, x_api_key: str = Header(...), db: Session = Depends(get_db)):
    if x_api_key != settings.MOCK_BANK_API_KEY:
        raise HTTPException(401, "Invalid API key")
    try:
        return mock_bank.lookup(db, body.fdr_number, body.ifsc)
    except mock_bank.SourceUnavailable as exc:
        raise HTTPException(503, str(exc))
    except mock_bank.UnknownBank:
        raise HTTPException(404, "Unknown bank / IFSC")


@router.get("/mock-bank/v1/records", summary="[SIMULATED] Bank ledger (demo control panel)")
def sandbox_records(bank_id: int | None = None, user: User = Depends(require_roles(Role.ADMIN, Role.BANK)),
                    db: Session = Depends(get_db)):
    q = select(BankLedgerRecord).order_by(BankLedgerRecord.id)
    if user.role == Role.BANK:
        q = q.where(BankLedgerRecord.bank_id == user.bank_id)
    elif bank_id:
        q = q.where(BankLedgerRecord.bank_id == bank_id)
    return [{"id": r.id, "bank": r.bank.name, "fdr_number": r.fdr_number, "ifsc": r.ifsc, "depositor": r.depositor_name,
             "amount": r.amount, "issue_date": r.issue_date, "maturity_date": r.maturity_date,
             "lien_marked": r.lien_marked, "lien_holder": r.lien_holder, "status": r.status.value}
            for r in db.execute(q).scalars()]


@router.patch("/mock-bank/v1/records/{record_id}",
              summary="[SIMULATED] Change the bank's record, e.g. status=ENCASHED to demo premature-encashment detection")
def sandbox_update(record_id: int, body: MockLedgerUpdateIn, user: User = Depends(require_roles(Role.ADMIN, Role.BANK)),
                   db: Session = Depends(get_db)):
    rec = db.get(BankLedgerRecord, record_id)
    if rec is None or (user.role == Role.BANK and rec.bank_id != user.bank_id):
        raise HTTPException(404, "Record not found")
    before = {"status": rec.status.value, "lien_marked": rec.lien_marked, "amount": rec.amount}
    if body.status:
        rec.status = BankRecordStatus(body.status)
    if body.lien_marked is not None:
        rec.lien_marked = body.lien_marked
    if body.amount is not None:
        rec.amount = body.amount
    if body.maturity_date is not None:
        rec.maturity_date = body.maturity_date
    audit.record(db, user, "MOCK_BANK_RECORD_CHANGED", "mock_bank_record", rec.id, before=before,
                 after={"status": rec.status.value, "lien_marked": rec.lien_marked, "amount": rec.amount})
    db.commit()
    return {"ok": True}


@router.post("/mock-bank/v1/banks/{bank_id}/availability",
             summary="[SIMULATED] Toggle a bank API outage to demo graceful fallback")
def sandbox_availability(bank_id: int, available: bool, user: User = Depends(require_roles(Role.ADMIN)),
                         db: Session = Depends(get_db)):
    bank = db.get(Bank, bank_id)
    if bank is None:
        raise HTTPException(404, "Bank not found")
    bank.api_available = available
    audit.record(db, user, "MOCK_BANK_AVAILABILITY", "bank", bank.id, after={"api_available": available})
    db.commit()
    return {"bank": bank.name, "api_available": available}


# ------------------------- 2. one-time secure link -------------------------- #
@router.get("/bank-link/{token}", summary="Bank nodal officer opens the link: sees WHAT to confirm, not the declared values")
def link_view(token: str, db: Session = Depends(get_db)):
    vr = verification.get_by_token(db, token)
    inst = db.get(Instrument, vr.instrument_id)
    bank = db.get(Bank, vr.bank_id) if vr.bank_id else None
    return {
        "request_id": vr.id, "bank": bank.name if bank else None,
        "fdr_number": inst.fdr_number, "ifsc": inst.ifsc, "institution": inst.institution.name,
        "expires_at": vr.token_expires_at,
        "please_provide": ["found", "amount", "issue_date", "maturity_date", "lien_marked", "depositor_name", "bank_status"],
        "note": "Blind confirmation: enter the values from your core banking system. "
                "Declared values are intentionally not shown.",
    }


@router.post("/bank-link/{token}", summary="Bank nodal officer submits the confirmation (one-time)")
def link_respond(token: str, body: BankResponseIn, db: Session = Depends(get_db)):
    vr = verification.get_by_token(db, token)
    values = body.model_dump(exclude={"found", "bank_status", "remarks"}, exclude_none=True)
    vr = verification.respond(db, vr, body.found, values, None, VerificationChannel.BANK_EMAIL_LINK,
                              body.bank_status, body.remarks)
    db.commit()
    return {"ok": True, "result": vr.result.value if vr.result else None,
            "message": "Thank you. Your confirmation has been recorded in the AICTE ledger."}


# ------------------------- 3. bank user portal ------------------------------ #
@router.get("/bank/requests", summary="Pending confirmation requests for my bank (BANK role)")
def bank_requests(user: User = Depends(require_roles(Role.BANK)), db: Session = Depends(get_db)):
    q = select(VerificationRequest).where(VerificationRequest.bank_id == user.bank_id).order_by(VerificationRequest.id.desc())
    out = []
    for vr in db.execute(q).scalars():
        inst = db.get(Instrument, vr.instrument_id)
        out.append({"id": vr.id, "status": vr.status.value, "channel": vr.channel.value,
                    "fdr_number": inst.fdr_number, "ifsc": inst.ifsc,
                    "institution": db.get(Institution, inst.institution_id).name,
                    "requested_at": vr.requested_at, "responded_at": vr.responded_at,
                    "result": vr.result.value if vr.result else None})
    return out


@router.post("/bank/requests/{request_id}/respond", summary="BANK user answers a confirmation request (blind)")
def bank_respond(request_id: int, body: BankResponseIn, user: User = Depends(require_roles(Role.BANK)),
                 db: Session = Depends(get_db)):
    vr = db.get(VerificationRequest, request_id)
    if vr is None or vr.bank_id != user.bank_id:
        raise HTTPException(404, "Request not found")
    if vr.status != VerificationRequestStatus.PENDING:
        raise HTTPException(409, "Already answered")
    values = body.model_dump(exclude={"found", "bank_status", "remarks"}, exclude_none=True)
    vr = verification.respond(db, vr, body.found, values, user, VerificationChannel.BANK_PORTAL, body.bank_status, body.remarks)
    db.commit()
    return {"ok": True, "result": vr.result.value if vr.result else None}
