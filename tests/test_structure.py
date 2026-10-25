"""Repository checks: metadata, the domain change, and what must never ship."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "nohassle_av"


def test_metadata():
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["domain"] == "nohassle_av"
    assert manifest["config_flow"] is True
    assert manifest["requirements"] == []  # the matrix speaks HTTP via HA's session
    assert manifest["version"] == project["project"]["version"] == "0.4.0"
    assert hacs["name"] == "No Hassle AV"


def test_english_translation_matches_source_strings():
    strings = json.loads((PACKAGE / "strings.json").read_text(encoding="utf-8"))
    english = json.loads(
        (PACKAGE / "translations" / "en.json").read_text(encoding="utf-8")
    )
    assert english == strings


def test_no_core_domain_is_shipped():
    """HACS rejects integrations that override a core domain such as monoprice."""
    folders = [p.name for p in (ROOT / "custom_components").iterdir() if p.is_dir()]
    assert folders == ["nohassle_av"]


def test_no_em_dashes_in_user_facing_text():
    files = [ROOT / "README.md", ROOT / "AUDIT.md", PACKAGE / "strings.json"]
    files += list(PACKAGE.glob("*.py"))
    for path in files:
        assert "\u2014" not in path.read_text(encoding="utf-8"), path.name


def test_nothing_touches_another_integration():
    """Setup, flows and entities stay inside this domain, importing no other."""
    for path in PACKAGE.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "monoprice" not in text, path.name
        assert "legacy" not in text, path.name
    assert not (PACKAGE / "migration.py").exists()
