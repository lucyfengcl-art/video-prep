# video-prep

This repo provides the **`video-prep` skill** and the **`video-prep-edit` CLI**
for prepping raw video clips before the real edit: cut silent gaps, transcribe
subtitles (any language, auto-detected), normalize speed, and stitch clips
in natural numeric order — outputting clean per-clip `.mp4` + `.srt` plus an
optional merged, subtitle-burned preview. Pre-processing, not the creative edit.

When the user asks to "clean up / prep / edit my clips" (usually in `./raw/`),
process the whole folder in **one** run — never merge clips pairwise yourself:

```sh
video-prep-edit ./raw            # language auto-detected; or --language en / es / zh
video-prep-edit ./raw -j 3       # parallelize many clips on a multi-core CPU
```

Full, authoritative guidance lives in the skill — read it before running:

- **Skill (source of truth):** [`skills/video-prep/SKILL.md`](skills/video-prep/SKILL.md)
- **CLI install:** `uv tool install git+https://github.com/lucyfengcl-art/video-prep`
- **Human docs:** [`README.md`](README.md) · [`BLOCKS.md`](BLOCKS.md) (lower-level building blocks)

Requires `ffmpeg` (and `ffmpeg-full` to burn subtitles) on the machine.
