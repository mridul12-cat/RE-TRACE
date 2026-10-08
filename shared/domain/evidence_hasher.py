"""
RE:TRACE Deterministic Evidence Hasher & Cryptographic Commitment Engine.

Implements:
1. Deterministic RFC 8785 JSON Canonicalization Scheme (JCS).
2. Streaming SHA-256 file and payload hashing.
3. Standard EVM Keccak-256 commitment calculation.
"""

from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Tuple, Union
from pydantic import BaseModel


# Standard Keccak-f[1600] Round Constants
_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]

# Keccak-f[1600] Lane Rotation Offsets
_R = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]


def _rotl64(x: int, n: int) -> int:
    return ((x << (n % 64)) | (x >> (64 - (n % 64)))) & 0xFFFFFFFFFFFFFFFF


def keccak256_bytes(data: bytes) -> bytes:
    """
    Computes raw 32-byte EVM Keccak-256 digest of data.
    Matches Solidity keccak256() exactly.
    """
    rate = 136  # bytes (1088 bits)
    state = [[0] * 5 for _ in range(5)]

    # Padding: Keccak pad10*1 with domain separator 0x01
    padlen = rate - (len(data) % rate)
    if padlen == 1:
        padded = data + b"\x81"
    else:
        padded = data + b"\x01" + b"\x00" * (padlen - 2) + b"\x80"

    # Absorb phase
    for block_start in range(0, len(padded), rate):
        block = padded[block_start : block_start + rate]
        for i in range(rate // 8):
            x = i % 5
            y = i // 5
            lane = int.from_bytes(block[i * 8 : (i + 1) * 8], "little")
            state[x][y] ^= lane

        # 24 rounds of Keccak-f[1600]
        for round_idx in range(24):
            # Theta step
            C = [
                state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4]
                for x in range(5)
            ]
            D = [C[(x - 1) % 5] ^ _rotl64(C[(x + 1) % 5], 1) for x in range(5)]
            for x in range(5):
                for y in range(5):
                    state[x][y] ^= D[x]

            # Rho and Pi steps
            B = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    B[y][(2 * x + 3 * y) % 5] = _rotl64(state[x][y], _R[x][y])

            # Chi step
            for x in range(5):
                for y in range(5):
                    state[x][y] = (
                        B[x][y]
                        ^ ((~B[(x + 1) % 5][y]) & B[(x + 2) % 5][y])
                        & 0xFFFFFFFFFFFFFFFF
                    )

            # Iota step
            state[0][0] ^= _RC[round_idx]

    # Squeeze phase: 32 bytes (4 lanes of 8 bytes)
    out = bytearray()
    for i in range(4):
        x = i % 5
        y = i // 5
        out.extend(state[x][y].to_bytes(8, "little"))
    return bytes(out)


def keccak256(data: bytes, prefix_0x: bool = True) -> str:
    """
    Computes hexadecimal EVM Keccak-256 digest of data.
    """
    digest_hex = keccak256_bytes(data).hex()
    return f"0x{digest_hex}" if prefix_0x else digest_hex


def hash_bytes_sha256(data: bytes) -> str:
    """Computes hexadecimal SHA-256 digest of binary payload."""
    return hashlib.sha256(data).hexdigest()


def hash_file_sha256(file_path: Union[str, Path]) -> str:
    """
    Streams file in 64KB chunks and computes hexadecimal SHA-256 digest.
    """
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Evidence file not found: {file_path}")

    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _normalize_for_canonical_json(obj: Any) -> Any:
    """
    Recursively converts Pydantic models, dates, tuples, and enums into
    primitive JSON-compatible structures for RFC 8785 canonicalization.
    """
    if isinstance(obj, BaseModel):
        # Support Pydantic v2 model_dump or v1 dict
        if hasattr(obj, "model_dump"):
            dumped = obj.model_dump(mode="python")
        else:
            dumped = obj.dict()
        return _normalize_for_canonical_json(dumped)

    if isinstance(obj, dict):
        return {str(k): _normalize_for_canonical_json(v) for k, v in obj.items()}

    if isinstance(obj, (set, frozenset)):
        # Sets have non-deterministic iteration order in Python.
        # Normalize and sort elements deterministically for canonical JSON.
        normalized_items = [_normalize_for_canonical_json(item) for item in obj]
        try:
            return sorted(normalized_items)
        except TypeError:
            # Fallback for heterogeneous unorderable types: sort by deterministic JSON string
            return sorted(
                normalized_items,
                key=lambda x: json.dumps(
                    x,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                    default=str,
                ),
            )

    if isinstance(obj, (list, tuple)):
        # Preserve declared semantic sequence order for lists and tuples
        return [_normalize_for_canonical_json(item) for item in obj]

    if isinstance(obj, (datetime, date)):
        # ISO 8601 formatted string
        return obj.isoformat()

    if hasattr(obj, "value"):
        # Enum instance
        return obj.value

    return obj


def canonicalize_json(data: Any) -> bytes:
    """
    Serializes arbitrary Python object/dictionary into canonical JSON bytes
    per RFC 8785 (JCS):
    - Lexicographically sorted dictionary keys (UTF-8 code point order).
    - Compact representation with no whitespace separators (',', ':').
    - Deterministic float and string serialization.
    - Disallows non-standard NaN and Infinity.
    """
    normalized = _normalize_for_canonical_json(data)
    json_str = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return json_str.encode("utf-8")


def compute_evidence_bundle_commitment(manifest_data: Any) -> Tuple[str, str]:
    """
    Computes both the canonical manifest SHA-256 and the on-chain EVM keccak256 commitment.
    Returns (canonical_manifest_sha256, bundle_keccak256_commitment).
    """
    canonical_bytes = canonicalize_json(manifest_data)
    sha256_digest = hash_bytes_sha256(canonical_bytes)
    keccak_commitment = keccak256(canonical_bytes, prefix_0x=True)
    return sha256_digest, keccak_commitment
