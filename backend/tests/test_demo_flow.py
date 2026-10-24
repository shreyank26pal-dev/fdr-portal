"""End-to-end test of the demo story through the HTTP API.

Requires a PostgreSQL database (DATABASE_URL). The fixture re-seeds it, so do NOT point
this at data you care about.   Run:  pytest -q
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("ENABLE_SCHEDULER", "false")

from fastapi.testclient import TestClient  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
SAMPLES = BACKEND / "samples"
PW = "Password@123"


@pytest.fixture(scope="module")
def client():
    subprocess.run([sys.executable, "-m", "scripts.seed", "--reset"], cwd=BACKEND, check=True,
                   stdout=subprocess.DEVNULL)
    from app.main import app

    with TestClient(app) as c:
        yield c
        c.post("/api/v1/admin/demo/clock/reset", headers=auth(c, "admin"))


_tokens: dict[str, str] = {}


def auth(c: TestClient, who: str) -> dict:
    if who not in _tokens:
        r = c.post("/api/v1/auth/login", json={"email": f"{who}@aicte-demo.in", "password": PW})
        assert r.status_code == 200, r.text
        _tokens[who] = r.json()["access_token"]
    return {"Authorization": f"Bearer {_tokens[who]}"}


def upload(c, iid, path, doc_type, who="college1"):
    with open(path, "rb") as f:
        return c.post(f"/api/v1/instruments/{iid}/documents", headers=auth(c, who),
                      files={"file": (path.name, f, "application/pdf" if path.suffix == ".pdf" else "image/png")},
                      data={"doc_type": doc_type})


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ocr_prefill(client):
    with open(SAMPLES / "fdr_demo_correct.pdf", "rb") as f:
        r = client.post("/api/v1/ocr/extract", headers=auth(client, "college1"),
                        files={"file": ("f.pdf", f, "application/pdf")})
    assert r.status_code == 200
    pre = r.json()["prefill"]
    assert pre["fdr_number"] == "40112233445" and pre["amount"] == "2500000.00" and pre["ifsc"] == "SBIN0004321"


def test_full_submission_verification_approval(client):
    h = auth(client, "college1")
    # typed amount is WRONG on purpose (2.5 lakh instead of 25 lakh)
    body = {"fdr_number": "40112233445", "bank_name": "State Bank of India", "branch": "Pune Main Branch",
            "ifsc": "SBIN0004321", "amount": 250000, "issue_date": None, "maturity_date": None,
            "lien_marked": True, "lien_in_favour_of": "AICTE, New Delhi", "purpose": "EXTENSION_OF_APPROVAL",
            "depositor_name": "Demo Institute of Technology, Pune"}
    with open(SAMPLES / "fdr_demo_correct.pdf", "rb") as f:
        pre = client.post("/api/v1/ocr/extract", headers=h, files={"file": ("f.pdf", f, "application/pdf")}).json()["prefill"]
    body["issue_date"], body["maturity_date"] = pre["issue_date"], pre["maturity_date"]
    r = client.post("/api/v1/instruments", headers=h, json=body)
    assert r.status_code == 201, r.text
    iid = r.json()["instrument"]["id"]

    r = upload(client, iid, SAMPLES / "fdr_demo_correct.pdf", "FDR_SCAN")
    assert r.status_code == 201, r.text
    mism = {m["field"] for m in r.json()["mismatches"]}
    assert "amount" in mism  # OCR caught the typo at the point of entry

    # submit blocked: lien letter missing
    r = client.post(f"/api/v1/instruments/{iid}/submit", headers=h)
    assert r.status_code == 422

    client.patch(f"/api/v1/instruments/{iid}", headers=h, json={"amount": 2500000})
    upload(client, iid, SAMPLES / "lien_letter_demo.pdf", "LIEN_LETTER")
    r = client.post(f"/api/v1/instruments/{iid}/submit", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["instrument"]["status"] == "SUBMITTED" and d["instrument"]["ack_number"].startswith("AICTE/SD/")
    assert not [f for f in d["flags"] if f["status"] == "OPEN"], d["flags"]
    badges = {f["field"]: f["trust"] for f in d["fields"]}
    assert badges["amount"] == "OCR_CONSISTENT"

    o = auth(client, "officer")
    assert any(i["id"] == iid for i in client.get("/api/v1/instruments/work-queue", headers=o).json())
    assert client.post(f"/api/v1/instruments/{iid}/pickup", headers=o).status_code == 200
    r = client.post(f"/api/v1/instruments/{iid}/verify-bank", headers=o)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["verification"]["result"] == "VERIFIED" and d["verification"]["is_simulated"] is True
    badges = {f["field"]: f["trust"] for f in d["fields"]}
    assert badges["amount"] == "BANK_VERIFIED" and badges["maturity_date"] == "BANK_VERIFIED"

    assert client.post(f"/api/v1/instruments/{iid}/mark-verified", headers=o, json={}).status_code == 200
    # officer cannot approve; approver can
    assert client.post(f"/api/v1/instruments/{iid}/approve", headers=o, json={}).status_code == 403
    r = client.post(f"/api/v1/instruments/{iid}/approve", headers=auth(client, "approver"), json={})
    assert r.status_code == 200 and r.json()["instrument"]["status"] == "ACTIVE"
    actions = [e["action"] for e in r.json()["timeline"]]
    for a in ("created", "document_uploaded", "submit", "pickup", "bank_verification", "mark_verified", "approve"):
        assert a in actions


def test_duplicate_and_tamper_detection(client):
    h = auth(client, "college1")
    with open(SAMPLES / "fdr_demo_duplicate_number.pdf", "rb") as f:
        pre = client.post("/api/v1/ocr/extract", headers=h, files={"file": ("f.pdf", f, "application/pdf")}).json()["prefill"]
    dup = client.post("/api/v1/instruments/check-duplicate", headers=h,
                      json={"fdr_number": pre["fdr_number"], "ifsc": pre["ifsc"]}).json()
    assert dup["duplicate"] and dup["other_institution"]
    r = client.post("/api/v1/instruments", headers=h, json={**pre, "lien_marked": True,
                                                            "lien_in_favour_of": "AICTE", "purpose": "EXTENSION_OF_APPROVAL"})
    assert any(f["rule_id"] == "R09" for f in r.json()["flags"])

    with open(SAMPLES / "fdr_demo_tampered_words.pdf", "rb") as f:
        pre = client.post("/api/v1/ocr/extract", headers=h, files={"file": ("f.pdf", f, "application/pdf")}).json()["prefill"]
    r = client.post("/api/v1/instruments", headers=h, json={**pre, "lien_marked": True,
                                                            "lien_in_favour_of": "AICTE", "purpose": "EXTENSION_OF_APPROVAL"})
    iid = r.json()["instrument"]["id"]
    r = upload(client, iid, SAMPLES / "fdr_demo_tampered_words.pdf", "FDR_SCAN")
    assert any(f["rule_id"] == "R15" for f in r.json()["flags"])
    # institution sees plain language only
    assert "officer_message" not in client.get(f"/api/v1/instruments/{iid}", headers=h).json()["flags"][0]


def test_refund_two_person_rule_and_tracker(client):
    h = auth(client, "college1")
    ov = client.get("/api/v1/me/overview", headers=h).json()
    extra = next(i for i in ov["instruments"] if i["purpose"] == "INCREASE_IN_INTAKE" and i["status"] == "ACTIVE")
    r = client.post("/api/v1/refunds", headers=h, json={"instrument_id": extra["id"], "ground": "PROGRAMME_DISCONTINUED"})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["status"] == "BLOCKED"  # undertaking missing
    with open(SAMPLES / "undertaking_demo.pdf", "rb") as f:
        r = client.post(f"/api/v1/refunds/{rid}/documents", headers=h,
                        files={"file": ("u.pdf", f, "application/pdf")}, data={"doc_type": "UNDERTAKING"})
    assert r.json()["status"] == "REQUESTED"
    o = auth(client, "officer")
    client.post(f"/api/v1/refunds/{rid}/start-review", headers=o, json={})
    client.post(f"/api/v1/refunds/{rid}/recommend", headers=o, json={})
    a = auth(client, "approver")
    r = client.post(f"/api/v1/refunds/{rid}/approve", headers=a, json={"note": "Sanctioned"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/refunds/{rid}/process", headers=o, json={})
    assert r.status_code == 200
    rr = r.json()
    assert rr["status"] == "PROCESSED" and rr["instrument"]["status"] == "RELEASED"
    states = [s["state"] for s in rr["tracker"]["steps"]]
    assert states == ["done"] * 5
    pdf = client.get(f"/api/v1/documents/{rr['discharge_document_id']}/download", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["X-Integrity"] == "verified"


def test_blocked_release_with_open_compliance_case(client):
    r = client.get("/api/v1/refunds?status=BLOCKED", headers=auth(client, "officer")).json()
    assert r and any(not c["passed"] and c["code"] == "NO_OPEN_COMPLIANCE_CASE" for c in r[0]["precondition_results"])


def test_bank_email_link_fallback(client):
    o = auth(client, "officer")
    # take bank API down -> automatic fallback to secure link
    banks = client.get("/api/v1/banks", headers=o).json()
    sbi = next(b for b in banks if b["ifsc_prefix"] == "SBIN")
    client.post(f"/api/v1/mock-bank/v1/banks/{sbi['id']}/availability?available=false", headers=auth(client, "admin"))
    items = client.get("/api/v1/instruments?status=ACTIVE&bank_name=State Bank&page_size=1", headers=o).json()["items"]
    iid = items[0]["id"]
    r = client.post(f"/api/v1/instruments/{iid}/verify-bank", headers=o).json()
    v = r["verification"]
    assert v["channel"] == "BANK_EMAIL_LINK" and "demo_confirmation_token" in v
    tok = v["demo_confirmation_token"]
    view = client.get(f"/api/v1/bank-link/{tok}").json()
    assert "amount" not in view  # blind confirmation
    det = client.get(f"/api/v1/instruments/{iid}", headers=o).json()["instrument"]
    r = client.post(f"/api/v1/bank-link/{tok}", json={"found": True, "amount": str(det["amount"]),
                                                       "maturity_date": det["maturity_date"], "lien_marked": True})
    assert r.json()["result"] == "VERIFIED"
    assert client.post(f"/api/v1/bank-link/{tok}", json={"found": True}).status_code == 410  # one-time
    client.post(f"/api/v1/mock-bank/v1/banks/{sbi['id']}/availability?available=true", headers=auth(client, "admin"))


def test_time_travel_lock_escalation_and_renewal(client):
    adm, h = auth(client, "admin"), auth(client, "college1")
    ov = client.get("/api/v1/me/overview", headers=h).json()
    target = min((i for i in ov["instruments"] if i["status"] == "ACTIVE" and i["purpose"] == "EXTENSION_OF_APPROVAL"
                  and i["days_to_maturity"] and 60 < i["days_to_maturity"] < 120), key=lambda i: i["days_to_maturity"])
    days = target["days_to_maturity"] - 29
    r = client.post("/api/v1/admin/demo/clock", headers=adm, json={"days": days})
    assert r.status_code == 200, r.text
    ov = client.get("/api/v1/me/overview", headers=h).json()
    assert ov["locked"]
    assert next(i for i in ov["instruments"] if i["id"] == target["id"])["status"] == "ACTION_REQUIRED"
    assert client.post("/api/v1/instruments", headers=h, json={"fdr_number": "X1"}).status_code == 423
    ro = auth(client, "ro.western")
    alerts = client.get("/api/v1/alerts", headers=ro).json()
    assert any(a["instrument_id"] == target["id"] and a["alert_type"] == "ACTION_REQUIRED" for a in alerts)

    client.post("/api/v1/admin/demo/clock", headers=adm, json={"days": 8})
    al = client.get("/api/v1/alerts?alert_type=ACTION_REQUIRED", headers=adm).json()
    mine = next(a for a in al if a["instrument_id"] == target["id"])
    assert mine["level"] == 2 and mine["assigned_role"] == "APPROVING_AUTHORITY"

    r = client.post(f"/api/v1/instruments/{target['id']}/renew", headers=h,
                    json={"fdr_number": "40112299001", "amount": 2500000, "issue_date": str(r.json()["today"]),
                          "maturity_date": "2030-01-01", "lien_marked": True, "lien_in_favour_of": "AICTE"})
    assert r.status_code == 201, r.text
    nid = r.json()["instrument"]["id"]
    upload(client, nid, SAMPLES / "fdr_demo_correct.pdf", "RENEWAL_FDR")
    upload(client, nid, SAMPLES / "lien_letter_demo.pdf", "LIEN_LETTER")
    r = client.post(f"/api/v1/instruments/{nid}/submit", headers=h)
    assert r.status_code == 200, r.text
    assert not client.get("/api/v1/me/overview", headers=h).json()["locked"]
    assert len(r.json()["lineage"]) >= 2
    client.post("/api/v1/admin/demo/clock/reset", headers=adm)


def test_audit_chain_tamper_detection(client):
    adm = auth(client, "admin")
    assert client.get("/api/v1/audit/verify", headers=adm).json()["valid"]
    client.post("/api/v1/admin/demo/tamper-audit/10", headers=adm)
    v = client.get("/api/v1/audit/verify", headers=adm).json()
    assert not v["valid"] and v["broken_at_id"] == 10
    client.post("/api/v1/admin/demo/tamper-audit/10/restore", headers=adm)
    assert client.get("/api/v1/audit/verify", headers=adm).json()["valid"]


def test_rbac(client):
    aud = auth(client, "auditor")
    assert client.get("/api/v1/instruments", headers=aud).status_code == 200
    assert client.post("/api/v1/instruments/1/pickup", headers=aud).status_code == 403
    h = auth(client, "college2")
    mine = client.get("/api/v1/instruments", headers=h).json()["items"]
    assert all(i["institution_id"] == mine[0]["institution_id"] for i in mine)
    other = client.get("/api/v1/instruments", headers=auth(client, "college1")).json()["items"][0]["id"]
    assert client.get(f"/api/v1/instruments/{other}", headers=h).status_code == 404


def test_dashboards_and_reports(client):
    o = auth(client, "officer")
    for path in ("summary", "by-bank", "by-region", "maturity-projection", "renewal-heatmap",
                 "predicted-late-renewals", "verification-ageing"):
        assert client.get(f"/api/v1/dashboard/{path}", headers=o).status_code == 200, path
    hm = client.get("/api/v1/dashboard/renewal-heatmap", headers=o).json()
    assert hm["rows"]
    for name in ("maturity-schedule", "pending-refunds", "bank-summary", "missing-documents", "audit-extract"):
        for fmt in ("json", "xlsx", "pdf"):
            r = client.get(f"/api/v1/reports/{name}?format={fmt}", headers=o)
            assert r.status_code == 200, (name, fmt, r.text[:200])
