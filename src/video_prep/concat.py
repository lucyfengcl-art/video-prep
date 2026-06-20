"""Concatenate video clips into one file via ffmpeg's concat demuxer."""

from __future__ import annotations

import subprocess
from pathlib import Path


def concat_clips(sources: list[Path], dst: Path) -> Path:
    """Concatenate `sources` (in given order) into `dst`.

    Tries stream-copy first (fast, lossless) and falls back to re-encoding if
    the clips have mismatched codecs/resolutions/framerates. iPhone clips from
    the same phone almost always satisfy the stream-copy preconditions.
    """
    if not sources:
        raise ValueError("no source clips to concat")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    listfile = dst.parent / f"{dst.stem}.concat.txt"
    listfile.write_text(
        "\n".join(f"file '{Path(p).resolve()}'" for p in sources) + "\n",
        encoding="utf-8",
    )
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(listfile),
            "-c", "copy",
            str(dst),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        # Mismatched streams: re-encode so audio/video timelines align.
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(listfile),
            str(dst),
        ]
        subprocess.run(cmd, check=True)
    finally:
        listfile.unlink(missing_ok=True)
    return dst
