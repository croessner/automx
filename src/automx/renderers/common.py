"""Shared renderer helpers for account-specific protocol output."""

from __future__ import annotations

from automx.domain import AccountProfile


def expand_username(profile: AccountProfile, template: str) -> str:
    """Resolve Mail Autoconfig username placeholders for non-Autoconfig output."""

    local_part, domain = profile.email_address.rsplit("@", 1)
    return (
        template.replace("%EMAILADDRESS%", profile.email_address)
        .replace("%EMAILLOCALPART%", local_part)
        .replace("%EMAILDOMAIN%", domain)
    )
