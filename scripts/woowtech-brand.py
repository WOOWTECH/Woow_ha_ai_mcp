#!/usr/bin/env python3
"""Apply the WOOWTECH display-layer rebrand to custom_components/ha_mcp_tools.

Idempotent: running it on an already-branded tree makes no changes. It ONLY
touches user-visible display strings — the brand name shown in the sidebar
panel, config-flow titles, notifications, device registry, and manifest.

It deliberately does NOT touch functional endpoints, so pip-install and
auto-update keep working against upstream:
  - const.py DIST_NAME_STABLE/DEV ("ha-mcp"/"ha-mcp-dev")  -> untouched
  - all github.com/homeassistant-ai + raw.githubusercontent + pypi URLs -> untouched
  - HACS mirror/legacy repo names, DOMAIN, notification IDs               -> untouched
  - LICENSE                                                               -> untouched
(These stay lowercase "ha-mcp"; only the UPPERCASE brand token "HA-MCP" and a
few explicit strings are rebranded.)

Run after every upstream sync (see docs/UPSTREAM-SYNC-NOTES.md).
Usage:  python scripts/woowtech-brand.py
"""

from __future__ import annotations

from pathlib import Path

DISPLAY = "WOOWTECH MCP"
FORK_URL = "https://github.com/WOOWTECH/Woow_ha_ai_mcp"

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / "custom_components" / "ha_mcp_tools"

# Files that carry the UPPERCASE "HA-MCP" brand token (display/log/comments
# only — verified no URL or identifier uses the uppercase form).
GLOBAL_FILES = [
    "__init__.py", "config_flow.py", "const.py", "coordinator.py",
    "embedded_server.py", "embedded_setup.py", "hacs.json", "hacs_nudge.py",
    "install_source_check.py", "llm_api.py", "manifest.json", "mcp_webhook.py",
    "oauth_legacy.py", "strings.json", "ui_panel.py", "update.py",
    "translations/en.json", "translations/de.json", "translations/ru.json",
]

# Applied in order to each GLOBAL_FILES file. The "Custom Component" pair runs
# first so the component name collapses to a clean "WOOWTECH MCP".
GLOBAL_REPLACEMENTS = [
    ("HA-MCP Custom Component", DISPLAY),
    ("HA-MCP", DISPLAY),
]

# Exact, file-scoped replacements for brand bits that are NOT the "HA-MCP"
# token (device identity, display links, "Home Assistant MCP" prose).
TARGETED = {
    "update.py": [
        ('manufacturer="homeassistant-ai"', 'manufacturer="WOOWTECH"'),
        ('model="ha-mcp (in-process server)"',
         f'model="{DISPLAY} (in-process server)"'),
        ('configuration_url="https://github.com/homeassistant-ai/ha-mcp"',
         f'configuration_url="{FORK_URL}"'),
    ],
    "manifest.json": [
        ('"documentation": "https://github.com/homeassistant-ai/ha-mcp"',
         f'"documentation": "{FORK_URL}"'),
        ('"issue_tracker": "https://github.com/homeassistant-ai/ha-mcp/issues"',
         f'"issue_tracker": "{FORK_URL}/issues"'),
    ],
    "llm_api.py": [
        ("Home Assistant MCP toolset", f"{DISPLAY} toolset"),
        ("Home Assistant MCP tool by name", f"{DISPLAY} tool by name"),
    ],
    "oauth_legacy.py": [
        ("your Home Assistant MCP server", f"your {DISPLAY} server"),
    ],
}

# English-prose polish: rebrand lowercase "ha-mcp server" where it names the
# running SERVER PRODUCT (now WOOWTECH MCP), applied ONLY to the English source
# strings. Deliberately KEEPS genuine package/repo references accurate:
#   "ha-mcp package" / "ha-mcp build" / pip_spec / "ha-mcp add-on" /
#   "homeassistant-ai/ha-mcp-integration" / "tracking the main ha-mcp server
#   repository"  -> untouched (that is literally the upstream PyPI package/repo).
# de.json/ru.json prose is translated (different surrounding words) and is left
# as-is; the uppercase brand token in them is already handled above.
EN_PROSE_FILES = ["strings.json", "translations/en.json"]
EN_PROSE = [
    ("runs the full ha-mcp server", f"runs the full {DISPLAY} server"),
    ("If your ha-mcp server already runs", f"If your {DISPLAY} server already runs"),
    ("alongside another ha-mcp server", f"alongside another {DISPLAY} server"),
    ("The installed ha-mcp server requires", f"The installed {DISPLAY} server requires"),
    ("with an external ha-mcp server running", f"with an external {DISPLAY} server running"),
    ("managed from the ha-mcp server's own settings",
     f"managed from the {DISPLAY} server's own settings"),
    ("ha-mcp's opt-in file", f"{DISPLAY}'s opt-in file"),
    ("This controls the ha-mcp server package only",
     f"This controls the {DISPLAY} server package only"),
]


def apply(path: Path, pairs: list[tuple[str, str]]) -> int:
    text = original = path.read_text(encoding="utf-8")
    n = 0
    for old, new in pairs:
        if old in text:
            n += text.count(old)
            text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8", newline="\n")
    return n


def main() -> None:
    files_changed = 0
    total = 0
    # Global brand-token pass
    for rel in GLOBAL_FILES:
        c = apply(COMP / rel, GLOBAL_REPLACEMENTS)
        if c:
            files_changed += 1
            total += c
            print(f"  HA-MCP->{DISPLAY:<12} {c:>3}x  {rel}")
    # Targeted pass
    for rel, pairs in TARGETED.items():
        c = apply(COMP / rel, pairs)
        if c:
            files_changed += 1
            total += c
            print(f"  targeted           {c:>3}x  {rel}")
    # English-prose polish pass
    for rel in EN_PROSE_FILES:
        c = apply(COMP / rel, EN_PROSE)
        if c:
            files_changed += 1
            total += c
            print(f"  en-prose           {c:>3}x  {rel}")
    print(f"\nWOOWTECH brand applied: {total} replacement(s) across "
          f"{files_changed} file(s). (0 = already branded / idempotent no-op)")


if __name__ == "__main__":
    main()
