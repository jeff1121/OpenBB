---
name: develop_extension
description: 這是一份從零開始建立新 OpenBB Platform 擴充套件的完整指南。請依序完成每個階段。當使用者說「build me an application that does X」時，使用本指南來建立專案骨架、實作、安裝並驗證擴充套件。
---

# 建立 OpenBB Platform 擴充套件

這是一份從零開始建立新 OpenBB Platform 擴充套件的完整指南。
請依序完成每個階段。當使用者說「build me an application that does X」時，
使用本指南來建立專案骨架、實作、安裝並驗證擴充套件。

---

## 階段 1：建立專案骨架

建立專案骨架前，必須先在目前啟用的 Python 環境中安裝
`openbb-cookiecutter` 套件。使用以下指令安裝：

```
pip install openbb-cookiecutter
```

接著執行 CLI 來產生專案骨架。
所有變數都有合理預設值；只覆寫你需要的項目。

### 樣板變數

| 變數 | 預設值 | 說明 |
|---|---|---|
| `full_name` | `"Hello World"` | 作者名稱 |
| `email` | `"hello@world.com"` | 作者 email |
| `project_name` | `"OpenBB Python Extension Template"` | 人類可讀的專案名稱 |
| `project_tag` | 由 `project_name` 衍生 | 以連字號分隔的 slug（作為目錄名稱與套件識別字） |
| `package_name` | 由 `project_name` 衍生 | Python 套件名稱（lower_snake_case） |
| `provider_name` | 由 `project_name` 衍生 | Provider 識別字（lower_snake_case） |
| `router_name` | 由 `project_name` 衍生 | Router 識別字（lower_snake_case） |
| `obbject_name` | 由 `project_name` 衍生 | OBBject accessor 名稱（lower_snake_case） |

所有衍生值都會自動從 `project_name` 產生，大多數情況只需要
提供 `project_name`。

### CLI 指令

```
openbb-cookiecutter \
  -o /path/to/output \
  --no-input \
  --extra-context project_name="My Extension Name"
```

加入更多 `--extra-context KEY=VALUE` 配對即可覆寫個別變數。
使用 `-f` 覆寫既有目錄。

---

## 階段 2：了解產生的結構

建立骨架後，你會得到這棵樹狀結構（template 變數已解析）：

```
<project_tag>/
├── pyproject.toml          # 相依套件、entry points（重要）
├── <package_name>/
│   ├── providers/
│   │   └── <provider_name>/
│   │       ├── __init__.py     # Provider 註冊（fetcher_dict）
│   │       ├── models/
│   │       │   ├── example.py      # 自訂 schema fetcher 範例
│   │       │   └── ohlc_example.py # 標準 model fetcher 範例
│   │       └── utils/
│   │           └── helpers.py      # 共用工具函式
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── <router_name>.py        # Router commands（API endpoints）
│   │   ├── <router_name>_views.py  # Chart views（選用）
│   │   └── depends.py              # Dependency injection
│   └── obbject/
│       └── <obbject_name>/
│           └── __init__.py         # OBBject accessors（選用）
└── tests/
    └── conftest.py
```

### 四種 Plugin 類型

OpenBB 會透過 `pyproject.toml` 中的 Python entry points 探索擴充套件。
每種 plugin 類型都有自己的 entry point group：

| Entry point group | 註冊內容 | 所在位置 |
|---|---|---|
| `openbb_provider_extension` | Data provider（fetchers） | `providers/<name>/__init__.py` |
| `openbb_core_extension` | Router（API endpoints/commands） | `routers/<name>.py` |
| `openbb_charting_extension` | 圖表 views | `routers/<name>_views.py` |
| `openbb_obbject_extension` | 結果後處理 accessors | `obbject/<name>/__init__.py` |

---

## 階段 3：實作資料 Provider

這是任何擴充套件的核心。Provider 會從外部來源擷取資料，
並以具型別的 Pydantic models 回傳。

### 三類別 Fetcher 模式

每個 data fetcher 都遵循此結構：

**Class 1 — QueryParams**（輸入 schema）：
- 繼承自 `openbb_core.provider.abstract.query_params.QueryParams`
- 定義使用者可傳入的所有參數（例如 `symbol`、`start_date`）
- 使用 `pydantic.Field` 提供說明與預設值

**Class 2 — Data**（輸出 schema）：
- 繼承自 `openbb_core.provider.abstract.data.Data`
- 定義回應中的所有欄位（例如 `open`、`high`、`low`、`close`、`volume`）
- 使用 `pydantic.Field` 提供說明
- 使用 `__alias_dict__` 將來源欄位名稱對應到你的 schema 欄位名稱

**Class 3 — Fetcher**（協調器）：
- 繼承自 `Fetcher[YourQueryParams, list[YourData]]`
- 正好有三個 static methods：

  1. `transform_query(params: dict) -> YourQueryParams`
     預先處理使用者輸入。回傳已驗證的 QueryParams 實例。

  2. `extract_data(query, credentials, **kwargs) -> list[dict]`
     對資料來源發出實際 HTTP request。以 dicts 回傳原始資料。
     若使用 async 擷取，請改名為 `aextract_data`。

  3. `transform_data(query, data, **kwargs) -> list[YourData]`
     將原始 dicts 轉換成具型別的 Data model 實例。

### Fetcher 檔案的匯入項目

```python
from typing import Any
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field
```

### HTTP requests：必要工具

**重要：** fetchers 與 utility helpers 內的所有 HTTP requests **必須**使用
`openbb_core.provider.utils.helpers` 內建工具。**不要**從零建立原始
`requests`、`aiohttp` 或 `httpx` clients。內建 helpers 會自動套用使用者
在 `system_settings.json` 中設定的 HTTP 設定（proxy、timeout、user-agent 等）。

#### 建立 query strings

將 QueryParams model 轉換成 URL query string，可選擇排除
不應出現在 URL 中的參數：

```python
from openbb_core.provider.utils.helpers import get_querystring

query_string = get_querystring(query.model_dump(), ["interval", "provider"])
url = f"https://api.example.com/data?{query_string}"
```

`model_dump()` 會自動移除 `None` 值。第二個參數傳入要排除的參數名稱
list（若沒有要排除的項目，使用 `[]`）。

#### 同步 requests

用於 `extract_data` 內（sync fetchers）：

```python
from openbb_core.provider.utils import make_request

# 回傳 requests.Response 物件
response = make_request(url, headers={"Authorization": f"Bearer {api_key}"})
data = response.json()
```

所有 `requests.get`/`requests.post` keyword arguments 都會被傳遞下去。

如果多個 requests 需要 session 物件：

```python
from openbb_core.provider.utils.helpers import get_requests_session

session = get_requests_session()
response = session.get(url)
```

#### 非同步 requests（建議）

用於 `aextract_data` 內（async fetchers）。**一律優先使用 async。**

**單一 URL**：預設回傳已解析的 JSON：

```python
from openbb_core.provider.utils.helpers import amake_request

data = await amake_request(url)  # 回傳 dict（已解析 JSON）
```

**多個 URLs**：並行下載並回傳 list：

```python
from openbb_core.provider.utils.helpers import amake_requests

urls = [f"https://api.example.com/data/{s}" for s in symbols]
all_data = await amake_requests(urls)  # 回傳 list[dict]
```

**自訂回應處理（例如 CSV）：** `amake_request` 與
`amake_requests` 預設會解析 JSON。若是非 JSON 內容（CSV、text、
binary），請傳入 `response_callback`：

```python
from io import StringIO
from typing import Any
from pandas import read_csv
from openbb_core.provider.utils.helpers import amake_request

results: list[dict] = []

async def csv_callback(response, _: Any):
    """將 CSV 回應解析成 dict 清單。"""
    text = await response.text()
    df = read_csv(StringIO(text))
    results.extend(df.to_dict("records"))

await amake_request(url, response_callback=csv_callback)
# results 現在包含已解析的資料列
```

如果 CSV 檔有需要略過的 header rows，將 `skiprows` 傳給 `read_csv`：

```python
async def csv_callback(response, _: Any):
    text = await response.text()
    df = read_csv(StringIO(text), skiprows=3)
    results.extend(df.to_dict("records"))
```

**Async session 物件**：如果需要原始 `aiohttp.ClientSession`：

```python
from openbb_core.provider.utils.helpers import get_async_requests_session

async with await get_async_requests_session() as session:
    async with session.get(url) as response:
        if response.status != 200:
            raise OpenBBError(f"Failed: {response.status} -> {response.reason}")
        data = await response.json()
```

#### 摘要：該使用哪個 Helper

| 情境 | Function | Module |
|---|---|---|
| 建立 query string | `get_querystring()` | `openbb_core.provider.utils.helpers` |
| Sync 單一 request | `make_request()` | `openbb_core.provider.utils` |
| Sync session | `get_requests_session()` | `openbb_core.provider.utils.helpers` |
| Async 單一 request（JSON） | `amake_request()` | `openbb_core.provider.utils.helpers` |
| Async 多個 URLs（JSON） | `amake_requests()` | `openbb_core.provider.utils.helpers` |
| Async 單一/多個（CSV/text） | `amake_request()` + `response_callback` | `openbb_core.provider.utils.helpers` |
| Async 原始 session | `get_async_requests_session()` | `openbb_core.provider.utils.helpers` |

### 使用標準 models（多 Provider endpoints）

若要接入其他 providers 已經支援的既有 endpoints（例如 `EquityHistorical`），
請繼承標準 query/data classes，而不是 abstract base classes：

```python
from openbb_core.provider.standard_models.equity_historical import (
    EquityHistoricalData,
    EquityHistoricalQueryParams,
)
```

接著將 provider 特定欄位作為額外 attributes 加入。
使用 `__alias_dict__` 將來源欄位名稱對應到標準欄位名稱。

### 在 Provider 中註冊 fetchers

在 `providers/<provider_name>/__init__.py` 中建立 `Provider` 實例：

```python
from openbb_core.provider.abstract.provider import Provider

my_provider = Provider(
    name="my_provider",
    description="此 provider 功能的說明。",
    # credentials=["api_key"],  # 如果需要 API key，取消註解
    website="https://example.com",
    fetcher_dict={
        "MyCustomModel": MyCustomFetcher,
        "EquityHistorical": MyEquityHistoricalFetcher,  # 接入既有 endpoint
    },
)
```

`fetcher_dict` keys 是 model names。當 key 符合標準 model name
（例如 `"EquityHistorical"`）時，這個 provider 就能透過該既有 endpoint
的 `provider` 參數被選用。

若是自訂/新的 model names，也必須建立一個引用該 model name 的 router command
（請見階段 4）。

### 憑證

如果你的 provider 需要 API key：
1. 將 `credentials=["api_key"]` 加到 Provider constructor
2. 在 `extract_data` 透過 `credentials.get("<package_name>_api_key")` 存取
3. 使用者在自己的 OpenBB user settings 中設定它

---

## 階段 4：實作 Router

Router 會定義使用者呼叫的 API endpoints（commands）。

### Router 基礎

```python
from openbb_core.app.router import Router

router = Router(prefix="")
```

最上層 prefix 由 `pyproject.toml` 中的 entry point name 決定，
不是由 `prefix` 參數決定。只有 sub-routers 才需要設定 `prefix`。

### Provider 支援的 command（標準模式）

這是最常見的模式。它會透過 model name 將 router command
連接到一個或多個 provider fetchers：

```python
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import (
    ExtraParams,
    ProviderChoices,
    StandardParams,
)
from openbb_core.app.query import Query
from pydantic import BaseModel

@router.command(model="MyCustomModel")
async def my_command(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """此 command 的說明。"""
    return await OBBject.from_query(Query(**locals()))
```

四個參數（`cc`、`provider_choices`、`standard_params`、`extra_params`）
以及 `OBBject.from_query(Query(**locals()))` 回傳模式都是必要的，
而且必須完全依照範例使用。

`model="MyCustomModel"` 字串必須符合至少一個 provider 的
`fetcher_dict` 內的 key。

### 自由格式 GET endpoint

用於不使用 provider/fetcher 系統的 endpoints：

```python
@router.command(methods=["GET"])
async def my_endpoint(symbol: str = "AAPL") -> OBBject[dict]:
    """直接取得一些資料。"""
    # 發出 HTTP requests、計算等
    return OBBject(results={"key": "value"})
```

### 自由格式 POST endpoint

```python
@router.command(methods=["POST"])
async def my_post_endpoint(
    data: BaseModel,   # Body 參數
    flag: bool = False, # Query 參數
) -> OBBject[dict]:
    """處理提交的資料。"""
    return OBBject(results={"processed": True})
```

### 相依性注入

使用 `routers/depends.py` 放置共用 dependencies：

```python
from typing import Annotated
import requests
from fastapi import Depends
from openbb_core.provider.utils.helpers import get_requests_session

Session = Annotated[requests.Session, Depends(get_requests_session)]
```

接著在 router commands 中使用 `session: Session` 作為參數。

### 加入範例

```python
from openbb_core.app.model.example import APIEx, PythonEx

@router.command(
    model="MyModel",
    examples=[
        PythonEx(
            description="取得 AAPL 的資料",
            code=["obb.my_router.my_command(symbol='AAPL')"],
        )
    ],
)
```

---

## 階段 5：`pyproject.toml` 中的 Entry Points

這一點**非常重要**：OpenBB 完全透過這些 entry points 探索你的程式碼。

### Provider Entry Point

```toml
[tool.poetry.plugins."openbb_provider_extension"]
my_provider = "my_package.providers.my_provider:my_provider_variable"
```

變數（`my_provider_variable`）是你在階段 3 建立的 `Provider(...)` 實例。

### Router Entry Point

```toml
[tool.poetry.plugins."openbb_core_extension"]
my_router = "my_package.routers.my_router:router"
```

entry point **name**（`my_router`）會決定 API path prefix。
例如，`my_router` 代表 endpoints 會出現在 `/my_router/...` 底下。

### Charting Entry Point（選用）

```toml
[tool.poetry.plugins."openbb_charting_extension"]
my_router = "my_package.routers.my_router_views:MyRouterViews"
```

### OBBject Entry Point（選用）

```toml
[tool.poetry.plugins."openbb_obbject_extension"]
my_accessor = "my_package.obbject.my_obbject:ext"
my_namespace = "my_package.obbject.my_obbject:class_ext"
```

---

## 階段 6：Chart Views（選用）

如果你想加入 charting 支援：

```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openbb_charting.core.openbb_figure import OpenBBFigure

class MyRouterViews:
    """Router 的 chart views。"""

    @staticmethod
    def my_router_my_command(**kwargs) -> tuple["OpenBBFigure", dict[str, Any]]:
        """為 my_command 結果建立 chart。"""
        from openbb_charting.core.openbb_figure import OpenBBFigure

        data = kwargs["obbject_item"]
        fig = OpenBBFigure()
        # 使用 fig.add_*() methods 建立你的 chart
        content = fig.show(external=True).to_plotly_json()
        return fig, content
```

Method 命名慣例：`<router_name>_<command_name>`，需符合
lower_snake_case 的 route path。

---

## 階段 7：OBBject Accessors（選用）

結果後處理擴充套件，可將 methods 加到 `OBBject` response。

### Function Accessor（類似 Property）

```python
from openbb_core.app.model.extension import Extension

ext = Extension(name="to_csv", description="將 results 轉換成 CSV 字串。")

@ext.obbject_accessor
def to_csv(obbject, **kwargs) -> str:
    """轉換成 CSV。"""
    return obbject.to_dataframe().to_csv()
```

### Class Accessor（具命名空間的 Methods）

```python
class_ext = Extension(name="my_tools", description="自訂結果工具。")

@class_ext.obbject_accessor
class MyTools:
    def __init__(self, obbject):
        self._obbject = obbject

    def summary(self, **kwargs):
        """回傳摘要。"""
        df = self._obbject.to_dataframe()
        return df.describe()
```

---

## 階段 8：安裝、建置與測試

### 以開發模式安裝

從產生的專案根目錄執行：

```
pip install -e ".[dev]"
```

這會註冊 entry points，讓 OpenBB 立即探索到你的擴充套件。

### 使用 `openbb-build` 建置 static assets

**重要：** 安裝新擴充套件後，或變更下列任一項目後，在使用 Python
interface（`obb.<router>.<command>(...)`）前，**必須**執行 `openbb-build`：

- **Model definitions**：`QueryParams` 或 `Data` classes（欄位名稱、型別、
  預設值、說明）
- **Provider registration**：`fetcher_dict` keys 的變更、新增/移除
  fetchers
- **Router commands**：新增、移除或重新命名 `@router.command()`
  endpoints
- **Entry points**：`pyproject.toml` plugin entries 的變更
- **註冊鏈中的任何可 import 項目**：`Provider(...)`
  實例、router module 或 model module paths

變更以下項目時，**不需要**重新執行 `openbb-build`：

- `extract_data` / `aextract_data` / `transform_data` /
  `transform_query` static methods 內的邏輯（Fetcher method bodies）
- Utility/helper functions
- 不影響 public schema 的內部實作細節

```
openbb-build
```

這會重新產生 Python interface 所依賴的 static assets（type stubs、
package interface、provider maps）。若缺少此步驟，新增或修改過的
commands 不會出現在 `obb` 物件上，呼叫也會失敗。

**作為 API server 執行時**（例如透過 `uvicorn` 或 MCP server），
static assets **不會被使用**，API 會在啟動時動態探索 extensions。
純 API 用途不需要執行 `openbb-build`。

### 驗證安裝

啟動 Python session 並檢查：

```python
from openbb import obb
# 你的新 commands 應該會出現：
# obb.<router_name>.<command_name>(...)
```

或啟動 API server，確認新的 endpoints 有出現。

### 執行 tests

```
pytest tests/ -v
```

產生的 `tests/conftest.py` 會設定 `OPENBB_AUTO_BUILD=true`，以正確
準備 test environment。

---

## 工作流程摘要

當使用者要求「Build me an application that does X」時：

1. **Analyze**：判斷需要哪些 data sources、要公開哪些 endpoints，
   以及要使用標準 models 還是自訂 schemas。
2. **Scaffold**：使用有意義的 `project_name` 執行 `openbb-cookiecutter`。
3. **Delete examples**：從 models 目錄移除 `example.py` 與 `ohlc_example.py`。
   清理範例 router commands。
4. **Implement models**：針對每個 data source，在 `providers/<name>/models/`
   建立 `QueryParams` + `Data` + `Fetcher` classes。
5. **Register fetchers**：使用 `fetcher_dict` 更新
   `providers/<name>/__init__.py`。
6. **Implement router**：在 `routers/<name>.py` 建立
   `@router.command(model="...")` endpoints。
7. **Update entry points**：確保 `pyproject.toml` entry points 符合實際
   module paths 與 variable names。
8. **Add dependencies**：將任何 third-party packages 加到 `pyproject.toml`
   的 `[tool.poetry.dependencies]`。
9. **Install**：從專案根目錄執行 `pip install -e ".[dev]"`。
10. **Build**：執行 `openbb-build`，為 Python interface 重新產生
    static assets。如果只使用 API server，略過此步驟。
11. **Test**：驗證 commands 可運作，接著撰寫 tests。
