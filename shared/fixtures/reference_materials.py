"""
RE:TRACE Circular Economy Reference Datasets.

Official benchmark compositions and Best Available Techniques (BAT) recovery yields
grounded in EU Battery Regulation (EU) 2023/1542 Annex XII and Argonne BatPaC models.
"""

from datetime import datetime, timezone
from shared.schemas.dpp import DigitalProductPassport
from shared.schemas.material import MaterialComponent, MaterialComposition
from shared.schemas.provenance import ProvenanceCategory
from shared.domain.lifecycle import LifecycleState


# -------------------------------------------------------------------------
# Dataset 1: EV Traction Battery Module (NMC 622 Chemistry)
# -------------------------------------------------------------------------
NMC_622_COMPONENTS = [
    MaterialComponent(
        material_name="Nickel",
        mass_kg=4.50,
        percentage=18.00,
        is_critical_raw_material=True,
        expected_yield_loss_pct=8.0,   # 92% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Cobalt",
        mass_kg=1.50,
        percentage=6.00,
        is_critical_raw_material=True,
        expected_yield_loss_pct=7.0,   # 93% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Manganese",
        mass_kg=1.50,
        percentage=6.00,
        is_critical_raw_material=True,
        expected_yield_loss_pct=12.0,  # 88% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Lithium",
        mass_kg=0.70,
        percentage=2.80,
        is_critical_raw_material=True,
        expected_yield_loss_pct=25.0,  # 75% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Copper",
        mass_kg=2.80,
        percentage=11.20,
        is_critical_raw_material=True,
        expected_yield_loss_pct=6.0,   # 94% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Aluminum",
        mass_kg=4.00,
        percentage=16.00,
        is_critical_raw_material=False,
        expected_yield_loss_pct=12.0,  # 88% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Anode Graphite",
        mass_kg=3.75,
        percentage=15.00,
        is_critical_raw_material=True,
        expected_yield_loss_pct=15.0,  # 85% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Casing Steel",
        mass_kg=3.00,
        percentage=12.00,
        is_critical_raw_material=False,
        expected_yield_loss_pct=2.0,   # 98% BAT recovery
        tolerance_band_pct=2.0,        # 2% tolerance ensures upper envelope (99.96%) <= stoichiometric ceiling (100.50%)
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Electrolyte & Inerts",
        mass_kg=3.25,
        percentage=13.00,
        is_critical_raw_material=False,
        expected_yield_loss_pct=100.0, # Process loss / thermal oxidation
        tolerance_band_pct=10.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
]

EV_BATTERY_NMC_622_COMPOSITION = MaterialComposition(
    components=NMC_622_COMPONENTS,
    total_mass_kg=25.0,
)

EV_BATTERY_NMC_622_DPP = DigitalProductPassport(
    passport_id="dpp-ev-nmc622-2026-m04",
    product_id="SKU-EV-NMC622-48V",
    product_name="VoltMax EV Traction Battery Module NMC 622 (24V 6S2P)",
    product_category="EV_BATTERY",
    manufacturer="NorthVolt Energy Systems AB",
    manufacturing_date=datetime(2026, 3, 15, 8, 30, tzinfo=timezone.utc),
    initial_total_mass_kg=25.0,
    material_composition=EV_BATTERY_NMC_622_COMPOSITION,
    current_lifecycle_state=LifecycleState.MANUFACTURED,
    created_at=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
    updated_at=datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
    metadata={
        "chemistry": "NMC 622",
        "cell_count": 12,
        "regulation": "EU Battery Regulation 2023/1542 Annex XII",
        "standard_batch_modules": 40,
        "standard_batch_mass_kg": 1000.0,
    },
)


# -------------------------------------------------------------------------
# Dataset 2: Smartphone Li-ion Battery (LCO Chemistry)
# -------------------------------------------------------------------------
LCO_COMPONENTS = [
    MaterialComponent(
        material_name="Cobalt",
        mass_kg=0.009,
        percentage=20.00,
        is_critical_raw_material=True,
        expected_yield_loss_pct=6.0,   # 94% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Lithium",
        mass_kg=0.00108,
        percentage=2.40,
        is_critical_raw_material=True,
        expected_yield_loss_pct=22.0,  # 78% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Copper",
        mass_kg=0.004275,
        percentage=9.50,
        is_critical_raw_material=True,
        expected_yield_loss_pct=5.0,   # 95% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Aluminum",
        mass_kg=0.0063,
        percentage=14.00,
        is_critical_raw_material=False,
        expected_yield_loss_pct=10.0,  # 90% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Anode Graphite",
        mass_kg=0.0081,
        percentage=18.00,
        is_critical_raw_material=True,
        expected_yield_loss_pct=15.0,  # 85% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Casing & Electrolyte",
        mass_kg=0.016245,
        percentage=36.10,
        is_critical_raw_material=False,
        expected_yield_loss_pct=100.0, # Process loss / polymer casing
        tolerance_band_pct=10.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
]

SMARTPHONE_LCO_COMPOSITION = MaterialComposition(
    components=LCO_COMPONENTS,
    total_mass_kg=0.045,  # 45 grams
)

SMARTPHONE_LCO_DPP = DigitalProductPassport(
    passport_id="dpp-consumer-lco-2026-b10",
    product_id="SKU-PHONE-BATT-4500",
    product_name="UltraPower 4500mAh Smartphone Li-ion Pouch Cell",
    product_category="CONSUMER_BATTERY",
    manufacturer="Apex Energy Technologies Inc.",
    manufacturing_date=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
    initial_total_mass_kg=0.045,
    material_composition=SMARTPHONE_LCO_COMPOSITION,
    current_lifecycle_state=LifecycleState.MANUFACTURED,
    created_at=datetime(2026, 1, 10, 10, 30, tzinfo=timezone.utc),
    updated_at=datetime(2026, 1, 10, 10, 30, tzinfo=timezone.utc),
    metadata={
        "chemistry": "LCO (LiCoO2)",
        "capacity_mah": 4500,
        "standard_batch_units": 10000,
        "standard_batch_mass_kg": 450.0,
    },
)


# -------------------------------------------------------------------------
# Dataset 3: EV / ESS Traction Battery (LFP Chemistry — LiFePO4)
# -------------------------------------------------------------------------
LFP_COMPONENTS = [
    MaterialComponent(
        material_name="Lithium",
        mass_kg=0.85,
        percentage=3.40,
        is_critical_raw_material=True,
        expected_yield_loss_pct=25.0,  # 75% BAT recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Iron",
        mass_kg=6.125,
        percentage=24.50,
        is_critical_raw_material=False,
        expected_yield_loss_pct=10.0,  # 90% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Phosphorus",
        mass_kg=3.45,
        percentage=13.80,
        is_critical_raw_material=True,
        expected_yield_loss_pct=20.0,  # 80% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Copper",
        mass_kg=2.375,
        percentage=9.50,
        is_critical_raw_material=True,
        expected_yield_loss_pct=6.0,   # 94% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Aluminum",
        mass_kg=3.75,
        percentage=15.00,
        is_critical_raw_material=False,
        expected_yield_loss_pct=10.0,  # 90% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Anode Graphite",
        mass_kg=4.00,
        percentage=16.00,
        is_critical_raw_material=True,
        expected_yield_loss_pct=15.0,  # 85% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Casing & Inerts",
        mass_kg=4.45,
        percentage=17.80,
        is_critical_raw_material=False,
        expected_yield_loss_pct=100.0, # Process loss
        tolerance_band_pct=10.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
]

EV_BATTERY_LFP_COMPOSITION = MaterialComposition(
    components=LFP_COMPONENTS,
    total_mass_kg=25.0,
)

EV_BATTERY_LFP_DPP = DigitalProductPassport(
    passport_id="dpp-ev-lfp-2026-c22",
    product_id="SKU-EV-LFP-Blade",
    product_name="BladePower LFP Stationary / EV Energy Storage Pack",
    product_category="EV_BATTERY",
    manufacturer="BYD Commercial Energy Systems Co.",
    manufacturing_date=datetime(2026, 2, 20, 11, 0, tzinfo=timezone.utc),
    initial_total_mass_kg=25.0,
    material_composition=EV_BATTERY_LFP_COMPOSITION,
    current_lifecycle_state=LifecycleState.MANUFACTURED,
    created_at=datetime(2026, 2, 20, 11, 30, tzinfo=timezone.utc),
    updated_at=datetime(2026, 2, 20, 11, 30, tzinfo=timezone.utc),
    metadata={
        "chemistry": "LFP (LiFePO4)",
        "cell_topology": "Prismatic Blade",
        "standard_batch_modules": 40,
        "standard_batch_mass_kg": 1000.0,
    },
)

# -------------------------------------------------------------------------
# Dataset 4: Emerging Sodium-Ion Battery (SIB Chemistry — Na-Ion / Prussian Blue)
# -------------------------------------------------------------------------
SODIUM_ION_COMPONENTS = [
    MaterialComponent(
        material_name="Sodium",
        mass_kg=0.90,
        percentage=4.50,
        is_critical_raw_material=False,
        expected_yield_loss_pct=20.0,  # 80% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Iron",
        mass_kg=4.40,
        percentage=22.00,
        is_critical_raw_material=False,
        expected_yield_loss_pct=8.0,   # 92% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Manganese",
        mass_kg=2.40,
        percentage=12.00,
        is_critical_raw_material=True,
        expected_yield_loss_pct=10.0,  # 90% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Aluminum",
        mass_kg=5.00,
        percentage=25.00,  # SIB uses aluminum for both cathode and anode current collectors (0% copper)
        is_critical_raw_material=False,
        expected_yield_loss_pct=6.0,   # 94% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Hard Carbon",
        mass_kg=3.70,
        percentage=18.50,
        is_critical_raw_material=False,
        expected_yield_loss_pct=20.0,  # 80% recovery
        tolerance_band_pct=5.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
    MaterialComponent(
        material_name="Electrolyte & Packaging",
        mass_kg=3.60,
        percentage=18.00,
        is_critical_raw_material=False,
        expected_yield_loss_pct=100.0, # Process loss
        tolerance_band_pct=10.0,
        provenance=ProvenanceCategory.REFERENCE_ASSUMED,
    ),
]

SODIUM_ION_BATTERY_COMPOSITION = MaterialComposition(
    components=SODIUM_ION_COMPONENTS,
    total_mass_kg=20.0,
)

SODIUM_ION_BATTERY_DPP = DigitalProductPassport(
    passport_id="dpp-sib-grid-2026-s05",
    product_id="SKU-SIB-GRID-20KWH",
    product_name="NatriumGrid Sodium-Ion Stationary Battery Module",
    product_category="INDUSTRIAL_BATTERY",
    manufacturer="HiNa Battery Technology Ltd.",
    manufacturing_date=datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
    initial_total_mass_kg=20.0,
    material_composition=SODIUM_ION_BATTERY_COMPOSITION,
    current_lifecycle_state=LifecycleState.MANUFACTURED,
    created_at=datetime(2026, 4, 1, 9, 30, tzinfo=timezone.utc),
    updated_at=datetime(2026, 4, 1, 9, 30, tzinfo=timezone.utc),
    metadata={
        "chemistry": "Sodium-Ion (Na-Fe-Mn Prussian White / Hard Carbon)",
        "critical_raw_material_free": True,
        "standard_batch_units": 50,
        "standard_batch_mass_kg": 1000.0,
    },
)
