---
name: build_workspace_app
description: 本指南涵蓋從 `openbb-cookiecutter` 建立骨架的擴充套件專案中，建置、執行與服務自訂 OpenBB Workspace 應用程式的完整生命週期。它假設專案外殼已存在（建立骨架的說明請見 `develop_extension` skill）。
---

# 建置並執行 OpenBB Workspace 應用程式

本指南涵蓋從 `openbb-cookiecutter` 建立骨架的擴充套件專案中，
建置、執行與服務自訂 OpenBB Workspace 應用程式的完整生命週期。
它假設專案外殼已存在（建立骨架的說明請見 `develop_extension` skill）。

---

## 前置需求

請確認目前啟用的 Python 環境已安裝下列套件：

```
pip install openbb-core openbb-platform-api openbb-devtools
```

- `openbb-core` 提供 Router、Provider、OBBject 與 Fetcher base classes。
- `openbb-platform-api` 提供 `openbb-api` CLI，用於服務 backends，
  並為 OpenBB Workspace 自動產生 `widgets.json`。
- `openbb-devtools` 提供 `pytest`、cassette recording 與 QA utilities。

如果也需要 Python Interface wrapper（`obb` 物件），請安裝主套件：

```
pip install openbb --no-deps
```

---

## 架構概觀

OpenBB 建立在 FastAPI 與 Pydantic 之上。應用程式有兩個獨立
介面，共用核心邏輯與 models：

- **Python Interface**：將已安裝 routers 包裝成 `obb` Python package，
  並包含自動產生的 docstrings 與 function signatures。需要建置步驟
  （`openbb-build`）來產生 static assets。
- **REST API**：FastAPI instance，所有已安裝 routers 都可透過 HTTP 使用。
  可用 `from openbb_core.api.rest_api import app` 匯入，或用
  `uvicorn openbb_core.api.rest_api:app` 啟動。

應用程式是所有已安裝 extensions 的產物。若只有 `openbb-core`，
不會有 routers 或 endpoints；使用者可組合自己的套件集合。

### 主要類別

| 類別 | 匯入位置 | 用途 |
|---|---|---|
| `Router` | `openbb_core.app.router` | `fastapi.APIRouter` 的 subclass；定義 commands |
| `OBBject` | `openbb_core.app.model.obbject` | 標準 response object，包含 results、provider、warnings、extra |
| `Provider` | `openbb_core.provider.abstract.provider` | 為 provider interface 註冊 fetchers |
| `Fetcher` | `openbb_core.provider.abstract.fetcher` | TET pipeline：Transform query → Extract data → Transform data |
| `QueryParams` | `openbb_core.provider.abstract.query_params` | 輸入參數的 base class |
| `Data` | `openbb_core.provider.abstract.data` | 輸出資料 schemas 的 base class |

---

## Router 擴充套件（API endpoints）

Router extensions 是使用者面向的 endpoints，支援 REST API、MCP
與 Python Interface。

### 建立 Router

```python
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.router import Router

router = Router(prefix="", description="我的自訂擴充套件。")
```

最上層 API path prefix 由 `pyproject.toml` 中的 entry point name 決定，
不是由 `prefix` 參數決定。`prefix` 只用於 sub-routers。

```toml
[tool.poetry.plugins."openbb_core_extension"]
my_app = "my_package.routers.my_router:router"
```

Commands 會出現在 API 的 `/my_app/...` 與 Python 的 `obb.my_app.` 底下。

### Provider Interface endpoints

透過 model name 將 router command 連接到一個或多個 provider fetchers：

```python
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import ExtraParams, ProviderChoices, StandardParams
from openbb_core.app.query import Query
from pydantic import BaseModel

@router.command(model="MyModel")
async def my_command(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject[BaseModel]:
    """此 command 的說明。"""
    return await OBBject.from_query(Query(**locals()))
```

這四個參數與 `OBBject.from_query(Query(**locals()))` 回傳都是必要的，
而且必須完全依照範例使用。

### 基本 GET Endpoint

```python
@router.command(methods=["GET"])
async def hello() -> OBBject[str]:
    """OpenBB 問候範例。"""
    return OBBject(results="來自擴充套件的問候！")
```

### 基本 POST Endpoint

```python
from openbb_core.provider.abstract.data import Data

@router.command(methods=["POST"])
async def process(data: Data, some_param: str) -> OBBject:
    """處理提交的資料。"""
    return OBBject(results=data.model_dump())
```

### Decorator 參數

`@router.command` 接受：
- `model`：連結到 Provider fetchers 的 metamodel name
- `methods`：HTTP methods list，通常為 `["GET"]` 或 `["POST"]`
- `examples`：文件用的 `APIEx` 或 `PythonEx` list
- `deprecated`：deprecation notice
- `exclude_from_api`：僅適用於 Python Interface
- `no_validate`：略過 response validation，將輸出視為 `Any`
- `openapi_extra`：用於 inline `widget_config` 或 `mcp_config` 的 dictionary

### 直接使用 FastAPI APIRouter

透過 `router._api_router` 存取底層 FastAPI router：

```python
@router._api_router.get("/also_empty")
async def also_empty(param: str) -> str:
    """也為空。"""
    return "Hello world!"
```

---

## 從 FastAPI 轉換既有 apps

任何既有 FastAPI 應用程式都可以不改程式碼就變成 OpenBB extension。
在 `pyproject.toml` 中定義指向 FastAPI 或 APIRouter instance 的 entry point：

```toml
[tool.poetry.plugins."openbb_core_extension"]
my_app = "my_package.app:app"
```

安裝套件並建置 static assets：

```
pip install -e .
openbb-build
```

已知限制：
- Authorization hooks 不會注入 Python Interface
- Request-bound dependencies 或回傳 None 的 dependencies 不會被注入
- Python Interface 不支援 WebSockets
- Multi-method routes（同一路徑上的 GET + POST）可能無法正確產生

---

## 使用 openbb-api 服務（Workspace backends）

`openbb-api` CLI 會將 FastAPI instance 轉換成 OpenBB Workspace
backend，並自動產生 widget definitions。

### 基本用法

```
# 使用預設 OpenBB extensions 啟動
openbb-api

# 使用自訂 FastAPI 檔案啟動
openbb-api --app ./my_app.py --host 0.0.0.0 --port 8005

# Factory function 模式
openbb-api --app my_app.py:create_app --factory

# 自訂 FastAPI instance 名稱
openbb-api --app my_app.py --name my_app
```

預設值為 `--host 127.0.0.1 --port 6900`，若已被使用則退到下一個
可用 port。

### 主要參數

| 參數 | 說明 |
|---|---|
| `--app` | 含 FastAPI instance 的 Python 檔案路徑 |
| `--name` | FastAPI instance 的名稱（預設：`app`） |
| `--factory` | app name 為 factory function 時使用的 flag |
| `--editable` | 讓 `widgets.json` 可於 runtime 編輯 |
| `--no-build` | 不檢查更新，直接載入既有 `widgets.json` |
| `--exclude` | 要從 widgets 排除的 API paths JSON list |
| `--widgets-json` | `widgets.json` 的自訂路徑 |
| `--apps-json` | `workspace_apps.json` 的自訂路徑 |

所有剩餘 arguments 都會傳給 `uvicorn.run`。

---

## Inline widget 定義

Widget properties 可透過 `openapi_extra` 在程式碼中 inline 定義：

```python
@app.get(
    "/some_endpoint",
    openapi_extra={
        "widget_config": {
            "name": "自訂 Widget 名稱",
            "description": "覆寫 docstring 說明",
        }
    },
)
async def some_endpoint():
    """來自 docstring 的說明。"""
    pass
```

### 從 widgets 排除 endpoint

```python
@app.get(
    "/internal_endpoint",
    openapi_extra={"widget_config": {"exclude": True}},
)
async def internal_endpoint():
    return [{"label": "選項 1", "value": "choice1"}]
```

### Dropdown 參數

Dropdowns 會從 `Literal` types 自動產生：

```python
from typing import Literal

@app.get("/with_dropdown")
async def with_dropdown(
    choices: Literal["Choice 1", "Choice 2", "Choice 3"] = "Choice 3"
):
    pass
```

### Table 欄位定義

使用 Pydantic response models 自動產生 table column definitions：

```python
import datetime
from pydantic import BaseModel, Field

class MyData(BaseModel):
    date: datetime.date = Field(description="日期。")
    value: float = Field(description="數值。")

@app.get("/my_data")
async def my_data() -> list[MyData]:
    """具備 typed columns 的 widget。"""
    return [MyData(date=datetime.date.today(), value=42.0)]
```

### 依回傳型別對應 Widget 類型

| 回傳型別 | Widget 類型 |
|---|---|
| `list[dict]` 或 `list[BaseModel]` | Table（AgGrid） |
| `str` | Markdown |
| `dict`（搭配 `widget_config.type="chart"`） | Plotly Chart |
| `MetricResponseModel` | Metric |
| `PdfResponseModel` | PDF |

### 特殊 widgets 的 response models

```python
from openbb_platform_api.response_models import MetricResponseModel, PdfResponseModel

@app.get("/metric", response_model=MetricResponseModel)
async def metric():
    """Metric widget 範例。"""
    return dict(label="Revenue", value=12345, delta=5.67)

@app.get("/pdf", response_model=PdfResponseModel)
async def open_pdf(file_path: str):
    """開啟 PDF 文件。"""
    with open(file_path, "rb") as f:
        return dict(content=f.read())
```

### Plotly Chart Widget

```python
@app.get(
    "/chart",
    openapi_extra={"widget_config": {"type": "chart"}},
)
async def chart() -> dict:
    """Chart widget 範例。"""
    from plotly.graph_objs import Bar, Layout, Figure

    fig = Figure(
        data=[Bar(x=["A", "B", "C"], y=[1, 2, 3])],
        layout=Layout(title="我的 Chart", template="plotly_dark"),
    )
    return fig.to_plotly_json()
```

### 參數用的 JSON schema extra

為參數標註額外 widget configuration：

```python
from typing import Annotated
from fastapi import Query

my_param: Annotated[
    str,
    Query(
        title="我的標題",
        description="詳細 hover 文字",
        json_schema_extra={
            "x-widget_config": {
                "optionsEndpoint": "/my_choices_endpoint"
            }
        },
    ),
]
```

### Form input widget

建立連結到 table 的 input form：
- GET endpoint 定義 `widget_config.form_endpoint` 指向 POST route
- POST route 接受單一 Pydantic model argument

---

## OBBject 擴充套件（結果後處理）

以自訂 methods 擴充 `OBBject` response，可在 Python Interface 中存取。

### Class Accessor（具命名空間的 Methods）

```python
from openbb_core.app.model.extension import Extension

ext = Extension(name="my_tools", description="自訂結果工具。")

@ext.obbject_accessor
class MyTools:
    def __init__(self, obbject):
        self._obbject = obbject

    def summary(self):
        """回傳摘要。"""
        return self._obbject.to_dataframe().describe()
```

在 `pyproject.toml` 中註冊：

```toml
[tool.poetry.plugins."openbb_obbject_extension"]
my_tools = "my_package.obbject.my_ext:ext"
```

### Callable Accessor（類似 Property）

```python
ext = Extension(name="to_csv", description="將 results 轉換成 CSV。")

@ext.obbject_accessor
def to_csv(obbject):
    """轉換成 CSV 字串。"""
    return obbject.to_dataframe().to_csv()
```

### OBBject 輸出轉換 Methods

每個 `OBBject` 都有內建轉換 methods：
- `to_df()` / `to_dataframe()`：Pandas DataFrame
- `to_dict(orientation=...)`：Python dict
- `to_numpy()`：NumPy array
- `to_polars()`：Polars DataFrame（需要安裝 `polars`）
- `model_dump()`：完整物件的 dict
- `model_dump_json()`：序列化 JSON 字串

---

## OBBject plugins（return 前攔截器）

Plugins 會在 response 回傳前執行，並同時相容 REST API 與 Python Interface。
它們可以有條件地改變任何 command 的輸出。

**警告**：Plugins 被視為可能有風險。環境必須明確設定才允許使用。

在 `system_settings.json` 中：

```json
{
    "allow_on_command_output": true,
    "allow_mutable_extensions": true
}
```

### Plugin 設定

```python
from openbb_core.app.model.extension import Extension

plugin = Extension(
    name="my_plugin",
    description="在回傳前攔截輸出。",
    on_command_output=True,
    command_output_paths=["/my_router/my_command"],
    immutable=False,
    results_only=False,
)
```

主要參數：
- `on_command_output=True`：plugins 必填
- `command_output_paths`：要攔截的 endpoint paths list（None = 全部）
- `immutable=False`：設定為允許修改 response object
- `results_only=True`：只接收 `results` 部分，而不是完整 OBBject

### Plugin 程式碼

```python
@plugin.obbject_accessor
def my_plugin_func(obbject):
    """在 response 回傳前修改或檢查它。"""
    # 直接修改 obbject；不要回傳任何東西
    pass
```

---

## Charting 擴充套件（views）

將自訂 chart views 加到任何 router endpoint，當使用者設定 `chart=True`
時啟用。

### 結構

```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openbb_charting.core.openbb_figure import OpenBBFigure

class MyViews:
    """Router 的圖表 views。"""

    @staticmethod
    def my_router_my_command(**kwargs) -> tuple["OpenBBFigure", dict[str, Any]]:
        """my_command 的圖表。"""
        from openbb_charting.core.openbb_figure import OpenBBFigure

        data = kwargs["obbject_item"]
        fig = OpenBBFigure()
        # 使用 fig.add_*() methods 建立 chart
        content = fig.show(external=True).to_plotly_json()
        return fig, content
```

Method 命名慣例：`<router_name>_<command_name>`，需符合
lower_snake_case 的 route path。

在 `pyproject.toml` 中註冊：

```toml
[tool.poetry.plugins."openbb_charting_extension"]
my_router = "my_package.routers.my_views:MyViews"
```

### Views 中可用的 kwargs

| Key | 內容 |
|---|---|
| `obbject_item` | 已驗證的 results object |
| `charting_settings` | 使用者 charting preferences |
| `standard_params` | 標準 model parameters |
| `extra_params` | Provider-specific parameters |
| `provider` | 使用的 provider name |
| `extra` | 執行 metadata |

---

## Fetchers 中的 HTTP requests

使用內建工具，不要從零建立新的 clients。

### Query string helper

```python
from openbb_core.provider.utils.helpers import get_querystring

query_string = get_querystring(query.model_dump(), ["exclude_this_param"])
```

### 同步 Requests

```python
from openbb_core.provider.utils import make_request

response = make_request(url, headers=headers, params=params)
```

### Requests session

```python
from openbb_core.provider.utils.helpers import get_requests_session

session = get_requests_session()
```

### 非同步 Requests（AIOHTTP）

```python
from openbb_core.provider.utils.helpers import amake_request

response_json = await amake_request(url)
```

### 多 URL async requests

```python
from openbb_core.provider.utils.helpers import amake_requests

results = await amake_requests([url1, url2, url3])
```

### 自訂 response callback

```python
from io import StringIO
from pandas import DataFrame

results = []

async def response_callback(response, _):
    text = await response.text()
    data = DataFrame(StringIO(text), skiprows=2)
    results.append(data.to_dict("records"))

await amake_requests(url, response_callback=response_callback)
```

### Async session

```python
from openbb_core.provider.utils.helpers import get_async_requests_session

async with await get_async_requests_session() as session:
    async with await session.get(url) as response:
        data = await response.json()
```

### Async fetchers

Async fetchers 使用 `aextract_data`，不要使用 `extract_data`：

```python
@staticmethod
async def aextract_data(
    query: MyQueryParams,
    credentials: dict[str, str] | None,
    **kwargs: Any,
) -> list[dict]:
    """非同步資料擷取。"""
    ...
```

---

## 測試

### 內建 Fetcher Test

每個 Fetcher 都有 `.test()` method 可快速驗證：

```python
from my_package.providers.my_provider.models.my_model import MyFetcher

fetcher = MyFetcher()
fetcher.test({"symbol": "AAPL"}, {})  # 成功時回傳 None
```

### 使用 Cassettes 的 Unit Tests

安裝 dev tools，並使用 `pytest_recorder` 進行 HTTP cassette recording：

```
pip install openbb-devtools
pytest test_my_fetcher.py --record http
```

後續 test runs 會重播已錄製的 HTTP interactions。

### 執行 Tests

```
# 僅執行 unit tests
pytest tests/ -m "not integration"

# 僅執行 integration tests
pytest tests/ -m integration

# 所有 tests
pytest tests/
```

### 整合測試

若要執行 API integration tests，先啟動 local server：

```
uvicorn openbb_core.api.rest_api:app --host 0.0.0.0 --port 8000 --reload
```

---

## 安裝與建置

### 開發模式安裝

從專案根目錄執行：

```
pip install -e ".[dev]"
```

### 建置 Python Interface

安裝或移除 extensions 後，重新產生 static assets：

```
openbb-build
```

### 在 Python 中驗證

```python
from openbb import obb
# 你的 commands 會出現在 obb.<router_name>.<command_name>() 底下
```

### 作為 Workspace Backend 服務

```
openbb-api --app ./my_app.py --editable --host 0.0.0.0 --port 6900
```

---

## 工作流程摘要

當使用者要求「Build me a Workspace application that does X」時：

1. **Scaffold**：使用 `openbb-cookiecutter` 建立專案（見 `develop_extension` skill）。
2. **Remove**：移除範例檔案並清理 boilerplate。
3. **Implement fetchers**：在 `providers/<name>/models/` 為每個 data source
   實作 fetchers。
4. **Register fetchers**：在 `providers/<name>/__init__.py` 透過
   `fetcher_dict` 註冊 fetchers。
5. **Implement router commands**：在 `routers/<name>.py` 實作 router commands。
6. **Add widget config**：透過 `openapi_extra` 加入 Workspace-specific behavior。
7. **Update `pyproject.toml`**：更新 entry points 與 dependencies。
8. **Install**：使用 `pip install -e ".[dev]"` 安裝。
9. **Build**：使用 `openbb-build` 建置 static assets。
10. **Serve**：使用 `openbb-api` 服務，並在 OpenBB Workspace 中驗證 widgets。
11. **Test**：使用 `pytest` 與 fetcher `.test()` methods 測試。
