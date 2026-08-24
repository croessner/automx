"""Process settings for the ASGI application."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AppSettings(BaseModel):
    """Validated process-level settings, separate from account configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_path: Path
    max_request_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)

    @classmethod
    def from_environment(cls) -> AppSettings:
        """Load the narrow environment contract used by the CLI."""

        return cls(
            config_path=Path(os.environ.get("AUTOMX_CONFIG", "/etc/automx.conf")),
            max_request_bytes=int(os.environ.get("AUTOMX_MAX_REQUEST_BYTES", "65536")),
        )
