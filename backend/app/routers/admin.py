from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.enums import CaseStatus, Role
from app.models import AuditLog, Bank, ComplianceCase, Holiday, Institution, SystemConfig, User
from app.routers.common import scope_institution_ids
from app.schemas import (
    AdvanceClockIn,
    BankIn,
    BankOut,
    ComplianceCaseIn,
    ConfigUpdateIn,
    HolidayIn,
    InstitutionIn,
    InstitutionOut,
    RejectIn,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
)
from app.security import get_current_user, hash_password, require_roles
from app.services import audit, clock, config_service, monitor, rules

router = APIRouter(prefix="/admin", tags=["Admin & configuration"])
public = APIRouter(tags=["Masters (read)"])

ADMIN = require_roles(Role.ADMIN)


# ------------------------------ read masters ------------------------------ #
@public.get("/banks", response_model=list[BankOut], summary="Bank master (for dropdowns)")
def banks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.execute(select(Bank).order_by(Bank.name)).scalars().all()


@public.get("/institutions", response_model=list[InstitutionOut], summary="Institutions (scoped)")
def institutions(q: str | None = None, region: str | None = None, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    query = select(Institution).order_by(Institution.name)
    ids = scope_institution_ids(db, user)
    if ids is not None:
        query = query.where(Institution.id.in_(ids))
    if region:
        query = query.where(Institution.region == region)
    if q:
        query = query.where(Institution.name.ilike(f"%{q}%") | Institution.aicte_id.ilike(f"%{q}%"))
    return db.execute(query).scalars().all()


@public.get("/meta/enums", summary="All enum values (for frontend dropdowns / badges)")
def enums():
    from app import enums as E

    names = ["Role", "InstrumentStatus", "VerificationStatus", "TrustLevel", "FieldTrust", "DocType", "Purpose",
             "Severity", "FlagStatus", "DiscrepancyReason", "AlertType", "AlertStatus", "RefundStatus", "ReleaseGround"]
    from app.services.lifecycle import STATUS_LABEL
    from app.services.fields import BADGE

    return {
        **{n: [m.value for m in getattr(E, n)] for n in names},
        "status_labels": {k.value: v for k, v in STATUS_LABEL.items()},
        "field_badges": {k.value: v for k, v in BADGE.items()},
    }


@public.get("/meta/rules", summary="Discrepancy rule catalogue with current overrides")
def rule_catalogue(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ov = config_service.get(db, "rule_overrides") or {}
    return [{"rule_id": k, "code": v.code, "default_severity": v.severity.value, "description": v.description,
             "override": ov.get(k)} for k, v in rules.RULES.items()]


SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"
SAMPLE_META = {
    "fdr_demo_correct.pdf": {
        "label": "Valid SBI FDR Receipt (Rs 25,00,000)",
        "doc_type": "FDR_SCAN",
        "description": "Clean synthetic SBI FDR 40112233445 (IFSC SBIN0004321, Rs 25,00,000) matching the simulated bank record - verifies green.",
    },
    "fdr_demo_correct_scan.png": {
        "label": "Valid SBI FDR Scanned Image (.PNG)",
        "doc_type": "FDR_SCAN",
        "description": "Image of the same FDR, to test the image OCR path (needs Tesseract or Google Vision).",
    },
    "lien_letter_demo.pdf": {
        "label": "Bank Lien Marking Confirmation Letter",
        "doc_type": "LIEN_LETTER",
        "description": "Bank letter confirming lien marked in favour of AICTE.",
    },
    "undertaking_demo.pdf": {
        "label": "Institution Release / Refund Undertaking",
        "doc_type": "UNDERTAKING",
        "description": "Institution undertaking required before a Release / Refund request can proceed.",
    },
    "fdr_demo_tampered_words.pdf": {
        "label": "Tampered FDR - Words vs Figures Mismatch (Rule R15)",
        "doc_type": "FDR_SCAN",
        "description": "Figures say Rs 25,00,000 but words say 'Two Lakh Fifty Thousand'; the bank record says 2.5 lakh - triggers R15 and a bank mismatch.",
    },
    "fdr_demo_duplicate_number.pdf": {
        "label": "Duplicate FDR - Reused Across Institutions (Rule R09)",
        "doc_type": "FDR_SCAN",
        "description": "FDR number already registered under another institution - triggers CRITICAL R09.",
    },
}


@public.get("/meta/samples", summary="[DEMO] Synthetic sample documents available for 1-click loading")
def list_demo_samples():
    _demo_only()
    items = []
    if SAMPLES_DIR.exists():
        for name, meta in SAMPLE_META.items():
            fp = SAMPLES_DIR / name
            if fp.exists():
                items.append({"filename": name, "size_bytes": fp.stat().st_size, **meta})
    return items


@public.get("/meta/samples/{filename}", summary="[DEMO] Download a synthetic sample file by filename")
def get_demo_sample(filename: str):
    _demo_only()
    safe_name = Path(filename).name
    if safe_name != filename or safe_name not in SAMPLE_META:
        raise HTTPException(404, "Sample file not found")
    fp = SAMPLES_DIR / safe_name
    if not fp.exists():
        raise HTTPException(404, "Sample file not generated yet")
    media = "image/png" if safe_name.endswith(".png") else "application/pdf"
    return FileResponse(fp, media_type=media, filename=safe_name)


@public.get("/compliance-cases", summary="Compliance cases (block release while OPEN)")
def list_cases(institution_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(ComplianceCase).order_by(ComplianceCase.id.desc())
    ids = scope_institution_ids(db, user)
    if ids is not None:
        q = q.where(ComplianceCase.institution_id.in_(ids))
    if institution_id:
        q = q.where(ComplianceCase.institution_id == institution_id)
    return [{"id": c.id, "institution_id": c.institution_id, "title": c.title, "description": c.description,
             "status": c.status.value, "created_at": c.created_at, "closed_at": c.closed_at}
            for c in db.execute(q).scalars()]


@public.post("/compliance-cases", status_code=201)
def open_case(body: ComplianceCaseIn, user: User = Depends(require_roles(Role.ADMIN, Role.SCRUTINY_OFFICER,
                                                                       Role.REGIONAL_OFFICER, Role.APPROVING_AUTHORITY)),
              db: Session = Depends(get_db)):
    c = ComplianceCase(institution_id=body.institution_id, title=body.title, description=body.description,
                       opened_by=user.id, created_at=clock.now())
    db.add(c)
    db.flush()
    audit.record(db, user, "COMPLIANCE_CASE_OPENED", "compliance_case", c.id, after={"title": c.title},
                 institution_id=c.institution_id)
    db.commit()
    return {"id": c.id}


@public.post("/compliance-cases/{case_id}/close")
def close_case(case_id: int, body: RejectIn, user: User = Depends(require_roles(Role.ADMIN, Role.SCRUTINY_OFFICER,
                                                                              Role.REGIONAL_OFFICER, Role.APPROVING_AUTHORITY)),
               db: Session = Depends(get_db)):
    c = db.get(ComplianceCase, case_id)
    if c is None:
        raise HTTPException(404, "Not found")
    c.status = CaseStatus.CLOSED
    c.closed_at = clock.now()
    audit.record(db, user, "COMPLIANCE_CASE_CLOSED", "compliance_case", c.id, after={"note": body.note},
                 institution_id=c.institution_id)
    db.commit()
    return {"ok": True}


# --------------------------------- users ---------------------------------- #
@router.get("/users", response_model=list[UserOut])
def list_users(role: Role | None = None, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    q = select(User).order_by(User.id)
    if role:
        q = q.where(User.role == role)
    return db.execute(q).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreateIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    if db.execute(select(User).where(User.email == body.email.lower())).scalar():
        raise HTTPException(409, "Email already exists")
    if body.role == Role.INSTITUTION and not body.institution_id:
        raise HTTPException(422, "institution_id required for INSTITUTION users")
    if body.role == Role.REGIONAL_OFFICER and not body.region:
        raise HTTPException(422, "region required for REGIONAL_OFFICER")
    if body.role == Role.BANK and not body.bank_id:
        raise HTTPException(422, "bank_id required for BANK users")
    u = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(body.password),
             role=body.role, phone=body.phone, institution_id=body.institution_id, region=body.region,
             bank_id=body.bank_id, created_at=clock.now())
    db.add(u)
    db.flush()
    audit.record(db, user, "USER_CREATED", "user", u.id, after={"email": u.email, "role": u.role.value})
    db.commit()
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdateIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Not found")
    data = body.model_dump(exclude_unset=True)
    before = {k: getattr(u, k) for k in data if k != "password"}
    if "password" in data:
        u.password_hash = hash_password(data.pop("password"))
        u.failed_logins = 0
    for k, v in data.items():
        setattr(u, k, v)
    audit.record(db, user, "USER_UPDATED", "user", u.id, before=before, after={k: getattr(u, k) for k in data})
    db.commit()
    return u


@router.post("/users/{user_id}/unlock", response_model=UserOut)
def unlock_user(user_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Not found")
    u.failed_logins = 0
    audit.record(db, user, "USER_UNLOCKED", "user", u.id)
    db.commit()
    return u


# ------------------------------ institutions ------------------------------ #
@router.post("/institutions", response_model=InstitutionOut, status_code=201)
def create_institution(body: InstitutionIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    inst = Institution(**body.model_dump(), created_at=clock.now())
    db.add(inst)
    db.flush()
    audit.record(db, user, "INSTITUTION_CREATED", "institution", inst.id, after=body.model_dump(), institution_id=inst.id)
    db.commit()
    return inst


# --------------------------------- banks ---------------------------------- #
@router.post("/banks", response_model=BankOut, status_code=201)
def create_bank(body: BankIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    b = Bank(**body.model_dump(), created_at=clock.now())
    b.ifsc_prefix = b.ifsc_prefix.upper()
    db.add(b)
    db.flush()
    audit.record(db, user, "BANK_CREATED", "bank", b.id, after=body.model_dump())
    db.commit()
    return b


@router.patch("/banks/{bank_id}", response_model=BankOut)
def update_bank(bank_id: int, body: BankIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    b = db.get(Bank, bank_id)
    if b is None:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    audit.record(db, user, "BANK_UPDATED", "bank", b.id, after=body.model_dump())
    db.commit()
    return b


# -------------------------------- config ---------------------------------- #
@router.get("/config", summary="All configurable business rules")
def get_config(user: User = Depends(require_roles(Role.ADMIN, Role.AUDITOR)), db: Session = Depends(get_db)):
    rows = {r.key: r for r in db.execute(select(SystemConfig)).scalars()}
    return [{"key": k, "value": config_service.get(db, k), "description": spec["description"],
             "updated_at": rows[k].updated_at if k in rows else None}
            for k, spec in config_service.DEFAULT_CONFIG.items()]


@router.put("/config/{key}", summary="Change a rule (reminder offsets, escalation ladder, slabs, ...)")
def put_config(key: str, body: ConfigUpdateIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    if key == "clock_offset_days":
        raise HTTPException(422, "Use /admin/demo/clock to move the clock")
    try:
        before = config_service.get(db, key)
        config_service.set_value(db, key, body.value, user.id)
    except KeyError:
        raise HTTPException(404, "Unknown config key")
    audit.record(db, user, "CONFIG_CHANGED", "config", key, before={"value": before}, after={"value": body.value})
    db.commit()
    return {"key": key, "value": body.value}


@router.get("/holidays")
def list_holidays(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"day": h.day, "name": h.name} for h in db.execute(select(Holiday).order_by(Holiday.day)).scalars()]


@router.post("/holidays", status_code=201)
def add_holiday(body: HolidayIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    db.merge(Holiday(day=body.day, name=body.name))
    audit.record(db, user, "HOLIDAY_ADDED", "holiday", body.day.isoformat(), after={"name": body.name})
    db.commit()
    return {"ok": True}


# ---------------------------- jobs & demo tools ---------------------------- #
@router.post("/jobs/run", summary="Run the daily monitor + re-verification + escalations now")
def run_jobs(force_reverify: bool = False, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    result = monitor.run_all(db, reverify_force=force_reverify)
    audit.record(db, user, "JOBS_RUN_MANUALLY", "system", None, after={"transitions": len(result["daily"]["transitions"])})
    db.commit()
    return result


def _demo_only():
    if not settings.DEMO_MODE:
        raise HTTPException(403, "Demo tools are disabled (DEMO_MODE=false)")


@router.get("/demo/clock", summary="[DEMO] Current simulated date")
def get_clock(user: User = Depends(get_current_user)):
    return {"offset_days": clock.offset_days(), "today": clock.today(), "now": clock.now()}


@router.post("/demo/clock", summary="[DEMO] Time travel: shift the clock by N days and run all jobs, day by day")
def advance_clock(body: AdvanceClockIn, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    _demo_only()
    start = clock.offset_days()
    target = start + body.days
    timeline = []
    if body.run_jobs and body.days > 0:
        # walk day by day so reminders / escalations happen in the same order as in real life
        step = 1 if body.days <= 120 else max(1, body.days // 120)
        cur = start
        while cur < target:
            cur = min(target, cur + step)
            clock.set_offset_days(cur)
            res = monitor.run_all(db)
            if res["daily"]["transitions"] or res["escalations"] or res["daily"]["reminders"] or res["reverification"]["changed"]:
                timeline.append({"date": clock.today(), "transitions": res["daily"]["transitions"],
                                 "reminders": res["daily"]["reminders"], "escalations": res["escalations"],
                                 "alerts_opened": res["daily"]["alerts_opened"],
                                 "bank_changes": res["reverification"]["changed"]})
    clock.set_offset_days(target)
    config_service.set_value(db, "clock_offset_days", target, user.id)
    audit.record(db, user, "DEMO_CLOCK_SHIFTED", "system", None, before={"offset_days": start}, after={"offset_days": target})
    db.commit()
    return {"offset_days": target, "today": clock.today(), "events": timeline}


@router.post("/demo/clock/reset", summary="[DEMO] Reset clock to real time (does not undo state changes)")
def reset_clock(user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    _demo_only()
    clock.set_offset_days(0)
    config_service.set_value(db, "clock_offset_days", 0, user.id)
    db.commit()
    return {"offset_days": 0, "today": clock.today()}


@router.post("/demo/tamper-audit/{entry_id}",
             summary="[DEMO] Simulate an insider silently editing an audit row via SQL, then call /audit/verify")
def tamper(entry_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    _demo_only()
    row = db.get(AuditLog, entry_id)
    if row is None:
        raise HTTPException(404, "No such entry")
    backup = db.get(SystemConfig, "demo_tamper_backup")
    if backup is None:
        backup = SystemConfig(key="demo_tamper_backup", value={}, description="DEMO: original values of tampered rows")
        db.add(backup)
    backup.value = {**(backup.value or {}), str(entry_id): {"after": row.after, "actor_email": row.actor_email}}
    # raw SQL on purpose: this is what a malicious DBA would do (bypasses the application entirely)
    db.execute(text("UPDATE audit_log SET actor_email = :e WHERE id = :i"), {"e": "someone.else@aicte-demo.in", "i": entry_id})
    db.commit()
    return {"tampered_entry": entry_id, "next": "GET /api/v1/audit/verify"}


@router.post("/demo/tamper-audit/{entry_id}/restore", summary="[DEMO] Undo the simulated tampering")
def untamper(entry_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    _demo_only()
    backup = db.get(SystemConfig, "demo_tamper_backup")
    orig = (backup.value or {}).get(str(entry_id)) if backup else None
    if not orig:
        raise HTTPException(404, "Nothing to restore")
    db.execute(text("UPDATE audit_log SET actor_email = :e WHERE id = :i"), {"e": orig["actor_email"], "i": entry_id})
    backup.value = {k: v for k, v in backup.value.items() if k != str(entry_id)}
    db.commit()
    return {"restored": entry_id}


@router.post("/demo/reseed", summary="[DEMO] Reset database and storage back to clean golden demo dataset")
def reseed_demo(user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    _demo_only()
    db.close()
    from scripts.seed import seed
    clock.set_offset_days(0)
    seed(force=True)
    return {"reseeded": True, "today": clock.today(), "offset_days": clock.offset_days()}


