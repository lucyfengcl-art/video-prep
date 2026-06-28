---
name: prep-clips
description: Runs the tedious cleanup pass on raw video recordings before the real edit — cut silent gaps, transcribe subtitles in any language (Mandarin by default), normalize speed, and stitch clips in filename order. Use when the user drops recordings into a raw/ folder or asks to "clean up", "prep", or "edit" their clips. Outputs clean per-clip mp4 + .srt (plus an optional merged, subtitle-burned preview) ready to drop into any editor (CapCut, Premiere, DaVinci, …). This is pre-processing, not the creative edit.
version: 1.1.0
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

1. Confirm where the raw clips are (default `./raw/`) and check the sequence.
   Clips merge in **natural numeric order**, so `1.MOV, 2.MOV, … 10.MOV` sort
   correctly with no zero-padding, and mixed extensions (`.mp4`/`.MOV`) are fine.
   With many clips, list the resolved order and confirm it with the user before
   running — a wrong order otherwise wastes a long transcription pass.
2. Pick the spoken language. The default is Mandarin (`--language zh`). For other
   languages pass the Whisper code (e.g. `--language en` for English) or
   `--language auto` to detect it. If it isn't obvious from the request, ask the
   user. Subtitle line length adapts automatically (Chinese wraps by character,
   spaced languages like English wrap on whole words).
3. Run the one-command prep (via the bundled launcher — see "How to invoke"):
   ```sh
   "${CLAUDE_SKILL_DIR}/scripts/video-prep" video-prep-edit ./raw          # Mandarin
   "${CLAUDE_SKILL_DIR}/scripts/video-prep" video-prep-edit ./raw --language en
   ```
   This writes everything into `out/<today's date>/`:
   - `NN.processed.mp4` + `NN.srt` — each clip, cleaned (**the main handoff** — drop
     these into your editor)
   - `final.mp4` + `final.srt` — the clips merged in order, if you just want one
     stitched file
   - `final.subbed.mp4` — merged video with subtitles burned in, an **optional quick
     preview** to eyeball pacing or share as-is
4. Report the output folder. Point the user at the cleaned per-clip files as the
   handoff for their edit, and mention `final.subbed.mp4` as an optional preview.
   Re-running reuses the same dated folder and only reprocesses clips whose source
   file changed.

## Handling many clips

A folder of 10+ clips works the same way — one command — but keep these in mind:

- **One run, no divide-and-conquer.** Always process the whole folder in a single
  `video-prep-edit` call. Do **not** batch the clips or merge them pairwise
  yourself: the tool already cuts, transcribes, normalizes, and concatenates in one
  pass, and manual splitting/merging re-encodes the same footage repeatedly (slower,
  quality loss) and reintroduces audio/video drift at every seam.
- **Run it in the background.** Transcription dominates (~10–20s per clip on CPU
  with the default `large-v3-turbo`), so a large folder runs for many minutes and
  will exceed a single foreground command's timeout. Launch the run in the
  background and poll for completion instead of blocking on it.
- **Parallelize with `-j`.** Pass `-j 3` to `video-prep-edit` to process several
  clips at once (~1.4x faster on a multi-core CPU — transcription already uses all
  cores, so the gain is sub-linear). Each worker loads its own ~1.5 GB model, so
  keep it to 2–4 unless the machine has plenty of RAM.
- **Re-runs are cheap.** Per-clip output is cached by source mtime in the dated
  folder, so after you swap or re-trim one clip, re-running reprocesses only that
  clip and rebuilds the merge. Keep the same `out/<date>/` folder — don't delete it.
- **Sanity-check the result.** Confirm every clip produced an `NN.processed.mp4`
  and that `final.mp4`'s duration ≈ the sum of the clips; a large gap means a clip
  failed or was skipped.

## Common follow-ups

- **Remove filler words** (然后, 就是 … / um, uh, you know …) — the cutter
  **suggests, you decide**: it scans, lists matches with context, and cuts
  *nothing* until you pass `--indices`. Default word lists exist per language
  (Mandarin `zh`, English `en`); pass `--word` to override. Matching is
  case-insensitive and handles multi-token words (于是, "you know").

  Drive it as a two-step, user-in-the-loop flow:
  ```sh
  VP="${CLAUDE_SKILL_DIR}/scripts/video-prep"
  # 1. Scan with the language's default fillers and get machine-readable matches:
  "$VP" video-prep-cut-filler out/<date>/final.mp4 --language en --json
  # (present the matches to the user with their prev/this/next context, let them pick)
  # 2. Cut only the ones they chose:
  "$VP" video-prep-cut-filler out/<date>/final.mp4 --language en --indices 1,4,5
  ```
  Use `--word 于是` to target a specific word, or `--indices all` to take every
  match. Always confirm the selection with the user before cutting.
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
