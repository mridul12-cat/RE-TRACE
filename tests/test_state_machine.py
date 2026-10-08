"""
Unit tests for RE:TRACE Lifecycle State Machine Engine.
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

from shared.domain.lifecycle import (
    LifecycleState,
    AuthorizedRole,
    validate_transition,
    assert_valid_transition,
    InvalidStateTransitionError,
)


class TestLifecycleStateMachine(unittest.TestCase):
    """Tier 1 Unit tests for RE:TRACE Lifecycle State Machine Engine."""

    def test_valid_lifecycle_pipeline(self):
        """Tests the canonical linear lifecycle progression."""
        # 1. MANUFACTURED -> IN_USE
        r1 = validate_transition(LifecycleState.MANUFACTURED, LifecycleState.IN_USE, AuthorizedRole.LOGISTICS)
        self.assertTrue(r1.is_valid)

        # 2. IN_USE -> RETURNED
        r2 = validate_transition(LifecycleState.IN_USE, LifecycleState.RETURNED, AuthorizedRole.COLLECTION_AGENT)
        self.assertTrue(r2.is_valid)

        # 3. RETURNED -> RECYCLING_PENDING
        r3 = validate_transition(LifecycleState.RETURNED, LifecycleState.RECYCLING_PENDING, AuthorizedRole.RECYCLER)
        self.assertTrue(r3.is_valid)

        # 4. RECYCLING_PENDING -> RECYCLING_VERIFIED
        r4 = validate_transition(
            LifecycleState.RECYCLING_PENDING,
            LifecycleState.RECYCLING_VERIFIED,
            AuthorizedRole.VERIFIER_SERVICE,
            guard_context={"mass_balance_decision": "VALID", "evidence_commitment": "0x1234"},
        )
        self.assertTrue(r4.is_valid)

        # 5. RECYCLING_VERIFIED -> MATERIALS_RECOVERED
        r5 = validate_transition(
            LifecycleState.RECYCLING_VERIFIED, LifecycleState.MATERIALS_RECOVERED, AuthorizedRole.RECYCLER
        )
        self.assertTrue(r5.is_valid)

    def test_illegal_state_skips(self):
        """Skipping intermediate steps is prohibited."""
        # Skipping from MANUFACTURED directly to RECYCLING_VERIFIED
        r = validate_transition(
            LifecycleState.MANUFACTURED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.SYSTEM
        )
        self.assertFalse(r.is_valid)
        self.assertIn("Path forbidden", r.message)

        with self.assertRaises(InvalidStateTransitionError):
            assert_valid_transition(
                LifecycleState.MANUFACTURED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.SYSTEM
            )

    def test_anti_replay_self_loop(self):
        """Transitioning to the identical current state must be rejected."""
        r = validate_transition(
            LifecycleState.RECYCLING_VERIFIED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.SYSTEM
        )
        self.assertFalse(r.is_valid)
        self.assertIn("Replay prevented", r.message)

    def test_unauthorized_role_rejected(self):
        """An unauthorized actor cannot execute a transition."""
        # RECYCLER cannot trigger MANUFACTURED -> IN_USE
        r = validate_transition(LifecycleState.MANUFACTURED, LifecycleState.IN_USE, AuthorizedRole.RECYCLER)
        self.assertFalse(r.is_valid)
        self.assertIn("Unauthorized actor", r.message)

    def test_flagged_quarantine_and_auditor_resolution(self):
        """Quarantined products in FLAGGED can only be unflagged by AUDITOR."""
        # 1. Trigger quarantine
        r_flag = validate_transition(
            LifecycleState.RECYCLING_PENDING, LifecycleState.FLAGGED, AuthorizedRole.VERIFIER_SERVICE
        )
        self.assertTrue(r_flag.is_valid)

        # 2. Recycler attempts unflagging -> BLOCKED
        r_unflag_recycler = validate_transition(
            LifecycleState.FLAGGED,
            LifecycleState.RECYCLING_VERIFIED,
            AuthorizedRole.RECYCLER,
            guard_context={"auditor_resolution_notes": "Recycler manual override attempt."},
        )
        self.assertFalse(r_unflag_recycler.is_valid)
        self.assertIn("Unauthorized actor", r_unflag_recycler.message)

        # 3. Auditor unflags with missing notes -> BLOCKED
        r_unflag_no_notes = validate_transition(
            LifecycleState.FLAGGED,
            LifecycleState.RECYCLING_VERIFIED,
            AuthorizedRole.AUDITOR,
            guard_context={"auditor_resolution_notes": ""},
        )
        self.assertFalse(r_unflag_no_notes.is_valid)
        self.assertIn("formal auditor resolution notes", r_unflag_no_notes.message)

        # 4. Auditor unflags with valid notes -> PASSED
        r_unflag_valid = validate_transition(
            LifecycleState.FLAGGED,
            LifecycleState.RECYCLING_VERIFIED,
            AuthorizedRole.AUDITOR,
            guard_context={"auditor_resolution_notes": "ADR-002: Independent lab assays confirmed battery grade purity."},
        )
        self.assertTrue(r_unflag_valid.is_valid)


if __name__ == "__main__":
    unittest.main()
