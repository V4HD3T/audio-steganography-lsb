# Changelog

All notable changes to this project are documented in this file. Entries below
are sourced from the project's own README "Version History" table — git tags
only exist from v0.3.0 onward; v0.1.0–v0.2.2 predate consistent tagging and
their exact commit boundaries are ambiguous, so no retroactive tags were added
for them.

## [0.3.1] - Changelog

Added this CHANGELOG.md, reconstructed from the README's "Version History"
table. No code changes.

## [0.3.0] - 2026-07-20

Complete rewrite: selectable 1/2/3-bit LSB depth, PRNG byte distribution,
AES-256-GCM encryption, Reed-Solomon ECC, WAV/MP3/FLAC support, RS Analysis +
SPA steganalysis testing, capacity pre-flight checks, automated benchmarking,
visual quality reports, a CLI, and a Tkinter GUI.

## [0.2.2]

Switched embedding from bit position 0 to bit position 2 ("LSB+2") to reduce
detectability against naive LSB steganalysis. Added the ENG (Energy-to-Noise
Gain) metric alongside SNR, plus robust handling of zero-power edge cases.

## [0.2.1]

Embedded a 32-bit size header (16-bit width + 16-bit height) directly into the
stego audio, making extraction fully self-contained — no more manual
dimension input.

## [0.2.0]

Added the SNR quality metric (`calculate_snr`) to objectively measure how much
embedding degrades the carrier audio. Still no self-contained size header.

## [0.1.0]

Initial proof of concept. Basic LSB-0 embedding (`steganography.py`).
Required the caller to know image dimensions in advance for extraction.
