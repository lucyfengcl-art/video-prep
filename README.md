# video-prep

**English** | [简体中文](README.zh-CN.md)

Automate the tedious cleanup pass that almost every talking-head edit needs: cut
silent gaps, transcribe speech to `.srt` (any language, Mandarin by default),
normalize speed. Outputs a clean
`.mp4` + matching `.srt` per input clip, ready to drop into any editor (CapCut,
Premiere, DaVinci, …) for the actual arrangement, transitions, and touch-ups.
It's the pre-processing, not the creative edit.

## How it works

For each clip, in order:

1. **Cut silence** with [`auto-editor`](https://auto-editor.com)
2. **Transcribe** the trimmed audio (at natural speed, for best accuracy) with
   [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper), model
   `large-v3-turbo` (≈2× faster than `large-v3` on CPU, negligible quality loss;
   use `--model large-v3` for maximum accuracy). Works in any Whisper language;
   defaults to Mandarin (`--language
   zh`, override with `--language`). Runs on CPU anywhere, or a CUDA GPU
   automatically if one is present.
3. **Speed up** to 1.2x with `ffmpeg` (`setpts` + `atempo`, preserves pitch)
4. **Rescale** the `.srt` timestamps by `1 / 1.2` so subtitles stay in sync

## One-command edit (recommended)

`video-prep-edit` runs the whole flow — process each clip, **merge in order**, and
**burn subtitles** — into a dated folder, so you don't chain commands by hand:

```sh
video-prep-edit ./raw
```

Output:

```
out/2026-06-15/                # today's date; pass --name to override
├── 01.processed.mp4  01.srt   # each clip, processed (in natural filename order)
├── 02.processed.mp4  02.srt
├── final.mp4         final.srt        # clips merged in order
└── final.subbed.mp4                   # merged + burned subtitles  ← upload this
```

The merged `.srt` is built by offsetting the per-clip subtitles (no second
transcription). Per-clip outputs are cached by mtime, so re-running after changing
one clip only reprocesses that clip — the merge and burn always rebuild from the
current pieces. Burning needs `ffmpeg-full` (see below); without it you still get
`final.mp4` + `final.srt`.

The sections below cover the lower-level commands (`video-prep`, `-burn`,
`-cut-filler`, `-assemble`) that `video-prep-edit` is built from — see also
[`BLOCKS.md`](BLOCKS.md).

## Requirements

- macOS, Windows, or Linux (Intel or ARM) — transcription runs on CPU via
  `faster-whisper`, or a CUDA GPU automatically if present
- `ffmpeg` — `brew install ffmpeg` (macOS) / your package manager elsewhere
- `ffmpeg-full` (subtitle burning) — `brew install ffmpeg-full` plus
  `brew install --cask font-noto-sans-cjk-sc && fc-cache -f`
- `uv` — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Python 3.11+ (auto-installed by `uv`)

## Install

Install the CLI globally straight from GitHub — works on any machine, no clone:

```sh
uv tool install git+https://github.com/lucyfengcl-art/video-prep
```

This puts `video-prep`, `video-prep-edit`, `video-prep-burn`, and
`video-prep-cut-filler` on your `PATH`. Upgrade later with
`uv tool upgrade video-prep`.

> Running the commands below from a **source checkout** instead? Use `uv sync`
> once, then prefix each command with `uv run` (e.g. `uv run video-prep-edit`).

The first transcription run downloads the Whisper model (~1.6 GB for
`large-v3-turbo`); subsequent runs use the cached copy in `~/.cache/huggingface`.

## Usage

Two modes: per-clip (default) or combined (`--combine`).

### Per-clip mode

Each input gets its own processed `.mp4` + `.srt`. Useful when you want to
arrange / rearrange sections in CapCut.

```sh
# single clip
video-prep clip.mov

# whole folder of clips
video-prep ./raw/

# different output dir
video-prep ./raw/ -o ./out/

# tweak speed or silence margin
video-prep ./raw/ --speed 1.3 --margin 0.3s

# keep work dir for debugging
video-prep clip.mov --keep-intermediates
```

Outputs land in `./out/` (default):

```
out/
├── clip1.processed.mp4
├── clip1.srt
├── clip2.processed.mp4
└── clip2.srt
```

### Combined mode

All inputs are concatenated (in order) into one video before processing, so
you get **one** `.mp4` + **one** `.srt`. Useful when the order is fixed —
clips in a folder are sorted by **natural** filename order, so `1.mov, 2.mov,
… 10.mov` sequence correctly with no zero-padding needed (`01-`, `02-` also
works). Silence between clips also gets trimmed (e.g. you repositioning the
phone).

```sh
# combine a folder of clips named 1.mov, 2.mov, ... 10.mov
video-prep ./raw/ --combine

# custom output basename
video-prep ./raw/ --combine --name vlog-2026-05-25

# explicit order on the command line beats filename order
video-prep intro.mov middle.mov outro.mov --combine
```

Output:

```
out/
├── combined.processed.mp4    # or {--name}.processed.mp4
└── combined.srt
```

Drag both into CapCut, drop the `.srt` onto the subtitle track, do final
touch-ups.

## First-run smoke test

1. AirDrop a short (~30s) Mandarin clip from your phone to the project folder
2. `video-prep test.mov`
3. First run will download the Whisper model — be patient
4. Open `out/test.processed.mp4` in QuickPlayer:
   - Silent gaps should be removed
   - Audio plays at ~1.2x, pitch unchanged (no chipmunk voice)
5. Open `out/test.srt` — check the Chinese transcription
6. Drop both into a fresh CapCut project — **the key check**: subtitles should
   stay aligned with audio after the speed change. If they drift, the
   timestamp rescaling has a bug (off-by-1.2x).

## Cutting filler words (然后, 就是 … / um, uh …)

After the main pipeline, scrub a finished video for spoken filler words — removed
from audio AND video together. The cutter **suggests, you decide**: it scans and
lists matches with sentence context, and removes nothing until you pick which
with `--indices`.

```sh
# 1. Scan with the language's built-in filler list (zh by default); lists matches
video-prep-cut-filler out/final.mp4

# English clip; --json prints matches for a tool/agent to present for selection
video-prep-cut-filler out/final.mp4 --language en --json

# target specific words instead of the defaults
video-prep-cut-filler out/final.mp4 --word 然后 --word 就是

# 2. Cut only the matches you chose (1-based ranges, or 'all')
video-prep-cut-filler out/final.mp4 --indices 1,3,5-8
video-prep-cut-filler out/final.mp4 --word 然后 --indices all -o out/final.cleaned.mp4
```

Notes:

- Built-in filler lists exist for `zh` and `en`; `--word` overrides them.
- Matching is case-insensitive and spans multi-token words (于是, "you know").
- Each match shows prev/this/next context, so you can tell whether an ambiguous
  word (English "so", "like") is really a filler before cutting it.

How it works:

1. Transcribes with word-level timestamps to get per-word start/end times.
2. An ffmpeg `select`/`aselect` filter drops every chosen word's time range —
   audio and video stay in sync.
3. Rebuilds the `.srt` from the same transcription — dropping the cut tokens and
   shifting later timestamps onto the new timeline (no second transcription pass).

Each cut is ~0.2–0.6s, so expect roughly that × N word occurrences shaved off
the total runtime. Visual jump cuts are tiny and read as normal Rednote pacing.

## Burning subtitles into the video for preview

`video-prep-burn` renders `.srt` text onto the video so you can preview the
pacing without opening CapCut. Defaults: **Noto Sans CJK SC Bold** (the
open-source equivalent of CapCut's 思源黑体), size 18, no outline, sitting
near the bottom edge of the frame.

```sh
# defaults (looks for <stem>.srt next to the video, writes <stem>.subbed.mp4)
video-prep-burn out/combined.cleaned.mp4

# tweak styling
video-prep-burn out/combined.cleaned.mp4 \
    --font-size 26 --outline 3 --margin-v 100

# different srt or output path
video-prep-burn out/combined.cleaned.mp4 \
    --srt out/combined.cleaned.srt \
    -o out/preview.mp4
```

Requires `ffmpeg-full` (auto-detected at `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`):

```sh
brew install ffmpeg-full
brew install --cask font-noto-sans-cjk-sc
fc-cache -f
```

The plain `brew install ffmpeg` bottle is built without libass and can't
render subtitles. The font cask + `fc-cache -f` makes libass aware of the
font for selection.

## Tuning

- `--margin 0.3s` if Mandarin tone tails are getting clipped
- `--edit "audio:threshold=0.03"` to cut more aggressively on quiet audio
- `--model large-v3` for maximum subtitle accuracy (slower); `--model medium`
  (or `small`) if even the default `large-v3-turbo` is too slow on CPU
- `--language en` (or any Whisper code, or `auto` to detect) for non-Mandarin
  clips; subtitle wrapping adapts (word-wrap for spaced languages, char-wrap for
  Chinese)
- `-j 3` to process clips in parallel on a multi-core CPU (~1.4×)
- `--max-chars` controls subtitle cue length: default `-1` auto-picks by language
  (20 for Chinese, 42 for spaced languages); `0` keeps Whisper's original lengths

## Speeding up a multi-clip edit

- **Re-runs are incremental.** `video-prep-edit` caches each `NN.processed.mp4` /
  `NN.srt` by source mtime in the dated `out/` folder. Keep that folder and just
  re-run after changing one raw clip — only that clip re-transcribes, then the
  merge rebuilds. (Don't delete `out/` between runs.)
- **Parallelize with `-j N`.** `video-prep-edit -j 3 ./raw` processes several
  clips at once (~1.4× on a multi-core CPU; sub-linear because transcription
  already uses every core). Each worker loads its own ~1.5 GB model, so keep `N`
  to 2–4 unless you have plenty of RAM.
- **Don't pairwise-merge ("divide and conquer").** The clips are the independent,
  cacheable unit; the merge is one pass. Merging already-merged files re-encodes
  the same footage repeatedly (slower, quality loss) and compounds A/V drift at
  every level. Let the tool process clips once and concatenate them in a single
  step.

## Use it from your coding agent

You can drive the whole edit by just saying *"edit my raw clips"* — the agent runs
`video-prep-edit ./raw` for you. Works with either agent; both need `ffmpeg`
(+ `ffmpeg-full` for burning) on the machine, as listed under
[Requirements](#requirements).

### Claude Code (skill + plugin)

This repo ships a **`prep-clips` skill** and packages itself as a **Claude Code
plugin**, so you can say *"clean up my raw clips"* (or invoke
`/video-prep:prep-clips`) and Claude runs the cleanup pass. Install the plugin
from GitHub:

```
/plugin marketplace add lucyfengcl-art/video-prep
/plugin install video-prep
```

The plugin bundles the Python tool and runs it through `uv` via a self-locating
launcher, so it works from any folder — no separate install step beyond `uv` +
`ffmpeg`.

### Codex (or any other shell-driven agent)

Codex has no plugin system, so install the CLI once and let the agent call it:

```sh
uv tool install git+https://github.com/lucyfengcl-art/video-prep
```

The repo's [`AGENTS.md`](AGENTS.md) tells Codex when and how to run
`video-prep-edit`. Copy it (or its relevant lines) into the project where you keep
your clips, then ask the agent to *"edit my raw clips"*.

## Customize and extend

The skill is intentionally just the **cleanup pass**. There are three ways to adapt
it to your own flow — pick the lightest one that does the job.

> **Don't edit the installed copy.** Files under `~/.claude/plugins/…` (and a
> `uv tool install`-ed CLI) live in a managed directory that gets **overwritten on
> the next update**. Hand-edits there are silently lost. Use one of the paths below
> instead — they all survive updates.

**1. Pass different options — no editing.** Most "changes" are already flags, so
just tell the agent (or type them yourself):

| Want to change | Flag |
|---|---|
| Speed | `--speed 1.3` |
| Subtitle language | `--language en` (any Whisper language) |
| Silence sensitivity | `--margin 0.3s`, `--edit "audio:threshold=0.03"` |
| Whisper model | `--model medium` |
| Subtitle styling | `video-prep-burn --font-size 26 --outline 3 --margin-v 100` |

**2. Build your own skill on top (recommended for repeatable workflows).** Add a
skill in your **own** `~/.claude/skills/` (or a project's `.claude/skills/`) that
calls `video-prep-edit` — or the smaller building blocks in [`BLOCKS.md`](BLOCKS.md)
— and layers your editing steps on the cleaned output. It lives in your space, so
plugin updates never touch it. Plugin skills are namespaced (`video-prep:prep-clips`),
so give yours its own name (e.g. `/my-edit`); it won't clash.

**3. Fork it.** To change the core behavior and keep it, fork the repo and install
**your fork** — `/plugin marketplace add <you>/video-prep` for Claude Code, or
`uv tool install git+https://github.com/<you>/video-prep` for the CLI.

## Tests

```sh
uv run pytest
```

Unit tests cover the SRT timestamp scaler, the per-clip SRT concatenation
(`concat_srts`), and the filler-word matcher (multi-character Mandarin words like
于是) + post-cut SRT rebuild — the pieces with non-obvious math where a bug would
silently desync subtitles.
