"""Cut silent gaps using auto-editor."""

from __future__ import annotations

import subprocess
from pathlib import Path


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
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "auto-editor",
        str(src),
        "-o",
        str(dst),
        "--margin",
        margin,
        "--edit",
        edit_expression,
        "--no-open",
    ]
    subprocess.run(cmd, check=True)
    return dst
