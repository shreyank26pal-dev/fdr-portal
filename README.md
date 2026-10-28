# 🏛️ SecureDeposit: AICTE Security Deposit & FDR Lifecycle Portal

[![SIH26265](https://img.shields.io/badge/SIH26265-AICTE%20%7C%20Ministry%20of%20Education-orange?style=for-the-badge)](https://www.sih.gov.in/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React_19-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS_v4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Cryptographic Audit](https://img.shields.io/badge/Audit_Chain-SHA--256%20Immutable-emerald?style=for-the-badge)](#6-cryptographic-hash-chained-audit-ledger)
[![India Stack](https://img.shields.io/badge/India_Stack-DigiLocker%20%2B%20Aadhaar%20eSign-blue?style=for-the-badge)](#5-india-stack-integrations-digilocker--aadhaar-esign)

> **Problem Statement ID:** `SIH26265` — *Streamlining of Security Deposit / FDR Portal*  
> **Organization:** All India Council for Technical Education (AICTE), Ministry of Education, Government of India  
> **Tagline:** *"Moving from Physical Vaults to an Immutable, Bank-Verified Digital Custody"*

---

## 📑 Table of Contents

1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [End-to-End System Architecture](#2-end-to-end-system-architecture)
3. [Key Pillars & Architectural Highlights](#3-key-pillars--architectural-highlights)
   - [Pillar 1: Dual-Truth Verification Engine](#pillar-1-dual-truth-verification-engine)
   - [Pillar 2: Zero-Block Bank Verification Hub](#pillar-2-zero-block-bank-verification-hub)
   - [Pillar 3: Explainable 20-Rule Fraud & Anomaly Engine](#pillar-3-explainable-20-rule-fraud--anomaly-engine)
   - [Pillar 4: Automated State Machine & T-30 Statutory Lock](#pillar-4-automated-state-machine--t-30-statutory-lock)
   - [Pillar 5: Guarded Release Workflow & 5-Step Courier Tracker](#pillar-5-guarded-release-workflow--5-step-courier-tracker)
4. [Master 15 Unique Selling Propositions (USPs)](#4-master-15-unique-selling-propositions-usps)
5. [India Stack Integrations (DigiLocker & Aadhaar eSign)](#5-india-stack-integrations-digilocker--aadhaar-esign)
6. [Cryptographic Hash-Chained Audit Ledger](#6-cryptographic-hash-chained-audit-ledger)
7. [Bilingual Interface (NEP 2020 & Bhashini Ready)](#7-bilingual-interface-nep-2020--bhashini-ready)
8. [Statutory Compliance Certificate Generator](#8-statutory-compliance-certificate-generator)
9. [Pre-Packaged Demo Accounts & Role Matrix](#9-demo-accounts--role-matrix)
10. [Quick Start & Launcher Guide](#10-quick-start--launcher-guide)
11. [Testing & Verification Suite](#11-testing--verification-suite)
12. [Demo Video Clips & Voiceover Sync Suite](#12-demo-video-clips--voiceover-sync-suite)
13. [Honesty Rule & Simulation Transparency](#13-honesty-rule--simulation-transparency)

---

## 1. Executive Summary & Problem Statement

Technical education institutions across India deposit hundreds of crores of rupees with AICTE as paper Fixed Deposit Receipts (FDRs) to satisfy Approval Process Handbook (APH) norms and safeguard student liabilities. Historically, this critical financial mechanism relied on physical paper receipts, manual postal dispatches, untracked maturity registers, and unverified bank confirmations.

### The ₹1,000+ Crore Operational Blindspot: "As-Is" vs "To-Be"

| Operational Area | Current Manual Reality ("As-Is") | SecureDeposit Solution ("To-Be") |
| :--- | :--- | :--- |
| **Document Custody** | Paper FDRs stored in office vaults; prone to damage, misplacement, or catastrophic loss. | Encrypted storage (Fernet AES-128-CBC) with dynamic SHA-256 fingerprint verification on access. |
| **Authenticity Check** | Trust-based acceptance without direct bank confirmation; risk of forged paper receipts. | **Dual-Truth Engine**: Real-time Core Banking System (CBS) API integration with automated blind nodal link fallback. |
| **Maturity Tracking** | Spreadsheet tracking; silent deposit lapse without timely renewals or encashment. | **Automated State Machine**: Daily holiday-aware scheduler with reminders at T-90/60/30/7/0/+7 days. |
| **Institutional Enforcement**| Colleges ignore reminders with zero portal-level consequences. | **T-30 Statutory Lockout**: Automatic `HTTP 423 Locked` state prevents new admissions/approvals until renewal proof is submitted. |
| **Fraud & Tampering** | Reused deposit receipts across institutes; post-approval premature encashment. | **20 Explainable Fraud Rules** (R01–R20) + Continuous re-verification detecting bank liquidation within 24h. |
| **Refund Processing** | 6–12 months of manual bureaucratic file circulation and postal delays. | **Guarded Two-Person Release**: 6-gate pre-condition engine, Aadhaar eSigned undertaking, and courier tracker. |
| **Audit & Vigilance** | Vulnerable to retrospective database manipulation by insiders. | **Cryptographic Blockchain-Lite Ledger**: SHA-256 hash-chained log with one-click mathematical tamper detection. |

---

## 2. End-to-End System Architecture

```
                          ┌────────────────────────────────────────────────────────┐
                          │   Modern Web Frontend (React 19 + TypeScript + Vite)   │
                          │   Tailwind CSS v4 • Lucide Icons • Bilingual EN/हिन्दी  │
                          └───────────┬────────────────────────────────┬───────────┘
                                      │                                │
                       REST / JSON + JWT Bearer Auth      1-Click Role Switcher
                                      ▼                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             FastAPI High-Performance Application Core                            │
├─────────────────────┬──────────────────────┬──────────────────────┬──────────────────────────────┤
│ 1. Lifecycle Engine │ 2. 20-Rule Engine    │ 3. Bank Hub          │ 4. Guarded Release Engine    │
│  • State Machine    │  • Duplicate Detect  │  • Mock CBS API      │  • 6 Pre-condition Gates     │
│  • Timeline & Trees │  • Words vs Figures  │  • Zero-Rubber Stamp │  • Two-Person Rule           │
│  • Lineage Tracking │  • Tamper Warnings   │  • 7-Day Blind Link  │  • Discharge PDF Generator   │
├─────────────────────┼──────────────────────┼──────────────────────┼──────────────────────────────┤
│ 5. India Stack Hub  │ 6. Daily Monitor     │ 7. Audit Chain       │ 8. Analytics & Heatmap       │
│  • DigiLocker Sync  │  • Holiday-aware     │  • SHA-256 Chained   │  • Exposure Heatmaps         │
│  • Aadhaar eSign    │  • T-30 Auto-Lock    │  • Mathematical      │  • Bank Concentration        │
│  • UIDAI OTP Gate   │  • Auto-Escalations  │    Tamper Proofing   │  • Excel/PDF Report Export   │
└──────────┬──────────┴──────────┬───────────┴──────────┬───────────┴──────────────┬───────────────┘
           │                     │                      │                          │
           ▼                     ▼                      ▼                          ▼
   ┌───────────────┐     ┌───────────────┐      ┌───────────────┐          ┌───────────────┐
   │ SQLite / PG   │     │  Fernet Store │      │ OCR Pipeline  │          │ Notification  │
   │ 19 Relational │     │  Encrypted    │      │ Digital PDF   │          │ In-App, Email │
   │ Tables        │     │  PDF/Scan Dir │      │ Tesseract/GVis│          │ & SMS Gateway │
   └───────────────┘     └───────────────┘      └───────────────┘          └───────────────┘
```

---

## 3. Key Pillars & Architectural Highlights

### Pillar 1: Dual-Truth Verification Engine
Every single financial data point (FDR Number, Principal Amount, Maturity Date, Interest Rate, IFSC Code, Joint Name status) is evaluated across **three independent truth sources**:
1. **Declared Data**: What the educational institution claims in its application.
2. **OCR Read Data**: Extracted by automated optical character recognition from uploaded receipts.
3. **Bank Confirmed Data**: Direct response from the bank's Core Banking System or nodal officer.

Every field displays a trust state badge:
- `[DECLARED]`: Submitted by college, uncorroborated.
- `[OCR_CONSISTENT]`: College declaration matches document text extraction.
- `[BANK_VERIFIED]`: Directly authenticated by the issuing bank's records.
- `[MISMATCH]`: Inconsistency detected between sources (triggers explainable alert).

### Pillar 2: Zero-Block Bank Verification Hub
Technical disparity among Indian commercial and cooperative banks is resolved through a **4-tiered resilient verification architecture**:
- **Tier 1 (Direct API Integration)**: Automated query against the bank’s Core Banking System (CBS) sandbox simulating the RBI Account Aggregator framework.
- **Tier 2 (Anti-Rubber-Stamp Blind Web Link)**: For banks lacking live APIs, an automated, one-time, cryptographically signed link (`/bank-link/:token`, 7-day TTL) is emailed to the verified branch manager. **Institution-declared figures are strictly hidden** so bank officers must independently enter CBS figures blind.
- **Tier 3 (Dedicated Bank Nodal Portal)**: Bank officials log into their designated portal to query pending requests, look up their CBS internal ledger, and confirm/flag lien status in bulk.
- **Tier 4 (Officer Manual Physical Verification)**: Scrutiny Officers can record officially stamped physical letters received from bank branches with mandatory scan attachment.

### Pillar 3: Explainable 20-Rule Fraud & Anomaly Engine
SecureDeposit runs every submission and renewal through **20 deterministic, explainable fraud-detection rules**. The system never acts as an unexplainable "black box" — it surfaces the exact rule ID, statutory regulation violated, and side-by-side evidence:

| Rule ID | Severity | Rule Description & Detection Logic | AICTE Regulation / Security Objective |
| :---: | :---: | :--- | :--- |
| **R01** | `CRITICAL` | Minimum Statutory Deposit Requirement Check | Flags deposits below mandatory threshold for intake. |
| **R02** | `CRITICAL` | Mandatory Joint Name Compliance Check | Verifies FDR is issued in joint name with AICTE Member Secretary. |
| **R03** | `CRITICAL` | Minimum Mandatory Tenure (5 Years / 60 Months) | Flags short-term deposits that violate tenure norms. |
| **R04** | `HIGH` | Issuing Bank Schedule Status | Validates issuing bank belongs to RBI Scheduled Commercial Banks. |
| **R05** | `CRITICAL` | Amount in Figures vs Amount in Words Mismatch | Catches numerical tampering where words say "Two Lakh" but figures say "₹25,00,000". |
| **R06** | `HIGH` | Valid Indian Financial System Code (IFSC) Structure | Validates 11-character regex structure of IFSC codes. |
| **R07** | `CRITICAL` | IFSC Bank Code vs Declared Bank Entity Match | Catches counterfeit IFSC codes belonging to different banks. |
| **R08** | `HIGH` | Branch Geographic Location vs Institution Region | Flags out-of-state/suspicious branch allocations. |
| **R09** | `CRITICAL` | **Cross-Institution Duplicate FDR Detection** | Catches the same FDR number registered across multiple colleges. |
| **R10** | `CRITICAL` | Intra-Institution Duplicate Instrument Number | Prevents re-submitting an existing active deposit. |
| **R11** | `CRITICAL` | **Cryptographic Document Fingerprint Reuse (SHA-256)**| Catches scanned PDF images recycled across different applications. |
| **R12** | `HIGH` | Post-Dated Issue Date or Excessive Back-Dating | Flags chronological impossibilities in issue/maturity dates. |
| **R13** | `CRITICAL` | **Declared Amount vs OCR Extracted Amount Discrepancy**| Flags manual data entry typos and deliberate inflation. |
| **R14** | `HIGH` | Declared Dates vs OCR Extracted Dates Discrepancy | Catches maturity date tampering between scan and form. |
| **R15** | `CRITICAL` | **Document Internal Word vs Figure OCR Conflict** | Flags scans where the physical document itself was tampered with. |
| **R16** | `CRITICAL` | Mandatory Official Lien Marking Confirmation | Checks existence of unequivocal non-encashment lien to AICTE. |
| **R17** | `HIGH` | Authorized Bank Branch Manager Signatory Presence | Flags receipts lacking branch stamp and manager signature. |
| **R18** | `HIGH` | Auto-Renewal Instruction Clause Verification | Validates auto-rollover instructions where stipulated by APH. |
| **R19** | `CRITICAL` | Core Banking Verification Confirmation Discrepancy | Flags differences between bank CBS lookup and submitted FDR. |
| **R20** | `CRITICAL` | **Continuous Re-Verification & Silent Encashment Catch**| **Detects post-approval unauthorized premature encashment.** |

### Pillar 4: Automated State Machine & T-30 Statutory Lock
Deposit lifecycles are governed by a strictly enforced daily scheduler:
$$\text{SUBMITTED} \longrightarrow \text{UNDER\_SCRUTINY} \longrightarrow \text{VERIFIED} \longrightarrow \text{ACTIVE} \longrightarrow \text{EXPIRING\_SOON} \longrightarrow \text{ACTION\_REQUIRED} \longrightarrow \text{MATURED} \longrightarrow \text{OVERDUE}$$

- **Reminder Ladder**: Holiday-aware notifications are dispatched at **T-90, T-60, T-30, T-7, T-0, and T+7 days**.
- **T-30 Automatic Portal Lockout**: At exactly 30 days prior to maturity, if renewal proof has not been accepted, the institution’s portal is clamped with an **`HTTP 423 Locked`** status. New FDR submissions, academic intake expansions, and NOC requests are blocked until compliance is restored.
- **Automated SLA Escalation Ladder**: Overdue renewal tickets automatically escalate from the Regional Officer (Level 1) to the Approving Authority (Level 2) and Bureau Head (Level 3) if neglected.

### Pillar 5: Guarded Release Workflow & 5-Step Courier Tracker
Refund requests are protected against premature or unauthorized liquidation through a **strict two-person rule** and automated pre-condition checks:
1. **Automated 6-Gate Pre-Condition Engine**:
   - Zero open compliance/vigilance cases against the college.
   - Zero open audit or anomaly flags on the instrument.
   - Active, verified deposit standing.
   - Valid excess-deposit ground (APH approved closure or intake reduction).
   - Bank lien confirmation recorded.
   - Legally executed statutory non-encashment undertaking attached.
2. **Two-Person Rule Separation of Duties**:
   - Scrutiny Officers can only investigate and **Recommend Release** (`RECOMMENDED`).
   - Only the **Competent Approving Authority** can **Sanction Release** (`SANCTIONED`).
3. **Discharge Letter Generation & Courier-Style Tracker**:
   - Upon sanction, the portal issues an official AICTE Discharge Letter PDF with QR code and cryptographic digest.
   - Both the institution and authorities track the 5 steps in real time:
     `Requested ➔ Under Scrutiny ➔ Recommended ➔ Sanctioned ➔ Processed & Released`

---

## 4. Master 15 Unique Selling Propositions (USPs)

| # | USP Identifier | Technical Feature | Implementation File & Endpoint |
| :-: | :--- | :--- | :--- |
| **1** | **USP-01** | **Complete Lifecycle Lineage & Event Trees** | `services/lifecycle.py`, `GET /instruments/{id}` |
| **2** | **USP-02** | **Smart Reminders + Auto-Escalation Ladder** | `services/monitor.py`, `services/alerts.py`, `GET /alerts/escalations` |
| **3** | **USP-03** | **4-Route Authenticity Verification Hub** | `services/verification.py`, `POST /instruments/{id}/verify-bank` |
| **4** | **USP-04** | **Hybrid CBS API + Blind Nodal Fallback** | `services/mock_bank.py`, `POST /bank-link/{token}` |
| **5** | **USP-05** | **Anti-Rubber-Stamp Blind Bank Confirmation** | `components/BankConfirmPortal.tsx`, `POST /bank/confirm` |
| **6** | **USP-06** | **Explainable 20-Rule Fraud Detection Engine** | `services/rules.py`, `POST /instruments/cross-check` |
| **7** | **USP-07** | **Interactive Time-Travel Simulation Lab** | `services/monitor.py`, `POST /admin/demo/clock` |
| **8** | **USP-08** | **T-30 Statutory Lock & Institutional Clamp** | `models.py` (InstitutionLock), `components/InstitutionPortal.tsx` |
| **9** | **USP-09** | **Guarded Two-Person Release Protocol** | `services/refunds.py`, `POST /refunds/{id}/action` |
| **10** | **USP-10** | **Cryptographic SHA-256 Tamper-Evident Ledger**| `services/audit.py`, `GET /audit/verify` |
| **11** | **USP-11** | **Fernet AES-128-CBC Encrypted Document Vault**| `services/documents.py`, `GET /documents/{id}/download` |
| **12** | **USP-12** | **Continuous Post-Approval Encashment Catch** | `services/monitor.py`, `POST /admin/demo/simulate-encashment` |
| **13** | **USP-13** | **Multi-Source Dual-Truth Field Trust Badges** | `services/fields.py`, `GET /instruments/{id}/fields` |
| **14** | **USP-14** | **India Stack DigiLocker & Aadhaar eSign Hub** | `components/InstitutionPortal.tsx` |
| **15** | **USP-15** | **Bilingual Portal Interface (NEP 2020 / Bhashini)**| `components/Header.tsx`, `components/ExploreHome.tsx` |

---

## 5. India Stack Integrations (DigiLocker & Aadhaar eSign)

SecureDeposit is architected natively for the **Digital India / India Stack ecosystem**:

```
 ┌──────────────────────┐         ┌──────────────────────┐
 │   DigiLocker Vault   │         │  Aadhaar eSign Gate  │
 │  (UIDAI / MeitY Hub) │         │ (C-DAC / NSDL e-Gov) │
 └──────────┬───────────┘         └──────────┬───────────┘
            │                                │
            ▼ (1-Click PKI Ingestion)        ▼ (IT Act Sec 3A Legal Stamp)
 ┌───────────────────────────────────────────────────────┐
 │               SecureDeposit Integration               │
 │ • Pulls verified FDR certificates & lien letters      │
 │ • Digital Undertaking authentication with OTP (123456)│
 │ • Zero physical paper handling required               │
 └───────────────────────────────────────────────────────┘
```

1. **DigiLocker 1-Click Electronic Document Import**:
   - Technical colleges import official FDR certificates directly from their institution’s DigiLocker vault.
   - Documents arrive pre-verified with cryptographic PKI signatures (`✓ PKI Verified`), eliminating manual uploads.
2. **Aadhaar eSign Gateway for Statutory Undertakings**:
   - Compliant with **Information Technology Act 2000 (Section 3A)**.
   - The institution head authenticates the statutory non-encashment undertaking via Aadhaar OTP (simulated via gateway with test OTP `123456`).
   - A digital audit stamp with the signatory name, UIDAI reference, and timestamp is permanently embedded into the release record.

---

## 6. Cryptographic Hash-Chained Audit Ledger

To satisfy Central Vigilance Commission (CVC) guidelines and Comptroller & Auditor General (CAG) audit standards, every state change, document upload, and verification decision is written to an immutable hash chain:

$$\text{Block Hash}_N = \text{SHA-256}\Big(\text{Block Hash}_{N-1} \;\|\; \text{Canonical JSON}(\text{Audit Record}_N)\Big)$$

### Mathematical Proof of Tamper Resistance
- Any out-of-band manipulation (such as an insider running `UPDATE audit_log SET ...` in raw SQL) immediately breaks the chain linkage:
  $$\text{SHA-256}(\text{Modified Data}) \neq \text{Stored Hash}$$
- The verification endpoint (`GET /api/v1/admin/audit/verify`) mathematically traverses the ledger and pinpoints the exact entry where tampering occurred.
- The built-in **Interactive Audit Chain Visualizer** enables administrators and judges to simulate malicious database tampering on Row #10 (turning the block bright red with broken link indicators) and restore it to green in one click.

---

## 7. Bilingual Interface (NEP 2020 & Bhashini Ready)

In adherence to the **National Education Policy (NEP 2020)** promoting vernacular accessibility in governance:
- The top navigation bar includes an instant **EN / हिन्दी** toggle.
- Translates navigation menus, KPI cards, and dashboard telemetry in real time.
- Pre-configured for direct integration with the Government of India’s **Bhashini Language Translation Engine**.

---

## 8. Statutory Compliance Certificate Generator

Technical institutions can instantly generate and export an **Official AICTE Statutory Security Deposit Compliance Certificate**:
- Features the national emblem (Ashok Stambh), gold ornamental borders, and formal legal declaration.
- Embeds a dynamic verification QR code linking to the live deposit record.
- Stamped with the SHA-256 cryptographic digest of the active instruments.
- Fully print-ready and exportable as PDF for state licensing bodies, affiliating universities, and accreditation councils (NBA/NAAC).

---

## 9. Demo Accounts & Role Matrix

Every account uses the universal testing password: **`Password@123`**.

| Role Name | Email Address | Assigned Functional Scope & Test Scenario |
| :--- | :--- | :--- |
| **Technical Institution** | `college1@aicte-demo.in` | **Demo Institute of Technology, Pune.** Clean institution with an active deposit and eligible extra FDR for guarded release. |
| **Overdue Locked College**| `college5@aicte-demo.in` | **Apex College of Engineering.** Triggers **`HTTP 423 Locked`** state due to overdue renewal pending (T-30). |
| **Non-Compliant College** | `college8@aicte-demo.in` | **National Institute of Management.** Demonstrates **`BLOCKED BY PRE-CONDITIONS`** (open compliance case blocks refund). |
| **Scrutiny Officer** | `officer@aicte-demo.in` | Scrutiny queue, Dual-Truth split view, bank verification trigger, anomaly confirm/dismiss, recommend release. |
| **Approving Authority** | `approver@aicte-demo.in` | Final approval of new FDRs, release sanctioning (two-person rule), SLA escalation management. |
| **Scheduled Bank Official**| `bank.sbi@aicte-demo.in` | State Bank of India nodal queue, mock CBS ledger lookup, blind entry mode, bank outage toggle. |
| **Central Administrator** | `admin@aicte-demo.in` | Bureau head access, Time-Travel Clock (+66d, +8d), silent encashment simulator, audit tamper test, golden re-seed. |
| **Statutory Auditor** | `auditor@aicte-demo.in` | Strict read-only access enforced across every API endpoint; audit chain inspection. |

---

## 10. Quick Start & Launcher Guide

### One-Click Local Launcher (Windows PowerShell)

Ensure **Python 3.10+** and **Node.js 18+** are installed.

```powershell
# Clone the repository
git clone https://github.com/shreyank26pal-dev/fdr-portal.git
cd fdr-portal

# One-Click Launch (initializes SQLite DB, runs seed, starts FastAPI & Vite Frontend)
powershell -ExecutionPolicy Bypass -File .\start-securedeposit.ps1
```

Once launched:
- **Frontend Portal**: `http://localhost:5173`
- **FastAPI Interactive Swagger**: `http://127.0.0.1:8000/docs`
- **System Health & OCR Diagnostics**: `http://127.0.0.1:8000/health`

### Docker Compose Launcher (PostgreSQL Production Stack)

```bash
# Build and run containers (API, PostgreSQL, Mailpit)
docker compose up --build

# In another terminal, reset to clean seed at any time:
docker compose exec api python -m scripts.seed --reset
```
- **Mailpit Email Sandbox**: `http://localhost:8025` (captures all simulated notifications and blind links).

---

## 11. Testing & Verification Suite

The repository includes a comprehensive automated test suite verifying the end-to-end user journeys:

```bash
# Run backend pytest suite
cd backend
pytest tests/test_demo_flow.py -v
```

### Verified Test Capabilities (11/11 Passing)
- `test_01_health_and_seed_data`: Verifies 40 institutions and 123 initial instruments.
- `test_02_rbac_and_mfa`: Enforces 7-role access boundaries and TOTP authentication.
- `test_03_ocr_and_clean_submission`: Validates OCR extraction and draft saving.
- `test_04_rule_engine_catches_typo`: Asserts R13 and R05 fire on amount discrepancy.
- `test_05_cross_institution_duplicate`: Confirms Rule R09 catches reused FDR numbers.
- `test_06_bank_verification_success`: Validates dual-truth badge flipping on CBS verification.
- `test_07_bank_outage_and_blind_link`: Verifies `SOURCE_UNAVAILABLE` and blind token creation.
- `test_08_time_travel_lock_and_escalate`: Simulates +66d jump, `HTTP 423` lock, and L2 escalation.
- `test_09_continuous_reverification_catch`: Asserts Rule R20 catches premature silent encashment.
- `test_10_guarded_release_two_person_rule`: Tests 6 pre-condition gates and recommendation separation.
- `test_11_audit_chain_tamper_and_verify`: Mathematically proves broken block detection on Row #10.

---

## 12. Demo Video Clips & Voiceover Sync Suite

All 11 motion video clips required for the **5-minute YouTube cut** are pre-recorded at **1920×1080 Full HD (10 fps)** with visual cursor tracking and saved in [`docs/video_clips/`](docs/video_clips/):

| Scene | Clip Filename | Resolution | Length | Key Highlights Captured on Screen |
| :---: | :--- | :---: | :---: | :--- |
| **01** | `clip_01_landing_hero_cards.mp4` | 1080p | 31.4s | Hero banner, 4 problem cards, Declared vs Bank-verified badges on FDR `40112233445`. |
| **02** | `clip_02_signin_national_picture.mp4` | 1080p | 21.5s | 1-Click login, Explore Hub 8 KPI tiles, live telemetry, bilingual EN/हिन्दी toggle. |
| **03** | `clip_03_ocr_submission_typo_ack.mp4` | 1080p | 46.8s | Clean receipt OCR auto-fill, ₹2.5L typo, R13+R05 flags, fix to ₹25L, **Official Ack No.** |
| **04** | `clip_04_digilocker_india_stack.mp4` | 1080p | 15.9s | India Stack DigiLocker modal, UIDAI verified Aadhaar link, 1-click fetch, PKI badge. |
| **05** | `clip_05_scrutiny_dual_truth_verification.mp4` | 1080p | 49.5s | Scrutiny queue, Dual-Truth split view, CBS verification, **badges flip to Bank-verified**. |
| **06** | `clip_06_fraud_gallery_tamper_dup.mp4` | 1080p | 36.5s | Tampered words flag (**R15**), duplicate FDR alert (**R09**), Confirm/Dismiss buttons. |
| **07** | `clip_07_bank_outage_blind_confirmation.mp4` | 1080p | 53.6s | SBI offline toggle, `SOURCE_UNAVAILABLE` chip, one-time blind link, mock CBS lookup. |
| **08** | `clip_08_time_travel_lock_encashment.mp4` | 1080p | 42.7s | Time-Travel +66d jump, College 5 red **`HTTP 423 LOCKED`** banner, **R20 CRITICAL** alert. |
| **09** | `clip_09_guarded_release_esign_tracker.mp4` | 1080p | 59.7s | College 8 pre-condition block, Aadhaar OTP eSign, two-person rule, 5-step courier tracker. |
| **10** | `clip_10_audit_chain_tamper_recovery.mp4` | 1080p | 27.6s | Intact SHA-256 chain, Block #10 red tamper alert, 1-click restore to green, B-roll. |
| **Bonus**| `bonus_clip_aicte_deposit_certificate.mp4` | 1080p | 11.4s | AICTE Deposit Certificate parchment modal with gold seal, QR code, and SHA-256 stamp. |

> 📖 **Video Editor Guide:** For exact word-for-word voiceover sync scripts, zoom timestamps, and trimming instructions, see [`docs/video_clips/README.md`](docs/video_clips/README.md).

---

## 13. Honesty Rule & Simulation Transparency

In strict compliance with hackathon integrity guidelines, simulated components are **transparently labeled on screen**:
- Responses from the simulated banking sandbox include `"simulated": true` and `source: SIMULATED_AA_SANDBOX`.
- DigiLocker and Aadhaar eSign modules are labeled *"Simulated India Stack Gateway"*.
- SMS and email notifications are logged as `SIMULATED` when running without a physical SMTP gateway.
- The Time-Travel Clock and Chaos Lab are classified as `[DEMO TOOLS]` and are automatically stripped when `DEMO_MODE=false`.

---

## 👥 Developed By Team SecureDeposit

Built for the **Smart India Hackathon (SIH26265)** under the aegis of the **All India Council for Technical Education (AICTE)**, Ministry of Education, Government of India.
