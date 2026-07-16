"""Transcribe audio to .srt with faster-whisper (cross-platform: CPU or CUDA).

Runs anywhere faster-whisper installs (macOS/Windows/Linux, Intel/ARM). The model
is loaded through CTranslate2: it picks the GPU when one is available and falls
back to an int8 CPU run otherwise. faster-whisper decodes the audio itself, so a
video path can be passed directly.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from video_prep.media import probe_duration
from video_prep.subtitle_quality import sanitize_segments

# large-v3-turbo is ~2x faster than large-v3 on CPU with negligible quality loss
# for short-form subtitles; pass --model large-v3 when you want maximum accuracy.
DEFAULT_MODEL = "large-v3-turbo"

# Languages written without spaces between words: subtitles for these wrap by
# character; everything else wraps on word boundaries. Used to pick how long
# cues get split (see srt.split_cue).
SPACELESS_LANGS = {"zh", "yue", "ja", "th", "lo", "my", "km"}


def _whisper_language(language: str | None) -> str | None:
    """Map our language option to what faster-whisper wants.

    "auto" (or empty) -> None, which tells Whisper to auto-detect the language.
    """
    if not language or language.lower() == "auto":
        return None
    return language


def is_space_delimited(language: str | None) -> bool:
    """True if `language` writes words with spaces (so subtitles wrap on words)."""
    return bool(language) and language.lower() not in SPACELESS_LANGS


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


def _decode(whisper, src: Path, language: str | None, *, word_timestamps: bool):
    """Decode with conservative defaults for edited speech recordings."""
    return whisper.transcribe(
        str(src),
        language=_whisper_language(language),
        word_timestamps=word_timestamps,
        vad_filter=True,
        condition_on_previous_text=False,
        hallucination_silence_threshold=1.0,
    )


def _segment_dict(seg, *, word_timestamps: bool) -> dict:
    entry: dict = {
        "start": seg.start,
        "end": seg.end,
        "text": seg.text,
        "avg_logprob": getattr(seg, "avg_logprob", None),
        "no_speech_prob": getattr(seg, "no_speech_prob", None),
        "compression_ratio": getattr(seg, "compression_ratio", None),
    }
    if word_timestamps:
        entry["words"] = [
            {
                "word": w.word,
                "start": w.start,
                "end": w.end,
                "probability": getattr(w, "probability", None),
            }
            for w in (seg.words or [])
        ]
    return entry


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
    segments, _info = _decode(
        whisper, Path(src), language, word_timestamps=word_timestamps,
    )
    decoded = [_segment_dict(seg, word_timestamps=word_timestamps) for seg in segments]
    clean, _warnings = sanitize_segments(decoded, probe_duration(src))
    return clean


def transcribe_to_srt(
    src: Path,
    out_dir: Path,
    *,
    language: str = "zh",
    model: str = DEFAULT_MODEL,
    output_name: str | None = None,
    max_chars: int = -1,
    device: str = "auto",
    compute_type: str = "auto",
) -> Path:
    """Transcribe `src` and write an .srt into `out_dir`.

    The output filename is `<output_name>.srt` (default: input stem). `language`
    accepts a Whisper code or "auto" (detect). `max_chars` caps cue length so
    burned subtitles stay short: ``-1`` (default) picks a sensible cap by
    language (20 for spaceless scripts like Chinese, 42 for spaced ones like
    English) and wraps accordingly; ``0`` keeps Whisper's segments as-is; a
    positive value forces that cap. `device`/`compute_type` accept "auto" or any
    value faster-whisper understands.
    """
    from video_prep.srt import split_cue

    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = output_name or src.stem

    device, compute_type = _pick_runtime(device, compute_type)
    whisper = _load_model(model, device, compute_type)
    segments, info = _decode(whisper, src, language, word_timestamps=True)
    decoded = [_segment_dict(seg, word_timestamps=True) for seg in segments]
    duration = probe_duration(src)
    decoded, warnings = sanitize_segments(decoded, duration)

    warning_path = out_dir / f"{stem}.subtitle-warnings.json"
    if warnings:
        warning_path.write_text(
            json.dumps(
                {"media_duration": duration, "warnings": warnings},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        corrected = sum(w["action"] in {"dropped", "clamped"} for w in warnings)
        reviews = sum(w["action"] == "review" for w in warnings)
        print(
            f"  subtitle validation: corrected {corrected}, "
            f"flagged {reviews} for review -> {warning_path.name}"
        )
    else:
        warning_path.unlink(missing_ok=True)

    # Resolve language (Whisper detects it when "auto") to choose wrapping style.
    detected = _whisper_language(language) or getattr(info, "language", None) or "en"
    spaced = is_space_delimited(detected)
    if max_chars < 0:
        max_chars = 42 if spaced else 20

    cues: list[tuple[int, int, str]] = []
    for seg in decoded:
        text = seg["text"].strip()
        if not text:
            continue
        start_ms = max(0, round(seg["start"] * 1000))
        end_ms = max(0, round(seg["end"] * 1000))
        if max_chars > 0:
            cues.extend(split_cue(start_ms, end_ms, text, max_chars,
                                  space_delimited=spaced))
        else:
            cues.append((start_ms, end_ms, text))

    lines: list[str] = []
    for idx, (start_ms, end_ms, text) in enumerate(cues, 1):
        lines.append(str(idx))
        lines.append(f"{_format_ts(start_ms / 1000)} --> {_format_ts(end_ms / 1000)}")
        lines.append(text)
        lines.append("")

    out_path = out_dir / f"{stem}.srt"
    out_path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return out_path
