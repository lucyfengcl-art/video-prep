"""Validate Whisper segments before they become user-facing subtitles."""

from __future__ import annotations

import re
from collections.abc import Iterable

TAIL_WINDOW_S = 0.5
OVERRUN_TOLERANCE_S = 0.25
LONG_CUE_S = 10.0
LOW_TEXT_RATE = 0.75


def _normalized_text(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE).casefold()


def sanitize_segments(
    segments: Iterable[dict],
    duration: float,
) -> tuple[list[dict], list[dict]]:
    """Return timeline-safe segments and a machine-readable warning list.

    Timeline violations are corrected automatically. Text-only heuristics are
    reported for review instead of silently deleting potentially real speech.
    """
    clean: list[dict] = []
    warnings: list[dict] = []

    for original in segments:
        seg = dict(original)
        start = max(0.0, float(seg.get("start", 0.0)))
        end = max(0.0, float(seg.get("end", 0.0)))
        text = str(seg.get("text", "")).strip()
        base = {"start": start, "end": end, "text": text}

        if not text or end <= start:
            warnings.append({**base, "reason": "invalid-segment", "action": "dropped"})
            continue
        if start >= duration:
            warnings.append({**base, "reason": "starts-after-media", "action": "dropped"})
            continue

        visible = duration - start
        overrun = end - duration
        if (
            overrun > OVERRUN_TOLERANCE_S
            and visible <= TAIL_WINDOW_S
        ):
            warnings.append({**base, "reason": "hallucinated-tail-overrun", "action": "dropped"})
            continue
        if end > duration:
            warnings.append({**base, "reason": "ends-after-media", "action": "clamped"})
            end = duration

        seg.update(start=start, end=end, text=text)
        clean.append(seg)

    # Flag likely hallucinations while preserving them unless a hard timeline
    # invariant above proves they cannot belong to the media.
    for i, seg in enumerate(clean):
        span = seg["end"] - seg["start"]
        compact = _normalized_text(seg["text"])
        if span >= LONG_CUE_S and compact and len(compact) / span < LOW_TEXT_RATE:
            warnings.append({
                "start": seg["start"], "end": seg["end"], "text": seg["text"],
                "reason": "suspicious-long-low-text-cue", "action": "review",
            })

        if i >= 2 and compact and len(compact) <= 6:
            previous = [_normalized_text(clean[j]["text"]) for j in (i - 2, i - 1)]
            if previous == [compact, compact]:
                warnings.append({
                    "start": clean[i - 2]["start"], "end": seg["end"],
                    "text": seg["text"], "reason": "repeated-short-cue",
                    "action": "review",
                })

    return clean, warnings
