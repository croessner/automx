#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
compose_file="$script_dir/compose.yaml"
project_name="${COMPOSE_PROJECT_NAME:-automx-e2e}"

cleanup() {
    docker compose --project-name "$project_name" --file "$compose_file" down --volumes --remove-orphans
}
trap cleanup EXIT INT TERM

docker compose --project-name "$project_name" --file "$compose_file" up \
    --build --detach automx

automx_container_id=$(
    docker compose --project-name "$project_name" --file "$compose_file" \
        ps -q automx
)
if [ -z "$automx_container_id" ]; then
    echo "could not determine the automx container ID" >&2
    exit 1
fi
health_attempt=0
while :; do
    health_status=$(
        docker inspect --format '{{.State.Health.Status}}' \
            "$automx_container_id" 2>/dev/null || echo missing
    )
    if [ "$health_status" = "healthy" ]; then
        break
    fi
    if [ "$health_status" = "unhealthy" ]; then
        docker compose --project-name "$project_name" --file "$compose_file" logs automx >&2
        echo "automx became unhealthy" >&2
        exit 1
    fi
    health_attempt=$((health_attempt + 1))
    if [ "$health_attempt" -ge 30 ]; then
        docker compose --project-name "$project_name" --file "$compose_file" logs automx >&2
        echo "automx did not become healthy within 30 seconds" >&2
        exit 1
    fi
    sleep 1
done

runtime_uid=$(docker compose --project-name "$project_name" --file "$compose_file" exec -T automx id -u)
if [ "$runtime_uid" = "0" ]; then
    echo "runtime unexpectedly runs as root" >&2
    exit 1
fi
echo "non-root runtime uid: $runtime_uid"

runtime_version=$(docker compose --project-name "$project_name" --file "$compose_file" \
    exec -T automx automx --version)
if [ "$runtime_version" != "automx 3.0.0-beta.3" ]; then
    echo "unexpected runtime version: $runtime_version" >&2
    exit 1
fi
echo "runtime version: $runtime_version"

if docker compose --project-name "$project_name" --file "$compose_file" exec -T automx touch /rootfs-proof; then
    echo "runtime root filesystem is writable" >&2
    exit 1
fi
echo "read-only filesystem proof passed"

docker compose --project-name "$project_name" --file "$compose_file" run --rm probe
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    openapi check --config /etc/automx/automx.conf
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    render autoconfig --config /etc/automx/automx.conf \
    --email probe@example.test >/dev/null
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    render autodiscover --config /etc/automx/automx.conf \
    --email probe@example.test --schema outlook >/dev/null
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    render autodiscover --config /etc/automx/automx.conf \
    --email probe@example.test --schema mobilesync >/dev/null
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    render mobileconfig --config /etc/automx/automx.conf \
    --email probe@example.test --signature-status >/dev/null
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    render pacc --config /etc/automx/automx.conf --domain example.test >/dev/null
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    dns records --config /etc/automx/automx.conf --domain example.test \
    --service-host automx.example.test --format json

dns_container_id=$(docker compose --project-name "$project_name" --file "$compose_file" ps -q dns)
dns_address=$(docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
    "$dns_container_id")
if [ -z "$dns_address" ]; then
    echo "could not determine the synthetic DNS server address" >&2
    exit 1
fi
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    dns check --config /etc/automx/automx.conf --service-host automx.example.net \
    --nameserver "$dns_address" --port 1053 --format json
