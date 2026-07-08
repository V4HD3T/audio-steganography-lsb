"""
steganalysis.py — Steganalysis Resistance Testing
===================================================
Implements two classical steganalysis attacks against WAV audio files:

  1. RS Analysis (Regular-Singular)
     Estimates the hidden message length by analysing the statistical
     distribution of Regular (R), Singular (S), and Unusable (U) sample
     groups under two flipping functions (F and F̄).  A large |R-S| ratio
     near zero strongly suggests no embedding; convergence of R≈S suggests
     ~50 % LSB fill (full capacity used).

  2. SPA — Sample Pair Analysis
     Exploits the asymmetry introduced by LSB embedding in pairs of
     consecutive audio samples.  Produces an independent payload-length
     estimate that can cross-validate the RS result.

Both methods operate on 16-bit signed PCM WAV data.

References:
    Fridrich, J., Goljan, M., Du, R. (2001). Reliable Detection of LSB
    Steganography in Color and Grayscale Images. ACM Workshop on Multimedia
    and Security.

    Lu, P., Luo, X., Tang, Q., Shen, L. (2004). An Improved Sample Pairs
    Method for Detection of LSB Embedding. Information Hiding Workshop.

Dependencies:
    pip install numpy
"""

import wave
import numpy as np


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _load_samples(audio_path: str) -> np.ndarray:
    """Load a 16-bit WAV file and return samples as a signed int16 array.

    Args:
        audio_path: Path to the WAV file.

    Returns:
        1-D numpy array of int16 samples.
    """
    with wave.open(audio_path, "rb") as wav:
        raw = wav.readframes(wav.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


# ---------------------------------------------------------------------------
# RS Analysis
# ---------------------------------------------------------------------------

def _flip_lsb(sample: int) -> int:
    """Flip the LSB of a sample (F function)."""
    return sample ^ 1


def _flip_lsb_inverse(sample: int) -> int:
    """Flip bit-1 of a sample (F̄ function — shifts ±1 in the opposite direction)."""
    return sample ^ 2   # XOR with 2 shifts bit-1


def _discriminator(group: np.ndarray) -> float:
    """Compute the RS discriminant function f(x) = Σ |x[i+1] - x[i]|."""
    return float(np.sum(np.abs(np.diff(group.astype(np.float64)))))


def rs_analysis(audio_path: str, group_size: int = 4) -> dict:
    """Run RS Analysis on a WAV file and estimate payload fill ratio.

    Args:
        audio_path: Path to the (potentially stego) WAV file.
        group_size: Number of samples per analysis group (default 4).

    Returns:
        Dict with keys:
            estimated_fill_ratio  — fraction of LSB capacity used (0.0–1.0)
            R_positive, S_positive, R_negative, S_negative — raw RS counts
            verdict               — 'likely_stego' or 'likely_clean'
    """
    samples = _load_samples(audio_path).astype(np.int32)

    # Trim to a multiple of group_size
    n = (len(samples) // group_size) * group_size
    groups = samples[:n].reshape(-1, group_size)

    R_pos = S_pos = 0
    R_neg = S_neg = 0

    for group in groups:
        f0 = _discriminator(group)

        # Positive flip: apply F to even-indexed elements
        g_pos = group.copy()
        g_pos[::2] = np.vectorize(_flip_lsb)(g_pos[::2])
        f_pos = _discriminator(g_pos)

        # Negative flip: apply F̄ to even-indexed elements
        g_neg = group.copy()
        g_neg[::2] = np.vectorize(_flip_lsb_inverse)(g_neg[::2])
        f_neg = _discriminator(g_neg)

        if f_pos > f0:
            R_pos += 1
        elif f_pos < f0:
            S_pos += 1

        if f_neg > f0:
            R_neg += 1
        elif f_neg < f0:
            S_neg += 1

    total = len(groups)
    if total == 0:
        return {"error": "No groups to analyse."}

    # Estimated fill ratio: when R_pos ≈ S_pos embedding fills ~50 % capacity
    d = (R_pos - S_pos) / total
    # Simple linear approximation (Fridrich et al.)
    fill_ratio = max(0.0, min(1.0, 1.0 - abs(d) * 2))

    verdict = "likely_stego" if fill_ratio > 0.05 else "likely_clean"

    return {
        "estimated_fill_ratio": round(fill_ratio, 4),
        "R_positive": R_pos,
        "S_positive": S_pos,
        "R_negative": R_neg,
        "S_negative": S_neg,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# SPA — Sample Pair Analysis
# ---------------------------------------------------------------------------

def spa_analysis(audio_path: str) -> dict:
    """Run Sample Pair Analysis (SPA) on a WAV file.

    SPA exploits the asymmetry in the distribution of consecutive sample
    pairs introduced by LSB embedding.

    Args:
        audio_path: Path to the (potentially stego) WAV file.

    Returns:
        Dict with keys:
            estimated_fill_ratio  — estimated fraction of LSBs modified
            P_count, Q_count      — raw pair counts used in estimation
            verdict               — 'likely_stego' or 'likely_clean'
    """
    samples = _load_samples(audio_path).astype(np.int32)

    if len(samples) < 2:
        return {"error": "Too few samples for SPA."}

    x = samples[:-1]   # u[i]
    y = samples[1:]    # u[i+1]

    # Count pairs where the difference is ±1 with specific parity relationships
    # P: pairs where (x even, y = x+1) or (x odd, y = x-1)
    P = np.sum(((x % 2 == 0) & (y == x + 1)) | ((x % 2 == 1) & (y == x - 1)))
    # Q: pairs where (x even, y = x-1) or (x odd, y = x+1)
    Q = np.sum(((x % 2 == 0) & (y == x - 1)) | ((x % 2 == 1) & (y == x + 1)))

    denom = P + Q
    if denom == 0:
        fill_ratio = 0.0
    else:
        # SPA estimator: fill ≈ 2(P-Q)/(P+Q) clamped to [0,1]
        fill_ratio = max(0.0, min(1.0, 2.0 * abs(P - Q) / denom))

    verdict = "likely_stego" if fill_ratio > 0.05 else "likely_clean"

    return {
        "estimated_fill_ratio": round(fill_ratio, 4),
        "P_count": int(P),
        "Q_count": int(Q),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------

def analyse(audio_path: str) -> None:
    """Run both RS and SPA analyses and print a combined report.

    Args:
        audio_path: Path to the WAV file to analyse.
    """
    print(f"\n[Steganalysis Report] {audio_path}")
    print("=" * 55)

    rs  = rs_analysis(audio_path)
    spa = spa_analysis(audio_path)

    print("\n[RS Analysis]")
    for k, v in rs.items():
        print(f"  {k:<25} {v}")

    print("\n[SPA Analysis]")
    for k, v in spa.items():
        print(f"  {k:<25} {v}")

    verdicts = {rs.get("verdict"), spa.get("verdict")}
    if "likely_stego" in verdicts:
        print("\n[!] CONCLUSION: One or more tests suggest hidden data may be present.")
    else:
        print("\n[+] CONCLUSION: Both tests suggest the file is likely clean.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python steganalysis.py <audio.wav>")
        sys.exit(1)

    analyse(sys.argv[1])
