from automx.domain import AccountProfile
from automx.renderers.common import expand_username


def test_expand_username_supports_all_autoconfig_placeholders() -> None:
    profile = AccountProfile(
        provider="example.test",
        domains=("example.test",),
        email_address="user@example.test",
    )

    assert expand_username(profile, "%EMAILADDRESS%") == "user@example.test"
    assert expand_username(profile, "%EMAILLOCALPART%") == "user"
    assert expand_username(profile, "%EMAILDOMAIN%") == "example.test"
    assert (
        expand_username(profile, "%EMAILDOMAIN%\\%EMAILLOCALPART%")
        == "example.test\\user"
    )
