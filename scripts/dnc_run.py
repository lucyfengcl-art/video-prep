"""One-off divide-and-conquer driver for the 14-clip Rednote video.

Pairs (1+2, 3+4, ..., 13+14) are concatenated and silence-cut in parallel,
then all 7 pair outputs are re-encoded into one timeline, transcribed once,
sped up, and SRT-rescaled. Output lands in out/dnc/.
"""

from __future__ import annotations

import concurrent.futures as cf
import shutil
import subprocess
import sys
from pathlib import Path

from video_prep.concat import concat_clips
from video_prep.cut import cut_silence
from video_prep.speedup import speed_up
from video_prep.srt import rescale_srt
from video_prep.transcribe import transcribe_to_srt

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
OUT = ROOT / "out" / "dnc"
WORK = OUT / ".work"

PAIRS = [(2 * i + 1, 2 * i + 2) for i in range(7)]  # (1,2)..(13,14)
SPEED = 1.1
MARGIN = "0.2s"
EDIT = "audio"
LANGUAGE = "zh"
NAME = "combined"
PARALLEL = 3
EDGE_TRIM = 0.5  # seconds trimmed off each raw clip's start AND end


def log(msg: str) -> None:
    print(msg, flush=True)


def edge_trim(src: Path, dst: Path, trim_s: float) -> Path:
    """Trim `trim_s` seconds off both the start and end of `src`.

    Re-encode (not stream-copy) so the cut lands on an exact frame, avoiding
    leftover phone-placement noise that a keyframe-aligned copy would keep.
    """
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(src)],
        check=True, capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip())
    keep = max(0.1, duration - 2 * trim_s)
    subprocess.run(
        ["ffmpeg", "-y",
         "-ss", f"{trim_s}", "-i", str(src), "-t", f"{keep}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k",
         str(dst)],
        check=True, capture_output=True,
    )
    return dst


def process_pair(idx: int, a: int, b: int) -> Path:
    pair_work = WORK / f"pair_{idx}"
    pair_work.mkdir(parents=True, exist_ok=True)
    trimmed_a = pair_work / f"{a}.trim.mp4"
    trimmed_b = pair_work / f"{b}.trim.mp4"
    merged = pair_work / f"pair_{idx}.merged.mp4"
    cut = pair_work / f"pair_{idx}.cut.mp4"
    log(f"[pair {idx}] edge-trim {a}.MOV ({EDGE_TRIM}s each side)")
    edge_trim(RAW / f"{a}.MOV", trimmed_a, EDGE_TRIM)
    log(f"[pair {idx}] edge-trim {b}.MOV ({EDGE_TRIM}s each side)")
    edge_trim(RAW / f"{b}.MOV", trimmed_b, EDGE_TRIM)
    log(f"[pair {idx}] concat trimmed {a} + {b}")
    concat_clips([trimmed_a, trimmed_b], merged)
    log(f"[pair {idx}] silence-cut")
    cut_silence(merged, cut, margin=MARGIN, edit_expression=EDIT)
    trimmed_a.unlink(missing_ok=True)
    trimmed_b.unlink(missing_ok=True)
    merged.unlink(missing_ok=True)
    log(f"[pair {idx}] done -> {cut.relative_to(ROOT)}")
    return cut


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    WORK.mkdir(parents=True, exist_ok=True)

    log(f"Phase 1: silence-cut {len(PAIRS)} pairs (up to {PARALLEL} in parallel)")
    pair_cuts: list[Path] = [Path()] * len(PAIRS)
    with cf.ThreadPoolExecutor(max_workers=PARALLEL) as ex:
        futures = {
            ex.submit(process_pair, i, a, b): i for i, (a, b) in enumerate(PAIRS)
        }
        for fut in cf.as_completed(futures):
            i = futures[fut]
            pair_cuts[i] = fut.result()

    log("\nPhase 2: re-encode concat of 7 pair outputs")
    combined_cut = WORK / f"{NAME}.cut.mp4"
    listfile = WORK / f"{NAME}.concat.txt"
    listfile.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in pair_cuts) + "\n",
        encoding="utf-8",
    )
    # Force re-encode to normalize SPS/PPS across the 7 chunks.
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(listfile),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(combined_cut),
        ],
        check=True,
    )
    listfile.unlink(missing_ok=True)
    log(f"-> {combined_cut.relative_to(ROOT)}")

    log("\nPhase 3: transcribe (faster-whisper, zh)")
    srt_raw = transcribe_to_srt(
        combined_cut, WORK, language=LANGUAGE, output_name=NAME
    )
    log(f"-> {srt_raw.relative_to(ROOT)}")

    log("\nPhase 4: speedup 1.1x")
    final_video = OUT / f"{NAME}.processed.mp4"
    speed_up(combined_cut, final_video, factor=SPEED)
    log(f"-> {final_video.relative_to(ROOT)}")

    log("\nPhase 5: rescale srt by 1/speed")
    final_srt = OUT / f"{NAME}.srt"
    rescale_srt(srt_raw, factor=SPEED, out_path=final_srt)
    log(f"-> {final_srt.relative_to(ROOT)}")

    shutil.rmtree(WORK, ignore_errors=True)
    log(f"\nDone. {final_video} + {final_srt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
