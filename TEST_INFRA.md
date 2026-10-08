# TEST_INFRA.md — RE:TRACE E2E Test Infrastructure & Verification Architecture

## 1. Test Philosophy & Design Methodology

RE:TRACE employs a **requirement-driven, opaque-box testing methodology** rooted in formal software engineering verification standards (ISO/IEC/IEEE 29119). Tests interact exclusively through canonical interfaces, formal domain contracts, and observable outputs (cryptographic commitments, state transitions, HTTP responses, mathematical outcomes), deliberately avoiding coupling to ephemeral implementation details.

### 1.1 Core Testing Principles
1. **Opaque-Box Verification**: Test cases specify inputs and assert against contractually mandated outputs derived strictly from `ORIGINAL_REQUEST.md`, `PROJECT.md`, and regulatory specifications (EU Battery Regulation 2023/1542, RFC 8785).
2. **Deterministic Reproducibility (Dual-Mode Execution)**: No automated test requires internet access, external API keys (Gemini), or live blockchain networks. Tests utilize deterministic fixtures and a local in-memory EVM ledger simulation to achieve 100% deterministic, offline execution.
3. **Progressive Testability & Graceful Independence**: Tests are architecturally decoupled and self-contained. Each test suite provides its own baseline fixtures and can validate either the canonical domain modules (once provided) or verify contract invariants independently.
4. **Adversarial Resilience**: Following Section R5 of the specification, the test suite actively attacks the platform using 10 formal adversarial vectors (Cases A–J) including evidence tampering, double-spend/replay attacks, stoichiometric mass violations, and role spoofing.
5. **Thermodynamic & Mathematical Rigor**: Tests verify that conservation of mass and stoichiometric ceilings are mathematically unbreachable, preventing greenwashing and fraudulent claims.

### 1.2 Formal Test Design Techniques
- **Category-Partition Method**: The input domains (Provenance categories, Lifecycle states, Material fractions, MIME types, Replay event IDs, Actor roles) are partitioned into exhaustive disjoint equivalence classes.
- **Boundary Value Analysis (BVA)**: Precision testing concentrated at mathematical and physical boundaries:
  - Nominal BAT yield limits ($\eta_{min}, \eta_{max}$)
  - Tolerance boundaries ($\tau_i = \pm 3\%$, $\tau_{scale} = \pm 0.5\%$)
  - Absolute thermodynamic ceiling ($M_{absolute\_max} = M_{in} \cdot w_{max}^{ref} \cdot (1 + \tau_{scale})$)
  - Bill of Materials mass percentage summation ($100.0\% \pm 0.5\%$)
  - Evidence file boundaries (0-byte rejection, 25MB upload limits)
- **Pairwise (Combinatorial) Testing**: Systematic orthogonal sampling of multi-variable interactions (e.g. Actor Role $\times$ Current State $\times$ Target State; Evidence Tampering $\times$ Verification Decision $\times$ Certificate Issuance).
- **Workload & Anti-Replay Stress Testing**: Rapid replay of identical `event_id` and `certificate_id` tokens to ensure atomic idempotency and rejection.

---

## 2. Test Architecture & Directory Structure

```
tests/
├── __init__.py
├── conftest.py                   # Pytest fixtures, EU battery & smartphone reference datasets
├── test_mass_balance.py          # Tier 1: Deterministic math, BAT recovery envelopes, BVA bounds
├── test_evidence_commitment.py   # Tier 1: RFC 8785 JCS, SHA-256, keccak256 commitment pipeline
├── test_state_machine.py         # Tier 1: Lifecycle state matrix, guard conditions, role authorization
├── test_adversarial.py           # Tier 3: Mandatory adversarial test suite (Cases A through J)
├── test_vertical_slice.py        # Tier 4: 12-stage programmatic offline E2E integration test
└── run_all_tests.py              # Pure standard-library test runner for zero-dependency execution
```

---

## 3. Feature Inventory & 4-Tier Test Mapping (27 Features)

Every feature defined in `PROJECT.md` is mapped to an authoritative verification tier, test suite, and expected output derivation source:

| Feature # | Feature Name | Milestone | Tier | Primary Test Suite | Specific Test Functions / Methods | Authoritative Derivation Source |
|---|---|---|---|---|---|---|
| **F01** | Canonical Domain Schemas | M1 | Tier 2 | `tests/test_vertical_slice.py` | `test_stage_01_passport_registration`, `test_stage_02_passport_validation` | `ORIGINAL_REQUEST.md:40`, `PROJECT.md:50` |
| **F02** | Provenance Category Model | M1 | Tier 1 | `tests/test_vertical_slice.py` | `test_stage_04_provenance_tagging` | `ORIGINAL_REQUEST.md:59-65` (5 categories) |
| **F03** | Material Composition & BoM Schema | M1 | Tier 1 | `tests/test_mass_balance.py` | `test_bom_percentage_validation`, `test_invalid_bom_sum_rejection` | `ORIGINAL_REQUEST.md:40, 73-77` |
| **F04** | Lifecycle State Machine Spec | M1 | Tier 1 | `tests/test_state_machine.py` | `test_valid_linear_transitions`, `test_illegal_transition_hops` | `ORIGINAL_REQUEST.md:43-45` (7 states) |
| **F05** | OpenAPI 3.1 REST API Specification | M1 | Tier 2 | `tests/test_vertical_slice.py` | `test_api_contract_conformance` | `ORIGINAL_REQUEST.md:41`, `PROJECT.md:54` |
| **F06** | Solidity Smart-Contract Interfaces | M1 | Tier 1 | `tests/test_state_machine.py` | `test_contract_interface_state_alignment` | `IRETraceRegistry.sol` |
| **F07** | ADR Governance & Freeze Rule | M1 | Tier 2 | `tests/test_state_machine.py` | `test_flag_resolution_requires_auditor_adr` | `ORIGINAL_REQUEST.md:46-52` |
| **F08** | Schema Validation Script | M1 | Tier 2 | `tests/test_vertical_slice.py` | `test_stage_02_passport_validation` | `scripts/validate_schemas.py` |
| **F09** | Offline Environment Bootstrapper | M1 | Tier 2 | `tests/run_all_tests.py` | `test_offline_environment_readiness` | `PROJECT.md:58` |
| **F10** | Circular Economy Datasets | M1 | Tier 1 | `tests/test_mass_balance.py` | `test_nmc622_baseline_parameters`, `test_lco_baseline_parameters` | EU Battery Reg 2023/1542 Annex XII |
| **F11** | Deterministic Mass-Balance Engine | M2 | Tier 1 | `tests/test_mass_balance.py` | `test_case_a_legitimate_nmc622_recovery`, `test_case_b_borderline_claim`, `test_case_c_impossible_claim`, `test_case_d_negative_claim` | `ORIGINAL_REQUEST.md:71-84`, BAT yield envelopes |
| **F12** | Canonical Evidence Commitment Pipeline | M2 | Tier 1 | `tests/test_evidence_commitment.py` | `test_individual_file_sha256`, `test_rfc8785_canonical_serialization`, `test_bundle_keccak256_commitment` | `ORIGINAL_REQUEST.md:55-58`, RFC 8785 |
| **F13** | Local EVM Ledger & Anchor Client | M2 | Tier 2 | `tests/test_vertical_slice.py` | `test_stage_08_blockchain_anchor` | `ORIGINAL_REQUEST.md:98` (`LOCAL TESTNET`) |
| **F14** | Proof-of-Recycling Certificate Engine | M2 | Tier 2 | `tests/test_vertical_slice.py` | `test_stage_10_por_certificate_generation`, `test_stage_11_independent_verification` | `ORIGINAL_REQUEST.md:99, 140` |
| **F15** | Thin Vertical Slice Test Runner | M2 | Tier 4 | `tests/test_vertical_slice.py` | `test_complete_12_stage_vertical_slice` | `ORIGINAL_REQUEST.md:87-94, 130-142` |
| **F16** | FastAPI Core Backend Services | M3 | Tier 2 | `tests/test_vertical_slice.py` | `test_backend_pipeline_execution` | `ORIGINAL_REQUEST.md:91` |
| **F17** | Dual-Mode AI Observation Service | M3 | Tier 2 | `tests/test_vertical_slice.py` | `test_stage_04_ai_fixture_observation`, `test_ai_trust_boundary_non_verification` | `ORIGINAL_REQUEST.md:68-70, 100` |
| **F18** | Local Storage Service & File Hasher | M3 | Tier 2 | `tests/test_evidence_commitment.py` | `test_streaming_file_upload_hash`, `test_empty_file_rejection` | `ORIGINAL_REQUEST.md:112` |
| **F19** | Replay & Duplicate Event Guard | M3 | Tier 3 | `tests/test_adversarial.py` | `test_case_e_duplicate_recycling_event` | `ORIGINAL_REQUEST.md:97, 149` |
| **F20** | Duplicate Certificate Prevention | M3 | Tier 3 | `tests/test_adversarial.py` | `test_case_f_duplicate_certificate_issuance` | `ORIGINAL_REQUEST.md:97, 150` |
| **F21** | Adversarial Test Suite Runner | M4 | Tier 3 | `tests/test_adversarial.py` | `test_suite_all_adversarial_cases` | `ORIGINAL_REQUEST.md:144-155` |
| **F22** | FLAGGED State & Quarantine Protocol | M4 | Tier 1 | `tests/test_state_machine.py` | `test_flagged_state_quarantine_isolation`, `test_unauthorized_unflagging_blocked` | `ORIGINAL_REQUEST.md:44-45` |
| **F23** | Post-Anchoring Integrity Verifier | M4 | Tier 3 | `tests/test_adversarial.py` | `test_case_d_evidence_tampering` | `ORIGINAL_REQUEST.md:148, 159` |
| **F24** | Security Hardening & Upload Sanitizer | M5 | Tier 3 | `tests/test_adversarial.py` | `test_case_h_malformed_evidence_and_mime` | `ORIGINAL_REQUEST.md:111-117` |
| **F25** | UI Dashboard & Demonstrable Scenarios | M6 | Tier 4 | `tests/test_vertical_slice.py` | `test_ui_scenario_data_flow_readiness` | `ORIGINAL_REQUEST.md:156-160` |
| **F26** | Truthfulness & Blockchain Indicator | M6 | Tier 3 | `tests/test_adversarial.py` | `test_case_j_blockchain_unavailable_rpc_disconnect` | `ORIGINAL_REQUEST.md:98, 154` |
| **F27** | Final IEEE-Grade Hackathon Readiness | M7 | Tier 4 | `tests/test_vertical_slice.py` | `test_complete_audit_trail_consistency` | `ORIGINAL_REQUEST.md:163-178` |

---

## 4. Test Tier Hierarchy & Coverage Thresholds

| Tier | Category | Description | Coverage Target | Assertion Standard |
|---|---|---|---|---|
| **Tier 1** | Mathematical & Core Logic Unit Tests | Mass-balance physics, RFC 8785 canonical hashing, state machine transition guards | 100% path coverage | Exact numerical & cryptographic equality |
| **Tier 2** | Contract & Domain Integration Tests | Pydantic schema validation, evidence bundling, certificate generation, local EVM ledger client | 100% schema coverage | Model validation, contract event emissions |
| **Tier 3** | Mandatory Adversarial Suite | Cases A through J (replay attacks, tampering, fraud, role spoofing, RPC failure) | 100% scenario coverage (10/10) | Explicit rejection codes (`409`, `403`, `422`, `FLAGGED`) |
| **Tier 4** | End-to-End Vertical Slice | 12-stage programmatic lifecycle execution offline | 100% pipeline stages (12/12) | Unbroken chain of custody from passport to certificate |

---

## 5. Test Runner Invocation

### 5.1 Primary Test Runner (Pytest)
```bash
# Run all test suites with verbose output
pytest -v tests/

# Run specific test suites
pytest -v tests/test_vertical_slice.py
pytest -v tests/test_adversarial.py
pytest -v tests/test_mass_balance.py
pytest -v tests/test_evidence_commitment.py
pytest -v tests/test_state_machine.py

# Run by Tier marker
pytest -v -m tier1
pytest -v -m tier3
pytest -v -m tier4
```

### 5.2 Zero-Dependency Universal Runner (Python Standard Library)
For environments where pytest is not yet installed in the active virtual environment:
```bash
python3 tests/run_all_tests.py
```
This runner leverages Python's built-in `unittest` framework to execute the entire test suite, ensuring 100% offline verification under any runtime environment.
