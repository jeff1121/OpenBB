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
        description="If set, overrides the API prefix from SystemService. For testing or special cases.",
        alias="OPENBB_MCP_API_PREFIX",
    )

    # 基本伺服器設定
    name: str = Field(
        default="OpenBB MCP",
        alias="OPENBB_MCP_NAME",
    )
    description: str = Field(
        default="""All OpenBB REST endpoints exposed as MCP tools. Enables LLM agents
to query financial data, run screeners, and build workflows using
the exact same operations available to REST clients.""",
        alias="OPENBB_MCP_DESCRIPTION",
    )
    version: str | None = Field(
        default=None,
        description="Server version",
        alias="OPENBB_MCP_VERSION",
    )

    # 工具分類篩選
    default_tool_categories: list[str] = Field(
        default_factory=lambda: ["all"],
        description="Default active tool categories on startup",
        alias="OPENBB_MCP_DEFAULT_TOOL_CATEGORIES",
    )
    allowed_tool_categories: list[str] | None = Field(
        default=None,
        description="If set, restricts available tool categories to this list",
        alias="OPENBB_MCP_ALLOWED_TOOL_CATEGORIES",
    )

    # 工具探索設定
    enable_tool_discovery: bool = Field(
        default=False,
        description="""
            Enable tool discovery, allowing the agent to hot-swap tools at runtime.
            Disable for multi-client or fixed toolset deployments.
        """,
        alias="OPENBB_MCP_ENABLE_TOOL_DISCOVERY",
    )

    # 分頁設定
    list_page_size: int | None = Field(
        default=None,
        description="Maximum number of tools/resources/prompts returned per page in list responses. "
        "None disables pagination (all items returned in one response).",
        alias="OPENBB_MCP_LIST_PAGE_SIZE",
    )

    # 回應設定
    describe_responses: bool = Field(
        default=False,
        description="Include response types in tool descriptions",
        alias="OPENBB_MCP_DESCRIBE_RESPONSES",
    )

    # Prompt 設定
    instructions: str | None = Field(
        default=None,
        description="Server instructions sent to the agent during the MCP initialize handshake."
        " When set, this text is delivered before any tools or prompts are called."
        " If not explicitly set, it is auto-populated from the system prompt content.",
        alias="OPENBB_MCP_INSTRUCTIONS",
    )

    system_prompt_file: str | None = Field(
        default=None,
        description="Path to a text file containing the system prompt for the server",
        alias="OPENBB_MCP_SYSTEM_PROMPT_FILE",
    )

    server_prompts_file: str | None = Field(
        default=None,
        description="Path to a JSON file containing prompt templates for the server",
        alias="OPENBB_MCP_SERVER_PROMPTS_FILE",
    )

    default_skills_dir: str | None = Field(
        default=_DEFAULT_SKILLS_DIR,
        description="Path to a directory containing bundled skill prompt files (.md/.txt)."
        " Set to None or empty string to disable loading default skills.",
        alias="OPENBB_MCP_DEFAULT_SKILLS_DIR",
    )

    # ===== FastMCP 核心設定 =====

    # 快取設定
    cache_expiration_seconds: float | None = Field(
        default=None,
        description="Cache expiration time in seconds. set to 0 to disable caching.",
        alias="OPENBB_MCP_CACHE_EXPIRATION_SECONDS",
    )

    # 重複項處理
    on_duplicate_tools: DuplicateBehavior | None = Field(
        default=None,
        description="Behavior when duplicate tools are registered",
        alias="OPENBB_MCP_ON_DUPLICATE_TOOLS",
    )

    on_duplicate_resources: DuplicateBehavior | None = Field(
        default=None,
        description="Behavior when duplicate resources are registered",
        alias="OPENBB_MCP_ON_DUPLICATE_RESOURCES",
    )

    on_duplicate_prompts: DuplicateBehavior | None = Field(
        default=None,
        description="Behavior when duplicate prompts are registered",
        alias="OPENBB_MCP_ON_DUPLICATE_PROMPTS",
    )

    # Resource 與元件設定
    resource_prefix_format: Literal["protocol", "path"] | None = Field(
        default=None,
        description="Format for resource URI prefixes: 'protocol' (prefix+protocol://path) or 'path' (protocol://prefix/path)",
        alias="OPENBB_MCP_RESOURCE_PREFIX_FORMAT",
    )

    mask_error_details: bool | None = Field(
        default=None,
        description="If True, mask error details from user functions before sending to clients",
        alias="OPENBB_MCP_MASK_ERROR_DETAILS",
    )

    dependencies: list[str] | None = Field(
        default=None,
        description="list of dependencies to install in the server environment",
        alias="OPENBB_MCP_DEPENDENCIES",
    )

    skills_reload: bool = Field(
        default=False,
        description="If True, skills providers will reload skill files on every read (useful during development).",
        alias="OPENBB_MCP_SKILLS_RELOAD",
    )

    skills_providers: list[str] | None = Field(
        default=None,
        description="List of vendor skill provider short-names to load (e.g. ['claude', 'cursor']). "
        "Supported: claude, cursor, vscode, copilot, codex, gemini, goose, opencode.",
        alias="OPENBB_MCP_SKILLS_PROVIDERS",
    )

    module_exclusion_map: dict[str, str] | None = Field(
        default=None,
        description="Key:Value pairs mapping API Tags with their Python module names."
        + " Example, {'econometrics': 'openbb_econometrics'}",
        alias="OPENBB_MCP_MODULE_EXCLUSION_MAP",
    )
    deprecation_warnings: bool | None = Field(
        default=False,
        description="If True, show deprecation warnings in the console.",
    )

    # ===== HTTP 傳輸設定 =====

    # Uvicorn 伺服器設定
    uvicorn_config: dict[str, Any] | None = Field(
        default_factory=lambda: {"host": "127.0.0.1", "port": "8001"},
        description="Additional configuration object for the Uvicorn server."
        + " All items are passed as kwargs to `mcp.run(uvicorn_config=uvicorn_config)`",
        alias="OPENBB_MCP_UVICORN_CONFIG",
    )

    # 對外請求用的 HTTP client 設定
    httpx_client_kwargs: dict[str, Any] | None = Field(
        default_factory=dict,
        description="Configuration object for async httpx client used by FastMCP."
        + " Add custom headers as a dictionary under the 'headers' key."
        + " All items passed directly to FastMCP.from_fastapi(httpx_client_kwargs=httpx_client_kwargs)",
        alias="OPENBB_MCP_HTTPX_CLIENT_KWARGS",
    )
    client_auth: tuple[str, str] | None = Field(
        default=None,
        description="""
        A tuple of (username, password) for client-side basic authentication.
        If provided, this will be passed to the httpx client for downstream requests.
        Example: OPENBB_MCP_CLIENT_AUTH='["user","pass"]'
        """,
        alias="OPENBB_MCP_CLIENT_AUTH",
    )
    server_auth: tuple[str, str] | None = Field(
        default=None,
        description="""
        A tuple of (username, password) for server-side basic authentication.
        If provided, the MCP server will require incoming requests to provide these credentials.
        Example: OPENBB_MCP_SERVER_AUTH='["user","pass"]'
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
        return f"{self.__class__.__name__}\n\n" + "\n".join(
            f"{k}: {v}" for k, v in self.model_dump().items()
        )

    def update(self, incoming: "MCPSettings"):
        """更新目前設定。"""
        self.__dict__.update(incoming.model_dump(exclude_none=True))
