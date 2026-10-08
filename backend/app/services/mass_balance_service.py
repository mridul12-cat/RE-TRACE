"""
backend/app/services/mass_balance_service.py — Mass-Balance Verification Service.
Enforces Section R3: AI is NEVER used for mass-balance decisions.
"""

from typing import List, Dict, Any, Optional
from shared.domain.mass_balance import evaluate_mass_balance, MassBalanceOutcome
from shared.schemas.material import MaterialComposition
from shared.schemas.recycling_event import ClaimedMaterial
from shared.schemas.evidence_bundle import MassBalanceVerificationResult


class MassBalanceService:
    """Service wrapping the deterministic closed-form mass-balance evaluation."""

    @staticmethod
    def evaluate(
        intake_mass_kg: float,
        composition: MaterialComposition,
        claimed_materials: List[ClaimedMaterial],
        scale_uncertainty_pct: float = 0.5
    ) -> MassBalanceVerificationResult:
        return evaluate_mass_balance(
            intake_mass_kg=intake_mass_kg,
            composition=composition,
            claimed_materials=claimed_materials,
            scale_uncertainty_pct=scale_uncertainty_pct
        )


mass_balance_service = MassBalanceService()
