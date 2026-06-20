---
name: prep-clips
description: Runs the tedious cleanup pass on raw video recordings before the real edit — cut silent gaps, transcribe subtitles in any language (Mandarin by default), normalize speed, and stitch clips in filename order. Use when the user drops recordings into a raw/ folder or asks to "clean up", "prep", or "edit" their clips. Outputs clean per-clip mp4 + .srt (plus an optional merged, subtitle-burned preview) ready to drop into any editor (CapCut, Premiere, DaVinci, …). This is pre-processing, not the creative edit.
version: 1.0.0
---

# Prep raw clips for editing

Do the boring cleanup pass on raw recordings so the clips are ready for whatever
edit comes next. It handles the parts nobody wants to do by hand — cut silent
gaps, add subtitles in any language (Mandarin by default), normalize speed, and
stitch clips in filename order — and hands back clean clips plus matching `.srt`,
in one command.

This is **pre-processing, not the creative edit.** Arrangement, transitions,
b-roll, music, and styling stay in your own flow — the output is meant to drop
straight into your editor (CapCut, Premiere, DaVinci, …). The same cleanup is
needed across many kinds of video, which is exactly why it's split out here.

## When this applies

The user has raw clips (usually in `./raw/`) and wants the tedious cleanup done —
they say things like "clean up my clips", "prep my footage", "cut the silence and
subtitle these", or simply "do the edit" / "edit my videos". If what they actually
want is creative arrangement or transitions, that's outside this skill; this only
prepares the raw material.

## How to invoke the tool

The Python package ships **inside this plugin**, so never `cd` into a repo and
never run a bare `uv run video-prep-...`. Instead call the bundled launcher,
which finds the package and runs it (auto-installing Python + deps on first use)
from **whatever directory the user is in**:

```sh
"${CLAUDE_SKILL_DIR}/scripts/video-prep" <console-script> [args...]
```

`${CLAUDE_SKILL_DIR}` is set when running as an installed plugin and points at
this skill's folder. If it is empty (e.g. running the skill from source), use the
absolute path to `scripts/video-prep` next to this `SKILL.md` instead. The
launcher keeps the current working directory, so relative paths like `./raw`
resolve against the user's folder.

## Prerequisites (check once)

The launcher uses `uv` to provide Python and all Python dependencies — those are
**not** installed by hand. The host still needs:

- any OS (macOS / Windows / Linux, Intel or ARM) — transcription uses
  `faster-whisper` on CPU, or a CUDA GPU automatically if present
- `uv` — `curl -LsSf https://astral.sh/uv/install.sh | sh` (the launcher prints
  this if it is missing)
- `ffmpeg` (silence cut / speed / concat): `brew install ffmpeg`
- `ffmpeg-full` (burning subtitles via libass): `brew install ffmpeg-full` plus a
  CJK font — `brew install --cask font-noto-sans-cjk-sc && fc-cache -f`

Subtitles work in any Whisper language; the default is Mandarin (`--language zh`)
— pass another language code to override. If `ffmpeg-full` is missing, the prep still produces the cleaned clips
and `.srt` files (just skips the burned preview); tell the user how to enable it.

## Steps

1. Confirm where the raw clips are (default `./raw/`). Clips merge in **filename
   order**, so `1.MOV`, `2.MOV` (or `01-...`, `02-...`) define the sequence.
2. Run the one-command prep (via the bundled launcher — see "How to invoke"):
   ```sh
   "${CLAUDE_SKILL_DIR}/scripts/video-prep" video-prep-edit ./raw
   ```
   This writes everything into `out/<today's date>/`:
   - `NN.processed.mp4` + `NN.srt` — each clip, cleaned (**the main handoff** — drop
     these into your editor)
   - `final.mp4` + `final.srt` — the clips merged in order, if you just want one
     stitched file
   - `final.subbed.mp4` — merged video with subtitles burned in, an **optional quick
     preview** to eyeball pacing or share as-is
3. Report the output folder. Point the user at the cleaned per-clip files as the
   handoff for their edit, and mention `final.subbed.mp4` as an optional preview.
   Re-running reuses the same dated folder and only reprocesses clips whose source
   file changed.

## Common follow-ups

- **Remove a filler word** (然后, 就是, 于是 …) from a merged clip — works for
  multi-character Mandarin words and lets you target a single occurrence:
  ```sh
  VP="${CLAUDE_SKILL_DIR}/scripts/video-prep"
  "$VP" video-prep-cut-filler out/<date>/final.mp4 --word 于是 --dry-run   # list matches
  "$VP" video-prep-cut-filler out/<date>/final.mp4 --word 于是 --indices 3 # cut just #3
  ```
- **Re-burn / restyle subtitles** on a preview:
  ```sh
  "${CLAUDE_SKILL_DIR}/scripts/video-prep" video-prep-burn out/<date>/final.mp4 \
      --srt out/<date>/final.srt --font-size 18 --outline 2 --margin-v 100
  ```

## Extending this

This is intentionally just the cleanup step. To build a fuller workflow on top, add
your **own** skill/command that calls the launcher (`scripts/video-prep
video-prep-edit`, or the building blocks in `BLOCKS.md`) and layers your editing
steps on the cleaned output — don't edit this skill in place. See `BLOCKS.md` for
the composable commands and functions available.
