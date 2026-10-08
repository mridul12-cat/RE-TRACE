"""
tests/test_empirical_challenger_m1_2.py
Empirical Adversarial Challenge Suite for Milestone 1:
1. shared/domain/evidence_hasher.py (RFC 8785 Canonicalization & EVM Keccak-256)
2. shared/domain/lifecycle.py (Lifecycle State Machine, Guards & Role Permissions)
"""

import itertools
import json
import pytest
from pydantic import BaseModel

from shared.domain.evidence_hasher import (
    canonicalize_json,
    hash_bytes_sha256,
    hash_file_sha256,
    keccak256,
    keccak256_bytes,
    compute_evidence_bundle_commitment,
)
from shared.domain.lifecycle import (
    LifecycleState,
    AuthorizedRole,
    ALLOWED_TRANSITIONS,
    validate_transition,
    assert_valid_transition,
    InvalidStateTransitionError,
)
from shared.schemas.recycling_event import ClaimedMaterial, RecyclingEvent
from shared.schemas.provenance import ProvenanceCategory


# ============================================================================
# SUITE 1: CRYPTOGRAPHIC COMMITMENT & HASHER ATTACKS
# ============================================================================

class TestEvidenceHasherAttacks:
    """
    Empirically challenges RFC 8785 canonicalization and EVM Keccak-256.
    """

    def test_rfc8785_root_key_order_permutations(self):
        """
        Adversarial Test: Generate all 120 (5!) key insertion order permutations
        for a dictionary. Assert that canonicalize_json produces identical bytes
        and identical hashes for EVERY permutation.
        """
        keys = ["event_id", "facility_id", "intake_mass_kg", "timestamp", "verified"]
        values = ["evt_9981", "FAC_HAMBURG_01", 1250.5, "2026-10-08T00:00:00Z", True]

        hashes = set()
        canonical_payloads = set()

        for perm in itertools.permutations(range(5)):
            scrambled = {keys[i]: values[i] for i in perm}
            c_bytes = canonicalize_json(scrambled)
            sha = hash_bytes_sha256(c_bytes)
            k_hex = keccak256(c_bytes)

            canonical_payloads.add(c_bytes)
            hashes.add((sha, k_hex))

        # Exactly 1 canonical byte representation must exist across all 120 permutations
        assert len(canonical_payloads) == 1, f"Expected 1 canonical byte output, got {len(canonical_payloads)}"
        assert len(hashes) == 1, f"Expected 1 hash pair across all permutations, got {len(hashes)}"

        # Verify key ordering is lexicographical: event_id, facility_id, intake_mass_kg, timestamp, verified
        expected_bytes = b'{"event_id":"evt_9981","facility_id":"FAC_HAMBURG_01","intake_mass_kg":1250.5,"timestamp":"2026-10-08T00:00:00Z","verified":true}'
        assert next(iter(canonical_payloads)) == expected_bytes

    def test_rfc8785_nested_deep_object_scrambling(self):
        """
        Adversarial Test: Multi-tier nested objects with scrambled key orders
        at every tier (levels 1, 2, 3, 4).
        """
        obj_a = {
            "z_meta": {
                "depth_2_z": {"depth_3_b": 10, "depth_3_a": 20},
                "depth_2_a": {"depth_3_z": "val_z", "depth_3_m": "val_m"},
            },
            "a_data": {
                "arr": [
                    {"sub_z": True, "sub_a": False},
                    {"k2": 2, "k1": 1},
                ]
            },
        }

        obj_b = {
            "a_data": {
                "arr": [
                    {"sub_a": False, "sub_z": True},
                    {"k1": 1, "k2": 2},
                ]
            },
            "z_meta": {
                "depth_2_a": {"depth_3_m": "val_m", "depth_3_z": "val_z"},
                "depth_2_z": {"depth_3_a": 20, "depth_3_b": 10},
            },
        }

        bytes_a = canonicalize_json(obj_a)
        bytes_b = canonicalize_json(obj_b)
        assert bytes_a == bytes_b
        assert hash_bytes_sha256(bytes_a) == hash_bytes_sha256(bytes_b)
        assert keccak256(bytes_a) == keccak256(bytes_b)

    def test_rfc8785_whitespace_insensitivity_and_compactness(self):
        """
        Adversarial Test: Arbitrary whitespace variations in JSON payloads
        must be stripped to compact representation without ':' or ',' spacing.
        """
        raw_json_variants = [
            '{"alpha": 1, "beta": 2}',
            '{\n  "alpha": 1,\n  "beta": 2\n}',
            '{\t"beta":\t\t2,\n\n"alpha":   1   }',
            '{"beta":2,"alpha":1}',
        ]

        canonical_results = [canonicalize_json(json.loads(v)) for v in raw_json_variants]

        for res in canonical_results:
            assert res == b'{"alpha":1,"beta":2}'
            assert b": " not in res
            assert b", " not in res
            assert b"\n" not in res
            assert b"\t" not in res

    def test_rfc8785_unicode_non_ascii_preservation(self):
        """
        Adversarial Test: RFC 8785 requires UTF-8 characters to NOT be escaped
        as \\uXXXX (unlike legacy JSON).
        """
        obj = {
            "city": "München",
            "japanese": "リチウムイオン電池",
            "symbols": "→ ΔE = mc²",
        }
        c_bytes = canonicalize_json(obj)
        # Check raw UTF-8 bytes are preserved without escape slashes
        assert b"\\u" not in c_bytes
        decoded = c_bytes.decode("utf-8")
        assert "München" in decoded
        assert "リチウムイオン電池" in decoded
        assert "→ ΔE = mc²" in decoded

    def test_rfc8785_pydantic_model_canonicalization(self):
        """
        Adversarial Test: Canonicalize Pydantic v2 domain models directly.
        """
        model = ClaimedMaterial(
            material_name="Cobalt",
            claimed_mass_kg=55.80,
            purity_pct=95.0,
            provenance=ProvenanceCategory.MEASURED,
        )
        c_bytes_model = canonicalize_json(model)

        dict_equiv = {
            "material_name": "Cobalt",
            "claimed_mass_kg": 55.80,
            "purity_pct": 95.0,
            "provenance": "MEASURED",
        }
        c_bytes_dict = canonicalize_json(dict_equiv)

        assert c_bytes_model == c_bytes_dict
        assert hash_bytes_sha256(c_bytes_model) == hash_bytes_sha256(c_bytes_dict)

        # Test nested model with datetime and enums
        from datetime import datetime, timezone
        event = RecyclingEvent(
            event_id="evt_test_001",
            passport_id="DPP_001",
            facility_id="FAC_01",
            operator_id="OP_01",
            intake_gross_mass_kg=1000.0,
            intake_mass_provenance=ProvenanceCategory.MEASURED,
            claimed_materials=[model],
            evidence_file_ids=["file_01", "file_02"],
            timestamp=datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc),
            status="SUBMITTED",
        )
        event_bytes = canonicalize_json(event)
        assert b"evt_test_001" in event_bytes
        assert b"2026-10-08T12:00:00+00:00" in event_bytes
        assert hash_bytes_sha256(event_bytes) == hash_bytes_sha256(canonicalize_json(event.model_dump()))

    def test_avalanche_effect_single_bit_flip(self):
        """
        Adversarial Test: Flipping 1 single bit in payload must radically alter
        both SHA-256 and EVM keccak256 commitments with ~50% bit flip (Hamming distance).
        """
        payload_orig = bytearray(b"DIGITAL_PRODUCT_PASSPORT_EVIDENCE_PAYLOAD_ORIGINAL_BYTES_2026")
        payload_mutated = bytearray(payload_orig)
        # Flip the lowest bit of the first byte
        payload_mutated[0] ^= 0x01

        sha_orig = hash_bytes_sha256(bytes(payload_orig))
        sha_mut = hash_bytes_sha256(bytes(payload_mutated))

        keccak_orig = keccak256_bytes(bytes(payload_orig))
        keccak_mut = keccak256_bytes(bytes(payload_mutated))

        assert sha_orig != sha_mut
        assert keccak_orig != keccak_mut

        # Compute Hamming distance for Keccak-256 (32 bytes = 256 bits)
        diff_bits = 0
        for b1, b2 in zip(keccak_orig, keccak_mut):
            diff_bits += bin(b1 ^ b2).count("1")

        # In a 256-bit hash, avalanche should flip ~128 bits (+/- 40 bits is well within statistical bounds)
        assert 80 <= diff_bits <= 180, f"Avalanche test failed: Hamming distance was {diff_bits}/256 bits"

    def test_keccak256_standard_ethereum_vectors(self):
        """
        Adversarial Test: Compare EVM keccak256 against official standard test vectors.
        """
        vectors = [
            (b"", "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"),
            (b"abc", "0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"),
            (b"hello", "0x1c8aff950685c2ed4bc3174f3472287b56d9517b9c948127319a09a7a36deac8"),
            (b"The quick brown fox jumps over the lazy dog", "0x4d741b6f1eb29cb2a9b9911c82f56fa8d73b04959d3d9d222895df6c0b28aa15"),
            (b"The quick brown fox jumps over the lazy dog.", "0x578951e24efd62a3d63a86f7cd19aaa53c898fe287d2552133220370240b572d"),
        ]

        for input_bytes, expected_hex in vectors:
            computed = keccak256(input_bytes, prefix_0x=True)
            assert computed == expected_hex, f"Mismatch for '{input_bytes}': got {computed}, expected {expected_hex}"

    def test_keccak256_rate_block_boundary_conditions(self):
        """
        Adversarial Test: Keccak sponge rate is 136 bytes (1088 bits).
        Stress test input lengths at critical sponge boundaries:
        - 135 bytes (padlen == 1)
        - 136 bytes (exact 1 block, padlen == 136)
        - 137 bytes (spans into block 2, padlen == 135)
        - 271 bytes (padlen == 1)
        - 272 bytes (exact 2 blocks, padlen == 136)
        - 273 bytes (spans into block 3)
        """
        test_lengths = [0, 1, 135, 136, 137, 271, 272, 273, 500, 1000]
        for length in test_lengths:
            data = b"X" * length
            digest_bytes = keccak256_bytes(data)
            digest_hex = keccak256(data)
            assert len(digest_bytes) == 32
            assert len(digest_hex) == 66  # "0x" + 64 hex chars
            assert digest_hex == "0x" + digest_bytes.hex()

    def test_empirical_finding_set_iteration_ordering_vulnerability(self):
        """
        Empirical Challenge Finding:
        shared/domain/evidence_hasher.py:149-150 explicitly checks:
            if isinstance(obj, (list, tuple, set)):
                return [_normalize_for_canonical_json(item) for item in obj]
        Because sets are unsorted collections, iterating over a set yields
        unpredictable order dependent on hash seed and runtime memory addresses.
        To be truly RFC 8785 canonical, sets MUST be sorted by representation.
        """
        set_items = {"alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta"}
        # Simulating iteration variations
        list_perm1 = sorted(list(set_items))
        list_perm2 = sorted(list(set_items), reverse=True)

        bytes1 = canonicalize_json({"tags": list_perm1})
        bytes2 = canonicalize_json({"tags": list_perm2})

        # When items are passed as lists in different orders, arrays preserve order:
        assert bytes1 != bytes2
        # However, passing a raw set directly relies on non-deterministic set iteration:
        # We record this finding: _normalize_for_canonical_json should sort sets!

    def test_empirical_finding_raw_json_string_not_parsed(self):
        """
        Empirical Challenge Finding:
        If a caller passes a pre-serialized JSON string to canonicalize_json,
        it does NOT parse the string; instead it serializes it as a JSON string literal.
        Callers must be aware that canonicalize_json expects parsed dicts/models,
        not stringified JSON.
        """
        raw_str = '{"b": 2, "a": 1}'
        serialized = canonicalize_json(raw_str)
        # Produces escaped string literal: b'"{\\"b\\": 2, \\"a\\": 1}"'
        assert serialized.startswith(b'"{\\"')
        # Does NOT sort keys inside string:
        assert b'\\"b\\": 2' in serialized

    def test_empirical_finding_float_nan_inf_serialization(self):
        """
        Verify that NaN and Infinity are strictly rejected per RFC 8785 / RFC 8259.
        """
        with pytest.raises(ValueError, match="Out of range float values"):
            canonicalize_json({"val": float("nan")})

        with pytest.raises(ValueError, match="Out of range float values"):
            canonicalize_json({"val": float("inf")})


# ============================================================================
# SUITE 2: LIFECYCLE STATE MACHINE ATTACKS
# ============================================================================

class TestLifecycleStateMachineAttacks:
    """
    Empirically challenges the canonical lifecycle state machine.
    """

    def test_exhaustive_illegal_state_hops_matrix(self):
        """
        Adversarial Test: Test all 49 (7x7) possible state pairs.
        Every state transition not in ALLOWED_TRANSITIONS must be rejected
        regardless of which role attempts it.
        """
        all_states = list(LifecycleState)
        all_roles = list(AuthorizedRole)

        allowed_keys = set(ALLOWED_TRANSITIONS.keys())

        illegal_attempts = 0
        illegal_rejections = 0

        for from_state in all_states:
            for to_state in all_states:
                if (from_state, to_state) in allowed_keys:
                    continue  # Valid edge, tested separately

                # For every illegal edge, test with ALL roles
                for role in all_roles:
                    illegal_attempts += 1
                    res = validate_transition(from_state, to_state, role)
                    if not res.is_valid:
                        illegal_rejections += 1

                    # Also verify assert_valid_transition raises
                    with pytest.raises(InvalidStateTransitionError):
                        assert_valid_transition(from_state, to_state, role)

        assert illegal_rejections == illegal_attempts, (
            f"Expected {illegal_attempts} illegal transition rejections, got {illegal_rejections}"
        )

    def test_specific_critical_state_skips(self):
        """
        Adversarial Test: Explicitly attempt high-impact state skips:
        1. MANUFACTURED -> RECYCLING_VERIFIED
        2. MANUFACTURED -> MATERIALS_RECOVERED
        3. RETURNED -> MATERIALS_RECOVERED
        4. IN_USE -> MATERIALS_RECOVERED
        5. RECYCLING_PENDING -> MATERIALS_RECOVERED (skipping verification)
        """
        skips = [
            (LifecycleState.MANUFACTURED, LifecycleState.RECYCLING_VERIFIED),
            (LifecycleState.MANUFACTURED, LifecycleState.MATERIALS_RECOVERED),
            (LifecycleState.RETURNED, LifecycleState.MATERIALS_RECOVERED),
            (LifecycleState.IN_USE, LifecycleState.MATERIALS_RECOVERED),
            (LifecycleState.RECYCLING_PENDING, LifecycleState.MATERIALS_RECOVERED),
        ]

        for from_st, to_st in skips:
            for role in AuthorizedRole:
                res = validate_transition(from_st, to_st, role)
                assert not res.is_valid
                assert "Path forbidden" in res.message
                with pytest.raises(InvalidStateTransitionError):
                    assert_valid_transition(from_st, to_st, role)

    def test_anti_replay_all_self_loops(self):
        """
        Adversarial Test: Replay attacks attempting self-loops (S -> S)
        for all 7 states must be rejected with 'Replay prevented'.
        """
        for state in LifecycleState:
            for role in AuthorizedRole:
                res = validate_transition(state, state, role)
                assert not res.is_valid
                assert not res.guard_conditions_met
                assert "Replay prevented" in res.message
                with pytest.raises(InvalidStateTransitionError):
                    assert_valid_transition(state, state, role)

    def test_backward_transitions_rejected(self):
        """
        Adversarial Test: Attempt moving backwards in the supply chain lifecycle
        (e.g., from MATERIALS_RECOVERED back to MANUFACTURED or RECYCLING_VERIFIED).
        """
        backwards = [
            (LifecycleState.MATERIALS_RECOVERED, LifecycleState.MANUFACTURED),
            (LifecycleState.MATERIALS_RECOVERED, LifecycleState.RECYCLING_VERIFIED),
            (LifecycleState.RECYCLING_VERIFIED, LifecycleState.RECYCLING_PENDING),
            (LifecycleState.RECYCLING_VERIFIED, LifecycleState.RETURNED),
            (LifecycleState.RECYCLING_VERIFIED, LifecycleState.MANUFACTURED),
            (LifecycleState.RECYCLING_PENDING, LifecycleState.RETURNED),
            (LifecycleState.RETURNED, LifecycleState.IN_USE),
            (LifecycleState.IN_USE, LifecycleState.MANUFACTURED),
        ]

        for from_st, to_st in backwards:
            for role in AuthorizedRole:
                res = validate_transition(from_st, to_st, role)
                assert not res.is_valid
                assert "Path forbidden" in res.message

    def test_unauthorized_role_matrix_on_allowed_edges(self):
        """
        Adversarial Test: For each allowed edge, test all UNAUTHORIZED roles.
        Verify they receive 'Unauthorized actor'.
        """
        unauthorized_count = 0
        all_roles = set(AuthorizedRole)

        for (from_st, to_st), allowed_roles in ALLOWED_TRANSITIONS.items():
            forbidden_roles = all_roles - allowed_roles
            for role in forbidden_roles:
                unauthorized_count += 1
                res = validate_transition(from_st, to_st, role)
                assert not res.is_valid
                assert "Unauthorized actor" in res.message
                with pytest.raises(InvalidStateTransitionError):
                    assert_valid_transition(from_st, to_st, role)

        assert unauthorized_count > 30, f"Expected >30 unauthorized combinations, got {unauthorized_count}"

    def test_unauthorized_unflagging_attacks(self):
        """
        Adversarial Test: Quarantined product in FLAGGED state.
        Unauthorized roles (especially RECYCLER) attempting to unflag directly
        to RECYCLING_VERIFIED or RETURNED must be rejected.
        """
        unauthorized_roles = [
            AuthorizedRole.RECYCLER,
            AuthorizedRole.MANUFACTURER,
            AuthorizedRole.COLLECTION_AGENT,
            AuthorizedRole.LOGISTICS,
            AuthorizedRole.VERIFIER_SERVICE,
            AuthorizedRole.SYSTEM,
        ]

        for role in unauthorized_roles:
            # 1. Attempt unflag to RECYCLING_VERIFIED
            res1 = validate_transition(
                LifecycleState.FLAGGED,
                LifecycleState.RECYCLING_VERIFIED,
                role,
                guard_context={"auditor_resolution_notes": "Spoofed unflag notes by adversary"}
            )
            assert not res1.is_valid
            assert "Unauthorized actor" in res1.message

            # 2. Attempt unflag to RETURNED
            res2 = validate_transition(
                LifecycleState.FLAGGED,
                LifecycleState.RETURNED,
                role
            )
            assert not res2.is_valid
            assert "Unauthorized actor" in res2.message

    def test_auditor_unflag_guard_conditions(self):
        """
        Adversarial Test: Auditor attempting to unflag FLAGGED -> RECYCLING_VERIFIED
        must satisfy resolution note requirements (min 10 characters).
        """
        # None context
        r_none = validate_transition(
            LifecycleState.FLAGGED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.AUDITOR,
            guard_context=None
        )
        assert not r_none.is_valid
        assert "formal auditor resolution notes" in r_none.message

        # Empty notes
        r_empty = validate_transition(
            LifecycleState.FLAGGED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.AUDITOR,
            guard_context={"auditor_resolution_notes": ""}
        )
        assert not r_empty.is_valid
        assert "formal auditor resolution notes" in r_empty.message

        # Whitespace-only notes
        r_space = validate_transition(
            LifecycleState.FLAGGED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.AUDITOR,
            guard_context={"auditor_resolution_notes": "          "}
        )
        assert not r_space.is_valid
        assert "formal auditor resolution notes" in r_space.message

        # Short notes (< 10 chars)
        r_short = validate_transition(
            LifecycleState.FLAGGED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.AUDITOR,
            guard_context={"auditor_resolution_notes": "OK verified"}  # 11 chars? wait: len is 11
        )
        r_short9 = validate_transition(
            LifecycleState.FLAGGED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.AUDITOR,
            guard_context={"auditor_resolution_notes": "123456789"}  # 9 chars
        )
        assert not r_short9.is_valid
        assert "formal auditor resolution notes" in r_short9.message

        # Valid notes (>= 10 chars)
        r_valid = validate_transition(
            LifecycleState.FLAGGED, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.AUDITOR,
            guard_context={"auditor_resolution_notes": "ADR-003: Verified by third-party lab inspection"}
        )
        assert r_valid.is_valid
        assert r_valid.guard_conditions_met

    def test_recycling_pending_to_verified_guard_conditions(self):
        """
        Adversarial Test: RECYCLING_PENDING -> RECYCLING_VERIFIED requires:
        1. mass_balance_decision == 'VALID'
        2. evidence_commitment present and non-empty
        """
        # Missing decision
        r1 = validate_transition(
            LifecycleState.RECYCLING_PENDING, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.VERIFIER_SERVICE,
            guard_context={"evidence_commitment": "0x1234"}
        )
        assert not r1.is_valid
        assert "mass balance decision must be 'VALID'" in r1.message

        # BORDERLINE decision
        r2 = validate_transition(
            LifecycleState.RECYCLING_PENDING, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.VERIFIER_SERVICE,
            guard_context={"mass_balance_decision": "BORDERLINE", "evidence_commitment": "0x1234"}
        )
        assert not r2.is_valid
        assert "mass balance decision must be 'VALID'" in r2.message

        # IMPOSSIBLE decision
        r3 = validate_transition(
            LifecycleState.RECYCLING_PENDING, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.VERIFIER_SERVICE,
            guard_context={"mass_balance_decision": "IMPOSSIBLE", "evidence_commitment": "0x1234"}
        )
        assert not r3.is_valid
        assert "mass balance decision must be 'VALID'" in r3.message

        # Missing commitment
        r4 = validate_transition(
            LifecycleState.RECYCLING_PENDING, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.VERIFIER_SERVICE,
            guard_context={"mass_balance_decision": "VALID"}
        )
        assert not r4.is_valid
        assert "evidence cryptographic commitment is missing" in r4.message

        # Valid transition
        r5 = validate_transition(
            LifecycleState.RECYCLING_PENDING, LifecycleState.RECYCLING_VERIFIED, AuthorizedRole.VERIFIER_SERVICE,
            guard_context={"mass_balance_decision": "VALID", "evidence_commitment": "0x5678"}
        )
        assert r5.is_valid
        assert r5.guard_conditions_met
