"""
conftest.py — Global Test Fixtures and Verification Infrastructure for RE:TRACE
Provides deterministic datasets, cryptographic tools, reference engines,
and local EVM ledger mocks for opaque-box testing.
"""

import sys
import os
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)


# ============================================================================
# 1. ENUMS & DATA MODELS
# ============================================================================

class ProvenanceCategory(str, Enum):
    MEASURED = "MEASURED"                    # Verified physical scale / meter reading
    OBSERVED = "OBSERVED"                    # Human / operator visual observation
    AI_ESTIMATED = "AI_ESTIMATED"            # Computer vision inference output
    REFERENCE_ASSUMED = "REFERENCE_ASSUMED"  # OEM Bill of Materials or baseline reference
    SIMULATED = "SIMULATED"                  # Synthetic test fixture or mock data


class LifecycleState(str, Enum):
    MANUFACTURED = "MANUFACTURED"
    IN_USE = "IN_USE"
    RETURNED = "RETURNED"
    RECYCLING_PENDING = "RECYCLING_PENDING"
    RECYCLING_VERIFIED = "RECYCLING_VERIFIED"
    MATERIALS_RECOVERED = "MATERIALS_RECOVERED"
    FLAGGED = "FLAGGED"


class ActorRole(str, Enum):
    MANUFACTURER = "MANUFACTURER"
    SUPPLY_CHAIN_OPERATOR = "SUPPLY_CHAIN_OPERATOR"
    COLLECTION_AGENT = "COLLECTION_AGENT"
    RECYCLER = "RECYCLER"
    FACILITY_MANAGER = "FACILITY_MANAGER"
    VERIFIER_SERVICE = "VERIFIER_SERVICE"
    SYSTEM = "SYSTEM"
    AUDITOR = "AUDITOR"
    PUBLIC = "PUBLIC"


class VerificationDecision(str, Enum):
    VALID = "VALID"
    BORDERLINE = "BORDERLINE"
    IMPOSSIBLE = "IMPOSSIBLE"


# ============================================================================
# 2. CRYPTOGRAPHIC REFERENCE IMPLEMENTATION (Pure Python, Zero Dependency)
# ============================================================================

def sha256_hex(data: bytes) -> str:
    """Computes SHA-256 hexadecimal hash string."""
    return hashlib.sha256(data).hexdigest()


def keccak256_bytes(data: bytes) -> bytes:
    """Computes Ethereum Keccak-256 hash in pure Python matching EVM specification."""
    RC = [
        0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
        0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
        0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
        0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
        0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
        0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008
    ]
    ROTC = [
        [0, 36, 3, 41, 18],
        [1, 44, 10, 45, 2],
        [62, 6, 43, 15, 61],
        [28, 55, 25, 21, 56],
        [27, 20, 39, 8, 14]
    ]
    rate = 136  # bytes (1088 bits)
    pad_len = rate - (len(data) % rate)
    if pad_len == 1:
        padded = data + b'\x81'
    else:
        padded = data + b'\x01' + b'\x00' * (pad_len - 2) + b'\x80'
    
    state = [[0] * 5 for _ in range(5)]
    
    for block_idx in range(0, len(padded), rate):
        block = padded[block_idx:block_idx + rate]
        for i in range(len(block) // 8):
            x, y = i % 5, i // 5
            val = int.from_bytes(block[i * 8:(i + 1) * 8], 'little')
            state[x][y] ^= val
        for round_idx in range(24):
            # Theta
            C = [state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4] for x in range(5)]
            D = [C[(x - 1) % 5] ^ (((C[(x + 1) % 5] << 1) | (C[(x + 1) % 5] >> 63)) & 0xFFFFFFFFFFFFFFFF) for x in range(5)]
            for x in range(5):
                for y in range(5):
                    state[x][y] ^= D[x]
            # Rho and Pi
            B = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    r = ROTC[x][y]
                    B[y][(2 * x + 3 * y) % 5] = (((state[x][y] << r) | (state[x][y] >> (64 - r))) & 0xFFFFFFFFFFFFFFFF) if r else state[x][y]
            # Chi
            for x in range(5):
                for y in range(5):
                    state[x][y] = B[x][y] ^ ((~B[(x + 1) % 5][y]) & B[(x + 2) % 5][y]) & 0xFFFFFFFFFFFFFFFF
            # Iota
            state[0][0] ^= RC[round_idx]
            
    out = b''
    for i in range(4):
        x, y = i % 5, i // 5
        out += state[x][y].to_bytes(8, 'little')
    return out


def keccak256_hex(data: bytes) -> str:
    """Returns keccak256 hex string with '0x' prefix."""
    return "0x" + keccak256_bytes(data).hex()


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Serializes a dictionary or list into deterministic RFC 8785 JSON canonical format:
    - Keys sorted lexicographically
    - Compact separators (',', ':')
    - UTF-8 encoding
    """
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


# ============================================================================
# 3. CIRCULAR ECONOMY REFERENCE DATASETS (EU Battery Reg 2023/1542)
# ============================================================================

EV_BATTERY_NMC622_DATASET = {
    "product_id": "DPP-EV-NMC622-2026-M04",
    "product_name": "24V Lithium-Ion EV Traction Battery Module (6S2P)",
    "category": "INDUSTRIAL_EV_BATTERY",
    "unit_gross_mass_kg": 25.0,
    "standard_batch_units": 40,
    "standard_intake_mass_kg": 1000.0,
    "scale_uncertainty_pct": 0.5,   # +/- 0.5%
    "components": {
        "NI": {
            "name": "Nickel",
            "nominal_fraction": 0.1800,
            "min_fraction": 0.1700,
            "max_fraction": 0.1900,
            "nominal_yield": 0.9200,
            "bat_yield_range": (0.8900, 0.9500),
            "process_tolerance_pct": 3.0,
            "is_critical": True
        },
        "CO": {
            "name": "Cobalt",
            "nominal_fraction": 0.0600,
            "min_fraction": 0.0550,
            "max_fraction": 0.0650,
            "nominal_yield": 0.9300,
            "bat_yield_range": (0.9000, 0.9500),
            "process_tolerance_pct": 3.0,
            "is_critical": True
        },
        "MN": {
            "name": "Manganese",
            "nominal_fraction": 0.0600,
            "min_fraction": 0.0550,
            "max_fraction": 0.0650,
            "nominal_yield": 0.8800,
            "bat_yield_range": (0.8500, 0.9200),
            "process_tolerance_pct": 3.0,
            "is_critical": False
        },
        "LI": {
            "name": "Lithium",
            "nominal_fraction": 0.0280,
            "min_fraction": 0.0250,
            "max_fraction": 0.0310,
            "nominal_yield": 0.7500,
            "bat_yield_range": (0.7000, 0.8000),
            "process_tolerance_pct": 3.0,
            "is_critical": True
        },
        "CU": {
            "name": "Copper",
            "nominal_fraction": 0.1120,
            "min_fraction": 0.1050,
            "max_fraction": 0.1180,
            "nominal_yield": 0.9400,
            "bat_yield_range": (0.9100, 0.9600),
            "process_tolerance_pct": 3.0,
            "is_critical": True
        },
        "AL": {
            "name": "Aluminum",
            "nominal_fraction": 0.1600,
            "min_fraction": 0.1500,
            "max_fraction": 0.1700,
            "nominal_yield": 0.8800,
            "bat_yield_range": (0.8400, 0.9200),
            "process_tolerance_pct": 3.0,
            "is_critical": False
        },
        "C_GRAPHITE": {
            "name": "Anode Graphite",
            "nominal_fraction": 0.1500,
            "min_fraction": 0.1400,
            "max_fraction": 0.1600,
            "nominal_yield": 0.8500,
            "bat_yield_range": (0.8000, 0.9000),
            "process_tolerance_pct": 3.0,
            "is_critical": False
        },
        "STEEL": {
            "name": "Casing Steel",
            "nominal_fraction": 0.1200,
            "min_fraction": 0.1100,
            "max_fraction": 0.1300,
            "nominal_yield": 0.9800,
            "bat_yield_range": (0.9600, 0.9900),
            "process_tolerance_pct": 3.0,
            "is_critical": False
        },
        "OTHER_LOSS": {
            "name": "Electrolyte/Separator/Slag Loss",
            "nominal_fraction": 0.1300,
            "min_fraction": 0.1100,
            "max_fraction": 0.1500,
            "nominal_yield": 0.0000,
            "bat_yield_range": (0.0000, 0.0000),
            "process_tolerance_pct": 0.0,
            "is_critical": False
        }
    }
}

SMARTPHONE_LCO_DATASET = {
    "product_id": "DPP-CONSUMER-LCO-2026-B10",
    "product_name": "3.85V 4500mAh Smartphone Li-ion Pouch Cell",
    "category": "CONSUMER_ELECTRONICS_BATTERY",
    "unit_gross_mass_kg": 0.045,
    "standard_batch_units": 10000,
    "standard_intake_mass_kg": 450.0,
    "scale_uncertainty_pct": 0.5,
    "components": {
        "CO": {
            "name": "Cobalt",
            "nominal_fraction": 0.2000,
            "min_fraction": 0.1900,
            "max_fraction": 0.2100,
            "nominal_yield": 0.9400,
            "bat_yield_range": (0.9000, 0.9600),
            "process_tolerance_pct": 3.0,
            "is_critical": True
        },
        "LI": {
            "name": "Lithium",
            "nominal_fraction": 0.0240,
            "min_fraction": 0.0220,
            "max_fraction": 0.0260,
            "nominal_yield": 0.7800,
            "bat_yield_range": (0.7200, 0.8200),
            "process_tolerance_pct": 3.0,
            "is_critical": True
        },
        "CU": {
            "name": "Copper",
            "nominal_fraction": 0.0950,
            "min_fraction": 0.0900,
            "max_fraction": 0.1000,
            "nominal_yield": 0.9500,
            "bat_yield_range": (0.9200, 0.9700),
            "process_tolerance_pct": 3.0,
            "is_critical": True
        },
        "AL": {
            "name": "Aluminum",
            "nominal_fraction": 0.0700,
            "min_fraction": 0.0650,
            "max_fraction": 0.0750,
            "nominal_yield": 0.9000,
            "bat_yield_range": (0.8500, 0.9300),
            "process_tolerance_pct": 3.0,
            "is_critical": False
        },
        "C_GRAPHITE": {
            "name": "Anode Graphite",
            "nominal_fraction": 0.1700,
            "min_fraction": 0.1600,
            "max_fraction": 0.1800,
            "nominal_yield": 0.8500,
            "bat_yield_range": (0.8000, 0.8900),
            "process_tolerance_pct": 3.0,
            "is_critical": False
        },
        "OTHER_LOSS": {
            "name": "Casing & Electrolyte Loss",
            "nominal_fraction": 0.4410,
            "min_fraction": 0.4000,
            "max_fraction": 0.4600,
            "nominal_yield": 0.0000,
            "bat_yield_range": (0.0000, 0.0000),
            "process_tolerance_pct": 0.0,
            "is_critical": False
        }
    }
}


# ============================================================================
# 4. REFERENCE DETERMINISTIC MASS-BALANCE ENGINE
# ============================================================================

@dataclass
class ComponentEvaluation:
    material_key: str
    material_name: str
    claimed_mass_kg: float
    nominal_expected_kg: float
    expected_range_kg: Tuple[float, float]
    tolerance_bounds_kg: Tuple[float, float]
    absolute_ceiling_kg: float
    decision: VerificationDecision
    discrepancy_kg: float
    explanation: str


@dataclass
class MassBalanceResult:
    intake_mass_kg: float
    total_claimed_recovered_kg: float
    decision: VerificationDecision
    component_evaluations: Dict[str, ComponentEvaluation]
    mathematical_explanation: str
    is_conservation_of_mass_valid: bool


class ReferenceMassBalanceEngine:
    """
    Closed-form physics-based mass-balance verification engine.
    Satisfies R3 of ORIGINAL_REQUEST.md.
    """

    @classmethod
    def evaluate(
        cls,
        intake_mass_kg: float,
        dataset: Dict[str, Any],
        claimed_materials: Dict[str, float]
    ) -> MassBalanceResult:
        if intake_mass_kg <= 0:
            return MassBalanceResult(
                intake_mass_kg=intake_mass_kg,
                total_claimed_recovered_kg=sum(claimed_materials.values()),
                decision=VerificationDecision.IMPOSSIBLE,
                component_evaluations={},
                mathematical_explanation="IMPOSSIBLE: Intake mass must be strictly positive.",
                is_conservation_of_mass_valid=False
            )

        scale_uncertainty = dataset.get("scale_uncertainty_pct", 0.5) / 100.0
        max_allowed_total = intake_mass_kg * (1.0 + scale_uncertainty)
        total_claimed = sum(claimed_materials.values())

        # Check total mass conservation
        if total_claimed > max_allowed_total:
            return MassBalanceResult(
                intake_mass_kg=intake_mass_kg,
                total_claimed_recovered_kg=total_claimed,
                decision=VerificationDecision.IMPOSSIBLE,
                component_evaluations={},
                mathematical_explanation=(
                    f"IMPOSSIBLE: Total claimed recovered mass ({total_claimed:.2f} kg) "
                    f"exceeds intake gross mass + scale tolerance ({max_allowed_total:.2f} kg). "
                    f"Violates conservation of mass (First Law of Thermodynamics)."
                ),
                is_conservation_of_mass_valid=False
            )

        components = dataset["components"]
        evaluations: Dict[str, ComponentEvaluation] = {}
        has_impossible = False
        has_borderline = False
        explanation_lines = []

        for mat_key, claimed_mass in claimed_materials.items():
            if mat_key not in components:
                expl = f"Material '{mat_key}' not present in product Bill of Materials."
                evaluations[mat_key] = ComponentEvaluation(
                    material_key=mat_key,
                    material_name=mat_key,
                    claimed_mass_kg=claimed_mass,
                    nominal_expected_kg=0.0,
                    expected_range_kg=(0.0, 0.0),
                    tolerance_bounds_kg=(0.0, 0.0),
                    absolute_ceiling_kg=0.0,
                    decision=VerificationDecision.IMPOSSIBLE,
                    discrepancy_kg=claimed_mass,
                    explanation=expl
                )
                explanation_lines.append(expl)
                has_impossible = True
                continue

            comp = components[mat_key]
            name = comp["name"]
            w_nom = comp["nominal_fraction"]
            w_min = comp["min_fraction"]
            w_max = comp["max_fraction"]
            eta_nom = comp["nominal_yield"]
            eta_min, eta_max = comp["bat_yield_range"]
            tau = comp.get("process_tolerance_pct", 3.0) / 100.0

            if claimed_mass < 0:
                evaluations[mat_key] = ComponentEvaluation(
                    material_key=mat_key,
                    material_name=name,
                    claimed_mass_kg=claimed_mass,
                    nominal_expected_kg=intake_mass_kg * w_nom * eta_nom,
                    expected_range_kg=(intake_mass_kg * w_min * eta_min, intake_mass_kg * w_max * eta_max),
                    tolerance_bounds_kg=(0.0, 0.0),
                    absolute_ceiling_kg=intake_mass_kg * w_max * (1.0 + scale_uncertainty),
                    decision=VerificationDecision.IMPOSSIBLE,
                    discrepancy_kg=claimed_mass,
                    explanation=f"Negative claimed mass for {name} ({claimed_mass} kg) is physically invalid."
                )
                has_impossible = True
                continue

            m_exp_nom = intake_mass_kg * w_nom * eta_nom
            m_exp_min = intake_mass_kg * w_min * eta_min
            m_exp_max = intake_mass_kg * w_max * eta_max

            m_lower = m_exp_min * (1.0 - tau)
            m_upper = m_exp_max * (1.0 + tau)
            m_abs_max = intake_mass_kg * w_max * (1.0 + scale_uncertainty)

            # Decision bounds
            if m_lower <= claimed_mass <= m_exp_max:
                decision = VerificationDecision.VALID
                expl = (
                    f"VALID: Claimed {claimed_mass:.2f} kg {name} is within nominal recovery envelope "
                    f"[{m_exp_min:.2f} kg - {m_exp_max:.2f} kg] (effective yield: {(claimed_mass/(intake_mass_kg*w_nom)*100.0 if w_nom>0 else 0):.1f}%)."
                )
            elif (m_exp_max < claimed_mass <= m_upper) or (m_lower * (1.0 - tau) <= claimed_mass < m_lower):
                decision = VerificationDecision.BORDERLINE
                has_borderline = True
                expl = (
                    f"BORDERLINE: Claimed {claimed_mass:.2f} kg {name} deviates from nominal range "
                    f"[{m_exp_min:.2f} kg - {m_exp_max:.2f} kg], but remains within process tolerance bound "
                    f"[{m_lower*(1.0-tau):.2f} kg - {m_upper:.2f} kg]. Requires supervisor audit."
                )
            else:
                decision = VerificationDecision.IMPOSSIBLE
                has_impossible = True
                expl = (
                    f"IMPOSSIBLE: Claimed {claimed_mass:.2f} kg {name} exceeds plausible limits "
                    f"(Upper tolerance limit: {m_upper:.2f} kg, Stoichiometric ceiling: {m_abs_max:.2f} kg). "
                    f"Claimed excess: +{(claimed_mass - m_upper):.2f} kg."
                )

            discrepancy = claimed_mass - m_exp_nom
            evaluations[mat_key] = ComponentEvaluation(
                material_key=mat_key,
                material_name=name,
                claimed_mass_kg=claimed_mass,
                nominal_expected_kg=m_exp_nom,
                expected_range_kg=(m_exp_min, m_exp_max),
                tolerance_bounds_kg=(m_lower, m_upper),
                absolute_ceiling_kg=m_abs_max,
                decision=decision,
                discrepancy_kg=discrepancy,
                explanation=expl
            )
            explanation_lines.append(expl)

        if has_impossible:
            agg_decision = VerificationDecision.IMPOSSIBLE
        elif has_borderline:
            agg_decision = VerificationDecision.BORDERLINE
        else:
            agg_decision = VerificationDecision.VALID

        return MassBalanceResult(
            intake_mass_kg=intake_mass_kg,
            total_claimed_recovered_kg=total_claimed,
            decision=agg_decision,
            component_evaluations=evaluations,
            mathematical_explanation="\n".join(explanation_lines),
            is_conservation_of_mass_valid=True
        )


# ============================================================================
# 5. REFERENCE LIFECYCLE STATE MACHINE
# ============================================================================

class ReferenceLifecycleStateMachine:
    """
    Enforces strict lifecycle transitions and role authorization.
    Satisfies R1:5 and R5 of ORIGINAL_REQUEST.md.
    """

    ALLOWED_TRANSITIONS: Dict[LifecycleState, List[Tuple[LifecycleState, List[ActorRole]]]] = {
        LifecycleState.MANUFACTURED: [
            (LifecycleState.IN_USE, [ActorRole.MANUFACTURER, ActorRole.SUPPLY_CHAIN_OPERATOR])
        ],
        LifecycleState.IN_USE: [
            (LifecycleState.RETURNED, [ActorRole.COLLECTION_AGENT, ActorRole.RECYCLER])
        ],
        LifecycleState.RETURNED: [
            (LifecycleState.RECYCLING_PENDING, [ActorRole.RECYCLER])
        ],
        LifecycleState.RECYCLING_PENDING: [
            (LifecycleState.RECYCLING_VERIFIED, [ActorRole.VERIFIER_SERVICE, ActorRole.SYSTEM]),
            (LifecycleState.FLAGGED, [ActorRole.VERIFIER_SERVICE, ActorRole.SYSTEM])
        ],
        LifecycleState.RECYCLING_VERIFIED: [
            (LifecycleState.MATERIALS_RECOVERED, [ActorRole.RECYCLER, ActorRole.FACILITY_MANAGER]),
            (LifecycleState.FLAGGED, [ActorRole.VERIFIER_SERVICE, ActorRole.AUDITOR, ActorRole.SYSTEM]),
        ],
        LifecycleState.FLAGGED: [
            (LifecycleState.RECYCLING_VERIFIED, [ActorRole.AUDITOR])  # Auditor only!
        ],
        LifecycleState.MATERIALS_RECOVERED: []  # Terminal state
    }

    @classmethod
    def validate_transition(
        cls,
        current_state: LifecycleState,
        target_state: LifecycleState,
        actor_role: ActorRole,
        has_auditor_proof: bool = False
    ) -> Tuple[bool, str]:
        if current_state == target_state:
            return False, f"Replay rejected: Product is already in state {current_state}."

        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, [])
        valid_target = None
        for (tgt, roles) in allowed:
            if tgt == target_state:
                valid_target = roles
                break

        if valid_target is None:
            return False, f"Illegal state transition: Cannot transition from {current_state} directly to {target_state}."

        if actor_role not in valid_target:
            return False, f"Unauthorized: Role {actor_role} is not permitted to transition from {current_state} to {target_state} (Required: {valid_target})."

        if current_state == LifecycleState.FLAGGED and target_state == LifecycleState.RECYCLING_VERIFIED:
            if not has_auditor_proof:
                return False, "Auditor resolution requires documented ADR/audit justification."

        return True, "Transition authorized."


# ============================================================================
# 6. LOCAL MOCK EVM BLOCKCHAIN LEDGER
# ============================================================================

@dataclass
class OnChainEvent:
    event_id: str
    passport_id: str
    evidence_commitment: str
    recycler_address: str
    timestamp: int
    tx_hash: str
    block_number: int


@dataclass
class OnChainCertificate:
    certificate_id: str
    event_id: str
    passport_id: str
    cert_hash: str
    evidence_commitment: str
    issuer_address: str
    timestamp: int
    tx_hash: str
    block_number: int


class LocalMockEVMLedger:
    """
    In-memory EVM ledger simulation honoring Section R5 Blockchain Truthfulness.
    Clearly labelled 'LOCAL TESTNET' / 'LOCAL DEVELOPMENT BLOCKCHAIN'.
    """

    def __init__(self, network_label: str = "LOCAL TESTNET", chain_id: int = 31337):
        self.network_label = network_label
        self.chain_id = chain_id
        self.current_block = 1000
        self.is_connected = True

        self.passports: Dict[str, Dict[str, Any]] = {}
        self.events: Dict[str, OnChainEvent] = {}
        self.certificates: Dict[str, OnChainCertificate] = {}
        self.lifecycle_states: Dict[str, LifecycleState] = {}
        self.flagged_products: Dict[str, str] = {}

    def simulate_rpc_disconnect(self):
        self.is_connected = False

    def simulate_rpc_reconnect(self):
        self.is_connected = True

    def _generate_tx_hash(self, action: str, identifier: str) -> str:
        self.current_block += 1
        raw = f"{action}:{identifier}:{self.current_block}:{self.chain_id}".encode()
        return "0x" + sha256_hex(raw)

    def register_passport(self, passport_id: str, bom_hash: str, manufacturer: str) -> str:
        if not self.is_connected:
            raise ConnectionError("RPC node offline (LOCAL TESTNET disconnected)")
        if passport_id in self.passports:
            raise ValueError(f"Passport {passport_id} already registered.")
        tx_hash = self._generate_tx_hash("REGISTER_PASSPORT", passport_id)
        self.passports[passport_id] = {
            "passport_id": passport_id,
            "bom_hash": bom_hash,
            "manufacturer": manufacturer,
            "registered_at": int(datetime.now(timezone.utc).timestamp()),
            "tx_hash": tx_hash,
            "block_number": self.current_block
        }
        self.lifecycle_states[passport_id] = LifecycleState.MANUFACTURED
        return tx_hash

    def anchor_recycling_evidence(
        self,
        event_id: str,
        passport_id: str,
        evidence_commitment: str,
        recycler_address: str
    ) -> str:
        if not self.is_connected:
            raise ConnectionError("RPC node offline (LOCAL TESTNET disconnected)")
        if event_id in self.events:
            raise ValueError(f"Replay detected: Event {event_id} already anchored on-chain.")
        if passport_id not in self.passports:
            raise ValueError(f"Passport {passport_id} not registered on-chain.")

        tx_hash = self._generate_tx_hash("ANCHOR_EVIDENCE", event_id)
        self.events[event_id] = OnChainEvent(
            event_id=event_id,
            passport_id=passport_id,
            evidence_commitment=evidence_commitment,
            recycler_address=recycler_address,
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            tx_hash=tx_hash,
            block_number=self.current_block
        )
        return tx_hash

    def issue_certificate(
        self,
        certificate_id: str,
        event_id: str,
        passport_id: str,
        cert_hash: str,
        evidence_commitment: str,
        issuer_address: str
    ) -> str:
        if not self.is_connected:
            raise ConnectionError("RPC node offline (LOCAL TESTNET disconnected)")
        if certificate_id in self.certificates:
            raise ValueError(f"Certificate {certificate_id} already issued.")
        # Ensure only one certificate per recycling event (Anti-Replay)
        for existing in self.certificates.values():
            if existing.event_id == event_id:
                raise ValueError(f"Duplicate certificate prohibited: Event {event_id} already has certificate {existing.certificate_id}.")

        tx_hash = self._generate_tx_hash("ISSUE_CERTIFICATE", certificate_id)
        self.certificates[certificate_id] = OnChainCertificate(
            certificate_id=certificate_id,
            event_id=event_id,
            passport_id=passport_id,
            cert_hash=cert_hash,
            evidence_commitment=evidence_commitment,
            issuer_address=issuer_address,
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            tx_hash=tx_hash,
            block_number=self.current_block
        )
        return tx_hash

    def flag_product(self, passport_id: str, event_id: str, reason: str):
        if not self.is_connected:
            raise ConnectionError("RPC node offline (LOCAL TESTNET disconnected)")
        self.flagged_products[passport_id] = reason
        self.lifecycle_states[passport_id] = LifecycleState.FLAGGED

    def resolve_flag(self, passport_id: str, auditor_address: str, target_state: LifecycleState):
        if not self.is_connected:
            raise ConnectionError("RPC node offline (LOCAL TESTNET disconnected)")
        if passport_id in self.flagged_products:
            del self.flagged_products[passport_id]
        self.lifecycle_states[passport_id] = target_state
