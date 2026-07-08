# Audio Steganography — v0.2.2

**Switches to LSB+2 bit-position embedding and adds the ENG metric.** This is the final v0.2.x release before the major v0.3.0 rewrite.

## What's new since v0.2.1

- Embedding now targets **bit position 2** of each byte instead of bit position 0 (the classic LSB). This is referred to as "LSB+2" throughout the project.
- `calculate_snr()` now handles edge cases: returns `+inf` when no noise was introduced, `-inf` when the original signal has zero power (silent audio), instead of raising a division error.
- `calculate_eng()` — a new Energy-to-Noise Gain metric, reported alongside SNR.

## Stego layout

Same header + payload structure as v0.2.1, but every bit is now written to **bit position 2** instead of bit position 0:

```
bytes 0–31   → 32-bit header, 1 bit per byte at position 2
bytes 32+    → image RGB bits, 1 bit per byte at position 2
```

## Usage

```python
python hide_data.py
```

Edit paths at the bottom of the script:

```python
image_path = 'input_image.png'
audio_input_path = 'input.wav'
audio_output_path = 'output.wav'
extracted_image_path = 'extracted_image.png'
```

Console output now reports both metrics:

```
SNR Değeri: 41.07 dB
ENG Değeri: 12809.55
```

## How it works

Embedding formula (LSB+2):

```
new_byte = (original_byte & 0xFB) | (bit << 2)
```

`0xFB` (`11111011` in binary) clears bit 2 before inserting the payload bit shifted into that position.

Extraction reverses this:

```python
bit = (frame_bytes[i] >> 2) & 1
```

ENG formula:

```
ENG = Σ(original²) / Σ((original - modified)²)
```

A higher ENG means less noise power relative to the signal's total energy — a linear-scale complement to the SNR metric.

## Why LSB+2 instead of LSB-0?

Bit position 0 changes are the most likely to be flagged by simple LSB steganalysis tools (histogram/RS analysis), because it is the position attackers check first. Moving to bit position 2 trades a slightly higher noise floor for reduced detectability against naive detectors — though it remains vulnerable to more advanced steganalysis (addressed later in v0.3.0).

## Requirements

```
pip install Pillow numpy
```

## Next version

[v0.3.0](../v0.3.0) is a full production-grade rewrite: AES-256-GCM encryption, Reed-Solomon error correction, selectable 1/2/3-bit LSB depth, PRNG-based byte distribution, WAV/MP3/FLAC support, RS/SPA steganalysis testing, a CLI, and a Tkinter GUI.
