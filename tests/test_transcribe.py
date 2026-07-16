from video_prep.transcribe import _decode


class FakeWhisper:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, source, **kwargs):
        self.kwargs = kwargs
        return [], object()


def test_decode_enables_anti_hallucination_options(tmp_path):
    whisper = FakeWhisper()

    _decode(whisper, tmp_path / "clip.mp4", "zh", word_timestamps=True)

    assert whisper.kwargs == {
        "language": "zh",
        "word_timestamps": True,
        "vad_filter": True,
        "condition_on_previous_text": False,
        "hallucination_silence_threshold": 1.0,
    }
