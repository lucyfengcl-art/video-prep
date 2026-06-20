"""Rescale SRT subtitle timestamps by a constant factor.

When the underlying video is sped up by N, timestamps must be divided by N to
stay in sync. Pure-string transform so we don't depend on a subtitle library.
"""

from __future__ import annotations

import re
from pathlib import Path

TIMESTAMP_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _ts_to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def _ms_to_ts(ms: int) -> str:
    ms = max(0, ms)
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def rescale_timestamp(ts: str, factor: float) -> str:
    """Divide a single 'HH:MM:SS,mmm' timestamp by factor."""
    match = TIMESTAMP_RE.fullmatch(ts)
    if not match:
        raise ValueError(f"not an SRT timestamp: {ts!r}")
    total_ms = _ts_to_ms(*match.groups())
    return _ms_to_ts(round(total_ms / factor))


def rescale_srt_text(text: str, factor: float) -> str:
    """Rescale every HH:MM:SS,mmm timestamp in an SRT string."""
    if factor <= 0:
        raise ValueError("factor must be positive")

    def sub(match: re.Match[str]) -> str:
        return rescale_timestamp(match.group(0), factor)

    return TIMESTAMP_RE.sub(sub, text)


def rescale_srt(path: Path, factor: float, *, out_path: Path | None = None) -> Path:
    """Read SRT at `path`, divide timestamps by `factor`, write result.

    Overwrites `path` unless `out_path` is given.
    """
    path = Path(path)
    target = Path(out_path) if out_path else path
    rescaled = rescale_srt_text(path.read_text(encoding="utf-8"), factor)
    target.write_text(rescaled, encoding="utf-8")
    return target


def _shift_timestamp(ts: str, delta_ms: int) -> str:
    """Add `delta_ms` to a single 'HH:MM:SS,mmm' timestamp."""
    match = TIMESTAMP_RE.fullmatch(ts)
    if not match:
        raise ValueError(f"not an SRT timestamp: {ts!r}")
    return _ms_to_ts(_ts_to_ms(*match.groups()) + delta_ms)


def _iter_blocks(text: str):
    """Yield (time_line, text_lines) for each cue in an SRT string.

    The leading numeric index is dropped (callers renumber); the `-->` line is
    returned verbatim so its two timestamps can be shifted, followed by the
    remaining text lines of the cue.
    """
    for raw_block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in raw_block.splitlines() if ln.strip() != ""]
        if not lines:
            continue
        time_idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if time_idx is None:
            continue
        yield lines[time_idx], lines[time_idx + 1:]


def concat_srts(
    srts: list[Path], offsets: list[float], out_path: Path
) -> Path:
    """Merge per-clip SRTs into one, shifting clip i by offsets[i] seconds.

    `offsets[i]` is the start time of clip i on the merged timeline (i.e. the
    cumulative duration of the preceding clips). Cues are renumbered 1..N. This
    lets us build a combined .srt from already-transcribed per-clip subtitles
    without a second transcription pass.
    """
    if len(srts) != len(offsets):
        raise ValueError("srts and offsets must be the same length")

    out_lines: list[str] = []
    idx = 1
    for srt, offset in zip(srts, offsets):
        delta_ms = round(offset * 1000)
        text = Path(srt).read_text(encoding="utf-8")
        for time_line, body in _iter_blocks(text):
            shifted = TIMESTAMP_RE.sub(
                lambda m: _shift_timestamp(m.group(0), delta_ms), time_line
            )
            out_lines.append(str(idx))
            out_lines.append(shifted)
            out_lines.extend(body)
            out_lines.append("")
            idx += 1

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return out_path


# Punctuation/whitespace that may trail a stripped word at the start of a line.
_TRAILING_PUNCT = "，。、！？!?,.:;"


def strip_leading_words(text: str, words: list[str]) -> tuple[str, int]:
    """For each SRT entry, strip leading occurrences of any `words` from its
    text. Returns (new_text, count_removed). Useful for cleaning up filler-word
    hallucinations from a re-transcription after audio cuts."""
    new_lines: list[str] = []
    removed = 0
    for raw in text.splitlines():
        line = raw
        if line and not line[0].isdigit() and "-->" not in line:
            changed = True
            while changed:
                changed = False
                stripped = line.lstrip()
                for w in words:
                    if stripped.startswith(w):
                        leading = line[: len(line) - len(stripped)]
                        rest = stripped[len(w):].lstrip(_TRAILING_PUNCT).lstrip()
                        line = leading + rest
                        removed += 1
                        changed = True
                        break
        new_lines.append(line)
    return "\n".join(new_lines), removed


def strip_leading_words_in_file(
    path: Path, words: list[str], *, out_path: Path | None = None
) -> tuple[Path, int]:
    path = Path(path)
    target = Path(out_path) if out_path else path
    new_text, removed = strip_leading_words(
        path.read_text(encoding="utf-8"), words
    )
    target.write_text(new_text, encoding="utf-8")
    return target, removed
