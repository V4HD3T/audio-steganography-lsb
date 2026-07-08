"""
embedder.py — Advanced LSB Embedder / Extractor
================================================
Core steganography engine supporting:

  • Selectable LSB depth  — embed 1, 2, or 3 bits per audio byte.
  • PRNG byte selection   — bits are written to pseudo-randomly chosen
                            byte positions (seeded), making sequential
                            steganalysis much harder.
  • Optional AES-256-GCM  — encrypt the payload before embedding.
  • Optional Reed-Solomon — add FEC before embedding for burst-error recovery.

Self-contained header (64 bits):
  ┌──────────┬───────────┬──────────┬───────────────────────────────┐
  │ width    │ height    │ flags    │ payload_bit_length             │
  │ 16 bits  │ 16 bits   │ 8 bits   │ 24 bits                       │
  └──────────┴───────────┴──────────┴───────────────────────────────┘

  flags byte:
    bit 0 — encryption enabled (1 = yes)
    bit 1 — ECC enabled        (1 = yes)
    bits 2-3 — LSB depth - 1   (00=1bit, 01=2bits, 10=3bits)

Dependencies:
    pip install Pillow numpy cryptography reedsolo
"""

import wave
import struct
import random
import numpy as np
from PIL import Image

from crypto import encrypt, decrypt
from ecc    import encode as ecc_encode, decode as ecc_decode

# Header layout constants (total 64 bits = 8 bytes)
_HEADER_BITS = 64


def _int_to_bits(value: int, n: int) -> list[int]:
    """Convert an integer to a list of n bits (MSB first)."""
    return [(value >> (n - 1 - i)) & 1 for i in range(n)]


def _bits_to_int(bits: list[int]) -> int:
    """Convert a list of bits (MSB first) to an integer."""
    result = 0
    for b in bits:
        result = (result << 1) | b
    return result


def _bytes_to_bits(data: bytes) -> list[int]:
    """Flatten bytes to a list of bits (MSB first per byte)."""
    bits = []
    for byte in data:
        bits.extend(_int_to_bits(byte, 8))
    return bits


def _bits_to_bytes(bits: list[int]) -> bytes:
    """Pack a list of bits (MSB first) into bytes."""
    # Pad to multiple of 8
    remainder = len(bits) % 8
    if remainder:
        bits = bits + [0] * (8 - remainder)
    return bytes(
        _bits_to_int(bits[i : i + 8])
        for i in range(0, len(bits), 8)
    )


def _prng_positions(total_bytes: int, num_positions: int, seed: int) -> list[int]:
    """Generate a shuffled list of byte positions using a seeded PRNG.

    Args:
        total_bytes:   Size of the audio frame buffer in bytes.
        num_positions: Number of positions needed (header + payload bytes).
        seed:          Integer seed (e.g. derived from password hash).

    Returns:
        List of unique byte indices in pseudo-random order.

    Raises:
        ValueError: If num_positions exceeds total_bytes.
    """
    if num_positions > total_bytes:
        raise ValueError(
            f"Need {num_positions} positions but audio only has {total_bytes} bytes."
        )
    rng = random.Random(seed)
    positions = list(range(total_bytes))
    rng.shuffle(positions)
    return positions[:num_positions]


def embed(
    audio_path:  str,
    output_path: str,
    image_path:  str,
    lsb_depth:   int  = 1,
    password:    str  = None,
    use_ecc:     bool = False,
    prng_seed:   int  = None,
) -> dict:
    """Embed a PNG image into a WAV audio file.

    Args:
        audio_path:  Path to the carrier (cover) WAV file.
        output_path: Path where the stego WAV file will be written.
        image_path:  Path to the image to hide (any Pillow-supported format).
        lsb_depth:   Number of LSBs to use per byte (1, 2, or 3).
        password:    If provided, encrypts the payload with AES-256-GCM.
        use_ecc:     If True, applies Reed-Solomon FEC before embedding.
        prng_seed:   Seed for PRNG byte-position selection.
                     If None, bits are embedded sequentially (LSB-classic).

    Returns:
        Dict with keys: bits_embedded, capacity_bits, snr_db.

    Raises:
        ValueError: If lsb_depth not in {1, 2, 3} or payload too large.
    """
    if lsb_depth not in (1, 2, 3):
        raise ValueError("lsb_depth must be 1, 2, or 3.")

    # --- Load image ---
    with Image.open(image_path) as img:
        img   = img.convert("RGB")
        width, height = img.size
        pixel_bytes = np.array(img).tobytes()

    # --- Optional pipeline: ECC → encrypt ---
    payload = pixel_bytes
    if use_ecc:
        payload = ecc_encode(payload)
    if password:
        payload = encrypt(payload, password)

    payload_bits = _bytes_to_bits(payload)
    payload_len  = len(payload_bits)

    # --- Build 64-bit header ---
    flags = 0
    if password:
        flags |= 0b00000001
    if use_ecc:
        flags |= 0b00000010
    flags |= ((lsb_depth - 1) & 0b11) << 2

    header_bits = (
        _int_to_bits(width,       16) +
        _int_to_bits(height,      16) +
        _int_to_bits(flags,        8) +
        _int_to_bits(payload_len, 24)
    )   # 64 bits total

    all_bits = header_bits + payload_bits

    # --- Load audio ---
    with wave.open(audio_path, "rb") as wav:
        params      = wav.getparams()
        frame_bytes = bytearray(wav.readframes(wav.getnframes()))

    original_bytes = bytes(frame_bytes)  # keep for SNR calculation

    # --- Capacity check ---
    capacity_bits = len(frame_bytes) * lsb_depth
    if len(all_bits) > capacity_bits:
        raise ValueError(
            f"Payload ({len(all_bits)} bits) exceeds capacity "
            f"({capacity_bits} bits at LSB depth {lsb_depth})."
        )

    # --- Determine byte positions ---
    # We need ceil(len(all_bits) / lsb_depth) byte slots
    import math
    n_slots = math.ceil(len(all_bits) / lsb_depth)

    if prng_seed is not None:
        positions = _prng_positions(len(frame_bytes), n_slots, prng_seed)
    else:
        positions = list(range(n_slots))

    # --- Embed bits ---
    bit_index = 0
    mask = (1 << lsb_depth) - 1   # e.g. depth=2 → 0b11

    for slot, pos in enumerate(positions):
        if bit_index >= len(all_bits):
            break
        chunk = all_bits[bit_index : bit_index + lsb_depth]
        # Pad chunk if at the end
        while len(chunk) < lsb_depth:
            chunk.append(0)
        value = _bits_to_int(chunk)
        frame_bytes[pos] = (frame_bytes[pos] & ~mask) | value
        bit_index += lsb_depth

    # --- Write stego WAV ---
    with wave.open(output_path, "wb") as out:
        out.setparams(params)
        out.writeframes(bytes(frame_bytes))

    # --- SNR ---
    orig = np.frombuffer(original_bytes, dtype=np.int16).astype(np.float64)
    mod  = np.frombuffer(bytes(frame_bytes), dtype=np.int16).astype(np.float64)
    noise_power  = np.sum((orig - mod) ** 2)
    signal_power = np.sum(orig ** 2)
    snr_db = float("inf") if noise_power == 0 else 10 * np.log10(signal_power / noise_power)

    print(f"[+] Embedded {len(all_bits)} bits using LSB-{lsb_depth}.")
    print(f"[*] SNR: {snr_db:.2f} dB" if snr_db != float("inf") else "[*] SNR: inf (no change)")

    return {
        "bits_embedded":  len(all_bits),
        "capacity_bits":  capacity_bits,
        "snr_db":         snr_db,
    }


def extract(
    audio_path:  str,
    output_path: str,
    lsb_depth:   int  = 1,
    password:    str  = None,
    prng_seed:   int  = None,
) -> tuple[int, int]:
    """Extract a hidden image from a stego WAV file.

    Args:
        audio_path:  Path to the stego WAV file.
        output_path: Destination path for the recovered image (PNG).
        lsb_depth:   LSB depth used during embedding (must match).
        password:    Decryption password (must match if encryption was used).
        prng_seed:   PRNG seed used during embedding (must match if used).

    Returns:
        Tuple of (width, height) of the recovered image.

    Raises:
        ValueError: If the header is invalid or payload extraction fails.
    """
    with wave.open(audio_path, "rb") as wav:
        frame_bytes = bytearray(wav.readframes(wav.getnframes()))

    mask = (1 << lsb_depth) - 1

    def read_bits(positions: list[int], n_bits: int) -> list[int]:
        """Read n_bits from the given byte positions."""
        bits = []
        for pos in positions:
            if len(bits) >= n_bits:
                break
            chunk = _int_to_bits(frame_bytes[pos] & mask, lsb_depth)
            bits.extend(chunk)
        return bits[:n_bits]

    # --- How many byte slots does the 64-bit header occupy? ---
    import math
    header_slots = math.ceil(_HEADER_BITS / lsb_depth)

    if prng_seed is not None:
        # We don't know total payload yet, use a large upper bound for now
        all_positions = _prng_positions(len(frame_bytes), len(frame_bytes), prng_seed)
        header_positions = all_positions[:header_slots]
    else:
        header_positions = list(range(header_slots))

    header_bits = read_bits(header_positions, _HEADER_BITS)

    width       = _bits_to_int(header_bits[0:16])
    height      = _bits_to_int(header_bits[16:32])
    flags       = _bits_to_int(header_bits[32:40])
    payload_len = _bits_to_int(header_bits[40:64])

    encrypted = bool(flags & 0b00000001)
    has_ecc   = bool(flags & 0b00000010)
    # lsb_depth from flags (informational — caller must pass correct depth)

    # --- Read payload bits ---
    payload_slots = math.ceil(payload_len / lsb_depth)
    total_slots   = header_slots + payload_slots

    if prng_seed is not None:
        all_positions    = _prng_positions(len(frame_bytes), total_slots, prng_seed)
        payload_positions = all_positions[header_slots:total_slots]
    else:
        payload_positions = list(range(header_slots, header_slots + payload_slots))

    payload_bits  = read_bits(payload_positions, payload_len)
    payload_bytes = _bits_to_bytes(payload_bits)

    # --- Reverse pipeline: decrypt → ECC decode ---
    if encrypted:
        if password is None:
            raise ValueError("Payload is encrypted but no password was provided.")
        payload_bytes = decrypt(payload_bytes, password)

    if has_ecc:
        payload_bytes = ecc_decode(payload_bytes)

    # --- Reconstruct image ---
    pixel_array = np.frombuffer(payload_bytes[: width * height * 3], dtype=np.uint8)
    pixel_array = pixel_array.reshape((height, width, 3))
    Image.fromarray(pixel_array, "RGB").save(output_path)

    print(f"[+] Extracted image ({width}x{height}) saved to: {output_path}")
    return width, height
