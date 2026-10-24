from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import DocType, RefundStatus, Role
from app.models import Document, RefundRequest, User
from app.routers.common import get_instrument, scope_institution_ids
from app.schemas import ActionNoteIn, DocumentOut, RefundIn, RefundOut, RejectIn
from app.security import get_current_user, require_roles
from app.services import documents, refunds, renewals, storage

router = APIRouter(prefix="/refunds", tags=["Release / refund (courier-style tracking)"])

OFFICER = (Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER, Role.ADMIN)
APPROVER = (Role.APPROVING_AUTHORITY, Role.ADMIN)


def _get(db: Session, refund_id: int, user: User) -> RefundRequest:
    rr = db.get(RefundRequest, refund_id)
    if rr is None:
        raise HTTPException(404, "Request not found")
    get_instrument(db, rr.instrument_id, user)  # access check
    return rr


def _out(db: Session, rr: RefundRequest) -> dict:
    docs = db.execute(select(Document).where(Document.refund_request_id == rr.id)).scalars().all()
    return {
        **RefundOut.model_validate(rr).model_dump(),
        "instrument": {"id": rr.instrument.id, "fdr_number": rr.instrument.fdr_number,
                       "amount": rr.instrument.amount, "bank_name": rr.instrument.bank_name,
                       "status": rr.instrument.status.value},
        "institution_name": rr.instrument.institution.name,
        "documents": [DocumentOut.model_validate(d).model_dump() for d in docs],
        "tracker": refunds.tracker(rr),
    }


@router.get("", summary="List release requests (scoped)")
def list_refunds(status: RefundStatus | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(RefundRequest).order_by(RefundRequest.id.desc())
    ids = scope_institution_ids(db, user)
    if ids is not None:
        q = q.where(RefundRequest.institution_id.in_(ids))
    if status:
        q = q.where(RefundRequest.status == status)
    return [_out(db, r) for r in db.execute(q).scalars()]


@router.post("", status_code=201, summary="Institution raises a release / refund request (pre-conditions auto-checked)")
def create(body: RefundIn, user: User = Depends(require_roles(Role.INSTITUTION)), db: Session = Depends(get_db)):
    inst = get_instrument(db, body.instrument_id, user)
    renewals.ensure_not_locked(db, user.institution_id, allow_instrument_id=inst.id)
    rr = refunds.create(db, inst, user, body.ground, body.reason_text)
    db.commit()
    return _out(db, rr)


@router.get("/{refund_id}", summary="Request detail incl. tracker and pre-condition checklist")
def get_one(refund_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(db, _get(db, refund_id, user))


@router.get("/{refund_id}/track", summary="Courier-style tracker: Requested -> Under review -> Approved -> Processed")
def track(refund_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return refunds.tracker(_get(db, refund_id, user))


@router.post("/{refund_id}/documents", status_code=201, summary="Upload undertaking / supporting document")
async def upload(refund_id: int, file: UploadFile = File(...), doc_type: DocType = Form(DocType.UNDERTAKING),
                 user: User = Depends(require_roles(Role.INSTITUTION)), db: Session = Depends(get_db)):
    rr = _get(db, refund_id, user)
    if rr.status not in (RefundStatus.REQUESTED, RefundStatus.BLOCKED, RefundStatus.UNDER_REVIEW):
        raise HTTPException(409, "Documents can no longer be added")
    try:
        doc, _ = documents.upload(db, user=user, institution_id=rr.institution_id, data=await file.read(),
                                  filename=file.filename or "upload", doc_type=doc_type, refund_request_id=rr.id)
    except storage.UploadRejected as exc:
        raise HTTPException(415, str(exc))
    refunds.recheck(db, rr, user)
    db.commit()
    return _out(db, rr)


@router.post("/{refund_id}/recheck", summary="Re-run the pre-condition engine")
def recheck(refund_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rr = _get(db, refund_id, user)
    refunds.recheck(db, rr, user)
    db.commit()
    return _out(db, rr)


@router.post("/{refund_id}/start-review")
def start_review(refund_id: int, body: ActionNoteIn, user: User = Depends(require_roles(*OFFICER)), db: Session = Depends(get_db)):
    rr = refunds.start_review(db, _get(db, refund_id, user), user, body.note)
    db.commit()
    return _out(db, rr)


@router.post("/{refund_id}/recommend", summary="Officer recommends (step 1 of the two-person rule)")
def recommend(refund_id: int, body: ActionNoteIn, user: User = Depends(require_roles(*OFFICER)), db: Session = Depends(get_db)):
    rr = refunds.recommend(db, _get(db, refund_id, user), user, body.note)
    db.commit()
    return _out(db, rr)


@router.post("/{refund_id}/approve", summary="Competent authority sanctions (step 2, must be a different person)")
def approve(refund_id: int, body: ActionNoteIn, user: User = Depends(require_roles(*APPROVER)), db: Session = Depends(get_db)):
    rr = refunds.approve(db, _get(db, refund_id, user), user, body.note)
    db.commit()
    return _out(db, rr)


@router.post("/{refund_id}/process", summary="Issue discharge letter to the bank and close the instrument")
def process(refund_id: int, body: ActionNoteIn, user: User = Depends(require_roles(*OFFICER, Role.APPROVING_AUTHORITY)),
            db: Session = Depends(get_db)):
    rr = refunds.process(db, _get(db, refund_id, user), user, body.note)
    db.commit()
    return _out(db, rr)


@router.post("/{refund_id}/reject")
def reject(refund_id: int, body: RejectIn, user: User = Depends(require_roles(*OFFICER, *APPROVER)), db: Session = Depends(get_db)):
    rr = refunds.reject(db, _get(db, refund_id, user), user, body.note)
    db.commit()
    return _out(db, rr)


@router.post("/{refund_id}/withdraw")
def withdraw(refund_id: int, user: User = Depends(require_roles(Role.INSTITUTION)), db: Session = Depends(get_db)):
    rr = refunds.withdraw(db, _get(db, refund_id, user), user)
    db.commit()
    return _out(db, rr)
