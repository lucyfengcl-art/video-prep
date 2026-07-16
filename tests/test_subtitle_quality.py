from video_prep.subtitle_quality import sanitize_segments


def test_drops_repeated_tail_segments_beyond_clip_03_duration():
    segments = [
        {"start": 69.891, "end": 73.509, "text": "真实字幕"},
        {"start": 73.509, "end": 74.200, "text": "好意思"},
        {"start": 74.200, "end": 74.691, "text": "好意思"},
        {"start": 74.691, "end": 78.800, "text": "好意思"},
    ]

    clean, warnings = sanitize_segments(segments, duration=73.800)

    assert [segment["text"] for segment in clean] == ["真实字幕"]
    assert all(warning["action"] == "dropped" for warning in warnings)


def test_drops_long_clip_06_hallucination_at_media_end():
    segments = [
        {"start": 59.491, "end": 62.745, "text": "真实结尾"},
        {"start": 62.745, "end": 90.000, "text": "然后我们再次创作的视频"},
    ]

    clean, warnings = sanitize_segments(segments, duration=62.866667)

    assert [segment["text"] for segment in clean] == ["真实结尾"]
    assert warnings[-1]["reason"] == "hallucinated-tail-overrun"


def test_clamps_small_timestamp_rounding_overrun():
    clean, warnings = sanitize_segments(
        [{"start": 8.0, "end": 10.1, "text": "最后一句"}],
        duration=10.0,
    )

    assert clean[0]["end"] == 10.0
    assert warnings[0]["reason"] == "ends-after-media"
    assert warnings[0]["action"] == "clamped"


def test_flags_repetition_for_review_without_deleting_possible_speech():
    segments = [
        {"start": 1.0, "end": 1.5, "text": "对"},
        {"start": 1.5, "end": 2.0, "text": "对"},
        {"start": 2.0, "end": 2.5, "text": "对"},
    ]

    clean, warnings = sanitize_segments(segments, duration=5.0)

    assert len(clean) == 3
    assert any(warning["reason"] == "repeated-short-cue" for warning in warnings)
