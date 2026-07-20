# Upstream Sync Notes

This fork (`WOOWTECH/Woow_ha_ai_mcp`) is a **WOOWTECH-branded distribution** of
[`homeassistant-ai/ha-mcp`](https://github.com/homeassistant-ai/ha-mcp),
maintained with a **rebrand-on-top** strategy: `master` is reset to the upstream
`master` on each sync, then only the WOOWTECH branding + a minimal publishing
setup are re-applied on top. No functional divergence from upstream is kept.

## 2026-07-20 sync

- **Upstream base:** `4911d09d` (`chore(addon): publish version 7.14.1`)
- **Custom component:** upgraded `ha_mcp_tools` v0.4.1 (old "File & YAML" only)
  → **v1.2.2** (full in-process server: webhook, `/ha-mcp` panel, LLM API).
- **Backup of the pre-sync state:** tag/branch `backup/pre-sync-2026-07-20`.

### What the old fork carried (12 ahead commits) and how each was handled

merge-base before this sync = `086d75d7` (2026-05-27, ~upstream v7.6.0).

| Group | Commit(s) | Purpose | Disposition |
|---|---|---|---|
| **A. Server optimizations** | `4e1d4f64`, `cbea205d` | 6 QoL tool tweaks (param anti-pattern warnings, `ha_get_history` `hours` alias, bulk-control `summary`, automation `stored_config`, `wait_for_automation_queryable`, Levenshtein fuzzy fallback) + 32 tests | **Dropped** — stale (~617 commits behind), very likely superseded upstream; not worth maintaining against a fast-moving base. |
| **B. Branding** | `c83ccc93`, `2d9f1272`, `64ec2a40`, `47df512d` | WOOWTECH icons/logos for the custom component + all three add-ons | **Re-applied** — 10 genuinely-woowtech images restored on top of upstream. |
| **C. Fork infra** | `8b4c2283`, `16c8dec1`, `88ac2ff7`, `5153419a`, `dead93d6` | Point add-on image registry/url at WOOWTECH; slim/adapt CI | **Re-derived** against upstream's current files (see below), not cherry-picked. |
| **D. Docs** | `19b729be` | Chinese guide for the old 86-tool set | **Dropped** — stale; regenerate from current tool set if wanted. |

### Branding re-applied

- Custom component: `custom_components/ha_mcp_tools/brand/{icon,icon@2x,logo,logo@2x}.png`
  (light variants; upstream `dark_*` kept as-is — they were never woowtech).
- Add-on store: `homeassistant-addon/{icon,logo}.png`, `homeassistant-addon-dev/{icon,logo}.png`.
- Webhook-proxy: `homeassistant-addon-webhook-proxy/{icon,logo}.png` (added; upstream has none).

### Config / publishing rebrand

- `homeassistant-addon/config.yaml` & `homeassistant-addon-dev/config.yaml`:
  `url` → this fork; `image` → `ghcr.io/woowtech/ha-mcp-addon(-dev)-{arch}`.
  `name`/`version` track upstream.
- `repository.yaml`: name/url/maintainer → WOOWTECH.
- `.github/workflows/addon-publish.yml`: `IMAGE_PREFIX` → `ghcr.io/woowtech/ha-mcp-addon`
  (so a manual dispatch publishes the branded add-on to the WOOWTECH registry).

### CI posture

Upstream ships ~38 workflows, many firing on `push` and needing upstream-only
secrets/infra (release/publish/notify/mirror/bots). To keep the fork quiet and
avoid unintended outward actions, **every workflow is disabled (`*.yml.disabled`)
except `addon-publish.yml`**, which is `workflow_dispatch`-only (manual) and
targets the WOOWTECH registry. Re-enable individual workflows deliberately if
needed.

## How to sync again next time

1. `git fetch upstream`
2. `git tag backup/pre-sync-<date> master && git reset --hard upstream/master`
3. Re-apply branding: `git checkout backup/pre-sync-<date> -- <the 10 image paths>`
4. Re-derive config/repository/addon-publish rebrand (this file's "Config" section).
5. Re-disable non-essential workflows (keep `addon-publish.yml`).
6. Update this file, commit, `git push --force-with-lease origin master`.
