"""Assemble recorded segments into one finished vertical (9:16) video.

Drop the recordings into a folder named ``NN-<kind>-<label>.<ext>`` and this
stitches them, in ``NN`` order, into a single 1080x1920 mp4 ready for Rednote.

``kind`` picks the treatment:

- ``talk``   -- you on camera. Runs the full pipeline (cut silence -> transcribe
  -> speed up -> rescale .srt), crops the (usually horizontal) camera frame to
  9:16, then burns the subtitles in.
- ``screen`` -- a screen recording (slides / Claude Code / terminal demo). Just
  normalized to 9:16; no silence-cut, speed change, or transcription.

All segments are normalized to the same codec/resolution/fps/audio so the final
concat is a fast lossless stream-copy.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from video_prep.burn import burn_subs
from video_prep.cli import VIDEO_EXTS
from video_prep.concat import concat_clips
from video_prep.pipeline import process_clip
from video_prep.transcribe import DEFAULT_MODEL

WIDTH = 1080
HEIGHT = 1920
FPS = 30

# NN-kind-label, e.g. "01-talk-intro", "02-screen-slide1"
NAME_RE = re.compile(r"^(?P<order>\d+)-(?P<kind>talk|screen)(?:-.*)?$", re.IGNORECASE)


@dataclass
class Segment:
    path: Path
    order: int
    kind: str  # "talk" | "screen"


def discover_segments(edit_dir: Path) -> list[Segment]:
    """Find and order the segment files in `edit_dir`.

    Returns segments sorted by their NN prefix. Raises if a video file doesn't
    follow the NN-kind-label convention, so a typo'd name fails loudly instead
    of being silently dropped from the final cut.
    """
    edit_dir = Path(edit_dir)
    if not edit_dir.is_dir():
        raise NotADirectoryError(edit_dir)

    segments: list[Segment] = []
    for f in sorted(edit_dir.iterdir()):
        if f.suffix.lower() not in VIDEO_EXTS:
            continue
        m = NAME_RE.match(f.stem)
        if not m:
            raise ValueError(
                f"{f.name!r} doesn't match NN-kind-label "
                f"(e.g. 01-talk-intro{f.suffix}, 02-screen-slide1{f.suffix}); "
                "kind must be 'talk' or 'screen'"
            )
        segments.append(
            Segment(path=f, order=int(m["order"]), kind=m["kind"].lower())
        )

    segments.sort(key=lambda s: (s.order, s.path.name))
    return segments


def _has_audio(src: Path) -> bool:
    """True if `src` has at least one audio stream (screen recordings may not)."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(src),
        ],
        capture_output=True, text=True,
    )
    return bool(out.stdout.strip())


def normalize(src: Path, dst: Path, *, mode: str) -> Path:
    """Re-encode `src` to a uniform 1080x1920 / 30fps / h264 + 48k stereo aac.

    `mode="cover"` scales to fill then center-crops (for a horizontal camera
    frame); `mode="contain"` scales to fit then pads (for a screen recording of
    a different aspect). Silent video gets a generated silent audio track so
    every segment has a matching audio stream for the final concat.
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if mode == "cover":
        vf = (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT}"
        )
    elif mode == "contain":
        vf = (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black"
        )
    else:
        raise ValueError(f"unknown mode: {mode!r}")
    vf += f",fps={FPS},setsar=1,format=yuv420p"

    cmd = ["ffmpeg", "-y", "-i", str(src)]
    has_audio = _has_audio(src)
    if not has_audio:
        cmd += [
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        ]
    cmd += [
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
    ]
    if has_audio:
        cmd += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    cmd += [str(dst)]

    subprocess.run(cmd, check=True)
    return dst


def _is_fresh(out: Path, src: Path) -> bool:
    """True if `out` exists and is newer than `src` (skip reprocessing)."""
    return out.exists() and out.stat().st_mtime >= src.stat().st_mtime


def assemble(
    edit_dir: Path,
    out_path: Path,
    *,
    speed: float = 1.1,
    margin: str = "0.2s",
    edit_expression: str = "audio",
    language: str = "zh",
    model: str = DEFAULT_MODEL,
) -> Path:
    """Assemble all segments in `edit_dir` into one vertical video at `out_path`.

    Per-segment normalized outputs are cached in a work dir keyed by mtime, so
    re-running after filming one more part only reprocesses the new segment.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = out_path.parent / f".{out_path.stem}.assemble.work"
    work.mkdir(parents=True, exist_ok=True)

    segments = discover_segments(edit_dir)
    if not segments:
        raise ValueError(f"no segments found in {edit_dir}")

    normalized: list[Path] = []
    for i, seg in enumerate(segments, 1):
        stem = seg.path.stem
        norm = work / f"{stem}.norm.mp4"
        print(f"[{i}/{len(segments)}] {seg.path.name} ({seg.kind})")

        if _is_fresh(norm, seg.path):
            print("  cached")
            normalized.append(norm)
            continue

        if seg.kind == "talk":
            clip_dir = work / f"{stem}.clip"
            result = process_clip(
                seg.path, clip_dir,
                speed=speed, margin=margin, edit_expression=edit_expression,
                language=language, model=model,
            )
            cropped = work / f"{stem}.crop.mp4"
            normalize(result.video, cropped, mode="cover")
            burn_subs(cropped, result.srt, norm)
        else:  # screen
            normalize(seg.path, norm, mode="contain")

        normalized.append(norm)
        print(f"  -> {norm.name}")

    print(f"\nConcatenating {len(normalized)} segment(s) -> {out_path}")
    concat_clips(normalized, out_path)
    print(f"-> {out_path}")
    return out_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-prep-assemble",
        description=(
            "Assemble NN-kind-label segments from a folder into one finished "
            "vertical (1080x1920) video. 'talk' segments get the full pipeline "
            "+ burned subtitles; 'screen' segments are just normalized to 9:16."
        ),
    )
    parser.add_argument("edit_dir", type=Path, help="Folder of segment files")
    parser.add_argument(
        "-o", "--out",
        type=Path,
        default=Path("./out/final.mp4"),
        help="Output video (default: ./out/final.mp4)",
    )
    parser.add_argument(
        "--speed", type=float, default=1.1,
        help="Speed factor for talk segments (default: 1.1)",
    )
    parser.add_argument(
        "--margin", default="0.2s",
        help="Silence-cut padding for talk segments (default: 0.2s)",
    )
    parser.add_argument("--edit", default="audio", help="auto-editor edit expr")
    parser.add_argument("--language", default="zh", help="Whisper language code")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="faster-whisper model")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = assemble(
            args.edit_dir, args.out,
            speed=args.speed, margin=args.margin, edit_expression=args.edit,
            language=args.language, model=args.model,
        )
    except (ValueError, NotADirectoryError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        print(f"failed ({e.cmd[0]} exited {e.returncode})", file=sys.stderr)
        return 1
    print(f"\nDone. Upload {result.name} to Rednote.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
