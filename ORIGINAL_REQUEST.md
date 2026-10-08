# Original User Request

## Initial Request — 2026-10-07T18:35:59Z

# Teamwork Project Prompt — RE:TRACE

> Status: Launched
> Goal: Execute multi-agent engineering workflow via teamwork_preview
> Requested team: Specialized team of 9 agents (Product/Architecture, Climate & Circular Economy Research, AI/Computer Vision, Backend, Blockchain/Solidity, Frontend, Security, QA/Adversarial Judge, Demo/Storytelling)

Use specialized agents for: Product/Architecture, Climate & Circular Economy Research, AI/Computer Vision, Backend, Blockchain/Solidity, Frontend, Security, QA/Adversarial Judge, Demo/Storytelling.

RE:TRACE is a circular economy and climate tracking platform for the Sustainable Supply Chains track, providing verifiable end-to-end digital product passport (DPP) traceability, AI-driven recycling observation, deterministic mass-balance verification, cryptographic evidence integrity commitments, and tamper-evident blockchain lifecycle tracking.

Working directory: /Users/mriduldabral/Downloads/Anti Gravity/Climate Change Hackathon
Integrity mode: demo

---

## 1. System Vision & Phased Multi-Agent Workflow

The engineering team must advance autonomously through seven sequential phases without stopping at design documents:
- **Phase 1**: Architecture, canonical schemas, API contracts, smart-contract interfaces, and verification models.
- **Phase 2**: Thin end-to-end vertical slice (programmatically executable).
- **Phase 3**: Cross-service integration.
- **Phase 4**: QA, automated adversarial test suite, and edge-case validation.
- **Phase 5**: Security audit and hardening.
- **Phase 6**: UI dashboard and demo scenario polish.
- **Phase 7**: Final IEEE-grade hackathon readiness.

Agents must not independently redesign the architecture. All agents must inspect existing canonical specifications before implementing dependent functionality.

---

## 2. Requirements

### R1. Canonical System Architecture & Controlled Interface Freeze (Phase 1 Gate)
Before writing implementation code, establish a single canonical source of truth under `/shared` (or `/docs/schemas`):
1. **Repository Structure**: Organized directories for `contracts/`, `backend/`, `ml/`, `frontend/`, `shared/` (schemas/contracts), `tests/`, and `docs/`.
2. **Canonical Domain Schemas**: Formal Pydantic models / JSON Schemas for Digital Product Passports (DPP), Recycling Events, Material Compositions, Provenance Metadata, and Proof-of-Recycling (PoR) Certificates.
3. **API Contracts**: OpenAPI 3.1 specification for Backend endpoints, ingestion payloads, and AI inference contracts.
4. **Smart-Contract Interfaces**: Solidity interfaces (`.sol`) defining DPP registration, event anchoring, lifecycle state transitions, and certificate verification.
5. **Lifecycle State Machine**: Strict state transition specification governing product lifecycle:
   $$\text{MANUFACTURED} \rightarrow \text{IN\_USE} \rightarrow \text{RETURNED} \rightarrow \text{RECYCLING\_PENDING} \rightarrow \text{RECYCLING\_VERIFIED} \rightarrow \text{MATERIALS\_RECOVERED}$$
   with `FLAGGED` as a dedicated investigation/verification state. A recycling event that fails deterministic verification, evidence integrity verification, or required validation may transition to `FLAGGED` from `RECYCLING_PENDING` or the applicable verification state; `FLAGGED` must not be treated as successful recycling and must require authorized resolution before any transition to `RECYCLING_VERIFIED`. Every transition must enforce explicit guard conditions and authorized roles. Smart contracts and backend validation must strictly agree.
6. **Controlled Interface Freeze Rule**: Following Phase 1 Gate completion, shared interfaces are considered frozen. If an agent discovers a genuine architectural flaw, the interface may be changed only through a documented Architecture Decision Record (ADR) under `docs/adr/` containing:
   - Reason for change
   - Affected components
   - Compatibility impact
   - Migration/update requirements
   - Regression tests
   Agents must NEVER independently redefine shared interfaces.

### R2. Canonical Evidence Commitment Pipeline & Provenance Standards
1. **Evidence Commitment Model**: Implement the simplified canonical evidence commitment pipeline:
   $$\text{Evidence Files} \rightarrow \text{Individual SHA-256 Hashes} \rightarrow \text{Canonical Evidence Manifest} \rightarrow \text{Canonical Evidence-Bundle SHA-256} \rightarrow \text{Blockchain Commitment}$$
   Use `keccak256` where appropriate for on-chain EVM commitments. Merkle trees are optional and must not be implemented unless a concrete technical benefit is demonstrated. The canonical serialization method used before hashing must be deterministic (e.g., canonical JSON key sorting) and documented.
2. **Evidence Bundle Contents**: Where applicable, evidence bundles must contain: evidence identifiers, references to raw input files, individual evidence hashes, AI model/provider, AI model version (where available), inference timestamp, observations, confidence values, material estimates, mass-balance inputs and results, verification result, timestamps, and canonical evidence-bundle commitment.
3. **Evidence Terminology & Provenance Categories**: Replace references to industrial sensors with "image/video evidence and optional structured measurement evidence". Do not imply physical industrial sensors exist unless actually integrated. Every important data value must explicitly declare its provenance category:
   - `MEASURED` (verified physical scale/meter reading)
   - `OBSERVED` (human/operator visual observation)
   - `AI_ESTIMATED` (output from computer vision inference)
   - `REFERENCE_ASSUMED` (OEM bill-of-materials or baseline data)
   - `SIMULATED` (test fixture or synthetic data)
   Never present simulated, assumed, or AI-estimated values as physical measurements. The UI must make this distinction visible where relevant.

### R3. AI Trust Boundary & Deterministic Mass-Balance Verification
1. **AI Trust Boundary**: AI is strictly an observation and estimation layer (identifying observable objects, classifying material categories, estimating material quantities and confidence). AI is NOT proof by itself and must NEVER independently determine that recycling occurred. The verification pipeline must strictly follow:
   $$\text{Physical Evidence} \rightarrow \text{AI Observation} \rightarrow \text{Material Estimation} \rightarrow \text{Deterministic Mass-Balance} \rightarrow \text{Evidence Integrity Check} \rightarrow \text{Verification Decision} \rightarrow \text{Blockchain Anchor} \rightarrow \text{Proof-of-Recycling}$$
   AI output must include: model/provider, version where available, timestamp, observations, confidence scores, and estimated values.
2. **Deterministic Mass-Balance Verification**: Must not use AI for basic conservation-of-mass calculations where deterministic mathematics is sufficient. The model must explicitly represent:
   - Input quantity and input mass
   - Reference material composition
   - Expected material range
   - Process/yield loss factors
   - Recovered material
   - Uncertainty/tolerance bounds
   - Claimed material
   - Verification result
   The system must support three deterministic outcomes:
   - `VALID` $\rightarrow$ `VERIFIED`
   - `BORDERLINE` $\rightarrow$ `REVIEW`
   - `IMPOSSIBLE` $\rightarrow$ `FLAGGED`
   The system and UI must explain mathematically WHY a claim passed, requires review, or failed. The evidence bundle must preserve the assumptions and reference composition values used.

### R4. Thin End-to-End Vertical Slice (Phase 2 Milestone)
Implement and programmatically verify a thin, fully functional end-to-end vertical slice executing the complete pipeline:
$$\text{Product Passport} \rightarrow \text{Recycling Event} \rightarrow \text{AI Observation} \rightarrow \text{Material Estimation} \rightarrow \text{Mass-Balance Verification} \rightarrow \text{Evidence Bundle} \rightarrow \text{Evidence Hash} \rightarrow \text{Blockchain Anchor} \rightarrow \text{Lifecycle Update} \rightarrow \text{Proof-of-Recycling Certificate}$$
Everything else is secondary until this vertical slice works end-to-end.
Technology stack:
- **Backend**: FastAPI (Python 3.11+) with Pydantic validation
- **Frontend**: Next.js (React) + Tailwind CSS
- **Smart Contracts**: Solidity on EVM, compiled and tested via Foundry or Hardhat
- **AI/CV**: Dual-mode execution (Gemini Multimodal API for live demo; deterministic fixtures for tests)

### R5. Anti-Replay, Duplicate Protection & Blockchain Truthfulness
1. **Replay & Duplicate Protection**: Every recycling event must have a unique identifier. Submitting the same recycling event more than once must be rejected or explicitly identified as a duplicate. Duplicate Proof-of-Recycling certificates for the same event must be prohibited. Replayed lifecycle transitions must be prevented.
2. **Blockchain Truthfulness**: Never fabricate transaction hashes, block numbers, contract addresses, deployment results, confirmations, explorer links, or wallet activity. If using local EVM infrastructure (Anvil / Hardhat Node), clearly label it `LOCAL TESTNET` or `LOCAL DEVELOPMENT BLOCKCHAIN`. Never present local blockchain records as public testnet transactions. If blockchain connectivity fails, show an unconfirmed/error state rather than pretending the transaction succeeded.
3. **Proof-of-Recycling Certificate**: Every certificate must contain: certificate ID, product ID, recycling event ID, facility ID, verified material quantities, verification result, verification confidence, evidence commitment, blockchain transaction reference, timestamp, and certificate hash. The certificate must be tied to the specific product passport and recycling event, with reproducible verification from the certificate data and blockchain commitment.
4. **Dual-Mode AI Testing**: Live/demo mode may use the Gemini Multimodal API. Automated tests must use deterministic replayable fixtures / mock inference. Automated tests must not depend on Gemini API availability, internet connectivity, API keys, or nondeterministic model output. Clearly distinguish fixture/simulated inference from live inference.
5. **Scope Guardrails**: Do NOT introduce unnecessary DAOs, tokenomics, cryptocurrency, DeFi, custom blockchains, custom consensus, unnecessary ZK proofs, unnecessary Merkle trees, large custom foundation models, Kubernetes, mobile applications, or real IoT hardware unless the core vertical slice is complete, tested, and stable.

### R6. System Trust & Limitations Boundaries
The documentation and system interfaces must explicitly document what RE:TRACE verifies and what it does not verify:
- AI observations are probabilistic estimates, not infallible scientific truth.
- Blockchain anchors prove that evidence and state were recorded at a specific time; they do not prove physical reality occurred merely because a record is on-chain.
- The system does not replace certified industrial mass-flow audits or universal statutory certification.
- Simulated and assumed data must never be claimed as physical ground truth.

### R7. Security Requirements
- Zero private keys or API keys in repository; `.env.example` provided.
- Upload validation enforcing strict MIME types and file-size limits.
- Backend input validation across all endpoints.
- Smart-contract access control and role-based permissions.
- Lifecycle transition guard conditions.
- Safe error handling without credential or secret leakage in logs or responses.
- Compile findings into `docs/security-review.md`.

---

## 3. Acceptance Criteria

### Canonical Specifications (Phase 1 Gate)
- [ ] Single canonical source of truth established under `/shared` or `/docs/schemas` containing formal specifications for domain models, OpenAPI 3.1 endpoints, Solidity interfaces, lifecycle state transitions, mass-balance rules, and evidence bundles.
- [ ] Schema validation script passes against sample test fixtures for passports, evidence bundles, and certificates.
- [ ] Smart-contract interfaces compile without errors using Foundry or Hardhat.
- [ ] Architecture Decision Record (ADR) template and initial records documented under `docs/adr/`.

### Programmatic Vertical Slice Integration Test (`tests/test_vertical_slice.py`)
- [ ] Automated end-to-end test executes the entire pipeline programmatically and offline without requiring a live Gemini API key:
  1. Product creation & passport registration
  2. Passport retrieval & schema validation
  3. Recycling event submission with image reference & declared materials
  4. Deterministic AI fixture replay & provenance tagging
  5. Material quantity and volume estimation
  6. Deterministic mass-balance verification (yielding `VERIFIED`)
  7. Evidence bundle compilation & canonical SHA-256 commitment calculation
  8. Local EVM blockchain transaction anchoring the commitment
  9. Lifecycle transition from `RECYCLING_PENDING` to `RECYCLING_VERIFIED`
  10. Proof-of-Recycling certificate generation
  11. Independent certificate verification against the anchored blockchain commitment
  12. State consistency verification

### Mandatory Adversarial Test Suite (`tests/test_adversarial.py`)
- [ ] **A. Legitimate Recycling**: Expected material range consistent with claim $\rightarrow$ `VERIFIED`.
- [ ] **B. Borderline Material Claim**: Claim near or slightly outside normal tolerance boundary $\rightarrow$ `REVIEW / BORDERLINE`.
- [ ] **C. Impossible Material Claim**: Claim significantly exceeds physically plausible yield $\rightarrow$ `CLAIM FLAGGED`.
- [ ] **D. Evidence Tampering**: Mutating one evidence field or file after anchoring $\rightarrow$ recomputed hash mismatch $\rightarrow$ `EVIDENCE_INTEGRITY_FAILURE`.
- [ ] **E. Duplicate Recycling Event**: Same event ID submitted twice $\rightarrow$ `DUPLICATE / REJECTED`.
- [ ] **F. Duplicate Certificate**: Repeated certificate issuance for same event $\rightarrow$ `REJECTED`.
- [ ] **G. Unauthorized Lifecycle Transition**: Unauthorized actor or invalid state hop $\rightarrow$ `REJECTED`.
- [ ] **H. Malformed Evidence**: Invalid schema or missing provenance $\rightarrow$ `VALIDATION FAILURE`.
- [ ] **I. AI Service Unavailable**: Service down $\rightarrow$ graceful fallback/retry without corrupted state.
- [ ] **J. Blockchain Unavailable**: RPC node offline $\rightarrow$ clear unconfirmed state; never fake success.

### Mandatory Demonstrable UI Scenarios
- [ ] **Scenario A (Legitimate Recycling)**: Product Passport $\rightarrow$ evidence $\rightarrow$ AI observation $\rightarrow$ material estimate $\rightarrow$ mass balance $\rightarrow$ blockchain commitment $\rightarrow$ `VERIFIED` $\rightarrow$ Proof-of-Recycling certificate.
- [ ] **Scenario B (Fraudulent Claim)**: Product Passport $\rightarrow$ claimed material $\rightarrow$ expected physical range $\rightarrow$ large deviation $\rightarrow$ `CLAIM FLAGGED` with explicit mathematical explanation.
- [ ] **Scenario C (Evidence Tampering)**: Original anchored evidence (`VERIFIED`) $\rightarrow$ evidence field modified $\rightarrow$ recomputed commitment mismatch $\rightarrow$ `EVIDENCE_INTEGRITY_FAILURE` visibly flagged.

---

## 4. Autonomous Execution Rules

After Phase 1 architecture and interfaces are established, agents must proceed autonomously through implementation, integration, testing, adversarial validation, security hardening, UI polish, and demo preparation.
- Do not stop at architecture documents.
- Do not expand scope until the core vertical slice works.
- When a fixable problem is found: (1) reproduce it, (2) identify root cause, (3) fix it, (4) add regression test, (5) rerun relevant tests.
- Do not ask the human for trivial engineering decisions.
- Engineering priority order:
  1. Working functionality
  2. Technical defensibility
  3. Security
  4. Reliability
  5. Judgeability
  6. Climate impact
  7. Simplicity
