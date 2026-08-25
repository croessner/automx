"""Single document-rendering service shared by ASGI and operator commands."""

from __future__ import annotations

from automx.configuration import ConfigurationRepository
from automx.renderers.autoconfig import render_autoconfig
from automx.renderers.autodiscover import (
    AutodiscoverSchema,
    render_mobile,
    render_outlook,
)
from automx.renderers.pacc import render_pacc
from automx.static_documents import load_static_xml


def autoconfig_document(
    repository: ConfigurationRepository,
    email_address: str,
) -> bytes:
    """Resolve an account and return its exact Autoconfig document bytes."""

    profile = repository.resolve(email_address)
    return load_static_xml(profile, "autoconfig") or render_autoconfig(profile)


def autodiscover_document(
    repository: ConfigurationRepository,
    email_address: str,
    schema: AutodiscoverSchema,
) -> bytes:
    """Resolve an account and return its exact requested Autodiscover schema."""

    profile = repository.resolve(email_address)
    static_body = load_static_xml(profile, "autodiscover")
    if static_body is not None:
        return static_body
    if schema is AutodiscoverSchema.OUTLOOK:
        return render_outlook(profile)
    return render_mobile(profile)


def pacc_document(repository: ConfigurationRepository, domain: str) -> bytes:
    """Return exact PACC bytes for a configured domain."""

    return render_pacc(repository.resolve(f"pacc@{domain}"))
