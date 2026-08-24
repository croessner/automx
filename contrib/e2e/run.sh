#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
compose_file="$script_dir/compose.yaml"
project_name="${COMPOSE_PROJECT_NAME:-automx-e2e}"

cleanup() {
    docker compose --project-name "$project_name" --file "$compose_file" down --volumes --remove-orphans
}
trap cleanup EXIT INT TERM

docker compose --project-name "$project_name" --file "$compose_file" up --build --detach automx

runtime_uid=$(docker compose --project-name "$project_name" --file "$compose_file" exec -T automx id -u)
if [ "$runtime_uid" = "0" ]; then
    echo "runtime unexpectedly runs as root" >&2
    exit 1
fi
echo "non-root runtime uid: $runtime_uid"

if docker compose --project-name "$project_name" --file "$compose_file" exec -T automx touch /rootfs-proof; then
    echo "runtime root filesystem is writable" >&2
    exit 1
fi
echo "read-only filesystem proof passed"

docker compose --project-name "$project_name" --file "$compose_file" run --rm probe
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    openapi check --config /etc/automx/automx.conf
docker compose --project-name "$project_name" --file "$compose_file" run --rm --no-deps automx \
    dns records --config /etc/automx/automx.conf --domain example.test \
    --service-host automx.example.test --format json
