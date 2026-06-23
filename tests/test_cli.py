from video_prep.cli import natural_key


def test_natural_key_orders_numbers_numerically():
    names = ["10.MOV", "1.MOV", "2.mp4", "13.MOV", "9.MOV", "11.MOV"]
    assert sorted(names, key=natural_key) == [
        "1.MOV",
        "2.mp4",
        "9.MOV",
        "10.MOV",
        "11.MOV",
        "13.MOV",
    ]


def test_natural_key_zero_padded_still_works():
    names = ["03-intro.mp4", "01-intro.mp4", "02-intro.mp4"]
    assert sorted(names, key=natural_key) == [
        "01-intro.mp4",
        "02-intro.mp4",
        "03-intro.mp4",
    ]


def test_natural_key_is_case_insensitive_for_text():
    # Letters compare case-insensitively so "B.mov" doesn't sort before "a.mov".
    assert sorted(["B.mov", "a.mov"], key=natural_key) == ["a.mov", "B.mov"]
