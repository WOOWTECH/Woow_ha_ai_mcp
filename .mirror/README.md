# `.mirror/` — mirror operations

Everything here is WOOWTECH-added, not from upstream (homeassistant-ai/ha-mcp). `master` is a Mirror source
since WOOW addon pipeline release-gating #216: `.github/workflows/mirror-sync.yml` rebuilds it every night
from upstream `master` plus this overlay. See `docs/woowtech-fork-sync.md` for the whole story.

## Files

- **`config.env`** — sourced by `mirror-sync`: upstream URL and branch.
- **`last-sync.yaml`** — timestamp and upstream commit of the last rebuild (written by `mirror-sync`).
- **`<add-on dir>/version-ceiling.yaml`** — the version ceiling (版本上限) of that add-on: the highest
  `config.yaml` `version:` that may get a formal Release. Above it the Store's upgrade comparison holds the
  add-on (暫緩): the snapshot still moves, no Release, the run stays green with a `Held (暫緩)` step.
  Format: `ceiling: "9.2.x"` (quoted; `N.N.x`, `N.x` or an exact `N.N.N`) and an optional `reason:`.
- **`<add-on dir>/upgrade-notes.yaml`**, **`<add-on dir>/upgrade-check/`** (optional) — declared breaking
  changes and upgrade test hooks/settings for the Store's upgrade comparison.

`mirror-sync` copies the per-add-on files into `<add-on dir>/` on every rebuild, where the Store tools read
them. Edit them here, never in `<add-on dir>/` (the next rebuild overwrites that copy).

## Overlay

The rebuild replaces the whole tree with upstream's and then copies back only: `.github/` (exactly
`woow-addon-sync.yml` and `mirror-sync.yml`), `.mirror/` and `docs/woowtech-fork-sync.md`. Anything else
committed to `master` by hand is lost at the next rebuild.

## Release gating (pipeline #91)

`mirror-sync` runs sync → the Store's upgrade comparison → Release, and only the add-ons that pass get a
Release (`ha_mcp-v<version>`, `ha_mcp_webhook_proxy-v<version>`). The dev channels are never compared or
released. For an intended upstream breaking change, declare it (with the migration) in
`.mirror/<add-on dir>/upgrade-notes.yaml`, commit it to `master`, and run `mirror-sync` by hand. To raise a
ceiling, edit `.mirror/<add-on dir>/version-ceiling.yaml`, commit, and run `mirror-sync` by hand.
