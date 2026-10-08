# ADR-001: Canonical Architecture & Controlled Interface Freeze

- **Status**: ACCEPTED & FROZEN
- **Date**: 2026-10-07
- **Author**: Architecture & Schemas Worker (`worker_m1_1`)
- **Scope**: Entire RE:TRACE platform (`shared/`, `backend/`, `ml/`, `contracts/`, `frontend/`, `tests/`)

---

## 1. Context and Problem Statement

RE:TRACE is a multi-agent circular economy and climate tracking platform providing end-to-end Digital Product Passport (DPP) traceability, AI-assisted visual recycling observation, deterministic mass-balance verification, cryptographic evidence integrity commitments, and blockchain lifecycle state tracking.

To prevent architectural drift, conflicting interfaces, and divergent schema definitions across autonomous engineering agents working in parallel across subsequent milestones (M2 through M7), a single canonical source of truth must be established and strictly frozen at the completion of Phase 1.

---

## 2. Decision

We establish the canonical source of truth under `shared/` and freeze all core interfaces across five critical architectural pillars:

### Pillar 1: Canonical Domain Schemas (`shared/schemas/`)
All data exchange between backend services, AI models, storage pipelines, and client applications must strictly validate against formal Pydantic v2 schemas:
- `provenance.py`: Strict `ProvenanceCategory` enum with exactly five allowed categories:
  - `MEASURED`: Certified physical scale, weighbridge, or meter reading.
  - `OBSERVED`: Manual visual operator inspection log.
  - `AI_ESTIMATED`: Probabilistic computer vision inference output.
  - `REFERENCE_ASSUMED`: OEM Bill of Materials (BoM) baseline or regulatory benchmark prior.
  - `SIMULATED`: Synthetic test fixture or replayed test artifact.
  *Rule*: Never present simulated, assumed, or AI-estimated values as physical measurements.
- `material.py`: `MaterialComponent` and `MaterialComposition`. Enforces that the sum of material percentages equals 100.0% within +/- 0.5% tolerance.
- `dpp.py`: `DigitalProductPassport` with immutable identifiers, product metadata, gross mass, BoM, and lifecycle state.
- `recycling_event.py`: `RecyclingEvent` with globally unique UUID `event_id` (enforcing anti-replay), intake gross mass, claimed recovered materials, and evidence file references.
- `evidence_bundle.py`: `EvidenceBundle` containing raw evidence file SHA-256 hashes, AI observation telemetry, deterministic mass-balance results, canonical manifest SHA-256, and EVM keccak256 commitment.
- `por_certificate.py`: `ProofOfRecyclingCertificate` linking passport, event, certified recovered quantities, blockchain transaction reference, and cryptographic commitment.

### Pillar 2: Strict Lifecycle State Machine (`shared/domain/lifecycle.py`)
The product lifecycle is governed by a 7-state finite state machine:
$$\text{MANUFACTURED} \rightarrow \text{IN\_USE} \rightarrow \text{RETURNED} \rightarrow \text{RECYCLING\_PENDING} \rightarrow \text{RECYCLING\_VERIFIED} \rightarrow \text{MATERIALS\_RECOVERED}$$
with `FLAGGED` as a dedicated quarantine/investigation state.

**State Machine Rules**:
1. **Linear Transitions**: Direct skips (e.g. `MANUFACTURED` $\rightarrow$ `RECYCLING_VERIFIED`) are strictly forbidden.
2. **Anti-Replay / Self-Loop Prevention**: Self-transitions (e.g. `RECYCLING_VERIFIED` $\rightarrow$ `RECYCLING_VERIFIED`) are rejected to prevent replayed events or double certificate issuance.
3. **Role Authorization**: Each transition requires an authorized role (`MANUFACTURER`, `LOGISTICS`, `COLLECTION_AGENT`, `RECYCLER`, `VERIFIER_SERVICE`, `AUDITOR`, `SYSTEM`).
4. **Quarantine Isolation (`FLAGGED`)**: Any recycling event with an `IMPOSSIBLE` mass-balance result, evidence hash mismatch, or severe anomaly transitions immediately to `FLAGGED`. A flagged product can **never** transition to `RECYCLING_VERIFIED` without explicit resolution by an authorized `AUDITOR` accompanied by documented resolution notes. Recyclers and operators are strictly prohibited from resolving flags.

### Pillar 3: AI Trust Boundary & Deterministic Mass-Balance (`shared/domain/mass_balance.py`)
1. **AI Trust Boundary**: AI is strictly an observation and estimation layer (detecting item classes, estimating unit counts, classifying damage, and providing confidence priors). AI is **never** proof of recycling and must **never** make verification decisions.
2. **Deterministic Mathematics**: Conservation of mass and recovery calculations use pure deterministic closed-form equations:
   - Total mass conservation: $\sum M_{claim, i} \le M_{in} \cdot (1 + \tau_{scale})$.
   - Expected recovered mass: $M_{exp, i} = M_{in} \cdot w_i \cdot (1 - L_i)$.
   - Bounded envelopes: Lower bound $M_{lower}$, nominal upper bound $M_{upper}$, borderline upper bound $M_{borderline}$, and stoichiometric ceiling $M_{abs\_max} = M_{in} \cdot w_i \cdot (1 + \tau_{scale})$.
3. **Three-Tier Outcome**:
   - `VALID` $\rightarrow$ `VERIFIED` (triggers on-chain anchoring and certificate issuance).
   - `BORDERLINE` $\rightarrow$ `REVIEW` (retains state in `RECYCLING_PENDING`, flags for supervisor assay review).
   - `IMPOSSIBLE` $\rightarrow$ `FLAGGED` (quarantines batch; blocks certificate issuance).
4. **Mathematical Transparency**: Every evaluation generates an auditable structured explanation explaining why the claim passed, is borderline, or failed.

### Pillar 4: Cryptographic Evidence Pipeline (`shared/domain/evidence_hasher.py`)
Evidence integrity follows a 5-step deterministic commitment pipeline:
$$\text{Evidence Files} \rightarrow \text{Individual SHA-256 Hashes} \rightarrow \text{Canonical Evidence Manifest} \rightarrow \text{Canonical Manifest SHA-256} \rightarrow \text{EVM keccak256 Commitment}$$
- **RFC 8785 Compliance**: Serialization uses strict JSON Canonicalization Scheme (JCS) sorting keys lexicographically with compact separators `(',', ':')`.
- **Commitment Calculation**: Manifest produces a SHA-256 digest for off-chain verification and an EVM-compatible `keccak256` commitment for on-chain anchoring.

### Pillar 5: Solidity Smart-Contract Interfaces (`shared/contracts/`, `contracts/contracts/`)
Smart contracts target EVM Solidity `^0.8.20`:
- `IRETraceRegistry.sol`: Complete interface defining passport registration, evidence anchoring, lifecycle updates, flag management, and certificate issuance.
- `IRETraceLifecycle.sol`: Controller interface for validating role-authorized transitions.

---

## 3. Controlled Interface Freeze Rules

Following Phase 1 Gate completion, all shared schemas, domain models, and interfaces are **FROZEN**.

### Rules for Modification:
If an engineering agent discovers a genuine architectural flaw or required schema extension in subsequent milestones:
1. **No Independent Redefinition**: Agents must **NEVER** independently redefine or alter shared interfaces, schemas, or smart contracts without an approved ADR.
2. **Mandatory ADR Procedure**: An ADR must be authored under `docs/adr/ADR-xxx-<description>.md` containing:
   - Reason for change (demonstrated flaw or gap).
   - Affected components (`shared/`, `backend/`, `contracts/`, `ml/`, `frontend/`, `tests/`).
   - Compatibility impact (breaking vs non-breaking changes).
   - Migration/update requirements.
   - Regression tests verifying existing functionality is preserved.
3. **Verification**: The schema validation suite (`scripts/validate_schemas.py`) and test suites must pass cleanly before any ADR is marked ACCEPTED.

---

## 4. Consequences and Verification

- **Positive**: Guarantees seamless cross-service integration in Phase 3; eliminates schema mismatch errors between FastAPI, AI service, and Solidity contracts.
- **Positive**: Guarantees automated test determinism in Phase 2 and Phase 4 adversarial testing without flaky or shifting API contracts.
- **Verification**: Verified via `scripts/validate_schemas.py` and `shared/fixtures/reference_materials.py`.
