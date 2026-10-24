"""OCR auto-fill and point-of-entry cross-check.

Pipeline:
  1. Digital PDF with a text layer  -> read text directly (PyMuPDF), no OCR needed.
  2. Scanned PDF / image            -> Google Vision (if GOOGLE_VISION_API_KEY set) else Tesseract.
  3. Regex + label-proximity parsing -> FDR number, bank, IFSC, amount (figures AND words),
                                        issue date, maturity date, lien, depositor.
Each field carries a confidence. Low confidence never silently passes - it routes to manual review.
"""
from __future__ import annotations

import base64
import io
import logging
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.config import settings

log = logging.getLogger("ocr")

FIELDS = ["fdr_number", "bank_name", "ifsc", "amount", "issue_date", "maturity_date", "lien_marked", "depositor_name"]


@dataclass
class OcrResult:
    status: str  # DONE | LOW_CONFIDENCE | UNAVAILABLE | FAILED
    engine: str | None
    confidence: float
    text: str
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    amount_in_words: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self, include_text: bool = False) -> dict[str, Any]:
        d = asdict(self)
        if not include_text:
            d["text"] = (self.text or "")[:2000]
        return d

    def value(self, name: str) -> Any:
        f = self.fields.get(name)
        return f["value"] if f else None


# --------------------------------------------------------------------------- #
# Text extraction engines
# --------------------------------------------------------------------------- #
def _pdf_text_and_images(data: bytes) -> tuple[str, list[bytes]]:
    try:
        import pymupdf as fitz
    except ImportError:  # older PyMuPDF
        import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    images: list[bytes] = []
    if len(text.strip()) < 40:  # scanned PDF: rasterise first 3 pages
        for page in list(doc)[:3]:
            images.append(page.get_pixmap(dpi=300).tobytes("png"))
    return text, images


def _google_vision(images: list[bytes]) -> tuple[str, float]:
    import httpx

    texts, confs = [], []
    for img in images:
        body = {"requests": [{"image": {"content": base64.b64encode(img).decode()},
                              "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]}]}
        r = httpx.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={settings.GOOGLE_VISION_API_KEY}",
            json=body, timeout=30,
        )
        r.raise_for_status()
        resp = r.json()["responses"][0]
        ann = resp.get("fullTextAnnotation") or {}
        texts.append(ann.get("text", ""))
        pages = ann.get("pages") or []
        confs.extend(p.get("confidence", 0.9) for p in pages)
    return "\n".join(texts), (sum(confs) / len(confs) if confs else 0.9)


def tesseract_available() -> bool:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    if settings.TESSERACT_CMD:
        return True
    return shutil.which("tesseract") is not None


def _tesseract(images: list[bytes]) -> tuple[str, float]:
    import pytesseract
    from PIL import Image, ImageOps

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    texts, confs = [], []
    for raw in images:
        img = ImageOps.grayscale(Image.open(io.BytesIO(raw)))
        if img.width < 1500:
            scale = 1500 / img.width
            img = img.resize((int(img.width * scale), int(img.height * scale)))
        texts.append(pytesseract.image_to_string(img))
        d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confs.extend(float(c) for c, w in zip(d["conf"], d["text"]) if w.strip() and float(c) >= 0)
    conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return "\n".join(texts), conf


def extract_text(data: bytes, content_type: str) -> tuple[str, str | None, float, list[str]]:
    warnings: list[str] = []
    images: list[bytes]
    if content_type == "application/pdf":
        text, images = _pdf_text_and_images(data)
        if text.strip() and not images:
            return text, "pdf-text-layer", 0.98, warnings
    else:
        images = [data]
    if settings.GOOGLE_VISION_API_KEY:
        try:
            t, c = _google_vision(images)
            return t, "google-vision", c, warnings
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Google Vision failed, falling back to Tesseract: {exc}")
    if tesseract_available():
        t, c = _tesseract(images)
        return t, "tesseract", c, warnings
    warnings.append("No OCR engine available (install Tesseract or set GOOGLE_VISION_API_KEY). Manual entry required.")
    return "", None, 0.0, warnings


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

DATE_RE = re.compile(
    r"(?P<d1>\d{1,2})[/\-.](?P<m1>\d{1,2})[/\-.](?P<y1>\d{4}|\d{2})\b"
    r"|(?P<d2>\d{1,2})(?:st|nd|rd|th)?[\s\-]+(?P<m2>[A-Za-z]{3,9})[,\s\-]+(?P<y2>\d{4})"
    r"|(?P<m3>[A-Za-z]{3,9})\s+(?P<d3>\d{1,2}),?\s+(?P<y3>\d{4})"
)


def _to_date(m: re.Match) -> date | None:
    try:
        if m.group("d1"):
            y = int(m.group("y1"))
            y = y + 2000 if y < 100 else y
            return date(y, int(m.group("m1")), int(m.group("d1")))
        if m.group("d2"):
            mon = MONTHS.get(m.group("m2")[:3].lower())
            return date(int(m.group("y2")), mon, int(m.group("d2"))) if mon else None
        if m.group("d3"):
            mon = MONTHS.get(m.group("m3")[:3].lower())
            return date(int(m.group("y3")), mon, int(m.group("d3"))) if mon else None
    except ValueError:
        return None
    return None


def _date_after_label(text: str, label_re: str) -> date | None:
    for lm in re.finditer(label_re, text, re.I):
        window = text[lm.end(): lm.end() + 60]
        dm = DATE_RE.search(window)
        if dm:
            d = _to_date(dm)
            if d:
                return d
    return None


UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
SCALES = {"thousand": 1_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000,
          "million": 1_000_000, "crore": 10_000_000, "crores": 10_000_000}


def words_to_number(s: str) -> int | None:
    """'Rupees Twenty Five Lakh Fifty Thousand Only' -> 2550000 (Indian numbering)."""
    total, current, found = 0, 0, False
    for t in re.findall(r"[a-z]+", s.lower()):
        if t in ("paise", "paisa"):
            break
        if t in UNITS:
            current += UNITS[t]
            found = True
        elif t in TENS:
            current += TENS[t]
            found = True
        elif t == "hundred":
            current = (current or 1) * 100
            found = True
        elif t in SCALES:
            total += (current or 1) * SCALES[t]
            current = 0
            found = True
    return total + current if found else None


def _amount(text: str) -> tuple[Decimal | None, bool]:
    pat = re.compile(
        r"(?P<label>principal(?:\s+amount)?|deposit\s+amount|amount\s+of\s+deposit|amount|sum\s+of)"
        r"\s*(?:\((?:in\s*)?(?:rs\.?|inr|₹)\))?\s*[:\-]?\s*(?:rs\.?|inr|₹)?\s*(?P<num>\d[\d,]*(?:\.\d{1,2})?)",
        re.I,
    )
    for m in pat.finditer(text):
        before = text[max(0, m.start() - 15): m.start()].lower()
        if "maturity" in before or "interest" in before:
            continue
        try:
            return Decimal(m.group("num").replace(",", "")), True
        except InvalidOperation:
            continue
    nums = [Decimal(n.replace(",", "")) for n in re.findall(r"(?:rs\.?|inr|₹)\s*(\d[\d,]*(?:\.\d{1,2})?)", text, re.I)]
    return (max(nums), False) if nums else (None, False)


def parse_fields(text: str, base_conf: float, banks: list[dict[str, str]] | None = None) -> tuple[dict, dict | None]:
    fields: dict[str, dict[str, Any]] = {}

    def put(name: str, value: Any, labelled: bool) -> None:
        if value is None or value == "":
            return
        fields[name] = {"value": value, "confidence": round(base_conf * (1.0 if labelled else 0.6), 3),
                        "method": "label" if labelled else "heuristic"}

    flat = re.sub(r"[ \t]+", " ", text)

    # FDR number
    m = re.search(
        r"(?:F\.?\s?D\.?\s?R\.?|F\.?\s?D\.?|S?TDR|Fixed\s+Deposit(?:\s+Receipt)?|Receipt|Deposit)\s*"
        r"(?:No\.?|Number|#)\s*[:\-.]?\s*([A-Z0-9][A-Z0-9\-/]{4,23})",
        flat, re.I,
    )
    if m and not DATE_RE.fullmatch(m.group(1)):
        put("fdr_number", m.group(1).upper().strip("-/"), True)

    # IFSC
    m = re.search(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", flat.upper())
    ifsc = m.group(1) if m else None
    put("ifsc", ifsc, True)

    # Bank
    bank_found = None
    for b in banks or []:
        if b["name"].lower() in flat.lower():
            bank_found = b["name"]
            put("bank_name", bank_found, True)
            break
    if not bank_found and ifsc:
        for b in banks or []:
            if b["ifsc_prefix"] == ifsc[:4]:
                put("bank_name", b["name"], False)
                break

    # Amount (figures)
    amt, labelled = _amount(flat)
    if amt is not None:
        put("amount", str(amt.quantize(Decimal("0.01"))), labelled)

    # Amount (words) - forgery signal when it disagrees with figures
    words = None
    wm = re.search(r"(?:rupees|rs\.?|inr)\s+([a-z\s\-]{4,160}?)\s+only", flat, re.I)
    if wm:
        n = words_to_number(wm.group(1))
        if n:
            words = {"text": wm.group(0).strip(), "value": str(Decimal(n).quantize(Decimal("0.01")))}

    # Dates
    issue = _date_after_label(flat, r"(?:date\s+of\s+(?:issue|deposit)|issue\s+date|deposit\s+date|value\s+date|opened\s+on|dated)")
    maturity = _date_after_label(flat, r"(?:date\s+of\s+maturity|maturity\s+date|due\s+date|matures\s+on|maturity\s+on)")
    put("issue_date", issue.isoformat() if issue else None, True)
    put("maturity_date", maturity.isoformat() if maturity else None, True)
    if not issue or not maturity:
        all_dates = sorted({d for d in (_to_date(x) for x in DATE_RE.finditer(flat)) if d})
        if len(all_dates) >= 2:
            if not issue:
                put("issue_date", all_dates[0].isoformat(), False)
            if not maturity:
                put("maturity_date", all_dates[-1].isoformat(), False)

    # Lien
    lm = re.search(r"lien", flat, re.I)
    if lm:
        ctx = flat[max(0, lm.start() - 60): lm.end() + 160].upper()
        negative = re.search(r"\bNO\s+LIEN\b|\bWITHOUT\s+LIEN\b|\bNOT\s+LIEN", ctx)
        put("lien_marked", not bool(negative), True)
        if "AICTE" in ctx or "ALL INDIA COUNCIL" in ctx:
            fields["lien_in_favour_of"] = {"value": "AICTE", "confidence": round(base_conf, 3), "method": "label"}

    # Depositor
    m = re.search(
        r"(?:depositor(?:'s)?\s*name|name\s+of\s+(?:the\s+)?depositor|in\s+the\s+name\s+of|account\s+holder)"
        r"\s*[:\-]?\s*([^\n]{3,80})",
        text, re.I,
    )
    if m:
        put("depositor_name", m.group(1).strip(" :-"), True)

    return fields, words


def run(data: bytes, content_type: str, banks: list[dict[str, str]] | None = None,
        min_confidence: float = 0.6) -> OcrResult:
    try:
        text, engine, conf, warnings = extract_text(data, content_type)
    except Exception as exc:  # noqa: BLE001
        log.exception("OCR failed")
        return OcrResult(status="FAILED", engine=None, confidence=0.0, text="", warnings=[str(exc)])
    if engine is None:
        return OcrResult(status="UNAVAILABLE", engine=None, confidence=0.0, text="", warnings=warnings)
    fields, words = parse_fields(text, conf, banks)
    status = "DONE" if conf >= min_confidence and fields else "LOW_CONFIDENCE"
    if not fields:
        warnings.append("No FDR fields could be read from the document.")
    return OcrResult(status=status, engine=engine, confidence=round(conf, 3), text=text, fields=fields,
                     amount_in_words=words, warnings=warnings)


# --------------------------------------------------------------------------- #
# Comparison helpers (shared by cross-check, rules and bank verification)
# --------------------------------------------------------------------------- #
def norm_id(v: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(v or "").upper())


def norm_value(field_name: str, v: Any) -> str | None:
    if v is None or v == "":
        return None
    if field_name in ("fdr_number", "ifsc"):
        return norm_id(v)
    if field_name == "amount":
        try:
            return str(Decimal(str(v).replace(",", "")).quantize(Decimal("0.01")))
        except InvalidOperation:
            return str(v)
    if field_name in ("issue_date", "maturity_date"):
        return v.isoformat() if isinstance(v, date) else str(v)[:10]
    if field_name == "lien_marked":
        return "true" if (v is True or str(v).lower() in ("true", "1", "yes", "y")) else "false"
    if field_name in ("bank_name", "depositor_name"):
        return re.sub(r"[^A-Z0-9]", "", str(v).upper())
    return str(v).strip().upper()


def values_match(field_name: str, a: Any, b: Any) -> bool:
    na, nb = norm_value(field_name, a), norm_value(field_name, b)
    if na is None or nb is None:
        return True  # nothing to compare
    if field_name == "depositor_name":
        return na in nb or nb in na
    return na == nb
