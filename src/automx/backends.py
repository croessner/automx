"""Optional dynamic configuration backends behind a small typed interface."""

from __future__ import annotations

import importlib
import shlex
import subprocess
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Protocol


class BackendError(RuntimeError):
    """A dynamic backend could not produce a safe result."""


@dataclass(frozen=True, slots=True)
class BackendContext:
    """Non-secret request values available to dynamic backends."""

    email_address: str
    local_part: str
    domain: str

    def expand(self, value: str) -> str:
        """Expand the documented, compatibility request macros."""

        return value.replace("%u", self.local_part).replace("%d", self.domain).replace(
            "%s", self.email_address
        )


class VariableBackend(Protocol):
    """Backend contract: return variables, never rendered protocol output."""

    def resolve(self, options: Mapping[str, str], context: BackendContext) -> Mapping[str, str]:
        """Resolve a set of variables for later static option expansion."""


def _split_list(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.replace(",", " ").split() if item)


class ScriptBackend:
    """Run an explicitly configured command without a shell or unbounded output."""

    def resolve(self, options: Mapping[str, str], context: BackendContext) -> Mapping[str, str]:
        command_text = options.get("script", "")
        attributes = _split_list(options.get("result_attrs", ""))
        if not command_text or not attributes:
            raise BackendError("script backend requires script and result_attrs")
        command = [context.expand(part) for part in shlex.split(command_text)]
        timeout = float(options.get("script_timeout", "3"))
        if not 0.1 <= timeout <= 30:
            raise BackendError("script_timeout must be between 0.1 and 30 seconds")

        try:
            completed = subprocess.run(  # noqa: S603 - argv is administrator configuration
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            raise BackendError("script backend execution failed") from exc
        if completed.returncode != 0:
            raise BackendError(f"script backend exited with status {completed.returncode}")
        if len(completed.stdout.encode("utf-8")) > 65_536:
            raise BackendError("script backend output exceeds 65536 bytes")

        separator = options.get("separator")
        values = completed.stdout.strip().split(separator) if separator else completed.stdout.split()
        if len(values) != len(attributes):
            raise BackendError("script backend result does not match result_attrs")
        return dict(zip(attributes, (value.strip() for value in values), strict=True))


class SQLBackend:
    """Resolve variables through SQLAlchemy 2 using bound parameters."""

    def resolve(self, options: Mapping[str, str], context: BackendContext) -> Mapping[str, str]:
        sqlalchemy = self._load_sqlalchemy()
        hosts = _split_list(options.get("host", ""))
        query = options.get("query", "")
        attributes = _split_list(options.get("result_attrs", ""))
        if not hosts or not query or not attributes:
            raise BackendError("sql backend requires host, query and result_attrs")
        if "%s" in query:
            raise BackendError("legacy SQL interpolation is unsafe; use :emailaddress")

        parameters = {
            "emailaddress": context.email_address,
            "localpart": context.local_part,
            "domain": context.domain,
        }
        last_error: Exception | None = None
        for host in hosts:
            try:
                engine = sqlalchemy.create_engine(host)
                with engine.connect() as connection:
                    row = connection.execute(sqlalchemy.text(query), parameters).mappings().first()
                if row is None:
                    continue
                return {name: str(row[name]) for name in attributes if name in row}
            except Exception as exc:  # SQLAlchemy drivers expose backend-specific exceptions.
                last_error = exc
        raise BackendError("sql backend returned no result") from last_error

    @staticmethod
    def _load_sqlalchemy() -> Any:
        try:
            return importlib.import_module("sqlalchemy")
        except ImportError as exc:
            raise BackendError("sql backend requires the 'sql' extra") from exc


class LDAPBackend:
    """LDAP backend with certificate validation enabled by default.

    The adapter is intentionally isolated so deployments not using LDAP do not
    import its native dependency. A complete connection is established only at
    request time by the selected backend.
    """

    def resolve(self, options: Mapping[str, str], context: BackendContext) -> Mapping[str, str]:
        ldap = self._load_ldap()
        if options.get("reqcert", "demand").lower() != "demand":
            raise BackendError("ldap reqcert must be 'demand'")
        hosts = _split_list(options.get("host", ""))
        base = options.get("base", "")
        filter_template = options.get("filter", "")
        attributes = _split_list(options.get("result_attrs", ""))
        if not hosts or not base or not filter_template or not attributes:
            raise BackendError("ldap backend requires host, base, filter and result_attrs")

        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
        escape = importlib.import_module("ldap.filter").escape_filter_chars
        search_filter = filter_template.replace("%s", escape(context.email_address))
        scope = {
            "base": ldap.SCOPE_BASE,
            "one": ldap.SCOPE_ONELEVEL,
            "onelevel": ldap.SCOPE_ONELEVEL,
            "sub": ldap.SCOPE_SUBTREE,
            "subtree": ldap.SCOPE_SUBTREE,
        }.get(options.get("scope", "sub").lower())
        if scope is None:
            raise BackendError("invalid LDAP scope")

        last_error: Exception | None = None
        for host in hosts:
            connection = None
            try:
                connection = ldap.initialize(host)
                connection.set_option(ldap.OPT_NETWORK_TIMEOUT, 5)
                if options.get("usetls", "yes").lower() in {"1", "true", "yes", "on"}:
                    connection.start_tls_s()
                connection.simple_bind_s(options.get("binddn", ""), options.get("bindpw", ""))
                results = connection.search_s(base, scope, search_filter, list(attributes))
                if not results:
                    continue
                values: dict[str, str] = {}
                for name in attributes:
                    raw = results[0][1].get(name)
                    if raw:
                        values[name] = raw[0].decode("utf-8", errors="strict")
                return values
            except Exception as exc:  # python-ldap exposes a broad native exception tree.
                last_error = exc
            finally:
                if connection is not None:
                    with suppress(Exception):
                        connection.unbind_s()
        raise BackendError("ldap backend returned no result") from last_error

    @staticmethod
    def _load_ldap() -> Any:
        try:
            return importlib.import_module("ldap")
        except ImportError as exc:
            raise BackendError("ldap backend requires the 'ldap' extra") from exc


DYNAMIC_BACKENDS: Mapping[str, VariableBackend] = {
    "script": ScriptBackend(),
    "sql": SQLBackend(),
    "ldap": LDAPBackend(),
}
