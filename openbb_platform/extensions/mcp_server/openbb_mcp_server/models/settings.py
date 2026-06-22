"""MCP Server 設定模型。"""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DEFAULT_SKILLS_DIR = str(Path(__file__).resolve().parent.parent / "skills")

DuplicateBehavior = Literal["warn", "error", "replace", "ignore"]


class MCPSettings(BaseModel):
    """MCP Server 設定模型。"""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        revalidate_instances="always",
        from_attributes=True,
        extra="allow",
    )

    # ===== OpenBB MCP 基本設定 =====
    api_prefix: str | None = Field(
        default=None,
        description="若有設定，會覆蓋 SystemService 提供的 API prefix；主要用於測試或特殊部署情境。",
        alias="OPENBB_MCP_API_PREFIX",
    )

    # 基本伺服器設定
    name: str = Field(
        default="OpenBB MCP",
        alias="OPENBB_MCP_NAME",
    )
    description: str = Field(
        default="""將所有 OpenBB REST 端點曝露為 MCP 工具。讓 LLM agent
可以查詢金融資料、執行篩選器，並使用與 REST client 相同的操作建立工作流程。""",
        alias="OPENBB_MCP_DESCRIPTION",
    )
    version: str | None = Field(
        default=None,
        description="伺服器版本。",
        alias="OPENBB_MCP_VERSION",
    )

    # 工具分類篩選
    default_tool_categories: list[str] = Field(
        default_factory=lambda: ["all"],
        description="啟動時預設啟用的工具分類。",
        alias="OPENBB_MCP_DEFAULT_TOOL_CATEGORIES",
    )
    allowed_tool_categories: list[str] | None = Field(
        default=None,
        description="若有設定，會將可用工具分類限制在此清單內。",
        alias="OPENBB_MCP_ALLOWED_TOOL_CATEGORIES",
    )

    # 工具探索設定
    enable_tool_discovery: bool = Field(
        default=False,
        description="""
            啟用工具探索，允許 agent 在執行期動態切換工具。
            多 client 或固定工具集部署可維持停用。
        """,
        alias="OPENBB_MCP_ENABLE_TOOL_DISCOVERY",
    )

    # 分頁設定
    list_page_size: int | None = Field(
        default=None,
        description="list 回應每頁最多回傳的 tools/resources/prompts 數量。"
        "None 代表停用分頁，並在單一回應中回傳所有項目。",
        alias="OPENBB_MCP_LIST_PAGE_SIZE",
    )

    # 回應設定
    describe_responses: bool = Field(
        default=False,
        description="在工具描述中包含回應型別。",
        alias="OPENBB_MCP_DESCRIBE_RESPONSES",
    )

    # Prompt 設定
    instructions: str | None = Field(
        default=None,
        description="MCP initialize 握手期間傳給 agent 的伺服器指令。"
        "設定後，這段文字會在任何工具或 prompt 被呼叫前送出。"
        "若未明確設定，會自動由 system prompt 內容填入。",
        alias="OPENBB_MCP_INSTRUCTIONS",
    )

    system_prompt_file: str | None = Field(
        default=None,
        description="包含伺服器 system prompt 的文字檔路徑。",
        alias="OPENBB_MCP_SYSTEM_PROMPT_FILE",
    )

    server_prompts_file: str | None = Field(
        default=None,
        description="包含伺服器 prompt template 的 JSON 檔案路徑。",
        alias="OPENBB_MCP_SERVER_PROMPTS_FILE",
    )

    default_skills_dir: str | None = Field(
        default=_DEFAULT_SKILLS_DIR,
        description="包含內建 skill prompt 檔案（.md/.txt）的目錄路徑。設為 None 或空字串可停用預設 skills 載入。",
        alias="OPENBB_MCP_DEFAULT_SKILLS_DIR",
    )

    # ===== FastMCP 核心設定 =====

    # 快取設定
    cache_expiration_seconds: float | None = Field(
        default=None,
        description="快取過期秒數；設為 0 可停用快取。",
        alias="OPENBB_MCP_CACHE_EXPIRATION_SECONDS",
    )

    # 重複項處理
    on_duplicate_tools: DuplicateBehavior | None = Field(
        default=None,
        description="註冊重複工具時的處理方式。",
        alias="OPENBB_MCP_ON_DUPLICATE_TOOLS",
    )

    on_duplicate_resources: DuplicateBehavior | None = Field(
        default=None,
        description="註冊重複 resources 時的處理方式。",
        alias="OPENBB_MCP_ON_DUPLICATE_RESOURCES",
    )

    on_duplicate_prompts: DuplicateBehavior | None = Field(
        default=None,
        description="註冊重複 prompts 時的處理方式。",
        alias="OPENBB_MCP_ON_DUPLICATE_PROMPTS",
    )

    # Resource 與元件設定
    resource_prefix_format: Literal["protocol", "path"] | None = Field(
        default=None,
        description="resource URI prefix 格式：'protocol'（prefix+protocol://path）或 'path'（protocol://prefix/path）。",
        alias="OPENBB_MCP_RESOURCE_PREFIX_FORMAT",
    )

    mask_error_details: bool | None = Field(
        default=None,
        description="若為 True，送往 client 前會隱藏使用者函式的錯誤細節。",
        alias="OPENBB_MCP_MASK_ERROR_DETAILS",
    )

    dependencies: list[str] | None = Field(
        default=None,
        description="要安裝到伺服器環境中的相依套件清單。",
        alias="OPENBB_MCP_DEPENDENCIES",
    )

    skills_reload: bool = Field(
        default=False,
        description="若為 True，skills providers 每次讀取時都會重新載入 skill 檔案，適合開發期間使用。",
        alias="OPENBB_MCP_SKILLS_RELOAD",
    )

    skills_providers: list[str] | None = Field(
        default=None,
        description="要載入的 vendor skill provider 短名稱清單（例如 ['claude', 'cursor']）。"
        "支援值：claude、cursor、vscode、copilot、codex、gemini、goose、opencode。",
        alias="OPENBB_MCP_SKILLS_PROVIDERS",
    )

    module_exclusion_map: dict[str, str] | None = Field(
        default=None,
        description="API tags 與 Python 模組名稱的 Key:Value 對應。" + "例如 {'econometrics': 'openbb_econometrics'}。",
        alias="OPENBB_MCP_MODULE_EXCLUSION_MAP",
    )
    deprecation_warnings: bool | None = Field(
        default=False,
        description="若為 True，會在 console 顯示 deprecation warnings。",
    )

    # ===== HTTP 傳輸設定 =====

    # Uvicorn 伺服器設定
    uvicorn_config: dict[str, Any] | None = Field(
        default_factory=lambda: {"host": "127.0.0.1", "port": "8001"},
        description="Uvicorn 伺服器的額外設定物件。"
        + "所有項目都會作為 kwargs 傳給 `mcp.run(uvicorn_config=uvicorn_config)`。",
        alias="OPENBB_MCP_UVICORN_CONFIG",
    )

    # 對外請求用的 HTTP client 設定
    httpx_client_kwargs: dict[str, Any] | None = Field(
        default_factory=dict,
        description="FastMCP 使用的非同步 httpx client 設定物件。"
        + "可在 'headers' 鍵下以字典加入自訂 headers。"
        + "所有項目都會直接傳給 FastMCP.from_fastapi(httpx_client_kwargs=httpx_client_kwargs)。",
        alias="OPENBB_MCP_HTTPX_CLIENT_KWARGS",
    )
    client_auth: tuple[str, str] | None = Field(
        default=None,
        description="""
        client 端基本驗證使用的 (username, password) tuple。
        若有提供，會傳給 httpx client 供下游請求使用。
        範例：OPENBB_MCP_CLIENT_AUTH='["user","pass"]'
        """,
        alias="OPENBB_MCP_CLIENT_AUTH",
    )
    server_auth: tuple[str, str] | None = Field(
        default=None,
        description="""
        server 端基本驗證使用的 (username, password) tuple。
        若有提供，MCP server 會要求傳入請求提供這組憑證。
        範例：OPENBB_MCP_SERVER_AUTH='["user","pass"]'
        """,
        alias="OPENBB_MCP_SERVER_AUTH",
    )

    @field_validator(
        "default_tool_categories",
        "allowed_tool_categories",
        "dependencies",
        "skills_providers",
        mode="before",
    )
    @classmethod
    def _split_list(cls, v):
        if isinstance(v, str):
            return [part.strip() for part in v.split(",") if part.strip()]
        return v

    @field_validator("httpx_client_kwargs", "client_auth", "server_auth", mode="before")
    @classmethod
    def _validate_json_or_tuple(cls, v):
        """驗證 JSON 或 tuple。"""
        if isinstance(v, str):
            if not v.strip():
                return None
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # 若不是合法 JSON，退回原始字串
                return v
        return v

    def get_fastmcp_kwargs(self) -> dict:
        """從設定中擷取 FastMCP 建構子參數。

        只回傳可直接傳給 FastMCP 建構子的非 None 參數。
        """
        fastmcp_fields = {
            "name": self.name,
            "instructions": self.instructions,
            "version": self.version,
            "cache_expiration_seconds": self.cache_expiration_seconds,
            "on_duplicate_tools": self.on_duplicate_tools,
            "on_duplicate_resources": self.on_duplicate_resources,
            "on_duplicate_prompts": self.on_duplicate_prompts,
            "resource_prefix_format": self.resource_prefix_format,
            "mask_error_details": self.mask_error_details,
            "dependencies": self.dependencies,
            "list_page_size": self.list_page_size,
        }

        # 只保留非 None 的值
        return {k: v for k, v in fastmcp_fields.items() if v is not None}

    def get_http_run_kwargs(self) -> dict:
        """擷取 FastMCP.run_http_async() 所需的 HTTP 執行參數。

        回傳包含 HTTP 傳輸設定的字典。
        """
        run_fields: dict = {}

        if self.uvicorn_config is not None:
            run_fields["uvicorn_config"] = self.uvicorn_config

        return run_fields

    def get_httpx_kwargs(self) -> dict:
        """擷取 httpx client 設定。

        回傳包含 httpx client 設定的字典。
        """
        kwargs = self.httpx_client_kwargs or {}
        if self.client_auth:
            kwargs["auth"] = self.client_auth
        return kwargs

    def __repr__(self) -> str:
        """回傳字串表示。"""
        return f"{self.__class__.__name__}\n\n" + "\n".join(f"{k}: {v}" for k, v in self.model_dump().items())

    def update(self, incoming: "MCPSettings"):
        """更新目前設定。"""
        self.__dict__.update(incoming.model_dump(exclude_none=True))
