"""Validated loading of administrator-provided compatibility documents."""

from __future__ import annotations

import plistlib

from lxml import etree

from automx.domain import AccountProfile, StaticDocument
from automx.mobileconfig_signing import MobileconfigSigningError, inspect_mobileconfig

MAX_STATIC_DOCUMENT_BYTES = 1_048_576


class StaticDocumentError(RuntimeError):
    """A configured static document is unsafe, malformed, or unavailable."""


def _selected(profile: AccountProfile, kind: str) -> StaticDocument | None:
    return next((document for document in profile.static_documents if document.kind == kind), None)


def _read(document: StaticDocument) -> bytes:
    try:
        with document.path.open("rb") as source:
            body = source.read(MAX_STATIC_DOCUMENT_BYTES + 1)
    except OSError as exc:
        raise StaticDocumentError("static document cannot be read") from exc
    if len(body) > MAX_STATIC_DOCUMENT_BYTES:
        raise StaticDocumentError("static document exceeds 1 MiB")
    return body


def load_static_xml(profile: AccountProfile, kind: str) -> bytes | None:
    """Return a safe configured XML document, if the selected backend has one."""

    document = _selected(profile, kind)
    if document is None:
        return None
    body = _read(document)
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise StaticDocumentError("static XML contains a DTD or entity declaration")
    try:
        root = etree.fromstring(
            body,
            parser=etree.XMLParser(
                resolve_entities=False,
                no_network=True,
                load_dtd=False,
                huge_tree=False,
            ),
        )
    except etree.XMLSyntaxError as exc:
        raise StaticDocumentError("static XML is malformed") from exc
    expected = "clientConfig" if kind == "autoconfig" else "Autodiscover"
    if etree.QName(root).localname != expected:
        raise StaticDocumentError(f"static {kind} document has the wrong root element")
    return body


def _contains_password_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold()
            if "password" in normalized and (
                normalized != "outgoingpasswordsameasincomingpassword" or child is not True
            ):
                return True
            if _contains_password_key(child):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_password_key(child) for child in value)
    return False


def load_static_mobileconfig(profile: AccountProfile) -> bytes | None:
    """Return a valid static Apple profile only when it contains no password keys."""

    document = _selected(profile, "mobileconfig")
    if document is None:
        return None
    body = _read(document)
    try:
        inspection = inspect_mobileconfig(body)
        parsed: object = plistlib.loads(inspection.content)
    except (MobileconfigSigningError, plistlib.InvalidFileException) as exc:
        raise StaticDocumentError("static mobileconfig is malformed or has an invalid signature") from exc
    if not isinstance(parsed, dict) or parsed.get("PayloadType") != "Configuration":
        raise StaticDocumentError("static mobileconfig is not a configuration profile")
    if _contains_password_key(parsed):
        raise StaticDocumentError("static mobileconfig must not contain password keys")
    return body
