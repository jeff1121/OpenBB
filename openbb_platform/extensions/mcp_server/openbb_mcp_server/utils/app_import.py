"""MCP Server 的應用程式匯入工具。"""

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI


def import_app(app_path: str, name: str = "app", factory: bool = False) -> FastAPI:
    """從本機檔案或模組匯入 FastAPI app 實例。"""
    # pylint: disable=import-outside-toplevel
    from importlib import import_module, util

    def _is_module_colon_notation(app_path: str) -> bool:
        """檢查路徑是否使用 module:name 表示法，而非 Windows 路徑。"""
        if ":" not in app_path:
            return False
        # Windows 絕對路徑檢查（例如 C:\path 或 D:/path）
        if len(app_path) >= 2 and app_path[1] == ":" and app_path[0].isalpha():
            # 仍可能是 colon 表示法：C:\path\file.py:app
            parts = app_path.split(":")
            return len(parts) > 2  # 不只是磁碟代號的冒號
        return True

    def _load_module_from_file_path(file_path: str):
        """從檔案路徑載入 Python 模組。"""
        spec_name = os.path.basename(file_path).split(".")[0]
        spec = util.spec_from_file_location(spec_name, file_path)

        if spec is None:
            raise RuntimeError(f"Failed to load the file specs for '{file_path}'")

        module = util.module_from_spec(spec)  # type: ignore
        sys.modules[spec_name] = module  # type: ignore
        spec.loader.exec_module(module)  # type: ignore
        return module

    # 情況 1：使用 colon 表示法的模組路徑（例如 "my_app.main:app" 或 "main:app"）
    if _is_module_colon_notation(app_path):
        module_path, name = app_path.rsplit(":", 1)
        try:  # 先嘗試以模組方式匯入
            module = import_module(module_path)
        except ImportError:  # 若模組匯入失敗，再改用本機檔案載入
            if not module_path.endswith(".py"):
                module_path += ".py"

            if not Path(module_path).is_absolute():
                cwd = Path.cwd()
                file_path = str(cwd.joinpath(module_path).resolve())
            else:
                file_path = module_path

            if not Path(file_path).exists():
                raise FileNotFoundError(  # pylint: disable=raise-missing-from
                    f"Error: Neither module '{module_path}' could be imported nor file '{file_path}' exists"
                )

            module = _load_module_from_file_path(file_path)

    # 情況 2：檔案路徑（例如 "main.py" 或 "my_app/main.py"）
    else:
        if not Path(app_path).is_absolute():
            cwd = Path.cwd()
            app_path = str(cwd.joinpath(app_path).resolve())

        if not Path(app_path).exists():
            raise FileNotFoundError(f"Error: The app file '{app_path}' does not exist")

        module = _load_module_from_file_path(app_path)

    if not hasattr(module, name):
        raise AttributeError(
            f"Error: The app file '{app_path}' does not contain an '{name}' instance"
        )

    app_or_factory = getattr(module, name)

    # 這裡採用與 uvicorn 相同的方式處理 factory function，
    # 避免依賴明確的型別註記。
    # 參考：https://github.com/encode/uvicorn/blob/master/uvicorn/config.py
    try:
        app = app_or_factory()
        if not factory:
            print(  # noqa: T201
                "\n\n[WARNING]   "
                "App factory detected. Using it, but please consider setting the --factory flag explicitly.\n"
            )
    except TypeError:
        if factory:
            raise TypeError(  # pylint: disable=raise-missing-from
                f"Error: The {name} instance in '{app_path}' appears not to be a callable factory function"
            )
        app = app_or_factory

    if not isinstance(app, FastAPI):
        raise TypeError(
            f"Error: The {name} instance in '{app_path}' is not an instance of FastAPI"
        )

    return app


cl_doc = """OpenBB MCP Server

用法：
    >>> python -m openbb_mcp_server [OPTIONS]

    >>> openbb-mcp --app ./some_app.py --host 0.0.0.0 --port 8005

說明：
    OpenBB MCP Server 是 OpenBB Platform 的組件之一，
    提供 Model Context Protocol（MCP）伺服器。
    REST 端點會被轉換成工具，並提供給已連線的客戶端使用。

    設定可定義於 `~/.openbb_platform/mcp_settings.json` 組態檔中。

    也可以透過環境變數設定，鍵名需以 `OPENBB_MCP_` 為前綴。

選項：
    --help
        顯示此說明並結束。

    --app <app_path>
        FastAPI app 實例的路徑。
        可使用 'module.path:app_instance' 或 'path/to/app.py' 格式。
        若未提供，伺服器會使用內建預設 app 啟動。

    --name <name>
        app 檔案中 FastAPI 實例或 factory function 的名稱。
        預設為 'app'。

    --factory
        若設定此旗標，會將 app 視為 factory function，
        並呼叫它來建立 FastAPI app 實例。

    --host <host>
        伺服器要綁定的 host。預設為 '127.0.0.1'。
        這是 uvicorn 參數。

    --port <port>
        伺服器要綁定的 port。預設為 8001。
        這是 uvicorn 參數。

    --transport <transport>
        MCP 伺服器使用的傳輸機制。
        預設為 'streamable-http'。

    --allowed-categories <categories>
        允許使用的工具分類，使用逗號分隔。
        若未提供，則允許所有分類。

    --default-categories <categories>
        預設啟用的工具分類，使用逗號分隔。
        預設為 'all'。

    --tool-discovery
        若設定此旗標，會啟用工具探索。

    --system-prompt <path>
        系統 prompt 的 TXT 檔案路徑。

    --server-prompts <path>
        包含 server prompts 清單的 JSON 檔案路徑。

其他所有參數都會作為 MCPSettings 傳入。
"""


def parse_args():
    """解析命令列參數。"""
    # pylint: disable=import-outside-toplevel
    from openbb_core.env import Env

    _ = Env()

    args = sys.argv[1:].copy()
    _kwargs: dict = {}

    # 將所有命令列參數解析為 kwargs
    for i, arg in enumerate(args):
        if arg == "--help":
            print(cl_doc)  # noqa: T201
            sys.exit(0)
        if arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            if key in ["no_use_colors", "use_colors"]:
                _kwargs["use_colors"] = key == "use_colors"
            elif i + 1 < len(args) and not args[i + 1].startswith("--"):
                value = args[i + 1]
                if isinstance(value, str) and value.lower() in ["false", "true"]:
                    _kwargs[key] = value.lower() == "true"
                else:
                    try:
                        if (value.startswith("{") and value.endswith("}")) or (
                            value.startswith("[") and value.endswith("]")
                        ):
                            _kwargs[key] = json.loads(value)
                        elif (
                            key != "app"
                            and ":" in value
                            and all(":" in part for part in value.split(","))
                        ):
                            _kwargs[key] = {
                                k.strip(): v.strip()
                                for k, v in (p.split(":", 1) for p in value.split(","))
                            }
                        else:
                            _kwargs[key] = value
                    except (json.JSONDecodeError, ValueError):
                        _kwargs[key] = value
            else:
                _kwargs[key] = True

    # 擷取並處理 app 匯入相關參數
    _app_path = _kwargs.pop("app", None)
    _name = _kwargs.pop("name", "app")
    _factory = _kwargs.pop("factory", False)

    imported_app = None
    if _app_path:
        if ":" in _app_path:
            _app_instance_name = _app_path.split(":")[-1]
            _name = _app_instance_name if _app_instance_name else _name

        if _factory and not _name:
            raise ValueError(
                "Error: The factory function name must be provided to the --name parameter when the factory flag is set."
            )
        imported_app = import_app(_app_path, _name, _factory)

    # 擷取 MCP 專用參數
    transport = _kwargs.pop("transport", "streamable-http")
    allowed_categories = _kwargs.pop("allowed_categories", None)
    default_categories = _kwargs.pop("default_categories", "all")
    tool_discovery = _kwargs.pop("tool_discovery", False)
    system_prompt = _kwargs.pop("system_prompt", None)
    server_prompts = _kwargs.pop("server_prompts", None)

    class Args:
        """已解析命令列參數的容器。"""

        def __init__(self):
            """初始化 Args 容器。"""
            self.imported_app = imported_app
            self.transport = transport
            self.allowed_categories = allowed_categories
            self.default_categories = default_categories
            self.tool_discovery = tool_discovery
            self.system_prompt = system_prompt
            self.server_prompts = server_prompts
            self.uvicorn_config = _kwargs  # 其餘 kwargs 全部交給 uvicorn

    return Args()
