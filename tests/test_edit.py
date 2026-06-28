from video_prep.edit import _build_parser


def test_jobs_defaults_to_one():
    args = _build_parser().parse_args(["./raw"])
    assert args.jobs == 1


def test_jobs_flag_parses():
    assert _build_parser().parse_args(["./raw", "-j", "3"]).jobs == 3
    assert _build_parser().parse_args(["./raw", "--jobs", "4"]).jobs == 4


def test_max_chars_default_is_auto():
    # -1 means "pick a cap by language" (20 for Chinese, 42 for spaced langs).
    assert _build_parser().parse_args(["./raw"]).max_chars == -1
