"""Encrypted document storage with integrity verification.

* Files are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256).
* SHA-256 of the ORIGINAL bytes is stored in the DB at upload and re-checked on
  every download, so a swapped / altered file is detected.
* Basic upload hygiene: type sniffing by magic bytes, size limit, rejection of
  PDFs carrying active content (JavaScript / Launch actions).

Local disk is used for the prototype; the interface maps 1:1 to S3/MinIO.
"""
import base64
import hashlib
import re
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.services import clock


class UploadRejected(Exception):
    pass


class IntegrityError(Exception):
    pass


def _fernet() -> Fernet:
    key = settings.FILE_ENCRYPTION_KEY
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.JWT_SECRET.encode()).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


ALLOWED = {
    "application/pdf": (b"%PDF",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


def sniff_content_type(data: bytes) -> str | None:
    for ctype, magics in ALLOWED.items():
        if any(data.startswith(m) for m in magics):
            return ctype
    return None


# A PDF name token like /JS must be followed by a delimiter, otherwise "/JSxyz" or random bytes match.
_ACTIVE_NAME = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFiles?)(?=[\s/<>\[\]()]|$)")


def pdf_has_active_content(data: bytes) -> bool:
    """Inspect the PDF's object dictionaries (decompressed) for scripts, launch actions or embedded files.

    Scanning raw bytes gives false positives, because compressed streams can contain any byte
    sequence. So we parse the document with PyMuPDF and only look at dictionary source text.
    """
    try:
        try:
            import pymupdf as fitz
        except ImportError:  # older PyMuPDF
            import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.embfile_count():
            return True
        for xref in range(1, doc.xref_length()):
            try:
                src = doc.xref_object(xref, compressed=False)
            except Exception:  # noqa: BLE001
                continue
            if _ACTIVE_NAME.search(src.encode("latin-1", "ignore")):
                return True
        return False
    except Exception:  # noqa: BLE001 - unparseable PDF: fall back to a conservative byte scan
        return bool(_ACTIVE_NAME.search(data))


def validate_upload(data: bytes) -> str:
    if not data:
        raise UploadRejected("Empty file")
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise UploadRejected(f"File larger than {settings.MAX_UPLOAD_MB} MB")
    ctype = sniff_content_type(data)
    if ctype is None:
        raise UploadRejected("Only PDF, PNG and JPEG files are accepted")
    if ctype == "application/pdf" and pdf_has_active_content(data):
        raise UploadRejected("PDF contains active content (JavaScript / launch actions) and was blocked")
    return ctype


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(data: bytes) -> tuple[str, str]:
    """Encrypt and store. Returns (storage_key, sha256_of_plaintext)."""
    digest = sha256_hex(data)
    now = clock.now()
    key = f"{now:%Y/%m}/{uuid.uuid4().hex}.bin"
    path = Path(settings.STORAGE_DIR) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_fernet().encrypt(data))
    return key, digest


def load(storage_key: str, expected_sha256: str) -> bytes:
    path = Path(settings.STORAGE_DIR) / storage_key
    if not path.exists():
        raise IntegrityError("Stored file is missing")
    try:
        data = _fernet().decrypt(path.read_bytes())
    except InvalidToken as exc:
        raise IntegrityError("Stored file failed decryption / authentication (tampered or wrong key)") from exc
    if sha256_hex(data) != expected_sha256:
        raise IntegrityError("SHA-256 mismatch: the stored file is not the file that was uploaded")
    return data
