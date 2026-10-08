"""
Unit tests for RE:TRACE Deterministic Mass-Balance Engine.
"""

import glob
import os
import sys
import unittest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

for _pat in [
    os.path.join(_PROJECT_ROOT, ".venv", "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages"),
    os.path.join(_PROJECT_ROOT, ".venv", "lib", "python*", "site-packages"),
]:
    for _matched in glob.glob(_pat):
        if os.path.isdir(_matched) and _matched not in sys.path:
            sys.path.insert(0, _matched)

from pydantic import ValidationError

from shared.domain.mass_balance import MassBalanceOutcome, evaluate_mass_balance
from shared.fixtures.reference_materials import (
    EV_BATTERY_NMC_622_COMPOSITION,
    SMARTPHONE_LCO_COMPOSITION,
    EV_BATTERY_LFP_COMPOSITION,
    SODIUM_ION_BATTERY_COMPOSITION,
)
from shared.schemas.recycling_event import ClaimedMaterial


class TestMassBalanceEngine(unittest.TestCase):
    """Tier 1 Unit tests for RE:TRACE Deterministic Mass-Balance Engine."""

    def test_legitimate_nmc622_batch(self):
        """Case A: Legitimate recycling within normal physical tolerance."""
        intake_mass = 1000.0  # kg
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Nickel", claimed_mass_kg=165.60),  # exp: 165.60
            ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=55.80),    # exp: 55.80
            ClaimedMaterial(material_name="Lithium", claimed_mass_kg=21.00),   # exp: 21.00
            ClaimedMaterial(material_name="Copper", claimed_mass_kg=105.28),   # exp: 105.28
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.VALID.value)
        self.assertIn("VALID", res.mathematical_explanation)
        self.assertAlmostEqual(res.claimed_total_recovered_kg, 347.68, places=2)

    def test_borderline_claim(self):
        """Case B: Claim near tolerance boundary requires review."""
        intake_mass = 1000.0
        comp = EV_BATTERY_NMC_622_COMPOSITION
        # Cobalt exp: 55.80 kg, tau=5% -> upper: 58.59 kg. Claim 59.50 kg is in [58.59, 60.30]
        claims = [
            ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=59.50),
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.BORDERLINE.value)
        self.assertIn("BORDERLINE", res.mathematical_explanation)

    def test_impossible_claim_exceeds_stoichiometric_ceiling(self):
        """Case C: Claim exceeds absolute physical ceiling -> IMPOSSIBLE."""
        intake_mass = 1000.0
        comp = EV_BATTERY_NMC_622_COMPOSITION
        # Cobalt total present is 60.00 kg. Claiming 90.00 kg creates matter from nothing!
        claims = [
            ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=90.00),
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.IMPOSSIBLE.value)
        self.assertIn("IMPOSSIBLE", res.mathematical_explanation)
        self.assertIn("stoichiometric ceiling", res.mathematical_explanation)

    def test_total_mass_conservation_violation(self):
        """Total recovered mass cannot exceed intake mass plus scale uncertainty."""
        intake_mass = 1000.0
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Nickel", claimed_mass_kg=600.0),
            ClaimedMaterial(material_name="Aluminum", claimed_mass_kg=500.0),
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.IMPOSSIBLE.value)
        self.assertIn("Gross conservation of mass violated", res.mathematical_explanation)

    def test_undeclared_material(self):
        """Claiming an element not in the product BoM must be rejected."""
        intake_mass = 1000.0
        comp = EV_BATTERY_NMC_622_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Platinum", claimed_mass_kg=5.0),
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.IMPOSSIBLE.value)
        self.assertIn("not present in product Bill of Materials", res.mathematical_explanation)

    def test_negative_mass_claim(self):
        """Negative recovered mass is physically impossible and rejected by schema."""
        with self.assertRaises(ValidationError):
            ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=-5.0)

    def test_smartphone_lco_batch(self):
        """Validates Smartphone LCO chemistry recovery evaluation."""
        intake_mass = 450.0  # 10,000 units
        comp = SMARTPHONE_LCO_COMPOSITION
        # Cobalt: 20% in BoM = 90.0 kg. Yield loss 6% (94% recovery) -> expected 84.6 kg
        claims = [
            ClaimedMaterial(material_name="Cobalt", claimed_mass_kg=84.6),
            ClaimedMaterial(material_name="Copper", claimed_mass_kg=40.61), # 9.5% * 95% = 40.6125 kg
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.VALID.value)

    def test_lfp_battery_batch(self):
        """Validates Lithium Iron Phosphate (LFP / LiFePO4) battery recovery evaluation."""
        intake_mass = 1000.0
        comp = EV_BATTERY_LFP_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Iron", claimed_mass_kg=220.5),       # 24.5% * 90% = 220.5 kg
            ClaimedMaterial(material_name="Lithium", claimed_mass_kg=25.5),     # 3.4% * 75% = 25.5 kg
            ClaimedMaterial(material_name="Copper", claimed_mass_kg=89.3),      # 9.5% * 94% = 89.3 kg
            ClaimedMaterial(material_name="Aluminum", claimed_mass_kg=135.0),   # 15.0% * 90% = 135.0 kg
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.VALID.value)
        self.assertIn("VALID", res.mathematical_explanation)

    def test_sodium_ion_battery_batch(self):
        """Validates critical mineral-free Sodium-Ion (SIB / Prussian Blue) battery recovery."""
        intake_mass = 1000.0
        comp = SODIUM_ION_BATTERY_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Sodium", claimed_mass_kg=36.0),      # 4.5% * 80% = 36.0 kg
            ClaimedMaterial(material_name="Iron", claimed_mass_kg=202.4),       # 22.0% * 92% = 202.4 kg
            ClaimedMaterial(material_name="Manganese", claimed_mass_kg=108.0),  # 12.0% * 90% = 108.0 kg
            ClaimedMaterial(material_name="Aluminum", claimed_mass_kg=235.0),   # 25.0% * 94% = 235.0 kg
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.VALID.value)
        self.assertIn("VALID", res.mathematical_explanation)

    def test_sodium_ion_undeclared_copper_rejection(self):
        """Sodium-ion batteries use Aluminum for both collectors (0% Copper). Claiming Copper must fail."""
        intake_mass = 1000.0
        comp = SODIUM_ION_BATTERY_COMPOSITION
        claims = [
            ClaimedMaterial(material_name="Sodium", claimed_mass_kg=36.0),
            ClaimedMaterial(material_name="Copper", claimed_mass_kg=50.0),      # Undeclared material
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.IMPOSSIBLE.value)
        self.assertIn("Material 'Copper' is not present in product Bill of Materials", res.mathematical_explanation)

    def test_sodium_ion_super_stoichiometric_claim(self):
        """Claiming more Sodium than chemically exists in the battery must be flagged as IMPOSSIBLE."""
        intake_mass = 1000.0
        comp = SODIUM_ION_BATTERY_COMPOSITION
        # Sodium in BoM is 4.5% = 45.0 kg. Claiming 65.0 kg is thermodynamically impossible.
        claims = [
            ClaimedMaterial(material_name="Sodium", claimed_mass_kg=65.0),
        ]
        res = evaluate_mass_balance(intake_mass, comp, claims)
        self.assertEqual(res.decision, MassBalanceOutcome.IMPOSSIBLE.value)
        self.assertIn("exceeds stoichiometric ceiling", res.mathematical_explanation)


if __name__ == "__main__":
    unittest.main()
