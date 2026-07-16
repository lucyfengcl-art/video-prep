from pathlib import Path

from video_prep.burn import srt_to_ass


def test_srt_to_ass_supports_size_position_bold_and_selected_box(tmp_path: Path):
    srt = tmp_path / "in.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n第一段\n\n"
        "2\n00:00:05,000 --> 00:00:07,000\n第二段\n",
        encoding="utf-8",
    )

    ass = srt_to_ass(
        srt, tmp_path / "out.ass", width=1080, height=1920,
        font="Noto Sans CJK SC", font_size=11, subtitle_y=0.75,
        bold=True, box_ranges=[(4.0, 8.0)],
    ).read_text(encoding="utf-8")

    assert "PlayResX: 162" in ass
    assert "PlayResY: 288" in ass
    assert "Style: Default,Noto Sans CJK SC,11" in ass
    assert ",-1,0,0,0,100,100" in ass
    assert ",72,1" in ass
    assert ",Default,,0,0,0,,第一段" in ass
    assert ",Box,,0,0,0,,第二段" in ass


def test_srt_to_ass_global_background_boxes_every_cue(tmp_path: Path):
    srt = tmp_path / "in.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\n字幕\n",
        encoding="utf-8",
    )

    ass = srt_to_ass(
        srt, tmp_path / "out.ass", width=1920, height=1080,
        background=True,
    ).read_text(encoding="utf-8")

    assert ",Box,,0,0,0,,字幕" in ass
