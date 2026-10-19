"""Dependencies needed before the embedded server can install its own package."""

import ast
import json
from pathlib import Path

from packaging.requirements import Requirement

COMPONENT = Path(__file__).resolve().parents[3] / "custom_components/ha_mcp_tools"


def test_schema_converter_is_installed_on_clean_home_assistant():
    """HA 2026.9+ no longer bundles llm_api's eager schema-converter import."""
    requirements = {
        requirement.name: requirement
        for value in json.loads((COMPONENT / "manifest.json").read_text())[
            "requirements"
        ]
        if (requirement := Requirement(value))
    }
    assert "voluptuous-openapi" in requirements
    assert "0.4.1" in requirements["voluptuous-openapi"].specifier
    # HA 2026.6 constrains this to 0.3.0, which already exports the converter.
    assert "0.3.0" in requirements["voluptuous-openapi"].specifier
    assert "0.2.0" not in requirements["voluptuous-openapi"].specifier


def test_manifest_and_component_version_match():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    constants = ast.parse((COMPONENT / "const.py").read_text())
    version = next(
        ast.literal_eval(node.value)
        for node in constants.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "COMPONENT_VERSION"
            for target in node.targets
        )
    )
    assert manifest["version"] == version
