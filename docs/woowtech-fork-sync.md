# WOOWTECH fork-sync：重新套用清單

`WOOWTECH/Woow_ha_ai_mcp` 是 `homeassistant-ai/ha-mcp` 的 fork。fork-sync 如果把 `master`
重設回上游，fork 專屬的修改都會消失。本文件列出同步之後**必須重新套用**的修改，以及哪些 fork
commit 可以丟掉。來源：WOOW addon pipeline #44（ai-mcp-pinning/44），#103 的 `ci.yml`。

「fork-sync 還是改成 mirror」由 pipeline #191 決定；這份清單兩種做法都要用。

盤點基準（2026-11-13）：fork `master` = `da0d2f3e`；和上游的 merge-base = `4911d09d`
（上游 `chore(addon): publish version 7.14.1`，2026-07-19）；當時上游 `master` = `25d32693`，
fork 落後 1466 個 commit。查 fork 專屬修改：

```sh
git fetch upstream master
git log --oneline "$(git merge-base upstream/master origin/master)"..origin/master
git diff --stat "$(git merge-base upstream/master origin/master)" origin/master
```

## 必須重新套用

| # | 路徑 | 來源 commit | 說明 |
|---|------|-------------|------|
| 1 | `.github/workflows/woow-addon-sync.yml` | `b94ee541`、`49d00c1e`、`c7b8d79f` | WOOWTECH 自有，整個檔案照抄回來。通知 App Store 有新版本：呼叫 `WOOWTECH/Woow_HA_App_Store/.github/workflows/woow-addon-publish.yml@main`，再以 `repository_dispatch woow-addon-ready` 通知 Store（secret `APP_STORE_DISPATCH_TOKEN`，沒有時只警告）。 |
| 2 | `.github/workflows/ci.yml` | `f3c2c536`、`e5d433f2`（fork PR #2，merge `4b368133`，#103） | WOOWTECH 自有，整個檔案照抄回來，**連同裡面的版本釘選**：add-on linter v2.21.2（`frenck/action-addon-linter` `d51677290aef26cdfc835271dd3c7343ce502809`）、`docker/setup-buildx-action@bb05f3f5519dd87d3ba754cc423b652a5edd6d2c`（v4）、`docker/build-push-action@53b7df96c91f9c12dcc8a07bcb9ccacbed38856a`（v7）。Store registry 把它列在 `required_workflows`；漏掉的話 Store 會擋住 ai_mcp 的同步。 |
| 3 | `woow-addon-sync.yml` 的 `on.workflow_run.workflows` 裡的 `- CI` | `6860a577`（fork PR #2） | **保留**（負責人 2026-11-13 決定）：ci.yml 跑完後再通知 Store 一次，Store 才看得到這個 commit 的 CI 結果。 |
| 4 | `custom_components/ha_mcp_tools/brand/*.png`（8 個檔） | `a770e7ad` | WOOWTECH 圖示（`icon`、`logo`、`dark_*`，含 `@2x`）。上游的同名檔會蓋掉它們。 |
| 5 | `custom_components/ha_mcp_tools/const.py` 的 `DEFAULT_AUTO_UPDATE = False`，元件版本 1.2.4（`COMPONENT_VERSION`、`manifest.json`），以及跟著改的單元測試 | `1987814b`（#44 步驟 44b） | 關閉 ha-mcp server 的自動更新：reload／重開機會留在已安裝的版本，update entity 仍會顯示新版。`DEFAULT_PIP_SPEC` **刻意不釘版**，等出貨的 HA ≥2026.8 再釘（見下一節）。 |
| 6 | `pyproject.toml`、`uv.lock` 的套件版本 = `homeassistant-addon/config.yaml` 的版本（目前 7.14.1） | 本 PR（#198） | fork 的 semantic-release 曾在 `49a47e1e` 把套件版本改成 7.7.0，上游 Unit／E2E 因版本不一致而紅燈。重設回上游後如果版本號一致就不必重套；之後若 fork 的排程發版又改壞版本號，照這列改回來。 |

### 第 5 列：已知的剩餘風險

`DEFAULT_PIP_SPEC` 沒有釘版，所以**第一次安裝**（機器上還沒有 ha-mcp）仍會裝當時最新的
ha-mcp。關掉自動更新只能讓之後的 reload／重開機不再自己升級。2026-11-13 在 .36、.33（HA 2026.7.2，
Python 3.14.6）驗證過：embedded server 接受的 ha-mcp（≥7.10.0）都釘 websockets 16.x，HA 2026.7.2
是 15.0.1；照 HA requirements manager 的方式安裝會一起升級 websockets、click、rich、cachetools、
opentelemetry-api 等，違反 HA 內建套件宣告的版本範圍；8.x 以後的元件還要求 HA ≥2026.8。出貨的 HA
升到 2026.8 以上之後，再把 `DEFAULT_PIP_SPEC` 釘在驗證過的版本。

另外兩種情況，自動更新關掉了仍會裝最新的 ha-mcp（負責人 2026-11-13 決定記為已知風險，不另外修正）：

- **已經存過選項的機器**：新的預設值只在 config entry 沒有 `auto_update` 這個 key 時生效。1.2.4 之前
  選項表單的「自動更新」預設是勾選的，所以有人開過伺服器選項並按下儲存的機器，存的是 `True`，升到
  1.2.4 之後仍會自動更新。元件沒有 options 遷移。要關掉，得在該機器的選項裡手動取消勾選。
- **已安裝的 ha-mcp 低於 `MIN_EMBEDDED_SERVER_VERSION`**：`embedded_server.py` 記一筆
  「Ignoring auto-update pin to legacy …」，然後改用不釘版的 dist，裝當時最新的 ha-mcp。

### 第 5 列：為什麼元件版本是 1.2.4

上游 AGENTS.md 的規則是：`master` 上的元件版本還沒進 `stable` 時不再升版。fork `master` 原本是
1.2.3，從沒出貨（出貨的 28 份副本都是 1.2.2），照上游規則應該留在 1.2.3。負責人 2026-11-13 決定用
1.2.4：WOOWTECH 不走上游的 `stable` 發版週期，元件靠同步副本出貨，新的版本號讓副本裡帶不帶這個修改
一眼就分得出來。

### 第 1、3 列的注意事項

- `woow-addon-sync.yml` 的 `workflow_run.workflows` 是照上游 workflow 的 `name:` 列的。同步後上游可能改名、增減 workflow，要用新的 `.github/workflows/*.yml` 重新核對這份清單。
- 上游的 add-on 設定（`homeassistant-addon*/config.yaml` 等）**刻意保持跟上游 byte-identical**，不要為了 linter 去改。`ci.yml` 的 lint job 只容許「`'<key>' should be removed, it uses a default value`」這一類錯誤（`startup: application`、`boot: auto`），其他錯誤都會讓 job 失敗。

## 元件本身：同步前要先決定

上游 `master`（`25d32693`）的 `ha_mcp_tools` 已經是 9.2.0：

- `manifest.json` 的 `requirements` 有 `"ha-mcp==9.2.0"`、`"mcp>=1.24.0"`、`"voluptuous-openapi>=0.4.1"`。
- `MIN_EMBEDDED_HOME_ASSISTANT_VERSION = "2026.8.0"`。

出貨機器是 HA 2026.7.2，所以直接重設回上游最新版，元件就不能用在出貨機器上。同步時要選一個上游
版本，或保留 fork 的元件（`1.2.4`），由 #191／#44 決定；不要只照抄上表就結束。

fork 的元件修正 `89ea666e`、`da0d2f3e`（`manifest.json` 加 `voluptuous-openapi>=0.3.0`，
`COMPONENT_VERSION` 與 manifest 版本 `1.2.3`，相關測試與 `pyproject.toml` 註解）上游已經用
`voluptuous-openapi>=0.4.1` 涵蓋。HA 2026.7.2 內建 `voluptuous_openapi` 0.4.1，所以上游的寫法
在出貨機器上也成立；只有要支援 HA 2026.6 時才需要保留 `>=0.3.0`。

## 上游 CI 在 fork 上不看的項目

`HAOS E2E Tests`、`HAOS E2E Tests (embedded)`、`HAOS E2E Tests (inaddon)` 在 fork 上從沒通過過（HAOS VM 在 600 秒內開不起來，原因未查，見 pipeline #198）。在 #191 決定 fork 要不要改成 mirror 之前，fork 的 PR 上這 3 項紅燈**不看**；合併以 WOOWTECH 的 `ci.yml` 與其餘上游 check 為準。

fork 的 `semver-release.yml` 仍有雙週排程（`49a47e1e` 就是它產生的）；它若再發版，可能再改壞第 6 列的版本號。

## 同步時丟掉的 fork commit

| commit | 內容 | 為什麼可以丟 |
|--------|------|--------------|
| `49a47e1e` | `7.7.0`（python-semantic-release 在 fork 上跑出來的 `CHANGELOG.md`、`pyproject.toml`、`uv.lock`） | 機器產生；上游有自己的版本號與 changelog。 |
| `83b3f4f2` | `chore(addon): sync changelog for Home Assistant add-on` | 同上，機器產生。 |

## 同步後的檢查

1. 上表第 1–6 列都在（第 3 列看當時的決定）。
2. `ci.yml` 在 `master` 的 push run 是綠的。
3. `woow-addon-sync.yml` 的 `workflow_run.workflows` 跟 `.github/workflows/*.yml` 的 `name:` 一致。
4. 元件版本和 ha-mcp 釘版跟出貨機器的 HA 版本相容（見上一節）。
