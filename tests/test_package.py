from automx import __version__


def test_version_matches_modernized_baseline() -> None:
    assert __version__ == "3.0.0-beta.1"
