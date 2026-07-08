"""
cli.py — Command-Line Interface
================================
Unified CLI for all audio steganography operations.

Commands:
    embed       Hide an image in a WAV/MP3/FLAC audio file.
    extract     Recover a hidden image from a stego WAV file.
    analyse     Run RS Analysis + SPA steganalysis on a WAV file.
    capacity    Check how large an image fits in a given audio file.
    benchmark   Run a full LSB-variant benchmark suite.
    report      Generate a visual quality report (PNG).

Examples:
    python cli.py embed   -a cover.wav   -i secret.png -o stego.wav --lsb 2 --ecc --password s3cr3t
    python cli.py extract -a stego.wav   -o recovered.png            --lsb 2 --ecc --password s3cr3t
    python cli.py analyse  -a stego.wav
    python cli.py capacity -a cover.wav  -i secret.png --ecc --enc
    python cli.py benchmark -a cover.wav -i secret.png --csv results.csv
    python cli.py report   -a cover.wav  -s stego.wav  --out report.png
"""

import argparse
import sys


def cmd_embed(args: argparse.Namespace) -> None:
    from formats  import load_as_wav, cleanup_temp
    from embedder import embed

    tmp = None
    try:
        # Auto-convert non-WAV inputs
        if not args.audio.lower().endswith(".wav"):
            print(f"[*] Converting '{args.audio}' to temporary WAV…")
            tmp = load_as_wav(args.audio)
            audio_src = tmp
        else:
            audio_src = args.audio

        result = embed(
            audio_path  = audio_src,
            output_path = args.output,
            image_path  = args.image,
            lsb_depth   = args.lsb,
            password    = args.password,
            use_ecc     = args.ecc,
            prng_seed   = args.seed,
        )
        print(f"\n[+] Done.  Fill ratio: {result['bits_embedded']/result['capacity_bits']*100:.1f}%")
    finally:
        if tmp:
            cleanup_temp(tmp)


def cmd_extract(args: argparse.Namespace) -> None:
    from embedder import extract

    extract(
        audio_path  = args.audio,
        output_path = args.output,
        lsb_depth   = args.lsb,
        password    = args.password,
        prng_seed   = args.seed,
    )


def cmd_analyse(args: argparse.Namespace) -> None:
    from steganalysis import analyse
    analyse(args.audio)


def cmd_capacity(args: argparse.Namespace) -> None:
    from capacity import check_fit, max_image_size
    check_fit(args.audio, args.image, use_ecc=args.ecc, encrypted=args.enc)
    for depth in (1, 2, 3):
        max_image_size(args.audio, lsb_depth=depth, use_ecc=args.ecc, encrypted=args.enc)


def cmd_benchmark(args: argparse.Namespace) -> None:
    from benchmark_suite import run_benchmark
    run_benchmark(args.audio, args.image, output_csv=args.csv)


def cmd_report(args: argparse.Namespace) -> None:
    from report import generate_report
    generate_report(args.audio, args.stego, output_path=args.out, show=args.show)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stego",
        description="Audio Steganography — hide images in WAV/MP3/FLAC files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # --- embed ---
    p_embed = sub.add_parser("embed", help="Hide an image in an audio file.")
    p_embed.add_argument("-a", "--audio",    required=True,  help="Carrier audio file (WAV/MP3/FLAC)")
    p_embed.add_argument("-i", "--image",    required=True,  help="Image to hide (PNG/JPG/…)")
    p_embed.add_argument("-o", "--output",   required=True,  help="Output stego WAV file")
    p_embed.add_argument("--lsb",            type=int, default=1, choices=[1, 2, 3],
                         help="LSB depth (default: 1)")
    p_embed.add_argument("--password",       default=None,   help="AES-256-GCM encryption password")
    p_embed.add_argument("--ecc",            action="store_true", help="Enable Reed-Solomon ECC")
    p_embed.add_argument("--seed",           type=int, default=None,
                         help="PRNG seed for random byte selection (omit for sequential)")
    p_embed.set_defaults(func=cmd_embed)

    # --- extract ---
    p_extr = sub.add_parser("extract", help="Recover a hidden image from a stego WAV.")
    p_extr.add_argument("-a", "--audio",    required=True,  help="Stego WAV file")
    p_extr.add_argument("-o", "--output",   required=True,  help="Output image path (PNG)")
    p_extr.add_argument("--lsb",            type=int, default=1, choices=[1, 2, 3],
                         help="LSB depth used during embedding (default: 1)")
    p_extr.add_argument("--password",       default=None,   help="Decryption password")
    p_extr.add_argument("--seed",           type=int, default=None,
                         help="PRNG seed used during embedding")
    p_extr.set_defaults(func=cmd_extract)

    # --- analyse ---
    p_anal = sub.add_parser("analyse", help="Run RS + SPA steganalysis on a WAV file.")
    p_anal.add_argument("-a", "--audio",    required=True,  help="WAV file to analyse")
    p_anal.set_defaults(func=cmd_analyse)

    # --- capacity ---
    p_cap = sub.add_parser("capacity", help="Check how large an image fits in an audio file.")
    p_cap.add_argument("-a", "--audio",     required=True,  help="Carrier WAV file")
    p_cap.add_argument("-i", "--image",     required=True,  help="Image to check")
    p_cap.add_argument("--ecc",             action="store_true", help="Include ECC overhead")
    p_cap.add_argument("--enc",             action="store_true", help="Include AES-GCM overhead")
    p_cap.set_defaults(func=cmd_capacity)

    # --- benchmark ---
    p_bench = sub.add_parser("benchmark", help="Run full LSB variant benchmark.")
    p_bench.add_argument("-a", "--audio",   required=True,  help="Carrier WAV file")
    p_bench.add_argument("-i", "--image",   required=True,  help="Image to embed")
    p_bench.add_argument("--csv",           default=None,   help="Save results to CSV")
    p_bench.set_defaults(func=cmd_benchmark)

    # --- report ---
    p_rep = sub.add_parser("report", help="Generate a visual quality report.")
    p_rep.add_argument("-a", "--audio",     required=True,  help="Original (cover) WAV file")
    p_rep.add_argument("-s", "--stego",     required=True,  help="Stego WAV file")
    p_rep.add_argument("--out",             default="stego_report.png",
                         help="Output PNG path (default: stego_report.png)")
    p_rep.add_argument("--show",            action="store_true",
                         help="Open report in interactive window")
    p_rep.set_defaults(func=cmd_report)

    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
