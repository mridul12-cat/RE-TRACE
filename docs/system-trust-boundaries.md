# RE:TRACE System Trust Boundaries & Verification Limitations

- **Status**: CANONICAL ARCHITECTURE SPECIFICATION
- **Mandate**: Section R6 System Trust & Limitations Boundaries (ORIGINAL_REQUEST.md)
- **Scope**: Entire RE:TRACE Verification Pipeline

---

## 1. Executive Purpose

To maintain scientific rigor and technical defensibility, RE:TRACE explicitly defines what the platform cryptographically and mathematically proves versus what it does **not** prove. Exaggerated claims of "immutable truth" or "AI proof of physical reality" undermine credibility with regulatory bodies, certification agencies, and hackathon judges.

---

## 2. Core Trust Boundaries Matrix

| Subsystem | What RE:TRACE Cryptographically Proves | What RE:TRACE DOES NOT Prove (Limitations) |
|---|---|---|
| **Digital Product Passport (DPP)** | The OEM Bill of Materials (BoM), initial mass, and serial identity were committed by an authorized manufacturer entity at a specific timestamp. | Does not physically prevent an operator from swapping identical battery pack casings prior to intake. |
| **Physical Evidence & Hasher** | The digital file (image, weighbridge PDF, assay report) has not been mutated by even 1 single bit since ingestion (SHA-256 integrity). | Does not prove that the physical camera photograph represents the exact truck present at that weighbridge. |
| **AI Computer Vision Observation** | A reproducible computer vision model observed visual features, estimated item counts, and flagged visible physical casing anomalies with a declared confidence score. | **AI is NEVER proof of recycling.** Visual appearance cannot detect internal chemical dilution, inert slag substitution, or counterfeit electrolyte additives. |
| **Deterministic Mass Balance** | The claimed recovered masses strictly satisfy the First Law of Thermodynamics (gross conservation of mass) and fall within the Best Available Techniques (BAT) yield envelope of the product BoM. | Does not replace statutory laboratory XRF spectrometry or physical metallurgical assays. |
| **Blockchain Circular Ledger** | The state transition, event hash, and evidence commitment were anchored to an EVM block header and cannot be repudiated or replayed off-chain. | An on-chain transaction proves data existed at block time $t$; it does NOT prove that secondary physical materials physically arrived in a smelter furnace. |
| **Proof-of-Recycling (PoR)** | Verifiable, tamper-evident certificate mathematically tied to an unflagged product passport, unique recycling event, and on-chain commitment. | Does not supersede national environmental agency inspection permits or statutory hazardous waste transfer notes. |

---

## 3. Data Provenance Hierarchy (ADR-001 Pillar 1)

Every metric in the RE:TRACE platform is strictly tagged with one of five canonical provenance categories. System interfaces and client dashboards must never present estimated or simulated values as certified physical measurements:

1. **`MEASURED`** (Certified Physical Instrument):
   - Weighbridge gross mass scale reading with certified calibration certificate (e.g. $\pm 0.5\%$).
   - Certified laboratory wet-chemistry or ICP-OES assay.
2. **`OBSERVED`** (Operator Visual Inspection):
   - Human operator pallet intake checklist and visual seal verification.
3. **`AI_ESTIMATED`** (Probabilistic Computer Vision):
   - Machine learning bounding box detections, unit counts, and visual damage classification.
   - Always probabilistic ($p < 1.0$); strictly restricted to feature estimation.
4. **`REFERENCE_ASSUMED`** (OEM BoM Prior / Regulatory Baseline):
   - EU Battery Regulation 2023/1542 benchmark fractions (e.g., NMC 622: 18% Ni, 6% Co, 6% Mn, 2.8% Li).
5. **`SIMULATED`** (Synthetic Test Artifact):
   - Offline replay test fixtures and simulated EVM transactions.

---

## 4. Blockchain Truthfulness Standard (Section R5)

1. **Local Testnet Transparency**: RE:TRACE development and hackathon demonstration environments operate on local EVM instances (`chain_id: 31337`). The platform explicitly labels these as `LOCAL TESTNET` / `LOCAL DEVELOPMENT BLOCKCHAIN`.
2. **Zero Fabrication Policy**: The system never fabricates fake public Ethereum mainnet transaction hashes, block numbers, gas fees, or explorer links. If the local node is unreachable, the system displays an explicit `UNCONFIRMED / BLOCKCHAIN_OFFLINE` error rather than pretending a transaction succeeded.

---

## 5. Conclusion & Regulatory Defensibility

By decoupling probabilistic AI estimation from deterministic mathematical mass-balance verification and anchoring cryptographic evidence hashes to an EVM state machine, RE:TRACE provides an auditable, adversarial-resistant digital paper trail while acknowledging the boundary between digital cryptography and physical reality.
