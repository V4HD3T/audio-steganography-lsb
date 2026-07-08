# Audio Steganography — v0.1.0

**Initial proof of concept.** Hides an RGB image inside a WAV audio file using basic Least Significant Bit (LSB) substitution.

## Features

- Convert an image to a flat bit array (R, G, B channels, 8 bits each).
- Embed each bit into the LSB of a WAV frame byte.
- Extract bits back and reconstruct the image.

## Limitation

The extraction step requires the original image dimensions to be known in advance — no size information is stored inside the audio file. The width/height must be hardcoded or passed manually by the caller.

## Usage

```python
python steganography.py
```

Edit the paths at the bottom of the script before running:

```python
image_path = 'input_image.png'
audio_input_path = 'input.wav'
audio_output_path = 'output.wav'
extracted_image_path = 'extracted_image.png'
```

## How it works

```
new_byte = (original_byte & 0xFE) | image_bit
```

Each audio sample byte has its least significant bit replaced with one payload bit. The `0xFE` mask clears bit 0 before inserting the new value.

## Requirements

```
pip install Pillow numpy
```

## Next version

[v0.2.0](../v0.2.0) removes the manual dimension requirement by embedding a size header directly into the audio file.
