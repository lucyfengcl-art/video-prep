"""Small media-probing helpers shared across the pipeline."""

from __future__ import annotations

import subprocess
from pathlib import Path


def probe_duration(path: Path) -> float:
    """Return the container duration of ``path`` in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def probe_video_size(path: Path) -> tuple[int, int]:
    """Return the first video stream's display width and height."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    width, height = result.stdout.strip().split("x", 1)
    return int(width), int(height)
