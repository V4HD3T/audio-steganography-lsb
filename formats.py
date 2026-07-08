"""
formats.py — Multi-Format Audio Support
========================================
Provides format-transparent loading and saving for WAV, MP3, and FLAC files.

Because LSB steganography requires uncompressed PCM data, any compressed
input is converted to a temporary WAV before embedding, and the final stego
output is always saved as WAV (the only lossless container supported here).

Supported input formats:  WAV, MP3, FLAC
Supported output format:  WAV (lossless — required for LSB integrity)

Why output is always WAV:
    MP3 and AAC use lossy compression that discards LSB-level detail.
    Re-encoding a stego file to MP3 would destroy all hidden data.

Dependencies:
    pip install pydub
    # Also requires ffmpeg on PATH for MP3/FLAC:
    # macOS:   brew install ffmpeg
    # Ubuntu:  sudo apt install ffmpeg
    # Windows: https://ffmpeg.org/download.html
"""

import os
import tempfile
from pydub import AudioSegment

# Maps file extensions to pydub format strings
_FORMAT_MAP = {
    ".wav":  "wav",
    ".mp3":  "mp3",
    ".flac": "flac",
}


def load_as_wav(input_path: str) -> str:
    """Load any supported audio file and return a path to a temporary WAV copy.

    If the input is already a WAV file, a copy is still made so the caller
    can freely modify it without affecting the original.

    Args:
        input_path: Path to the source audio file (WAV, MP3, or FLAC).

    Returns:
        Path to a temporary WAV file.  The caller is responsible for deleting
        it when done (use in a try/finally block or tempfile.NamedTemporaryFile).

    Raises:
        ValueError: If the file extension is not supported.
        FileNotFoundError: If the input file does not exist.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    ext = os.path.splitext(input_path)[1].lower()
    if ext not in _FORMAT_MAP:
        raise ValueError(
            f"Unsupported format '{ext}'. Supported: {list(_FORMAT_MAP.keys())}"
        )

    audio = AudioSegment.from_file(input_path, format=_FORMAT_MAP[ext])

    # Write to a named temp file that persists after close (delete=False)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    audio.export(tmp.name, format="wav")

    print(f"[*] Loaded '{os.path.basename(input_path)}' → temporary WAV: {tmp.name}")
    return tmp.name


def get_audio_info(input_path: str) -> dict:
    """Return basic metadata for any supported audio file.

    Args:
        input_path: Path to an audio file (WAV, MP3, or FLAC).

    Returns:
        Dict with keys: format, channels, sample_width_bytes,
        frame_rate_hz, duration_seconds, file_size_bytes.
    """
    ext   = os.path.splitext(input_path)[1].lower()
    audio = AudioSegment.from_file(input_path, format=_FORMAT_MAP.get(ext, ext.lstrip(".")))

    return {
        "format":              _FORMAT_MAP.get(ext, "unknown"),
        "channels":            audio.channels,
        "sample_width_bytes":  audio.sample_width,
        "frame_rate_hz":       audio.frame_rate,
        "duration_seconds":    len(audio) / 1000.0,
        "file_size_bytes":     os.path.getsize(input_path),
    }


def cleanup_temp(path: str) -> None:
    """Delete a temporary file created by load_as_wav().

    Args:
        path: Path to the temporary file to remove.
    """
    try:
        os.remove(path)
        print(f"[*] Removed temporary file: {path}")
    except OSError:
        pass   # Already deleted or never existed


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python formats.py <audio_file>")
        sys.exit(1)

    info = get_audio_info(sys.argv[1])
    print("\n[Audio Info]")
    for key, val in info.items():
        print(f"  {key:<22} {val}")

    tmp_wav = load_as_wav(sys.argv[1])
    print(f"[+] Temporary WAV ready at: {tmp_wav}")
    cleanup_temp(tmp_wav)
