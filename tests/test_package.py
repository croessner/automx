from automx import __version__


def test_version_matches_modernized_baseline() -> None:
    assert __version__ == "1.2.0"
