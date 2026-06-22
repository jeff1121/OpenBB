"""OpenBB MCP Server。"""

# pylint: disable=C0302, R0912, W0212

import asyncio
import json
import os
import re
import signal
import sys
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastmcp import FastMCP
from fastmcp.prompts import PromptArgument
from fastmcp.prompts.function_prompt import FunctionPrompt
from fastmcp.server.context import Context
from fastmcp.server.providers.openapi import (
    OpenAPIResource,
    OpenAPIResourceTemplate,
    OpenAPITool,
)
from fastmcp.server.providers.skills import (
    ClaudeSkillsProvider,
    CodexSkillsProvider,
    CopilotSkillsProvider,
    CursorSkillsProvider,
    GeminiSkillsProvider,
    GooseSkillsProvider,
    OpenCodeSkillsProvider,
    SkillProvider,
    SkillsDirectoryProvider,
    VSCodeSkillsProvider,
)
from fastmcp.server.transforms import PromptsAsTools, ResourcesAsTools
from fastmcp.utilities.json_schema import compress_schema
from fastmcp.utilities.logging import get_logger
from fastmcp.utilities.openapi import HTTPRoute
from openbb_core.api.rest_api import app
from openbb_core.app.service.system_service import SystemService
from pydantic import Field
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from openbb_mcp_server.models.category_index import CategoryIndex
from openbb_mcp_server.models.mcp_config import (
    ArgumentDefinitionModel,
    is_valid_mcp_config,
)
from openbb_mcp_server.models.prompts import StaticPrompt
from openbb_mcp_server.models.settings import MCPSettings
from openbb_mcp_server.models.tools import CategoryInfo, SubcategoryInfo, ToolInfo
from openbb_mcp_server.service.mcp_service import MCPService
from openbb_mcp_server.utils.app_import import parse_args
from openbb_mcp_server.utils.fastapi import (
    get_api_prefix,
    process_fastapi_routes_for_mcp,
)

logger = get_logger(__name__)

_VENDOR_SKILLS_PROVIDERS = {
    "claude": ClaudeSkillsProvider,
    "cursor": CursorSkillsProvider,
    "vscode": VSCodeSkillsProvider,
    "copilot": CopilotSkillsProvider,
    "codex": CodexSkillsProvider,
    "gemini": GeminiSkillsProvider,
    "goose": GooseSkillsProvider,
    "opencode": OpenCodeSkillsProvider,
}


def _extract_brief_description(full_description: str) -> str:
    """擷取詳細 API 文件之前的簡短描述。"""
    if not full_description:
        return "No description available"
    brief, *_ = re.split(r"\n{2,}\*\*(?:Query Parameters|Responses):", full_description, maxsplit=1)
    return brief.strip() or "No description available"


def _get_mcp_config_from_route(fa_route: APIRoute | None) -> dict:
    """從 FastAPI 路由的 `openapi_extra` 擷取 `mcp_config` 字典。"""
    if fa_route is None:
        return {}
    extra = fa_route.openapi_extra or {}
    cfg = extra.get("mcp_config") or extra.get("x-mcp") or {}
    if isinstance(cfg, dict):
        return cfg
    return {}


def _strip_api_prefix(path: str, api_prefix: str) -> str:
    """從絕對路徑中移除精確的 `api_prefix`（來自 SystemService）。

    回傳不含前導斜線的剩餘路徑。
    """
    if not path:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    remainder = path[len(api_prefix) :] if api_prefix and path.startswith(api_prefix) else path
    return remainder.lstrip("/")


def _read_system_prompt_file(file_path: str) -> str | None:
    """從文字檔讀取 system prompt 內容。

    若檔案不存在或無法讀取，則回傳 None。
    """
    try:
        prompt_path = Path(file_path)
        if prompt_path.exists() and prompt_path.is_file():
            return prompt_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning("Could not read system prompt file '%s': %s", file_path, e)
    return None


def _build_runtime_middleware() -> list:
    """建立與 `FastMCP.run(middleware=...)` 相容的 middleware 物件。"""
    cors = SystemService().system_settings.api_settings.cors

    return [
        Middleware(
            CORSMiddleware,
            allow_origins=cors.allow_origins,
            allow_methods=cors.allow_methods,
            allow_headers=cors.allow_headers,
            allow_credentials=True,
            expose_headers=["Mcp-Session-Id"],
        )
    ]


def _setup_file_system_prompt(mcp: FastMCP, settings: MCPSettings) -> None:
    """從檔案載入 system prompt，並以 prompt 與 resource 形式曝露。"""
    system_prompt_content = _read_system_prompt_file(settings.system_prompt_file or "")

    if not system_prompt_content:
        return

    def system_prompt_func() -> str:
        """回傳設定好的 system prompt。"""
        return system_prompt_content

    mcp.add_prompt(
        FunctionPrompt.from_function(
            system_prompt_func,
            name="system_prompt",
            description="這是 MCP Server 的 system prompt。"
            + "若你是連線到此 server 的 agent，"
            + "請仔細閱讀，以理解如何互動並使用 MCP 功能。"
            + "這個 prompt 會提供必要的操作指引，"
            + "協助有效使用此 server 提供的工具與 resources。",
            tags={"system"},
        )
    )

    if not mcp.instructions:
        mcp.instructions = system_prompt_content

    @mcp.resource("resource://system_prompt")
    def system_prompt_resource() -> str:
        """回傳 system prompt resource 內容。"""
        return system_prompt_func()


def _add_prompts_from_json(mcp: FastMCP, settings: MCPSettings) -> None:
    """從 `server_prompts_file` 載入 prompts，並註冊到 mcp。"""
    if not settings.server_prompts_file:
        return

    try:
        with open(settings.server_prompts_file, encoding="utf-8") as f:
            prompts_json: list = json.load(f) or []
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to load prompts from JSON file: %s", e)
        return

    prompts_added: list = []
    for prompt_def in prompts_json:
        prompt_name = prompt_def.get("name", "")

        if not prompt_name:
            logger.error("Skipping prompt definition without a name: %s", prompt_def)
            continue

        prompt_description = prompt_def.get("description", "")

        if not prompt_description:
            logger.error("Skipping prompt definition without a description: %s", prompt_def)
            continue

        prompt_content = prompt_def.get("content", "")

        if not prompt_content:
            logger.error("Skipping prompt definition without content: %s", prompt_def)
            continue

        if not isinstance(prompt_content, str):
            logger.error(
                "Skipping prompt definition with invalid content type. Expected string, got: %s",
                prompt_def,
            )
            continue

        prompt_arguments_def = prompt_def.get("arguments", [])
        arguments: list = []

        argument_defaults: dict = {}

        if prompt_arguments_def:
            for arg in prompt_arguments_def:
                try:
                    validated_arg = ArgumentDefinitionModel(**arg).model_dump(exclude_none=True)
                    arguments.append(
                        PromptArgument(
                            name=validated_arg["name"],
                            description=validated_arg["description"],
                            required="default" not in validated_arg,
                        )
                    )
                    if "default" in validated_arg:
                        argument_defaults[validated_arg["name"]] = validated_arg["default"]
                except Exception as e:  # pylint: disable=broad-except
                    logger.error(
                        "Skipping argument definition in server prompt, %s, due to error: %s\nDefinition: %s",
                        prompt_name,
                        e,
                        arg,
                    )
                    continue

        prompt_tags = prompt_def.get("tags", [])
        tags = set(prompt_tags) if isinstance(prompt_tags, list | set) else set()
        tags.add("server")
        mcp.add_prompt(
            StaticPrompt(
                name=prompt_name,
                description=prompt_description,
                content=prompt_content,
                arguments=arguments if arguments else None,
                argument_defaults=argument_defaults,
                tags=tags,
            )
        )
        prompts_added.append(prompt_name)

    logger.info("Successfully added %d server prompts.", len(prompts_added))


def _add_inline_prompts(mcp: FastMCP, prompt_definitions: list) -> None:
    """將路由設定中的 inline prompts 註冊到 mcp。"""
    inline_prompts_added: list = []
    for prompt_def in prompt_definitions:
        try:
            prompt_name = prompt_def["name"]
            prompt_description = prompt_def["description"]
            prompt_content = prompt_def["content"]
            prompt_arguments_def = prompt_def.get("arguments", [])
            prompt_tags = prompt_def.get("tags", [])
            tool = prompt_def.get("tool", "")

            tags = set(prompt_tags) if isinstance(prompt_tags, list | set) else set()
            tags.add("route-specific")
            tags.add(tool)

            arguments = []
            argument_defaults: dict = {}
            for arg in prompt_arguments_def:
                arguments.append(
                    PromptArgument(
                        name=arg["name"],
                        description=arg.get("description"),
                        required="default" not in arg,
                    )
                )
                if "default" in arg:
                    argument_defaults[arg["name"]] = arg["default"]

            mcp.add_prompt(
                StaticPrompt(
                    name=prompt_name,
                    description=prompt_description,
                    arguments=arguments,
                    argument_defaults=argument_defaults,
                    tags=tags,
                    content=prompt_content,
                )
            )
            inline_prompts_added.append(prompt_name)

        except (KeyError, TypeError) as e:
            logger.warning(
                "Skipping invalid prompt definition due to error: %s\nDefinition: %s",
                e,
                prompt_def,
            )
            continue

    if inline_prompts_added:
        logger.info("Successfully added %d inline prompts.", len(inline_prompts_added))


def _add_skills_default_prompt(mcp: FastMCP) -> None:
    """在未設定檔案型 prompt 時，註冊預設的 skills-aware system prompt。"""
    _default_system_content = (
        "This server includes bundled skill guides that teach you how to "
        "use advanced OpenBB Platform capabilities. "
        "Use list_resources() to discover available skills at skill://<name>/SKILL.md URIs."
    )

    def _default_system_prompt() -> str:
        """回傳預設的 system prompt 內容。"""
        return _default_system_content

    mcp.add_prompt(
        FunctionPrompt.from_function(
            _default_system_prompt,
            name="system_prompt",
            description=("System prompt with guidance on discovering and using this server's bundled skills and tools."),
            tags={"system"},
        )
    )

    if not mcp.instructions:
        mcp.instructions = _default_system_content

    logger.info("Added default system prompt with skill awareness nudge.")


# pylint: disable=R0914,R0915
def create_mcp_server(
    settings: MCPSettings,
    fastapi_app: FastAPI,
    httpx_kwargs: dict | None = None,
    auth: Any | None = None,
) -> FastMCP:
    """根據 FastAPI app 實例建立並設定 FastMCP 伺服器。

    參數
    ----------
    settings
        包含伺服器設定選項的 MCPSettings 實例。
    fastapi_app
        要用來建立伺服器的 FastAPI app 實例。
    httpx_kwargs
        傳給 httpx client 的可選關鍵字參數。
    auth
        伺服器要使用的驗證提供者。
        應為有效的 `FastMCP.server.auth.AuthProvider` 實例，
        或任何 FastMCP `auth` 參數可接受的物件。

    回傳
    -------
    FastMCP
        設定完成的 FastMCP 伺服器實例。
    """
    auth_provider = None
    if auth and isinstance(auth, list | tuple) and len(auth) == 2 and all(auth):
        # pylint: disable=import-outside-toplevel
        from .auth import get_auth_provider

        auth_provider = get_auth_provider(settings)

    category_index = CategoryIndex()
    _enabled_tools: set[str] = set()

    # 單次處理：過濾 routes、建立 route maps，並建立 lookup 字典
    processed_data = process_fastapi_routes_for_mcp(fastapi_app, settings)

    route_lookup = processed_data.route_lookup
    api_prefix = get_api_prefix(settings)
    tool_prompts_map: dict = {}

    for prompt_def in processed_data.prompt_definitions:
        tool_name = prompt_def.get("tool")

        if tool_name:
            if tool_name not in tool_prompts_map:
                tool_prompts_map[tool_name] = []
            tool_prompts_map[tool_name].append(
                {
                    "name": prompt_def.get("name"),
                    "description": prompt_def.get("description"),
                    "arguments": prompt_def.get("arguments", []),
                }
            )

    # pylint: disable=R0912
    def customize_components(
        route: HTTPRoute,
        component: OpenAPITool | OpenAPIResource | OpenAPIResourceTemplate,
    ) -> None:
        """依每個路由的設定套用命名、tags、啟用/停用與 resource MIME type。"""
        # 回查對應的 FastAPI route，以讀取 openapi_extra
        fa_route = route_lookup.get((route.path, route.method.upper()))
        mcp_cfg = _get_mcp_config_from_route(fa_route)

        if (exc := is_valid_mcp_config(mcp_cfg)) and isinstance(exc, Exception):
            logger.error(
                "Invalid MCP config found in route, '%s %s'."
                + " Skipping tool customization because of validation error ->\n%s",
                route.method,
                route.path,
                exc,
            )
            mcp_cfg = {}

        # 使用精確的 API prefix 判定 category / subcategory / tool
        local_path = _strip_api_prefix(route.path, api_prefix)
        segments = [seg for seg in local_path.split("/") if seg and "{" not in seg]

        if segments:
            category = segments[0]
            if len(segments) == 1:
                subcategory = "general"
                tool = segments[0]
            elif len(segments) == 2:
                subcategory = "general"
                tool = segments[1]
            else:
                subcategory = segments[1]
                tool = "_".join(segments[2:])
        else:
            category, subcategory, tool = "general", "general", "root"

        # 名稱覆寫
        if name := mcp_cfg.get("name"):
            component.name = name
        else:
            component.name = f"{category}_{subcategory}_{tool}" if subcategory != "general" else f"{category}_{tool}"

        # 標籤
        component.tags.add(category)
        extra_tags = mcp_cfg.get("tags") or []
        for t in extra_tags:
            component.tags.add(str(t))

        # 壓縮 schemas（僅適用於具有這些屬性的 OpenAPITool）
        if isinstance(component, OpenAPITool):
            if component.parameters:
                component.parameters = compress_schema(component.parameters)
            if hasattr(component, "output_schema"):
                output_schema = getattr(component, "output_schema", None)
                if output_schema is not None:
                    component.output_schema = compress_schema(output_schema)

        # 修剪描述內容
        describe_override = mcp_cfg.get("describe_responses")
        if describe_override is False or (describe_override is None and not settings.describe_responses):
            component.description = _extract_brief_description(component.description or "")

        # 將 prompt 中繼資料附加到工具描述中
        if isinstance(component, OpenAPITool):
            prompts = tool_prompts_map.get(component.name)
            if prompts:
                prompt_metadata_str = "\n\n**關聯 Prompts:**"
                for p in prompts:
                    prompt_metadata_str += f"\n- **{p['name']}**: {p['description']}"
                    if p["arguments"]:
                        prompt_metadata_str += "\n  - 參數：" + ", ".join([f"`{arg['name']}`" for arg in p["arguments"]])
                component.description = (component.description or "") + prompt_metadata_str

        # 啟用/停用：先看逐路由覆寫，再看分類預設值
        enable_override = mcp_cfg.get("enable")
        if isinstance(enable_override, bool):
            should_enable = enable_override
        elif "all" in settings.default_tool_categories or any(
            tag in settings.default_tool_categories for tag in getattr(component, "tags", set())
        ):
            should_enable = True
        else:
            should_enable = False

        if should_enable and isinstance(component, OpenAPITool):
            _enabled_tools.add(component.name)

        # Resource 專用的 MIME type
        if isinstance(component, OpenAPIResource):
            mime_type = mcp_cfg.get("mime_type")
            if isinstance(mime_type, str) and mime_type:
                component.mime_type = mime_type

        # 將工具註冊進分類索引，供探索瀏覽使用
        if isinstance(component, OpenAPITool):
            category_index.register(
                category=category,
                subcategory=subcategory,
                tool_name=component.name,
                description=component.description or "",
            )

    # 若有提供，從 settings/kwargs 擷取 httpx_client_kwargs
    httpx_client_kwargs = httpx_kwargs or settings.get_httpx_kwargs()

    # 僅取得 FastMCP 建構子參數（不含 uvicorn_config、httpx_client_kwargs）
    fastmcp_kwargs = settings.get_fastmcp_kwargs()

    # 根據處理後的 FastAPI app 建立 MCP 伺服器。
    mcp = FastMCP.from_fastapi(
        app=fastapi_app,  # app 已原地修改
        mcp_component_fn=customize_components,
        route_maps=processed_data.route_maps,
        httpx_client_kwargs=httpx_client_kwargs,
        auth=auth_provider,
        **fastmcp_kwargs,
    )

    # 先停用所有非管理工具，再有選擇地重新啟用。
    all_registered = category_index.all_tool_names()
    if all_registered:
        mcp.disable(names=all_registered)

    if settings.enable_tool_discovery:
        # 探索模式：所有工具預設保持停用。
        # Agent 會在各自 session 中透過
        # activate_tools / activate_category 逐步啟用需要的工具。
        pass
    elif _enabled_tools:
        # 固定工具集模式：重新啟用符合
        # 逐路由覆寫或 default_tool_categories 的工具。
        mcp.enable(names=_enabled_tools)

    # 若有設定 system prompt，則加入
    if settings.system_prompt_file:
        _setup_file_system_prompt(mcp, settings)

    # 若設定中有 prompts JSON 檔，則載入之
    _add_prompts_from_json(mcp, settings)

    # 加入路由設定中的 inline prompts
    _add_inline_prompts(mcp, processed_data.prompt_definitions)

    # 透過 SkillsDirectoryProvider 載入內建 skills
    _bundled_skills_loaded = False
    if settings.default_skills_dir:
        skills_dir = Path(settings.default_skills_dir)
        if skills_dir.is_dir():
            mcp.add_provider(
                SkillsDirectoryProvider(
                    roots=skills_dir,
                    reload=settings.skills_reload,
                )
            )
            _bundled_skills_loaded = True
            logger.info("Loaded bundled skills from '%s'", skills_dir)

    # 載入使用者設定的 vendor skills providers
    if settings.skills_providers:
        for provider_name in settings.skills_providers:
            key = provider_name.lower().strip()
            provider_cls = _VENDOR_SKILLS_PROVIDERS.get(key)
            if provider_cls:
                mcp.add_provider(provider_cls(reload=settings.skills_reload))
                logger.info("Loaded vendor skills provider: '%s'", key)
            else:
                logger.warning(
                    "Unknown skills provider '%s'. Supported: %s",
                    key,
                    ", ".join(_VENDOR_SKILLS_PROVIDERS),
                )

    # 若已載入任何 skills，且未設定自訂 system prompt，
    # 則加入簡短的預設 system prompt，引導 agent 探索這些 skills。
    _skills_loaded = _bundled_skills_loaded or bool(settings.skills_providers)
    if _skills_loaded and not settings.system_prompt_file:
        _add_skills_default_prompt(mcp)

    # 若啟用探索功能，則加入管理/探索工具
    if settings.enable_tool_discovery:

        @mcp.tool(tags={"admin"})
        def available_categories() -> list[CategoryInfo]:
            """列出可用的工具分類與子分類，以及各自的工具數量。"""
            categories = category_index.get_categories()
            return [
                CategoryInfo(
                    name=category_name,
                    subcategories=[
                        SubcategoryInfo(name=subcat_name, tool_count=len(tool_names))
                        for subcat_name, tool_names in sorted(subcategories.items())
                    ],
                    total_tools=sum(len(tool_names) for tool_names in subcategories.values()),
                )
                for category_name, subcategories in sorted(categories.items())
            ]

        @mcp.tool(tags={"admin"})
        async def available_tools(
            category: Annotated[str, Field(description="要列出的工具分類")],
            subcategory: Annotated[
                str | None,
                Field(description="可選的子分類篩選條件；分類直屬工具請使用 'general'。"),
            ] = None,
        ) -> list[ToolInfo]:
            """列出特定分類與子分類中的工具。"""
            cat_data = category_index.get_subcategories(category)

            if cat_data is None:
                available = list(category_index.get_categories().keys())
                raise ValueError(f"找不到分類 '{category}'。可用分類：{', '.join(sorted(available))}")

            if subcategory:
                names = category_index.get_subcategory_names(category, subcategory)
                if not names:
                    raise ValueError(
                        f"分類 '{category}' 中找不到子分類 '{subcategory}'。"
                        f"可用子分類：{', '.join(sorted(cat_data.keys()))}"
                    )
            else:
                names = category_index.get_category_names(category)

            # 從 FastMCP 目前的工具清單解析啟用狀態
            active_tools = await mcp.list_tools()
            active_names = {t.name for t in active_tools}

            # 建立描述：若可取得即時工具物件則優先使用，
            # 否則退回索引中的快取短描述。
            tool_map = {t.name: t for t in active_tools}
            results: list[ToolInfo] = []
            for name in sorted(names):
                if name in tool_map:
                    desc = _extract_brief_description(tool_map[name].description or "")
                else:
                    desc = category_index.get_description(name)
                results.append(ToolInfo(name=name, active=name in active_names, description=desc))
            return results

        @mcp.tool(tags={"admin"})
        async def activate_tools(
            tool_names: Annotated[list[str], Field(description="要啟用的工具名稱")],
            ctx: Context,
        ) -> str:
            """為目前 session 啟用一個或多個工具。"""
            valid = [n for n in tool_names if category_index.has_tool(n)]
            invalid = [n for n in tool_names if not category_index.has_tool(n)]
            if valid:
                await ctx.enable_components(names=set(valid))
            parts: list[str] = []
            if valid:
                parts.append(f"已啟用：{', '.join(valid)}")
            if invalid:
                parts.append(f"找不到：{', '.join(invalid)}")
            return " ".join(parts) or "沒有處理任何工具。"

        @mcp.tool(tags={"admin"})
        async def deactivate_tools(
            tool_names: Annotated[list[str], Field(description="要停用的工具名稱")],
            ctx: Context,
        ) -> str:
            """為目前 session 停用一個或多個工具。"""
            valid = [n for n in tool_names if category_index.has_tool(n)]
            invalid = [n for n in tool_names if not category_index.has_tool(n)]
            if valid:
                await ctx.disable_components(names=set(valid))
            parts: list[str] = []
            if valid:
                parts.append(f"已停用：{', '.join(valid)}")
            if invalid:
                parts.append(f"找不到：{', '.join(invalid)}")
            return " ".join(parts) or "沒有處理任何工具。"

        @mcp.tool(tags={"admin"})
        async def activate_category(
            category: Annotated[str, Field(description="要啟用所有工具的分類名稱")],
            ctx: Context,
            subcategory: Annotated[
                str | None,
                Field(description="可選的子分類，用於縮小啟用範圍"),
            ] = None,
        ) -> str:
            """為目前 session 啟用某個分類（或子分類）的所有工具。"""
            if subcategory:
                names = category_index.get_subcategory_names(category, subcategory)
            else:
                names = category_index.get_category_names(category)
            if not names:
                available = list(category_index.get_categories().keys())
                scope = f"'{category}'" + (f"/'{subcategory}'" if subcategory else "")
                raise ValueError(f"{scope} 中找不到工具。可用分類：{', '.join(sorted(available))}")
            await ctx.enable_components(names=names)
            scope = f"'{category}'" + (f"/'{subcategory}'" if subcategory else "")
            return f"已在 {scope} 啟用 {len(names)} 個工具：{', '.join(sorted(names))}"

    # 透過 transforms 將 prompts 與 resources 轉為工具，
    # 讓只有工具介面的 client 也能列出/渲染 prompts 與列出/讀取 resources。
    mcp.add_transform(PromptsAsTools(mcp))
    mcp.add_transform(ResourcesAsTools(mcp))

    @mcp.tool(tags={"resource", "admin"})
    async def install_skill(
        skill_name: Annotated[
            str,
            Field(
                description=("skill 名稱（會作為目錄名稱）。必須是合法目錄名稱（小寫、底線）。"),
            ),
        ],
        files: Annotated[
            dict[str, str],
            Field(
                description=(
                    "skill 目錄的 filename -> content 字典。"
                    "必須包含作為主檔案的 'SKILL.md'。"
                    "也可包含 templates、examples 或設定片段等支援檔案"
                    "（例如 'pyproject.toml.template'、'example.py'）。"
                ),
            ),
        ],
        target: Annotated[
            str,
            Field(
                description=(
                    "要安裝到的目標 skills provider。"
                    "伺服器內建 skills 目錄請使用 'bundled'，"
                    "或使用 vendor 名稱：" + ", ".join(f"'{k}'" for k in _VENDOR_SKILLS_PROVIDERS) + "。"
                ),
            ),
        ] = "bundled",
    ) -> dict:
        """將 skill（SKILL.md 與其支援檔案）安裝到 SkillsDirectoryProvider。

        若需要會建立 skill 目錄、寫入所有檔案，
        並將新 skill 註冊到目標 provider，
        使其可立即透過 `list_resources` / `read_resource` 使用。
        """
        if "SKILL.md" not in files:
            raise ValueError("'files' 字典必須包含作為主 skill 檔案的 'SKILL.md' 項目。")

        # 找出目標 SkillsDirectoryProvider
        target_key = target.lower().strip()
        target_provider: SkillsDirectoryProvider | None = None

        for provider in mcp.providers:
            if not isinstance(provider, SkillsDirectoryProvider):
                continue

            if target_key == "bundled":
                if settings.default_skills_dir:
                    bundled_root = Path(settings.default_skills_dir).resolve()
                    if bundled_root in provider._roots:  # noqa: SLF001
                        target_provider = provider
                        break
            else:
                vendor_cls = _VENDOR_SKILLS_PROVIDERS.get(target_key)
                if vendor_cls and isinstance(provider, vendor_cls):
                    target_provider = provider
                    break

        if target_provider is None:
            available = ["bundled"]
            for p in mcp.providers:
                for vendor_name, vendor_cls in _VENDOR_SKILLS_PROVIDERS.items():
                    if isinstance(p, vendor_cls):
                        available.append(vendor_name)
            raise ValueError(f"找不到或尚未載入目標 provider '{target}'。可用目標：{', '.join(available)}")

        if not target_provider._roots:  # noqa: SLF001
            raise ValueError(f"目標 provider '{target}' 未設定 root 目錄。")

        # 使用第一個 root 目錄進行寫入
        root_dir = target_provider._roots[0]  # noqa: SLF001
        skill_dir = root_dir / skill_name

        # 建立目錄並寫入所有檔案
        skill_dir.mkdir(parents=True, exist_ok=True)
        written_files: list[str] = []
        for filename, content in files.items():
            file_path = skill_dir / filename
            # 若檔名包含路徑分隔符，則建立子目錄
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            written_files.append(filename)

        # 將新 skill 註冊到 provider
        already_loaded = {
            p._skill_path.name  # noqa: SLF001
            for p in target_provider.providers
            if hasattr(p, "_skill_path")
        }

        if skill_name not in already_loaded:
            new_skill_provider = SkillProvider(skill_path=skill_dir)
            target_provider.providers.append(new_skill_provider)
            action = "Installed"
        else:
            # Skill 已存在：重新探索以載入更新後的內容
            target_provider._discover_skills()  # noqa: SLF001
            action = "Updated"

        logger.info(
            "%s skill '%s' (%d files) in %s provider (root: %s)",
            action,
            skill_name,
            len(written_files),
            target,
            root_dir,
        )

        return {
            "status": action.lower(),
            "skill_name": skill_name,
            "target": target,
            "path": str(skill_dir),
            "files_written": written_files,
            "uri": f"skill://{skill_name}/SKILL.md",
        }

    return mcp


class SSEShutdownWrapper:
    """在 SSE 連線關閉時優雅處理的 ASGI middleware。"""

    def __init__(self, asgi_app: ASGIApp):
        """初始化 SSEShutdownWrapper。"""
        self.asgi_app = asgi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """處理傳入的 ASGI 請求。"""
        if scope["type"] != "http":
            await self.asgi_app(scope, receive, send)
            return

        # 檢查這是否為 SSE 端點
        path = scope.get("path", "")

        if not path.endswith("/sse/"):
            await self.asgi_app(scope, receive, send)
            return

        # 包裝 send，以便在關閉時優雅處理
        response_started = False

        async def safe_send(message):
            """包裝 send 函式，以便在關閉時優雅處理。"""
            nonlocal response_started

            try:
                if message["type"] == "http.response.start":
                    response_started = True
                    await send(message)
                elif message["type"] == "http.response.body":
                    await send(message)
            except (ConnectionResetError, ConnectionAbortedError):
                # client 已中斷連線，直接忽略
                pass
            except RuntimeError as e:
                if "Expected ASGI message" in str(e):
                    # 關閉期間發生 ASGI 協定違規，改以優雅方式處理
                    if not response_started:
                        # 若尚未送出 response start，先補送正確的起始回應
                        await send(
                            {
                                "type": "http.response.start",
                                "status": 200,
                                "headers": [(b"content-type", b"text/plain")],
                            }
                        )
                        await send(
                            {
                                "type": "http.response.body",
                                "body": b"Connection closed",
                                "more_body": False,
                            }
                        )
                else:
                    raise

        await self.asgi_app(scope, receive, safe_send)


async def stdio_main(mcp_server):
    """以 STDIO 模式執行 MCP 伺服器，並處理系統訊號。"""
    loop = asyncio.get_running_loop()

    def signal_handler():
        """收到訊號時立即結束程序。"""
        logger.info("Shutdown signal received. Terminating process.")
        os._exit(0)  # pylint: disable=protected-access

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    logger.info("Starting OpenBB MCP Server in STDIO mode. Press Ctrl+C to stop.")

    await loop.run_in_executor(None, mcp_server.run, "stdio")


def main():
    """以擴充的 FastAPI app 匯入能力啟動 OpenBB MCP 伺服器。"""
    args = parse_args()
    mcp_service = MCPService()
    # 收集已解析參數中的所有命令列覆寫值
    cli_overrides = args.uvicorn_config.copy()
    # 若存在 MCP 專用 CLI 參數，則一併加入
    if hasattr(args, "allowed_categories") and args.allowed_categories:
        cli_overrides["allowed_categories"] = args.allowed_categories

    if hasattr(args, "default_categories") and args.default_categories:
        cli_overrides["default_categories"] = args.default_categories

    if hasattr(args, "tool_discovery") and args.tool_discovery:
        cli_overrides["tool_discovery"] = args.tool_discovery

    if hasattr(args, "system_prompt") and args.system_prompt:
        cli_overrides["system_prompt"] = args.system_prompt

    if hasattr(args, "server_prompts") and args.server_prompts:
        cli_overrides["server_prompts"] = args.server_prompts

    # 依正確優先順序載入設定（CLI > env > config file > defaults）
    settings = mcp_service.load_with_overrides(**cli_overrides)

    try:
        # 若有匯入自訂 app 就使用它，否則使用預設 OpenBB app
        target_app = args.imported_app if args.imported_app else app

        # 從設定中擷取執行期組態
        http_run_kwargs = settings.get_http_run_kwargs()
        httpx_kwargs = settings.get_httpx_kwargs()

        # 以完整組態建立 MCP 伺服器
        mcp_server = create_mcp_server(settings, target_app, httpx_kwargs, auth=settings.server_auth)

        if args.transport == "stdio":
            asyncio.run(stdio_main(mcp_server))
        else:
            cors_middleware = _build_runtime_middleware()

            # 開始組裝 `mcp.run` 的參數
            run_kwargs = {
                "transport": args.transport,
                "middleware": cors_middleware,
            }

            # 擷取 uvicorn 設定
            if http_run_kwargs.get("uvicorn_config"):
                uvicorn_config = http_run_kwargs["uvicorn_config"].copy()

                # 將 host 與 port 提升為頂層參數
                if "host" in uvicorn_config:
                    run_kwargs["host"] = uvicorn_config.pop("host")

                if "port" in uvicorn_config:
                    port = uvicorn_config.pop("port")
                    run_kwargs["port"] = int(port) if isinstance(port, str) else port

                # 其餘設定保留在巢狀字典中傳入
                if uvicorn_config:
                    run_kwargs["uvicorn_config"] = uvicorn_config

            # 將 SSE 關閉處理加入 middleware stack
            cors_middleware.append(Middleware(SSEShutdownWrapper))
            run_kwargs["middleware"] = cors_middleware

            mcp_server.run(**run_kwargs)

    except KeyboardInterrupt:
        logger.info("Shutdown requested via keyboard interrupt.")
        sys.exit(0)
    except Exception as e:
        logger.error("Server error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
