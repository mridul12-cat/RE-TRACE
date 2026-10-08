"""
Adversarial Stress Test Suite for RE:TRACE Mass-Balance Verification Engine.

Challenger 1 (Milestone 1) verification harness — synchronized for remediated engine.
Verifies:
1. Floating-point boundary conditions with epsilon matching.
2. Total mass conservation violations (\\sum M_{claim} > M_{in}).
3. Super-stoichiometric claims and duplicate material splitting exploits.
4. Numerical edge cases: Zero intake, negative intake, NaN, Inf, and underflow.
5. Severe under-recovery logic (claims below lower borderline flagged as IMPOSSIBLE).
6. Reference dataset thermodynamic consistency (Casing Steel upper bound <= stoichiometric ceiling).
7. Empty claim and name permutation edge cases.
"""

import math
import pytest
from pydantic import ValidationError

from shared.domain.mass_balance import (
    MassBalanceOutcome,
    evaluate_mass_balance,
)
from shared.fixtures.reference_materials import (
    EV_BATTERY_NMC_622_COMPOSITION,
    NMC_622_COMPONENTS,
    SMARTPHONE_LCO_COMPOSITION,
    LCO_COMPONENTS,
)
from shared.schemas.evidence_bundle import MassBalanceVerificationResult
from shared.schemas.recycling_event import ClaimedMaterial


# =============================================================================
# 1. FLOATING-POINT BOUNDARY VALUE STRESS TESTS
# =============================================================================

class TestFloatingPointBoundaries:
    """Tests exact transitions at nominal, borderline, and stoichiometric limits."""

    @pytest.fixture
    def nmc_context(self):
        intake_mass = 1000.0
        comp = EV_BATTERY_NMC_622_COMPOSITION
        # Cobalt: w_ref = 0.06, nominal_yield = 0.93, tau = 0.05, scale_tau = 0.005
        # m_exp = 1000 * 0.06 * 0.93 = 55.80 kg
        # m_lower = 55.80 * (1 - 0.05) = 53.01 kg
        # m_upper = 55.80 * (1 + 0.05) = 58.59 kg
        # m_borderline_upper = 55.80 * (1 + 0.10) = 61.38 kg
        # m_borderline_lower = 55.80 * (1 - 0.10) = 50.22 kg
        # m_abs_max = 1000 * 0.06 * 1.005 = 60.30 kg
        return {
            "intake_mass": intake_mass,
            "comp": comp,
            "m_exp": 55.80,
            "m_lower": 53.01,
            "m_upper": 58.59,
            "m_borderline_upper": 61.38,
            "m_borderline_lower": 50.22,
            "m_abs_max": 60.30,
        }

    def test_nominal_upper_boundary_epsilon(self, nmc_context):
        """
        Testing epsilon behavior around raw float m_upper.
        Published bound 58.59 kg is classified as VALID thanks to float tolerance matching.
        """
        ctx = nmc_context
        comp = ctx["comp"]

        c_cobalt = comp.get_component("Cobalt")
        raw_m_exp = ctx["intake_mass"] * (c_cobalt.percentage / 100.0) * (1.0 - c_cobalt.expected_yield_loss_pct / 100.0)
        raw_m_upper = raw_m_exp * (1.0 + c_cobalt.tolerance_band_pct / 100.0)

        # 1. Nominal recovery -> VALID
        c_below = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=raw_m_upper - 0.5)]
        res_below = evaluate_mass_balance(ctx["intake_mass"], comp, c_below)
        assert res_below.decision == MassBalanceOutcome.VALID.value

        # 2. Exactly at raw nominal upper bound -> VALID
        c_exact = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=raw_m_upper)]
        res_exact = evaluate_mass_balance(ctx["intake_mass"], comp, c_exact)
        assert res_exact.decision == MassBalanceOutcome.VALID.value

        # 3. Noticeably above nominal upper bound (in borderline zone) -> BORDERLINE
        c_above = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=raw_m_upper + 0.5)]
        res_above = evaluate_mass_balance(ctx["intake_mass"], comp, c_above)
        assert res_above.decision == MassBalanceOutcome.BORDERLINE.value

        # 4. Published rounded bound (58.59 kg) evaluates as VALID
        c_reported_bound = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=58.59)]
        res_reported = evaluate_mass_balance(ctx["intake_mass"], comp, c_reported_bound)
        assert res_reported.decision == MassBalanceOutcome.VALID.value
        assert "fits nominal recovery envelope" in res_reported.mathematical_explanation

    def test_stoichiometric_ceiling_boundary_epsilon(self, nmc_context):
        """Testing M_abs_max borderline and exceeding M_abs_max (IMPOSSIBLE)."""
        ctx = nmc_context

        # Within borderline zone below stoichiometric ceiling -> BORDERLINE
        c_below = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=ctx["m_abs_max"] - 0.2)]
        res_below = evaluate_mass_balance(ctx["intake_mass"], ctx["comp"], c_below)
        assert res_below.decision == MassBalanceOutcome.BORDERLINE.value

        # At absolute stoichiometric ceiling -> BORDERLINE
        c_exact = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=ctx["m_abs_max"])]
        res_exact = evaluate_mass_balance(ctx["intake_mass"], ctx["comp"], c_exact)
        assert res_exact.decision == MassBalanceOutcome.BORDERLINE.value

        # Above absolute stoichiometric ceiling -> IMPOSSIBLE
        c_above = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=ctx["m_abs_max"] + 0.5)]
        res_above = evaluate_mass_balance(ctx["intake_mass"], ctx["comp"], c_above)
        assert res_above.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "stoichiometric ceiling" in res_above.mathematical_explanation

    def test_nominal_lower_boundary_epsilon(self, nmc_context):
        """Testing M_lower nominal (VALID) and below M_lower (BORDERLINE)."""
        ctx = nmc_context

        # Nominal recovery above lower bound -> VALID
        c_above = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=ctx["m_lower"] + 0.5)]
        res_above = evaluate_mass_balance(ctx["intake_mass"], ctx["comp"], c_above)
        assert res_above.decision == MassBalanceOutcome.VALID.value

        # Exactly at lower nominal envelope -> VALID
        c_exact = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=ctx["m_lower"])]
        res_exact = evaluate_mass_balance(ctx["intake_mass"], ctx["comp"], c_exact)
        assert res_exact.decision == MassBalanceOutcome.VALID.value

        # Noticeably below lower nominal envelope (in borderline zone) -> BORDERLINE
        c_below = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=ctx["m_lower"] - 0.5)]
        res_below = evaluate_mass_balance(ctx["intake_mass"], ctx["comp"], c_below)
        assert res_below.decision == MassBalanceOutcome.BORDERLINE.value


# =============================================================================
# 2. SEVERE UNDER-RECOVERY FLAGGING AS IMPOSSIBLE
# =============================================================================

class TestUnderRecoveryFlaw:
    """
    Verifies that claims falling below m_borderline_lower are flagged as IMPOSSIBLE
    per EU Battery Regulation anti-greenwashing and mass-balance rules.
    """

    def test_lower_borderline_inverted_boundary_jump(self):
        """
        M_borderline_lower + 0.5 is BORDERLINE.
        M_borderline_lower is BORDERLINE.
        M_borderline_lower - 0.5 is correctly flagged as IMPOSSIBLE.
        """
        comp = EV_BATTERY_NMC_622_COMPOSITION
        m_borderline_lower = 50.22  # 55.80 * (1 - 2 * 0.05)

        # 1. Just above lower borderline -> BORDERLINE
        c_above = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=m_borderline_lower + 0.5)]
        res_above = evaluate_mass_balance(1000.0, comp, c_above)
        assert res_above.decision == MassBalanceOutcome.BORDERLINE.value

        # 2. Exactly at lower borderline -> BORDERLINE
        c_exact = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=m_borderline_lower)]
        res_exact = evaluate_mass_balance(1000.0, comp, c_exact)
        assert res_exact.decision == MassBalanceOutcome.BORDERLINE.value

        # 3. Below lower borderline -> IMPOSSIBLE
        c_below = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=m_borderline_lower - 0.5)]
        res_below = evaluate_mass_balance(1000.0, comp, c_below)
        assert res_below.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "severe process deficit" in res_below.mathematical_explanation

    def test_zero_recovery_falsely_classified_as_valid(self):
        """
        Claiming 0.0 kg recovered for a component with 93% expected recovery
        must be rejected as IMPOSSIBLE.
        """
        comp = EV_BATTERY_NMC_622_COMPOSITION
        c_zero = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=0.0)]
        res_zero = evaluate_mass_balance(1000.0, comp, c_zero)
        assert res_zero.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "severe process deficit" in res_zero.mathematical_explanation

    def test_severe_yield_deficit_classified_as_valid(self):
        """Claiming 10 kg Cobalt (16.7% recovery instead of 93%) must be IMPOSSIBLE."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        c_deficit = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=10.0)]
        res_deficit = evaluate_mass_balance(1000.0, comp, c_deficit)
        assert res_deficit.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "severe process deficit" in res_deficit.mathematical_explanation


# =============================================================================
# 3. SUPER-STOICHIOMETRIC & DUPLICATE SPLITTING EXPLOITS
# =============================================================================

class TestSuperStoichiometricExploits:
    """Challenges component-level stoichiometric ceilings and duplicate claim handling."""

    def test_single_component_super_stoichiometric_claim(self):
        """Claiming more material than physically present in BoM must be IMPOSSIBLE."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=65.0)]
        res = evaluate_mass_balance(1000.0, comp, claims)
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "stoichiometric ceiling" in res.mathematical_explanation

    def test_duplicate_material_claim_splitting_exploit(self):
        """
        Pre-aggregation blocks Sybil / smurfing claim splitting:
        10 duplicate entries of 55.0 kg Cobalt (total 550 kg Cobalt claimed, intake = 1000 kg).
        Engine returns IMPOSSIBLE.
        """
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=55.0) for _ in range(10)]
        res = evaluate_mass_balance(1000.0, comp, claims)

        assert res.claimed_total_recovered_kg == 550.0
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "stoichiometric ceiling" in res.mathematical_explanation


# =============================================================================
# 4. TOTAL MASS CONSERVATION VIOLATIONS
# =============================================================================

class TestTotalMassConservation:
    """Verifies that gross conservation of mass holds at the batch level."""

    def test_total_mass_exceeds_intake_plus_tolerance_epsilon(self):
        """Sum of claimed materials exceeds intake * (1 + scale_tau) -> IMPOSSIBLE."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        intake = 1000.0

        # Claim Nickel 600 kg, Aluminum 406.0 kg -> sum = 1006.0 kg (> 1005.0 kg max allowed)
        claims = [
            ClaimedMaterial(material_name="Nickel", claimed_mass_kg=600.0),
            ClaimedMaterial(material_name="Aluminum", claimed_mass_kg=406.0),
        ]
        res = evaluate_mass_balance(intake, comp, claims)
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "Gross conservation of mass violated" in res.mathematical_explanation

    def test_gross_total_mass_doubled(self):
        """Sum of claimed materials is 2000 kg for 1000 kg intake."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Nickel", claimed_mass_kg=1000.0),
            ClaimedMaterial(material_name="Aluminum", claimed_mass_kg=1000.0),
        ]
        res = evaluate_mass_balance(1000.0, comp, claims)
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "Gross conservation of mass violated" in res.mathematical_explanation


# =============================================================================
# 5. NUMERICAL & ROBUSTNESS EDGE CASES (Zero, Negative, NaN, Inf)
# =============================================================================

class TestNumericalRobustness:
    """Stress tests arithmetic anomalies: ZeroDivision, unhandled exceptions, NaN, Inf."""

    def test_intake_mass_zero_raises_zerodivision_error(self):
        """Gross intake 0.0 kg is handled cleanly and returns IMPOSSIBLE."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=10.0)]
        res = evaluate_mass_balance(0.0, comp, claims)
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "strictly positive" in res.mathematical_explanation

    def test_intake_mass_negative_raises_pydantic_validation_error(self):
        """Negative intake mass is rejected cleanly with IMPOSSIBLE."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=10.0)]
        res = evaluate_mass_balance(-100.0, comp, claims)
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "strictly positive" in res.mathematical_explanation

    def test_intake_mass_nan_raises_validation_error(self):
        """NaN intake mass is rejected cleanly with IMPOSSIBLE."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=55.8)]
        res = evaluate_mass_balance(float("nan"), comp, claims)
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "strictly positive and finite" in res.mathematical_explanation

    def test_intake_mass_inf_evaluates_to_valid(self):
        """Inf intake mass is rejected cleanly with IMPOSSIBLE."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=55.8)]
        res = evaluate_mass_balance(float("inf"), comp, claims)
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "strictly positive and finite" in res.mathematical_explanation

    def test_empty_claimed_materials_list_evaluates_to_valid(self):
        """Empty claims list evaluates to IMPOSSIBLE with explicit message."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        res = evaluate_mass_balance(1000.0, comp, [])
        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "No recovered materials declared" in res.mathematical_explanation


# =============================================================================
# 6. REFERENCE DATASET THERMODYNAMIC INCONSISTENCY (Casing Steel)
# =============================================================================

class TestReferenceDatasetsThermodynamics:
    """Verifies physical plausibility of reference material parameters."""

    def test_casing_steel_nominal_upper_exceeds_stoichiometric_ceiling(self):
        """
        With tolerance_band_pct = 2.0%, Casing Steel upper yield <= stoichiometric ceiling.
        """
        comp = EV_BATTERY_NMC_622_COMPOSITION
        steel_comp = comp.get_component("Casing Steel")

        y_nom = 1.0 - (steel_comp.expected_yield_loss_pct / 100.0)
        tau = steel_comp.tolerance_band_pct / 100.0
        upper_yield = y_nom * (1.0 + tau)

        scale_tau = 0.005  # 0.5% scale tolerance
        abs_max_yield = 1.0 + scale_tau

        assert upper_yield <= abs_max_yield, (
            f"Upper yield {upper_yield:.4f} must be <= stoichiometric limit {abs_max_yield:.4f}"
        )

        # Claiming nominal recovery yields VALID
        claim_nominal = [
            ClaimedMaterial(material_name="Casing Steel", claimed_mass_kg=117.60)
        ]
        res = evaluate_mass_balance(1000.0, comp, claim_nominal)
        assert res.decision == MassBalanceOutcome.VALID.value
        lower_reported, upper_reported = res.tolerance_bands_kg["Casing Steel"]
        assert upper_reported <= 120.60, f"Reported upper bound {upper_reported} exceeds stoichiometric limit 120.60!"

        # Claiming mass above stoichiometric ceiling triggers IMPOSSIBLE
        claim_super = [
            ClaimedMaterial(material_name="Casing Steel", claimed_mass_kg=120.80)
        ]
        res_super = evaluate_mass_balance(1000.0, comp, claim_super)
        assert res_super.decision == MassBalanceOutcome.IMPOSSIBLE.value

    def test_smartphone_lco_small_mass_precision(self):
        """
        Low-mass consumer cells retain 4-decimal precision in explanation text.
        """
        comp = SMARTPHONE_LCO_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Copper", claimed_mass_kg=0.045 * 0.095 * 0.95),
        ]
        res = evaluate_mass_balance(0.045, comp, claims)
        assert res.decision == MassBalanceOutcome.VALID.value
        assert "0.0041 kg" in res.mathematical_explanation


# =============================================================================
# 7. COMPONENT PERMUTATIONS & CASE SENSITIVITY
# =============================================================================

class TestComponentPermutationsAndCaseSensitivity:
    """Tests whitespace, case sensitivity, and order independence."""

    def test_case_sensitivity_duplicate_bypass(self):
        """
        Pre-aggregation groups 'Cobalt' and 'cobalt' together into canonical name.
        Total 111.6 kg exceeds stoichiometric ceiling -> IMPOSSIBLE.
        """
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=55.8),
            ClaimedMaterial(material_name="cobalt", claimed_mass_kg=55.8),
        ]
        res = evaluate_mass_balance(1000.0, comp, claims)

        assert res.decision == MassBalanceOutcome.IMPOSSIBLE.value
        assert "stoichiometric ceiling" in res.mathematical_explanation
        assert res.claimed_total_recovered_kg == 111.6

    def test_order_independence_with_impossible_claim(self):
        """Order of valid and impossible claims should not affect aggregate IMPOSSIBLE outcome."""
        comp = EV_BATTERY_NMC_622_COMPOSITION
        valid_c = ClaimedMaterial(material_name="Nickel", claimed_mass_kg=165.6)
        invalid_c = ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=90.0)

        # Order 1: Valid then Invalid
        res1 = evaluate_mass_balance(1000.0, comp, [valid_c, invalid_c])
        assert res1.decision == MassBalanceOutcome.IMPOSSIBLE.value

        # Order 2: Invalid then Valid
        res2 = evaluate_mass_balance(1000.0, comp, [invalid_c, valid_c])
        assert res2.decision == MassBalanceOutcome.IMPOSSIBLE.value
