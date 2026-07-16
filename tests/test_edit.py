from pathlib import Path

import pytest

from video_prep.edit import (
    _build_parser,
    _cache_is_valid,
    _clip_numbers,
    _write_cache,
)


def test_jobs_defaults_to_one():
    args = _build_parser().parse_args(["./raw"])
    assert args.jobs == 1


def test_jobs_flag_parses():
    assert _build_parser().parse_args(["./raw", "-j", "3"]).jobs == 3
    assert _build_parser().parse_args(["./raw", "--jobs", "4"]).jobs == 4


def test_max_chars_default_is_auto():
    # -1 means "pick a cap by language" (20 for Chinese, 42 for spaced langs).
    assert _build_parser().parse_args(["./raw"]).max_chars == -1


def test_subtitle_style_flags_parse():
    args = _build_parser().parse_args([
        "./raw", "--subtitle-font-size", "11", "--subtitle-bold",
        "--subtitle-y", "0.75", "--box-clips", "2,4",
    ])
    assert args.subtitle_font_size == 11
    assert args.subtitle_bold is True
    assert args.subtitle_y == 0.75
    assert args.box_clips == {2, 4}


def test_clip_numbers():
    assert _clip_numbers("1, 3,3") == {1, 3}


def test_subtitle_y_rejects_out_of_range_value():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["./raw", "--subtitle-y", "1.2"])


def test_cache_invalidates_when_processing_options_change(tmp_path: Path):
    src = tmp_path / "raw.mp4"
    video = tmp_path / "01.processed.mp4"
    srt = tmp_path / "01.srt"
    metadata = tmp_path / "01.cache.json"
    for path in (src, video, srt):
        path.write_bytes(b"x")

    options = {"language": "zh", "model": "large-v3-turbo", "speed": 1.1}
    _write_cache(metadata, src, options)

    assert _cache_is_valid(video, srt, metadata, src, options)
    assert not _cache_is_valid(video, srt, metadata, src, {**options, "model": "large-v3"})
