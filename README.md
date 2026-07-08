# Audio Steganography — v0.3.0

Hide an RGB image inside a WAV/MP3/FLAC audio file with AES-256-GCM encryption,
Reed-Solomon error correction, and PRNG-based byte selection — then recover it
without any audible quality loss to the carrier audio.

This is a full production-grade rewrite building on four earlier iterations
(v0.1.0 → v0.2.2). See [Version History](#version-history) below for what
each prior release contributed.

---

## Table of Contents

- [Version History](#version-history)
- [What's New in v0.3.0](#whats-new-in-v030)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Usage — CLI](#usage--cli)
- [Usage — GUI](#usage--gui)
- [Usage — Python API](#usage--python-api)
- [Quality Metrics](#quality-metrics)
- [Steganalysis Resistance](#steganalysis-resistance)
- [Capacity Estimation](#capacity-estimation)
- [Limitations](#limitations)
- [References](#references)

---

## Version History

| Version | Key contribution |
|---------|-------------------|
| **v0.1.0** | Initial proof of concept. Basic LSB-0 embedding (`steganography.py`). Required the caller to know image dimensions in advance for extraction. |
| **v0.2.0** | Added the SNR quality metric (`calculate_snr`) to objectively measure how much embedding degrades the carrier audio. Still no self-contained size header. |
| **v0.2.1** | Embedded a 32-bit size header (16-bit width + 16-bit height) directly into the stego audio, making extraction fully self-contained — no more manual dimension input. |
| **v0.2.2** | Switched embedding from bit position 0 to bit position 2 ("LSB+2") to reduce detectability against naive LSB steganalysis. Added the ENG (Energy-to-Noise Gain) metric alongside SNR, plus robust handling of zero-power edge cases. |
| **v0.3.0** *(this release)* | Complete rewrite: selectable 1/2/3-bit LSB depth, PRNG byte distribution, AES-256-GCM encryption, Reed-Solomon ECC, WAV/MP3/FLAC support, RS Analysis + SPA steganalysis testing, capacity pre-flight checks, automated benchmarking, visual quality reports, a CLI, and a Tkinter GUI. |

Each earlier version's script is preserved in the repository root (`steganography.py`, and the versioned `hide_data.py` history via git tags `v0.1.0`–`v0.2.2`) so the project's evolution stays visible.

---

## What's New in v0.3.0

| Feature | v0.1.0–v0.2.2 | v0.3.0 |
|---|---|---|
| LSB depth | 1 bit fixed (position 0, then position 2 from v0.2.2) | 1 / 2 / 3 bits selectable |
| Byte selection | Sequential | Sequential or PRNG (seeded) |
| Encryption | None | AES-256-GCM (PBKDF2 key derivation) |
| Error correction | None | Reed-Solomon (16 byte errors / block) |
| Format support | WAV only | WAV, MP3, FLAC |
| Steganalysis | None | RS Analysis + SPA |
| Capacity check | None | Pre-flight check with overhead breakdown |
| Visual report | None | Waveform, diff signal, LSB histogram |
| Interface | Script only | CLI + Tkinter GUI |

---

## Project Structure

```
audio_steganography/
├── crypto.py            AES-256-GCM encryption / decryption
├── ecc.py                Reed-Solomon error correction
├── embedder.py            Core multi-bit LSB embedder / extractor
├── formats.py             WAV / MP3 / FLAC loading and conversion
├── steganalysis.py        RS Analysis and SPA steganalysis
├── capacity.py            Pre-flight capacity calculator
├── benchmark_suite.py     Automated LSB-variant benchmark
├── report.py              Matplotlib visual quality report
├── cli.py                 Unified command-line interface
├── gui.py                 Tkinter desktop GUI
├── requirements.txt
└── README.md
```

---

## How It Works

### Stego frame layout (per byte index `i`)

```
i = 0 … H-1      64-bit self-describing header
i = H …           payload bits (ECC-encoded → AES-encrypted → image RGB)
```

The 64-bit header contains: width (16 bits) | height (16 bits) | flags (8 bits) | payload_bit_length (24 bits). This extends the 32-bit header introduced back in v0.2.1 with flag bits describing which optional layers (encryption, ECC, LSB depth) were used.

### Embedding pipeline

```
image bytes
    → [optional] Reed-Solomon encode  (+14 % size, corrects 16 bytes/block)
    → [optional] AES-256-GCM encrypt  (+44 bytes overhead)
    → prepend 64-bit header
    → write bits into selected audio bytes at chosen bit-position
    → save stego WAV
```

### Bit-position table

| LSB depth | Bits/byte | Capacity multiplier | Typical SNR drop |
|-----------|-----------|---------------------|-------------------|
| 1         | 1         | 1×                  | ~50 dB            |
| 2         | 2         | 2×                  | ~44 dB            |
| 3         | 3         | 3×                  | ~38 dB            |

The LSB+2 position introduced in v0.2.2 remains available as one of the three selectable depths, alongside classic LSB-0 and the new 3-bit mode.

### PRNG byte selection

When `--seed N` is supplied, bytes are chosen in a pseudo-random order
(seeded Fisher-Yates shuffle) instead of the sequential order used in every
prior version. This makes sequential steganalysis tools unable to detect
the embedding pattern — both the sender and receiver must use the same seed.

---

## Installation

Python 3.10+ required.

```bash
git clone https://github.com/your-username/audio-steganography.git
cd audio-steganography
pip install -r requirements.txt
```

For MP3/FLAC support also install **ffmpeg**:

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows — download from https://ffmpeg.org/download.html
```

For the GUI on Ubuntu:

```bash
sudo apt install python3-tk
```

---

## Usage — CLI

```bash
# Embed (AES + ECC + PRNG, LSB-2)
python cli.py embed \
    -a cover.wav -i secret.png -o stego.wav \
    --lsb 2 --password "my_secret" --ecc --seed 42

# Extract
python cli.py extract \
    -a stego.wav -o recovered.png \
    --lsb 2 --password "my_secret" --seed 42

# Steganalysis
python cli.py analyse -a stego.wav

# Capacity check
python cli.py capacity -a cover.wav -i secret.png --ecc --enc

# Benchmark all LSB variants
python cli.py benchmark -a cover.wav -i secret.png --csv results.csv

# Visual report
python cli.py report -a cover.wav -s stego.wav --out report.png
```

---

## Usage — GUI

```bash
python gui.py
```

Four tabs: **Embed**, **Extract**, **Analyse**, **Capacity**.
All operations run in a background thread; output streams to the log panel.

---

## Usage — Python API

```python
from embedder import embed, extract

# Embed
embed(
    audio_path  = "cover.wav",
    output_path = "stego.wav",
    image_path  = "secret.png",
    lsb_depth   = 2,
    password    = "my_secret",
    use_ecc     = True,
    prng_seed   = 42,
)

# Extract
extract(
    audio_path  = "stego.wav",
    output_path = "recovered.png",
    lsb_depth   = 2,
    password    = "my_secret",
    prng_seed   = 42,
)
```

```python
from steganalysis import analyse
analyse("stego.wav")

from report import generate_report
generate_report("cover.wav", "stego.wav", output_path="report.png")

from capacity import check_fit
check_fit("cover.wav", "secret.png", use_ecc=True, encrypted=True)
```

---

## Quality Metrics

| Metric | Formula | Interpretation | Introduced in |
|--------|---------|-----------------|----------------|
| SNR    | 10·log10(Σs² / Σn²) | dB; higher = less distortion | v0.2.0 |
| ENG    | Σs² / Σ(s−s̃)²       | Linear; higher = less noise  | v0.2.2 |
| PSNR   | 20·log10(255 / RMSE) | dB; > 40 dB = excellent recovery | v0.3.0 |
| BER    | error_bits / total_bits | 0.0 = perfect recovery | v0.3.0 |

---

## Steganalysis Resistance

`steganalysis.py` implements two classical detection methods:

**RS Analysis** — estimates fill ratio from Regular/Singular group distributions.
A value near 0 % suggests a clean file; above ~5 % suggests embedding.

**SPA (Sample Pair Analysis)** — exploits parity asymmetry in consecutive sample pairs.

PRNG byte selection (`--seed`) significantly reduces both RS and SPA detection rates
because the modified bytes no longer form a predictable sequential pattern — unlike
every version prior to v0.3.0, which embedded strictly sequentially.

---

## Capacity Estimation

```
capacity_bits = num_frames × num_channels × sample_width_bytes × lsb_depth
```

For a stereo 16-bit 44100 Hz 60-second WAV at LSB-2:
```
44100 × 60 × 2 × 2 × 2 = 21,168,000 bits ≈ 2.6 MB payload
```

An RGB 600×400 image requires:
```
600 × 400 × 3 × 8 = 5,760,000 bits  (+64 header + ECC +14% + AES +44 bytes)
```

---

## Limitations

- Output is always WAV — MP3/AAC re-encoding destroys LSB data.
- LSB steganography is not resistant to all steganalysis tools (e.g. StegExpose).
  Use PRNG seed + AES encryption for stronger security.
- This project is intended for **educational purposes** only.

---

## References

1. Fridrich, J., Goljan, M., Du, R. — *Reliable Detection of LSB Steganography in Color and Grayscale Images.* ACM Multimedia & Security Workshop, 2001.
2. Lu, P. et al. — *An Improved Sample Pairs Method for Detection of LSB Embedding.* Information Hiding Workshop, 2004.
3. Cvejic, N., Seppanen, T. — *Increasing the Capacity of LSB-Based Audio Steganography.* IEEE, 2004.
4. ITU-R BS.1387 — *Method for Objective Measurements of Perceived Audio Quality.*
5. NIST SP 800-132 — *Recommendation for Password-Based Key Derivation.*
