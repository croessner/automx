#!/bin/sh
set -eu

image=${1:?Usage: scripts/mojo-container-smoke.sh <image>}
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
config_path="$project_root/contrib/e2e/automx.conf"
container_name="automx-mojo-smoke-$$"

cleanup() {
    docker rm --force "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

docker run --rm "$image" "--version"
docker run --rm "$image" "--help" >/dev/null
docker run --rm \
    --volume "$config_path:/tmp/automx.conf:ro" \
    "$image" "config" "validate" \
    --config /tmp/automx.conf --domain example.test

docker run --detach --name "$container_name" \
    --volume "$config_path:/tmp/automx.conf:ro" \
    "$image" "serve" --config /tmp/automx.conf \
    --host 0.0.0.0 --port 8000 >/dev/null

attempt=0
while [ "$attempt" -lt 30 ]; do
    health=$(docker inspect --format '{{.State.Health.Status}}' "$container_name")
    if [ "$health" = "healthy" ]; then
        echo "Mojo container CLI, config, and /health/ready serve gates passed"
        exit 0
    fi
    if [ "$health" = "unhealthy" ]; then
        docker logs "$container_name" >&2
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep 1
done

docker logs "$container_name" >&2
echo "Mojo container did not become ready" >&2
exit 1
