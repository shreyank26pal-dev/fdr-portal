# SecureDeposit: AICTE Security Deposit / FDR Portal

**SIH26265: Streamline of Security Deposit/FDR Portal** (AICTE, Ministry of Education)

This is one portal that covers the full life of every Fixed Deposit Receipt an institution gives AICTE: submission, OCR cross-check, bank verification, approval, maturity monitoring, renewal, and release. Every step is recorded in a tamper-evident audit trail.

This repository contains the **complete backend** (FastAPI + PostgreSQL). The Next.js frontend goes in `frontend/`. See [`docs/API.md`](docs/API.md) for the screen-by-screen API guide.

---

## 1. Quick start (Docker, recommended)

You need **Docker Desktop**.

```bash
docker compose up --build
```

The first start builds the image and seeds the demo data (about 30 s). Then open:

| What | URL |
|---|---|
| API docs (Swagger, try every endpoint) | http://localhost:8000/docs |
| Health / OCR status | http://localhost:8000/health |
| Email inbox (every email the portal sends) | http://localhost:8025 |

To reset the demo to a clean state at any time:

```bash
docker compose exec api python -m scripts.seed --reset
```

### Without Docker (SQLite, simplest on Windows)

You need **Python 3.11+** and **Node.js 18+**.

```powershell
# one-time setup
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
"DATABASE_URL=sqlite:///./fdr_portal.db`nSMTP_HOST=`nSTORAGE_DIR=./storage" | Out-File -Encoding ascii .env
.venv\Scripts\python -m scripts.seed --reset
cd ..\frontend
npm install
cd ..

# every time
powershell -ExecutionPolicy Bypass -File .\start-securedeposit.ps1
```

This opens the frontend at http://localhost:5173 and the API at http://127.0.0.1:8000/docs. Emails are logged as SIMULATED; the Mailpit inbox is only available with Docker.

OCR for PNG/JPG scans needs Tesseract (UB-Mannheim build). After installing it, add `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` to `backend/.env`. Digital PDFs work without it.

### Tests

```bash
cd backend
pytest -q        # 11 end-to-end tests of the whole demo story. WARNING: re-seeds the database.
```

---

## 2. Demo accounts (password for all: `Password@123`)

| Role | Email | Notes |
|---|---|---|
| Institution | `college1@aicte-demo.in` | **Demo Institute of Technology, Pune.** Has an FDR maturing in about 95 days (for the time-travel demo) and an extra FDR to release |
| Institution | `college8@aicte-demo.in` | Open compliance case, so its release request is **blocked** |
| Institution | `college5@` … `college7@` | Renewal due, so the institution is **locked** |
| Scrutiny Officer | `officer@aicte-demo.in` / `officer2@` | Work queue, verification, discrepancies |
| Approving Authority | `approver@aicte-demo.in` / `approver2@` | Sign-off, release sanction, escalations |
| Regional Officer | `ro.western@aicte-demo.in` (also `ro.northern`, `ro.southern`, `ro.eastern`, `ro.central`, `ro.north_west`, `ro.south_west`, `ro.south_central`) | Sees only their region |
| Bank | `bank.sbi@aicte-demo.in`, `bank.canara@aicte-demo.in` | Answers confirmation requests |
| Admin (Bureau head) | `admin@aicte-demo.in` | Config, users, time travel, jobs |
| Auditor | `auditor@aicte-demo.in` | Read-only everywhere (enforced on every endpoint) |

Synthetic demo files (FDR receipts, a scanned image, a tampered FDR, a duplicate FDR, a lien letter and an undertaking) are in [`backend/samples/`](backend/samples/README.md).

---

## 3. How we close each gap in the problem statement

| Gap today | What we built | Why it is different |
|---|---|---|
| **No single record per institution and per FDR** | One instrument record per FDR, with a full **lifecycle timeline** (`fdr_events`). Renewals are **chained** to the FDR they replace (`replaces_instrument_id`). | AICTE sees one unbroken security history per institution across years, not separate yearly entries. |
| **No automatic reminders before maturity** | A daily **state machine** (ACTIVE → EXPIRING_SOON → ACTION_REQUIRED → MATURED → OVERDUE) with a reminder ladder at T-90/60/30/7/0/+7. It is **holiday-aware**, logs "who was told, when", and is fully configurable. | At T-30 it does more than send an email. It **locks the institution** until renewal proof is uploaded and **opens a ticket** for that region's officer. The ticket **escalates** up a configurable ladder if nobody resolves it. |
| **No easy way to check if an FDR is genuine** | (1) **OCR cross-check** of typed values against the uploaded scan *before* submission. (2) A **bank verification hub**: an Account-Aggregator-style bank API (simulated sandbox) that falls back to a **one-time blind confirmation link** for the bank, then to an officer upload. (3) A rule engine with **20 explainable rules** (duplicate FDR across institutions, reused document hash, amount in words ≠ figures, IFSC ↔ bank mismatch, …). (4) **Continuous re-verification** that catches an FDR encashed *after* approval. | Every field shows **"Declared" vs "Bank-verified"** with a badge. The system only *flags*; a human confirms or dismisses each flag with a reason. A bank outage is recorded as `SOURCE_UNAVAILABLE`, never as "fake". |
| **No clear tracking of refund requests** | A **courier-style tracker** (Requested → Under review → Recommended → Approved → Processed). A **pre-condition engine** checks open compliance cases, open discrepancies, bank confirmation, undertaking and minimum security. Release follows a **two-person rule** and generates a **discharge letter**. | Release is **never automatic**, and a premature refund is blocked before a human even looks at it. The institution sees exactly the same status as the officer. |

Cross-cutting features:

- A **hash-chained audit log**. Each entry stores the SHA-256 of the previous one. `/audit/verify` pinpoints the first tampered row, and the demo includes a "simulate a DBA editing a row" button.
- **Documents encrypted at rest**, with the SHA-256 re-checked on every download.
- **RBAC** with 7 roles, enforced at the API level, plus optional TOTP **MFA**.

### USP checklist

| # | USP | Where |
|---|---|---|
| 1 | Complete lifecycle tracking | `services/lifecycle.py`, `GET /instruments/{id}` (timeline, lineage) |
| 2 | Smart reminders + auto-escalation ladder | `services/monitor.py`, `services/alerts.py`, `config: escalation_ladder` |
| 3 | Authenticity verification workflow (Submitted → Sent to bank → Verified/Mismatch) | `services/verification.py`, `POST /instruments/{id}/verify-bank` |
| 4 | OCR auto-fill (Tesseract, optional Google Vision) | `services/ocr.py`, `POST /ocr/extract` |
| 5 | Refund tracker (courier-style) | `services/refunds.py`, `GET /refunds/{id}/track` |
| 6 | Duplicate & mismatch detection (FDR no. + bank, document hash) | `services/rules.py` R09–R11, `POST /instruments/check-duplicate` |
| 7 | Risk dashboard + predictive heatmap | `services/analytics.py`, `GET /dashboard/*` |
| 8 | Audit trail + role-based access | `services/audit.py`, `security.py` |
| 9 | Report export (Excel/PDF) | `services/reports.py`, `GET /reports/{name}?format=xlsx` |
| 10 | Simulated open-banking sandbox | `services/mock_bank.py`, `POST /mock-bank/v1/fdr/verify` |
| 11 | Cryptographic immutable ledger | `GET /audit/verify` |
| 12 | Automated state-machine encashment workflow (T-30 lock + ticket) | `services/monitor.py`, `services/renewals.py` |
| 13 | Declared vs bank-verified badge on every field | `services/fields.py`, `GET /instruments/{id}/fields` |
| 14 | Guarded release workflow | `services/refunds.py` |
| 15 | College self-service view with "documents needed" checklist | `GET /me/overview` |

---

## 4. Demo script (6 minutes)

1. **OCR catches a typo (college1).** Upload `fdr_demo_correct.pdf` to `POST /ocr/extract`; the form is pre-filled. Create the FDR but type the amount as `250000` instead of `2500000`. The upload response shows a **MISMATCH** on the amount, along with R13 and R05 flags. Fix it, upload the lien letter, and submit to get an acknowledgement number.
2. **Officer verifies with the bank.** Log in as `officer`, open the work queue (highest risk first), pick up the case and run **verify-bank**. Every field badge turns from *Declared* to **Bank-verified**. Then mark it verified, and `approver` approves it.
3. **Fraud signals.** Look at the seeded cases. College11 re-used another college's FDR number (**R09 CRITICAL**). College12 uploaded another college's scan (**R11**). College14's amount in words does not match the figures (**R15**). One FDR was encashed after approval and was caught by re-verification (**R20**, BANK_STATUS_CHANGED alert). College8's release request is blocked by an open compliance case.
4. **Bank outage.** `POST /mock-bank/v1/banks/{id}/availability?available=false`, then verify again. The result is recorded as SOURCE_UNAVAILABLE and a **secure link** is emailed (see Mailpit). Open `/bank-link/{token}`: the bank sees *what* to confirm, not the declared values.
5. **Time travel.** As admin, call `POST /admin/demo/clock {"days": 66}`. College1's FDR becomes **ACTION_REQUIRED**, the college is **locked** (423 on new submissions), and `ro.western` gets a ticket. Advance 8 more days and the ticket **escalates** to the Approving Authority. College1 then uploads the renewal and the lock lifts.
6. **Release.** College1 raises a release on its extra FDR. It shows BLOCKED (no undertaking yet), then REQUESTED once the undertaking is uploaded. The officer recommends; the officer **cannot** approve (two-person rule); the approver sanctions; processing generates the **discharge letter**. The tracker shows every step.
7. **Audit.** `GET /audit/verify` returns valid. `POST /admin/demo/tamper-audit/10` simulates an insider SQL edit, after which verify returns **broken at #10**. Restore it afterwards. Then export any report as Excel or PDF.

Reset with `python -m scripts.seed --reset` (about 25 s) between rehearsals.

---

## 5. Architecture

```
 Next.js frontend (frontend/)  ──REST/JSON + JWT──▶  FastAPI  /api/v1
                                                     │
   ┌──────────────┬──────────────┬───────────────────┼─────────────────┬──────────────┐
   │ lifecycle    │ rules engine │ verification hub  │ monitor (cron)  │ refunds      │
   │ state machine│ 20 rules     │ API → link → manual│ reminders,     │ pre-conditions│
   │ + timeline   │ flags only   │ (mock AA sandbox) │ lock, escalation│ two-person   │
   └──────┬───────┴──────┬───────┴─────────┬─────────┴────────┬────────┴──────┬───────┘
          │ OCR (PDF text layer → Google Vision → Tesseract)   │ notifications │
          ▼                                                     ▼  (in-app, email, SMS-sim)
   PostgreSQL (data + hash-chained audit_log)          Encrypted document store (Fernet)
```

```
backend/
  app/
    main.py            FastAPI app, middleware, scheduler start
    config.py          settings (.env)
    models.py          SQLAlchemy models (19 tables)
    enums.py           statuses, roles, ...
    security.py        JWT, bcrypt, TOTP MFA, RBAC dependencies
    routers/           HTTP endpoints (auth, me, instruments, documents, refunds, alerts, dashboard, bank, admin)
    services/          business logic (one file per USP, listed above)
  scripts/seed.py      replays ~500 historical actions through the real services
  scripts/sample_docs.py  synthetic FDR / letter generator
  samples/             demo files
  tests/               end-to-end tests
docs/API.md            frontend integration guide
```

**Honesty rule:** everything simulated is labelled. The bank API responses carry `"simulated": true` and `source: SIMULATED_AA_SANDBOX`, SMS is logged as `SIMULATED`, and the time-travel tools are `[DEMO]` and are disabled when `DEMO_MODE=false`.

## 6. Roadmap after the prototype

- Real bank verification APIs, or the RBI Account Aggregator framework with institution consent.
- DigiLocker / eSign for undertakings and sanction orders.
- An ML forgery model trained on real scans, replacing the heuristic rules.
- Alembic migrations, S3/MinIO storage, a Celery worker for OCR, and SSO with AICTE systems.
