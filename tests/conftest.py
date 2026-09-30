from __future__ import annotations

import pytest


@pytest.fixture(
    params=("/autodiscover/autodiscover.xml", "/Autodiscover/Autodiscover.xml"),
    ids=("canonical", "capitalized"),
)
def autodiscover_path(request: pytest.FixtureRequest) -> str:
    """Exercise the same XML contract on both supported HTTP paths."""
    return str(request.param)
