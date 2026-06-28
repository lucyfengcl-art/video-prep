"""CLI entry point for video-prep."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from video_prep.pipeline import process_clip, process_combined
from video_prep.transcribe import DEFAULT_MODEL

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


def natural_key(name: str) -> list:
    """Sort key that orders embedded numbers numerically, not lexically.

    Plain `sorted()` orders `1, 10, 11, 2, 3` because it compares strings
    character by character. This splits on digit runs so `2.mov` sorts before
    `10.mov` -- i.e. clips named `1, 2, ... 10, 11` merge in the order you'd
    expect, with no need to zero-pad them to `01, 02, ...`.
    """
    return [
        int(tok) if tok.isdigit() else tok.lower()
        for tok in re.split(r"(\d+)", name)
    ]


def _expand_inputs(inputs: list[Path]) -> list[Path]:
    """Expand directories to their video files, preserving caller-given order.

    Files passed explicitly keep argv order; directory contents are sorted by
    `natural_key`, so clips named `1.mov, 2.mov, ... 10.mov` merge in numeric
    order without zero-padding.
    """
    files: list[Path] = []
    for p in inputs:
        if p.is_dir():
            files.extend(
                sorted(
                    (f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXTS),
                    key=lambda f: natural_key(f.name),
                )
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
        help="Whisper language code, or 'auto' to detect (default: zh)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"faster-whisper model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=-1,
        help="Split subtitle cues longer than this many chars (default: -1 = auto "
             "by language: 20 for Chinese, 42 for spaced languages; 0 disables)",
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
        max_chars=args.max_chars,
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
