"""
test_evidence_commitment.py — Tier 1 Cryptographic Evidence Integrity & Commitment Tests
Verifies the canonical evidence commitment pipeline:
Raw Evidence Files -> SHA-256 -> RFC 8785 Canonical Manifest -> Bundle SHA-256 -> EVM keccak256 Commitment.
Satisfies Section R2 and R5 in ORIGINAL_REQUEST.md.
"""

import unittest
import json
import hashlib
from tests.conftest import (
    sha256_hex,
    keccak256_bytes,
    keccak256_hex,
    canonical_json_bytes
)


class TestEvidenceCommitmentPipeline(unittest.TestCase):
    """
    Tier 1 tests for cryptographic integrity, RFC 8785 canonicalization,
    SHA-256 hashing, and Ethereum Keccak-256 commitments.
    """

    # ------------------------------------------------------------------------
    # 1. Individual Evidence File Hashing
    # ------------------------------------------------------------------------
    def test_individual_file_sha256_known_vectors(self):
        """Verify SHA-256 computation against known standard test vectors."""
        self.assertEqual(
            sha256_hex(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        self.assertEqual(
            sha256_hex(b"RE:TRACE_PHYSICAL_EVIDENCE_SAMPLE"),
            hashlib.sha256(b"RE:TRACE_PHYSICAL_EVIDENCE_SAMPLE").hexdigest()
        )

    def test_streaming_hash_matches_oneshot(self):
        """Simulate chunked streaming upload (e.g. 25MB multipart) and verify exact hash."""
        chunk1 = b"IMAGE_HEADER_EXIF_DATA" * 50
        chunk2 = b"PIXEL_DATA_PAYLOAD_BYTES" * 100
        full_data = chunk1 + chunk2

        hasher = hashlib.sha256()
        hasher.update(chunk1)
        hasher.update(chunk2)

        self.assertEqual(hasher.hexdigest(), sha256_hex(full_data))

    # ------------------------------------------------------------------------
    # 2. RFC 8785 JSON Canonicalization Scheme (JCS) Determinism
    # ------------------------------------------------------------------------
    def test_rfc8785_lexicographical_key_sorting(self):
        """Verify keys are sorted strictly lexicographically regardless of insertion order."""
        dict_a = {"zebra": 1, "alpha": 2, "gamma": 3}
        dict_b = {"alpha": 2, "gamma": 3, "zebra": 1}
        dict_c = {"gamma": 3, "zebra": 1, "alpha": 2}

        bytes_a = canonical_json_bytes(dict_a)
        bytes_b = canonical_json_bytes(dict_b)
        bytes_c = canonical_json_bytes(dict_c)

        self.assertEqual(bytes_a, bytes_b)
        self.assertEqual(bytes_b, bytes_c)
        self.assertEqual(bytes_a, b'{"alpha":2,"gamma":3,"zebra":1}')

    def test_rfc8785_nested_structures_sorting(self):
        """Verify nested dictionaries and arrays of objects are recursively sorted."""
        complex_manifest = {
            "version": "1.0",
            "metadata": {
                "z_param": 99,
                "a_param": 10,
                "nested": {"beta": True, "alpha": False}
            },
            "evidence": [
                {"file_id": "f2", "hash": "bbb"},
                {"file_id": "f1", "hash": "aaa"}
            ]
        }
        canonical_bytes = canonical_json_bytes(complex_manifest)
        # Expected: root keys: evidence, metadata, version
        # metadata keys: a_param, nested (alpha, beta), z_param
        expected = (
            b'{"evidence":[{"file_id":"f2","hash":"bbb"},{"file_id":"f1","hash":"aaa"}],'
            b'"metadata":{"a_param":10,"nested":{"alpha":false,"beta":true},"z_param":99},'
            b'"version":"1.0"}'
        )
        self.assertEqual(canonical_bytes, expected)

    def test_rfc8785_compact_representation_no_whitespace(self):
        """Verify no extra whitespace exists after delimiters ':' or ','."""
        sample = {"key1": "val1", "key2": "val2"}
        serialized = canonical_json_bytes(sample).decode("utf-8")
        self.assertNotIn(": ", serialized)
        self.assertNotIn(", ", serialized)
        self.assertNotIn("\n", serialized)

    def test_rfc8785_utf8_encoding_fidelity(self):
        """Verify non-ASCII unicode characters are encoded deterministically in UTF-8."""
        sample = {
            "facility": "München Recycling Werk 4",
            "material": "リチウムイオン電池 (Lithium-ion Battery)"
        }
        canonical_bytes = canonical_json_bytes(sample)
        # ensure_ascii=False leaves UTF-8 bytes intact
        decoded = canonical_bytes.decode("utf-8")
        self.assertIn("München", decoded)
        self.assertIn("リチウムイオン電池", decoded)

    # ------------------------------------------------------------------------
    # 3. Canonical Keccak-256 EVM Commitment
    # ------------------------------------------------------------------------
    def test_keccak256_standard_vectors(self):
        """Verify EVM Keccak-256 against official Ethereum test vectors."""
        empty_keccak = keccak256_hex(b"")
        self.assertEqual(
            empty_keccak,
            "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
        )

        hello_keccak = keccak256_hex(b"hello")
        self.assertEqual(
            hello_keccak,
            "0x1c8aff950685c2ed4bc3174f3472287b56d9517b9c948127319a09a7a36deac8"
        )

    def test_full_evidence_bundle_commitment_pipeline(self):
        """
        End-to-end evidence commitment pipeline:
        1. Files -> individual SHA-256
        2. Manifest construction
        3. Canonical JCS serialization
        4. Manifest SHA-256
        5. EVM keccak256 commitment
        """
        raw_image_1 = b"WEIGHBRIDGE_SCALE_TICKET_RAW_IMAGE_BYTES_12345"
        raw_image_2 = b"BATTERY_MODULE_CRUSHER_INTAKE_STILL_67890"

        hash_1 = sha256_hex(raw_image_1)
        hash_2 = sha256_hex(raw_image_2)

        manifest = {
            "event_id": "evt_nmc622_batch_40",
            "passport_id": "DPP-EV-NMC622-2026-M04",
            "facility_id": "FAC_EU_DE_8810",
            "evidence_files": [
                {"file_id": "file_scale_ticket", "sha256": hash_1, "provenance": "MEASURED"},
                {"file_id": "file_intake_photo", "sha256": hash_2, "provenance": "OBSERVED"}
            ],
            "ai_observation": {
                "provider": "Deterministic Mock Fixture",
                "model": "fixture-v1",
                "estimated_items": 40,
                "confidence": 0.99
            },
            "mass_balance": {
                "intake_mass_kg": 1000.0,
                "decision": "VALID",
                "claimed_recovered_kg": {"CO": 55.80, "NI": 165.60}
            }
        }

        canonical_bytes = canonical_json_bytes(manifest)
        manifest_sha256 = sha256_hex(canonical_bytes)
        bundle_keccak = keccak256_hex(canonical_bytes)

        # Integrity checks
        self.assertEqual(len(manifest_sha256), 64)
        self.assertTrue(bundle_keccak.startswith("0x"))
        self.assertEqual(len(bundle_keccak), 66)

    # ------------------------------------------------------------------------
    # 4. Tampering & Cryptographic Integrity Verification
    # ------------------------------------------------------------------------
    def test_tampering_file_content_changes_commitment(self):
        """Mutating 1 byte of physical evidence alters individual hash and commitment."""
        original_file = b"SCALE_TICKET_WEIGHT_1000_KG"
        tampered_file = b"SCALE_TICKET_WEIGHT_1001_KG"  # 1 byte difference

        hash_orig = sha256_hex(original_file)
        hash_tamp = sha256_hex(tampered_file)
        self.assertNotEqual(hash_orig, hash_tamp)

        manifest_orig = {"evidence_hash": hash_orig}
        manifest_tamp = {"evidence_hash": hash_tamp}

        commitment_orig = keccak256_hex(canonical_json_bytes(manifest_orig))
        commitment_tamp = keccak256_hex(canonical_json_bytes(manifest_tamp))
        self.assertNotEqual(commitment_orig, commitment_tamp)

    def test_tampering_manifest_value_detected(self):
        """Mutating a single quantitative value in the manifest produces commitment mismatch."""
        manifest_orig = {
            "event_id": "evt_001",
            "claimed_cobalt_kg": 55.80
        }
        manifest_tampered = {
            "event_id": "evt_001",
            "claimed_cobalt_kg": 55.81  # 0.01 kg tampering
        }

        comm_orig = keccak256_hex(canonical_json_bytes(manifest_orig))
        comm_tampered = keccak256_hex(canonical_json_bytes(manifest_tampered))

        self.assertNotEqual(comm_orig, comm_tampered,
                            "Tampering 0.01 kg must invalidate commitment hash.")

    def test_whitespace_insensitivity_under_canonicalization(self):
        """
        Validates that formatted JSON strings with differing indentations or whitespaces
        produce the exact same canonical commitment when parsed and canonicalized.
        """
        raw_json_pretty = '''
        {
            "passport_id": "DPP-001",
            "status": "VERIFIED"
        }
        '''
        raw_json_compact = '{"status":"VERIFIED","passport_id":"DPP-001"}'

        obj_pretty = json.loads(raw_json_pretty)
        obj_compact = json.loads(raw_json_compact)

        self.assertEqual(
            canonical_json_bytes(obj_pretty),
            canonical_json_bytes(obj_compact)
        )


if __name__ == "__main__":
    unittest.main()
