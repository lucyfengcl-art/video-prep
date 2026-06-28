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
from concurrent.futures import ProcessPoolExecutor, as_completed
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


def _process_clip_task(src: Path, out_dir: Path, name: str, kwargs: dict) -> tuple[Path, Path]:
    """Run one clip's pipeline; module-level so it's picklable for a process pool.

    Each worker process loads its own Whisper model (~1.5 GB), so keep `--jobs`
    modest on low-RAM machines. Transcription already uses all CPU cores, so the
    real-world gain is sub-linear (~1.4x), mostly from overlapping load/decode.
    """
    result = process_clip(src, out_dir, out_name=name, **kwargs)
    return result.video, result.srt


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
    max_chars: int = -1,
    jobs: int = 1,
) -> dict[str, Path]:
    """Process `clips`, merge them in order, and burn subtitles into out_dir.

    Returns a dict of the key output paths. Per-clip outputs are reused when
    their source is unchanged (mtime cache). `jobs` > 1 processes the uncached
    clips in parallel across that many worker processes (each loads its own
    model, so raise it carefully on low-RAM machines); the merge stays one pass.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    width = max(2, len(str(len(clips))))  # 01, 02, ... (or 001 for 100+ clips)
    videos: list[Path | None] = [None] * len(clips)
    srts: list[Path | None] = [None] * len(clips)
    kwargs = dict(
        speed=speed, margin=margin, edit_expression=edit_expression,
        language=language, model=model, max_chars=max_chars,
    )

    # Resolve cache first; collect only the clips that actually need processing.
    todo: list[tuple[int, Path, str]] = []  # (index, src, name)
    for i, src in enumerate(clips):
        name = str(i + 1).zfill(width)
        video = out_dir / f"{name}.processed.mp4"
        srt = out_dir / f"{name}.srt"
        if _is_fresh(video, src) and _is_fresh(srt, src):
            print(f"[{i + 1}/{len(clips)}] {src.name} -> {name}  cached")
            videos[i], srts[i] = video, srt
        else:
            todo.append((i, src, name))

    workers = max(1, min(jobs, len(todo)))
    if workers > 1:
        if jobs > 4:
            print(
                f"  note: --jobs {jobs} runs {workers} Whisper models at once "
                "(~1.5 GB each); reduce it if you hit memory pressure.",
                file=sys.stderr,
            )
        print(f"Processing {len(todo)} clip(s) with {workers} workers...")
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_process_clip_task, src, out_dir, name, kwargs): (i, name)
                for i, src, name in todo
            }
            for fut in as_completed(futures):
                i, name = futures[fut]
                videos[i], srts[i] = fut.result()
                print(f"  done {name}")
    else:
        for i, src, name in todo:
            print(f"[{i + 1}/{len(clips)}] {src.name} -> {name}")
            videos[i], srts[i] = _process_clip_task(src, out_dir, name, kwargs)

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
    parser.add_argument(
        "--language", default="zh",
        help="Whisper language code, or 'auto' to detect (default: zh)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="faster-whisper model")
    parser.add_argument(
        "--max-chars", type=int, default=-1,
        help="Split subtitle cues longer than this many chars (default: -1 = auto "
             "by language: 20 for Chinese, 42 for spaced languages; 0 disables)",
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=1,
        help="Process this many clips in parallel (default: 1). Speeds up large "
             "folders ~1.4x; each worker loads its own ~1.5 GB model, so keep it "
             "modest on low-RAM machines.",
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

    out_dir = _resolve_out_dir(args.out, args.name)
    print(f"Editing {len(clips)} clip(s) -> {out_dir}/\n")
    try:
        outputs = edit(
            clips, out_dir,
            speed=args.speed, margin=args.margin, edit_expression=args.edit,
            language=args.language, model=args.model, max_chars=args.max_chars,
            jobs=args.jobs,
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
