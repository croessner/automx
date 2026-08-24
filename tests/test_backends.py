from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any

import pytest

from automx import backends
from automx.backends import BackendContext, BackendError, LDAPBackend, ScriptBackend, SQLBackend


def context() -> BackendContext:
    return BackendContext("user@example.test", "user", "example.test")


def test_backend_context_and_script_backend_contracts() -> None:
    assert context().expand("%s %u %d") == "user@example.test user example.test"
    backend = ScriptBackend()
    result = backend.resolve(
        {"script": "/usr/bin/printf 'first second'", "result_attrs": "one two"}, context()
    )
    assert result == {"one": "first", "two": "second"}

    with pytest.raises(BackendError, match="requires script"):
        backend.resolve({}, context())
    with pytest.raises(BackendError, match="between"):
        backend.resolve(
            {"script": "/usr/bin/true", "result_attrs": "one", "script_timeout": "99"},
            context(),
        )
    with pytest.raises(BackendError, match="status"):
        backend.resolve({"script": "/usr/bin/false", "result_attrs": "one"}, context())
    with pytest.raises(BackendError, match="does not match"):
        backend.resolve({"script": "/usr/bin/printf one", "result_attrs": "one two"}, context())


class FakeMappings:
    def __init__(self, row: dict[str, str] | None) -> None:
        self.row = row

    def mappings(self) -> FakeMappings:
        return self

    def first(self) -> dict[str, str] | None:
        return self.row


class FakeConnection:
    def __init__(self, row: dict[str, str] | None) -> None:
        self.row = row

    def execute(self, statement: object, parameters: dict[str, str]) -> FakeMappings:
        assert statement == "BOUND SELECT"
        assert parameters["emailaddress"] == "user@example.test"
        return FakeMappings(self.row)


class FakeEngine:
    def __init__(self, row: dict[str, str] | None) -> None:
        self.row = row

    def connect(self) -> nullcontext[FakeConnection]:
        return nullcontext(FakeConnection(self.row))


def test_sql_backend_uses_bound_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = SimpleNamespace(
        create_engine=lambda _host: FakeEngine({"mail": "resolved@example.test"}),
        text=lambda query: f"BOUND {query}",
    )
    monkeypatch.setattr(SQLBackend, "_load_sqlalchemy", staticmethod(lambda: fake_module))
    result = SQLBackend().resolve(
        {"host": "sqlite://", "query": "SELECT", "result_attrs": "mail missing"}, context()
    )
    assert result == {"mail": "resolved@example.test"}

    with pytest.raises(BackendError, match="unsafe"):
        SQLBackend().resolve(
            {"host": "sqlite://", "query": "SELECT '%s'", "result_attrs": "mail"}, context()
        )
    with pytest.raises(BackendError, match="requires host"):
        SQLBackend().resolve({}, context())


class FakeLDAPConnection:
    def __init__(self) -> None:
        self.unbound = False

    def set_option(self, _option: int, _value: int) -> None:
        pass

    def start_tls_s(self) -> None:
        pass

    def simple_bind_s(self, _dn: str, _password: str) -> None:
        pass

    def search_s(
        self, _base: str, _scope: int, search_filter: str, attributes: list[str]
    ) -> list[tuple[str, dict[str, list[bytes]]]]:
        assert search_filter == "(mail=user@example.test)"
        assert attributes == ["mail"]
        return [("dn", {"mail": [b"resolved@example.test"]})]

    def unbind_s(self) -> None:
        self.unbound = True


def test_ldap_backend_fails_closed_and_decodes_results(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeLDAPConnection()
    fake_ldap = SimpleNamespace(
        OPT_X_TLS_REQUIRE_CERT=1,
        OPT_X_TLS_DEMAND=2,
        OPT_NETWORK_TIMEOUT=3,
        SCOPE_BASE=4,
        SCOPE_ONELEVEL=5,
        SCOPE_SUBTREE=6,
        set_option=lambda *_args: None,
        initialize=lambda _host: connection,
    )
    monkeypatch.setattr(LDAPBackend, "_load_ldap", staticmethod(lambda: fake_ldap))
    original_import = backends.importlib.import_module

    def import_module(name: str) -> Any:
        if name == "ldap.filter":
            return SimpleNamespace(escape_filter_chars=lambda value: value)
        return original_import(name)

    monkeypatch.setattr(backends.importlib, "import_module", import_module)
    result = LDAPBackend().resolve(
        {
            "host": "ldaps://directory.example.test",
            "base": "dc=example,dc=test",
            "filter": "(mail=%s)",
            "result_attrs": "mail",
        },
        context(),
    )
    assert result == {"mail": "resolved@example.test"}
    assert connection.unbound

    with pytest.raises(BackendError, match="reqcert"):
        LDAPBackend().resolve({"reqcert": "never"}, context())
    with pytest.raises(BackendError, match="requires host"):
        LDAPBackend().resolve({}, context())
