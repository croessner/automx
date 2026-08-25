# ASGI and container deployment

automx 3.0 is ASGI-only. Run it with the packaged command:

```console
automx serve --config /etc/automx/automx.conf --host 127.0.0.1 --port 8000
```

Terminate public TLS at a maintained reverse proxy and forward only the
documented paths. Do not forward a client-supplied base URL into automx. Health
checks use `/health/live` and `/health/ready`; those routes intentionally expose
no configuration.

When running behind a proxy, configure trusted forwarded-header handling at the
process or ingress boundary. The packaged command disables proxy-header trust by
default. Do not expose Uvicorn directly to an untrusted network.

## Container

The root `Dockerfile` is multi-stage and runs as UID/GID 10001. Mount the
configuration read-only:

```console
docker compose up --build
```

The supplied Compose service binds only to `127.0.0.1:8000`, drops all Linux
capabilities, enables `no-new-privileges`, uses a read-only root filesystem, and
provides a bounded `/tmp` tmpfs. Adjust the host binding only when a trusted
reverse proxy or network policy protects the service.

Create and scan supply-chain artifacts with `make sbom` and `make scan`.
See [container scan details](security/container-scan.md).
