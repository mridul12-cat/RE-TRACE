"""
RE:TRACE Canonical Domain Schemas Package.

Exports core Pydantic schemas for Digital Product Passports, Recycling Events,
Material Compositions, Provenance Metadata, Evidence Bundles, and PoR Certificates.
"""

from shared.schemas.provenance import (
    ProvenanceCategory,
    ProvenanceRecord,
)
from shared.schemas.material import (
    MaterialComponent,
    MaterialComposition,
)
from shared.schemas.dpp import (
    DigitalProductPassport,
)
from shared.schemas.recycling_event import (
    ClaimedMaterial,
    RecyclingEvent,
)
from shared.schemas.evidence_bundle import (
    EvidenceFileRecord,
    AIInferenceObservation,
    MassBalanceVerificationResult,
    EvidenceBundle,
)
from shared.schemas.por_certificate import (
    VerifiedMaterialQuantity,
    ProofOfRecyclingCertificate,
)

__all__ = [
    "ProvenanceCategory",
    "ProvenanceRecord",
    "MaterialComponent",
    "MaterialComposition",
    "DigitalProductPassport",
    "ClaimedMaterial",
    "RecyclingEvent",
    "EvidenceFileRecord",
    "AIInferenceObservation",
    "MassBalanceVerificationResult",
    "EvidenceBundle",
    "VerifiedMaterialQuantity",
    "ProofOfRecyclingCertificate",
]
