"""One-command edit: process raw clips and assemble a finished video.

For a folder of raw clips, this runs the per-clip pipeline (cut silence ->
transcribe -> speed up -> rescale .srt), then merges the processed clips in
order and burns the subtitles in -- all into a dated output folder:

    out/2026-06-15/
      01.processed.mp4  01.srt   # per clip, in input order
      02.processed.mp4  02.srt
      final.mp4         final.srt        # merged
      final.subbed.mp4                   # merged + burned subs  <- deliverable

The merged .srt is built by offsetting the per-clip subtitles (see
`srt.concat_srts`), so assembling never re-transcribes. Per-clip outputs are
cached by mtime, so re-running after changing one clip only reprocesses that
clip; the merge + burn are always rebuilt from the current pieces.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from video_prep.burn import burn_subs
from video_prep.cli import _expand_inputs
from video_prep.concat import concat_clips
from video_prep.pipeline import process_clip
from video_prep.srt import concat_srts
from video_prep.transcribe import DEFAULT_MODEL


def _is_fresh(out: Path, src: Path) -> bool:
    """True if `out` exists and is at least as new as `src`."""
    return out.exists() and out.stat().st_mtime >= src.stat().st_mtime


def probe_duration(path: Path) -> float:
    """Return the duration of `path` in seconds via ffprobe."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def edit(
    clips: list[Path],
    out_dir: Path,
    *,
    speed: float = 1.1,
    margin: str = "0.2s",
    edit_expression: str = "audio",
    language: str = "zh",
    model: str = DEFAULT_MODEL,
) -> dict[str, Path]:
    """Process `clips`, merge them in order, and burn subtitles into out_dir.

    Returns a dict of the key output paths. Per-clip outputs are reused when
    their source is unchanged (mtime cache).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    width = max(2, len(str(len(clips))))  # 01, 02, ... (or 001 for 100+ clips)
    videos: list[Path] = []
    srts: list[Path] = []

    for i, src in enumerate(clips, 1):
        name = str(i).zfill(width)
        video = out_dir / f"{name}.processed.mp4"
        srt = out_dir / f"{name}.srt"
        print(f"[{i}/{len(clips)}] {src.name} -> {name}")

        if _is_fresh(video, src) and _is_fresh(srt, src):
            print("  cached")
        else:
            result = process_clip(
                src, out_dir, out_name=name,
                speed=speed, margin=margin, edit_expression=edit_expression,
                language=language, model=model,
            )
            video, srt = result.video, result.srt
        videos.append(video)
        srts.append(srt)

    # Merge in order: clip i starts at the cumulative duration of its predecessors.
    offsets: list[float] = []
    running = 0.0
    for v in videos:
        offsets.append(running)
        running += probe_duration(v)

    final_video = out_dir / "final.mp4"
    final_srt = out_dir / "final.srt"
    print(f"\nMerging {len(videos)} clip(s) -> {final_video.name}")
    concat_clips(videos, final_video)
    concat_srts(srts, offsets, final_srt)

    outputs = {"video": final_video, "srt": final_srt}

    subbed = out_dir / "final.subbed.mp4"
    print(f"Burning subtitles -> {subbed.name}")
    try:
        burn_subs(final_video, final_srt, subbed)
        outputs["subbed"] = subbed
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(
            f"  warning: subtitle burn skipped ({e}); "
            "final.mp4 + final.srt are still ready for CapCut.\n"
            "  Install ffmpeg-full to enable burning (see README).",
            file=sys.stderr,
        )

    return outputs


def _resolve_out_dir(out_root: Path, name: str | None) -> Path:
    """Pick the output folder: out_root/<name or today>, reused if it exists.

    Reusing the same folder is what lets the mtime cache skip unchanged clips on
    a re-run. Pass --name to keep separate edits made on the same day apart.
    """
    return out_root / (name or date.today().isoformat())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-prep-edit",
        description=(
            "Process raw clips and assemble one finished video (merged + "
            "burned subtitles) into a dated output folder."
        ),
    )
    parser.add_argument(
        "inputs", nargs="+", type=Path,
        help="Video files or directories to process (in order)",
    )
    parser.add_argument(
        "-o", "--out", type=Path, default=Path("./out"),
        help="Parent output directory (default: ./out)",
    )
    parser.add_argument(
        "--name",
        help="Output subfolder name (default: today's date, YYYY-MM-DD)",
    )
    parser.add_argument(
        "--speed", type=float, default=1.1,
        help="Playback speed factor (default: 1.1)",
    )
    parser.add_argument(
        "--margin", default="0.2s",
        help='Silence-cut padding around speech (default: 0.2s)',
    )
    parser.add_argument("--edit", default="audio", help="auto-editor edit expr")
    parser.add_argument("--language", default="zh", help="Whisper language code")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="faster-whisper model")
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

    out_dir = _resolve_out_dir(args.out, args.name)
    print(f"Editing {len(clips)} clip(s) -> {out_dir}/\n")
    try:
        outputs = edit(
            clips, out_dir,
            speed=args.speed, margin=args.margin, edit_expression=args.edit,
            language=args.language, model=args.model,
        )
    except subprocess.CalledProcessError as e:
        print(f"failed ({e.cmd[0]} exited {e.returncode})", file=sys.stderr)
        return 1

    print("\nDone.")
    for label, path in outputs.items():
        print(f"  {label}: {path}")
    deliverable = outputs.get("subbed", outputs["video"])
    print(f"\n-> Upload {deliverable} to Rednote.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
