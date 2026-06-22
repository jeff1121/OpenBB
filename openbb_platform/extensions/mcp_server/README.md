# OpenBB MCP Server

這個擴充讓 LLM agent 可以透過 MCP 協定，與 OpenBB Platform 的 REST API 端點互動。

伺服器提供探索工具，讓 agent 可以瀏覽可用分類，並動態啟用真正需要的工具。
這能讓初始工具清單維持精簡，避免 token 膨脹，同時又保有隨需使用整個平台能力的彈性。

工具可見性的變更是 **per-session** 的：每個連線中的 client 都有自己的啟用工具集合。
多個 agent 可以同時連線，並各自獨立啟用不同工具，而不會互相干擾。

## 安裝與使用

```bash
pip install openbb-mcp-server
```

使用預設設定啟動 OpenBB MCP Server：

```bash
openbb-mcp
```

或使用 `uvx` 指令：

```bash
uvx --from openbb-mcp-server --with openbb openbb-mcp
```

### Docker 快速啟動

若你想要快速提供給 LLM client 以 HTTP 方式連線，可直接使用這個擴充目錄中的容器設定。

映像預設會：

- 安裝 `openbb`，提供股票分析常用的 extension/provider。
- 安裝目前 repository 中的 `openbb-mcp-server` 程式碼。
- 以 `streamable-http` 啟動在 `0.0.0.0:8001`。
- 預設只啟用 `equity`、`etf`、`index`、`news` 四個股票分析常用分類。

**建置映像：**

```bash
docker build \
  -t openbb-mcp-stocks \
  -f openbb_platform/extensions/mcp_server/Dockerfile \
  openbb_platform/extensions/mcp_server
```

**直接啟動：**

```bash
docker run --rm \
  -p 8001:8001 \
  -v ~/.openbb_platform:/home/openbb/.openbb_platform \
  openbb-mcp-stocks
```

啟動後，多數支援 MCP over HTTP 的 client 都可以連到：

```text
http://localhost:8001/mcp
```

**使用 Compose：**

```bash
cd openbb_platform/extensions/mcp_server
docker compose up --build
```

`compose.yaml` 預設使用 named volume 保存 `/home/openbb/.openbb_platform`。
若你要沿用本機既有的 OpenBB 憑證與使用者設定，可將 volume 改成 bind mount，例如：

```yaml
volumes:
  - ${HOME}/.openbb_platform:/home/openbb/.openbb_platform
```

**常見客製項目：**

```bash
docker run --rm \
  -p 8001:8001 \
  -e OPENBB_MCP_ALLOWED_TOOL_CATEGORIES="equity,news" \
  -e OPENBB_MCP_DEFAULT_TOOL_CATEGORIES="equity,news" \
  -e OPENBB_MCP_ENABLE_TOOL_DISCOVERY=true \
  -v ~/.openbb_platform:/home/openbb/.openbb_platform \
  openbb-mcp-stocks
```

> **注意：** 若你要使用需要 API key 的資料來源，請確定容器中的 `/home/openbb/.openbb_platform/user_settings.json` 已包含對應設定。

### 命令列選項

輸入 `openbb-mcp --help` 可在命令列中查看說明文字。

```sh
--help
    Show this help message and exit.

--app <app_path>
    The path to the FastAPI app instance. This can be in the format
    'module.path:app_instance' or a file path 'path/to/app.py'.
    If not provided, the server will run with the default built-in app.

--name <name>
    The name of the FastAPI app instance or factory function in the app file.
    Defaults to 'app'.

--factory
    If set, the app is treated as a factory function that will be called
    to create the FastAPI app instance.

--host <host>
    The host to bind the server to. Defaults to '127.0.0.1'.
    This is a uvicorn argument.

--port <port>
    The port to bind the server to. Defaults to 8001.
    This is a uvicorn argument.

--transport <transport>
    The transport mechanism to use for the MCP server.
    Defaults to 'streamable-http'.

--allowed-categories <categories>
    A comma-separated list of tool categories to allow.
    If not provided, all categories are allowed.

--default-categories <categories>
    A comma-separated list of tool categories to be enabled by default.
    Defaults to 'all'.

--tool-discovery
    If set, tool discovery will be enabled.

--system-prompt <path>
    Path to a TXT file with the system prompt.

--server-prompts <path>
    Path to a JSON file with a list of server prompts.
```

#### 其他所有參數都會傳給 `uvicorn.run`。


## 設定方式

伺服器支援多種設定方式，優先順序如下：

1. **Command Line Arguments**：最高優先權，會覆蓋其他所有來源。
2. **Environment Variables**：每個設定都能透過環境變數控制，並覆蓋設定檔內容。
3. **Configuration File**：位於 `~/.openbb_platform/mcp_settings.json` 的 JSON 檔提供基礎設定。
   - 若設定檔不存在，系統會以預設值自動建立一份。

> **注意：** 某些資料提供者需要你在 `~/.openbb_platform/user_settings.json` 中設定 API key。

### 驗證

MCP 伺服器支援 client 端與 server 端驗證，以保護你的端點。

#### Server 端驗證

Server 端驗證要求傳入請求提供憑證。這透過 `server_auth` 設定控制，接受 `(username, password)` tuple。

啟用 `server_auth` 後，client 必須在 `Authorization` header 中帶入 `Bearer` token。
此 token 應為 `username:password` 的 Base64 編碼字串。

**範例：環境變數**

```env
OPENBB_MCP_SERVER_AUTH='["myuser", "mypass"]'
```

**範例：`mcp_settings.json`**

```json
{
  "server_auth": ["myuser", "mypass"]
}
```

#### Client 端驗證

Client 端驗證會讓 MCP 伺服器在對下游服務發送請求時帶上憑證。
當伺服器需要與其他服務進行驗證時，這會很有用。

**範例：環境變數**

```env
OPENBB_MCP_CLIENT_AUTH='["client_user", "client_pass"]'
```

**範例：`mcp_settings.json`**

```json
{
  "client_auth": ["client_user", "client_pass"]
}
```

#### 程式化驗證

在較進階的使用情境中，你可以透過 `auth` 參數，把預先設定好的驗證物件直接傳給 `create_mcp_server`。
這讓你可以自行實作客製驗證邏輯，或接入第三方驗證提供者。

```python
from fastmcp.server.auth.providers import BearerProvider
from openbb_mcp_server.app import create_mcp_server

# 建立自訂 auth provider
custom_auth = BearerProvider(...)

# 傳給 server
mcp_server = create_mcp_server(settings, fastapi_app, auth=custom_auth)
```

### 進階設定：List 與 Dictionary

對於接受 list 或 dictionary 的設定，你可以在命令列參數與環境變數中使用兩種彈性格式。

#### 1. 逗號分隔字串

這是定義 list 與簡單 dictionary 的一種直觀且易讀的方式。

- **Lists**：提供逗號分隔的字串。
  - 範例：`equity,news,crypto`
- **Dictionaries**：提供逗號分隔的 `key:value` 字串。
  - 範例：`host:0.0.0.0,port:9000`

#### 2. JSON 編碼字串

若資料結構較複雜，或你想確保型別處理更精準（例如數字與布林值），可以使用 JSON 編碼字串。

- **Lists**：標準 JSON array。
  - 範例：`'["equity", "news", "crypto"]'`
- **Dictionaries**：標準 JSON object。
  - 範例：`'{"host": "0.0.0.0", "port": 9000}'`

**引號注意事項**：在命令列中傳入 JSON 編碼字串時，強烈建議用 **單引號（`'`）** 包住整段字串。
這可以避免 shell 解讀 JSON 內部的雙引號（`"`），進而造成解析錯誤。

#### 實務範例

以下是這些格式的實際用法：

**命令列參數：**

```sh
# 使用逗號分隔的 list
openbb-mcp --default-categories equity,news

# 使用 JSON 編碼字串的 list（注意外層單引號）
openbb-mcp --default-categories '["equity", "news"]'

# 使用逗號分隔 key:value 的 dictionary
openbb-mcp --uvicorn-config "host:0.0.0.0,port:9000"

# 使用 JSON 編碼字串的 dictionary（注意外層單引號）
openbb-mcp --uvicorn-config '{"host": "0.0.0.0", "port": 9000, "env_file": "./path_to/.env"}'
```

**環境變數（於 `.env` 檔中）：**

```env
# 使用逗號分隔的 list
OPENBB_MCP_DEFAULT_TOOL_CATEGORIES="equity,news"

# 使用 JSON 編碼字串的 list
OPENBB_MCP_DEFAULT_TOOL_CATEGORIES='["equity", "news"]'

# 使用逗號分隔 key:value 的 dictionary
OPENBB_MCP_UVICORN_CONFIG="host:0.0.0.0,port:9000"

# 使用 JSON 編碼字串的 dictionary
OPENBB_MCP_UVICORN_CONFIG='{"host": "0.0.0.0", "port": 9000, "env_file": "./path_to/.env"}'
```

## 設定參考

`MCPSettings` 模型中的所有設定，都可以透過 `mcp_settings.json` 或環境變數進行配置。

| Setting | Environment Variable | Type | Default | Description |
|---|---|---|---|---|
| `api_prefix` | `OPENBB_MCP_API_PREFIX` | string | `None` | 覆蓋來自 SystemService 的 API prefix。 |
| `name` | `OPENBB_MCP_NAME` | string | `"OpenBB MCP"` | 伺服器名稱。 |
| `description` | `OPENBB_MCP_DESCRIPTION` | string | | 伺服器描述。 |
| `version` | `OPENBB_MCP_VERSION` | string | `None` | 伺服器版本。 |
| `instructions` | `OPENBB_MCP_INSTRUCTIONS` | string | `None` | 在 MCP `initialize` 握手期間傳給 agent 的伺服器說明；若未設定，會自動由 system prompt 補入。 |
| `default_tool_categories` | `OPENBB_MCP_DEFAULT_TOOL_CATEGORIES` | list[string] | `["all"]` | 啟動時預設啟用的工具分類。 |
| `allowed_tool_categories` | `OPENBB_MCP_ALLOWED_TOOL_CATEGORIES` | list[string] | `None` | 將可用工具限制在這些分類內。 |
| `enable_tool_discovery` | `OPENBB_MCP_ENABLE_TOOL_DISCOVERY` | boolean | `False` | 啟用 per-session 工具探索（瀏覽/啟用/停用用的管理工具）。 |
| `list_page_size` | `OPENBB_MCP_LIST_PAGE_SIZE` | integer | `None` | MCP list 回應每頁的最大項目數；`None` 代表停用分頁。 |
| `describe_responses` | `OPENBB_MCP_DESCRIBE_RESPONSES` | boolean | `False` | 在工具描述中包含回應型別。 |
| `system_prompt_file` | `OPENBB_MCP_SYSTEM_PROMPT_FILE` | string | `None` | system prompt 文字檔路徑。 |
| `server_prompts_file` | `OPENBB_MCP_SERVER_PROMPTS_FILE` | string | `None` | 包含 server prompt 定義清單的 JSON 檔案路徑。 |
| `default_skills_dir` | `OPENBB_MCP_DEFAULT_SKILLS_DIR` | string | *(bundled skills dir)* | 內建 skill 檔案所在目錄；設為 `null` 可停用。 |
| `skills_reload` | `OPENBB_MCP_SKILLS_RELOAD` | boolean | `False` | 每次讀取時重新載入 skill 檔案（適合開發時使用）。 |
| `skills_providers` | `OPENBB_MCP_SKILLS_PROVIDERS` | list[string] | `None` | 要載入的 vendor skill provider 短名稱（例如 `["claude", "cursor"]`）。 |
| `cache_expiration_seconds` | `OPENBB_MCP_CACHE_EXPIRATION_SECONDS` | float | `None` | 快取過期秒數；設為 `0` 可停用。 |
| `on_duplicate_tools` | `OPENBB_MCP_ON_DUPLICATE_TOOLS` | string | `None` | 工具重複註冊時的處理方式（`warn`、`error`、`replace`、`ignore`）。 |
| `on_duplicate_resources` | `OPENBB_MCP_ON_DUPLICATE_RESOURCES` | string | `None` | resource 重複時的處理方式。 |
| `on_duplicate_prompts` | `OPENBB_MCP_ON_DUPLICATE_PROMPTS` | string | `None` | prompt 重複時的處理方式。 |
| `resource_prefix_format` | `OPENBB_MCP_RESOURCE_PREFIX_FORMAT` | string | `None` | resource URI prefix 的格式（`protocol` 或 `path`）。 |
| `mask_error_details` | `OPENBB_MCP_MASK_ERROR_DETAILS` | boolean | `None` | 隱藏使用者函式回傳的錯誤細節。 |
| `dependencies` | `OPENBB_MCP_DEPENDENCIES` | list[string] | `None` | 要安裝的相依套件清單。 |
| `module_exclusion_map` | `OPENBB_MCP_MODULE_EXCLUSION_MAP` | dict[str, str] | `None` | API tag 與 Python 模組名稱的排除對應表。 |
| `uvicorn_config` | `OPENBB_MCP_UVICORN_CONFIG` | dict | `{"host": "127.0.0.1", "port": "8001"}` | Uvicorn 伺服器設定。 |
| `httpx_client_kwargs` | `OPENBB_MCP_HTTPX_CLIENT_KWARGS` | dict | `{}` | 非同步 httpx client 設定。 |
| `client_auth` | `OPENBB_MCP_CLIENT_AUTH` | tuple[string, string] | `None` | client 端基本驗證的 `(username, password)`，會傳遞給 HTTPX。 |
| `server_auth` | `OPENBB_MCP_SERVER_AUTH` | tuple[string, string] | `None` | server 端基本驗證的 `(username, password)`。 |

> **注意：** 執行期參數鍵名中的 `-` 與 `_` 一般可互換；巢狀 uvicorn 參數建議使用 `_`。

## 工具分類

伺服器會根據納入的 API Router（路徑）將 OpenBB 工具整理成不同分類。
分類會依已安裝的擴充而定，但通常會對應到 API prefix 後的第一段路徑。

例如：

- **`equity`** - 股票資料、基本面、價格歷史與估值預估
- **`crypto`** - 加密貨幣資料與分析
- **`economy`** - 經濟指標、GDP、就業資料
- **`news`** - 多種來源的財經新聞
- **`fixedincome`** - 債券、利率與公債資料
- **`derivatives`** - 選擇權與期貨資料
- **`etf`** - ETF 資訊與持倉
- **`currency`** - 外匯資料
- **`commodity`** - 商品價格與資料
- **`index`** - 市場指數資料
- **`regulators`** - SEC、CFTC 等監管資料

每個分類下還包含子分類，用來聚合相關功能（例如 `equity_price`、`equity_fundamental` 等）。

### 根工具

另外還有一組工具會被標記為 `admin` 或 `prompt`。

- **available_categories**：列出所有工具分類、子分類名稱與工具數量。

- **available_tools**：列出特定分類（以及可選子分類）中的工具。
  - `category`：要列出的工具分類。
  - `subcategory`：可選子分類。若要列出直接掛在分類底下的工具，使用 `general`。
  - 即使工具目前未啟用，仍會顯示簡短描述，方便探索。

- **activate_tools**：在目前 session 中，依名稱啟用一個或多個工具。
  - `tool_names`：要啟用的工具名稱清單。

- **deactivate_tools**：在目前 session 中，依名稱停用一個或多個工具。
  - `tool_names`：要停用的工具名稱清單。

- **activate_category**：一次啟用某個分類（或子分類）中的所有工具。
  - `category`：分類名稱。
  - `subcategory`：可選子分類，用來縮小啟用範圍。

- **list_prompts**：列出伺服器中所有可用的 prompts。

- **execute_prompt**：執行某個 prompt，並可帶入參數。
  - `prompt_name`：要執行的 prompt 名稱。
  - `arguments`：prompt 的 `argument:value` 字典。

## 工具探索

啟用 `enable_tool_discovery` 後，伺服器會註冊一小組管理工具，讓 agent 可以循序探索並啟用自己需要的工具：

1. **Browse** — `available_categories` 會回傳分類樹與工具數量。
2. **Inspect** — `available_tools` 會列出某分類中的所有工具、其啟用/停用狀態，以及簡短描述。
3. **Activate** — `activate_tools` 或 `activate_category` 可為目前 session 啟用特定工具（或整個分類）。
4. **Deactivate** — `deactivate_tools` 可在不再需要時移除工具。

所有可見性變更都是 **per-session** 的——每個 client 都維護自己的啟用工具集合，因此可安全用於多使用者部署。

若要徹底利用最小化啟動工具集，可設定 `--default-categories admin`，讓連線時只有探索工具處於啟用狀態。

若你希望提供探索能力，可使用 `--tool-discovery` 啟用。
否則伺服器會以固定工具集模式運行，而你可以透過 `allowed_tool_categories` 與 `default_tool_categories` 控制可用工具。

## System Prompt

system prompt 檔案可以在初始化時傳入，也可以定義在設定檔或環境變數中。
它必須是一個合法的 `.txt` 檔案路徑，可以是相對路徑或絕對路徑。

system prompt 會以 `resource://system_prompt` 這個 resource 對外提供，也能透過 `list_prompts` 工具被探索到。

client 不會自動使用 system prompt；你應該在 onboarding 與操作指引中明確要求它們使用。

## Skills

伺服器內建一組 **skill guides**，也就是 Markdown 文件，用來教導 agent 如何用 OpenBB Platform 完成複雜的多步驟任務。
這些 skills 會以 MCP resources 形式提供，並可透過 `list_resources()` 被探索到。

每個 skill 都能透過 `skill://<name>/SKILL.md` 這種 URI 取得。

### 內建 Skills

| Skill | URI | Description |
|---|---|---|
| `develop_extension` | `skill://develop_extension/SKILL.md` | 建立 OpenBB Platform 擴充的逐步指南。 |
| `build_workspace_app` | `skill://build_workspace_app/SKILL.md` | 建立與執行 OpenBB Workspace 應用程式的指南。 |
| `configure_mcp_server` | `skill://configure_mcp_server/SKILL.md` | 設定與客製化 OpenBB MCP Server 的參考文件。 |
| `work_with_server` | `skill://work_with_server/SKILL.md` | 以 agent 身分操作 OpenBB MCP Server 的實務指南。 |

只要有任一 skill 被載入，且未設定 `system_prompt_file`，伺服器就會自動加入一段簡短的預設 system prompt，引導 agent 去探索可用的 skills。

### Skill 設定

| Setting | Description |
|---|---|
| `default_skills_dir` | 內建 skills 目錄路徑。設為 `null` 或空字串可停用內建 skills 載入。 |
| `skills_reload` | 設為 `true` 時，每次讀取都會從磁碟重新載入 skill 檔案，適合撰寫或反覆調整 skill 內容時使用。 |
| `skills_providers` | vendor skill provider 短名稱清單。支援值：`claude`、`cursor`、`vscode`、`copilot`、`codex`、`gemini`、`goose`、`opencode`。 |

**範例——停用內建 skills：**

```json
{
  "default_skills_dir": null
}
```

**範例——載入 vendor skill providers：**

```json
{
  "skills_providers": ["claude", "cursor"]
}
```

**範例——在開發時啟用 skill reload：**

```env
OPENBB_MCP_SKILLS_RELOAD=true
```

## Server Prompts

server prompt 檔案可以在初始化時傳入，也可以定義在設定檔或環境變數中。
它必須是一個合法的 `.json` 檔案路徑，內容為 prompt 定義的清單。

JSON 檔中的每一筆資料都是一個 dictionary，包含以下屬性：

- **`name`**：prompt 名稱。
- **`description`**：prompt 的簡短說明。
- **`content`**：用來渲染 prompt 的內容。
- **`arguments`**：可選參數清單。
  - **`name`**：參數名稱。
  - **`type`**：以字串表示的簡單 Python 型別，例如 `"int"`。
  - **`default`**：提供預設值後，該參數就會變成 Optional。
  - **`description`**：參數描述，應提供 LLM 真正需要知道的資訊。
- **`tags`**：要套用到該 prompt 的 tags 清單。

這裡的 prompts 應該為 LLM 提供清楚的工作流程路徑，讓它能組合多個工具或步驟來完成任務，例如：

```json
[
    {
      "name": "equity_analysis",
      "description": "Perform a comprehensive equity analysis using multiple data sources and metrics",
      "content": "Conduct a comprehensive analysis of {symbol} for {analysis_period}. Follow this workflow:\n1. First, get basic stock quote and recent price performance using equity_price_performance.\n2. Retrieve fundamental data including financial statements, ratios, and key metrics using [equity_fundamental_ratios, equity_fundamental_metrics, quity_fundamental_balance].\n3. Gather recent news and analyst estimates for the company using [news_company, equity_estiments_price_target].\n4. Compare valuation metrics with industry peers using equity_compare_peers.\n5. Summarize findings with investment recommendation.\n\nFocus areas: {focus_areas}\nRisk tolerance: {risk_tolerance}",
      "arguments": [
        {
          "name": "symbol",
          "type": "str",
          "description": "Stock ticker symbol to analyze (e.g., AAPL, TSLA)"
        },
        {
          "name": "analysis_period",
          "type": "str",
          "default": "last 12 months",
          "description": "Time period for the analysis"
        },
        {
          "name": "focus_areas",
          "type": "str",
          "default": "growth, profitability, valuation",
          "description": "Specific areas to focus on in the analysis"
        },
        {
          "name": "risk_tolerance",
          "type": "str",
          "default": "moderate",
          "description": "Risk tolerance level: conservative, moderate, or aggressive"
        }
      ],
      "tags": ["equity", "analysis", "comprehensive"]
    }
]
```

若 prompt 定義或 prompt 參數無效，系統會把錯誤記錄到 console。
該項目會被忽略，但不會中斷整體流程。

## Inline Prompts

可以透過 `openapi_extra` 字典，把 prompts 加到某個 endpoint 上。

把 prompts 放在這裡，可以幫助 LLM 以較低的推理成本，將該 endpoint 用於特定用途。

你可以引導它使用 `execute_prompt`，或提醒它某些有用 prompts 可能已經附在工具 metadata 中。

以下範例假設 `app` 是一個 `FastAPI` 實例：

```python
@app.get(
    "/economy/gdp",
    openapi_extra={
        "mcp_config": {
            "prompts": [
                {
                    "name": "gdp_summary_prompt",
                    "description": "Generate a brief summary of GDP for a country.",
                    "content": "Provide a concise summary of the GDP for {country} over the last {years} years.",
                    "arguments": [
                        {
                            "name": "years",
                            "type": "int",
                            "default": 5,
                            "description": "Number of years to summarize.",
                        }
                    ],
                    "tags": ["economy", "gdp", "summary"],
                },
                {
                    "name": "gdp_comparison_prompt",
                    "description": "Compare the GDP of two countries.",
                    "content": "Compare the GDP growth of {country1} and {country2}.",
                    "arguments": [
                        {
                            "name": "country1",
                            "type": "str",
                            "description": "First country for comparison.",
                        },
                        {
                            "name": "country2",
                            "type": "str",
                            "description": "Second country for comparison.",
                        },
                    ],
                    "tags": ["economy", "gdp", "comparison"],
                },
            ]
        }
    },
)
def get_gdp_data(country: str, period: Literal["annual", "quarterly"] = "annual"):
    """Get GDP data for a specific country."""
    return {"country": country, "period": period}
```

除了會出現在 `list_prompts` 之外，這些 prompts 也會被放進工具的 metadata 中，並由 `list_tools` 回傳。

這個工具的探索 metadata 會長得像這樣：

__Economy Tools:__

- __`economy_gdp`__: Get GDP data for a specific country.

  - __Associated Prompts:__

    - `gdp_summary_prompt`: Generate a brief summary of GDP for a country. (Arguments: `years`, `country`)
    - `gdp_comparison_prompt`: Compare the GDP of two countries. (Arguments: `country1`, `country2`)

透過 `execute_prompt` 工具使用某個 prompt：

```json
{
  "prompt_name": "gdp_summary_prompt",
  "arguments": {
    "years": 10,
    "country": "Japan"
  }
}
```

輸出會像這樣：

```json
{
  "description": "Generate a brief summary of GDP for a country.",
  "messages": [
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "Use the tool, economy_gdp, to perform the following task.\n\nProvide a concise summary of the GDP for Japan over the last 10 years."
      }
    }
  ]
}
```

## Inline MCP 設定

除了定義 prompts 之外，`openapi_extra.mcp_config` 字典也能更細緻地控制 FastAPI 路由要如何作為 MCP 工具對外曝露。
透過 `MCPConfigModel`，你可以驗證設定內容，並使用多個強大的屬性來客製工具行為。

可透過下列方式匯入：

```
from openbb_mcp_server.models.mcp_config import MCPConfigModel
```

把這份設定放進 `openapi_extra` 後，會覆蓋任何自動產生的值。
你只需要填寫想要客製的欄位即可。

以下是你可以在 `mcp_config` 中定義的屬性：

- **`expose`** (`Optional[bool]`)：設為 `False` 時，該 route 會完全從 MCP server 隱藏。適合用於內部端點或已棄用、且不應作為工具提供的端點。

- **`mcp_type`** (`Optional[MCPType]`)：將 route 分類為特定的 MCP 類型。可用值為 `"tool"`、`"resource"` 或 `"resource_template"`。

- **`methods`** (`Optional[list[HTTPMethod]]`)：指定支援多種 HTTP 方法的 route 要曝露哪些方法（例如 GET、POST）。若省略，則會曝露所有支援的方法。合法值包含 `"GET"`、`"POST"`、`"PUT"`、`"PATCH"`、`"DELETE"`、`"HEAD"`、`"OPTIONS"` 與 `*`（代表全部）。

- **`exclude_args`** (`Optional[list[str]]`)：提供要從工具 signature 中排除的參數名稱清單。適合用來隱藏內部處理的參數，或對最終使用者不重要的欄位。

- **`prompts`** (`Optional[list[dict[str, str]]]`)：此 endpoint 專用的 prompt 清單。每個 prompt 可包含：
  - **`name`**：prompt 名稱。
  - **`description`**：prompt 的簡短描述。
  - **`content`**：用來渲染 prompt 的內容；endpoint 參數會由 placeholders 自動推斷。
  - **`arguments`**：可選參數清單。這些參數可以只存在於 prompt 中，而不一定出現在 endpoint 上。
    - **`name`**：參數名稱。
    - **`type`**：以字串表示的簡單 Python 型別，例如 `"int"`。
    - **`default`**：提供預設值後，該參數會變成 Optional。
    - **`description`**：參數描述，應提供 LLM 必須知道的資訊。
  - **`tags`**：套用到該 prompt 的 tags 清單。

### MCPConfigModel 驗證

在納入 server 之前，這些值會先經過模型驗證。
若設定無效，系統會把錯誤記錄到 console，並忽略該 inline 定義。

```console
ERROR    Invalid MCP config found in route, 'GET /equity/price'. Skipping tool customization because of validation error ->
          1 validation error for MCPConfigModel
          mcp_type
            Input should be 'tool', 'resource' or 'resource_template' [type=enum, input_value='some_setting', input_type=str]
              For further information visit https://errors.pydantic.dev/2.11/v/enum
```


### 範例

以下範例示範如何利用這些屬性微調工具行為：

```python
@app.get(
    "/some/route",
    openapi_extra={
        "mcp_config": {
            "expose": True,
            "mcp_type": "tool",
            "methods": ["GET"],
            "exclude_args": ["internal_param"],
            "prompts": [
                # ... prompt definitions ...
            ]
        }
    },
)
def some_route(param1: str, internal_param: str = "default"):
    """An example route with advanced MCP configuration."""
    return {"param1": param1}
```

在這個例子中，`/some/route` 端點會明確以 `tool` 形式對外提供，且只支援 `GET` 方法；`internal_param` 則會從工具介面中隱藏。

## Client 範例

請依照 client 需要的 transport 與設定啟動伺服器；預設 transport 為 `http`。

```bash
# 使用預設設定啟動
openbb-mcp

# 使用其他 transport
openbb-mcp --transport sse

# 以指定分類與自訂 host/port 啟動
openbb-mcp --default-categories equity,news --host 0.0.0.0 --port 8080

# 啟動時限制可用分類
openbb-mcp --allowed-categories equity,crypto,news

# 啟用 per-session 工具探索
openbb-mcp --tool-discovery
```

### Claude Desktop:

若要將 OpenBB MCP Server 連接到 Claude Desktop，你需要把它設定成自訂工具伺服器。步驟如下：

1. 找到 Claude Desktop 可定義自訂 MCP server 的設定或組態檔。
2. 在 `mcpServers` 設定中加入以下內容。這會讓 Claude Desktop 自動以 `stdio` 啟動 OpenBB MCP Server。

```json
{
  "mcpServers": {
    "openbb-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "openbb-mcp-server",
        "--with",
        "openbb",
        "openbb-mcp",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

3. 確認 `uvx` 已安裝，且可在系統 PATH 中找到；若尚未安裝，請依安裝說明處理。
4. 重新啟動 Claude Desktop 套用設定。之後你應該會看到 `"openbb-mcp"` 出現在可用工具來源中。

### Cursor:

若要在 Cursor 中使用 OpenBB 工具，你需要先啟動 MCP Server，再告訴 Cursor 如何連接它。

**Step 1：啟動 OpenBB MCP Server**

打開終端機並啟動伺服器。你可以使用預設設定，也可以自行客製。

若使用預設設定，請執行：
```bash
openbb-mcp
```
伺服器會在 `http://127.0.0.1:8001` 啟動。

**Step 2：設定 Cursor**

將下列設定加入 `mcp.json` 的 `mcpServers` 物件中。若該物件不存在，可以自行新增。

```json
{
  "mcpServers": {
    "openbb-mcp": {
      "url": "http://localhost:8001/mcp/"
    }
  }
}
```

### VS Code

**Step 1：在 VS Code 設定中啟用 MCP**

按下 `shift + command + p`，開啟「Preferences: Open User Settings」。

搜尋 `mcp`，該項目應會出現在「Chat」區塊下。勾選後即可啟用 MCP server 整合。

<img width="1278" height="411" alt="vs-code-mcp-enable" src="https://github.com/user-attachments/assets/5ace29de-e59c-45c3-b751-c6d92614e0ee" />

**Step 2：啟動 OpenBB MCP Server**

打開終端機並啟動伺服器。你可以使用預設設定，也可以自行客製。

若使用預設設定，請執行：
```bash
openbb-mcp
```
伺服器會在 `http://127.0.0.1:8001` 啟動。

**Step 3：以 HTTP 方式加入 Server**

按下 `shift + command + p`，選擇「MCP: Add Server」。

<img width="595" height="412" alt="vs-code-mcp-commands" src="https://github.com/user-attachments/assets/9b13a5b6-ec20-43e2-9aae-7982e9fdcae6" />

按 Enter，接著選擇 HTTP。

<img width="594" height="174" alt="vs-code-mcp-add-http" src="https://github.com/user-attachments/assets/d2a06e4b-404a-4317-ad2c-241c1ac5e04b" />

從執行中伺服器的 console 複製 URL，並貼上輸入：

```sh
INFO     Starting MCP server 'OpenBB MCP' with transport 'streamable-http' on http://127.0.0.1:8001/mcp
```

替它命名，並選擇加入全域設定或某個 workspace。完成後，系統會在對應範圍建立一份 `mcp.json` VS Code 設定檔。

<img width="402" height="195" alt="vs-code-mcp-json" src="https://github.com/user-attachments/assets/fdea335b-0523-4103-be3e-b5d9675c25b3" />

現在你就可以把這些工具加入聊天上下文中。

<img width="601" height="442" alt="vs-code-mcp-tools" src="https://github.com/user-attachments/assets/06c39248-aedd-4f53-9560-6dfbae1efaf8" />

**注意**：若要加到 Cline 擴充，啟動伺服器時請使用 `--transport sse`。
