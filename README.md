# Audio Steganography — v0.2.0

**Adds SNR quality measurement.** Same LSB-0 embedding as v0.1.0, with a new metric to quantify how much the embedding degrades the carrier audio.

## What's new since v0.1.0

- `calculate_snr()` — computes the Signal-to-Noise Ratio (dB) between the original and stego audio, giving an objective measure of embedding transparency.

## Still limited

Image dimensions are still not stored in the stego file — extraction requires knowing the original size in advance. This is fixed in [v0.2.1](../v0.2.1).

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

Console output includes:

```
SNR Değeri: 48.32 dB
```

## How it works

Identical embedding formula to v0.1.0:

```
new_byte = (original_byte & 0xFE) | image_bit
```

SNR formula:

```
SNR (dB) = 10 * log10( Σ(original²) / Σ(noise²) )
```
where `noise = original_signal - modified_signal`. Higher SNR means the stego audio is closer to the original — less perceptible distortion.

## Requirements

```
pip install Pillow numpy
```

## Next version

[v0.2.1](../v0.2.1) embeds a 32-bit size header so extraction becomes fully self-contained.
