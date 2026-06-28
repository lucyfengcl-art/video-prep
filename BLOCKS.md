# Building blocks

The video-prep pipeline is a set of small, single-purpose pieces. The `/prep-clips`
skill just composes them in the common order. Use this catalog to wire them into a
**different** workflow — your own skill, a script, or by hand — without changing the
core. Each block is both a CLI command and an importable Python function.

## End-to-end commands

| Command | Input | Output |
|---|---|---|
| `video-prep-edit DIR` | folder of raw clips | `out/<date>/` with per-clip `NN.processed.mp4` + `NN.srt`, merged `final.mp4` + `final.srt`, and burned `final.subbed.mp4` |
| `video-prep DIR [--combine]` | clips | per-clip (or one combined) `.processed.mp4` + `.srt`, flat in `out/` |
| `video-prep-assemble DIR` | `NN-talk/screen-*` segments | one 1080×1920 video; `talk` segments cropped + subtitled, `screen` normalized |
| `video-prep-cut-filler VIDEO [--word W]` | finished video | scans (built-in `zh`/`en` filler lists when `--word` omitted), lists matches with context, cuts only the `--indices` you pick → `*.cleaned.mp4` + `.srt` (audio+video+subs) |
| `video-prep-burn VIDEO --srt S` | video + `.srt` | `*.subbed.mp4` with subtitles burned in |

## Composable functions (`from video_prep...`)

| Function | Module | Signature → returns |
|---|---|---|
| `cut_silence` | `cut` | `(src, dst, *, margin, edit_expression)` → trimmed video |
| `transcribe_to_srt` | `transcribe` | `(src, out_dir, *, language, model, output_name, max_chars)` → `.srt` path (`language` accepts "auto"; `max_chars` -1 = auto by language, 0 = off) |
| `speed_up` | `speedup` | `(src, dst, factor, *, fps, …)` → sped-up video, normalized to canonical CFR/SAR/sample-rate (concat-safe) |
| `rescale_srt` | `srt` | `(path, factor, *, out_path)` → time-scaled `.srt` |
| `concat_clips` | `concat` | `(sources, dst, *, fps, sample_rate, channels)` → one video; decodes + re-encodes via the concat filter, normalizing every input (no silent stream-copy desync) |
| `concat_srts` | `srt` | `(srts, offsets, out_path)` → one `.srt` with each clip shifted by its offset (seconds) |
| `process_clip` | `pipeline` | `(src, out_dir, *, out_name, speed, …)` → `ProcessResult(video, srt)` (full per-clip pipeline) |
| `process_combined` | `pipeline` | `(sources, out_dir, *, name, …)` → `ProcessResult` (concat then process once) |
| `find_matches` | `cut_filler` | `(segments, words, *, pad)` → list of match dicts (pure; multi-token + case-insensitive) |
| `cut_ranges` | `cut_filler` | `(src, dst, ranges)` → video with `[(start,end), …]` removed |
| `build_cut_srt` | `cut_filler` | `(segments, removed, cuts, out_path)` → `.srt` rebuilt on the post-cut timeline |
| `burn_subs` | `burn` | `(video, srt, out, *, font, font_size, outline, margin_v)` → subtitled video |
| `normalize` | `assemble` | `(src, dst, *, mode)` → 1080×1920 video (`cover` crop / `contain` pad) |

## Example: a custom workflow on top

```python
from pathlib import Path
from video_prep.pipeline import process_clip
from video_prep.burn import burn_subs

# Process one clip, then burn subtitles with your own styling.
r = process_clip(Path("raw/talk.mov"), Path("out/"), speed=1.2)
burn_subs(r.video, r.srt, Path("out/talk.subbed.mp4"), font_size=22, outline=2)
```

A future "workflow-builder" skill reads this catalog to know what it can wire
together, then generates a script like the above for the user's specific needs.
