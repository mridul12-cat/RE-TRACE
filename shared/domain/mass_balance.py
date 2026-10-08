"""
RE:TRACE Deterministic Mass-Balance Verification Engine.

Implements closed-form physics-based conservation-of-mass evaluation and component
recovery yield boundary checks per ORIGINAL_REQUEST.md:71-84 and EU Battery Reg 2023/1542.
AI is NEVER used for mass-balance calculations.
"""

from enum import Enum
import math
from typing import Dict, List, Optional, Tuple

from shared.schemas.evidence_bundle import MassBalanceVerificationResult
from shared.schemas.material import MaterialComposition
from shared.schemas.recycling_event import ClaimedMaterial


class MassBalanceOutcome(str, Enum):
    """Canonical three-tier deterministic verification outcomes."""
    VALID = "VALID"          # Verified legitimate recovery within expected physics tolerance
    BORDERLINE = "BORDERLINE"# Near boundary; requires supervisor/auditor review
    IMPOSSIBLE = "IMPOSSIBLE"# Exceeds thermodynamic ceiling or conservation of mass; flagged


def _is_strictly_greater(val: float, bound: float, rel_tol: float = 1e-5, abs_tol: float = 1e-6) -> bool:
    """Returns True if val strictly exceeds bound beyond float tolerance."""
    return val > bound and not math.isclose(val, bound, rel_tol=rel_tol, abs_tol=abs_tol)


def _is_strictly_less(val: float, bound: float, rel_tol: float = 1e-5, abs_tol: float = 1e-6) -> bool:
    """Returns True if val is strictly below bound beyond float tolerance."""
    return val < bound and not math.isclose(val, bound, rel_tol=rel_tol, abs_tol=abs_tol)


def _format_mass_kg(mass_kg: float) -> str:
    """Formats mass adaptively to preserve precision for small consumer battery components."""
    if abs(mass_kg) < 0.1:
        return f"{mass_kg:.4f} kg"
    return f"{mass_kg:.2f} kg"


def evaluate_mass_balance(
    intake_mass_kg: float,
    composition: MaterialComposition,
    claimed_materials: List[ClaimedMaterial],
    scale_uncertainty_pct: float = 0.5,
) -> MassBalanceVerificationResult:
    """
    Deterministically evaluates a recycling batch against physical laws and BoM priors.

    Parameters:
    - intake_mass_kg: Gross physical input mass (MEASURED)
    - composition: Digital Product Passport Bill of Materials (REFERENCE_ASSUMED)
    - claimed_materials: Declared recovered material quantities (MEASURED/OBSERVED)
    - scale_uncertainty_pct: Instrument calibration tolerance (+/- %, default 0.5%)

    Returns:
    - MassBalanceVerificationResult containing detailed metrics, decision, and math explanation.
    """
    scale_tau = scale_uncertainty_pct / 100.0

    # 1. Input Validation Guards (Defense-in-depth)
    if not math.isfinite(intake_mass_kg) or intake_mass_kg <= 0.0:
        msg = (
            f"IMPOSSIBLE: Gross intake mass must be strictly positive and finite (> 0); "
            f"received {intake_mass_kg} kg."
        )
        safe_claimed = sum(
            c.claimed_mass_kg for c in claimed_materials
            if math.isfinite(c.claimed_mass_kg) and c.claimed_mass_kg > 0
        )
        return MassBalanceVerificationResult(
            intake_mass_kg=0.0,
            claimed_total_recovered_kg=round(safe_claimed, 4),
            expected_recoverable_kg={},
            tolerance_bands_kg={},
            discrepancies_kg={"GROSS_INTAKE": -1.0},
            decision=MassBalanceOutcome.IMPOSSIBLE.value,
            mathematical_explanation=msg,
        )

    if not claimed_materials:
        msg = "IMPOSSIBLE: No recovered materials declared in recycling batch."
        return MassBalanceVerificationResult(
            intake_mass_kg=round(intake_mass_kg, 4),
            claimed_total_recovered_kg=0.0,
            expected_recoverable_kg={},
            tolerance_bands_kg={},
            discrepancies_kg={"TOTAL_MASS": 0.0},
            decision=MassBalanceOutcome.IMPOSSIBLE.value,
            mathematical_explanation=msg,
        )

    # 2. Pre-aggregate Claimed Materials by Canonical Material Name (Sybil / Smurfing Guard)
    aggregated_claims: Dict[str, float] = {}
    for claim in claimed_materials:
        raw_name = claim.material_name.strip()
        m_val = claim.claimed_mass_kg

        # Resolve canonical name from composition if present (case-insensitive)
        canonical_name = raw_name
        for bom_comp in composition.components:
            if bom_comp.material_name.strip().lower() == raw_name.lower():
                canonical_name = bom_comp.material_name.strip()
                break

        aggregated_claims[canonical_name] = aggregated_claims.get(canonical_name, 0.0) + m_val

    claimed_total_recovered = sum(aggregated_claims.values())
    max_physical_total_intake = intake_mass_kg * (1.0 + scale_tau)

    expected_recoverable: Dict[str, float] = {}
    tolerance_bands: Dict[str, Tuple[float, float]] = {}
    discrepancies: Dict[str, float] = {}

    component_decisions: Dict[str, MassBalanceOutcome] = {}
    explanation_lines: List[str] = []

    # 3. Total Mass Conservation Check
    if _is_strictly_greater(claimed_total_recovered, max_physical_total_intake):
        excess = claimed_total_recovered - max_physical_total_intake
        excess_pct = (excess / intake_mass_kg) * 100.0 if intake_mass_kg > 0 else 100.0
        msg = (
            f"IMPOSSIBLE: Gross conservation of mass violated. Total claimed recovered mass "
            f"({_format_mass_kg(claimed_total_recovered)}) exceeds gross intake mass "
            f"({_format_mass_kg(intake_mass_kg)}) with scale tolerance "
            f"({_format_mass_kg(max_physical_total_intake)}) by +{_format_mass_kg(excess)} (+{excess_pct:.2f}%)."
        )
        return MassBalanceVerificationResult(
            intake_mass_kg=round(intake_mass_kg, 4),
            claimed_total_recovered_kg=round(claimed_total_recovered, 4),
            expected_recoverable_kg={},
            tolerance_bands_kg={},
            discrepancies_kg={"TOTAL_MASS": round(claimed_total_recovered - intake_mass_kg, 4)},
            decision=MassBalanceOutcome.IMPOSSIBLE.value,
            mathematical_explanation=msg,
        )

    # 4. Component-by-Component Plausibility Evaluation on Consolidated Claims
    for name, m_claim in aggregated_claims.items():
        # Negative mass check
        if not math.isfinite(m_claim) or m_claim < 0:
            component_decisions[name] = MassBalanceOutcome.IMPOSSIBLE
            explanation_lines.append(f"IMPOSSIBLE: Claimed mass for '{name}' is non-finite or negative ({m_claim}).")
            continue

        try:
            comp = composition.get_component(name)
        except KeyError:
            # Undeclared material not present in product BoM
            component_decisions[name] = MassBalanceOutcome.IMPOSSIBLE
            explanation_lines.append(
                f"IMPOSSIBLE: Material '{name}' is not present in product Bill of Materials."
            )
            continue

        # Mathematical parameters
        w_ref = comp.percentage / 100.0
        loss_pct = comp.expected_yield_loss_pct / 100.0
        nominal_yield = 1.0 - loss_pct
        tau = comp.tolerance_band_pct / 100.0

        # Expected mass and bounding envelopes
        m_exp = intake_mass_kg * w_ref * nominal_yield
        m_lower = m_exp * (1.0 - tau)

        # Absolute thermodynamic stoichiometric ceiling (100% recovery with scale tolerance)
        m_abs_max = intake_mass_kg * w_ref * (1.0 + scale_tau)

        # Defensively clamp upper bounds so nominal envelopes never exceed physical reality
        m_upper = min(m_exp * (1.0 + tau), m_abs_max)
        m_borderline_upper = min(m_exp * (1.0 + 2.0 * tau), m_abs_max)
        m_borderline_lower = max(0.0, m_exp * (1.0 - 2.0 * tau))

        expected_recoverable[name] = round(m_exp, 4)
        tolerance_bands[name] = (round(m_lower, 4), round(m_upper, 4))
        dev = m_claim - m_exp
        discrepancies[name] = round(dev, 4)

        # Complete Mutually Exclusive Decision Tree
        if _is_strictly_greater(m_claim, m_abs_max) or _is_strictly_greater(m_claim, m_borderline_upper):
            # Severe over-recovery / Stoichiometric violation
            component_decisions[name] = MassBalanceOutcome.IMPOSSIBLE
            explanation_lines.append(
                f"IMPOSSIBLE: Claimed {_format_mass_kg(m_claim)} {name} exceeds stoichiometric ceiling "
                f"({_format_mass_kg(m_abs_max)}) or upper threshold ({_format_mass_kg(m_borderline_upper)}) "
                f"by +{_format_mass_kg(dev)}. Physical theoretical recovery at 100% efficiency is only "
                f"{_format_mass_kg(intake_mass_kg * w_ref)}."
            )
        elif _is_strictly_less(m_claim, m_borderline_lower):
            # Severe under-recovery / Deficit violation
            component_decisions[name] = MassBalanceOutcome.IMPOSSIBLE
            deficit = m_exp - m_claim
            deficit_pct = (deficit / m_exp) * 100.0 if m_exp > 0 else 0.0
            explanation_lines.append(
                f"IMPOSSIBLE: Claimed {_format_mass_kg(m_claim)} {name} indicates severe process deficit or unrecovered material. "
                f"Claim falls below minimum viable threshold ({_format_mass_kg(m_borderline_lower)}) by "
                f"-{_format_mass_kg(deficit)} (-{deficit_pct:.1f}% vs expected {_format_mass_kg(m_exp)}). "
                f"Batch fails minimum recovery standards."
            )
        elif _is_strictly_greater(m_claim, m_upper) or _is_strictly_less(m_claim, m_lower):
            # Borderline tolerance deviation
            component_decisions[name] = MassBalanceOutcome.BORDERLINE
            explanation_lines.append(
                f"BORDERLINE: Claimed {_format_mass_kg(m_claim)} {name} deviates from nominal range "
                f"[{_format_mass_kg(m_lower)} – {_format_mass_kg(m_upper)}] (dev: {dev:+.2f} kg). "
                f"Requires supervisor audit of assay titration logs."
            )
        else:
            # Nominal verified recovery
            component_decisions[name] = MassBalanceOutcome.VALID
            eff_yield = (m_claim / (intake_mass_kg * w_ref)) * 100.0 if (intake_mass_kg * w_ref) > 0 else 0.0
            explanation_lines.append(
                f"VALID: Claimed {_format_mass_kg(m_claim)} {name} fits nominal recovery envelope "
                f"[{_format_mass_kg(m_lower)} – {_format_mass_kg(m_upper)}] "
                f"(effective yield: {eff_yield:.1f}% vs expected {nominal_yield * 100:.1f}%)."
            )

    # 5. Overall Aggregate Verdict
    if any(d == MassBalanceOutcome.IMPOSSIBLE for d in component_decisions.values()):
        aggregate_decision = MassBalanceOutcome.IMPOSSIBLE
    elif any(d == MassBalanceOutcome.BORDERLINE for d in component_decisions.values()):
        aggregate_decision = MassBalanceOutcome.BORDERLINE
    else:
        aggregate_decision = MassBalanceOutcome.VALID

    explanation = " | ".join(explanation_lines)

    return MassBalanceVerificationResult(
        intake_mass_kg=round(intake_mass_kg, 4),
        claimed_total_recovered_kg=round(claimed_total_recovered, 4),
        expected_recoverable_kg=expected_recoverable,
        tolerance_bands_kg=tolerance_bands,
        discrepancies_kg=discrepancies,
        decision=aggregate_decision.value,
        mathematical_explanation=explanation,
    )
