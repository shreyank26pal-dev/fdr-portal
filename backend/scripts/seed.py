"""Seed a realistic demo dataset by REPLAYING history through the real services.

Every instrument goes through the same code paths as in production (create -> upload ->
OCR -> submit -> bank verification -> approval -> renewal ...), with the simulated clock
set to the date each action happened. This gives genuine timelines, a valid hash-chained
audit log, real reminders/escalations, and a meaningful renewal-delay heatmap.

Usage (from backend/):
    python -m scripts.seed --reset      # wipe DB + storage and rebuild (about 1 minute)
    python -m scripts.seed --if-empty   # seed only when there are no users (used by docker)
"""
import argparse
import random
import shutil
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.config import settings

settings.SMTP_HOST = ""  # never send real e-mails while seeding

from app import models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.enums import (  # noqa: E402
    BankRecordStatus,
    DiscrepancyReason,
    DocType,
    FlagStatus,
    InstrumentStatus as S,
    Purpose,
    ReleaseGround,
    Role,
    Severity,
    VerificationChannel,
    VerificationRequestStatus,
)
from app.models import (  # noqa: E402
    Bank,
    BankLedgerRecord,
    ComplianceCase,
    Holiday,
    Institution,
    Instrument,
    Observation,
    User,
    VerificationRequest,
)
from app.security import hash_password  # noqa: E402
from app.services import (  # noqa: E402
    clock,
    config_service,
    documents,
    fields,
    lifecycle,
    monitor,
    refunds,
    renewals,
    rules,
    verification,
)
from scripts.sample_docs import fdr_pdf, lien_letter_pdf, pdf_to_png, undertaking_pdf  # noqa: E402

PASSWORD = "Password@123"
DOMAIN = "aicte-demo.in"
SAMPLES = Path(__file__).resolve().parent.parent / "samples"

REGIONS = {
    "NORTHERN": [("Uttar Pradesh", ["Lucknow", "Kanpur", "Noida"]), ("Bihar", ["Patna"]), ("Uttarakhand", ["Dehradun"])],
    "NORTH_WEST": [("Punjab", ["Ludhiana", "Mohali"]), ("Haryana", ["Gurugram"]), ("Rajasthan", ["Jaipur", "Kota"])],
    "WESTERN": [("Maharashtra", ["Pune", "Nagpur", "Nashik", "Mumbai"]), ("Goa", ["Panaji"])],
    "SOUTHERN": [("Tamil Nadu", ["Chennai", "Coimbatore", "Madurai"]), ("Kerala", ["Kochi"])],
    "SOUTH_WEST": [("Karnataka", ["Bengaluru", "Mysuru", "Mangaluru"])],
    "SOUTH_CENTRAL": [("Telangana", ["Hyderabad", "Warangal"]), ("Andhra Pradesh", ["Vijayawada", "Visakhapatnam"])],
    "EASTERN": [("West Bengal", ["Kolkata", "Durgapur"]), ("Odisha", ["Bhubaneswar"]), ("Assam", ["Guwahati"])],
    "CENTRAL": [("Madhya Pradesh", ["Bhopal", "Indore"]), ("Chhattisgarh", ["Raipur"]), ("Gujarat", ["Ahmedabad", "Vadodara"])],
}
PREFIXES = ["Aaranya", "Vidyanjali", "Shreshth", "Navonmesh", "Prajna", "Tejaswini", "Udaan", "Medhavi", "Pragyan",
            "Anvesha", "Srijan", "Abhyudaya", "Nirmaan", "Unnati", "Yantrika", "Gyanodaya", "Samarth", "Utkarsh",
            "Akshaya", "Dhruva"]
TYPES = [("Institute of Technology", "Engineering"), ("College of Engineering", "Engineering"),
         ("Institute of Management", "Management"), ("Polytechnic", "Diploma"), ("School of Pharmacy", "Pharmacy"),
         ("Institute of Architecture", "Architecture")]
BANKS = [
    ("State Bank of India", "SBI", "SBIN", True),
    ("Punjab National Bank", "PNB", "PUNB", True),
    ("Bank of Baroda", "BOB", "BARB", True),
    ("Canara Bank", "CANARA", "CNRB", False),
    ("HDFC Bank", "HDFC", "HDFC", True),
    ("ICICI Bank", "ICICI", "ICIC", True),
    ("Union Bank of India", "UNION", "UBIN", False),
    ("Axis Bank", "AXIS", "UTIB", True),
]
HOLIDAYS = [
    (date(2026, 1, 26), "Republic Day"), (date(2026, 8, 15), "Independence Day"),
    (date(2026, 10, 2), "Gandhi Jayanti"), (date(2026, 12, 25), "Christmas"),
    (date(2027, 1, 26), "Republic Day"), (date(2027, 8, 15), "Independence Day"),
    (date(2027, 10, 2), "Gandhi Jayanti"), (date(2027, 12, 25), "Christmas"),
]

rnd = random.Random(26265)


class Seeder:
    def __init__(self, db):
        self.db = db
        self.today = date.today()
        self.steps: list[tuple[date, int, str, callable]] = []
        self.seq = 0
        self.users: dict[str, User] = {}
        self.banks: dict[str, Bank] = {}
        self.insts: list[Institution] = []
        self.inst_user: dict[int, User] = {}
        self.pdf_cache: dict[int, bytes] = {}

    # ------------------------------------------------------------------ utils
    def at(self, d: date, label: str, fn) -> None:
        self.seq += 1
        self.steps.append((d, self.seq, label, fn))

    def set_day(self, d: date) -> None:
        clock.set_offset_days((d - self.today).days)

    @property
    def officer(self):
        return self.users["officer"]

    @property
    def approver(self):
        return self.users["approver"]

    # ---------------------------------------------------------------- masters
    def masters(self) -> None:
        db = self.db
        config_service.seed_defaults(db)
        for d, n in HOLIDAYS:
            db.add(Holiday(day=d, name=n))
        for name, code, prefix, api in BANKS:
            b = Bank(name=name, short_code=code, ifsc_prefix=prefix, api_enabled=api, api_available=True,
                     nodal_officer_email=f"nodal.{code.lower()}@bank-{DOMAIN}")
            db.add(b)
            self.banks[prefix] = b
        db.flush()

        regions = list(REGIONS)
        used = set()
        for i in range(40):
            if i == 0:
                region, state, city = "WESTERN", "Maharashtra", "Pune"
                name, itype = "Demo Institute of Technology, Pune", "Engineering"
            else:
                region = regions[i % len(regions)]
                state, cities = rnd.choice(REGIONS[region])
                city = rnd.choice(cities)
                while True:
                    p, (t, itype) = rnd.choice(PREFIXES), rnd.choice(TYPES)
                    name = f"{p} {t}, {city}"
                    if name not in used:
                        break
            used.add(name)
            inst = Institution(aicte_id=f"1-{4000000000 + i * 7919}", name=name, institution_type=itype,
                               state=state, district=city, region=region, email=f"office{i + 1}@college-{DOMAIN}",
                               phone=f"+9198{rnd.randint(10000000, 99999999)}")
            db.add(inst)
            self.insts.append(inst)
        db.flush()

        pw = hash_password(PASSWORD)

        def user(key, email, name, role, **kw):
            u = User(email=email, full_name=name, password_hash=pw, role=role,
                     phone=f"+9190{rnd.randint(10000000, 99999999)}", **kw)
            db.add(u)
            self.users[key] = u
            return u

        user("admin", f"admin@{DOMAIN}", "Bureau Head (Admin)", Role.ADMIN)
        user("officer", f"officer@{DOMAIN}", "R. Sharma (Scrutiny Officer)", Role.SCRUTINY_OFFICER)
        user("officer2", f"officer2@{DOMAIN}", "P. Iyer (Scrutiny Officer)", Role.SCRUTINY_OFFICER)
        user("approver", f"approver@{DOMAIN}", "Dr. A. Verma (Approving Authority)", Role.APPROVING_AUTHORITY)
        user("approver2", f"approver2@{DOMAIN}", "S. Khan (Approving Authority)", Role.APPROVING_AUTHORITY)
        user("auditor", f"auditor@{DOMAIN}", "C&AG Auditor (read-only)", Role.AUDITOR)
        for r in REGIONS:
            user(f"ro_{r}", f"ro.{r.lower()}@{DOMAIN}", f"Regional Officer - {r.replace('_', ' ').title()}",
                 Role.REGIONAL_OFFICER, region=r)
        user("bank_sbi", f"bank.sbi@{DOMAIN}", "SBI Nodal Officer", Role.BANK, bank_id=self.banks["SBIN"].id)
        user("bank_canara", f"bank.canara@{DOMAIN}", "Canara Bank Nodal Officer", Role.BANK, bank_id=self.banks["CNRB"].id)
        for i, inst in enumerate(self.insts):
            u = user(f"college{i + 1}", f"college{i + 1}@{DOMAIN}", f"Registrar, {inst.name}", Role.INSTITUTION,
                     institution_id=inst.id)
            self.inst_user[inst.id] = u
        db.flush()

    # -------------------------------------------------------------- primitives
    def new_spec(self, inst: Institution, bank: Bank, issue: date, maturity: date, amount: int,
                 purpose: Purpose = Purpose.EXTENSION_OF_APPROVAL, branch_ifsc: tuple[str, str] | None = None) -> dict:
        branch, ifsc = branch_ifsc or (inst.district or "Main", f"{bank.ifsc_prefix}0{rnd.randint(1000, 999999):06d}")
        return {"inst": inst, "bank": bank, "branch": f"{branch} Branch", "ifsc": ifsc,
                "fdr_number": str(rnd.randint(10 ** 10, 10 ** 11 - 1)), "amount": Decimal(amount),
                "issue": issue, "maturity": maturity, "purpose": purpose, "depositor": inst.name}

    def ledger(self, spec: dict, **override) -> BankLedgerRecord:
        rec = BankLedgerRecord(
            bank_id=spec["bank"].id, fdr_number=spec["fdr_number"], ifsc=spec["ifsc"],
            depositor_name=override.get("depositor", spec["depositor"]), amount=override.get("amount", spec["amount"]),
            issue_date=spec["issue"], maturity_date=override.get("maturity", spec["maturity"]),
            lien_marked=override.get("lien", True), lien_holder="AICTE, New Delhi" if override.get("lien", True) else None,
            status=override.get("status", BankRecordStatus.ACTIVE),
        )
        self.db.add(rec)
        spec["ledger"] = rec
        return rec

    def pdf_for(self, spec: dict, **kw) -> bytes:
        return fdr_pdf(bank_name=spec["bank"].name, branch=spec["branch"], ifsc=spec["ifsc"],
                       fdr_number=spec["fdr_number"], depositor=spec["depositor"], amount=spec["amount"],
                       issue_date=spec["issue"], maturity_date=spec["maturity"], **kw)

    def create(self, spec: dict, replaces: Instrument | None = None, lien: bool = True, **declared) -> Instrument:
        u = self.inst_user[spec["inst"].id]
        if replaces is not None:
            inst = renewals.start_renewal(self.db, replaces, u, {
                "fdr_number": spec["fdr_number"], "bank_name": spec["bank"].name, "branch": spec["branch"],
                "ifsc": spec["ifsc"], "amount": declared.get("amount", spec["amount"]), "issue_date": spec["issue"],
                "maturity_date": spec["maturity"], "lien_marked": lien, "lien_in_favour_of": "AICTE, New Delhi" if lien else None,
                "depositor_name": spec["depositor"]})
        else:
            inst = Instrument(
                institution_id=spec["inst"].id, created_by=u.id, status=S.DRAFT, purpose=spec["purpose"],
                fdr_number=spec["fdr_number"], bank_name=spec["bank"].name, bank_id=spec["bank"].id,
                branch=spec["branch"], ifsc=spec["ifsc"], depositor_name=spec["depositor"],
                amount=declared.get("amount", spec["amount"]), issue_date=spec["issue"], maturity_date=spec["maturity"],
                lien_marked=lien, lien_in_favour_of="AICTE, New Delhi" if lien else None,
            )
            self.db.add(inst)
            self.db.flush()
            fields.sync_declared(self.db, inst)
            lifecycle.log_event(self.db, inst, "created", u, note="Draft created")
        spec["obj"] = inst
        return inst

    def upload(self, spec: dict, pdf: bytes | None = None, lien_letter: bool = True) -> None:
        inst, u = spec["obj"], self.inst_user[spec["inst"].id]
        data = pdf or self.pdf_for(spec)
        self.pdf_cache[inst.id] = data
        dtype = DocType.RENEWAL_FDR if inst.replaces_instrument_id else DocType.FDR_SCAN
        documents.upload(self.db, user=u, institution_id=inst.institution_id, data=data,
                         filename=f"FDR_{spec['fdr_number']}.pdf", doc_type=dtype, instrument=inst)
        if lien_letter:
            documents.upload(self.db, user=u, institution_id=inst.institution_id,
                             data=lien_letter_pdf(spec["bank"].name, spec["branch"], spec["fdr_number"],
                                                  spec["depositor"], spec["amount"]),
                             filename=f"lien_{spec['fdr_number']}.pdf", doc_type=DocType.LIEN_LETTER, instrument=inst)

    def submit(self, spec: dict) -> None:
        inst, u = spec["obj"], self.inst_user[spec["inst"].id]
        lifecycle.transition(self.db, inst, "submit", u, note="Submitted by institution")
        inst.ack_number = f"AICTE/SD/{clock.today().year}/{inst.id:06d}"
        renewals.on_renewal_submitted(self.db, inst)
        rules.apply(self.db, inst)

    def pickup_verify(self, spec: dict) -> None:
        inst = spec["obj"]
        inst.assigned_officer_id = self.officer.id
        lifecycle.transition(self.db, inst, "pickup", self.officer, note=f"Picked up by {self.officer.full_name}")
        verification.verify_via_api(self.db, inst, self.officer)

    def bank_reply(self, spec: dict, found: bool = True) -> None:
        inst = spec["obj"]
        vr = self.db.execute(select(VerificationRequest).where(
            VerificationRequest.instrument_id == inst.id, VerificationRequest.status == VerificationRequestStatus.PENDING)
        ).scalar()
        if vr is None:
            return
        rec = spec.get("ledger")
        values = {} if not rec else {"amount": rec.amount, "issue_date": rec.issue_date, "maturity_date": rec.maturity_date,
                                     "lien_marked": rec.lien_marked, "depositor_name": rec.depositor_name,
                                     "fdr_number": rec.fdr_number, "ifsc": rec.ifsc}
        verification.respond(self.db, vr, found and rec is not None, values, None, VerificationChannel.BANK_EMAIL_LINK)

    def mark_verified(self, spec: dict) -> None:
        inst = spec["obj"]
        for f in inst.flags:  # officer reviews advisory flags
            if f.status == FlagStatus.OPEN and f.severity in (Severity.LOW, Severity.INFO):
                f.status, f.resolution_note, f.resolved_by = FlagStatus.DISMISSED, "Advisory only - noted", self.officer.id
        lifecycle.transition(self.db, inst, "mark_verified", self.officer, note="Scrutiny complete")

    def approve(self, spec: dict) -> None:
        inst = spec["obj"]
        lifecycle.transition(self.db, inst, "approve", self.approver, note="Approved")
        renewals.on_renewal_approved(self.db, inst, self.approver)
        prev = spec.get("prev")
        if prev and prev.get("ledger"):
            prev["ledger"].status = BankRecordStatus.CLOSED

    def full_flow(self, spec: dict, submit_day: date, replaces_spec: dict | None = None, stop: str = "ACTIVE") -> None:
        """Schedule create -> ... -> approve for one instrument."""
        if replaces_spec:
            spec["prev"] = replaces_spec
        no_api = not spec["bank"].api_enabled
        self.at(submit_day, "create+submit", lambda: (
            self.create(spec, replaces=replaces_spec["obj"] if replaces_spec else None),
            self.upload(spec), self.submit(spec)))
        if stop == "SUBMITTED":
            return
        self.at(submit_day + timedelta(days=2), "pickup+verify", lambda: self.pickup_verify(spec))
        if no_api:
            self.at(submit_day + timedelta(days=4), "bank reply", lambda: self.bank_reply(spec))
        if stop == "UNDER_SCRUTINY":
            return
        self.at(submit_day + timedelta(days=5), "verified", lambda: self.mark_verified(spec))
        if stop == "VERIFIED":
            return
        self.at(submit_day + timedelta(days=7), "approve", lambda: self.approve(spec))

    # ------------------------------------------------------------------ plans
    def plan(self) -> None:
        T = self.today
        api_banks = [b for b in self.banks.values() if b.api_enabled]
        all_banks = list(self.banks.values())
        late = {1, 2, 3, 4, 5, 12, 13, 14, 15, 16}
        very_late = {1, 2, 17, 18}

        def delay_for(i):
            if i in very_late:
                return rnd.randint(30, 60)
            if i in late:
                return rnd.randint(8, 35)
            return rnd.randint(-15, -1)

        finals = {0: 95, 1: -45, 2: -25, 3: -8, 4: 12, 5: 20, 6: 27, 7: 40, 8: 55, 9: 70, 10: 80, 11: 88}
        self.final_specs: dict[int, dict] = {}
        for i, inst in enumerate(self.insts):
            L = 3 if i < 24 else (2 if i < 34 else 1)
            bank = self.banks["SBIN"] if i == 0 else rnd.choice(all_banks if i % 5 else api_banks)
            ifsc = f"{bank.ifsc_prefix}0{rnd.randint(1000, 999999):06d}"
            branch = (inst.district or "Main", ifsc)
            mf = T + timedelta(days=finals.get(i, rnd.randint(100, 700)))
            # build backwards
            links = []
            for k in range(L, 0, -1):
                tenure = rnd.randint(365, 456)
                if k == L:
                    tenure = max(tenure, (mf - T).days + rnd.randint(30, 120))
                issue = mf - timedelta(days=tenure)
                sub = issue + timedelta(days=rnd.randint(3, 12))
                links.insert(0, {"issue": issue, "maturity": mf, "submit": sub})
                if k > 1:
                    mf = sub + timedelta(days=30 - delay_for(i))
            amount = rnd.choice([500000, 750000, 1000000, 1500000, 2500000])
            prev = None
            for k, ln in enumerate(links):
                spec = self.new_spec(inst, bank, ln["issue"], ln["maturity"], amount if k else amount, branch_ifsc=branch)
                self.ledger(spec)
                self.full_flow(spec, ln["submit"], replaces_spec=prev)
                prev = spec
            self.final_specs[i] = prev

        # ---- additional securities (single instrument, active, far maturity) ----
        self.extra: dict[int, dict] = {}
        for i in (0, 7, 20, 21, 22, 25):
            inst = self.insts[i]
            bank = self.banks["SBIN"] if i == 0 else rnd.choice(api_banks)
            issue = T - timedelta(days=rnd.randint(200, 400))
            spec = self.new_spec(inst, bank, issue, issue + timedelta(days=rnd.randint(700, 1100)),
                                 rnd.choice([500000, 1000000, 1500000]), Purpose.INCREASE_IN_INTAKE)
            self.ledger(spec)
            self.full_flow(spec, issue + timedelta(days=4))
            self.extra[i] = spec

        # ---- release / refund requests ----
        def refund_flow(i: int, start: int, upto: str, ground=ReleaseGround.PROGRAMME_DISCONTINUED):
            spec = self.extra[i]
            st = {}

            def create():
                u = self.inst_user[spec["inst"].id]
                rr = refunds.create(self.db, spec["obj"], u, ground, "Programme discontinued from this academic year")
                documents.upload(self.db, user=u, institution_id=rr.institution_id,
                                 data=undertaking_pdf(spec["inst"].name, spec["fdr_number"]),
                                 filename="undertaking.pdf", doc_type=DocType.UNDERTAKING, refund_request_id=rr.id)
                refunds.recheck(self.db, rr, u)
                st["rr"] = rr

            self.at(T + timedelta(days=start), "refund create", create)
            order = ["UNDER_REVIEW", "RECOMMENDED", "APPROVED", "PROCESSED"]
            fns = {
                "UNDER_REVIEW": lambda: refunds.start_review(self.db, st["rr"], self.officer, "Scrutiny started"),
                "RECOMMENDED": lambda: refunds.recommend(self.db, st["rr"], self.officer, "All conditions met"),
                "APPROVED": lambda: refunds.approve(self.db, st["rr"], self.approver, "Sanctioned"),
                "PROCESSED": lambda: refunds.process(self.db, st["rr"], self.officer, "Discharge letter sent"),
            }
            if upto == "REQUESTED":
                return
            for n, step in enumerate(order):
                self.at(T + timedelta(days=start + 2 + n * 2), f"refund {step}", fns[step])
                if step == upto:
                    break

        refund_flow(20, -120, "PROCESSED")
        refund_flow(21, -6, "UNDER_REVIEW")
        refund_flow(22, -10, "RECOMMENDED")
        refund_flow(25, -1, "REQUESTED")
        # institution 7: compliance case open -> request BLOCKED
        self.at(T - timedelta(days=30), "compliance case", lambda: self.db.add(ComplianceCase(
            institution_id=self.insts[7].id, title="Pending fee reconciliation (AY 2025-26)",
            description="Excess intake fee reconciliation pending", opened_by=self.officer.id, created_at=clock.now())))
        refund_flow(7, -2, "REQUESTED")
        self.at(T - timedelta(days=10), "compliance case 2", lambda: self.db.add(ComplianceCase(
            institution_id=self.insts[2].id, title="Show-cause: lapsed security deposit",
            opened_by=self.officer.id, created_at=clock.now())))

        # ---- verification pipeline ----
        def pipe_spec(i, days_ago_issue=40, bank=None, purpose=Purpose.EXTENSION_OF_APPROVAL, amount=None):
            inst = self.insts[i]
            b = bank or rnd.choice(api_banks)
            issue = T - timedelta(days=days_ago_issue)
            return self.new_spec(inst, b, issue, issue + timedelta(days=rnd.randint(400, 800)),
                                 amount or rnd.choice([500000, 1000000, 2500000]), purpose)

        for i, ago in zip((26, 27, 28, 29, 30), (1, 2, 5, 8, 12)):
            s = pipe_spec(i, ago + 20)
            self.ledger(s)
            self.full_flow(s, T - timedelta(days=ago), stop="SUBMITTED")
        s = pipe_spec(31, 30)
        self.ledger(s)
        self.full_flow(s, T - timedelta(days=6), stop="SUBMITTED")
        self.at(T - timedelta(days=3), "pickup only", lambda s=s: (
            setattr(s["obj"], "assigned_officer_id", self.officer.id),
            lifecycle.transition(self.db, s["obj"], "pickup", self.officer)))
        s = pipe_spec(32, 30)  # bank says a different amount
        self.ledger(s, amount=s["amount"] - Decimal(400000))
        self.full_flow(s, T - timedelta(days=9), stop="UNDER_SCRUTINY")
        s = pipe_spec(33, 25, bank=self.banks["CNRB"])  # no API -> email link still pending
        self.ledger(s)
        self.at(T - timedelta(days=5), "create+submit", lambda s=s: (self.create(s), self.upload(s), self.submit(s)))
        self.at(T - timedelta(days=3), "pickup+link", lambda s=s: self.pickup_verify(s))
        s = pipe_spec(34, 35)  # no ledger record -> NOT_FOUND
        self.full_flow(s, T - timedelta(days=7), stop="UNDER_SCRUTINY")

        for i, ago, reason, note in ((35, 22, DiscrepancyReason.WRONG_AMOUNT, "Amount on FDR differs from the form"),
                                     (36, 5, DiscrepancyReason.LIEN_NOT_MARKED, "Lien letter not in favour of AICTE")):
            s = pipe_spec(i, ago + 25)
            self.ledger(s)
            self.full_flow(s, T - timedelta(days=ago + 3), stop="UNDER_SCRUTINY")

            def disc(s=s, reason=reason, note=note):
                self.db.add(Observation(instrument_id=s["obj"].id, author_id=self.officer.id, reason_code=reason.value,
                                        note=note, created_at=clock.now()))
                lifecycle.transition(self.db, s["obj"], "raise_discrepancy", self.officer, note=note,
                                     data={"reason_code": reason.value})
            self.at(T - timedelta(days=ago), "discrepancy", disc)

        for i in (37, 38):
            s = pipe_spec(i, 45)
            self.ledger(s)
            self.full_flow(s, T - timedelta(days=12), stop="VERIFIED")
        for i in (24, 39):
            s = pipe_spec(i, 10)
            self.at(T - timedelta(days=1), "draft", lambda s=s: self.create(s))

        # ---- fraud / anomaly scenarios ----
        victim = self.final_specs[15]
        dup = self.new_spec(self.insts[10], victim["bank"], T - timedelta(days=50), T + timedelta(days=500), 1000000,
                            branch_ifsc=(victim["branch"].replace(" Branch", ""), victim["ifsc"]))
        dup["fdr_number"] = victim["fdr_number"]
        self.at(T - timedelta(days=3), "duplicate FDR", lambda: (self.create(dup), self.upload(dup), self.submit(dup)))

        src = self.final_specs[16]
        reuse = pipe_spec(11, 30)
        self.ledger(reuse)
        self.at(T - timedelta(days=2), "reused document", lambda: (
            self.create(reuse), self.upload(reuse, pdf=self.pdf_cache[src["obj"].id]), self.submit(reuse)))

        tam = pipe_spec(13, 20, bank=self.banks["SBIN"], amount=2500000)
        self.ledger(tam, amount=Decimal(250000))
        self.at(T - timedelta(days=1), "tampered amount", lambda: (
            self.create(tam), self.upload(tam, pdf=self.pdf_for(tam, words_override="Two Lakh Fifty Thousand")),
            self.submit(tam)))

        low = pipe_spec(14, 30, purpose=Purpose.NEW_APPROVAL, amount=500000)
        self.ledger(low)
        self.at(T - timedelta(days=6), "low amount", lambda: (self.create(low), self.upload(low), self.submit(low)))

        # ---- premature encashment, caught by continuous re-verification ----
        victim_enc = next(self.final_specs[i] for i in range(17, 24) if self.final_specs[i]["bank"].api_enabled)
        self.at(T - timedelta(days=4), "bank encashes FDR", lambda: setattr(
            victim_enc["ledger"], "status", BankRecordStatus.ENCASHED))

        # ---- the daily monitor runs every 7 days over the last 20 weeks, then today ----
        for d in range(-140, 0, 7):
            self.at(T + timedelta(days=d), "monitor", lambda: monitor.run_all(self.db))

    def run(self) -> None:
        self.steps.sort(key=lambda s: (s[0], s[1]))
        n = len(self.steps)
        t0 = time.time()
        for k, (d, _, label, fn) in enumerate(self.steps, 1):
            if d > self.today:
                d = self.today
            self.set_day(d)
            try:
                fn()
                self.db.flush()
            except Exception:
                print(f"\n!! step failed on {d} ({label})", file=sys.stderr)
                raise
            if k % 50 == 0:
                self.db.commit()
                print(f"  {k}/{n} steps ({time.time() - t0:.0f}s)", flush=True)
        self.db.commit()
        clock.set_offset_days(0)
        monitor.run_all(self.db, reverify_force=True)
        self.db.commit()

    # ------------------------------------------------------------ demo files
    def demo_samples(self) -> None:
        """Files for the live demo + matching (simulated) bank records."""
        SAMPLES.mkdir(exist_ok=True)
        T = self.today
        inst = self.insts[0]
        sbi = self.banks["SBIN"]
        good = self.new_spec(inst, sbi, T - timedelta(days=7), T - timedelta(days=7) + timedelta(days=3 * 365),
                             2500000, Purpose.EXTENSION_OF_APPROVAL, branch_ifsc=("Pune Main", "SBIN0004321"))
        good["fdr_number"] = "40112233445"
        self.ledger(good)
        pdf = self.pdf_for(good)
        (SAMPLES / "fdr_demo_correct.pdf").write_bytes(pdf)
        (SAMPLES / "fdr_demo_correct_scan.png").write_bytes(pdf_to_png(pdf))
        (SAMPLES / "lien_letter_demo.pdf").write_bytes(
            lien_letter_pdf(sbi.name, good["branch"], good["fdr_number"], inst.name, good["amount"]))
        (SAMPLES / "undertaking_demo.pdf").write_bytes(undertaking_pdf(inst.name, good["fdr_number"]))

        tam = dict(good, fdr_number="40112233999")
        self.ledger(tam, amount=Decimal(250000))
        (SAMPLES / "fdr_demo_tampered_words.pdf").write_bytes(self.pdf_for(tam, words_override="Two Lakh Fifty Thousand"))

        victim = self.final_specs[15]
        dup = dict(victim, inst=inst, depositor=inst.name)
        (SAMPLES / "fdr_demo_duplicate_number.pdf").write_bytes(self.pdf_for(dup))
        self.db.commit()
        (SAMPLES / "README.md").write_text(
            "# Demo files (synthetic)\n\n"
            "Generated by `python -m scripts.seed --reset`. Log in as `college1@aicte-demo.in` / `Password@123`.\n\n"
            "| File | What it demonstrates |\n|---|---|\n"
            f"| fdr_demo_correct.pdf | Clean FDR {good['fdr_number']} (SBI, IFSC SBIN0004321, Rs 25,00,000). OCR auto-fill + bank API -> all fields Bank-verified. Type amount 250000 instead to see the OCR mismatch flag. |\n"
            "| fdr_demo_correct_scan.png | Same FDR as an image -> Tesseract / Google Vision OCR path. |\n"
            "| lien_letter_demo.pdf | Lien letter (required document). |\n"
            "| fdr_demo_tampered_words.pdf | Figures say 25 lakh, words say 2.5 lakh, bank says 2.5 lakh -> R15 + bank mismatch. |\n"
            f"| fdr_demo_duplicate_number.pdf | FDR {victim['fdr_number']} already registered by {victim['inst'].name} -> R09 duplicate across institutions. |\n"
            "| undertaking_demo.pdf | Undertaking for a release request. |\n"
        )


def seed(force: bool = False, if_empty: bool = False) -> None:
    """Programmatic entry point (used by POST /admin/demo/reseed). force=True wipes and rebuilds."""
    if force:
        print("Dropping all tables ...")
        Base.metadata.drop_all(bind=engine)
        shutil.rmtree(settings.STORAGE_DIR, ignore_errors=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.execute(select(User.id).limit(1)).scalar():
            if if_empty or not force:
                print("Database already has data - skipping seed (use --reset to rebuild).")
                return
        t0 = time.time()
        rnd.seed(26265)
        s = Seeder(db)
        print("Masters ...")
        s.masters()
        db.commit()
        print("Planning history ...")
        s.plan()
        print(f"Replaying {len(s.steps)} steps through the real services ...")
        s.run()
        s.demo_samples()
        n = db.query(Instrument).count()
        print(f"Done in {time.time() - t0:.0f}s: {len(s.insts)} institutions, {n} instruments.")
        print(f"Login with any demo account, password: {PASSWORD}  (see README)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop everything and re-seed")
    ap.add_argument("--if-empty", action="store_true", help="seed only if no users exist")
    args = ap.parse_args()
    seed(force=args.reset, if_empty=args.if_empty)


if __name__ == "__main__":
    main()
