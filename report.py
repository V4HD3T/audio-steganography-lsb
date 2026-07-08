"""
report.py — Visual Quality Report Generator
============================================
Produces a 3-panel matplotlib figure comparing the cover and stego audio:

  Panel 1 — Waveform overlay
      Cover (blue) and stego (orange) waveforms plotted on the same axis.
      Visually confirms that the two signals are perceptually identical.

  Panel 2 — Difference signal
      Stego minus Cover, showing exactly which samples were modified
      and by how much.  For LSB-1 all non-zero values should be ±1.

  Panel 3 — LSB histogram comparison
      Distribution of the Least Significant Bit across all samples for
      both cover and stego.  LSB embedding shifts the stego histogram
      toward 50/50 even if the cover had a strong natural bias.

The figure is saved as a high-resolution PNG and optionally displayed
in an interactive window.

Dependencies:
    pip install numpy matplotlib
"""

import wave
import numpy as np
import matplotlib
matplotlib.use("Agg")   # Headless backend — no display required
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


# ---------------------------------------------------------------------------
# Audio loading
# ---------------------------------------------------------------------------

def _load_wav(path: str) -> tuple[np.ndarray, int]:
    """Load a WAV file and return (samples_int16, frame_rate)."""
    with wave.open(path, "rb") as wav:
        rate = wav.getframerate()
        raw  = wav.readframes(wav.getnframes())
    return np.frombuffer(raw, dtype=np.int16), rate


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    original_path: str,
    stego_path:    str,
    output_path:   str = "stego_report.png",
    show:          bool = False,
    max_samples:   int  = 4000,
) -> None:
    """Generate a 3-panel visual quality report and save it as PNG.

    Args:
        original_path: Path to the cover (original) WAV file.
        stego_path:    Path to the stego WAV file.
        output_path:   Destination PNG file path.
        show:          If True, open an interactive matplotlib window.
        max_samples:   Number of samples to plot in the waveform panels
                       (too many makes the plot unreadable).
    """
    orig, rate = _load_wav(original_path)
    steg, _    = _load_wav(stego_path)

    # Align lengths (in case files differ by a few samples)
    n    = min(len(orig), len(steg))
    orig = orig[:n]
    steg = steg[:n]

    # Time axis (seconds)
    t = np.arange(n) / rate

    # Difference signal
    diff = steg.astype(np.int32) - orig.astype(np.int32)

    # SNR
    signal_power = np.sum(orig.astype(np.float64) ** 2)
    noise_power  = np.sum(diff.astype(np.float64) ** 2)
    snr_db = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else float("inf")

    # Subset for waveform / diff plots
    step  = max(1, n // max_samples)
    ts    = t[::step]
    os_   = orig[::step]
    ss_   = steg[::step]
    ds_   = diff[::step]

    # LSB distributions
    orig_lsb = orig & 1
    steg_lsb = steg & 1

    # -----------------------------------------------------------------------
    # Figure layout
    # -----------------------------------------------------------------------
    fig = plt.figure(figsize=(14, 10))
    fig.suptitle(
        f"Steganography Quality Report\n"
        f"Cover: {original_path}   Stego: {stego_path}   SNR: {snr_db:.2f} dB",
        fontsize=12, fontweight="bold",
    )

    gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.35)

    # --- Panel 1: Waveform overlay (full width) ---
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(ts, os_, color="#2196F3", alpha=0.8, linewidth=0.6, label="Cover")
    ax1.plot(ts, ss_, color="#FF9800", alpha=0.6, linewidth=0.6, label="Stego", linestyle="--")
    ax1.set_title("Waveform Overlay (Cover vs Stego)")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # --- Panel 2: Difference signal ---
    ax2 = fig.add_subplot(gs[1, :])
    ax2.plot(ts, ds_, color="#F44336", linewidth=0.5)
    ax2.axhline(0, color="black", linewidth=0.8, linestyle=":")
    ax2.set_title(f"Difference Signal (Stego - Cover)  |  max={np.max(np.abs(diff))}")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Delta")
    ax2.grid(True, alpha=0.3)

    # --- Panel 3a: LSB histogram — Cover ---
    ax3 = fig.add_subplot(gs[2, 0])
    counts_orig = [np.sum(orig_lsb == 0), np.sum(orig_lsb == 1)]
    ax3.bar(["LSB=0", "LSB=1"], counts_orig, color=["#2196F3", "#64B5F6"], edgecolor="white")
    ax3.set_title("LSB Distribution — Cover")
    ax3.set_ylabel("Sample count")
    total = counts_orig[0] + counts_orig[1]
    for i, v in enumerate(counts_orig):
        ax3.text(i, v + total * 0.01, f"{v/total*100:.1f}%", ha="center", fontsize=9)
    ax3.grid(True, alpha=0.3, axis="y")

    # --- Panel 3b: LSB histogram — Stego ---
    ax4 = fig.add_subplot(gs[2, 1])
    counts_steg = [np.sum(steg_lsb == 0), np.sum(steg_lsb == 1)]
    ax4.bar(["LSB=0", "LSB=1"], counts_steg, color=["#FF9800", "#FFB74D"], edgecolor="white")
    ax4.set_title("LSB Distribution — Stego")
    ax4.set_ylabel("Sample count")
    total_s = counts_steg[0] + counts_steg[1]
    for i, v in enumerate(counts_steg):
        ax4.text(i, v + total_s * 0.01, f"{v/total_s*100:.1f}%", ha="center", fontsize=9)
    ax4.grid(True, alpha=0.3, axis="y")

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"[+] Report saved to: {output_path}")

    if show:
        matplotlib.use("TkAgg")
        plt.show()

    plt.close(fig)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python report.py <original.wav> <stego.wav> [output.png]")
        sys.exit(1)

    out = sys.argv[3] if len(sys.argv) > 3 else "stego_report.png"
    generate_report(sys.argv[1], sys.argv[2], output_path=out, show=False)
