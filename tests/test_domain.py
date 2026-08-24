from __future__ import annotations

import pytest
from pydantic import ValidationError

from automx.domain import (
    AccountProfile,
    AuthenticationMethod,
    OAuthConfiguration,
    Protocol,
    Server,
    TLSMode,
)


def test_server_is_immutable_and_requires_exactly_one_location() -> None:
    server = Server(
        protocol=Protocol.IMAP,
        host="mail.example.test",
        port=993,
        tls=TLSMode.SSL,
        authentication=(AuthenticationMethod.PASSWORD_CLEARTEXT,),
    )

    with pytest.raises(ValidationError):
        server.host = "changed.example.test"

    with pytest.raises(ValidationError):
        Server(
            protocol=Protocol.IMAP,
            host="mail.example.test",
            url="https://mail.example.test/jmap",
            port=993,
            tls=TLSMode.SSL,
        )


@pytest.mark.parametrize(
    "issuer",
    [
        "http://identity.example.test",
        "https://identity.example.test/issuer?tenant=one",
        "https://identity.example.test/issuer#fragment",
        "https://user:password@identity.example.test/issuer",
    ],
)
def test_oauth_issuer_is_https_and_contains_no_ambiguous_components(issuer: str) -> None:
    with pytest.raises(ValidationError):
        OAuthConfiguration(issuer=issuer)


def test_profile_rejects_servers_for_another_domain() -> None:
    with pytest.raises(ValidationError):
        AccountProfile(
            provider="example.test",
            domains=("example.test",),
            email_address="user@other.example",
        )
