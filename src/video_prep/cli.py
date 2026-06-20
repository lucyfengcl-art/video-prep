"""CLI entry point for video-prep."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from video_prep.pipeline import process_clip, process_combined
from video_prep.transcribe import DEFAULT_MODEL

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


def _expand_inputs(inputs: list[Path]) -> list[Path]:
    """Expand directories to their video files, preserving caller-given order.

    Files passed explicitly keep argv order; directory contents are sorted by
    filename (so prefixing clips with `01-`, `02-`, ... gives a stable order).
    """
    files: list[Path] = []
    for p in inputs:
        if p.is_dir():
            files.extend(
                sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXTS)
            )
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(p)
    return files


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-prep",
        description=(
            "Cut silence, transcribe Mandarin to .srt, and speed up clips for "
            "Rednote. Outputs a CapCut-ready video + .srt (one per clip, or "
            "one combined output with --combine)."
        ),
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Video files or directories to process",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("./out"),
        help="Output directory (default: ./out)",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help=(
            "Concatenate inputs (in given/filename order) into one video "
            "before processing. Yields one .mp4 + one .srt."
        ),
    )
    parser.add_argument(
        "--name",
        default="combined",
        help='Base filename for --combine output (default: "combined")',
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.1,
        help="Playback speed factor (default: 1.1)",
    )
    parser.add_argument(
        "--margin",
        default="0.2s",
        help='Silence-cut padding around speech, e.g. "0.3s" (default: 0.2s)',
    )
    parser.add_argument(
        "--edit",
        default="audio",
        help='auto-editor edit expression (default: "audio")',
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="Whisper language code (default: zh)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"faster-whisper model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--keep-intermediates",
        action="store_true",
        help="Keep the work directory after processing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        clips = _expand_inputs(args.inputs)
    except FileNotFoundError as e:
        print(f"error: input not found: {e}", file=sys.stderr)
        return 2

    if not clips:
        print("error: no video files found in inputs", file=sys.stderr)
        return 2

    common = dict(
        speed=args.speed,
        margin=args.margin,
        edit_expression=args.edit,
        language=args.language,
        model=args.model,
        keep_intermediates=args.keep_intermediates,
    )

    if args.combine:
        print(f"Combining {len(clips)} clip(s) -> {args.out}/{args.name}.*")
        for i, src in enumerate(clips, 1):
            print(f"  [{i}] {src.name}")
        try:
            result = process_combined(clips, args.out, name=args.name, **common)
        except subprocess.CalledProcessError as e:
            print(f"failed ({e.cmd[0]} exited {e.returncode})", file=sys.stderr)
            return 1
        print(f"\n-> {result.video}")
        print(f"-> {result.srt}")
        print(f"\nDone. Drag {result.video.name} + {result.srt.name} into CapCut.")
        return 0

    print(f"Processing {len(clips)} clip(s) -> {args.out}")
    for i, src in enumerate(clips, 1):
        print(f"\n[{i}/{len(clips)}] {src.name}")
        try:
            result = process_clip(src, args.out, **common)
        except subprocess.CalledProcessError as e:
            print(f"  failed ({e.cmd[0]} exited {e.returncode})", file=sys.stderr)
            return 1
        print(f"  -> {result.video.name}")
        print(f"  -> {result.srt.name}")

    print(f"\nDone. Drag {args.out}/ into CapCut.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
