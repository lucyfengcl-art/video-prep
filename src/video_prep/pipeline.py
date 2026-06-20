"""End-to-end pipeline: cut silence -> transcribe -> speed up -> rescale srt."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from video_prep.concat import concat_clips
from video_prep.cut import cut_silence
from video_prep.speedup import speed_up
from video_prep.srt import rescale_srt
from video_prep.transcribe import DEFAULT_MODEL, transcribe_to_srt


@dataclass
class ProcessResult:
    video: Path
    srt: Path


def process_clip(
    src: Path,
    out_dir: Path,
    *,
    out_name: str | None = None,
    speed: float = 1.1,
    margin: str = "0.2s",
    edit_expression: str = "audio",
    language: str = "zh",
    model: str = DEFAULT_MODEL,
    keep_intermediates: bool = False,
) -> ProcessResult:
    """Run the full pipeline on one clip.

    Order: cut silence -> transcribe at 1x -> speed up video -> rescale srt
    timestamps by 1/speed. Transcribing the natural-speed cut audio gives the
    best subtitle accuracy; rescaling at the end keeps subs in sync.

    `out_name` overrides the output basename (default: the input stem).
    """
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_name or src.stem

    work_dir = out_dir / f".{stem}.work"
    work_dir.mkdir(parents=True, exist_ok=True)

    cut_path = work_dir / f"{stem}.cut{src.suffix}"
    cut_silence(src, cut_path, margin=margin, edit_expression=edit_expression)

    srt_raw = transcribe_to_srt(
        cut_path, work_dir, language=language, model=model, output_name=stem
    )

    final_video = out_dir / f"{stem}.processed.mp4"
    speed_up(cut_path, final_video, factor=speed)

    final_srt = out_dir / f"{stem}.srt"
    rescale_srt(srt_raw, factor=speed, out_path=final_srt)

    if not keep_intermediates:
        shutil.rmtree(work_dir, ignore_errors=True)

    return ProcessResult(video=final_video, srt=final_srt)


def process_combined(
    sources: list[Path],
    out_dir: Path,
    *,
    name: str = "combined",
    speed: float = 1.1,
    margin: str = "0.2s",
    edit_expression: str = "audio",
    language: str = "zh",
    model: str = DEFAULT_MODEL,
    keep_intermediates: bool = False,
) -> ProcessResult:
    """Concatenate `sources` in given order, then run the full pipeline once.

    Concat happens before silence-cutting, so pauses between clips (e.g. you
    repositioning the phone) also get trimmed. Single transcription pass over
    the whole video yields one .srt naturally aligned to the final output.
    """
    if not sources:
        raise ValueError("no source clips provided")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    work_dir = out_dir / f".{name}.work"
    work_dir.mkdir(parents=True, exist_ok=True)

    merged = work_dir / f"{name}.merged.mp4"
    concat_clips(sources, merged)

    cut_path = work_dir / f"{name}.cut.mp4"
    cut_silence(merged, cut_path, margin=margin, edit_expression=edit_expression)

    srt_raw = transcribe_to_srt(
        cut_path, work_dir, language=language, model=model, output_name=name
    )

    final_video = out_dir / f"{name}.processed.mp4"
    speed_up(cut_path, final_video, factor=speed)

    final_srt = out_dir / f"{name}.srt"
    rescale_srt(srt_raw, factor=speed, out_path=final_srt)

    if not keep_intermediates:
        shutil.rmtree(work_dir, ignore_errors=True)

    return ProcessResult(video=final_video, srt=final_srt)
