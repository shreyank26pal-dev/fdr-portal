"""Generate realistic (synthetic) FDR receipts, lien letters and undertakings as PDF / PNG.

Used by the seed script and to produce the files in backend/samples/ for the live demo.
"""
import io
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
        "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    return ONES[n] if n < 20 else (TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))


def _three(n: int) -> str:
    h, r = divmod(n, 100)
    return ((ONES[h] + " Hundred" + (" " if r else "")) if h else "") + (_two(r) if r else "")


def indian_words(n: int) -> str:
    """2550000 -> 'Twenty Five Lakh Fifty Thousand'."""
    if n == 0:
        return "Zero"
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(_three(crore) + " Crore")
    if lakh:
        parts.append(_two(lakh) + " Lakh")
    if thousand:
        parts.append(_two(thousand) + " Thousand")
    if n:
        parts.append(_three(n))
    return " ".join(parts)


def indian_commas(v: Decimal | int | float) -> str:
    v = Decimal(str(v)).quantize(Decimal("0.01"))
    whole, frac = str(v).split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{whole}.{frac}"


def fdr_pdf(*, bank_name: str, branch: str, ifsc: str, fdr_number: str, depositor: str, amount: Decimal | int,
            issue_date: date, maturity_date: date, rate: float = 7.10, lien_aicte: bool = True,
            words_override: str | None = None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFillColor(colors.HexColor("#0B3D91"))
    c.rect(0, h - 38 * mm, w, 38 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(20 * mm, h - 18 * mm, bank_name)
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, h - 26 * mm, f"Branch: {branch}    IFSC: {ifsc}")
    c.drawString(20 * mm, h - 32 * mm, "SPECIMEN - SYNTHETIC DOCUMENT FOR SIH PROTOTYPE")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(w / 2, h - 52 * mm, "FIXED DEPOSIT RECEIPT")
    words = words_override or indian_words(int(Decimal(str(amount))))
    lines = [
        ("FDR No.", fdr_number),
        ("Depositor Name", depositor),
        ("Date of Issue", issue_date.strftime("%d/%m/%Y")),
        ("Maturity Date", maturity_date.strftime("%d/%m/%Y")),
        ("Principal Amount", f"Rs. {indian_commas(amount)}"),
        ("Amount in words", f"Rupees {words} Only"),
        ("Rate of Interest", f"{rate:.2f}% p.a."),
        ("Interest Payout", "Cumulative (re-invested quarterly)"),
    ]
    y = h - 70 * mm
    for label, value in lines:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(22 * mm, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(70 * mm, y, value)
        y -= 9 * mm
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 11)
    if lien_aicte:
        c.drawString(22 * mm, y, "LIEN: Lien marked in favour of AICTE, New Delhi (All India Council for Technical Education).")
        y -= 6 * mm
        c.setFont("Helvetica", 9)
        c.drawString(22 * mm, y, "This deposit shall not be withdrawn or pledged without written consent of AICTE.")
    else:
        c.drawString(22 * mm, y, "Lien status: No lien recorded on this deposit.")
    c.setFont("Helvetica", 9)
    c.drawString(22 * mm, 40 * mm, "Authorised Signatory")
    c.line(22 * mm, 45 * mm, 70 * mm, 45 * mm)
    c.drawString(130 * mm, 40 * mm, "Branch Manager")
    c.line(130 * mm, 45 * mm, 180 * mm, 45 * mm)
    c.drawString(22 * mm, 20 * mm, "Non-transferable. Subject to the bank's terms for term deposits.")
    c.showPage()
    c.save()
    return buf.getvalue()


def letter_pdf(title: str, body_lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, h - 25 * mm, title)
    c.setFont("Helvetica", 10)
    y = h - 40 * mm
    for line in body_lines:
        c.drawString(20 * mm, y, line)
        y -= 6 * mm
    c.drawString(20 * mm, 40 * mm, "SPECIMEN - SYNTHETIC DOCUMENT FOR SIH PROTOTYPE")
    c.showPage()
    c.save()
    return buf.getvalue()


def lien_letter_pdf(bank_name: str, branch: str, fdr_number: str, depositor: str, amount) -> bytes:
    return letter_pdf(f"{bank_name} - Lien Marking Confirmation", [
        "To: The Member Secretary, AICTE, Nelson Mandela Marg, New Delhi",
        f"We confirm that lien has been marked in favour of AICTE on FDR No. {fdr_number}",
        f"held by {depositor} for Rs. {indian_commas(amount)} at our {branch} branch.",
        "The deposit will not be released without a discharge letter from AICTE.",
        "", "Branch Manager",
    ])


def undertaking_pdf(institution: str, fdr_number: str) -> bytes:
    return letter_pdf("Undertaking for release of security deposit", [
        f"We, {institution}, request release of the security deposit FDR No. {fdr_number}.",
        "We undertake that no compliance requirement is pending with AICTE and that",
        "any dues found later shall be paid by the institution.",
        "", "Principal / Director (with seal)",
    ])


def pdf_to_png(pdf: bytes, dpi: int = 200) -> bytes:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    doc = fitz.open(stream=pdf, filetype="pdf")
    return doc[0].get_pixmap(dpi=dpi).tobytes("png")
