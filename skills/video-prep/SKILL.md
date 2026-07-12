---
name: video-prep
description: Runs the tedious cleanup pass on raw video recordings before the real edit — cut silent gaps, transcribe subtitles in any language (Mandarin by default), normalize speed, and stitch clips in natural numeric order. Use when the user drops recordings into a raw/ folder or asks to "clean up", "prep", or "edit" their clips. Outputs clean per-clip mp4 + .srt (plus an optional merged, subtitle-burned preview) ready to drop into any editor (CapCut, Premiere, DaVinci, …). This is pre-processing, not the creative edit.
version: 2.0.0
---

# Prep raw clips for editing

Do the boring cleanup pass on raw recordings so the clips are ready for whatever
edit comes next. It handles the parts nobody wants to do by hand — cut silent
gaps, add subtitles in any language (Mandarin by default), normalize speed, and
stitch clips in natural numeric order — and hands back clean clips plus matching `.srt`,
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

## First contact — introduce the skill before doing anything

If the user invokes this skill **without a concrete task** — a bare
`/video-prep`, a greeting, "what can this do?", "how do I use this?", or anything
that shows they just installed it and are exploring — **do not silently wait for
clips or start asking for a folder.** First give a short capability intro so they
know what's on offer and how to trigger each part.

**Answer in the user's language.** Match whatever language they wrote in — if they
message in Chinese, give the whole intro (and the example prompts) in Chinese; if
in English, English; and so on. The template below is written in English only as a
reference for *what to say* — translate it, don't echo it verbatim. Keep the
`./raw` folder name and CLI flags as-is, but everything a human reads should be in
their language. Use roughly this template (keep it tight):

> **Video Prep** does the boring cleanup pass on raw recordings so they're ready
> to edit — in one command. Here's what I can do and how to ask:
>
> 1. **Prep a folder of clips** (the main one) — cut silent gaps, add subtitles,
>    normalize speed, and stitch clips in order.
>    → *"Prep the clips in ./raw"* or *"clean up my footage in English"*
> 2. **Subtitles in any language** — Mandarin by default; say the language.
>    → *"…and subtitle them in English"* / *"detect the language automatically"*
> 3. **Suggest & remove filler words** (然后, 就是… / um, uh, you know…) — I list
>    matches with context and cut **only** the ones you pick.
>    → *"find the filler words"* / *"cut the ums"*
> 4. **Burn / restyle subtitles** onto a preview video.
>    → *"burn the subtitles bigger"* / *"restyle the captions"*
>
> Drop your recordings into a `raw/` folder and tell me which of these you want.
> To just get going: *"prep my clips in ./raw"*.

Then wait for their choice. Only skip this intro when the user's first message is
already an actionable request (they named a folder, a language, or a specific
capability) — in that case go straight to the matching section below. When you do
run a capability, briefly mention the *other* things the skill can do afterward so
they discover the full toolkit over time.

## What you can ask for (capability → how to invoke)

Quick map from what a user wants to the section that handles it:

| The user wants… | Trigger phrases | Go to |
| --- | --- | --- |
| The full cleanup pass on a folder | "prep / clean up / edit my clips", "do the edit" | **Steps** |
| Subtitles in a specific language | "in English", "in Japanese", "auto-detect the language" | **Steps** (step 2) |
| A big batch (10+ clips) done fast | "I have 20 clips", "this is a lot of footage" | **Handling many clips** |
| Filler words gone | "cut the ums", "remove 然后/就是", "clean up my speech" | **Common follow-ups** |
| Different-looking captions | "bigger subtitles", "restyle the captions", "move them up" | **Common follow-ups** |
| To build a bigger workflow on top | "add transitions too", "make my own edit flow" | **Extending this** |

## How to invoke the tool

The tool runs as console scripts — `video-prep-edit`, `video-prep-cut-filler`,
`video-prep-burn`, etc. There are two ways to reach them; pick whichever applies,
then use the bare command names in the examples below:

1. **Installed on `PATH`** — if `video-prep-edit` resolves (e.g. the user ran
   `uv tool install git+https://github.com/lucyfengcl-art/video-prep`), call the
   commands directly: `video-prep-edit ./raw`.
2. **Bundled launcher** (no separate install) — this skill ships a self-locating
   launcher at `scripts/video-prep` next to this `SKILL.md` that finds the package
   and runs it via `uv`, auto-installing Python + deps on first use. Prefix the
   command with it:
   ```sh
   "<skill-dir>/scripts/video-prep" video-prep-edit ./raw
   ```
   Resolve `<skill-dir>` to the folder containing this `SKILL.md`. The host
   usually exposes it as an env var — `$CLAUDE_SKILL_DIR` (Claude Code),
   `$CODEX_SKILL_DIR` / `$SKILL_DIR` (other agents) — otherwise use the absolute
   path of the directory you loaded this `SKILL.md` from.

Either way, don't `cd` into a source checkout or run a bare `uv run video-prep-…`.
The commands keep the current working directory, so relative paths like `./raw`
resolve against the user's folder. The examples below use the bare command names;
add the launcher prefix from (2) if the CLI isn't on `PATH`.

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
3. Run the one-command prep (see "How to invoke" — prefix with the launcher if
   `video-prep-edit` isn't on `PATH`):
   ```sh
   video-prep-edit ./raw                 # Mandarin
   video-prep-edit ./raw --language en   # English
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
  # 1. Scan with the language's default fillers and get machine-readable matches:
  video-prep-cut-filler out/<date>/final.mp4 --language en --json
  # (present the matches to the user with their prev/this/next context, let them pick)
  # 2. Cut only the ones they chose:
  video-prep-cut-filler out/<date>/final.mp4 --language en --indices 1,4,5
  ```
  Use `--word 于是` to target a specific word, or `--indices all` to take every
  match. Always confirm the selection with the user before cutting.
- **Re-burn / restyle subtitles** on a preview:
  ```sh
  video-prep-burn out/<date>/final.mp4 \
      --srt out/<date>/final.srt --font-size 18 --outline 2 --margin-v 100
  ```

## Extending this

This is intentionally just the cleanup step. To build a fuller workflow on top, add
your **own** skill/command that calls the launcher (`scripts/video-prep
video-prep-edit`, or the building blocks in `BLOCKS.md`) and layers your editing
steps on the cleaned output — don't edit this skill in place. See `BLOCKS.md` for
the composable commands and functions available.
