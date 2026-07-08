"""
ecc.py — Reed-Solomon Error Correction Layer
=============================================
Wraps the `reedsolo` library to add forward error correction (FEC) to
steganography payloads.  Reed-Solomon can recover from burst errors —
ideal for cases where a portion of the stego audio is corrupted or
recompressed.

Configuration:
    ECC_SYMBOLS = 32  →  corrects up to 16 byte errors per 223-byte block
                          (RS(255, 223) shortened to fit arbitrary payload sizes)

Usage pattern:
    encoded = encode(raw_bytes)        # before embedding
    decoded = decode(encoded_bytes)    # after extraction

Dependencies:
    pip install reedsolo
"""

import reedsolo

# Number of error-correction symbols per block.
# Each symbol corrects half its count in byte errors: 32 → 16 byte errors/block.
ECC_SYMBOLS = 32

_rs = reedsolo.RSCodec(ECC_SYMBOLS)


def encode(data: bytes) -> bytes:
    """Encode a byte payload with Reed-Solomon error correction.

    The payload is split into blocks internally by reedsolo.  Each block
    has ECC_SYMBOLS parity bytes appended.  The encoded output is longer
    than the input by roughly ECC_SYMBOLS bytes per 223-byte chunk.

    Args:
        data: Raw bytes to protect.

    Returns:
        RS-encoded bytes (data + parity symbols).
    """
    encoded = _rs.encode(data)
    return bytes(encoded)


def decode(data: bytes) -> bytes:
    """Decode and error-correct a Reed-Solomon encoded payload.

    Args:
        data: RS-encoded bytes, possibly with up to 16 byte errors per block.

    Returns:
        Recovered original bytes (parity symbols stripped).

    Raises:
        reedsolo.ReedSolomonError: If the number of errors exceeds the
            correction capacity (more than ECC_SYMBOLS/2 errors per block).
    """
    decoded, _, _ = _rs.decode(data)
    return bytes(decoded)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    original = b"Audio steganography payload protected by Reed-Solomon ECC."

    encoded = encode(original)
    print(f"[*] Original  : {len(original)} bytes")
    print(f"[*] Encoded   : {len(encoded)} bytes  (+{len(encoded) - len(original)} parity)")

    # Simulate 10 byte errors at random positions
    import random
    corrupted = bytearray(encoded)
    error_positions = random.sample(range(len(corrupted)), 10)
    for pos in error_positions:
        corrupted[pos] ^= 0xFF   # flip all bits in the byte
    print(f"[*] Introduced 10 byte errors at positions: {sorted(error_positions)}")

    recovered = decode(bytes(corrupted))
    assert recovered == original, "Recovery failed!"
    print(f"[+] Recovered successfully: {recovered.decode()}")
