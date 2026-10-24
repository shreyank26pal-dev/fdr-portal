"""SIMULATED bank core system exposed in an Account-Aggregator-like shape.

This is clearly labelled as a sandbox everywhere it surfaces. In production the
same adapter interface would call a bank's authorised verification API (or the
RBI Account Aggregator framework with institution consent).
"""
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bank, BankLedgerRecord
from app.services import clock
from app.services.ocr import norm_id

SOURCE_LABEL = "SIMULATED_AA_SANDBOX"


class SourceUnavailable(Exception):
    pass


class UnknownBank(Exception):
    pass


def bank_for_ifsc(db: Session, ifsc: str) -> Bank | None:
    return db.execute(select(Bank).where(Bank.ifsc_prefix == (ifsc or "")[:4].upper())).scalar()


def find_record(db: Session, fdr_number: str, ifsc: str) -> BankLedgerRecord | None:
    key = norm_id(fdr_number)
    recs = db.execute(select(BankLedgerRecord).where(BankLedgerRecord.ifsc == (ifsc or "").upper())).scalars()
    for r in recs:
        if norm_id(r.fdr_number) == key:
            return r
    return None


def aa_response(rec: BankLedgerRecord | None, fdr_number: str, ifsc: str, bank: Bank) -> dict[str, Any]:
    base = {
        "source": SOURCE_LABEL,
        "simulated": True,
        "txnId": str(uuid.uuid4()),
        "timestamp": clock.now().isoformat(),
        "fipId": f"{bank.short_code}-FIP",
        "fiType": "TERM_DEPOSIT",
        "query": {"fdrNumber": fdr_number, "ifsc": ifsc},
    }
    if rec is None:
        return base | {"found": False, "error": {"code": "RECORD_NOT_FOUND", "message": "No term deposit with this number at this branch"}}
    return base | {
        "found": True,
        "account": {
            "fdrNumber": rec.fdr_number,
            "ifsc": rec.ifsc,
            "bankName": bank.name,
            "holder": {"name": rec.depositor_name},
            "summary": {
                "principalAmount": str(rec.amount),
                "openingDate": rec.issue_date.isoformat(),
                "maturityDate": rec.maturity_date.isoformat(),
                "accountStatus": rec.status.value,
                "lien": {"marked": rec.lien_marked, "holder": rec.lien_holder},
            },
        },
    }


def lookup(db: Session, fdr_number: str, ifsc: str) -> dict[str, Any]:
    bank = bank_for_ifsc(db, ifsc)
    if bank is None:
        raise UnknownBank(ifsc)
    if not bank.api_available:
        raise SourceUnavailable(f"{bank.name} verification service is not reachable")
    return aa_response(find_record(db, fdr_number, ifsc), fdr_number, ifsc, bank)


def to_confirmed(payload: dict[str, Any]) -> dict[str, Any]:
    """Map AA-style payload to our tracked field names."""
    if not payload.get("found"):
        return {}
    acc = payload["account"]
    s = acc["summary"]
    lien = s.get("lien") or {}
    return {
        "fdr_number": acc["fdrNumber"],
        "ifsc": acc["ifsc"],
        "bank_name": acc["bankName"],
        "depositor_name": acc["holder"]["name"],
        "amount": s["principalAmount"],
        "issue_date": s["openingDate"],
        "maturity_date": s["maturityDate"],
        "lien_marked": bool(lien.get("marked")) and "AICTE" in (lien.get("holder") or "").upper(),
        "_bank_status": s["accountStatus"],
    }
