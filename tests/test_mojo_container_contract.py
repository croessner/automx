from __future__ import annotations

import os
import subprocess
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
    assert "--target-triple=x86_64-unknown-linux-gnu" in dockerfile
    assert "--march=x86-64-v3" in dockerfile
    assert "scripts/check-no-avx512.sh /out/automx" in dockerfile
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
    assert "ARG PYTHON_BASE_DIGEST" in dockerfile
    assert "io.automx.base.python.digest" in runtime
    assert "org.opencontainers.image.revision" in runtime
    assert "io.automx.build.reason" in runtime


def test_makefile_exposes_a_distinct_mojo_image_build() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "docker-build-mojo:" in makefile
    assert "--file Dockerfile-mojo" in makefile
    mojo_target = makefile.split(
        "docker-build-mojo:", maxsplit=1
    )[1]
    assert "--build-arg VERSION=$(VERSION)" in mojo_target
    assert "--tag $(MOJO_IMAGE)" in mojo_target
    assert "scripts/mojo-container-smoke.sh $(MOJO_IMAGE)" in makefile


def test_mojo_release_guard_rejects_avx512_code() -> None:
    guard = (ROOT / "scripts/check-no-avx512.sh").read_text(encoding="utf-8")

    assert "objdump -d" in guard
    assert "AVX-512" in guard
    assert "zmm" in guard
    assert "[0-7]" in guard


def test_mojo_release_guard_fails_on_evex_machine_code(tmp_path: Path) -> None:
    fake_objdump = tmp_path / "objdump"
    fake_objdump.write_text(
        "#!/bin/sh\n"
        "printf '    5b41:\\t62 f1 fd 48 6f 05  vmovdqa64 %%%%zmm0,%%%%zmm1\\n'\n",
        encoding="utf-8",
    )
    fake_objdump.chmod(0o755)
    binary = tmp_path / "automx"
    binary.touch()

    completed = subprocess.run(  # noqa: S603 - fixed repository script under test
        [str(ROOT / "scripts/check-no-avx512.sh"), str(binary)],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"},
    )

    assert completed.returncode == 1
    assert "AVX-512 instructions detected" in completed.stderr


def test_mojo_container_smoke_covers_cli_config_and_serve() -> None:
    smoke = (ROOT / "scripts/mojo-container-smoke.sh").read_text(encoding="utf-8")

    assert '"--version"' in smoke
    assert '"--help"' in smoke
    assert '"config" "validate"' in smoke
    assert '"serve"' in smoke
    assert "/health/ready" in smoke
