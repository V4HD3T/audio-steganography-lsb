"""
benchmark_suite.py — Automated LSB Variant Benchmark
=====================================================
Runs a full embed → extract cycle for every combination of:
  • LSB depth       : 1, 2, 3
  • PRNG seed       : None (sequential), or a fixed seed (e.g. 42)
  • ECC             : off / on
and records SNR, ENG, pixel PSNR, and bit-error rate (BER) for each run.

Results are printed as a markdown-style table and optionally saved to CSV.

Dependencies:
    pip install Pillow numpy reedsolo cryptography
"""

import os
import csv
import time
import wave
import tempfile
import numpy as np
from PIL import Image

from embedder import embed, extract


# ---------------------------------------------------------------------------
# Image quality metrics
# ---------------------------------------------------------------------------

def psnr(original_path: str, recovered_path: str) -> float:
    """Compute Peak Signal-to-Noise Ratio between two images (dB).

    PSNR = 20 * log10(MAX_I / RMSE)   where MAX_I = 255 for 8-bit images.

    Higher is better; > 40 dB is generally considered excellent.

    Args:
        original_path: Path to the ground-truth image.
        recovered_path: Path to the reconstructed image.

    Returns:
        PSNR in decibels, or +inf if images are identical.
    """
    orig = np.array(Image.open(original_path).convert("RGB"), dtype=np.float64)
    recv = np.array(Image.open(recovered_path).convert("RGB"), dtype=np.float64)

    mse = np.mean((orig - recv) ** 2)
    if mse == 0:
        return float("inf")
    return 20.0 * np.log10(255.0 / np.sqrt(mse))


def ber(original_path: str, recovered_path: str) -> float:
    """Compute the Bit Error Rate between two images.

    BER = (number of differing bits) / (total bits)

    Args:
        original_path: Path to the ground-truth image.
        recovered_path: Path to the reconstructed image.

    Returns:
        BER in range [0.0, 1.0].  0.0 = perfect recovery.
    """
    orig_bytes = np.array(Image.open(original_path).convert("RGB"), dtype=np.uint8).flatten()
    recv_bytes = np.array(Image.open(recovered_path).convert("RGB"), dtype=np.uint8).flatten()

    # XOR finds differing bits; unpackbits counts them
    xor        = np.bitwise_xor(orig_bytes, recv_bytes)
    error_bits = np.unpackbits(xor).sum()
    total_bits = orig_bytes.size * 8

    return float(error_bits) / total_bits


def audio_snr(original_path: str, stego_path: str) -> float:
    """Compute SNR (dB) between original and stego audio."""
    with wave.open(original_path, "rb") as w:
        orig = np.frombuffer(w.readframes(-1), dtype=np.int16).astype(np.float64)
    with wave.open(stego_path, "rb") as w:
        steg = np.frombuffer(w.readframes(-1), dtype=np.int16).astype(np.float64)

    noise_power  = np.sum((orig - steg) ** 2)
    signal_power = np.sum(orig ** 2)

    if noise_power == 0:
        return float("inf")
    return 10.0 * np.log10(signal_power / noise_power)


def audio_eng(original_path: str, stego_path: str) -> float:
    """Compute Energy-to-Noise Gain between original and stego audio."""
    with wave.open(original_path, "rb") as w:
        orig = np.frombuffer(w.readframes(-1), dtype=np.int16).astype(np.float64)
    with wave.open(stego_path, "rb") as w:
        steg = np.frombuffer(w.readframes(-1), dtype=np.int16).astype(np.float64)

    signal_power = np.sum(orig ** 2)
    noise_power  = np.sum((orig - steg) ** 2)

    if noise_power == 0:
        return float("inf")
    return signal_power / noise_power


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    audio_path: str,
    image_path: str,
    output_csv: str = None,
) -> list[dict]:
    """Run all LSB variant combinations and collect quality metrics.

    Args:
        audio_path: Path to the carrier WAV file.
        image_path: Path to the image to hide.
        output_csv: Optional path to save results as a CSV file.

    Returns:
        List of result dicts, one per configuration.
    """
    configs = [
        {"lsb_depth": d, "prng_seed": seed, "use_ecc": ecc}
        for d    in (1, 2, 3)
        for seed in (None, 42)
        for ecc  in (False, True)
    ]

    results = []

    print("\n[Benchmark Suite]")
    print(f"  Audio : {audio_path}")
    print(f"  Image : {image_path}")
    print(f"  Runs  : {len(configs)}\n")

    col = f"{'LSB':>4}  {'PRNG':>6}  {'ECC':>4}  {'SNR(dB)':>9}  {'ENG':>10}  {'PSNR(dB)':>9}  {'BER':>8}  {'Time(s)':>8}"
    print(col)
    print("-" * len(col))

    for cfg in configs:
        depth = cfg["lsb_depth"]
        seed  = cfg["prng_seed"]
        ecc   = cfg["use_ecc"]

        stego_tmp    = tempfile.NamedTemporaryFile(suffix=".wav",  delete=False)
        recovered_tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        stego_tmp.close()
        recovered_tmp.close()

        t0 = time.time()
        try:
            embed(
                audio_path  = audio_path,
                output_path = stego_tmp.name,
                image_path  = image_path,
                lsb_depth   = depth,
                use_ecc     = ecc,
                prng_seed   = seed,
            )
            extract(
                audio_path  = stego_tmp.name,
                output_path = recovered_tmp.name,
                lsb_depth   = depth,
                prng_seed   = seed,
            )
            elapsed = time.time() - t0

            snr_val  = audio_snr(audio_path, stego_tmp.name)
            eng_val  = audio_eng(audio_path, stego_tmp.name)
            psnr_val = psnr(image_path, recovered_tmp.name)
            ber_val  = ber(image_path, recovered_tmp.name)

            row = {
                "lsb_depth": depth,
                "prng_seed": seed if seed is not None else "seq",
                "use_ecc":   ecc,
                "snr_db":    round(snr_val,  2),
                "eng":       round(eng_val,  2),
                "psnr_db":   round(psnr_val, 2),
                "ber":       round(ber_val,  6),
                "time_s":    round(elapsed,  3),
            }
            results.append(row)

            prng_str = str(seed) if seed is not None else "seq"
            print(
                f"{depth:>4}  {prng_str:>6}  {'on' if ecc else 'off':>4}  "
                f"{snr_val:>9.2f}  {eng_val:>10.2f}  {psnr_val:>9.2f}  "
                f"{ber_val:>8.6f}  {elapsed:>8.3f}"
            )

        except Exception as ex:
            print(f"  [FAIL] LSB-{depth} seed={seed} ecc={ecc}: {ex}")

        finally:
            os.unlink(stego_tmp.name)
            os.unlink(recovered_tmp.name)

    if output_csv and results:
        with open(output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[+] Results saved to: {output_csv}")

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python benchmark_suite.py <audio.wav> <image.png> [output.csv]")
        sys.exit(1)

    csv_out = sys.argv[3] if len(sys.argv) > 3 else None
    run_benchmark(sys.argv[1], sys.argv[2], output_csv=csv_out)
