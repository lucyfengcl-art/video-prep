"""Burn an .srt into a video as styled overlay text via libass.

Uses the keg-only `ffmpeg-full` from homebrew because the default `ffmpeg`
bottle is built without libass and has no `subtitles` filter.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

FFMPEG = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"

DEFAULT_FONT = "Noto Sans CJK SC Medium"
DEFAULT_FONT_SIZE = 12
DEFAULT_OUTLINE = 0
DEFAULT_MARGIN_V = 60


def burn_subs(
    video: Path,
    srt: Path,
    out: Path,
    *,
    font: str = DEFAULT_FONT,
    font_size: int = DEFAULT_FONT_SIZE,
    outline: int = DEFAULT_OUTLINE,
    margin_v: int = DEFAULT_MARGIN_V,
) -> Path:
    """Burn `srt` into `video`, writing to `out`. Audio is stream-copied."""
    video = Path(video).resolve()
    srt = Path(srt).resolve()
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    force_style = ",".join([
        f"FontName={font}",
        f"FontSize={font_size}",
        "PrimaryColour=&H00FFFFFF",
        "OutlineColour=&H00000000",
        f"Outline={outline}",
        "Shadow=0",
        f"MarginV={margin_v}",
    ])
    cmd = [
        FFMPEG,
        "-hide_banner", "-v", "error",
        "-i", str(video),
        "-vf", f"subtitles={srt}:force_style='{force_style}'",
        "-c:a", "copy",
        "-y", str(out),
    ]
    subprocess.run(cmd, check=True)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="video-prep-burn",
        description="Burn an .srt into a video as styled overlay text",
    )
    parser.add_argument("video", type=Path, help="Input video")
    parser.add_argument(
        "--srt",
        type=Path,
        help="Subtitle file (default: <video-stem>.srt next to the video)",
    )
    parser.add_argument(
        "-o", "--out",
        type=Path,
        help="Output path (default: <video-stem>.subbed<ext> next to video)",
    )
    parser.add_argument("--font", default=DEFAULT_FONT)
    parser.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE)
    parser.add_argument("--outline", type=int, default=DEFAULT_OUTLINE)
    parser.add_argument(
        "--margin-v",
        type=int,
        default=DEFAULT_MARGIN_V,
        help="Distance from bottom in subtitle units (default 60 ≈ 1/4 above bottom on portrait clips)",
    )
    args = parser.parse_args(argv)

    video = args.video
    if not video.is_file():
        print(f"error: video not found: {video}", file=sys.stderr)
        return 2
    srt = args.srt or video.with_suffix(".srt")
    if not srt.is_file():
        print(f"error: srt not found: {srt}", file=sys.stderr)
        return 2
    out = args.out or video.with_name(f"{video.stem}.subbed{video.suffix}")

    print(f"Burning {srt.name} into {video.name} -> {out.name}")
    print(
        f"  font={args.font!r} size={args.font_size} "
        f"outline={args.outline} marginV={args.margin_v}"
    )
    try:
        burn_subs(
            video, srt, out,
            font=args.font,
            font_size=args.font_size,
            outline=args.outline,
            margin_v=args.margin_v,
        )
    except subprocess.CalledProcessError as e:
        print(f"failed (ffmpeg exited {e.returncode})", file=sys.stderr)
        return 1

    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
