# RE:TRACE — Demonstration Walkthrough Guide for Evaluators & Judges

- **Track**: Sustainable Supply Chains & Circular Economy
- **Platform**: RE:TRACE — Verifiable Digital Product Passport & Mass-Balance Infrastructure
- **Execution Mode**: 100% Deterministic & Offline-Ready (with optional Live Gemini Multimodal Vision)

---

## 1. Quickstart (Under 30 Seconds)

### Step 1: Launch Backend API & Interactive Dashboard
From the repository root directory, run:
```bash
./scripts/start_demo.sh
```
*(Alternatively: `.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`)*

### Step 2: Open the Web Dashboard
Open your web browser and navigate to:
```
http://localhost:8000/dashboard
```
*(Also accessible at `http://localhost:8000/` and API documentation at `http://localhost:8000/docs`)*

---

## 2. Interactive Demonstrations (1-Click Execution)

The web dashboard header provides three prominent 1-click execution buttons at the top of the interface:

```
[ Run Scenario A (Legitimate) ]   [ Run Scenario B (Fraud Claim) ]   [ Run Scenario C (Evidence Tampering) ]
```

---

### Scenario A: Legitimate Circular Recycling Pipeline
**Objective**: Demonstrate end-to-end trace from physical weighbridge intake through dual-mode AI observation, deterministic physics validation, blockchain anchoring, and PoR certificate issuance.

1. **Action**: Click the green **"Run Scenario A (Legitimate)"** button.
2. **Observed Execution Flow**:
   - **Stage 1**: Digital Product Passport `DPP-EV-NMC622-2026-M04` registered on local EVM ledger (`LOCAL TESTNET`, Chain ID 31337).
   - **Stage 2**: Lifecycle state advances linearly: `MANUFACTURED` $\rightarrow$ `IN_USE` $\rightarrow$ `RETURNED` $\rightarrow$ `RECYCLING_PENDING`.
   - **Stage 3**: Physical evidence uploaded (`weighbridge_intake_nmc622.jpg`, SHA-256 computed on stream). Tagged `MEASURED`.
   - **Stage 4**: AI Computer Vision observation extracts feature priors: 40 battery modules detected, confidence 96.5%, zero physical casing breach. Tagged `AI_ESTIMATED`.
   - **Stage 5**: Deterministic mass-balance engine evaluates claimed metals (165.6 kg Ni, 55.8 kg Co, 21.0 kg Li). All claims fit within nominal BAT recovery envelope. Verdict: **`VALID`**.
   - **Stage 6**: RFC 8785 canonical manifest generated; `keccak256` commitment anchored to EVM blockchain. State transitions to **`RECYCLING_VERIFIED`**.
   - **Stage 7**: Immutable Proof-of-Recycling certificate (`POR-2026-XXXX`) issued.
   - **Stage 8**: Independent cryptographic verification confirms certificate hash and commitment match on-chain ledger records.
3. **Verify On-Chain**:
   - Click the **"Verify On-Chain"** button on the bottom right panel to trigger real-time cryptographic audit. A green confirmation badge confirms: `AUTHENTICATED on LOCAL TESTNET`.

---

### Scenario B: Fraudulent Material Claim Blocked by Stoichiometry
**Objective**: Demonstrate that the deterministic mass-balance engine catches fraudulent yield inflation that violates thermodynamic physical limits, instantly quarantining the batch into `FLAGGED`.

1. **Action**: Click the red **"Run Scenario B (Fraud Claim)"** button.
2. **Observed Execution Flow**:
   - **The Fraud Attempt**: Recycler claims 95.00 kg of recovered Cobalt from a 1,000 kg intake batch of NMC 622 modules.
   - **The Physics Check**:
     - Product OEM BoM nominal fraction: 6.00% ($60.00\text{ kg}$).
     - Maximum stoichiometric ceiling including scale uncertainty: $60.30\text{ kg}$.
     - Claimed excess: $+34.70\text{ kg}$ ($+57.5\%$ above absolute thermodynamic ceiling).
   - **Decision**: Engine flags claim as **`IMPOSSIBLE`**.
   - **Quarantine Action**: Product passport transitions immediately to **`FLAGGED`**.
   - **Anti-Fraud Guard**: Proof-of-Recycling certificate issuance is strictly **BLOCKED**.
   - **Auditor Rule**: A recycler cannot unflag this product (HTTP 403). Only an authorized `AUDITOR` with written justification can resolve the quarantine.

---

### Scenario C: Post-Anchoring Physical Evidence Tampering Detection
**Objective**: Prove that mutating a single byte of an evidence file after on-chain anchoring is caught by the cryptographic manifest re-hasher.

1. **Action**: Click the amber **"Run Scenario C (Evidence Tampering)"** button.
2. **Observed Execution Flow**:
   - Original evidence bundle is verified and anchored on-chain with EVM commitment hash.
   - System simulates an adversary mutating 1 single byte in the raw weighbridge file on disk.
   - Post-anchoring integrity verifier re-reads disk bytes and re-computes SHA-256 and RFC 8785 canonical manifest.
   - SHA-256 digest mismatch is detected immediately.
   - System flags: **`EVIDENCE_INTEGRITY_FAILURE`**.
   - Quarantines product and alerts auditor to cryptographic tampering attempt.

---

## 3. Automated Test Suite Verification

To verify that all tests across canonical tiers and challenger suites pass cleanly:

```bash
# Run universal zero-dependency runner (Standard Library, 108 tests across canonical tiers)
python3 tests/run_all_tests.py

# Run comprehensive pytest battery (146 tests including challenger stress suites)
./scripts/run_tests.sh
```

**Expected Result**:
```
======================== 145 passed, 1 skipped in ~1.8s ========================
>>> ALL TIERS PASSED VERIFICATION (STATUS: GREEN) <<<
```
*(Note: 1 test skipped in offline execution is `test_18_optional_environment_gated_live_gemini`, which runs when live internet access to the Google Gemini API is available).*

---

## 4. Key Architectural Differentiators for Judges

1. **AI Trust Segregation**: AI is strictly an observation and estimation layer (`AI_ESTIMATED`). Verification decisions are 100% deterministic, closed-form physics equations.
2. **Standardized Data Provenance**: Every number explicitly displays its source (`MEASURED`, `OBSERVED`, `AI_ESTIMATED`, `REFERENCE_ASSUMED`, `SIMULATED`).
3. **Cryptographic Anti-Replay**: Duplicate event IDs, duplicate certificate requests, and state hops are rejected at both API and smart-contract levels.
4. **Blockchain Truthfulness**: Explicitly labelled `LOCAL TESTNET` (Chain 31337). No fabricated mainnet transactions or fake explorer links.
