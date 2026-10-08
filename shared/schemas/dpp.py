"""
RE:TRACE Canonical Digital Product Passport (DPP) Schema.

Represents an industrial or consumer circular asset tracked throughout its lifecycle,
including identity, manufacturer, Bill of Materials (BoM), and state machine position.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from shared.domain.lifecycle import LifecycleState
from shared.schemas.material import MaterialComposition


class DigitalProductPassport(BaseModel):
    """
    Canonical Digital Product Passport per EU Ecodesign and Battery Regulation specifications.
    """
    model_config = ConfigDict(use_enum_values=False)

    passport_id: str = Field(..., description="Unique immutable passport identifier (UUID or decentralized ID)")
    product_id: str = Field(..., description="OEM serial number, SKU, or GS1 Digital Link GTIN")
    product_name: str = Field(..., description="Descriptive product commercial model name")
    product_category: str = Field(..., description="E.g., 'EV_BATTERY', 'CONSUMER_ELECTRONICS', 'INDUSTRIAL_BATTERY'")
    manufacturer: str = Field(..., description="Legal entity name or identifier of manufacturer")
    manufacturing_date: datetime = Field(..., description="UTC manufacturing assembly timestamp")
    initial_total_mass_kg: float = Field(..., gt=0.0, description="Gross nominal mass at manufacturing in kg")
    material_composition: MaterialComposition = Field(..., description="Validated Bill of Materials and yield loss bounds")
    current_lifecycle_state: LifecycleState = Field(
        default=LifecycleState.MANUFACTURED,
        description="Current state within the canonical 7-state lifecycle machine",
    )
    created_at: datetime = Field(..., description="UTC registration timestamp")
    updated_at: datetime = Field(..., description="UTC last state transition timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional domain-specific attributes")

