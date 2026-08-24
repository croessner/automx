"""Bounded and non-networking request parsers."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import parse_qs

from fastapi import Request
from lxml import etree


class RequestContractError(RuntimeError):
    """A request violates an explicit HTTP or parser contract."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def media_type(request: Request) -> str:
    """Return a normalized media type without parameters."""

    return request.headers.get("content-type", "").partition(";")[0].strip().lower()


async def read_limited_body(
    request: Request,
    *,
    max_bytes: int,
    allowed_media_types: frozenset[str],
) -> bytes:
    """Read a request body while enforcing declared and actual byte limits."""

    content_type = media_type(request)
    if content_type not in allowed_media_types:
        raise RequestContractError(415, "unsupported_media_type", "unsupported media type")

    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            length = int(declared_length)
        except ValueError as exc:
            raise RequestContractError(400, "invalid_content_length", "invalid content length") from exc
        if length < 0:
            raise RequestContractError(400, "invalid_content_length", "invalid content length")
        if length > max_bytes:
            raise RequestContractError(413, "request_too_large", "request body is too large")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise RequestContractError(413, "request_too_large", "request body is too large")
    return bytes(body)


async def parse_xml_request(request: Request, *, max_bytes: int) -> etree._Element:
    """Parse bounded XML with DTD, entities and network access disabled."""

    body = await read_limited_body(
        request,
        max_bytes=max_bytes,
        allowed_media_types=frozenset({"application/xml", "text/xml"}),
    )
    upper_body = body.upper()
    if b"<!DOCTYPE" in upper_body or b"<!ENTITY" in upper_body:
        raise RequestContractError(400, "unsafe_xml", "DTD and entity declarations are forbidden")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
        recover=False,
        remove_comments=False,
    )
    try:
        return etree.fromstring(body, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise RequestContractError(400, "invalid_xml", "malformed XML request") from exc


async def parse_form_request(request: Request, *, max_bytes: int) -> Mapping[str, tuple[str, ...]]:
    """Parse a small UTF-8 form without storing uploads or temporary files."""

    body = await read_limited_body(
        request,
        max_bytes=max_bytes,
        allowed_media_types=frozenset({"application/x-www-form-urlencoded"}),
    )
    try:
        decoded = body.decode("utf-8", errors="strict")
        parsed = parse_qs(decoded, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
    except (UnicodeError, ValueError) as exc:
        raise RequestContractError(400, "invalid_form", "malformed form request") from exc
    return {key: tuple(values) for key, values in parsed.items()}
