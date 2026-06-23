"""Speed up video + audio with ffmpeg, preserving pitch.

This is the final per-clip encode, so it also normalizes every clip to one
canonical format (constant frame rate, square pixels, yuv420p, 48 kHz mono,
fixed video timescale). Uniform clips are what makes concatenation reliable:
mixing time bases / SARs / channel layouts is what causes frozen video, A/V
desync, and click artifacts when clips are joined later.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def speed_up(
    src: Path,
    dst: Path,
    factor: float,
    *,
    fps: int = 30,
    pix_fmt: str = "yuv420p",
    sample_rate: int = 48000,
    channels: int = 1,
    timescale: int = 15360,
) -> Path:
    """Re-encode `src` at `factor`x speed, writing to `dst`.

    Audio uses `atempo` (preserves pitch), video uses `setpts` (drops frames).
    The output is normalized to a canonical, concat-safe format: constant
    `fps`, `setsar=1`, `pix_fmt`, `sample_rate`/`channels`, and a fixed video
    `timescale`. Pass `factor=1.0` to normalize without changing speed.
    """
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    layout = "mono" if channels == 1 else "stereo"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        # setpts changes the timestamps; fps then renders a constant-rate stream
        # (so 30 + 60 fps sources both come out at `fps`); setsar squares pixels.
        "-filter:v", f"setpts=PTS/{factor},fps={fps},setsar=1",
        # apad pads the audio with silence so -shortest can trim it to exactly the
        # video length: atempo and the frame-quantized video otherwise end a few
        # tens of ms apart, and that per-clip gap accumulates into audible A/V
        # drift once many clips are concatenated.
        "-filter:a", f"atempo={factor},aresample={sample_rate},aformat=channel_layouts={layout},apad",
        "-pix_fmt", pix_fmt,
        "-r", str(fps),
        "-fps_mode", "cfr",  # force true constant frame rate (not 29.985 vs 30)
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-video_track_timescale", str(timescale),
        "-shortest",  # end at the (now frame-aligned) video; audio padded to match
        str(dst),
    ]
    subprocess.run(cmd, check=True)
    return dst
