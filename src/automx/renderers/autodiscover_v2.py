"""Conservative, experimental Autodiscover v2 JSON profile."""

from __future__ import annotations

from enum import StrEnum

from automx.domain import AccountProfile, Protocol


class AutodiscoverV2Error(RuntimeError):
    """A v2 request cannot be answered from the explicit allowlist."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class AutodiscoverV2Protocol(StrEnum):
    EWS = "EWS"
    ACTIVESYNC = "ActiveSync"
    REST = "REST"
    GRAPH = "Graph"
    OAB = "OAB"
    ACTIONS = "Actions"


_DOMAIN_PROTOCOL = {
    AutodiscoverV2Protocol.EWS: Protocol.EWS,
    AutodiscoverV2Protocol.ACTIVESYNC: Protocol.ACTIVESYNC,
    AutodiscoverV2Protocol.REST: Protocol.REST,
    AutodiscoverV2Protocol.GRAPH: Protocol.GRAPH,
    AutodiscoverV2Protocol.OAB: Protocol.OAB,
    AutodiscoverV2Protocol.ACTIONS: Protocol.ACTIONS,
}


def parse_v2_protocol(value: str) -> AutodiscoverV2Protocol:
    normalized = value.casefold()
    for protocol in AutodiscoverV2Protocol:
        if protocol.value.casefold() == normalized:
            return protocol
    raise AutodiscoverV2Error(400, "unsupported protocol")


def render_autodiscover_v2(
    profile: AccountProfile, requested_protocol: str
) -> dict[str, str]:
    """Return only a configured URL; user-provided URLs are never consumed."""

    protocol = parse_v2_protocol(requested_protocol)
    domain_protocol = _DOMAIN_PROTOCOL[protocol]
    endpoint = next(
        (server for server in profile.servers if server.protocol is domain_protocol),
        None,
    )
    if endpoint is None or endpoint.url is None:
        raise AutodiscoverV2Error(404, "protocol is not configured")
    result = {"Protocol": protocol.value, "Url": endpoint.url}
    if endpoint.server_location is not None:
        result["ServerLocation"] = endpoint.server_location
    return result
