"""Document upload -> validate -> encrypt+store -> OCR -> field cross-check -> rules."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import DocType, OcrStatus
from app.models import Bank, Document, Instrument, User
from app.services import audit, config_service, fields, lifecycle, ocr, rules, storage

OCR_TYPES = (DocType.FDR_SCAN, DocType.RENEWAL_FDR)


def bank_list(db: Session) -> list[dict[str, str]]:
    return [{"name": b.name, "ifsc_prefix": b.ifsc_prefix} for b in db.execute(select(Bank)).scalars()]


def run_ocr(db: Session, data: bytes, content_type: str) -> ocr.OcrResult:
    min_conf = float(config_service.get(db, "ocr_min_confidence"))
    return ocr.run(data, content_type, bank_list(db), min_conf)


def cross_check(inst: Instrument, result: ocr.OcrResult) -> list[dict[str, Any]]:
    """Point-of-entry comparison of typed values vs document values."""
    rows = []
    for name in fields.TRACKED_FIELDS:
        doc_val = result.value(name)
        typed = fields.declared(inst, name)
        if doc_val is None:
            rows.append({"field": name, "label": fields.LABELS[name], "typed": typed, "document": None,
                         "status": "NOT_READ"})
            continue
        if typed is None:
            status = "PREFILL_AVAILABLE"
        else:
            status = "MATCH" if ocr.values_match(name, typed, doc_val) else "MISMATCH"
        rows.append({"field": name, "label": fields.LABELS[name], "typed": typed, "document": doc_val,
                     "confidence": result.fields[name]["confidence"], "status": status})
    if result.amount_in_words:
        fig = result.value("amount") or typed_amount(inst)
        rows.append({
            "field": "amount_in_words", "label": "Amount in words vs figures",
            "typed": fig, "document": result.amount_in_words["value"],
            "status": "MATCH" if (fig is None or ocr.values_match("amount", fig, result.amount_in_words["value"])) else "MISMATCH",
        })
    return rows


def typed_amount(inst: Instrument) -> str | None:
    return str(inst.amount) if inst.amount is not None else None


def upload(
    db: Session, *, user: User, institution_id: int, data: bytes, filename: str, doc_type: DocType,
    instrument: Instrument | None = None, refund_request_id: int | None = None,
) -> tuple[Document, ocr.OcrResult | None]:
    ctype = storage.validate_upload(data)
    key, digest = storage.save(data)
    doc = Document(
        institution_id=institution_id, instrument_id=instrument.id if instrument else None,
        refund_request_id=refund_request_id, doc_type=doc_type, original_filename=filename[:255],
        content_type=ctype, size_bytes=len(data), sha256=digest, storage_key=key, encrypted=True,
        uploaded_by=user.id,
    )
    result = None
    if doc_type in OCR_TYPES:
        result = run_ocr(db, data, ctype)
        doc.ocr_status = OcrStatus(result.status)
        doc.ocr_engine = result.engine
        doc.ocr_confidence = result.confidence
        doc.ocr_text = result.text[:20000] if result.text else None
        doc.ocr_fields = {**result.fields, **({"_amount_in_words": result.amount_in_words} if result.amount_in_words else {})}
    db.add(doc)
    db.flush()

    if instrument is not None:
        # supersede older docs of the same type (history retained, never deleted)
        for old in instrument.documents:
            if old.id != doc.id and old.doc_type == doc_type and not old.is_superseded:
                old.is_superseded = True
        if doc not in instrument.documents:
            instrument.documents.append(doc)
        if result is not None and result.fields:
            fields.apply_ocr(db, instrument, result.fields)
        lifecycle.log_event(
            db, instrument, "document_uploaded", user,
            note=f"{doc_type.value}: {filename}",
            data={"document_id": doc.id, "sha256": digest, "ocr_status": doc.ocr_status.value,
                  "ocr_engine": doc.ocr_engine},
        )
        rules.apply(db, instrument)
    else:
        audit.record(db, user, "DOCUMENT_UPLOADED", "document", doc.id,
                     after={"doc_type": doc_type.value, "sha256": digest, "refund_request_id": refund_request_id},
                     institution_id=institution_id)
    return doc, result
