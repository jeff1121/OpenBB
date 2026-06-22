# OpenBB 專案 Copilot 協作指南

本文件旨在指導未來的 Copilot 會話及 AI 助手，確保在 OpenBB 儲存庫中進行開發、測試與維護時，能遵循最符合專案架構與規範的實踐。

---

## 核心行為原則

### 1. 先思考，後編碼
* **不要假設，不要隱瞞疑惑，主動提出折衷方案。**
* 在實作前，明確闡述你的假設。若有不確定之處，請主動詢問使用者。
* 若有多種實作詮釋，請主動呈現，不要默默替使用者決定。
* 若有更簡單的解決方案，請提出。必要時勇於推動更簡潔的設計。

### 2. 簡潔至上
* **用最少且最簡單的程式碼解決問題，不進行任何預測性、投機性的開發。**
* 不要加入使用者未要求的額外功能。
* 不要為單次使用的代碼建立不必要的抽象。
* 不要為不可能發生的情境編寫錯誤處理。
* 儘可能保持程式碼精簡，避免過度設計（MVP 原則）。

### 3. 精準修改
* **只觸碰必須修改的部分，且僅清理自己產生的變更。**
* 編輯現有代碼時，不要「順便」改進相鄰代碼、註解或格式。
* 不要重構沒有損壞的部分。
* 保持並符合現有的代碼風格。
* 若發現無關的死程式碼，請提及即可，不要直接刪除。
* 變更所產生的孤立導入或變數，請務必清理乾淨。

### 4. 目標導向執行
* **定義成功的檢驗標準，並持續循環驗證直到成功。**
* 將任務轉換為可驗證的目標：
  * 「新增驗證」 → 「為無效輸入編寫測試，並使其通過」
  * 「修復 Bug」 → 「編寫重現 Bug 的測試，並使其通過」
  * 「重構 X」 → 「確保重構前後測試皆能通過」

### 5. 品質與設計原則
* **遵循 MVP 原則，切勿過度設計。**
* 設計前端時，使用 `ui-ux-pro-max` 技能。
* 使用 `felo-search` 進行搜尋。
* 使用 `playwright-cli` 以有頭模式測試前端。
* **全程使用繁體中文（zh-TW）**：所有文件、對話與程式碼註解皆必須使用繁體中文。

---

## 建置、測試與 Linter 指令

### 1. Python 平台 (openbb_platform)
* **以可編輯模式安裝本地平台包**：
  ```bash
  cd openbb_platform && python dev_install.py
  ```
* **連同 CLI 包一併安裝**：
  ```bash
  cd openbb_platform && python dev_install.py --cli
  ```
* **安裝開發與社群/可選擴充套件依賴**：
  ```bash
  cd openbb_platform && python dev_install.py -e
  ```
* **重新建置產生的 Python 介面**（在更改 router、進入點或套件關聯後）：
  ```bash
  cd openbb_platform && python -c "import openbb; openbb.build()"
  # 或者在環境安裝好後直接使用：
  openbb-build
  ```
* **啟動 FastAPI 開發伺服器**：
  ```bash
  cd openbb_platform && uvicorn openbb_platform.core.openbb_core.api.rest_api:app --host 0.0.0.0 --port 8000 --reload
  ```

### 2. Python 測試
* **執行平台單元測試 (排除整合測試)**：
  ```bash
  pytest openbb_platform -m "not integration"
  ```
* **執行平台整合測試**：
  ```bash
  pytest openbb_platform -m integration
  ```
* **執行單個 Python 測試檔案或特定測試**：
  ```bash
  pytest openbb_platform/core/tests/app/test_extension_loader.py::test_core_objects
  ```
* **CI 風格的完整平台單元測試套件 (Nox)**：
  ```bash
  nox -f .github/scripts/noxfile.py -s unit_test_platform --python 3.12
  ```
* **CI 風格的 CLI 單元測試套件 (Nox)**：
  ```bash
  nox -f .github/scripts/noxfile.py -s unit_test_cli --python 3.12
  ```
* **CLI 特定測試**（需先安裝 `--cli`）：
  ```bash
  pytest cli/tests/test_cli.py -k <pattern>
  ```

### 3. Linter 與靜態分析
* **執行 Pre-commit 檢查所有檔案**：
  ```bash
  pre-commit run --all-files
  ```
* **Repo CI Linter 工具**：
  ```bash
  # 拼字檢查
  codespell --ignore-words=.codespell.ignore --skip=\"$(tr \"\\n\" \",\" < .codespell.skip | sed \"s/,$//\")\" --quiet-level=2
  # Black 格式化檢查
  black --diff --check <python-files>
  # MyPy 型別檢查
  mypy <python-files> --ignore-missing-imports --scripts-are-modules --check-untyped-defs
  # Pylint & Ruff 檢查
  pylint <python-files>
  ruff check <python-files>
  ```

### 4. 桌面端應用程式 (desktop)
* **安裝 Node 依賴**：
  ```bash
  cd desktop && npm ci
  ```
* **啟動 Vite 開發伺服器** (偵聽埠 1470，適合瀏覽器檢查)：
  ```bash
  cd desktop && npm run dev
  ```
* **啟動 Tauri 開發環境**：
  ```bash
  cd desktop && npm run tauri dev
  ```
* **建置桌面應用程式**：
  ```bash
  cd desktop && npm run build
  ```
* **執行前端 Linter**：
  ```bash
  cd desktop && npm run lint
  ```
* **TypeScript 類型檢查**：
  ```bash
  cd desktop && ./node_modules/.bin/tsc --noEmit
  ```
* **執行桌面端單元測試**：
  ```bash
  cd desktop && npm run test -- --watch=false
  ```
* **執行特定前端單元測試**：
  ```bash
  cd desktop && npx vitest run src/tests/components/Icon.test.tsx
  ```

---

## 高階架構設計

OpenBB 儲存庫主要分為三大區塊：
1. **`openbb_platform/`**：Python 平台與 API 執行期。
2. **`cli/`**：基於 `prompt-toolkit` 封裝 Python 平台的命令列介面。
3. **`desktop/`**：基於 Tauri + React 的桌面外殼，負責本地環境管理並封裝平台、API 與 MCP 工作流。

### 平台動態載入與擴充機制
* **擴充載入器 (`extension_loader.py`)**：位於 `openbb_platform/core/openbb_core/app/extension_loader.py`。它利用 Poetry 的 entry-point 群組在執行期動態偵測並載入已安裝的 routers、providers 與 OBBject 擴充套件。
* **提供者介面 (`provider_interface.py`)**：位於 `openbb_platform/core/openbb_core/app/provider_interface.py`。它是標準模型與提供者特定實作之間的橋樑。它在執行期合併參數與結果 Schema，讓單一命令在統一的 API 簽名下暴露多個提供者。
* **路由器與 REST API 整合 (`router.py` & `rest_api.py`)**：`router.py` 將基於模型的命令轉化為 API 路由與 Python 進入點。`rest_api.py` 則將這些動態路由組裝成完整的 FastAPI 應用程式。
* **領域與擴充模組**：
  * `openbb_platform/extensions/*`：定義用戶端的路由器 (如 `equity`, `news`, `crypto` 等)。
  * `openbb_platform/providers/*`：註冊 `Provider` 對象與對應的 fetcher 字典。
  * `openbb_platform/core/openbb_core/provider/standard_models`：存放標準模型。提供者專屬模型繼承這些基準 `QueryParams` 與 `Data` 模型，加上專屬欄位，並實作 fetchers 將原始上游數據轉換為標準化輸出。
  * `openbb_platform/obbject_extensions/*`：包含命令輸出後處理擴充功能 (如 `charting` 圖表繪製)。

---

## 關鍵開發慣例

### 1. 標準數據流向
* 所有的數據功能都必須遵循：**Standard Model (標準模型) -> Provider Fetcher (提供者獲取器) -> Router (路由器)** 的流向。
* 例如：調用 `obb.equity.price.historical()` 時，會經由 extension 路由器，透過提供者註冊表解析，最後交由對應的 provider fetcher 執行。

### 2. TET 設計模式 (Transform, Extract, Transform)
Fetcher 實作必須嚴格遵守 **TET 模式**：
1. **Transform Query (`transform_query`)**：將輸入參數轉換為 API 端點所需的格式，並回傳型別安全的 `QueryParams` 子類別。
2. **Extract Data (`extract_data` / `aextract_data`)**：攜帶憑證與查詢參數，實際對外部 API 發起請求並獲取原始字典數據。
3. **Transform Data (`transform_data`)**：將原始 API 數據對照 Pydantic Schema 轉換成標準化 `Data` 模型的列表。

### 3. 精簡的路由器
* 路由器應保持薄層設計。標準模式是使用 `@router.command(model="...")`，並回傳 `return await OBBject.from_query(Query(**locals()))`。
* 參數類型需明確指定為 `ProviderChoices`、`StandardParams` 與 `ExtraParams`。

### 4. Poetry 外掛群組與套件建置
* 平台偵測極度依賴 `pyproject.toml` 中的 Poetry plugin 進入點群組：
  * `openbb_core_extension` (路由器)
  * `openbb_provider_extension` (提供者)
  * `openbb_obbject_extension` (輸出後處理鉤子)
* 新增或移動功能後，必須更新 `pyproject.toml`，並手動執行 `python -c "import openbb; openbb.build()"` 或 `openbb-build` 重新產生靜態包。
* **禁止提交**：不要將自動產生的文件提交至 `openbb_platform/core/openbb/package/` 目錄下（除 `__init__.py` 之外），Pre-commit 會進行阻擋。

### 5. 自動化測試鷹架
* 許多 provider 單元測試與 extension 整合測試是由 `openbb_platform/providers/tests/utils` 及 `openbb_platform/extensions/tests/utils` 的腳本自動生成的。請重新執行腳本生成測試，而非手動複製。
* 整合測試使用 `@pytest.mark.integration`，通常依賴於 `~/.openbb_platform/user_settings.json` 或執行期設定的 provider 憑證。

---

## MCP 伺服器與前端調試

* **Playwright MCP**：在對 `desktop/` 進行前端 React/Vite 開發時，Playwright MCP 是最有效的偵錯工具。先在桌面端啟動開發伺服器 (`cd desktop && npm run dev`，偵聽埠 `http://127.0.0.1:1470`)，再透過 Playwright 進行 DOM 斷言、路由與迴歸測試。
* **測試邊界**：Playwright MCP 無法處理 Tauri 專屬的原生效果（如系統托盤、原生對話框或 Rust 側的系統文件交互）。對於這些部分，請使用 Vitest 與 Tauri 專屬測試流程。
