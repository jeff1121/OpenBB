---
name: configure_mcp_server
description: 本指南涵蓋 `openbb-mcp-server` 的安裝、設定、驗證、工具探索、提示詞管理與用戶端整合。
---

# 設定並建置 OpenBB MCP 伺服器

本指南涵蓋 `openbb-mcp-server` 的安裝、設定、驗證、工具探索、
提示詞管理與用戶端整合。

---

## 安裝

```
pip install openbb-mcp-server
```

這會安裝 `openbb-mcp` CLI 命令。若要將預設 OpenBB
擴充套件納入工具，也請安裝它們：

```
pip install openbb
```

或安裝個別擴充套件：

```
pip install openbb-equity openbb-economy
```

---

## 啟動伺服器

### 預設值（所有已安裝的 OpenBB 擴充套件）

```
openbb-mcp
```

預設值：`--host 127.0.0.1 --port 8001 --transport streamable-http`

### 使用自訂 FastAPI 應用程式

```
# 使用預設實例名稱 "app" 的檔案路徑
openbb-mcp --app ./my_app.py

# 明確指定實例名稱
openbb-mcp --app ./my_app.py --name my_app

# 模組 import 語法
openbb-mcp --app my_package.app:my_app

# Factory function 模式
openbb-mcp --app ./my_app.py:create_app --factory
```

### 傳輸選項

| 傳輸方式 | 旗標 | 使用情境 |
|---|---|---|
| `streamable-http` | `--transport streamable-http` | 預設值。以 HTTP 為基礎，可搭配 Cursor、VS Code 使用 |
| `sse` | `--transport sse` | 舊版 Server-Sent Events。Cline 需要此選項 |
| `stdio` | `--transport stdio` | Standard I/O。Claude Desktop 使用此選項 |

---

## CLI 引數

| 引數 | 說明 | 預設值 |
|---|---|---|
| `--app <path>` | FastAPI 應用程式檔案路徑或 `module:instance` | OpenBB 預設應用程式 |
| `--name <name>` | FastAPI 實例或 factory function 的名稱 | `app` |
| `--factory` | 將 `--name` 視為 factory function | `false` |
| `--host <host>` | 伺服器 host | `127.0.0.1` |
| `--port <port>` | 伺服器 port | `8001` |
| `--transport <type>` | `streamable-http`、`sse` 或 `stdio` | `streamable-http` |
| `--default-categories <csv>` | 以逗號分隔的預設啟用工具分類 | `all` |
| `--allowed-categories <csv>` | 將可用分類限制為此清單 | 所有分類 |
| `--tool-discovery` | 啟用執行期間的工具啟用/停用 | 探索已停用 |
| `--system-prompt <path>` | `.txt` system prompt 檔案路徑 | None |
| `--server-prompts <path>` | `.json` server prompts 檔案路徑 | None |

任何額外的 `--key value` 組合都會作為 config 轉送給 Uvicorn。

---

## 設定優先順序

設定會依以下順序解析（最高優先權在前）：

1. **CLI 引數** — 命令列旗標
2. **環境變數** — 以 `OPENBB_MCP_` 為前綴
3. **設定檔** — `~/.openbb_platform/mcp_settings.json`
4. **預設值** — 內建 MCPSettings 預設值

### 設定檔範例

建立 `~/.openbb_platform/mcp_settings.json`：

```json
{
    "name": "我的 MCP 伺服器",
    "default_tool_categories": ["equity", "economy"],
    "enable_tool_discovery": false,
    "describe_responses": false,
    "system_prompt_file": "/path/to/system_prompt.txt",
    "server_prompts_file": "/path/to/prompts.json"
}
```

### 環境變數

所有設定都會對應到以 `OPENBB_MCP_` 為前綴的環境變數：

```
OPENBB_MCP_NAME="我的 MCP 伺服器"
OPENBB_MCP_DEFAULT_TOOL_CATEGORIES="equity,economy,crypto"
OPENBB_MCP_ENABLE_TOOL_DISCOVERY=true
OPENBB_MCP_SYSTEM_PROMPT_FILE="/path/to/prompt.txt"
OPENBB_MCP_SERVER_PROMPTS_FILE="/path/to/prompts.json"
```

---

## 設定參考

### 伺服器識別

| 設定 | 環境變數 | 型別 | 預設值 |
|---|---|---|---|
| `name` | `OPENBB_MCP_NAME` | `str` | `"OpenBB MCP"` |
| `description` | `OPENBB_MCP_DESCRIPTION` | `str` | 自動產生 |
| `version` | `OPENBB_MCP_VERSION` | `str \| None` | `None` |

### 工具設定

| 設定 | 環境變數 | 型別 | 預設值 |
|---|---|---|---|
| `default_tool_categories` | `OPENBB_MCP_DEFAULT_TOOL_CATEGORIES` | `list[str]` | `["all"]` |
| `allowed_tool_categories` | `OPENBB_MCP_ALLOWED_TOOL_CATEGORIES` | `list[str] \| None` | `None` |
| `enable_tool_discovery` | `OPENBB_MCP_ENABLE_TOOL_DISCOVERY` | `bool` | `false` |
| `list_page_size` | `OPENBB_MCP_LIST_PAGE_SIZE` | `int \| None` | `None` |
| `describe_responses` | `OPENBB_MCP_DESCRIBE_RESPONSES` | `bool` | `false` |
| `api_prefix` | `OPENBB_MCP_API_PREFIX` | `str \| None` | `None` |

### 提示詞設定

| 設定 | 環境變數 | 型別 | 預設值 |
|---|---|---|---|
| `system_prompt_file` | `OPENBB_MCP_SYSTEM_PROMPT_FILE` | `str \| None` | `None` |
| `server_prompts_file` | `OPENBB_MCP_SERVER_PROMPTS_FILE` | `str \| None` | `None` |
| `default_skills_dir` | `OPENBB_MCP_DEFAULT_SKILLS_DIR` | `str \| None` | 內建 skills 目錄 |
| `skills_reload` | `OPENBB_MCP_SKILLS_RELOAD` | `bool` | `false` |
| `skills_providers` | `OPENBB_MCP_SKILLS_PROVIDERS` | `list[str] \| None` | `None` |

### HTTP 傳輸

| 設定 | 環境變數 | 型別 | 預設值 |
|---|---|---|---|
| `uvicorn_config` | `OPENBB_MCP_UVICORN_CONFIG` | `dict` | `{"host": "127.0.0.1", "port": "8001"}` |

### 重複項目處理

| 設定 | 環境變數 | 型別 | 預設值 |
|---|---|---|---|
| `on_duplicate_tools` | `OPENBB_MCP_ON_DUPLICATE_TOOLS` | `str \| None` | `None` |
| `on_duplicate_resources` | `OPENBB_MCP_ON_DUPLICATE_RESOURCES` | `str \| None` | `None` |
| `on_duplicate_prompts` | `OPENBB_MCP_ON_DUPLICATE_PROMPTS` | `str \| None` | `None` |

選項：`"warn"`、`"error"`、`"replace"`、`"ignore"`

### 模組排除

| 設定 | 環境變數 | 型別 | 預設值 |
|---|---|---|---|
| `module_exclusion_map` | `OPENBB_MCP_MODULE_EXCLUSION_MAP` | `dict \| None` | 自動偵測 |

預設情況下，無法匯入 Python 模組的分類會被排除
（例如 `econometrics`、`quantitative`、`technical`、`coverage`）。

---

## 驗證

可使用三種驗證模式。

### 伺服器端驗證

使用 Bearer token 保護傳入的 MCP 請求：

```json
{
    "server_auth": ["username", "password"]
}
```

或透過環境變數：

```
OPENBB_MCP_SERVER_AUTH='["username", "password"]'
```

用戶端必須在請求中包含 `Authorization: Bearer <base64(username:password)>`。
Token 是經過 base64 編碼的 `username:password`。

### 用戶端驗證

驗證送往下游服務的對外請求：

```json
{
    "client_auth": ["api_user", "api_key"]
}
```

或透過環境變數：

```
OPENBB_MCP_CLIENT_AUTH='["api_user", "api_key"]'
```

這會將 `auth=(user, pass)` 傳給用於內部請求的 httpx 用戶端。

### 程式化驗證

將伺服器作為函式庫使用時，將自訂 `AuthProvider` 傳給
`create_mcp_server()`：

```python
from openbb_mcp_server.app.app import create_mcp_server
from openbb_mcp_server.models.settings import MCPSettings

settings = MCPSettings()
mcp = create_mcp_server(settings, my_fastapi_app, auth=my_auth_provider)
```

---

## 工具探索

當 `enable_tool_discovery` 為 `true` 時，agent 可使用五個管理工具：

| 工具 | 說明 |
|---|---|
| `available_categories` | 列出所有工具分類及工具數量 |
| `available_tools` | 列出特定分類中的工具，包含啟用狀態與簡短描述 |
| `activate_tools` | 依名稱啟用本工作階段的工具 |
| `deactivate_tools` | 依名稱停用本工作階段的工具 |
| `activate_category` | 批次啟用本工作階段中某個分類（或子分類）的所有工具 |

所有可見性變更都是 **每個工作階段獨立** — 每個已連線用戶端都會維護自己的
啟用工具集，因此伺服器可安全用於多使用者部署。

### 控制啟動時的啟用工具

使用 `default_tool_categories` 控制哪些分類一開始為啟用狀態：

```
# 啟動時只啟用 equity 與 economy tools
openbb-mcp --default-categories equity,economy

# 啟用所有 admin 工具（用於探索）
openbb-mcp --default-categories admin
```

之後 agent 可視需要使用 `available_categories` 與 `activate_tools`
（或用 `activate_category` 批次啟用）來動態啟用額外工具。

### 限制可用分類

使用 `allowed_tool_categories` 永久隱藏分類：

```
openbb-mcp --allowed-categories equity,economy,crypto
```

不在此清單中的分類即使透過探索工具也無法啟用。

### 啟用探索

```
openbb-mcp --tool-discovery
```

`default_tool_categories` 中的所有工具都會成為啟用狀態；若未啟用探索，
管理工具不會被註冊。

---

## 工具命名慣例

工具會根據移除 API prefix 後的 API route 路徑命名：

| Route 路徑 | 工具名稱 |
|---|---|
| `/equity/price/historical` | `equity_price_historical` |
| `/economy/cpi` | `economy_cpi` |
| `/my_app/process` | `my_app_process` |

第一個路徑區段是 **分類**，最後一個區段是 **工具
名稱**，中間的區段組成 **子分類**。沒有
子分類時，預設為 `"general"`。

---

## 提示詞系統

伺服器支援四層提示詞，全部都可透過
`list_prompts` 與 `execute_prompt` 工具存取。

### 1. 系統提示詞（tag：`system`）

啟動時載入一次的純文字檔。也會以 `resource://system_prompt`
公開。

```
openbb-mcp --system-prompt /path/to/system_prompt.txt
```

### 2. 伺服器提示詞 JSON（tag：`server`）

定義可重用提示詞並可選擇性附帶 arguments 的 JSON 檔案：

```json
[
    {
        "name": "analyze_stock",
        "description": "分析股票的架構。",
        "content": "分析 {symbol}，並聚焦於 {aspect}。",
        "arguments": [
            {
                "name": "symbol",
                "type": "str",
                "description": "股票代號"
            },
            {
                "name": "aspect",
                "type": "str",
                "default": "fundamentals",
                "description": "分析重點領域"
            }
        ],
        "tags": ["analysis"]
    }
]
```

Argument 型別：`str`、`int`、`float`、`bool`、`list`、`dict`、`any`

含有 `default` 值的 arguments 為選填；未提供 `default` 的則為必填。

```
openbb-mcp --server-prompts /path/to/prompts.json
```

### 3. Inline 提示詞（tag：route-specific）

透過 `openapi_extra` 直接在 FastAPI routes 上定義提示詞：

```python
@router.command(
    methods=["GET"],
    openapi_extra={
        "mcp_config": {
            "prompts": [
                {
                    "name": "usage_guide",
                    "description": "如何使用此 endpoint。",
                    "content": "若要分析 {symbol}，請以...呼叫此 endpoint"
                }
            ]
        }
    },
)
async def my_endpoint(symbol: str) -> OBBject:
    ...
```

### 4. 內建 Skills（Resources）

Skill 指南會公開為 MCP resources，可透過 `list_resources()` 探索。
每個 skill 都可在 `skill://<name>/SKILL.md` URI 存取。

```
# 探索可用 skills
list_resources()  # 回傳 skill://develop_extension/SKILL.md 等

# 讀取特定 skill
read_resource("skill://configure_mcp_server/SKILL.md")
```

自訂 skills 目錄：

```
OPENBB_MCP_DEFAULT_SKILLS_DIR=/path/to/my/skills
```

設為空字串可停用內建 skills：

```
OPENBB_MCP_DEFAULT_SKILLS_DIR=""
```

### Skills Reload

啟用 skill files 的 hot-reload，無須重新啟動伺服器（適合開發期間使用）：

```json
{
    "skills_reload": true
}
```

或透過環境變數：

```
OPENBB_MCP_SKILLS_RELOAD=true
```

### Vendor Skills Providers

從知名 vendor 位置載入 skill directories（例如 `~/.claude/skills/`）。
這會設定 `mcp_settings.json` 中的 `skills_providers` 清單：

```json
{
    "skills_providers": ["claude", "cursor"]
}
```

或透過環境變數（以逗號分隔）：

```
OPENBB_MCP_SKILLS_PROVIDERS="claude,cursor"
```

支援的 provider names：

| 名稱 | 預設目錄 |
|---|---|
| `claude` | `~/.claude/skills/` |
| `cursor` | `~/.cursor/skills/` |
| `vscode` / `copilot` | `~/.copilot/skills/` |
| `codex` | `/etc/codex/skills/` + `~/.codex/skills/` |
| `gemini` | `~/.gemini/skills/` |
| `goose` | `~/.config/agents/skills/` |
| `opencode` | `~/.config/opencode/skills/` |

---

## Inline MCP Configuration（MCPConfigModel）

透過 `openapi_extra` 控制個別路由在 MCP 伺服器中的呈現方式：

```python
@app.get(
    "/my_endpoint",
    openapi_extra={
        "mcp_config": {
            "expose": True,
            "mcp_type": "tool",
            "methods": ["GET"],
            "exclude_args": ["internal_param"],
            "prompts": []
        }
    },
)
```

### MCPConfigModel 欄位

| 欄位 | 型別 | 預設值 | 說明 |
|---|---|---|---|
| `expose` | `bool \| None` | `None` | 設為 `false` 可從 MCP 隱藏路由 |
| `mcp_type` | `str \| None` | `None` | `"tool"`、`"resource"` 或 `"resource_template"` |
| `methods` | `list[str] \| None` | `None` | 要公開的 HTTP 方法 |
| `exclude_args` | `list[str] \| None` | `None` | 要從工具 schema 隱藏的 arguments |
| `prompts` | `list[dict]` | `[]` | Inline prompt 定義 |

---

## 用戶端設定範例

### Claude Desktop（stdio 傳輸）

在 Claude Desktop 的 MCP 設定檔中：

```json
{
    "mcpServers": {
        "openbb-mcp": {
            "command": "uvx",
            "args": [
                "--from", "openbb-mcp-server",
                "--with", "openbb",
                "openbb-mcp",
                "--transport", "stdio"
            ]
        }
    }
}
```

若使用自訂應用程式：

```json
{
    "mcpServers": {
        "openbb-mcp": {
            "command": "uvx",
            "args": [
                "--from", "openbb-mcp-server",
                "openbb-mcp",
                "--app", "./my_app.py",
                "--transport", "stdio"
            ]
        }
    }
}
```

### Cursor（streamable-http）

1. 啟動伺服器：`openbb-mcp`
2. 在 Cursor 的 `mcp.json` 中：

```json
{
    "mcpServers": {
        "openbb-mcp": {
            "url": "http://localhost:8001/mcp/"
        }
    }
}
```

### VS Code（streamable-http）

1. 在 VS Code 設定中啟用 MCP（Settings → Chat → MCP）
2. 啟動伺服器：`openbb-mcp`
3. 開啟 Command Palette → "MCP: Add Server" → HTTP
4. 輸入 URL：`http://127.0.0.1:8001/mcp`

若使用 Cline VS Code extension，請使用 `--transport sse`：

```
openbb-mcp --transport sse
```

### 使用驗證

以啟用伺服器驗證的方式啟動：

```
openbb-mcp --host 0.0.0.0 --port 8001
```

搭配 `mcp_settings.json`：

```json
{
    "server_auth": ["admin", "secretpass"]
}
```

用戶端會在設定中包含 Bearer token：

```json
{
    "mcpServers": {
        "openbb-mcp": {
            "url": "http://localhost:8001/mcp/",
            "headers": {
                "Authorization": "Bearer YWRtaW46c2VjcmV0cGFzcw=="
            }
        }
    }
}
```

Token 值為 `base64("admin:secretpass")`。

---

## 進階設定

### 環境變數中的清單與字典

清單可以用逗號分隔字串傳入：

```
OPENBB_MCP_DEFAULT_TOOL_CATEGORIES="equity,economy,crypto"
OPENBB_MCP_ALLOWED_TOOL_CATEGORIES="equity,economy"
```

字典與 tuples 必須是 JSON 編碼字串：

```
OPENBB_MCP_SERVER_AUTH='["user", "pass"]'
OPENBB_MCP_UVICORN_CONFIG='{"host": "0.0.0.0", "port": 8001, "log_level": "info"}'
OPENBB_MCP_HTTPX_CLIENT_KWARGS='{"timeout": 30, "verify": false}'
```

### SSL / HTTPS

透過 Uvicorn 傳入 SSL 設定：

```
openbb-mcp --ssl-keyfile /path/to/key.pem --ssl-certfile /path/to/cert.pem
```

或在設定檔中設定：

```json
{
    "uvicorn_config": {
        "host": "0.0.0.0",
        "port": 443,
        "ssl_keyfile": "/path/to/key.pem",
        "ssl_certfile": "/path/to/cert.pem"
    }
}
```

### 作為函式庫使用

```python
import asyncio
from fastapi import FastAPI
from openbb_mcp_server.app.app import create_mcp_server
from openbb_mcp_server.models.settings import MCPSettings

app = FastAPI()

@app.get("/hello")
async def hello():
    return "Hello World"

settings = MCPSettings(
    name="我的自訂 MCP",
    default_tool_categories=["all"],
    enable_tool_discovery=False,
)

mcp = create_mcp_server(settings, app)
mcp.run(transport="streamable-http")
```

---

## 工作流程摘要

若要設定並部署 OpenBB MCP 伺服器：

1. **安裝**：`pip install openbb-mcp-server`（以及任何需要的 OpenBB 擴充套件）。
2. **設定**：使用所需設定建立 `~/.openbb_platform/mcp_settings.json`。
3. **新增提示詞**：撰寫 system prompt 檔案和/或 server prompts JSON。
4. **啟動**：使用適當的 CLI 旗標執行 `openbb-mcp`。
5. **連線**：使用伺服器 URL 或 stdio 命令設定 MCP 用戶端（Claude Desktop、Cursor、VS Code）。
6. **探索**：使用 `available_categories`、`activate_tools` 與 `activate_category` 尋找並啟用工具。
7. **迭代**：調整設定、將 inline `mcp_config` 加入路由、加入 skill files。
