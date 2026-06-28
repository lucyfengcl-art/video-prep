"""Suggested filler words per language for `video-prep-cut-filler`.

These are only *candidates*: the cutter scans for them and presents matches with
context for the user to choose from — nothing is removed without an explicit
selection. Many (especially English `like`, `so`, `actually`) double as ordinary
words, which is exactly why the workflow suggests rather than auto-cuts.
"""

from __future__ import annotations

DEFAULT_FILLERS: dict[str, list[str]] = {
    "zh": ["然后", "就是", "那个", "这个", "嗯", "呃", "啊", "反正", "其实"],
    "en": ["um", "uh", "er", "erm", "hmm", "like", "you know", "i mean",
           "kind of", "sort of", "basically", "literally", "actually"],
}


def default_fillers(language: str | None) -> list[str]:
    """Suggested filler words for `language` (Whisper code); empty if unknown."""
    if not language:
        return []
    return list(DEFAULT_FILLERS.get(language.lower(), []))
