"""Burn an .srt into a video as styled overlay text via libass.

Uses the keg-only `ffmpeg-full` from homebrew because the default `ffmpeg`
bottle is built without libass and has no `subtitles` filter.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from video_prep.media import probe_video_size
from video_prep.srt import TIMESTAMP_RE, _iter_blocks, _ts_to_ms

FFMPEG = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"

DEFAULT_FONT = "Noto Sans CJK SC Medium"
DEFAULT_FONT_SIZE = 12
DEFAULT_OUTLINE = 0
DEFAULT_MARGIN_V = 60


def subtitle_fraction(value: str) -> float:
    try:
        fraction = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a number between 0 and 1") from exc
    if not 0 < fraction < 1:
        raise argparse.ArgumentTypeError("expected a number between 0 and 1")
    return fraction


def _ass_ts(ms: int) -> str:
    centiseconds = max(0, round(ms / 10))
    hours, rem = divmod(centiseconds, 360_000)
    minutes, rem = divmod(rem, 6_000)
    seconds, centiseconds = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _ass_text(lines: list[str]) -> str:
    escaped = [
        line.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
        for line in lines
    ]
    return r"\N".join(escaped)


def srt_to_ass(
    srt: Path,
    out: Path,
    *,
    width: int,
    height: int,
    font: str = DEFAULT_FONT,
    font_size: int = DEFAULT_FONT_SIZE,
    outline: int = DEFAULT_OUTLINE,
    margin_v: int = DEFAULT_MARGIN_V,
    subtitle_y: float | None = None,
    bold: bool = False,
    background: bool = False,
    box_ranges: list[tuple[float, float]] | None = None,
) -> Path:
    """Convert SRT to ASS with stable portrait-aware styling."""
    if subtitle_y is not None and not 0 < subtitle_y < 1:
        raise ValueError("subtitle_y must be between 0 and 1")

    play_res_y = 288
    play_res_x = max(1, round(play_res_y * width / height))
    ass_margin_v = (
        round((1 - subtitle_y) * play_res_y)
        if subtitle_y is not None else margin_v
    )
    bold_value = -1 if bold else 0
    box_padding = max(1, outline + 1)
    ranges = box_ranges or []

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {play_res_x}",
        f"PlayResY: {play_res_y}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{font_size},&H00FFFFFF,&H000000FF,&H00000000,"
        f"&H00000000,{bold_value},0,0,0,100,100,0,0,1,{outline},0,2,10,10,"
        f"{ass_margin_v},1",
        f"Style: Box,{font},{font_size},&H00FFFFFF,&H000000FF,&H00000000,"
        f"&H00000000,{bold_value},0,0,0,100,100,0,0,3,{box_padding},0,2,10,10,"
        f"{ass_margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for time_line, body in _iter_blocks(Path(srt).read_text(encoding="utf-8")):
        matches = list(TIMESTAMP_RE.finditer(time_line))
        if len(matches) != 2:
            continue
        start_ms = _ts_to_ms(*matches[0].groups())
        end_ms = _ts_to_ms(*matches[1].groups())
        start_s, end_s = start_ms / 1000, end_ms / 1000
        boxed = background or any(start_s < box_end and end_s > box_start
                                  for box_start, box_end in ranges)
        style = "Box" if boxed else "Default"
        lines.append(
            f"Dialogue: 0,{_ass_ts(start_ms)},{_ass_ts(end_ms)},{style},,0,0,0,,"
            f"{_ass_text(body)}"
        )

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def burn_subs(
    video: Path,
    srt: Path,
    out: Path,
    *,
    font: str = DEFAULT_FONT,
    font_size: int = DEFAULT_FONT_SIZE,
    outline: int = DEFAULT_OUTLINE,
    margin_v: int = DEFAULT_MARGIN_V,
    subtitle_y: float | None = None,
    bold: bool = False,
    background: bool = False,
    box_ranges: list[tuple[float, float]] | None = None,
) -> Path:
    """Burn `srt` into `video`, writing to `out`. Audio is stream-copied."""
    video = Path(video).resolve()
    srt = Path(srt).resolve()
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="video-prep-subs-") as temp_dir:
        subtitle_source = srt
        if srt.suffix.lower() != ".ass":
            width, height = probe_video_size(video)
            subtitle_source = srt_to_ass(
                srt, Path(temp_dir) / "subtitles.ass",
                width=width, height=height, font=font, font_size=font_size,
                outline=outline, margin_v=margin_v, subtitle_y=subtitle_y,
                bold=bold, background=background, box_ranges=box_ranges,
            )
        cmd = [
            FFMPEG,
            "-hide_banner", "-v", "error",
            "-i", str(video),
            "-vf", f"subtitles={subtitle_source}",
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
    parser.add_argument("--bold", action="store_true")
    parser.add_argument(
        "--background", action="store_true",
        help="Render every subtitle on an opaque black background",
    )
    parser.add_argument(
        "--subtitle-y", type=subtitle_fraction,
        help="Vertical baseline as a fraction from the top (for example 0.75)",
    )
    parser.add_argument(
        "--box-range", action="append", default=[], metavar="START:END",
        help="Apply a black background in this time range in seconds (repeatable)",
    )
    parser.add_argument(
        "--margin-v",
        type=int,
        default=DEFAULT_MARGIN_V,
        help="Distance from bottom in subtitle units (default 60 ≈ 1/4 above bottom on portrait clips)",
    )
    args = parser.parse_args(argv)

    try:
        box_ranges = [tuple(map(float, value.split(":", 1))) for value in args.box_range]
    except ValueError:
        parser.error("--box-range must be START:END in seconds")
    if any(start < 0 or end <= start for start, end in box_ranges):
        parser.error("--box-range requires 0 <= START < END")

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
            subtitle_y=args.subtitle_y,
            bold=args.bold,
            background=args.background,
            box_ranges=box_ranges,
        )
    except subprocess.CalledProcessError as e:
        print(f"failed (ffmpeg exited {e.returncode})", file=sys.stderr)
        return 1

    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
