from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.enums import FlagStatus, Role
from app.models import Document, Flag, Instrument, RefundRequest, User
from app.routers.common import flag_view, get_instrument
from app.schemas import FlagDecisionIn
from app.security import get_current_user, require_roles
from app.services import audit, clock, documents, lifecycle, ocr, rules, storage

router = APIRouter(tags=["Documents, OCR & flags"])


@router.post("/ocr/extract", summary="OCR auto-fill: upload a scan, get pre-filled fields (nothing is stored)")
async def ocr_extract(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = await file.read()
    try:
        ctype = storage.validate_upload(data)
    except storage.UploadRejected as exc:
        raise HTTPException(415, str(exc))
    result = documents.run_ocr(db, data, ctype)
    prefill = {k: v["value"] for k, v in result.fields.items()}
    return {"ocr": result.to_dict(), "prefill": prefill,
            "engines": {"tesseract_available": ocr.tesseract_available(),
                        "google_vision_configured": bool(settings.GOOGLE_VISION_API_KEY)}}


@router.post("/instruments/{instrument_id}/cross-check",
             summary="Compare typed values with the latest uploaded FDR scan (point-of-entry check)")
def cross_check(instrument_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    inst = get_instrument(db, instrument_id, user)
    scans = [d for d in inst.documents if d.doc_type.value in ("FDR_SCAN", "RENEWAL_FDR") and not d.is_superseded]
    if not scans:
        raise HTTPException(404, "No FDR scan uploaded yet")
    doc = scans[-1]
    stored = dict(doc.ocr_fields or {})
    words = stored.pop("_amount_in_words", None)
    result = ocr.OcrResult(status=doc.ocr_status.value, engine=doc.ocr_engine, confidence=doc.ocr_confidence or 0,
                           text="", fields=stored, amount_in_words=words)
    rows = documents.cross_check(inst, result)
    return {"document_id": doc.id, "rows": rows, "mismatches": [r for r in rows if r["status"] == "MISMATCH"]}


@router.get("/documents/{document_id}/download",
            summary="Download (decrypts and re-verifies SHA-256 - a swapped file is refused)")
def download(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    if doc.instrument_id:
        get_instrument(db, doc.instrument_id, user)
    elif doc.refund_request_id:
        rr = db.get(RefundRequest, doc.refund_request_id)
        get_instrument(db, rr.instrument_id, user)
    elif user.role == Role.INSTITUTION and doc.institution_id != user.institution_id:
        raise HTTPException(404, "Document not found")
    try:
        data = storage.load(doc.storage_key, doc.sha256)
    except storage.IntegrityError as exc:
        audit.record(db, user, "DOCUMENT_INTEGRITY_FAILURE", "document", doc.id, after={"error": str(exc)},
                     institution_id=doc.institution_id)
        db.commit()
        raise HTTPException(409, f"Integrity check failed: {exc}")
    audit.record(db, user, "DOCUMENT_DOWNLOADED", "document", doc.id, institution_id=doc.institution_id)
    db.commit()
    return Response(content=data, media_type=doc.content_type, headers={
        "Content-Disposition": f'inline; filename="{doc.original_filename}"',
        "X-Content-SHA256": doc.sha256, "X-Integrity": "verified",
    })


@router.get("/documents/{document_id}/ocr", summary="Full OCR output of a document (officers)")
def document_ocr(document_id: int, user: User = Depends(require_roles(Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER,
                                                                      Role.APPROVING_AUTHORITY, Role.ADMIN, Role.AUDITOR)),
                 db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return {"id": doc.id, "status": doc.ocr_status.value, "engine": doc.ocr_engine, "confidence": doc.ocr_confidence,
            "fields": doc.ocr_fields, "text": doc.ocr_text}


@router.post("/flags/{flag_id}/decide", summary="Human decision on a flag: CONFIRMED or DISMISSED (reason mandatory)")
def decide_flag(flag_id: int, body: FlagDecisionIn,
                user: User = Depends(require_roles(Role.SCRUTINY_OFFICER, Role.REGIONAL_OFFICER,
                                                   Role.APPROVING_AUTHORITY, Role.ADMIN)),
                db: Session = Depends(get_db)):
    flag = db.get(Flag, flag_id)
    if flag is None:
        raise HTTPException(404, "Flag not found")
    if body.decision not in (FlagStatus.CONFIRMED, FlagStatus.DISMISSED):
        raise HTTPException(422, "decision must be CONFIRMED or DISMISSED")
    inst: Instrument = get_instrument(db, flag.instrument_id, user)
    before = flag.status.value
    flag.status = body.decision
    flag.resolved_by = user.id
    flag.resolved_at = clock.now()
    flag.resolution_note = body.note
    inst.risk_score = rules.compute_risk(inst)
    lifecycle.log_event(db, inst, f"flag_{body.decision.value.lower()}", user, note=f"{flag.rule_id} {flag.title}: {body.note}",
                        audit_before={"flag_id": flag.id, "status": before},
                        audit_after={"flag_id": flag.id, "status": body.decision.value, "note": body.note})
    db.commit()
    return flag_view(flag, user)
