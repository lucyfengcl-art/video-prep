"""Speed up video + audio with ffmpeg, preserving pitch."""

from __future__ import annotations

import subprocess
from pathlib import Path


def speed_up(src: Path, dst: Path, factor: float) -> Path:
    """Re-encode `src` at `factor`x speed, writing to `dst`.

    Audio uses `atempo` (preserves pitch), video uses `setpts` (drops frames).
    """
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-filter:v", f"setpts=PTS/{factor}",
        "-filter:a", f"atempo={factor}",
        str(dst),
    ]
    subprocess.run(cmd, check=True)
    return dst
