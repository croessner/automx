"""Single document-rendering service shared by ASGI and operator commands."""

from __future__ import annotations

from dataclasses import dataclass

from automx.configuration import ConfigurationRepository
from automx.mobileconfig_signing import (
    MobileconfigInspection,
    MobileconfigSigningError,
    inspect_mobileconfig,
)
from automx.renderers.autoconfig import render_autoconfig
from automx.renderers.autodiscover import (
    AutodiscoverSchema,
    render_mobile,
    render_outlook,
)
from automx.renderers.mobileconfig import MobileconfigRenderError, render_mobileconfig
from automx.renderers.pacc import render_pacc
from automx.static_documents import load_static_mobileconfig, load_static_xml


@dataclass(frozen=True, slots=True)
class RenderedMobileconfig:
    """Exact profile bytes and their verified CMS signature status."""

    body: bytes
    signature: MobileconfigInspection


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


def mobileconfig_document_result(
    repository: ConfigurationRepository,
    email_address: str,
    *,
    common_name: str | None = None,
) -> RenderedMobileconfig:
    """Resolve an account, optionally sign it, and return verified profile bytes."""

    profile = repository.resolve(email_address)
    body = load_static_mobileconfig(profile) or render_mobileconfig(
        profile,
        common_name=common_name,
    )
    inspected = inspect_mobileconfig(body)
    if not inspected.signed and repository.mobileconfig_signer is not None:
        try:
            body, inspected = repository.mobileconfig_signer.sign(inspected.content)
        except MobileconfigSigningError as exc:
            raise MobileconfigRenderError("mobileconfig signing failed") from exc
    return RenderedMobileconfig(body=body, signature=inspected)


def mobileconfig_document(
    repository: ConfigurationRepository,
    email_address: str,
    *,
    common_name: str | None = None,
) -> bytes:
    """Return exact plain or signed Apple profile bytes."""

    return mobileconfig_document_result(
        repository,
        email_address,
        common_name=common_name,
    ).body


def pacc_document(repository: ConfigurationRepository, domain: str) -> bytes:
    """Return exact PACC bytes for a configured domain."""

    return render_pacc(repository.resolve(f"pacc@{domain}"))
