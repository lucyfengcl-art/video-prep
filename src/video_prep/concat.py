"""Concatenate video clips into one file via ffmpeg's concat filter.

We deliberately do NOT use the concat *demuxer* with stream-copy here. Stream
copy only works when every clip shares an identical time base, SAR, frame rate,
and audio layout -- and when it doesn't, ffmpeg often still exits 0 while
producing frozen video, drifting audio, or clicks at each join (edit lists in
iPhone .MOV files trigger this even between clips from the same phone). Those
failures are silent, so the safe default is to fully decode every clip and
re-encode once, normalizing each input first. That costs one extra encode of
the merged file; the per-clip outputs remain the high-quality handoff.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _probe_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) of the first video stream in `path`."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    w, h = out.split("x")
    return int(w), int(h)


def concat_clips(
    sources: list[Path],
    dst: Path,
    *,
    fps: int = 30,
    sample_rate: int = 48000,
    channels: int = 1,
) -> Path:
    """Concatenate `sources` (in given order) into `dst`, re-encoding once.

    Every input is normalized before joining: video is scaled (preserving aspect
    ratio, padding if needed) to the first clip's dimensions, set to constant
    `fps`, square pixels, and yuv420p; audio is resampled to `sample_rate` and
    the chosen channel layout. This makes the join robust to mixed time bases,
    resolutions, frame rates, and mono/stereo inputs -- the things that silently
    corrupt a stream-copy concat.
    """
    if not sources:
        raise ValueError("no source clips to concat")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    width, height = _probe_dimensions(sources[0])
    layout = "mono" if channels == 1 else "stereo"

    inputs: list[str] = []
    filters: list[str] = []
    concat_labels = ""
    for i, src in enumerate(sources):
        inputs += ["-i", str(Path(src).resolve())]
        filters.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"fps={fps},format=yuv420p[v{i}];"
            f"[{i}:a]aresample={sample_rate},"
            f"aformat=channel_layouts={layout}:sample_fmts=fltp[a{i}]"
        )
        concat_labels += f"[v{i}][a{i}]"

    n = len(sources)
    filtergraph = (
        ";".join(filters) + ";" + concat_labels + f"concat=n={n}:v=1:a=1[v][a]"
    )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filtergraph,
        "-map", "[v]", "-map", "[a]",
        # Force true CFR on the merged output: the concat filter can otherwise
        # emit a slightly off rate (e.g. 29.985 vs 30), which makes the picture
        # drift behind the audio over a long video.
        "-r", str(fps), "-fps_mode", "cfr",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-ar", str(sample_rate), "-ac", str(channels),
        "-video_track_timescale", "15360",
        str(dst),
    ]
    subprocess.run(cmd, check=True)
    return dst
