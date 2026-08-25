from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "POLICY.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    ROOT / "contrib/production-example/README.md",
)


def test_relative_markdown_links_exist() -> None:
    checked_links = 0
    for document in DOCUMENTS:
        links = re.findall(
            r"\[[^]]+]\(([^)]+)\)", document.read_text(encoding="utf-8")
        )
        relative_links = [
            link
            for link in links
            if "://" not in link and not link.startswith("#")
        ]
        for link in relative_links:
            path = link.split("#", maxsplit=1)[0]
            assert (document.parent / path).is_file(), f"{document}: {link}"
            checked_links += 1

        code_references = re.findall(
            r"`([^`]+\.md)`", document.read_text(encoding="utf-8")
        )
        for reference in code_references:
            assert (document.parent / reference).is_file(), (
                f"{document}: {reference}"
            )
            checked_links += 1
    assert checked_links > 0


def test_required_policy_documentation_and_skills_exist() -> None:
    required = (
        "AGENTS.md",
        "POLICY.md",
        "docs/architecture.md",
        "docs/configuration.md",
        "docs/deployment.md",
        "docs/cli.md",
        "docs/testing.md",
        "docs/migration.md",
        "docs/troubleshooting.md",
        "docs/protocols/status.md",
        "docs/protocols/oauth-dcr.md",
        "docs/protocols/pacc.md",
        ".agents/skills/automx-modernization/SKILL.md",
        ".agents/skills/automx-protocol-contracts/SKILL.md",
        ".agents/skills/automx-e2e-sbom/SKILL.md",
    )
    for path in required:
        assert (ROOT / path).is_file(), path


def test_documentation_examples_use_reserved_test_domains() -> None:
    for document in DOCUMENTS:
        source = document.read_text(encoding="utf-8")
        assert "example.com" not in source, document
        assert "example.net" not in source, document


def test_obsolete_runtime_and_installation_entrypoints_are_removed() -> None:
    obsolete = (
        "src/automx_wsgi.py",
        "src/automx-test",
        "src/automx/config.py",
        "src/automx/view.py",
        "src/conf/apache.conf.example",
        "src/conf/nginx-automx.conf",
        "INSTALL",
        "BASIC_CONFIGURATION_README",
    )
    for path in obsolete:
        assert not (ROOT / path).exists(), path
