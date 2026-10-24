"""Auto-generated discharge letter (PDF) to the issuing bank."""
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors
from sqlalchemy.orm import Session

from app.models import Instrument, RefundRequest, User
from app.services import clock


def discharge_letter(db: Session, rr: RefundRequest, inst: Instrument) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm)
    ss = getSampleStyleSheet()
    approver = db.get(User, rr.approved_by) if rr.approved_by else None
    today = clock.today().strftime("%d-%m-%Y")
    story = [
        Paragraph("<b>ALL INDIA COUNCIL FOR TECHNICAL EDUCATION</b>", ss["Title"]),
        Paragraph("Regulation Bureau - Security Deposit Cell", ss["Normal"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Ref: {rr.ref_number}&nbsp;&nbsp;&nbsp;&nbsp;Date: {today}", ss["Normal"]),
        Spacer(1, 4 * mm),
        Paragraph(f"To,<br/>The Branch Manager<br/>{inst.bank_name}, {inst.branch or ''}<br/>IFSC: {inst.ifsc}", ss["Normal"]),
        Spacer(1, 4 * mm),
        Paragraph(f"<b>Subject: Discharge of lien on Fixed Deposit Receipt No. {inst.fdr_number}</b>", ss["Normal"]),
        Spacer(1, 4 * mm),
        Paragraph(
            f"With reference to the above, AICTE hereby releases its lien on the Fixed Deposit described below, "
            f"held as security deposit of <b>{inst.institution.name}</b> (AICTE ID {inst.institution.aicte_id}). "
            f"The release has been sanctioned by the competent authority on the ground: "
            f"<i>{rr.ground.value.replace('_', ' ').title()}</i>.", ss["Normal"]),
        Spacer(1, 4 * mm),
    ]
    t = Table([
        ["FDR number", inst.fdr_number],
        ["Depositor", inst.depositor_name or inst.institution.name],
        ["Amount (INR)", f"{inst.amount:,.2f}" if inst.amount is not None else "-"],
        ["Issue date", inst.issue_date.strftime("%d-%m-%Y") if inst.issue_date else "-"],
        ["Maturity date", inst.maturity_date.strftime("%d-%m-%Y") if inst.maturity_date else "-"],
        ["Portal acknowledgement", inst.ack_number or "-"],
    ], colWidths=[55 * mm, 100 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
    story += [
        t, Spacer(1, 6 * mm),
        Paragraph("You are requested to remove the lien marked in favour of AICTE and confirm the same on the "
                  "SecureDeposit portal.", ss["Normal"]),
        Spacer(1, 12 * mm),
        Paragraph(f"Sanctioned by: {approver.full_name if approver else '-'} (Approving Authority)", ss["Normal"]),
        Paragraph("This letter is system-generated; its SHA-256 hash is recorded in the AICTE audit ledger.",
                  ss["Italic"]),
    ]
    doc.build(story)
    return buf.getvalue()
