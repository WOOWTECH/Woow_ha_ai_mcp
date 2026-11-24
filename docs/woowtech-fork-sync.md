# WOOWTECH fork：`master` 是 mirror，integration 在 `woowtech/ha-mcp-tools`

`WOOWTECH/Woow_ha_ai_mcp` 是 `homeassistant-ai/ha-mcp` 的 fork。從 WOOW addon pipeline release-gating #216
起（母 issue #191），`master` 不再是「上游＋WOOWTECH 修改」，而是和其他 5 個 Mirror 來源一樣的 **mirror**：
`master` 只跟上游 `master`，WOOWTECH 只在上面加一層 overlay。這份文件是本 repo 唯一的 WOOWTECH 說明，
也是 overlay 的一部分（每次重建都會放回 `master`）。

## `master` 怎麼來的

`.github/workflows/mirror-sync.yml`，每天排程一次，也可以手動觸發（作法同 pipeline #166）：

1. 抓上游 `master`，把去掉 `.github` 的 tree 加成 `upstream` 分支上的一個 snapshot commit
   （只往前加 commit，不 force-push，不推上游的 tag）。
2. `master` 的 tree 換成上游 tree，刪掉上游的 `.github`，放回 overlay，在舊的 `master` 上面加一個 commit
   （不 force-push；Store 只接受從上一個快照往下長的 commit）。
3. Store 的升版比對（sha 模式）把每個版本和最新正式 Release 不同的出貨 add-on 跟那個 Release 比；
   通過的才由 Store 的 Release workflow 發正式 Release（`ha_mcp-v<version>`、`ha_mcp_webhook_proxy-v<version>`）。
   dev 通道（`homeassistant-addon-dev`、`homeassistant-addon-webhook-proxy-dev`）不比對、不發 Release、不進 Store。

**overlay**（其他東西都會在下一次重建被上游的版本蓋掉，不要手動改在 `master` 上）：

| 路徑 | 內容 |
|------|------|
| `.github/workflows/woow-addon-sync.yml` | 通知 App Store 有新的正式 Release（`push` 到 `master`、`mirror-sync` 跑完、排程）。 |
| `.github/workflows/mirror-sync.yml` | 上面的同步、比對、發 Release。 |
| `.mirror/` | `config.env`（上游網址與分支）、`last-sync.yaml`、各 add-on 的 `version-ceiling.yaml`、`upgrade-notes.yaml`（說明見 `.mirror/README.md`）。 |
| `docs/woowtech-fork-sync.md` | 本文件。 |

`.github` 只有上面兩個 workflow。上游的 CI（E2E、semantic-release、dev 發布、Codex…）以及 #103 的
`ci.yml` 都不在 `master` 上，不會在 fork 上跑。Store registry 的 `required_workflows` 是空的，
`branch_rules.exempt` 以 `mirror:` 開頭（issue monitor 靠它列出 mirror-sync 結果）。

出貨的兩個 add-on 目錄 `homeassistant-addon/`、`homeassistant-addon-webhook-proxy/` 和上游 `master` 相同，
只多了 overlay 複製進去的 `version-ceiling.yaml`、`upgrade-notes.yaml`。ha_mcp 用上游預先建好的映像
（`ghcr.io/homeassistant-ai/ha-mcp-addon-{arch}`，`config.yaml` 的 `version:` 決定拉哪個）；webhook proxy
在裝置上建置。映像沒有複製到 WOOWTECH 的 GHCR。

## 版本上限（Version Ceiling）

在 `.mirror/<add-on 目錄>/version-ceiling.yaml`，每個出貨 add-on 一份：

| add-on | 檔案 | 上限 |
|--------|------|------|
| `ha_mcp` | `.mirror/homeassistant-addon/version-ceiling.yaml` | `9.2.x` |
| `ha_mcp_webhook_proxy` | `.mirror/homeassistant-addon-webhook-proxy/version-ceiling.yaml` | `3.0.x` |

- **為什麼**：上游 `master` 在 9.2.0 之後的程式碼（`d5c88170e`，2026-11-21）要求 HA 2026.11，但 add-on 的
  `config.yaml` 沒寫 `homeassistant:`，所以 Store 的 Core 版本要求檢查（#217）抓不到。出貨 HA 是 2026.7.2；
  9.2.0／3.0.5 在 2026.7.2 上實機驗過（#214）。
- **超過時**：Store 的升版比對把該 add-on 判為**暫緩**：`upstream` 快照與 `master` 照樣更新，但不比對、
  不發正式 Release；`mirror-sync` 的 run 是綠的，多一個 `Held (暫緩)` 步驟，monitor 以黃色「held」顯示，
  和失敗的紅色分開。Store 繼續提供最後一個正式 Release。
- **怎麼調**：只能由人改。出貨 HA 升到上游新版要求的版本（並經過實機驗收）之後，改這份檔案的 `ceiling`
  （或刪掉檔案），commit 到 `master`，手動觸發 `mirror-sync`；新版本通過升版比對才會發 Release。
  沒有自動解除。不要改 `homeassistant-addon/version-ceiling.yaml`，那是重建時複製過去的副本。

## integration：分支 `woowtech/ha-mcp-tools`（pipeline #215）

WOOWTECH 版的 `custom_components/ha_mcp_tools`（元件 1.2.4）在長期分支 `woowtech/ha-mcp-tools` 維護。
`master` 上的 `custom_components/ha_mcp_tools` 是上游版，**不是**出貨的版本，也不會從 `master` 出貨。

- **起點**：mirror 之前的 fork `master` `3456f26f`（integration tree `76a79bfc`）。
- **誰在用**：`apporo_ha_multi_ha_core`、`woowtech_ha_multi_ha_core` 的 seed manifest 把 `ha_mcp_tools` 釘在
  這個分支上的 commit sha；ha-rebrand 的副本來源紀錄也指向這個分支。元件要出貨新版時，先合進這個分支，
  再到兩個 multi_ha_core repo 改釘 sha、重跑 vendor。
- **怎麼改**：只能經 PR 合併（ruleset「woowtech/ha-mcp-tools: PR and green checks」），必要檢查是這個分支上的
  `.github/workflows/ha-mcp-tools-tests.yml`（job `ha_mcp_tools unit tests`）。分支上的說明文件寫了它的細節。
- **什麼時候結束**：出貨 HA ≥2026.8 時，從上游當時的 integration 重新開始，重新套用 WOOWTECH 的修改
  （品牌圖、`DEFAULT_AUTO_UPDATE = False`，`DEFAULT_PIP_SPEC` 那時釘在驗證過的 ha-mcp 版本），不要 rebase 舊分支。

## mirror 之前的 WOOWTECH 修改去哪了

切換時沒有改寫歷史：mirror 之前的 commit（含 WOOWTECH 的修改與合併）仍在 `master` 的歷史裡，第一個重建
commit 直接接在 `3456f26f` 上面。舊的「fork-sync 重新套用清單」（#44、#103）各列的去向：

| 舊列 | 內容 | 現在 |
|------|------|------|
| 1 | `woow-addon-sync.yml` | 留在 overlay；`workflow_run` 只剩 `mirror-sync`。 |
| 2、3 | `ci.yml` 與 `woow-addon-sync.yml` 裡的 `- CI` | 刪除（#191 決定 4）；mirror 改由升版比對把關。 |
| 4、5 | integration 的品牌圖、`DEFAULT_AUTO_UPDATE`、元件 1.2.4 | 在 `woowtech/ha-mcp-tools`（#215）。 |
| 6 | `pyproject.toml`、`uv.lock` 的版本號 | 不再需要：用上游的。fork 的 `semver-release.yml` 已不在 `master`，不會再改壞版本號。 |

fork 的 GitHub Release `v7.7.0` 與 `v7.*.dev*` 是 fork 以前的 semantic-release 產生的，不是正式 Release
（正式 Release 的 tag 是 `ha_mcp-v<version>` 與 `ha_mcp_webhook_proxy-v<version>`），Store 不看它們。
第一組正式 Release 是 mirror 之前 `master` `3456f26f` 上手動建立的種子 `ha_mcp-v7.14.1`、
`ha_mcp_webhook_proxy-v2.0.4`，第一次 `mirror-sync` 拿 9.2.0／3.0.5 跟它們比對。
