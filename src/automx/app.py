"""FastAPI application factory for the pure-ASGI automx service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from lxml import etree
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from automx import __version__
from automx.configuration import ConfigurationError, ConfigurationRepository
from automx.renderers.autoconfig import AutoconfigRenderError, render_autoconfig
from automx.renderers.autodiscover import (
    MOBILE_RESPONSE_NAMESPACE,
    OUTLOOK_RESPONSE_NAMESPACE,
    AutodiscoverRenderError,
    AutodiscoverRequestError,
    AutodiscoverSchema,
    parse_autodiscover_request,
    render_autodiscover_error,
    render_mobile,
    render_outlook,
)
from automx.renderers.autodiscover_v2 import AutodiscoverV2Error, render_autodiscover_v2
from automx.renderers.mobileconfig import MobileconfigRenderError, render_mobileconfig
from automx.renderers.mobileconfig_form import (
    render_mobileconfig_form,
    render_mobileconfig_script,
    render_mobileconfig_styles,
)
from automx.renderers.pacc import PaccRenderError, render_pacc
from automx.requests import RequestContractError, parse_form_request, parse_xml_request
from automx.settings import AppSettings
from automx.static_documents import (
    StaticDocumentError,
    load_static_mobileconfig,
    load_static_xml,
)

_ACCESS_LOG = logging.getLogger("automx.access")


class SafeAccessLogMiddleware:
    """Log only method, route path and status; never query, headers or body."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            route_path = getattr(route, "path", None)
            if not isinstance(route_path, str):
                route_path = "-"
            _ACCESS_LOG.info(
                "%s %s %d",
                scope.get("method", ""),
                route_path,
                status_code,
            )


def _request_domain(
    request: Request,
    configured_domains: tuple[str, ...],
    *,
    prefixes: tuple[str, ...],
) -> str | None:
    """Select an explicit configured domain from the HTTP authority."""

    explicit_domains = tuple(domain for domain in configured_domains if domain != "*")
    hostname = request.url.hostname
    if hostname is not None:
        normalized = hostname.rstrip(".").lower()
        candidates = [normalized]
        candidates.extend(
            normalized.removeprefix(prefix)
            for prefix in prefixes
            if normalized.startswith(prefix)
        )
        for candidate in candidates:
            if candidate in explicit_domains:
                return candidate
    if len(explicit_domains) == 1:
        return explicit_domains[0]
    return None


def create_app(
    *,
    config_path: str | Path | None = None,
    max_request_bytes: int | None = None,
    repository: ConfigurationRepository | None = None,
) -> FastAPI:
    """Create an isolated ASGI application with explicit dependencies."""

    if repository is None:
        if config_path is None:
            environment_settings = AppSettings.from_environment()
            settings = AppSettings(
                config_path=environment_settings.config_path,
                max_request_bytes=(
                    environment_settings.max_request_bytes
                    if max_request_bytes is None
                    else max_request_bytes
                ),
            )
        else:
            settings = AppSettings(
                config_path=Path(config_path),
                max_request_bytes=65_536 if max_request_bytes is None else max_request_bytes,
            )
        repository = ConfigurationRepository.from_path(settings.config_path)
    else:
        settings = AppSettings(
            config_path=repository.path,
            max_request_bytes=65_536 if max_request_bytes is None else max_request_bytes,
        )

    app = FastAPI(
        title="automx",
        version=__version__,
        description="Standards-oriented automatic account configuration service",
        openapi_tags=[
            {"name": "PACC", "description": "PACC-02 user-agent configuration."},
            {"name": "Autoconfig", "description": "Mail Autoconfig 1.2 XML."},
            {"name": "Autodiscover", "description": "Microsoft Autodiscover XML."},
            {
                "name": "Autodiscover v2",
                "description": "Experimental, configuration-gated Autodiscover v2 subset.",
            },
            {"name": "Mobileconfig", "description": "Password-free Apple Mail profiles."},
        ],
    )
    app.add_middleware(SafeAccessLogMiddleware)
    app.state.repository = repository
    app.state.settings = settings

    @app.exception_handler(RequestContractError)
    async def request_contract_error(
        _request: Request, exc: RequestContractError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "message": "request validation failed"},
        )

    @app.exception_handler(ConfigurationError)
    async def configuration_error(_request: Request, _exc: ConfigurationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "message": "account configuration unavailable"},
        )

    @app.exception_handler(AutoconfigRenderError)
    async def autoconfig_render_error(
        _request: Request, _exc: AutoconfigRenderError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_configuration", "message": "renderer contract failed"},
        )

    @app.exception_handler(PaccRenderError)
    async def pacc_render_error(_request: Request, _exc: PaccRenderError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_configuration", "message": "PACC contract failed"},
        )

    @app.exception_handler(MobileconfigRenderError)
    async def mobileconfig_render_error(
        _request: Request, _exc: MobileconfigRenderError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "unsupported_configuration",
                "message": "Apple Mail profile cannot represent this account configuration",
            },
        )

    @app.exception_handler(StaticDocumentError)
    async def static_document_error(
        _request: Request, _exc: StaticDocumentError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": "invalid_static_document",
                "message": "configured compatibility document is unavailable",
            },
        )

    @app.get("/health/live", include_in_schema=False)
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    async def health_ready() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/", include_in_schema=False)
    async def index() -> RedirectResponse:
        return RedirectResponse(url="/mobileconfig")

    @app.get(
        "/mobileconfig",
        tags=["Mobileconfig"],
        summary="Show the password-free Apple Mail configuration form",
        operation_id="get_mobileconfig_form",
        response_class=HTMLResponse,
    )
    async def mobileconfig_form() -> HTMLResponse:
        return HTMLResponse(
            content=render_mobileconfig_form(),
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'self'; script-src 'self'; "
                    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
                ),
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/mobileconfig.css", include_in_schema=False)
    async def mobileconfig_styles() -> Response:
        return Response(
            content=render_mobileconfig_styles(),
            media_type="text/css",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/mobileconfig.js", include_in_schema=False)
    async def mobileconfig_script() -> Response:
        return Response(
            content=render_mobileconfig_script(),
            media_type="text/javascript",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get(
        "/.well-known/user-agent-configuration.json",
        tags=["PACC"],
        summary="Get the PACC-02 configuration document",
        operation_id="get_pacc_configuration",
    )
    async def pacc(request: Request) -> Response:
        domain = _request_domain(
            request,
            repository.domains,
            prefixes=("ua-auto-config.",),
        )
        if domain is None:
            raise RequestContractError(404, "not_found", "not found")
        body = render_pacc(repository.resolve(f"pacc@{domain}"))
        return Response(content=body, media_type="application/json")

    @app.get(
        "/mail/config-v1.1.xml",
        tags=["Autoconfig"],
        summary="Get Mail Autoconfig 1.2 through the traditional path",
        operation_id="get_autoconfig_traditional",
    )
    @app.get(
        "/.well-known/autoconfig/mail/config-v1.1.xml",
        tags=["Autoconfig"],
        summary="Get Mail Autoconfig 1.2 through the well-known path",
        operation_id="get_autoconfig_well_known",
    )
    async def autoconfig(
        request: Request,
        email_address: Annotated[str | None, Query(alias="emailaddress")] = None,
    ) -> Response:
        selected_address = email_address
        if selected_address is None:
            synthetic_domain = _request_domain(
                request,
                repository.domains,
                prefixes=("autoconfig.",),
            )
            if synthetic_domain is None:
                raise RequestContractError(
                    400,
                    "email_required",
                    "emailaddress is required for wildcard configurations",
                )
            selected_address = f"autoconfig@{synthetic_domain}"
        profile = repository.resolve(selected_address)
        body = load_static_xml(profile, "autoconfig") or render_autoconfig(profile)
        return Response(content=body, media_type="text/xml")

    @app.post(
        "/autodiscover/autodiscover.xml",
        tags=["Autodiscover"],
        summary="Resolve an Outlook or MobileSync Autodiscover request",
        operation_id="post_autodiscover_xml",
    )
    async def autodiscover(request: Request) -> Response:
        try:
            root: etree._Element = await parse_xml_request(
                request, max_bytes=settings.max_request_bytes
            )
        except RequestContractError as exc:
            if exc.status_code != 400:
                raise
            return Response(
                content=render_autodiscover_error(600, "Invalid Request"),
                media_type="text/xml",
            )
        try:
            autodiscover_request = parse_autodiscover_request(root)
        except AutodiscoverRequestError as exc:
            return Response(
                content=render_autodiscover_error(exc.error_code, exc.message),
                media_type="text/xml",
            )
        response_namespace = (
            OUTLOOK_RESPONSE_NAMESPACE
            if autodiscover_request.schema is AutodiscoverSchema.OUTLOOK
            else MOBILE_RESPONSE_NAMESPACE
        )
        try:
            profile = repository.resolve(autodiscover_request.email_address)
        except ConfigurationError:
            return Response(
                content=render_autodiscover_error(
                    500,
                    "Email Address Not Found",
                    response_namespace=response_namespace,
                ),
                media_type="text/xml",
            )
        static_body = load_static_xml(profile, "autodiscover")
        if static_body is not None:
            return Response(content=static_body, media_type="text/xml")
        try:
            body = (
                render_outlook(profile)
                if autodiscover_request.schema is AutodiscoverSchema.OUTLOOK
                else render_mobile(profile)
            )
        except AutodiscoverRenderError:
            return Response(
                content=render_autodiscover_error(
                    602,
                    "Configuration Error",
                    response_namespace=response_namespace,
                ),
                media_type="text/xml",
            )
        return Response(content=body, media_type="text/xml")

    def v2_response(email_address: str, protocol: str) -> JSONResponse:
        if not repository.autodiscover_v2_enabled:
            raise RequestContractError(404, "not_found", "not found")
        profile = repository.resolve(email_address)
        try:
            result = render_autodiscover_v2(profile, protocol)
        except AutodiscoverV2Error as exc:
            raise RequestContractError(exc.status_code, "autodiscover_v2", exc.message) from exc
        return JSONResponse(content=result)

    @app.get(
        "/autodiscover/autodiscover.json/v1.0/{email_address}",
        tags=["Autodiscover v2"],
        summary="Resolve an experimental Autodiscover v2 path request",
        operation_id="get_autodiscover_v2_path",
        openapi_extra={"x-automx-status": "experimental"},
    )
    async def autodiscover_v2_path(
        request: Request,
        email_address: str,
        protocol: Annotated[str, Query(alias="Protocol")],
    ) -> JSONResponse:
        if set(request.query_params) != {"Protocol"}:
            raise RequestContractError(400, "invalid_query", "unexpected query parameter")
        return v2_response(email_address, protocol)

    @app.get(
        "/autodiscover/autodiscover.json",
        tags=["Autodiscover v2"],
        summary="Resolve an experimental Autodiscover v2 query request",
        operation_id="get_autodiscover_v2_query",
        openapi_extra={"x-automx-status": "experimental"},
    )
    async def autodiscover_v2_query(
        request: Request,
        email_address: Annotated[str, Query(alias="Email")],
        protocol: Annotated[str, Query(alias="Protocol")],
    ) -> JSONResponse:
        if set(request.query_params) != {"Email", "Protocol"}:
            raise RequestContractError(400, "invalid_query", "unexpected query parameter")
        return v2_response(email_address, protocol)

    @app.post(
        "/mobileconfig",
        tags=["Mobileconfig"],
        summary="Create a password-free Apple Mail configuration profile",
        operation_id="post_mobileconfig",
    )
    async def mobileconfig(request: Request) -> Response:
        form = await parse_form_request(request, max_bytes=settings.max_request_bytes)
        if set(form) - {"_mobileconfig", "cn", "emailaddress", "password"}:
            raise RequestContractError(400, "invalid_form", "unexpected form field")
        if any(len(values) != 1 for values in form.values()):
            raise RequestContractError(400, "invalid_form", "form fields must be singular")
        email_values = form.get("emailaddress", ())
        if not email_values or not email_values[0]:
            raise RequestContractError(400, "email_required", "emailaddress is required")
        password_values = form.get("password", ())
        if password_values and password_values[0]:
            raise RequestContractError(
                400,
                "password_not_accepted",
                "passwords are never embedded in configuration profiles",
            )
        common_name_values = form.get("cn", ())
        common_name = common_name_values[0] if common_name_values else None
        profile = repository.resolve(email_values[0])
        body = load_static_mobileconfig(profile) or render_mobileconfig(
            profile, common_name=common_name or None
        )
        return Response(
            content=body,
            media_type="application/x-apple-aspen-config",
            headers={"Content-Disposition": 'attachment; filename="automx.mobileconfig"'},
        )

    return app
