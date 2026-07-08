# Audio Steganography — v0.2.1

**Adds a self-contained size header.** Extraction no longer requires knowing the image dimensions in advance — width and height are embedded directly into the stego audio.

## What's new since v0.2.0

- A 32-bit header (16-bit width + 16-bit height) is prepended to the image bitstream before embedding.
- `extract_bits_from_audio()` now takes only the audio path — it reads the header first, decodes the dimensions, then extracts exactly the right number of payload bits.
- `hide_data_in_audio()` now takes the image path directly instead of a pre-computed bit list, since it needs to read the image dimensions itself.

## Stego layout

```
bytes 0–31   → 32-bit header (16-bit width || 16-bit height), 1 bit per byte (LSB)
bytes 32+    → image RGB bits, 1 bit per byte (LSB)
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

No manual size input needed anymore — `extract_bits_from_audio()` returns `(extracted_bits, image_size)` directly.

## How it works

Embedding formula is unchanged from v0.1.0/v0.2.0 (still LSB-0):

```
new_byte = (original_byte & 0xFE) | bit
```

Header encoding:

```python
width_bits  = format(width,  '016b')
height_bits = format(height, '016b')
size_bits   = list(width_bits + height_bits)   # 32 bits total
```

## Requirements

```
pip install Pillow numpy
```

## Next version

[v0.2.2](../v0.2.2) moves embedding from bit position 0 to bit position 2 (LSB+2) and adds the ENG metric alongside SNR.
