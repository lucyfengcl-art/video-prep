import json
from pathlib import Path

from video_prep.pipeline import _publish_subtitle_warnings


def test_warning_report_uses_processed_video_timeline(tmp_path: Path):
    work = tmp_path / "work"
    out = tmp_path / "out"
    work.mkdir()
    out.mkdir()
    (work / "01.subtitle-warnings.json").write_text(
        json.dumps({
            "media_duration": 20.0,
            "warnings": [{
                "start": 10.0, "end": 12.0, "text": "x",
                "reason": "review", "action": "review",
            }],
        }),
        encoding="utf-8",
    )

    _publish_subtitle_warnings(work, out, "01", speed=2.0)

    report = json.loads((out / "01.subtitle-warnings.json").read_text())
    assert report["timeline"] == "processed-video"
    assert report["media_duration"] == 10.0
    assert report["warnings"][0]["start"] == 5.0
    assert report["warnings"][0]["end"] == 6.0
