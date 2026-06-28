# Prepping raw video clips with video-prep

When the user asks to **"clean up my clips"**, **"prep my footage"**, **"do the
edit"**, **"edit the raw clips"**, or drops recordings into a `raw/` folder and
wants them ready for editing, use the `video-prep` CLI described here.

It runs the tedious cleanup pass on raw recordings — cut silence → transcribe
subtitles (any language, Mandarin by default) → normalize speed → stitch clips in
natural numeric order — and hands back clean per-clip `.mp4` + `.srt` ready to drop
into any editor (CapCut, Premiere, …), plus an optional merged, subtitle-burned
preview. This is pre-processing, not the creative edit.

## Setup (check once)

The CLI is a Python tool installed with `uv`. If `video-prep-edit` is not on the
`PATH`, install it:

```sh
uv tool install git+https://github.com/lucyfengcl-art/video-prep
```

System dependencies the tool cannot install itself:

- `uv` — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `ffmpeg` (silence cut / speed / concat)
- `ffmpeg-full` + a CJK font (only needed to **burn** subtitles) —
  `brew install ffmpeg-full && brew install --cask font-noto-sans-cjk-sc && fc-cache -f`

Transcription runs on CPU on any OS (macOS/Windows/Linux, Intel or ARM), or a CUDA
GPU automatically if present. The first run downloads the Whisper model
(`large-v3-turbo`, ~1.6 GB; pass `--model large-v3` for maximum accuracy).

## The one-command prep

1. **Check the order.** Clips merge in **natural numeric order**, so `1.MOV,
   2.MOV, … 10.MOV` sort correctly with no zero-padding, and mixed extensions
   (`.mp4`/`.MOV`) are fine. With many clips, list the resolved order and confirm
   it before running — a wrong order wastes a long transcription pass.
2. **Pick the language.** Default is Mandarin (`--language zh`). For others pass
   the Whisper code (`--language en`) or `--language auto` to detect. Ask the user
   if it isn't clear. Subtitle line length adapts automatically (Chinese wraps by
   character, spaced languages like English wrap on whole words).
3. **Run it** (default location `./raw/`):

```sh
video-prep-edit ./raw                 # Mandarin
video-prep-edit ./raw --language en   # English
```

This writes into `out/<today's date>/`:

- `NN.processed.mp4` + `NN.srt` — each clip, cleaned (**the main handoff** — drop
  these into the user's editor)
- `final.mp4` + `final.srt` — the clips merged in order, if they just want one file
- `final.subbed.mp4` — merged video with subtitles burned in, an **optional preview**

Report the output folder, pointing at the cleaned per-clip files as the handoff for
editing and `final.subbed.mp4` as an optional preview. Re-running reuses the same
dated folder and only reprocesses clips whose source file changed. If
`ffmpeg-full` is missing, the prep still produces `final.mp4` + `final.srt` and
skips `final.subbed.mp4` — tell the user how to enable burning.

## Many clips (10+)

- **One run, no divide-and-conquer.** Always process the whole folder in a single
  `video-prep-edit` call — the tool cuts, transcribes, normalizes, and
  concatenates in one pass. Merging clips pairwise yourself re-encodes the same
  footage repeatedly (slower, quality loss) and causes A/V drift.
- **Run it in the background.** Transcription dominates (~10–20s per clip on CPU),
  so a large folder runs for minutes and can exceed a foreground command timeout.
- **Parallelize with `-j`.** `video-prep-edit -j 3 ./raw` processes several clips
  at once (~1.4× — sub-linear, since transcription already uses all cores). Each
  worker loads its own ~1.5 GB model, so keep `-j` to 2–4 unless RAM is plentiful.
- **Sanity-check.** Confirm every clip produced an `NN.processed.mp4` and that
  `final.mp4`'s duration ≈ the sum of the clips.

## Common follow-ups

- **Remove filler words** (然后, 就是 … / um, uh, you know …) — the cutter
  **suggests, you decide**: it scans, lists matches with prev/this/next context,
  and cuts *nothing* until you pass `--indices`. `--word` is optional (built-in
  default lists for `zh` and `en`); matching is case-insensitive and handles
  multi-token words (于是, "you know"). Drive it in two steps:
  ```sh
  # 1. scan (--json gives machine-readable matches to present for selection)
  video-prep-cut-filler out/<date>/final.mp4 --language en --json
  # 2. cut only the chosen matches (or --indices all)
  video-prep-cut-filler out/<date>/final.mp4 --language en --indices 1,4,5
  ```
  Always confirm the selection with the user before cutting.
- **Re-burn / restyle subtitles**:
  ```sh
  video-prep-burn out/<date>/final.mp4 --srt out/<date>/final.srt \
      --font-size 18 --outline 2 --margin-v 100
  ```

See `BLOCKS.md` for the lower-level commands and importable functions to compose a
different workflow.
