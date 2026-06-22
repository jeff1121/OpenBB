---
name: work_with_server
description: 本指南說明與 OpenBB MCP server 互動時，如何呼叫工具、解讀回應、探索能力、使用 prompts，以及處理錯誤。
---

# 使用 OpenBB MCP Server

本指南說明與 OpenBB MCP server 互動時，如何呼叫工具、解讀回應、
探索能力、使用 prompts，以及處理錯誤。

---

## 工具探索流程

第一次連線時，server 會公開一小組 **admin** 工具，用來探索並啟用完整
工具目錄。並非所有工具都會預設啟用。

所有可見性變更都是 **per-session**，每個連線 client 都會維護自己的
啟用工具集，因此多個 agent 可以獨立運作。

### 步驟 1：列出分類

呼叫 `available_categories`（不帶 arguments）查看已安裝項目：

```json
[
    {
        "name": "equity",
        "subcategories": [
            {"name": "price", "tool_count": 5},
            {"name": "fundamental", "tool_count": 12}
        ],
        "total_tools": 17
    },
    {
        "name": "economy",
        "subcategories": [
            {"name": "general", "tool_count": 3}
        ],
        "total_tools": 3
    }
]
```

每個 category 都對應到頂層 API router。Subcategory 則是巢狀 router。

### 步驟 2：瀏覽分類中的工具

以 category 名稱呼叫 `available_tools`：

```json
// 輸入
{"category": "equity", "subcategory": "price"}

// 輸出
[
    {"name": "equity_price_historical", "active": true, "description": "取得歷史價格資料..."},
    {"name": "equity_price_quote", "active": false, "description": "取得目前價格報價..."}
]
```

`active` 欄位表示工具目前是否已啟用。未啟用的工具在啟用前不能呼叫，
但仍會顯示簡短的快取說明，因此仍可被探索。

`subcategory` argument 是選用的。省略它即可查看該 category 中的所有工具。

### 步驟 3：啟用工具

以工具名稱清單呼叫 `activate_tools`：

```json
// 輸入
{"tool_names": ["equity_price_quote", "equity_price_historical"]}

// 輸出
"已啟用：equity_price_quote, equity_price_historical"
```

已經啟用的工具會被靜默納入。未知名稱會在回應中回報：

```
"已啟用：equity_price_quote 找不到：nonexistent_tool"
```

如果沒有處理任何工具，回應會是：

```
"沒有處理任何工具。"
```

### 步驟 4：啟用整個分類

呼叫 `activate_category` 可一次啟用某個 category（或 subcategory）中的所有工具：

```json
// 啟用 equity 中的全部工具
{"category": "equity"}

// 只啟用 equity/price 工具
{"category": "equity", "subcategory": "price"}

// 輸出
"已在 'equity'/'price' 啟用 5 個工具：equity_price_historical, equity_price_quote, ..."
```

當你需要整個 category 時，這比逐一列出工具名稱更快。

### 步驟 5：停用工具

呼叫 `deactivate_tools` 來停用不再需要的工具：

```json
// 輸入
{"tool_names": ["equity_price_quote"]}

// 輸出
"已停用：equity_price_quote"
```

未知名稱會在回應中回報：

```
"找不到：nonexistent_tool"
```

這會減少啟用工具清單中的雜訊，並能提升 context 效率。

### 探索功能停用時

如果 server 啟動時未使用 `--tool-discovery`，admin 工具將不可用。
`default_tool_categories` 中的所有工具都會永久啟用。

---

## 呼叫資料工具

### 輸入參數

每個資料工具都有描述其輸入的 JSON Schema。典型工具 schema：

```json
{
    "type": "object",
    "properties": {
        "symbol": {
            "type": "string",
            "description": "要取得資料的 symbol。"
        },
        "provider": {
            "type": "string",
            "enum": ["fmp", "polygon", "yfinance"],
            "description": "查詢要使用的 provider。"
        },
        "start_date": {
            "anyOf": [{"type": "string", "format": "date"}, {"type": "null"}],
            "description": "資料的開始日期。"
        },
        "end_date": {
            "anyOf": [{"type": "string", "format": "date"}, {"type": "null"}],
            "description": "資料的結束日期。"
        },
        "interval": {
            "type": "string",
            "default": "1d",
            "description": "資料的時間間隔。"
        }
    },
    "required": ["symbol"]
}
```

主要規則：

- **`provider`**：只會出現在使用 provider interface 的 endpoint。
  當它被列出時，其 enum 會顯示可用的 provider sources。如果 endpoint
  只有一個 provider，可以省略它，系統會自動使用唯一的 provider。
  當有多個 provider 可用時，請從 enum 中選擇一個。不同 provider 可能
  回傳不同欄位，或支援不同參數。不使用 provider interface 的 endpoint
  （基本 GET/POST routes）完全不會有 `provider` 參數。
- **`symbol` 格式**：symbols 不區分大小寫。多個 symbols 可用逗號分隔：
  `"AAPL,MSFT,GOOG"`。
- **日期**：一律格式化為 `YYYY-MM-DD` 字串。
- **選用參數**：會有包含 `null` type 的 `anyOf`，或帶有 `default`
  value。省略它們即可使用 defaults。
- **Provider-specific 參數**：部分參數只和特定 providers 有關。
  schema 會聯集所有參數；無關的參數會被靜默忽略。

### 工具呼叫範例

```json
{
    "name": "equity_price_historical",
    "arguments": {
        "symbol": "AAPL",
        "provider": "fmp",
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "interval": "1d"
    }
}
```

---

## 了解回應

每個 OpenBB 工具都會回傳 **OBBject**，也就是標準化的 response envelope：

```json
{
    "id": "06520558-d54a-7e53-8000-7aafc8a42694",
    "results": [...],
    "provider": "fmp",
    "warnings": null,
    "chart": null,
    "extra": {
        "metadata": {
            "arguments": {...},
            "duration": 565256375,
            "route": "/equity/price/historical",
            "timestamp": "2025-01-15 11:28:57.149548"
        }
    }
}
```

### 回應欄位

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `string` | 識別這次請求的 UUID |
| `results` | `list[dict] \| dict \| string \| null` | 實際資料。通常是 records 清單 |
| `provider` | `string \| null` | 完成請求的 provider |
| `warnings` | `list[object] \| null` | 來自 provider 或 platform 的非致命警告 |
| `chart` | `object \| null` | 傳入 `chart=true` 時的 chart data |
| `extra` | `dict` | 執行 metadata 與 results metadata |

### `results` 欄位

這是主要資料 payload。其結構取決於 endpoint：

**表格式資料**：最常見，為 dictionaries 清單（每列一個 dictionary）：

```json
"results": [
    {"date": "2025-01-02", "open": 150.0, "high": 155.0, "low": 149.0, "close": 153.5, "volume": 1000000},
    {"date": "2025-01-03", "open": 153.0, "high": 157.0, "low": 152.0, "close": 156.2, "volume": 1200000}
]
```

**單筆 record**：部分 endpoint 會回傳單一 dict：

```json
"results": {"symbol": "AAPL", "price": 185.50, "change": 2.30, "volume": 45000000}
```

**空結果**：沒有可用資料時：

```json
"results": null
```

或：

```json
"results": []
```

**欄位名稱會因 provider 而異**：不同 provider 對同一 endpoint 可能回傳
不同欄位。請一律檢查回傳 records 中的 keys。

### `warnings` 欄位

Warnings 是執行期間發生的非致命問題：

```json
"warnings": [
    {
        "category": "OpenBBWarning",
        "message": "參數 'source' 不受 fmp 支援。可用於：intrinio。"
    }
]
```

常見 warning 情境：

- 未知參數被 provider 靜默忽略
- 回傳部分資料（列數少於要求）
- Provider-specific 的資料品質註記

當 `warnings` 為 `null` 時，表示沒有產生 warnings。

### `extra` 欄位

包含 execution metadata，以及選用的 results metadata：

```json
"extra": {
    "metadata": {
        "arguments": {
            "provider_choices": {"provider": "fmp"},
            "standard_params": {"symbol": "AAPL", "start_date": "2025-01-01"},
            "extra_params": {}
        },
        "duration": 565256375,
        "route": "/equity/price/historical",
        "timestamp": "2025-01-15 11:28:57.149548"
    },
    "results_metadata": {
        "...provider-specific metadata..."
    }
}
```

**`metadata`**：一律存在（除非停用）：

- `arguments`：實際使用的精確參數，拆分為 provider choices、
  standard params 與 extra（provider-specific）params
- `duration`：請求花費的奈秒數
- `route`：API endpoint path
- `timestamp`：請求建立時間

**`results_metadata`**：當 provider 回傳資料的情境資訊時會出現，例如
FRED series metadata、CBOE options metadata。內容會因 endpoint 與
provider 而異。

### `chart` 欄位

當呼叫工具時帶入 `chart: true`（若支援），`chart` 欄位會包含 Plotly figure：

```json
"chart": {
    "content": { "data": [...], "layout": {...} },
    "fig": { "data": [...], "layout": {...} }
}
```

`content` key 包含可直接 render 的 Plotly JSON。並非所有 endpoint 都支援 charting。

---

## Provider（資料來源）選擇

### Provider 的運作方式

每個資料 endpoint 都可以有多個 provider sources（例如 FMP、Yahoo Finance、
Polygon）。Providers 的差異包括：

- **可用參數**：部分 providers 會提供額外篩選或選項
- **回傳欄位**：欄位名稱與資料粒度可能不同
- **Rate limits 與 authentication**：部分 providers 需要 API keys
- **資料涵蓋範圍**：地理市場、日期範圍、資產類型

### 選擇 Provider

當工具的輸入 schema 包含 `provider` 時，其 enum 會列出該 endpoint
所有已安裝的 provider sources。如果只有一個 provider，可以省略該參數，
系統會自動選取唯一的 provider。當有多個 providers 可用時，依據以下條件選擇：

1. **檢查 enum**：只有列出的選項能使用
2. **考量資料需求**：不同 providers 可能有不同欄位
3. **API key 要求**：部分 providers 需要在
   `~/.openbb_platform/user_settings.json` 設定 credentials

不使用 provider interface 的 endpoints（透過 `router.command(methods=["GET"])`
或 raw FastAPI 加入的基本 GET/POST routes）沒有 `provider` 參數。

如果 provider 因缺少 credentials 而失敗，錯誤訊息會指出 authentication 問題。

### Provider-Specific 參數

部分參數只適用於特定 providers。例如 `source` 參數可能只適用於
`intrinio` provider。將它傳給 `fmp` 會產生 warning，但不會造成 error。

---

## 使用 Prompts（提示）

server 內含 prompt system，可用來存取文件、使用指南與分析框架。

### 列出可用 Prompts（提示）

呼叫 `list_prompts`（不帶 arguments）：

```json
[
    {"name": "develop_extension", "tags": ["skill"], "arguments": []},
    {"name": "build_workspace_app", "tags": ["skill"], "arguments": []},
    {"name": "configure_mcp_server", "tags": ["skill"], "arguments": []},
    {"name": "analyze_stock", "tags": ["analysis"], "arguments": [
        {"name": "symbol", "type": "str", "required": true},
        {"name": "focus", "type": "str", "required": false, "default": "fundamentals"}
    ]}
]
```

### 執行 Prompt（提示）

以 prompt name 與必要 arguments 呼叫 `execute_prompt`：

```json
// 輸入
{"prompt_name": "analyze_stock", "arguments": {"symbol": "AAPL"}}

// 輸出 - render 後的 prompt content
{
    "messages": [
        {"role": "user", "content": "分析 AAPL，聚焦於 fundamentals..."}
    ]
}
```

沒有 arguments 的 prompts（例如 skills）會原樣回傳完整內容。
帶有 arguments 的 prompts 會把提供的值替換到 template 中。

### 依 Tag 區分的 Prompt（提示）類別

| Tag | 來源 | 說明 |
|---|---|---|
| `system` | System prompt 檔案 | 整個 server 的 context 與指示 |
| `server` | Server prompts JSON | 可重複使用的分析框架 |
| `route-specific` | API routes 上的 inline 內容 | Endpoint 使用指南 |

---

## 錯誤處理

### 錯誤類型

| 情境 | 會發生什麼 |
|---|---|
| **無效參數** | 回傳 error，包含 HTTP 422 詳細資訊，說明哪個參數驗證失敗 |
| **缺少必要參數** | 回傳 error，包含 HTTP 422，指出缺少的欄位 |
| **Provider authentication 失敗** | 回傳 error，包含 HTTP 401/403，指出 credentials 遺失或無效 |
| **Provider rate limit** | 回傳 error，包含 HTTP 429 或 provider-specific rate limit 訊息 |
| **沒有可用資料** | 成功回應，且 `results: null` 或 `results: []` |
| **工具未啟用** | 工具不會出現在可用工具清單中 |
| **未知工具名稱** | 標準 MCP protocol error |
| **找不到 category**（discovery） | 回傳 error 並列出可用分類 |
| **連線失敗** | 回傳 error，內容為 "Request error: ..." |

### 解讀空結果

包含 `results: null` 或 `results: []` 的回應 **不是 error**，它表示
provider 沒有符合查詢的資料。常見原因：

- 日期範圍內沒有交易日
- 選取的 provider 不涵蓋該 symbol
- 要求期間的資料尚未可用

請嘗試不同 provider、調整日期範圍，或確認 symbol 格式。

### 讀取 Validation 錯誤

Validation errors（HTTP 422）會包含出錯細節：

```
HTTP error 422: Unprocessable Entity - {"detail": [{"loc": ["query", "symbol"], "msg": "field required", "type": "value_error.missing"}]}
```

`loc` 欄位會顯示哪個 parameter 失敗，`msg` 說明原因。

---

## 實用模式

### 取得時間序列資料

1. 啟用工具：`activate_tools(["equity_price_historical"])`
2. 以日期範圍呼叫：
   ```json
   {"symbol": "AAPL", "provider": "fmp", "start_date": "2025-01-01", "end_date": "2025-02-01"}
   ```
3. 讀取 `results`：每筆 record 都有 `date`、`open`、`high`、`low`、`close`、
   `volume`（欄位名稱取決於 provider）

### 比較多個 Symbols

傳入逗號分隔的 symbols：

```json
{"symbol": "AAPL,MSFT,GOOG", "provider": "fmp"}
```

回傳結果會包含所有 symbols 的 records。如果存在 `symbol` 欄位，可依該欄位
篩選；否則可依排序模式篩選。

### 串接工具呼叫

將某個工具的輸出作為另一個工具的輸入：

1. 取得 peers：`equity_compare_peers({"symbol": "AAPL", "provider": "fmp"})`
2. 從 `results` 擷取 symbols
3. 取得 quotes：`equity_price_quote({"symbol": "AAPL,PEER1,PEER2", "provider": "fmp"})`

### 檢查資料涵蓋範圍

不確定 endpoint 可用哪些 providers 時，查看工具的輸入 schema；
`provider` 參數的 `enum` 會列出所有已安裝選項。

### 使用 Charts

傳入 `chart: true` 以取得預先建立的 Plotly 視覺化：

```json
{"symbol": "AAPL", "provider": "fmp", "chart": true}
```

回應中的 `chart` 欄位包含 Plotly figure JSON。

---

## 使用者設定與預設值

server 會讀取 `~/.openbb_platform/user_settings.json` 中的使用者設定：

### API 金鑰

Provider 憑證儲存在 `credentials` 底下：

```json
{
    "credentials": {
        "fmp_api_key": "YOUR_KEY",
        "polygon_api_key": "YOUR_KEY"
    }
}
```

如果缺少必要 API key，對該 provider 的呼叫會因 authentication error 而失敗。

### 預設 Provider

為每個 endpoint 設定預設 provider，使其預先被選取：

```json
{
    "defaults": {
        "commands": {
            "/equity/price/historical": {"provider": "yfinance"},
            "/economy/cpi": {"provider": "oecd"}
        }
    }
}
```

當有多個 providers 可用時，如果省略參數，這會決定預設選擇。

### 預設參數

可為個別參數設定 defaults，使它們在未明確傳入時套用：

```json
{
    "defaults": {
        "commands": {
            "/equity/price/historical": {
                "provider": "fmp",
                "chart": true,
                "chart_params": {
                    "heikin_ashi": true,
                    "indicators": {"sma": {"length": [21, 50]}}
                }
            }
        }
    }
}
```

### 輸出偏好

`output_type` preference 控制 Python Interface 回傳資料的方式。
對 MCP 而言，server 一律回傳完整 OBBject JSON，不受此設定影響；
但它與 Python Interface 相關：

| 輸出型別 | 說明 |
|---|---|
| `OBBject` | 完整 response object（預設） |
| `dataframe` | Pandas DataFrame |
| `numpy` | NumPy array |
| `dict` | Python dictionary |
| `polars` | Polars DataFrame |
| `llm` | 只包含 results 的 JSON 編碼字串 |
| `chart` | Chart object |

### LLM 模式

在 Python Interface 中將 `output_type` 設為 `"llm"` 會移除除了 `results`
以外的所有內容，並以 JSON 字串回傳。這針對 LLM frameworks 的 token
效率最佳化。在 REST API / MCP 情境中，一律回傳完整 OBBject。

---

## 使用技能

技能是以 `skill://<name>/SKILL.md` URI 公開的 MCP resources。
透過標準 MCP resource methods 探索並讀取它們。

### 探索可用技能

呼叫 `list_resources()`（不帶 arguments）：

```json
[
    {"uri": "skill://develop_extension/SKILL.md", "name": "develop_extension"},
    {"uri": "skill://build_workspace_app/SKILL.md", "name": "build_workspace_app"},
    {"uri": "skill://configure_mcp_server/SKILL.md", "name": "configure_mcp_server"},
    {"uri": "skill://work_with_server/SKILL.md", "name": "work_with_server"}
]
```

### 讀取技能

以 skill URI 呼叫 `read_resource()`：

```json
// 輸入
{"uri": "skill://develop_extension/SKILL.md"}

// 輸出 - skill guide 的完整 Markdown content
```

### 支援檔案

技能目錄可以包含額外支援檔案（例如 templates、examples）。
參考 `skill://<name>/_manifest` 的 skill manifest，即可探索與主要
`SKILL.md` 一起封裝的支援檔案。

---

## 快速參考

### Admin 工具（探索）

| 工具 | 輸入 | 回傳 |
|---|---|---|
| `available_categories` | *(none)* | 含 subcategories 與 tool counts 的 categories 清單 |
| `available_tools` | `category`, `subcategory?` | 含 active 狀態與說明的 tools 清單 |
| `activate_tools` | `tool_names: list` | 狀態訊息 |
| `deactivate_tools` | `tool_names: list` | 狀態訊息 |
| `activate_category` | `category`, `subcategory?` | 含數量與工具名稱的狀態訊息 |

### OBBject 回應結構

| 欄位 | 一律存在 | 內容 |
|---|---|---|
| `id` | 是 | 識別請求的 UUID |
| `results` | 是 | 資料 payload（list、dict、string 或 null） |
| `provider` | 是 | Provider 名稱或 null |
| `warnings` | 是 | Warning 清單或 null |
| `chart` | 是 | Chart 資料或 null |
| `extra` | 是 | metadata 字典（可能為空） |
