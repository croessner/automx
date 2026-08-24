from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_readme_relative_markdown_links_exist() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^]]+]\(([^)]+)\)", readme)

    relative_links = [link for link in links if "://" not in link and not link.startswith("#")]
    assert relative_links
    for link in relative_links:
        assert (ROOT / link).is_file(), link


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
