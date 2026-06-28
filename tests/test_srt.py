from pathlib import Path

import pytest

from video_prep.srt import (
    concat_srts,
    rescale_srt,
    rescale_srt_text,
    rescale_timestamp,
    split_cue,
    strip_leading_words,
    strip_leading_words_in_file,
)


def test_split_cue_short_text_unchanged():
    # A cue at or under max_chars passes through as a single piece.
    assert split_cue(0, 1000, "你好世界", 20) == [(0, 1000, "你好世界")]


def test_split_cue_splits_at_punctuation_without_losing_text():
    text = "上个视频发完之后,好多人都来问我那个小工具,我后来整理成了一个skill"
    cues = split_cue(0, 10000, text, 20)
    assert len(cues) > 1
    # No on-screen line exceeds the cap.
    assert all(len(t) <= 20 for _, _, t in cues)
    # Nothing is dropped (ignoring spaces collapsed at break points).
    assert "".join(t for _, _, t in cues).replace(" ", "") == text.replace(" ", "")


def test_split_cue_timeline_is_contiguous_and_covers_window():
    text = "第一句话在这里结束,第二句话也到这里,第三句话同样结束了哦"
    cues = split_cue(2000, 8000, text, 12)
    assert cues[0][0] == 2000
    assert cues[-1][1] == 8000
    # Pieces tile the window with no gaps or overlaps.
    for (_, end_a, _), (start_b, _, _) in zip(cues, cues[1:]):
        assert end_a == start_b


def test_split_cue_disabled_with_zero():
    long_text = "这是一句没有标点的很长很长很长很长很长很长很长的话"
    assert split_cue(0, 1000, long_text, 0) == [(0, 1000, long_text)]


def test_rescale_timestamp_basic():
    assert rescale_timestamp("00:00:06,000", 1.2) == "00:00:05,000"


def test_rescale_timestamp_with_milliseconds():
    # 12.000s / 1.2 = 10.000s
    assert rescale_timestamp("00:00:12,000", 1.2) == "00:00:10,000"
    # 1.500s / 1.5 = 1.000s
    assert rescale_timestamp("00:00:01,500", 1.5) == "00:00:01,000"


def test_rescale_timestamp_across_minute_hour():
    # 1h 12m 0s = 4_320_000ms; /1.2 = 3_600_000ms = 1h
    assert rescale_timestamp("01:12:00,000", 1.2) == "01:00:00,000"


def test_rescale_timestamp_rejects_bad_input():
    with pytest.raises(ValueError):
        rescale_timestamp("not a timestamp", 1.2)


def test_rescale_srt_text_only_touches_timestamps():
    srt = (
        "1\n"
        "00:00:00,000 --> 00:00:06,000\n"
        "你好,这是第一段字幕\n"
        "\n"
        "2\n"
        "00:00:06,000 --> 00:00:12,000\n"
        "这是第二段\n"
    )
    out = rescale_srt_text(srt, 1.2)
    assert "00:00:05,000" in out
    assert "00:00:10,000" in out
    assert "你好,这是第一段字幕" in out  # Chinese content preserved
    assert "这是第二段" in out
    # original 6.000 timestamp should be replaced everywhere
    assert "00:00:06,000" not in out


def test_rescale_srt_writes_file(tmp_path: Path):
    src = tmp_path / "in.srt"
    src.write_text("1\n00:00:00,000 --> 00:00:12,000\nhi\n", encoding="utf-8")
    out = tmp_path / "out.srt"
    rescale_srt(src, 1.2, out_path=out)
    assert "00:00:10,000" in out.read_text(encoding="utf-8")
    # source untouched when out_path given
    assert "00:00:12,000" in src.read_text(encoding="utf-8")


def test_rescale_srt_factor_must_be_positive():
    with pytest.raises(ValueError):
        rescale_srt_text("00:00:01,000 --> 00:00:02,000", 0)


def test_strip_leading_words_removes_chinese_filler():
    srt = (
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "然后你的朋友还会来问你\n"
        "\n"
        "2\n"
        "00:00:02,000 --> 00:00:04,000\n"
        "然后，我突然间意识到了一个事儿\n"
        "\n"
        "3\n"
        "00:00:04,000 --> 00:00:06,000\n"
        "这是一个先A然后B的句子\n"  # mid-sentence 然后 stays
    )
    out, n = strip_leading_words(srt, ["然后"])
    assert n == 2
    assert "你的朋友还会来问你" in out
    assert "我突然间意识到了一个事儿" in out
    assert "先A然后B" in out  # mid-sentence preserved
    # leading 然后 + comma stripped
    assert "然后你的朋友" not in out
    assert "然后，我突然" not in out


def test_strip_leading_words_handles_multiple_targets():
    srt = (
        "1\n00:00:00,000 --> 00:00:01,000\n就是这个意思\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\n然后他就走了\n"
    )
    out, n = strip_leading_words(srt, ["然后", "就是"])
    assert n == 2
    assert "这个意思" in out
    assert "他就走了" in out


def test_strip_leading_words_preserves_timestamps_and_indices():
    srt = "5\n00:00:10,000 --> 00:00:12,000\n然后开始\n"
    out, n = strip_leading_words(srt, ["然后"])
    assert n == 1
    assert out.startswith("5\n")
    assert "00:00:10,000 --> 00:00:12,000" in out


def test_strip_leading_words_in_file_writes_back(tmp_path: Path):
    p = tmp_path / "in.srt"
    p.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n然后开始\n", encoding="utf-8"
    )
    _, n = strip_leading_words_in_file(p, ["然后"])
    assert n == 1
    assert "然后" not in p.read_text(encoding="utf-8")


def test_concat_srts_offsets_and_renumbers(tmp_path: Path):
    a = tmp_path / "a.srt"
    a.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n第一段甲\n\n"
        "2\n00:00:02,000 --> 00:00:04,000\n第一段乙\n",
        encoding="utf-8",
    )
    b = tmp_path / "b.srt"
    b.write_text(
        "1\n00:00:00,000 --> 00:00:03,000\n第二段甲\n",
        encoding="utf-8",
    )
    out = tmp_path / "merged.srt"
    # clip a is 5s long, so clip b starts at t=5
    concat_srts([a, b], [0.0, 5.0], out)
    text = out.read_text(encoding="utf-8")

    # renumbered sequentially across both files
    assert "1\n00:00:00,000 --> 00:00:02,000" in text
    assert "2\n00:00:02,000 --> 00:00:04,000" in text
    # clip b shifted by +5s
    assert "3\n00:00:05,000 --> 00:00:08,000" in text
    assert "第二段甲" in text
    # no leftover original index for clip b
    assert text.count("第二段甲") == 1


def test_concat_srts_length_mismatch_raises(tmp_path: Path):
    a = tmp_path / "a.srt"
    a.write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    with pytest.raises(ValueError):
        concat_srts([a], [0.0, 1.0], tmp_path / "out.srt")


def test_split_cue_english_wraps_on_word_boundaries():
    text = "so basically I think this is a really interesting point to make"
    cues = split_cue(0, 4000, text, 20, space_delimited=True)
    lines = [t for _, _, t in cues]
    assert len(lines) > 1
    assert all(len(t) <= 20 for t in lines)
    # No word is split across lines: rejoining yields the original word sequence.
    assert " ".join(lines).split() == text.split()


def test_split_cue_chinese_wraps_by_character():
    text = "这是一句没有标点符号的很长很长很长很长很长的中文句子需要按字符换行"
    cues = split_cue(0, 5000, text, 12, space_delimited=False)
    lines = [t for _, _, t in cues]
    assert all(len(t) <= 12 for t in lines)
    assert "".join(lines) == text


def test_fillers_defaults():
    from video_prep.fillers import default_fillers
    assert "um" in default_fillers("en")
    assert "就是" in default_fillers("zh")
    assert default_fillers("xx") == []
    assert default_fillers(None) == []
