# Prepping raw video clips with video-prep

When the user asks to **"clean up my clips"**, **"prep my footage"**, **"do the
edit"**, **"edit the raw clips"**, or drops recordings into a `raw/` folder and
wants them ready for editing, use the `video-prep` CLI described here.

It runs the tedious cleanup pass on raw recordings — cut silence → transcribe
subtitles (any language, Mandarin by default) → normalize speed → stitch clips in
filename order — and hands
back clean per-clip `.mp4` + `.srt` ready to drop into any editor (CapCut,
Premiere, …), plus an optional merged, subtitle-burned preview. This is
pre-processing, not the creative edit.

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
GPU automatically if present. The first run downloads the Whisper model (~3 GB).

## The one-command prep

Clips merge in **filename order** — `1.MOV`, `2.MOV` (or `01-...`, `02-...`) define
the sequence. Confirm where the raw clips are (default `./raw/`), then run:

```sh
video-prep-edit ./raw
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

## Common follow-ups

- **Remove a filler word** (然后, 就是, 于是 …) from a finished video:
  ```sh
  video-prep-cut-filler out/<date>/final.mp4 --word 于是 --dry-run   # list matches
  video-prep-cut-filler out/<date>/final.mp4 --word 于是 --indices 3 # cut just #3
  ```
- **Re-burn / restyle subtitles**:
  ```sh
  video-prep-burn out/<date>/final.mp4 --srt out/<date>/final.srt \
      --font-size 18 --outline 2 --margin-v 100
  ```

See `BLOCKS.md` for the lower-level commands and importable functions to compose a
different workflow.
