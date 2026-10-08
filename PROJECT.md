# Project: RE:TRACE — Circular Economy & Climate Tracking Platform

## Architecture
RE:TRACE provides verifiable end-to-end digital product passport (DPP) traceability, AI-driven recycling observation, deterministic mass-balance verification, cryptographic evidence integrity commitments, and tamper-evident blockchain lifecycle tracking for the Sustainable Supply Chains track.

### System Architecture Diagram
```
[Physical Evidence Upload]
         │ (Images / Weighbridge tickets)
         ▼
[Dual-Mode AI Observation Service] (Gemini Multimodal / Deterministic Fixtures)
         │ (Item counts, estimated materials, confidence, anomaly flags)
         ▼
[Deterministic Mass-Balance Engine] (EU Battery Reg 2023/1542, conservation of mass)
         │ (Decisions: VALID -> VERIFIED, BORDERLINE -> REVIEW, IMPOSSIBLE -> FLAGGED)
         ▼
[Cryptographic Evidence Pipeline] (Files -> SHA-256 -> RFC 8785 Canonical Manifest -> Bundle SHA-256 / keccak256)
         │
         ├──────────────────────────────────────────┐
         ▼                                          ▼
[Local EVM Blockchain Ledger]               [Proof-of-Recycling Engine]
(State transitions, evidence anchors)      (Verifiable PoR Certificates)
         │                                          │
         └────────────────────┬─────────────────────┘
                              ▼
                     [FastAPI Backend REST API]
                              ▼
                  [Next.js / React UI Dashboard]
                  (Scenarios A, B, C & Provenance Badges)
```

### Data Flow & Trust Segregation
1. **Physical Evidence**: Raw files uploaded via multipart endpoint with strict MIME sniffing and 25MB limits. Individual SHA-256 computed on ingestion.
2. **AI Observation**: Strictly observation and feature extraction (`AI_ESTIMATED`), never verification decision.
3. **Deterministic Mass-Balance**: Pure closed-form mathematical equations evaluate theoretical mass, yield recovery envelopes, and instrument tolerance. Three outcomes: `VALID` -> `VERIFIED`, `BORDERLINE` -> `REVIEW`, `IMPOSSIBLE` -> `FLAGGED`.
4. **Canonical Evidence Manifest**: RFC 8785 JSON canonicalization sorts keys deterministically.
5. **Cryptographic Commitment**: Manifest hashed via SHA-256 and EVM keccak256.
6. **Blockchain Anchoring**: Event ID, Passport ID, and commitment recorded on-chain via `IRETraceRegistry` / Local EVM Ledger client.
7. **Lifecycle Progression**: Strict state machine: `MANUFACTURED` -> `IN_USE` -> `RETURNED` -> `RECYCLING_PENDING` -> `RECYCLING_VERIFIED` -> `MATERIALS_RECOVERED` (or `FLAGGED`).
8. **Proof-of-Recycling (PoR)**: Verifiable certificate generated only upon verified state and confirmed on-chain commitment.

---

## Feature Inventory

Every feature discovered in the Survey phase is mapped to its assigned milestone:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Canonical Domain Schemas | Formal Pydantic v2 & JSON schemas for DPP, MaterialComposition, ProvenanceMetadata, RecyclingEvent, EvidenceBundle, PoRCertificate | M1 | survey (spec_miner) |
| 2 | Provenance Category Model | Strict 5-category data provenance (`MEASURED`, `OBSERVED`, `AI_ESTIMATED`, `REFERENCE_ASSUMED`, `SIMULATED`) | M1 | survey (spec_miner & domain) |
| 3 | Material Composition & BoM Schema | Hierarchical bill of materials with stoichiometry and BAT yield loss limits | M1 | survey (spec_miner) |
| 4 | Lifecycle State Machine Specification | 7 states with explicit guard condition equations and authorized role matrix | M1 | survey (spec_miner) |
| 5 | OpenAPI 3.1 REST API Specification | Formal OpenAPI 3.1 schema covering all 10 endpoints | M1 | survey (spec_miner) |
| 6 | Solidity Smart-Contract Interfaces | Solidity interface `IRETraceRegistry.sol` defining structs, events, and functions | M1 | survey (spec_miner) |
| 7 | ADR Governance & Template | Initial Architecture Decision Records under `docs/adr/` and interface freeze rule | M1 | survey (spec_miner) |
| 8 | Schema Validation Script | Programmatic validator (`scripts/validate_schemas.py`) validating schemas against test fixtures | M1 | survey (codebase & spec) |
| 9 | Offline Environment Bootstrapper | Script (`scripts/setup_offline_env.py`) indexing 173 cached wheels into `.wheelhouse/` and virtualenv | M1 | survey (codebase) |
| 10 | Circular Economy Datasets | EU Battery Regulation 2023/1542 NMC 622 EV Battery & Smartphone LCO reference datasets | M1 | survey (domain) |
| 11 | Deterministic Mass-Balance Engine | Closed-form conservation of mass and component BAT yield evaluation engine | M2 | survey (spec & domain) |
| 12 | Canonical Evidence Commitment Pipeline | File hashing -> canonical RFC 8785 manifest -> bundle SHA-256 -> keccak256 commitment | M2 | survey (spec_miner) |
| 13 | Local EVM Ledger & Anchor Client | EVM-compliant state ledger client honoring Section R5 blockchain truthfulness | M2 | survey (codebase & spec) |
| 14 | Proof-of-Recycling Certificate Engine | Certificate generator and independent cryptographic verification engine | M2 | survey (spec_miner) |
| 15 | Thin Vertical Slice Test Runner | `tests/test_vertical_slice.py` executing all 12 stages programmatically and offline | M2 | survey (spec_miner) |
| 16 | FastAPI Core Backend Services | REST endpoints implementation for passports, evidence, events, verification, and certs | M3 | survey (spec_miner) |
| 17 | Dual-Mode AI Observation Service | Multimodal Gemini client + deterministic offline replayable fixture client | M3 | survey (domain & codebase) |
| 18 | Local Storage Service & File Hasher | Streaming file upload with SHA-256 calculation and mime-sniffing | M3 | survey (spec_miner) |
| 19 | Replay & Duplicate Event Guard | Backend & contract anti-replay preventing duplicate event ingestion | M3 | survey (spec_miner) |
| 20 | Duplicate Certificate Prevention | Enforce exactly one certificate per recycling event | M3 | survey (spec_miner) |
| 21 | Adversarial Test Suite Runner | `tests/test_adversarial.py` implementing automated cases A through J | M4 | survey (spec_miner) |
| 22 | FLAGGED State & Quarantine Protocol | State isolation for suspicious/impossible claims; auditor-only resolution | M4 | survey (spec_miner) |
| 23 | Post-Anchoring Integrity Verifier | Recomputes evidence commitment and flags tampering (`EVIDENCE_INTEGRITY_FAILURE`) | M4 | survey (spec_miner) |
| 24 | Security Hardening & Upload Sanitizer | Strict MIME sniffing, 25MB limits, credential leakage prevention, `docs/security-review.md` | M5 | survey (spec_miner) |
| 25 | UI Dashboard & Demonstrable Scenarios | Next.js/React or Streamlit UI executing Scenario A, B, C with color-coded provenance badges | M6 | survey (spec_miner) |
| 26 | Truthfulness & Blockchain Indicator | Clear `LOCAL TESTNET` labelling, RPC status check, unconfirmed transaction states | M6 | survey (spec_miner) |
| 27 | Final IEEE-Grade Hackathon Readiness | End-to-end documentation, demo walk-through, trust boundaries report, victory audit | M7 | survey (all) |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Phase 1: Canonical Architecture & Interface Freeze | Canonical schemas under `/shared`, OpenAPI 3.1 contract, Solidity interfaces, state machine rules, offline wheelhouse setup, ADRs, schema validator | none | PLANNED |
| M2 | Phase 2: Thin End-to-End Vertical Slice | Programmatic execution of 12-step vertical slice offline in `tests/test_vertical_slice.py`, mass-balance engine, local EVM ledger client, certificate generator | M1 | PLANNED |
| M3 | Phase 3: Cross-Service Integration | Complete FastAPI backend, dual-mode AI service, storage manager, anti-replay guards, lifecycle controller | M2 | PLANNED |
| M4 | Phase 4: QA & Automated Adversarial Suite | `tests/test_adversarial.py` cases A through J, stress tests, tampering detection, offline verification | M3 | PLANNED |
| M5 | Phase 5: Security Audit and Hardening | Upload validation, RBAC, transition guards, zero-leakage error handling, `docs/security-review.md` | M4 | PLANNED |
| M6 | Phase 6: UI Dashboard & Demo Scenarios | Interactive UI dashboard, Scenarios A, B, C, mathematical explanation visuals, provenance badges | M5 | PLANNED |
| M7 | Phase 7: IEEE Hackathon Readiness & Audit | Full system integration, documentation, demo walkthroughs, final Victory verification | M6 | PLANNED |

---

## Interface Contracts

### Shared Schemas (`/shared/schemas/`) ↔ Backend (`backend/app/`)
- `DigitalProductPassport`: Pydantic model with immutable identifiers, Bill of Materials (`MaterialComposition`), lifecycle state.
- `RecyclingEvent`: Pydantic model with unique UUID `event_id`, `passport_id`, `facility_id`, `intake_gross_mass_kg`, `claimed_materials`, `evidence_file_ids`.
- `EvidenceBundle`: Pydantic model with `evidence_files`, `ai_observation`, `mass_balance_result`, `canonical_manifest_sha256`, `bundle_keccak256_commitment`.
- `ProofOfRecyclingCertificate`: Pydantic model with `certificate_id`, `passport_id`, `event_id`, `verified_material_quantities`, `evidence_commitment`, `tx_hash`.

### AI Observation Service (`ml/`) ↔ Mass-Balance Engine (`backend/app/services/` or `shared/`)
- `AIObservationResult`:
  - `provider`: str
  - `model`: str
  - `inference_timestamp`: datetime
  - `execution_mode`: "LIVE_GEMINI" | "DETERMINISTIC_FIXTURE"
  - `detected_items`: list[DetectedItem]
  - `material_estimates`: dict[str, float]
  - `confidence`: float
  - `anomaly_flags`: list[str]
  - `provenance_category`: ProvenanceCategory.AI_ESTIMATED

### Mass-Balance Engine ↔ Blockchain Ledger
- Verification output:
  - `decision`: "VALID" | "BORDERLINE" | "IMPOSSIBLE"
  - `mathematical_explanation`: str
  - If `VALID`: Triggers `anchorRecyclingEvidence(eventId, passportId, commitment)` and state transition to `RECYCLING_VERIFIED`.
  - If `BORDERLINE`: State remains `RECYCLING_PENDING` (tagged `REVIEW_REQUIRED`).
  - If `IMPOSSIBLE`: State transitions to `FLAGGED`.

### Smart Contract Interface (`IRETraceRegistry.sol`)
- Enums: `LifecycleState { MANUFACTURED, IN_USE, RETURNED, RECYCLING_PENDING, RECYCLING_VERIFIED, MATERIALS_RECOVERED, FLAGGED }`
- Functions:
  - `registerPassport(bytes32 passportId, bytes32 bomHash) external`
  - `anchorRecyclingEvidence(bytes32 eventId, bytes32 passportId, bytes32 evidenceCommitment) external`
  - `transitionLifecycleState(bytes32 passportId, LifecycleState newState, bytes32 evidenceRef) external`
  - `issueCertificate(bytes32 certificateId, bytes32 eventId, bytes32 passportId, bytes32 certHash, bytes32 commitment) external`
  - `flagProduct(bytes32 passportId, bytes32 eventId, string calldata reason) external`
  - `resolveFlag(bytes32 passportId, LifecycleState targetState, string calldata notes) external`

---

## Code Layout
```
/Users/mriduldabral/Downloads/Anti Gravity/Climate Change Hackathon/
├── .agents/                      # Multi-agent coordination metadata
├── .wheelhouse/                  # Offline Python binary wheels extracted from cache
├── shared/                       # Canonical Source of Truth (Frozen at Phase 1 Gate)
│   ├── schemas/                  # Pydantic v2 & JSON schemas
│   │   ├── __init__.py
│   │   ├── dpp.py
│   │   ├── provenance.py
│   │   ├── material.py
│   │   ├── recycling_event.py
│   │   ├── evidence_bundle.py
│   │   └── por_certificate.py
│   ├── contracts/                # Canonical Solidity interfaces
│   │   ├── IRETraceRegistry.sol
│   │   └── IRETraceLifecycle.sol
│   ├── domain/                   # Canonical business logic models
│   │   ├── lifecycle.py
│   │   ├── mass_balance.py
│   │   └── evidence_hasher.py
│   └── fixtures/                 # Reference datasets (EU Battery NMC 622 & LCO)
│       └── reference_materials.py
├── backend/                      # FastAPI Python Application
│   └── app/
│       ├── api/v1/               # API Routers (passports, evidence, recycling, certs, blockchain)
│       ├── core/                 # Config, security, error handlers, logging
│       ├── models/               # Domain database/state models
│       ├── services/             # Business logic (mass_balance, blockchain_client, storage, certs)
│       └── main.py               # FastAPI entrypoint
├── contracts/                    # Solidity Contracts & Foundry/Hardhat configs
│   ├── contracts/                # RETraceRegistry.sol implementation
│   ├── scripts/                  # Deployment & verification scripts
│   └── test/                     # Contract unit tests
├── ml/                           # AI & Computer Vision Service
│   ├── inference/                # Dual-mode observation adapters (Gemini & Fixture)
│   ├── data/fixtures/            # Replayable deterministic offline AI fixtures
│   └── models/                   # Prompt templates & vision schemas
├── frontend/                     # UI Dashboard (Next.js / React / Tailwind or Streamlit)
├── tests/                        # Automated Test Suites
│   ├── test_vertical_slice.py    # Thin end-to-end vertical slice (Phase 2 Milestone)
│   ├── test_adversarial.py       # Mandatory adversarial test suite Cases A-J (Phase 4 Milestone)
│   ├── test_mass_balance.py      # Mathematical unit tests
│   ├── test_evidence_pipeline.py # Hashing & canonical manifest tests
│   └── test_state_machine.py     # Lifecycle guard tests
├── docs/                         # Specifications & Architecture Documentation
│   ├── adr/                      # Architecture Decision Records (ADR-001, etc.)
│   ├── security-review.md        # Security audit findings (Phase 5)
│   ├── system-trust-boundaries.md# System boundaries and limitations (R6)
│   └── demo-walkthrough.md       # Step-by-step guide for Scenarios A, B, C
└── scripts/                      # Utility and automation scripts
    ├── setup_offline_env.py      # Offline wheelhouse & venv installer
    ├── validate_schemas.py       # Phase 1 Gate validation script
    └── run_tests.sh              # Test runner script
```
