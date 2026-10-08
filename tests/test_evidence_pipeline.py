"""
Unit tests for RE:TRACE Evidence Commitment Pipeline & Hasher.
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

from shared.domain.evidence_hasher import (
    canonicalize_json,
    hash_bytes_sha256,
    keccak256,
    compute_evidence_bundle_commitment,
)


class TestEvidencePipeline(unittest.TestCase):
    """Tier 1 Unit tests for RFC 8785 Canonical Hasher & EVM Keccak-256."""

    def test_keccak256_known_vectors(self):
        """Verify EVM Keccak-256 implementation against Ethereum standard vectors."""
        # Empty string
        empty_digest = keccak256(b"", prefix_0x=True)
        self.assertEqual(empty_digest, "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")

        # Known string
        data = b"RETRACE"
        digest = keccak256(data, prefix_0x=False)
        self.assertEqual(len(digest), 64)

    def test_canonicalize_json_key_sorting(self):
        """Keys must be sorted lexicographically per RFC 8785."""
        obj1 = {"z": 1, "a": 2, "m": {"b": 3, "a": 4}}
        obj2 = {"a": 2, "m": {"a": 4, "b": 3}, "z": 1}

        bytes1 = canonicalize_json(obj1)
        bytes2 = canonicalize_json(obj2)

        self.assertEqual(bytes1, bytes2)
        self.assertEqual(bytes1, b'{"a":2,"m":{"a":4,"b":3},"z":1}')

    def test_sha256_hashing(self):
        """Validates standard SHA-256 digest calculation."""
        data = b"hello circular economy"
        h = hash_bytes_sha256(data)
        self.assertEqual(len(h), 64)
        self.assertTrue(h.isalnum())

    def test_evidence_bundle_commitment_tampering(self):
        """Mutating any field in the manifest must produce a different commitment."""
        manifest_orig = {
            "event_id": "evt-001",
            "intake_mass_kg": 1000.0,
            "evidence_hashes": ["abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"],
        }
        sha_orig, keccak_orig = compute_evidence_bundle_commitment(manifest_orig)

        # Tampered manifest (1 digit changed in intake mass)
        manifest_tampered = {
            "event_id": "evt-001",
            "intake_mass_kg": 1000.1,
            "evidence_hashes": ["abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"],
        }
        sha_tamp, keccak_tamp = compute_evidence_bundle_commitment(manifest_tampered)

        self.assertNotEqual(sha_orig, sha_tamp)
        self.assertNotEqual(keccak_orig, keccak_tamp)


if __name__ == "__main__":
    unittest.main()
