#!/usr/bin/env bash
# Build a self-contained skill zip for uploading as a standalone skill
# (e.g. claude.ai). Bundles the Python package inside the skill folder so the
# launcher at scripts/video-prep finds pyproject.toml without the full repo.
#
# Usage:  scripts/package-skill.sh [OUT_ZIP]   (default: dist/video-prep-skill.zip)
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-$root/dist/video-prep-skill.zip}
case $out in /*) ;; *) out=$PWD/$out ;; esac

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
skill=$stage/video-prep

cp -R "$root/skills/video-prep" "$skill"
cp "$root/pyproject.toml" "$root/uv.lock" "$root/README.md" "$root/LICENSE" "$skill/"
mkdir -p "$skill/src"
cp -R "$root/src/video_prep" "$skill/src/"

find "$skill" \( -name .DS_Store -o -name __pycache__ \) -prune -exec rm -rf {} +

mkdir -p "$(dirname "$out")"
rm -f "$out"
(cd "$stage" && zip -qrX "$out" video-prep)
echo "Built $out ($(du -h "$out" | cut -f1))"
