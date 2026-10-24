# Frontend integration guide (Next.js)

- **Base URL:** `http://localhost:8000/api/v1`
- **Interactive docs:** `http://localhost:8000/docs`. Every endpoint, schema and enum is there, and you can try them live.
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`. You can generate TypeScript types from it:
  `npx openapi-typescript http://localhost:8000/openapi.json -o src/lib/api-types.ts`

CORS already allows `http://localhost:3000`.

## Auth

```ts
const r = await fetch(`${API}/auth/login`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password, otp }),   // otp only if MFA enabled
});
const { access_token, user } = await r.json();      // user.role decides the layout
// every later call:  headers: { Authorization: `Bearer ${access_token}` }
```

Roles are `INSTITUTION`, `SCRUTINY_OFFICER`, `REGIONAL_OFFICER`, `APPROVING_AUTHORITY`, `BANK`, `ADMIN` and `AUDITOR`. `GET /auth/me` returns the user, their institution and `simulated_today`. Show the date in the header during the demo, because it changes when the clock is moved.

Error shapes are FastAPI defaults: `{ "detail": "text" }` or `{ "detail": { "message": "...", ... } }`.

| Code | Meaning | What the UI should do |
|---|---|---|
| 401 | Not logged in or expired | Redirect to login (on login, `detail.mfa_required` means ask for the OTP) |
| 403 | Role not allowed | Hide the button. Use `allowed_actions` (see below) |
| 409 | Wrong state for this action | Show `detail` |
| 422 | Validation failed or record incomplete | `detail.problems[]` gives the per-field messages |
| 423 | Institution locked (renewal due) | Show `detail.pending_renewals[]` with an "Upload renewal" call to action |

## Screens and the endpoints behind them

### Institution (college)

| Screen | Endpoints |
|---|---|
| Home dashboard | `GET /me/overview` returns `locked`, `lock_reasons`, `action_required[]` (top strip), `documents_needed[]` (checklist), `upcoming_deadlines[]`, `instruments[]`, `refunds[]` (each with a tracker), `totals` |
| New FDR (OCR auto-fill) | 1. `POST /ocr/extract` (multipart `file`) returns `prefill` (pre-fill the form) and `ocr.fields[x].confidence` (highlight low-confidence fields). 2. `POST /instruments/check-duplicate` on blur of the FDR number. 3. `POST /instruments` (JSON) creates a draft. 4. `POST /instruments/{id}/documents` (multipart `file` + `doc_type=FDR_SCAN`) returns `cross_check[]` and `mismatches[]`; show them in red **before** submit. 5. Upload `LIEN_LETTER`. 6. `POST /instruments/{id}/submit` returns an `ack_number` (422 lists what is missing) |
| FDR detail | `GET /instruments/{id}` (see "Case view" below) |
| Fix a discrepancy | `PATCH /instruments/{id}`, re-upload, then `submit` again |
| Renewal | `POST /instruments/{old_id}/renew` returns a new draft linked to the old one. Upload `RENEWAL_FDR` and `LIEN_LETTER`, then submit. The lock lifts on submit |
| Release / refund | `POST /refunds {instrument_id, ground}`, then `POST /refunds/{id}/documents` (`doc_type=UNDERTAKING`). Track it with `GET /refunds/{id}/track` |
| Bell | `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read` |

### Officer / Approver / Regional officer

| Screen | Endpoints |
|---|---|
| Risk dashboard | `GET /dashboard/summary` (tiles), `/dashboard/by-bank`, `/dashboard/by-region`, `/dashboard/maturity-projection`, `/dashboard/renewal-heatmap`, `/dashboard/predicted-late-renewals`, `/dashboard/verification-ageing` |
| Work queue | `GET /instruments/work-queue`, sorted by risk then age. Each item has `flag_chips[]` and `age_days` |
| Search | `GET /instruments?q=&status=&region=&bank_name=&maturing_within_days=&min_risk=&has_open_flags=&sort=risk\|maturity\|oldest\|newest\|amount&page=&page_size=` |
| Case view (split screen) | `GET /instruments/{id}`. Left pane: `fields[]` with badges. Right pane: the document via `GET /documents/{doc_id}/download` (render the PDF inline) |
| Actions | `pickup`, `verify-bank`, `manual-verify`, `raise-discrepancy`, `mark-verified`, `approve`, `send-back`, `reject`, `observations`. Show only what `allowed_actions[]` contains |
| Flag decision | `POST /flags/{id}/decide {decision: "CONFIRMED" or "DISMISSED", note}` |
| Alerts / tickets | `GET /alerts` (my queue, highest level first), `acknowledge`, `resolve`. `history[]` shows the escalation trail |
| Releases | `GET /refunds?status=`, then `start-review`, `recommend` (officer), `approve` (approver, a different person), `process`, `reject` |
| Reports | `GET /reports` lists them. Download with `GET /reports/{name}?format=xlsx\|pdf\|json` (blob download, filename in `Content-Disposition`) |
| Audit | `GET /audit?entity_type=instrument&entity_id=12`, `GET /audit/verify`, `GET /audit/instrument/{id}` |

### Bank

`GET /bank/requests` lists the bank's requests. Answer with `POST /bank/requests/{id}/respond {found, amount, issue_date, maturity_date, lien_marked, depositor_name, bank_status}`.

The public one-time link page is `/bank-confirm/[token]`. It needs no login: call `GET /bank-link/{token}` and submit with `POST /bank-link/{token}`. **Do not show any declared values on this page.** The bank must enter the values blind.

### Admin

`/admin/users`, `/admin/config` (edit the reminder ladder, escalation ladder, slabs and rule overrides), `/admin/holidays`, `/admin/banks`, `/compliance-cases`, `/admin/jobs/run`.

Demo panel: `GET`/`POST /admin/demo/clock {days}` (time travel; returns `events[]` that you can animate), `POST /admin/demo/clock/reset`, `POST /admin/demo/tamper-audit/{id}` and `/restore`, `POST /mock-bank/v1/banks/{id}/availability?available=false`, and `PATCH /mock-bank/v1/records/{id} {status:"ENCASHED"}`.

## Case view payload (`GET /instruments/{id}`)

```jsonc
{
  "instrument": { "id", "ack_number", "status", "status_label", "verification_status", "trust_level",
                  "risk_score", "days_to_maturity", "amount", ... },
  "institution": { ... },
  "fields": [   // one row per field -> render the badge
    { "field": "amount", "label": "Amount (INR)", "declared_value": "2500000.00",
      "ocr_value": "2500000.00", "confirmed_value": "2500000.00",
      "trust": "BANK_VERIFIED", "badge": { "label": "Bank-verified", "color": "green" } }
  ],
  "pending_action": { "owner": "INSTITUTION|AICTE|NONE", "text": "..." },  // same text for both sides
  "allowed_actions": ["pickup", "verify_with_bank", ...],
  "flags": [ { "rule_id": "R13", "severity": "HIGH", "status": "OPEN", "title", "officer_message"|"message", "evidence" } ],
  "observations": [...], "documents": [...], "missing_documents": ["LIEN_LETTER"],
  "timeline": [ { "action", "from_status", "to_status", "actor_role", "note", "created_at" } ],
  "verification_requests": [ { "channel", "status", "result", "source_name", "is_simulated" } ],
  "lineage": [ ...renewal chain oldest -> newest... ],
  "pending_renewal_id": null
}
```

Badge colours (`GET /meta/enums` returns `field_badges` and `status_labels`):

| Trust | Label | Colour |
|---|---|---|
| `DECLARED` | Declared | grey |
| `OCR_CONSISTENT` | Matches document | blue |
| `OCR_CONFLICT` | Differs from document | orange |
| `BANK_VERIFIED` | Bank-verified | green |
| `OFFICER_VERIFIED` | Officer-verified | teal |
| `MISMATCH` | Bank mismatch | red |

Institutions receive `flags[].message` (plain language). Officers receive `officer_message` and `evidence`.

## Uploads

```ts
const fd = new FormData();
fd.append("file", file);
fd.append("doc_type", "FDR_SCAN");   // FDR_SCAN | LIEN_LETTER | RENEWAL_FDR | BANK_CONFIRMATION | UNDERTAKING | OTHER
await fetch(`${API}/instruments/${id}/documents`, { method: "POST", headers: { Authorization }, body: fd });
```

Only PDF, PNG and JPEG are accepted, up to 10 MB. PDFs with JavaScript are rejected (415).
