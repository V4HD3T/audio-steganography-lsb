"""
capacity.py — Steganographic Capacity Calculator
=================================================
Answers two complementary questions before any embedding attempt:

  1. FORWARD:  Given a WAV file and an image, does the image fit?
               What is the fill ratio at each LSB depth (1/2/3)?

  2. REVERSE:  Given a WAV file and an LSB depth, what is the maximum
               image resolution (in pixels) that can be hidden?

All calculations include the 64-bit self-describing header used by embedder.py,
as well as optional overhead for ECC (+~14 %) and AES-GCM (+44 bytes).

Dependencies:
    pip install Pillow
"""

import wave
import math
from PIL import Image

# Header overhead from embedder.py
_HEADER_BITS = 64

# Reed-Solomon overhead: ECC_SYMBOLS=32 parity bytes per 223-byte data block
_ECC_SYMBOLS     = 32
_ECC_BLOCK_DATA  = 223
_ECC_BLOCK_TOTAL = 255

# AES-GCM overhead: salt(16) + nonce(12) + tag(16) = 44 bytes
_AES_OVERHEAD_BYTES = 44


def _wav_capacity_bits(audio_path: str, lsb_depth: int) -> int:
    """Return the raw bit capacity of a WAV file at the given LSB depth.

    Args:
        audio_path: Path to the WAV file.
        lsb_depth:  Bits per audio byte to use (1, 2, or 3).

    Returns:
        Total embeddable bits (including space for the header).
    """
    with wave.open(audio_path, "rb") as wav:
        n_frames   = wav.getnframes()
        n_channels = wav.getnchannels()
        sampwidth  = wav.getsampwidth()   # bytes per sample

    total_bytes = n_frames * n_channels * sampwidth
    return total_bytes * lsb_depth


def _image_payload_bits(image_path: str, use_ecc: bool = False, encrypted: bool = False) -> int:
    """Return the total bits needed to embed an image (header + optional overhead).

    Args:
        image_path: Path to the image file.
        use_ecc:    Whether Reed-Solomon ECC will be applied.
        encrypted:  Whether AES-GCM encryption will be applied.

    Returns:
        Total bits required (header + payload).
    """
    with Image.open(image_path) as img:
        width, height = img.size

    raw_bytes = width * height * 3   # RGB, 1 byte per channel

    payload = raw_bytes
    if use_ecc:
        # RS expands data: each 223-byte block becomes 255 bytes
        n_blocks = math.ceil(payload / _ECC_BLOCK_DATA)
        payload  = n_blocks * _ECC_BLOCK_TOTAL
    if encrypted:
        payload += _AES_OVERHEAD_BYTES

    return _HEADER_BITS + payload * 8


def check_fit(
    audio_path: str,
    image_path: str,
    use_ecc:    bool = False,
    encrypted:  bool = False,
) -> None:
    """Print a capacity report: does the image fit at each LSB depth?

    Args:
        audio_path: Path to the carrier WAV file.
        image_path: Path to the image to be hidden.
        use_ecc:    Whether ECC overhead should be included.
        encrypted:  Whether AES-GCM overhead should be included.
    """
    with Image.open(image_path) as img:
        iw, ih = img.size
    raw_bytes = iw * ih * 3

    needed_bits = _image_payload_bits(image_path, use_ecc, encrypted)

    print(f"\n[Capacity Check]")
    print(f"  Image        : {iw} x {ih} px  ({raw_bytes:,} bytes raw RGB)")
    print(f"  ECC          : {'yes (+{:.0f}%)'.format((_ECC_BLOCK_TOTAL/_ECC_BLOCK_DATA - 1)*100) if use_ecc else 'no'}")
    print(f"  Encryption   : {'yes (+44 bytes AES-GCM)' if encrypted else 'no'}")
    print(f"  Payload bits : {needed_bits:,}\n")

    with wave.open(audio_path, "rb") as wav:
        n_frames   = wav.getnframes()
        n_channels = wav.getnchannels()
        sampwidth  = wav.getsampwidth()
        framerate  = wav.getframerate()

    duration    = n_frames / framerate
    total_bytes = n_frames * n_channels * sampwidth

    print(f"  Audio        : {duration:.1f}s  {n_channels}ch  {framerate} Hz  {sampwidth*8}-bit")
    print(f"  Frame bytes  : {total_bytes:,}\n")

    header = f"  {'LSB depth':<12} {'Capacity (bits)':<20} {'Needed (bits)':<20} {'Fill %':<10} Fits?"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for depth in (1, 2, 3):
        cap  = total_bytes * depth
        fill = needed_bits / cap * 100
        fits = "YES" if needed_bits <= cap else "NO "
        print(f"  {depth:<12} {cap:<20,} {needed_bits:<20,} {fill:<10.1f} {fits}")


def max_image_size(
    audio_path: str,
    lsb_depth:  int  = 1,
    use_ecc:    bool = False,
    encrypted:  bool = False,
) -> tuple[int, int]:
    """Return the maximum square image resolution that fits in a WAV file.

    Args:
        audio_path: Path to the carrier WAV file.
        lsb_depth:  Bits per audio byte (1, 2, or 3).
        use_ecc:    Whether to account for ECC overhead.
        encrypted:  Whether to account for AES-GCM overhead.

    Returns:
        (max_width, max_height) in pixels for a square RGB image.
    """
    capacity_bits = _wav_capacity_bits(audio_path, lsb_depth)
    payload_bits  = capacity_bits - _HEADER_BITS

    payload_bytes = payload_bits // 8
    if encrypted:
        payload_bytes = max(0, payload_bytes - _AES_OVERHEAD_BYTES)
    if use_ecc:
        # Reverse ECC expansion: usable data = total * (223/255)
        payload_bytes = int(payload_bytes * _ECC_BLOCK_DATA / _ECC_BLOCK_TOTAL)

    # RGB: 3 bytes per pixel → max pixels = payload_bytes / 3
    max_pixels = payload_bytes // 3
    side = int(math.isqrt(max_pixels))

    print(f"\n[Max Image Size] LSB-{lsb_depth}"
          f"  ECC={'on' if use_ecc else 'off'}"
          f"  Enc={'on' if encrypted else 'off'}")
    print(f"  Max pixels : {max_pixels:,}")
    print(f"  Max square : {side} x {side} px")

    return side, side


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python capacity.py <audio.wav> <image.png> [--ecc] [--enc]")
        sys.exit(1)

    use_ecc   = "--ecc" in sys.argv
    encrypted = "--enc" in sys.argv

    check_fit(sys.argv[1], sys.argv[2], use_ecc=use_ecc, encrypted=encrypted)

    for depth in (1, 2, 3):
        max_image_size(sys.argv[1], lsb_depth=depth, use_ecc=use_ecc, encrypted=encrypted)
