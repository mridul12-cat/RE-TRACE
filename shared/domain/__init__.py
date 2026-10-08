"""
RE:TRACE Canonical Domain Logic Package.

Exports lifecycle state machine, deterministic mass-balance verification engine,
and cryptographic evidence hashing/commitment utilities.
"""

from shared.domain.lifecycle import (
    LifecycleState,
    AuthorizedRole,
    TransitionValidationResult,
    InvalidStateTransitionError,
    ALLOWED_TRANSITIONS,
    validate_transition,
    assert_valid_transition,
)
from shared.domain.mass_balance import (
    MassBalanceOutcome,
    evaluate_mass_balance,
)
from shared.domain.evidence_hasher import (
    keccak256_bytes,
    keccak256,
    hash_bytes_sha256,
    hash_file_sha256,
    canonicalize_json,
    compute_evidence_bundle_commitment,
)

__all__ = [
    "LifecycleState",
    "AuthorizedRole",
    "TransitionValidationResult",
    "InvalidStateTransitionError",
    "ALLOWED_TRANSITIONS",
    "validate_transition",
    "assert_valid_transition",
    "MassBalanceOutcome",
    "evaluate_mass_balance",
    "keccak256_bytes",
    "keccak256",
    "hash_bytes_sha256",
    "hash_file_sha256",
    "canonicalize_json",
    "compute_evidence_bundle_commitment",
]
