from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_mojo_entrypoint_forwards_arguments_and_exit_status_to_python_cli() -> None:
    source = (ROOT / "src/automx_mojo/main.mojo").read_text(encoding="utf-8")

    assert "from std.python import Python, PythonObject" in source
    assert "from std.sys import argv, exit" in source
    assert 'Python.import_module("automx.mojo_entrypoint")' in source
    assert "range(1, len(mojo_args))" in source
    assert "bridge.run(args)" in source
    assert "sys.stdout.flush()" in source
    assert "sys.stderr.flush()" in source
    assert "exit(status)" in source


def test_mojo_image_has_separate_build_and_hardened_runtime_stages() -> None:
    dockerfile = (ROOT / "Dockerfile-mojo").read_text(encoding="utf-8")
    runtime = dockerfile.split(" AS runtime", maxsplit=1)[1]

    assert "ARG MOJO_VERSION=1.0.0" in dockerfile
    assert " AS python-builder" in dockerfile
    assert " AS mojo-builder" in dockerfile
    assert '"mojo==${MOJO_VERSION}"' in dockerfile
    assert "mojo build" in dockerfile
    assert "src/automx_mojo/main.mojo" in dockerfile
    assert "COPY --from=python-builder /opt/automx /opt/automx" in runtime
    assert (
        "COPY --from=mojo-builder --chmod=0555 /out/automx /usr/local/bin/automx"
        in runtime
    )
    assert "libKGENCompilerRTShared.so" in runtime
    assert "libMSupportGlobals.so" in runtime
    assert "libAsyncRTRuntimeGlobals.so" in runtime
    assert "USER automx:automx" in runtime
    assert 'ENTRYPOINT ["/usr/local/bin/automx"]' in runtime
    assert "pip install" not in runtime
    assert "mojo build" not in runtime
    assert "install --yes --no-install-recommends gcc" not in runtime
    assert "COPY --from=mojo-builder /opt/mojo /opt/mojo" not in runtime


def test_makefile_exposes_a_distinct_mojo_image_build() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "docker-build-mojo:" in makefile
    assert "--file Dockerfile-mojo" in makefile
    assert "--build-arg VERSION=3.0.0-beta.1" in makefile.split(
        "docker-build-mojo:", maxsplit=1
    )[1]
