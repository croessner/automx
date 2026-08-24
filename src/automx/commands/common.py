"""Shared CLI configuration helpers."""

from __future__ import annotations

from pathlib import Path

from automx.configuration import ConfigurationError, ConfigurationRepository

DEFAULT_CONFIG = "/etc/automx/automx.conf"


def repository(path: str) -> ConfigurationRepository:
    return ConfigurationRepository.from_path(Path(path))


def selected_domain(repository: ConfigurationRepository, domain: str | None) -> str:
    result = domain or next((item for item in repository.domains if item != "*"), None)
    if result is None:
        raise ConfigurationError("--domain is required for wildcard configuration")
    return result
