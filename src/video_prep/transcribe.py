"""Transcribe audio to .srt with faster-whisper (cross-platform: CPU or CUDA).

Runs anywhere faster-whisper installs (macOS/Windows/Linux, Intel/ARM). The model
is loaded through CTranslate2: it picks the GPU when one is available and falls
back to an int8 CPU run otherwise. faster-whisper decodes the audio itself, so a
video path can be passed directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

DEFAULT_MODEL = "large-v3"


def _pick_runtime(device: str, compute_type: str) -> tuple[str, str]:
    """Resolve "auto" device/compute_type to concrete values.

    GPU runs use float16; CPU runs use int8 (much faster, negligible quality
    loss for subtitles). Detection never raises — it falls back to CPU.
    """
    if device == "auto":
        try:
            import ctranslate2

            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"
    return device, compute_type


@lru_cache(maxsize=2)
def _load_model(model: str, device: str, compute_type: str):
    """Load (and cache) a WhisperModel so a multi-clip edit reuses one instance."""
    from faster_whisper import WhisperModel

    return WhisperModel(model, device=device, compute_type=compute_type)


def _format_ts(seconds: float) -> str:
    """Format seconds as an SRT 'HH:MM:SS,mmm' timestamp (matches srt.py)."""
    ms = max(0, round(seconds * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_segments(
    src: Path,
    *,
    language: str = "zh",
    model: str = DEFAULT_MODEL,
    word_timestamps: bool = False,
    device: str = "auto",
    compute_type: str = "auto",
) -> list[dict]:
    """Transcribe `src` and return segments as plain dicts.

    Each dict has ``start``, ``end``, ``text``; with ``word_timestamps=True`` it
    also has ``words`` (a list of ``{"word", "start", "end"}``). This is the
    shape the filler-word cutter consumes.
    """
    device, compute_type = _pick_runtime(device, compute_type)
    whisper = _load_model(model, device, compute_type)
    segments, _info = whisper.transcribe(
        str(src), language=language, word_timestamps=word_timestamps
    )
    out: list[dict] = []
    for seg in segments:
        entry: dict = {"start": seg.start, "end": seg.end, "text": seg.text}
        if word_timestamps:
            entry["words"] = [
                {"word": w.word, "start": w.start, "end": w.end}
                for w in (seg.words or [])
            ]
        out.append(entry)
    return out


def transcribe_to_srt(
    src: Path,
    out_dir: Path,
    *,
    language: str = "zh",
    model: str = DEFAULT_MODEL,
    output_name: str | None = None,
    device: str = "auto",
    compute_type: str = "auto",
) -> Path:
    """Transcribe `src` and write an .srt into `out_dir`.

    The output filename is `<output_name>.srt` (default: input stem). `device`
    and `compute_type` accept "auto" (detect GPU, else int8 CPU) or any value
    faster-whisper understands ("cpu"/"cuda", "int8"/"float16"/...).
    """
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = output_name or src.stem

    device, compute_type = _pick_runtime(device, compute_type)
    whisper = _load_model(model, device, compute_type)
    segments, _info = whisper.transcribe(str(src), language=language)

    lines: list[str] = []
    idx = 1
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{_format_ts(seg.start)} --> {_format_ts(seg.end)}")
        lines.append(text)
        lines.append("")
        idx += 1

    out_path = out_dir / f"{stem}.srt"
    out_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return out_path
