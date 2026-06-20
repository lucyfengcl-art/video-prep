from pathlib import Path

import pytest

from video_prep.assemble import discover_segments


def _touch(p: Path) -> None:
    p.write_bytes(b"")


def test_discover_orders_by_nn_prefix(tmp_path: Path):
    _touch(tmp_path / "02-screen-slide1.mp4")
    _touch(tmp_path / "01-talk-intro.mov")
    _touch(tmp_path / "10-talk-end.mov")  # lexically < "02" but numerically last

    segs = discover_segments(tmp_path)

    assert [s.order for s in segs] == [1, 2, 10]
    assert [s.kind for s in segs] == ["talk", "screen", "talk"]


def test_discover_ignores_non_video_files(tmp_path: Path):
    _touch(tmp_path / "01-talk-intro.mov")
    _touch(tmp_path / "README.md")
    _touch(tmp_path / ".DS_Store")

    segs = discover_segments(tmp_path)

    assert len(segs) == 1
    assert segs[0].path.name == "01-talk-intro.mov"


def test_discover_rejects_bad_name(tmp_path: Path):
    _touch(tmp_path / "intro.mov")  # no NN-kind prefix
    with pytest.raises(ValueError):
        discover_segments(tmp_path)


def test_discover_rejects_unknown_kind(tmp_path: Path):
    _touch(tmp_path / "01-broll-x.mov")  # kind must be talk|screen
    with pytest.raises(ValueError):
        discover_segments(tmp_path)


def test_discover_kind_is_case_insensitive(tmp_path: Path):
    _touch(tmp_path / "01-TALK-intro.MOV")
    segs = discover_segments(tmp_path)
    assert segs[0].kind == "talk"
