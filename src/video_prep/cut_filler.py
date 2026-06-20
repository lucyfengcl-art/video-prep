"""Cut filler words (e.g. 然后, 于是) from a finished video + rebuild its .srt.

Workflow:
1. Transcribe input once with word-level timestamps (faster-whisper) to get
   per-word start/end times.
2. Find every run of words matching any of the user's --word targets. Matching
   slides a window over consecutive word tokens, so multi-character Mandarin
   words survive Whisper splitting them into per-character tokens (于 + 是).
3. Use ffmpeg's `select`/`aselect` filters to drop those time ranges from
   audio AND video together, so they stay in sync.
4. Rebuild the .srt from the *same* transcription -- drop the cut tokens and
   shift later timestamps onto the new timeline. No second transcription pass.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from video_prep.transcribe import DEFAULT_MODEL, transcribe_segments

# Punctuation we ignore when matching transcribed words against --word targets.
_PUNCT_RE = re.compile(
    r"[\s。，、！？!?,.;:\"'“”‘’「」『』（）()【】《》\-]+"
)


def normalize_word(w: str) -> str:
    return _PUNCT_RE.sub("", w)


def find_word_ranges(
    video: Path,
    words: set[str],
    *,
    model: str = DEFAULT_MODEL,
    language: str = "zh",
    pad: float = 0.05,
) -> tuple[list[dict], list[dict]]:
    """Find filler-word occurrences and return ``(matches, segments)``.

    Each match has the padded start/end cut window, the raw matched text, the
    segment index, the indices of the matched word tokens within that segment
    (so the .srt can drop exactly those), and prev/this/next segment text for
    the dry-run context table. ``segments`` is the full transcript, reused to
    rebuild the .srt without transcribing again.
    """
    video = Path(video)
    segments = transcribe_segments(
        video, language=language, model=model, word_timestamps=True
    )
    return find_matches(segments, words, pad=pad), segments


def find_matches(
    segments: list[dict], words: set[str], *, pad: float = 0.05
) -> list[dict]:
    """Locate filler-word runs in an already-transcribed `segments` list.

    Pure function (no transcription) so it is unit-testable. Matching slides a
    window over consecutive word tokens within each segment, so a multi-char
    target like 于是 matches even when Whisper emits 于 and 是 as separate tokens.
    """
    targets = {normalize_word(w) for w in words if normalize_word(w)}
    max_len = max((len(t) for t in targets), default=0)
    if max_len == 0:
        return []

    matches: list[dict] = []
    for seg_idx, seg in enumerate(segments):
        toks = seg.get("words", [])
        norm = [normalize_word(t["word"]) for t in toks]
        i = 0
        while i < len(toks):
            # Grow a window of consecutive tokens until its concatenation hits a
            # target (catches 于 + 是 == 于是) or exceeds the longest target.
            acc = ""
            last = None
            for j in range(i, min(len(toks), i + max_len + 4)):
                acc += norm[j]
                if len(acc) > max_len:
                    break
                if acc and acc in targets:
                    last = j
                    break
            if last is None:
                i += 1
                continue
            prev_text = (
                segments[seg_idx - 1].get("text", "").strip()
                if seg_idx > 0 else ""
            )
            next_text = (
                segments[seg_idx + 1].get("text", "").strip()
                if seg_idx + 1 < len(segments) else ""
            )
            matches.append({
                "start": max(0.0, float(toks[i]["start"]) - pad),
                "end": float(toks[last]["end"]) + pad,
                "word": "".join(toks[k]["word"] for k in range(i, last + 1)),
                "segment_text": (seg.get("text") or "").strip(),
                "segment_idx": seg_idx,
                "word_indices": list(range(i, last + 1)),
                "prev_segment_text": prev_text,
                "next_segment_text": next_text,
            })
            i = last + 1
    return matches


def parse_indices(spec: str, max_idx: int) -> list[int]:
    """Parse '1,3,5-7,10' or 'all' into a sorted list of 1-based indices."""
    if spec.strip().lower() in ("all", "*"):
        return list(range(1, max_idx + 1))
    chosen: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            for i in range(int(a), int(b) + 1):
                chosen.add(i)
        else:
            chosen.add(int(part))
    if not chosen:
        raise ValueError(f"no valid indices in {spec!r}")
    if min(chosen) < 1 or max(chosen) > max_idx:
        raise ValueError(
            f"indices must be in 1..{max_idx}, got {sorted(chosen)!r}"
        )
    return sorted(chosen)


def cut_ranges(src: Path, dst: Path, ranges: list[tuple[float, float]]) -> Path:
    """Remove [(start, end), ...] (seconds) from src using ffmpeg filters.

    `select` + `aselect` keep only frames/samples outside every cut range; the
    `setpts`/`asetpts` resets make playback continuous after the drops.
    """
    if not ranges:
        shutil.copy2(src, dst)
        return dst
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    expr = "*".join(f"not(between(t,{a:.3f},{b:.3f}))" for a, b in ranges)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
        "-af", f"aselect='{expr}',asetpts=N/SR/TB",
        str(dst),
    ]
    subprocess.run(cmd, check=True)
    return dst


def _srt_ts(t: float) -> str:
    """Format seconds as an 'HH:MM:SS,mmm' SRT timestamp."""
    ms = max(0, round(t * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_cut_srt(
    segments: list[dict],
    removed: set[tuple[int, int]],
    cuts: list[tuple[float, float]],
    out_path: Path,
) -> Path:
    """Rebuild an .srt from `segments` after `cuts` were removed from the video.

    `removed` is the set of (segment_idx, word_idx) tokens that were cut; those
    are dropped from the cue text. Every surviving timestamp is compressed onto
    the post-cut timeline by subtracting the total cut duration before it -- the
    same ranges ffmpeg removed -- so subtitles stay in sync without a re-transcribe.
    """
    cuts = sorted(cuts)

    def compress(t: float) -> float:
        shift = 0.0
        for s, e in cuts:
            if t >= e:
                shift += e - s
            elif t > s:  # inside a cut: clamp to its start
                shift += t - s
                break
            else:
                break
        return max(0.0, t - shift)

    lines: list[str] = []
    idx = 1
    for seg_idx, seg in enumerate(segments):
        toks = seg.get("words") or []
        if toks:
            kept = [
                (k, t) for k, t in enumerate(toks)
                if (seg_idx, k) not in removed
            ]
            if not kept:
                continue
            text = "".join(t["word"] for _, t in kept).strip()
            start = compress(float(kept[0][1]["start"]))
            end = compress(float(kept[-1][1]["end"]))
        else:  # segment with no word-level timing: keep as-is
            text = (seg.get("text") or "").strip()
            start = compress(float(seg["start"]))
            end = compress(float(seg["end"]))
        if not text:
            continue
        if end <= start:
            end = start + 0.1
        lines += [str(idx), f"{_srt_ts(start)} --> {_srt_ts(end)}", text, ""]
        idx += 1

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _fmt_time(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def _format_match_table(matches: list[dict]) -> str:
    """Each match printed with its time window and prev/this/next context."""
    lines = []
    for i, m in enumerate(matches, 1):
        lines.append(
            f"  [{i:>2}] {_fmt_time(m['start'])} - {_fmt_time(m['end'])} "
            f"({m['end']-m['start']:.2f}s)"
        )
        if m.get("prev_segment_text"):
            lines.append(f"       prev: {m['prev_segment_text']}")
        lines.append(f"       this: {m['segment_text']}")
        if m.get("next_segment_text"):
            lines.append(f"       next: {m['next_segment_text']}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="video-prep-cut-filler",
        description=(
            "Cut filler words (e.g. 然后) from a video and regenerate its .srt"
        ),
    )
    parser.add_argument("video", type=Path, help="Input video (.mp4/.mov)")
    parser.add_argument(
        "--word",
        action="append",
        required=True,
        help="Filler word to cut (repeatable, e.g. --word 然后 --word 就是)",
    )
    parser.add_argument(
        "-o", "--out",
        type=Path,
        help="Output video path (default: <input-stem>.cleaned<ext> next to input)",
    )
    parser.add_argument(
        "--pad",
        type=float,
        default=0.05,
        help="Seconds of padding on each side of each cut (default: 0.05)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--language", default="zh")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Find and list matches without cutting",
    )
    parser.add_argument(
        "--indices",
        help=(
            "Cut only the listed matches (1-based). "
            "Examples: '1,3,5-8' or 'all'. Default: cut everything found."
        ),
    )
    args = parser.parse_args(argv)

    src = args.video.resolve()
    if not src.is_file():
        print(f"error: video not found: {src}", file=sys.stderr)
        return 2

    out = (args.out.resolve() if args.out
           else src.with_name(f"{src.stem}.cleaned{src.suffix}"))

    print(f"Scanning {src.name} for: {', '.join(args.word)}")
    matches, segments = find_word_ranges(
        src,
        set(args.word),
        model=args.model,
        language=args.language,
        pad=args.pad,
    )

    if not matches:
        print("No occurrences found.")
        return 0

    total = sum(m["end"] - m["start"] for m in matches)
    print(f"\nFound {len(matches)} occurrence(s), {total:.2f}s total:")
    print(_format_match_table(matches))

    if args.dry_run:
        print("(dry-run: nothing written)")
        return 0

    if args.indices:
        chosen = parse_indices(args.indices, len(matches))
        selected = [matches[i - 1] for i in chosen]
        print(
            f"Cutting {len(selected)} of {len(matches)} matches "
            f"(indices: {chosen}) -> {out}"
        )
    else:
        selected = matches
        print(f"\nCutting all {len(matches)} matches -> {out}")
    ranges = [(m["start"], m["end"]) for m in selected]
    cut_ranges(src, out, ranges)

    # Rebuild the .srt from the transcription we already have: drop the cut
    # tokens and shift later timestamps. No second transcription pass.
    removed = {
        (m["segment_idx"], k)
        for m in selected for k in m["word_indices"]
    }
    srt = build_cut_srt(segments, removed, ranges, out.with_suffix(".srt"))
    print(f"-> {out}")
    print(f"-> {srt}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
