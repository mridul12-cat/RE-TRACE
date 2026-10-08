"""
RE:TRACE Canonical Lifecycle State Machine Engine.

Governs product lifecycle states, explicit transition guard conditions,
and strict role-based access authorization per ORIGINAL_REQUEST.md:43-45.
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class LifecycleState(str, Enum):
    """
    Seven canonical lifecycle states for a Digital Product Passport.
    """
    MANUFACTURED = "MANUFACTURED"          # Assembled, DPP registered with BoM
    IN_USE = "IN_USE"                      # Active commercial or consumer operation
    RETURNED = "RETURNED"                  # End-of-life return accepted at collection facility
    RECYCLING_PENDING = "RECYCLING_PENDING"# Received at recycler, intake mass recorded, awaiting verification
    RECYCLING_VERIFIED = "RECYCLING_VERIFIED"# Physical evidence, AI, and mass-balance verified & anchored
    MATERIALS_RECOVERED = "MATERIALS_RECOVERED"# Reclaimed secondary materials extracted & PoR cert issued
    FLAGGED = "FLAGGED"                    # Quarantined due to mass discrepancy, tampering, or fraud


class AuthorizedRole(str, Enum):
    """
    Authorized actor roles in the circular economy supply chain.
    """
    MANUFACTURER = "MANUFACTURER"
    LOGISTICS = "LOGISTICS"
    COLLECTION_AGENT = "COLLECTION_AGENT"
    RECYCLER = "RECYCLER"
    VERIFIER_SERVICE = "VERIFIER_SERVICE"
    AUDITOR = "AUDITOR"
    SYSTEM = "SYSTEM"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal lifecycle transition is attempted."""
    def __init__(self, current_state: LifecycleState, target_state: LifecycleState, reason: str):
        super().__init__(f"Illegal transition from '{current_state}' to '{target_state}': {reason}")
        self.current_state = current_state
        self.target_state = target_state
        self.reason = reason


class TransitionValidationResult(BaseModel):
    """Result of a lifecycle state transition validation check."""
    is_valid: bool
    current_state: LifecycleState
    target_state: LifecycleState
    authorized_role: AuthorizedRole
    message: str
    guard_conditions_met: bool = True


# Canonical transition permission map: (current_state, target_state) -> set of allowed roles
ALLOWED_TRANSITIONS: Dict[Tuple[LifecycleState, LifecycleState], Set[AuthorizedRole]] = {
    # Product deployment
    (LifecycleState.MANUFACTURED, LifecycleState.IN_USE): {
        AuthorizedRole.MANUFACTURER,
        AuthorizedRole.LOGISTICS,
        AuthorizedRole.SYSTEM,
    },
    # Collection intake
    (LifecycleState.IN_USE, LifecycleState.RETURNED): {
        AuthorizedRole.COLLECTION_AGENT,
        AuthorizedRole.RECYCLER,
        AuthorizedRole.SYSTEM,
    },
    # Facility intake & batch creation
    (LifecycleState.RETURNED, LifecycleState.RECYCLING_PENDING): {
        AuthorizedRole.RECYCLER,
        AuthorizedRole.SYSTEM,
    },
    # Deterministic verification pass & on-chain anchor
    (LifecycleState.RECYCLING_PENDING, LifecycleState.RECYCLING_VERIFIED): {
        AuthorizedRole.VERIFIER_SERVICE,
        AuthorizedRole.SYSTEM,
    },
    # Fraud / discrepancy quarantine
    (LifecycleState.RECYCLING_PENDING, LifecycleState.FLAGGED): {
        AuthorizedRole.VERIFIER_SERVICE,
        AuthorizedRole.SYSTEM,
        AuthorizedRole.AUDITOR,
    },
    # Post-anchoring evidence tampering / fraud quarantine on verified product (Scenario C)
    (LifecycleState.RECYCLING_VERIFIED, LifecycleState.FLAGGED): {
        AuthorizedRole.VERIFIER_SERVICE,
        AuthorizedRole.AUDITOR,
        AuthorizedRole.SYSTEM,
    },
    # Auditor-only flag resolution (Recycler is strictly prohibited!)
    (LifecycleState.FLAGGED, LifecycleState.RECYCLING_VERIFIED): {
        AuthorizedRole.AUDITOR,
    },
    # Rejection of fraudulent batch back to returned or scrap disposal
    (LifecycleState.FLAGGED, LifecycleState.RETURNED): {
        AuthorizedRole.AUDITOR,
    },
    # Downstream certificate issuance and material handoff
    (LifecycleState.RECYCLING_VERIFIED, LifecycleState.MATERIALS_RECOVERED): {
        AuthorizedRole.RECYCLER,
        AuthorizedRole.VERIFIER_SERVICE,
        AuthorizedRole.SYSTEM,
    },
}


def validate_transition(
    current_state: LifecycleState,
    target_state: LifecycleState,
    role: AuthorizedRole,
    guard_context: Optional[dict] = None,
) -> TransitionValidationResult:
    """
    Validates a requested state transition against the canonical state machine.

    Enforces:
    1. No self-transitions (prevents replay / duplicate execution).
    2. Transition must exist in canonical graph (no illegal skips like MANUFACTURED -> RECYCLING_VERIFIED).
    3. Role must be authorized for this specific edge.
    4. Dedicated guard conditions for sensitive edges:
       - RECYCLING_PENDING -> RECYCLING_VERIFIED requires mass_balance == 'VALID' and commitment.
       - FLAGGED -> RECYCLING_VERIFIED strictly requires role == AUDITOR and documented resolution notes.
    """
    # 1. Reject self-transition (anti-replay)
    if current_state == target_state:
        msg = f"Replay prevented: current state is already '{current_state}'"
        return TransitionValidationResult(
            is_valid=False,
            current_state=current_state,
            target_state=target_state,
            authorized_role=role,
            message=msg,
            guard_conditions_met=False,
        )

    # 2. Check transition graph
    key = (current_state, target_state)
    if key not in ALLOWED_TRANSITIONS:
        msg = f"Path forbidden: no transition permitted from '{current_state}' to '{target_state}'"
        return TransitionValidationResult(
            is_valid=False,
            current_state=current_state,
            target_state=target_state,
            authorized_role=role,
            message=msg,
            guard_conditions_met=False,
        )

    # 3. Check role authorization
    allowed_roles = ALLOWED_TRANSITIONS[key]
    if role not in allowed_roles:
        msg = (
            f"Unauthorized actor: role '{role}' is not authorized to transition "
            f"from '{current_state}' to '{target_state}'. Required: {[r.value for r in allowed_roles]}"
        )
        return TransitionValidationResult(
            is_valid=False,
            current_state=current_state,
            target_state=target_state,
            authorized_role=role,
            message=msg,
            guard_conditions_met=False,
        )

    # 4. Check edge-specific guard conditions
    guard_context = guard_context or {}

    if (current_state, target_state) == (LifecycleState.RECYCLING_PENDING, LifecycleState.RECYCLING_VERIFIED):
        decision = guard_context.get("mass_balance_decision")
        commitment = guard_context.get("evidence_commitment")
        if decision != "VALID":
            msg = f"Guard failed: mass balance decision must be 'VALID' (got '{decision}')"
            return TransitionValidationResult(
                is_valid=False,
                current_state=current_state,
                target_state=target_state,
                authorized_role=role,
                message=msg,
                guard_conditions_met=False,
            )
        if not commitment:
            msg = "Guard failed: evidence cryptographic commitment is missing"
            return TransitionValidationResult(
                is_valid=False,
                current_state=current_state,
                target_state=target_state,
                authorized_role=role,
                message=msg,
                guard_conditions_met=False,
            )

    if (current_state, target_state) == (LifecycleState.FLAGGED, LifecycleState.RECYCLING_VERIFIED):
        resolution_notes = guard_context.get("auditor_resolution_notes")
        if not resolution_notes or len(resolution_notes.strip()) < 10:
            msg = "Guard failed: formal auditor resolution notes (min 10 chars) required to unflag"
            return TransitionValidationResult(
                is_valid=False,
                current_state=current_state,
                target_state=target_state,
                authorized_role=role,
                message=msg,
                guard_conditions_met=False,
            )

    if (current_state, target_state) == (LifecycleState.RECYCLING_VERIFIED, LifecycleState.FLAGGED):
        flag_reason = guard_context.get("flag_reason")
        if flag_reason is not None and not str(flag_reason).strip():
            msg = "Guard failed: quarantine flag_reason must not be empty if provided"
            return TransitionValidationResult(
                is_valid=False,
                current_state=current_state,
                target_state=target_state,
                authorized_role=role,
                message=msg,
                guard_conditions_met=False,
            )

    return TransitionValidationResult(
        is_valid=True,
        current_state=current_state,
        target_state=target_state,
        authorized_role=role,
        message=f"Transition from '{current_state}' to '{target_state}' authorized by '{role}'",
        guard_conditions_met=True,
    )


def assert_valid_transition(
    current_state: LifecycleState,
    target_state: LifecycleState,
    role: AuthorizedRole,
    guard_context: Optional[dict] = None,
):
    """
    Executes validate_transition and raises InvalidStateTransitionError if invalid.
    """
    res = validate_transition(current_state, target_state, role, guard_context)
    if not res.is_valid:
        raise InvalidStateTransitionError(current_state, target_state, res.message)
