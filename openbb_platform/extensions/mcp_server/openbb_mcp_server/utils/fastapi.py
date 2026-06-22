"""處理 FastAPI 路由的工具函式。"""

import inspect
import re
import sys
from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastmcp.server.providers.openapi import MCPType, RouteMap
from openbb_core.app.service.system_service import SystemService
from pydantic import ValidationError

from openbb_mcp_server.models.mcp_config import MCPConfigModel, validate_mcp_config
from openbb_mcp_server.models.settings import MCPSettings


class ProcessedRouteData:
    """保存路由處理期間蒐集到的所有資料。"""

    def __init__(self):
        """以空的串列與字典初始化。"""
        self.route_maps: list[RouteMap] = []
        self.route_lookup: dict[tuple[str, str], APIRoute] = {}
        self.removed_routes: list[APIRoute] = []
        self.prompt_definitions: list[dict] = []


def get_api_prefix(settings: MCPSettings | None) -> str:
    """取得正規化後的 API prefix（前有斜線、後無斜線）。

    若有提供 `settings.api_prefix`，則優先使用。
    """
    override = getattr(settings, "api_prefix", None)
    if isinstance(override, str) and override.strip():
        prefix = override
    else:
        prefix = SystemService().system_settings.api_settings.prefix or ""
    prefix = "/" + prefix.lstrip("/")
    if prefix.endswith("/"):
        prefix = prefix[:-1]
    return prefix


def _get_module_exclusion_targets(settings: MCPSettings | None) -> dict[str, str]:
    """建立 path segment -> module name 的對應。

    若有提供 `settings.module_exclusion_map` 且為字典，則優先使用。
    """
    override = getattr(settings, "module_exclusion_map", None)
    if isinstance(override, dict) and override:
        # 確保鍵與值都是字串
        return {str(k): str(v) for k, v in override.items()}
    return {
        "econometrics": "openbb_econometrics",
        "quantitative": "openbb_quantitative",
        "technical": "openbb_technical",
        "coverage": "openbb_core",
    }


def get_mcp_config(route: APIRoute, *, strict: bool = False) -> MCPConfigModel:
    """從 `openapi_extra` 讀取並驗證每個路由的 MCP 設定。

    參數
    ----------
    route
        要處理的 APIRoute。
    strict
        若為 True，直接拋出驗證錯誤；若為 False，則只記錄警告。

    回傳
    -------
    MCPConfigModel
        驗證後的 MCPConfigModel 實例。
    """
    extra = route.openapi_extra or {}
    raw_config = extra.get("mcp_config") or extra.get("x-mcp") or {}

    if not isinstance(raw_config, dict):
        if strict:
            raise TypeError("mcp_config must be a dictionary.")
        raw_config = {}

    try:
        return validate_mcp_config(raw_config, strict=strict)
    except (ValidationError, TypeError, ValueError) as e:
        if strict:
            raise e from e
        return MCPConfigModel()


def _get_prompt_configs(route: APIRoute) -> list[dict]:
    """從每個路由的 MCP 設定中擷取 prompt 設定。

    支援由字典組成的 `prompts` 清單。
    回傳 prompt 設定列表。
    """
    mcp_cfg = get_mcp_config(route)
    # 將 PromptConfigModel 轉為字典
    return [p.model_dump() for p in mcp_cfg.prompts] if mcp_cfg.prompts else []


def _create_prompt_definitions_for_route(
    route: APIRoute, settings: MCPSettings | None = None
) -> list[dict]:
    """若路由存在 prompt 設定，則建立對應的 prompt 定義。"""
    prompt_configs = _get_prompt_configs(route)
    definitions: list[dict] = []

    if not prompt_configs:
        return definitions

    # 從 endpoint signature 取得參數定義
    # 這是參數名稱、型別與預設值的準確來源
    try:
        sig = inspect.signature(route.endpoint)
        endpoint_args = {
            p.name: {
                "name": p.name,
                "type": (
                    p.annotation.__name__
                    if hasattr(p.annotation, "__name__")
                    else "str"
                ),
                "default": p.default if p.default is not p.empty else ...,
            }
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        }
    except (ValueError, TypeError):
        # 無法檢查 signature
        endpoint_args = {}

    # 這個路由上所有 prompts 共用的資訊
    api_prefix = get_api_prefix(settings)
    tool_uri = route.path.replace(api_prefix, "").lstrip("/").replace("/", "_")
    path = route.path or ""
    if not path.startswith("/"):
        path = "/" + path
    remainder = (
        path[len(api_prefix) :] if api_prefix and path.startswith(api_prefix) else path
    )
    local_path = remainder.lstrip("/")
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

    for i, prompt_cfg in enumerate(prompt_configs):
        if not prompt_cfg or not prompt_cfg.get("content"):
            continue

        # 產生 prompt 名稱
        prompt_name = prompt_cfg.get("name")
        if not prompt_name:
            base_name = (
                f"{category}_{subcategory}_{tool}"
                if subcategory != "general"
                else f"{category}_{tool}"
            )
            # 若有多個未命名 prompt，加入索引以確保唯一性
            suffix = f"_{i}" if len(prompt_configs) > 1 else ""
            prompt_name = f"{base_name}_prompt{suffix}"

        # prompt 參數可能來自 endpoint 參數與自訂參數的組合
        final_args: dict = {}
        prompt_arg_defs = {arg["name"]: arg for arg in prompt_cfg.get("arguments", [])}
        content = (
            f"Use the tool, {tool_uri}, to perform the following task.\n\n"
            + prompt_cfg.get("content", "")
        )

        # content 字串中的所有變數都視為 prompt 參數
        prompt_vars = re.findall(r"\{(\w+)\}", content)

        for var in set(prompt_vars):
            if var in prompt_arg_defs:
                # 使用 prompt 自身 `arguments` 清單中的定義
                final_args[var] = prompt_arg_defs[var]
            elif var in endpoint_args:
                # 繼承 endpoint signature 中的定義
                final_args[var] = endpoint_args[var]
            else:
                # 參數被 prompt 使用，但未在任何地方定義
                final_args[var] = {"name": var, "type": "str"}

        # 建立 prompt 定義
        prompt_def = {
            "name": prompt_name,
            "description": prompt_cfg.get("description") or f"Prompt for {tool_uri}",
            "content": content,
            "arguments": list(final_args.values()),
            "tool": tool_uri,
        }

        # 加上 tags，且一定包含路由路徑
        tags = list(prompt_cfg.get("tags", []))
        if route.path and route.path not in tags:
            tags.insert(0, route.path)
        prompt_def["tags"] = tags

        definitions.append(prompt_def)

    return definitions


def _normalize_methods(methods: Sequence[str] | None) -> list[str]:
    """將方法轉為大寫並過濾掉 HEAD/OPTIONS；若無內容則回傳 []。"""
    if not methods:
        return []
    out = []
    for m in methods:
        if not m:
            continue
        mu = str(m).upper()
        if mu in {"HEAD", "OPTIONS"}:
            continue
        out.append(mu)
    return out


def _methods_from_config_or_route(cfg: MCPConfigModel, route: APIRoute) -> list:
    """若 cfg.methods 存在則使用之，否則改用 route.methods。"""
    if cfg.methods:
        # 處理代表全部方法的 '*' 萬用字元
        if any(m.value == "*" for m in cfg.methods):
            return ["*"]
        methods = [m.value for m in cfg.methods]
    else:
        methods = list(route.methods or [])
    return _normalize_methods(methods)


def _resolve_mcp_type(value: str | None) -> MCPType | None:
    if not value:
        return None
    v = value.lower().strip()
    if v == "tool":
        return MCPType.TOOL
    if v == "resource":
        return MCPType.RESOURCE
    if v in {"resource_template", "resource-template"}:
        return MCPType.RESOURCE_TEMPLATE
    return None


def _should_exclude_by_module_and_path(path: str, settings: MCPSettings | None) -> bool:
    """若對應模組已載入，則排除特定的路由樹。"""
    api_prefix = get_api_prefix(settings)
    targets = _get_module_exclusion_targets(settings)

    # 正規化路徑，避免雙斜線造成干擾
    if not path.startswith("/"):
        path = "/" + path

    for segment, module_name in targets.items():
        base = f"{api_prefix}/{segment}"
        if path.startswith(base) and module_name in sys.modules:
            return True
    return False


def process_fastapi_routes_for_mcp(
    app: FastAPI, settings: MCPSettings | None = None
) -> ProcessedRouteData:
    """以單次走訪處理 FastAPI 路由，並完成以下工作：

    1. 直接從 app 中移除不需要的 routes
    2. 建立 FastMCP 所需的 route maps
    3. 建立供客製化使用的 route lookup 字典
    """
    processed = ProcessedRouteData()
    routes_to_keep = []

    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            routes_to_keep.append(route)  # 保留非 HTTP 路由
            continue

        # 檢查是否應排除此路由
        cfg = get_mcp_config(route)
        should_exclude = False

        # 明確的逐路由曝露控制
        if cfg.expose is False or _should_exclude_by_module_and_path(
            route.path or "", settings
        ):
            should_exclude = True

        if should_exclude:
            processed.removed_routes.append(route)
            continue

        # 保留此路由
        routes_to_keep.append(route)

        # 建立供客製化使用的 route lookup（只處理保留的路由）
        for method in route.methods or []:
            method_upper = str(method).upper()
            if method_upper not in {"HEAD", "OPTIONS"}:
                processed.route_lookup[(route.path, method_upper)] = route

        # 為 FastMCP 建立 route maps（只處理明確指定 mcp_type 的路由）
        mcp_type_str = cfg.mcp_type.value if cfg.mcp_type else None
        mcp_type = _resolve_mcp_type(mcp_type_str)
        if mcp_type is not None:
            methods = _methods_from_config_or_route(cfg, route)
            pattern = f"^{re.escape(route.path)}$"
            if methods:
                processed.route_maps.append(
                    RouteMap(pattern=pattern, methods=methods, mcp_type=mcp_type)
                )
            else:
                processed.route_maps.append(
                    RouteMap(pattern=pattern, mcp_type=mcp_type)
                )

        # 收集 prompt 定義（只處理有 prompt 設定的路由）
        prompt_defs = _create_prompt_definitions_for_route(route, settings)
        if prompt_defs:
            processed.prompt_definitions.extend(prompt_defs)

    # 原地更新 app 的 routes
    app.router.routes = routes_to_keep

    # 加入 catch-all route map
    catchall_type = (
        _resolve_mcp_type(getattr(settings, "default_catchall_mcp_type", None))
        or MCPType.TOOL
    )
    processed.route_maps.append(RouteMap(pattern=r".*", mcp_type=catchall_type))

    return processed
