"""Cut silent gaps using auto-editor."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _video_is_first_stream(src: Path) -> bool:
    """True if the first stream in `src` is the video stream.

    iPhone `.MOV` files put audio first (stream 0 = audio, stream 1 = video),
    and auto-editor v29 renders all-black video for that ordering. We detect it
    so it can be remuxed video-first beforehand.
    """
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(src)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return bool(out) and out[0].strip() == "video"


def cut_silence(
    src: Path,
    dst: Path,
    *,
    margin: str = "0.2s",
    edit_expression: str = "audio",
) -> Path:
    """Remove silent segments from `src`, writing the trimmed video to `dst`.

    `margin` is how much padding to keep around speech (e.g. "0.2s", "0.3s").
    A larger margin protects Mandarin tonal onsets/offsets from being clipped.
    `edit_expression` is auto-editor's edit method (default "audio"); pass
    something like "audio:threshold=0.03" to lower the silence threshold.
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # auto-editor v29 produces all-black video when the audio stream precedes
    # the video stream (the iPhone .MOV ordering). Remux video-first first --
    # a lossless stream copy -- so the picture survives.
    reordered: Path | None = None
    infile = src
    if not _video_is_first_stream(src):
        reordered = dst.with_name(f".{dst.stem}.reorder{src.suffix}")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
             "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", str(reordered)],
            check=True,
        )
        infile = reordered

    try:
        subprocess.run(
            ["auto-editor", str(infile), "-o", str(dst),
             "--margin", margin, "--edit", edit_expression, "--no-open"],
            check=True,
        )
    finally:
        if reordered is not None:
            reordered.unlink(missing_ok=True)
    return dst
