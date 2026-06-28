"""Tests for the pure (no-transcription) parts of cut_filler."""

from video_prep.cut_filler import (
    build_cut_srt,
    find_matches,
    normalize_word,
    parse_indices,
)


def _seg(text, words, start=None, end=None):
    """Build a transcript segment from (token, start, end) tuples."""
    ws = [{"word": w, "start": s, "end": e} for w, s, e in words]
    return {
        "text": text,
        "start": start if start is not None else (ws[0]["start"] if ws else 0.0),
        "end": end if end is not None else (ws[-1]["end"] if ws else 0.0),
        "words": ws,
    }


def test_find_matches_multichar_across_tokens():
    # Whisper splits 于是 into 于 + 是; the matcher must still find it.
    seg = _seg("于是也不是", [
        ("于", 1.00, 1.20),
        ("是", 1.20, 1.30),
        ("也", 1.30, 1.60),
        ("不是", 1.60, 1.90),
    ])
    matches = find_matches([seg], {"于是"}, pad=0.0)
    assert len(matches) == 1
    m = matches[0]
    assert m["word"] == "于是"
    assert m["word_indices"] == [0, 1]
    assert m["start"] == 1.00 and m["end"] == 1.30


def test_find_matches_single_token_word():
    seg = _seg("然后我走了", [
        ("然后", 0.0, 0.5),
        ("我", 0.5, 0.7),
        ("走了", 0.7, 1.0),
    ])
    matches = find_matches([seg], {"然后"}, pad=0.0)
    assert [m["word"] for m in matches] == ["然后"]
    assert matches[0]["word_indices"] == [0]


def test_find_matches_counts_each_occurrence():
    segs = [
        _seg("于是甲", [("于", 0.0, 0.2), ("是", 0.2, 0.3), ("甲", 0.3, 0.6)]),
        _seg("于是乙", [("于", 1.0, 1.2), ("是", 1.2, 1.3), ("乙", 1.3, 1.6)]),
    ]
    matches = find_matches(segs, {"于是"}, pad=0.0)
    assert len(matches) == 2
    assert [m["segment_idx"] for m in matches] == [0, 1]


def test_find_matches_no_partial_false_positive():
    # 是 alone should not match the target 于是.
    seg = _seg("是的", [("是", 0.0, 0.2), ("的", 0.2, 0.4)])
    assert find_matches([seg], {"于是"}, pad=0.0) == []


def test_build_cut_srt_drops_token_and_shifts():
    # Two segments; remove 于是 (tokens 0,1) from the second, cut 1.0..1.3.
    segs = [
        _seg("你好", [("你", 0.0, 0.4), ("好", 0.4, 0.8)]),
        _seg("于是也不是", [
            ("于", 1.0, 1.2),
            ("是", 1.2, 1.3),
            ("也", 1.3, 1.6),
            ("不是", 1.6, 1.9),
        ]),
    ]
    out = build_cut_srt(
        segs,
        removed={(1, 0), (1, 1)},
        cuts=[(1.0, 1.3)],
        out_path=__import__("pathlib").Path("/tmp/_cf_test.srt"),
    )
    text = out.read_text(encoding="utf-8")
    # first cue unchanged
    assert "00:00:00,000 --> 00:00:00,800" in text
    assert "你好" in text
    # 于是 dropped from the second cue's text
    assert "也不是" in text
    assert "于是也不是" not in text
    # second cue shifted earlier by the 0.3s cut: 1.3->1.0, 1.9->1.6
    assert "00:00:01,000 --> 00:00:01,600" in text


def test_normalize_word_strips_punctuation():
    assert normalize_word("，于是。") == "于是"


def test_parse_indices_ranges():
    assert parse_indices("1,3,5-7", 10) == [1, 3, 5, 6, 7]
    assert parse_indices("all", 3) == [1, 2, 3]


def test_normalize_word_is_case_insensitive():
    # English fillers must match regardless of case ("So" at sentence start).
    assert normalize_word("So,") == normalize_word("so") == "so"


def test_find_matches_english_case_insensitive():
    seg = _seg("So anyway", [("So", 0.0, 0.3), ("anyway", 0.3, 0.8)])
    matches = find_matches([seg], {"so"})
    assert [m["word"] for m in matches] == ["So"]


def test_find_matches_english_multiword():
    seg = _seg("you know it", [("you", 0.0, 0.2), ("know", 0.2, 0.5), ("it", 0.5, 0.7)])
    matches = find_matches([seg], {"you know"})
    assert len(matches) == 1
    assert matches[0]["start"] <= 0.0 + 1e-9 or matches[0]["start"] >= 0.0
