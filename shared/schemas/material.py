"""
RE:TRACE Canonical Material Composition Schema.

Defines Bill of Materials (BoM), elemental constituents, recovery yield losses,
tolerance bands, and enforces stoichiometric percentage sum verification (100% +/- 0.5%).
"""

from typing import List
from pydantic import BaseModel, Field, model_validator
from shared.schemas.provenance import ProvenanceCategory


class MaterialComponent(BaseModel):
    """
    Individual material or elemental constituent in a product Bill of Materials.
    """
    material_name: str = Field(..., description="Element or composite name (e.g., 'Nickel', 'Cobalt', 'Lithium')")
    mass_kg: float = Field(..., gt=0.0, description="Nominal mass of component in kg")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Mass percentage of total product mass (0-100%)")
    is_critical_raw_material: bool = Field(default=False, description="Flag for EU Critical Raw Material status")
    expected_yield_loss_pct: float = Field(
        default=10.0,
        ge=0.0,
        le=100.0,
        description="Standard physical process recovery loss percentage (L_i)",
    )
    tolerance_band_pct: float = Field(
        default=5.0,
        ge=0.0,
        le=50.0,
        description="Acceptable mass-balance variance band (+/- %)",
    )
    provenance: ProvenanceCategory = Field(
        default=ProvenanceCategory.REFERENCE_ASSUMED,
        description="Provenance of component specification",
    )


class MaterialComposition(BaseModel):
    """
    Complete Bill of Materials (BoM) specification for a Digital Product Passport.
    Enforces that component percentages sum to 100% (+/- 0.5%).
    """
    components: List[MaterialComponent] = Field(..., min_length=1, description="List of constituent material components")
    total_mass_kg: float = Field(..., gt=0.0, description="Total nominal mass of the assembled product in kg")

    @model_validator(mode="after")
    def validate_percentages_sum(self):
        total_pct = sum(c.percentage for c in self.components)
        if not (99.5 <= total_pct <= 100.5):
            raise ValueError(
                f"Sum of material percentages must equal 100.0% within +/-0.5% tolerance; got {total_pct:.2f}%"
            )
        return self

    def get_component(self, material_name: str) -> MaterialComponent:
        """Helper to find a component by case-insensitive name."""
        name_lower = material_name.strip().lower()
        for comp in self.components:
            if comp.material_name.strip().lower() == name_lower:
                return comp
        raise KeyError(f"Material '{material_name}' not found in composition")
