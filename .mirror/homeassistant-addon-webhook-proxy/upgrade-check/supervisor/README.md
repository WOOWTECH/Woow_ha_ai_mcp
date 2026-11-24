# Upgrade-test fixtures for the webhook proxy (release-gating #216)

The Store upgrade test runs the proxy against a mock Supervisor. On start the proxy lists `/addons` and reads
`/addons/<slug>/info` to find a running ha_mcp add-on and its secret path; without an answer it exits with
"No running MCP addon found". These fixtures answer with one started `ha_mcp` (secret path set in its options),
so both the comparison target and the new version can start. mirror-sync copies this directory into
`homeassistant-addon-webhook-proxy/upgrade-check/` on every rebuild.
