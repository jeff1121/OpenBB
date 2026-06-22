"""MCP 組態結構的驗證模型。

此模組提供 Pydantic 模型，用來驗證 FastAPI 路由定義中
`openapi_extra.mcp_config` 欄位的 JSON 內容。
"""

import re
from enum import Enum
from typing import Any

from fastmcp.utilities.logging import get_logger
from pydantic import BaseModel, Field, field_validator, model_validator

logger = get_logger(__name__)


class MCPType(str, Enum):
    """合法的 MCP 類型值。"""

    TOOL = "tool"
    RESOURCE = "resource"
    RESOURCE_TEMPLATE = "resource_template"


class HTTPMethod(str, Enum):
    """路由設定可用的合法 HTTP 方法。"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    ALL = "*"


class ArgumentDefinitionModel(BaseModel):
    """用於驗證 prompt 參數定義的模型。"""

    name: str = Field(..., description="Name of the argument")
    type: str = Field(default="str", description="Type of the argument")
    default: Any | None = Field(
        default=None, description="Default value for the argument"
    )
    description: str | None = Field(
        default=None, description="Description of the argument"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """驗證參數名稱是否為合法識別字。"""
        if not v:
            raise ValueError("Argument name cannot be empty")
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(f"Argument name '{v}' must be a valid Python identifier")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """驗證型別是否為可辨識的型別字串。"""
        valid_types = {
            "str",
            "string",
            "int",
            "integer",
            "float",
            "bool",
            "boolean",
            "list",
            "dict",
            "any",
            "Any",
        }
        if v not in valid_types:
            raise ValueError(
                f"Type '{v}' not recognized. Valid types: {', '.join(sorted(valid_types))}"
            )
        return v


class PromptConfigModel(BaseModel):
    """用於驗證單一 prompt 設定的模型。"""

    name: str | None = Field(
        default=None, description="Name of the prompt (auto-generated if not provided)"
    )
    description: str | None = Field(
        default=None, description="Description of the prompt"
    )
    content: str = Field(description="Template content with {variable} placeholders")
    arguments: list[ArgumentDefinitionModel] = Field(
        default_factory=list, description="Argument definitions for the prompt"
    )
    tags: list[str] = Field(
        default_factory=list, description="Tags for categorizing the prompt"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """驗證內容不為空，且包含合法的樣板語法。"""
        if not v.strip():
            raise ValueError("Prompt content cannot be empty")

        # 檢查大括號是否成對
        open_braces = v.count("{")
        close_braces = v.count("}")
        if open_braces != close_braces:
            raise ValueError(
                f"Unmatched braces in prompt content: {open_braces} opening, {close_braces} closing"
            )

        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """若有提供 prompt 名稱，則驗證其合法性。"""
        if v is not None:
            if not v.strip():
                raise ValueError("Prompt name cannot be empty string")
            # 檢查是否為類似識別字的合法名稱
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v.strip()):
                raise ValueError(f"Prompt name '{v}' should be a valid identifier")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """驗證 tags 是否為非空字串。"""
        validated_tags = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError(f"Tag must be a string, got {type(tag)}")
            if not tag.strip():
                raise ValueError("Tag cannot be empty string")
            validated_tags.append(tag.strip())
        return validated_tags


class MCPConfigModel(BaseModel):
    """用於驗證主要 MCP 組態結構的模型。"""

    expose: bool | None = Field(
        default=None, description="Whether to expose this route (False = exclude)."
    )
    mcp_type: MCPType | None = Field(
        default=None, description="MCP type classification for the route."
    )
    methods: list[HTTPMethod] | None = Field(
        default=None, description="HTTP methods to include for this route."
    )
    prompts: list[PromptConfigModel] = Field(
        default_factory=list, description="Prompt configurations for this route."
    )
    exclude_args: list[str] | None = Field(
        default=None, description="List of argument names to exclude from this route."
    )

    @field_validator("methods", mode="before")
    @classmethod
    def validate_methods(cls, v: str | list[str] | None) -> list[HTTPMethod] | None:
        """正規化並驗證 HTTP 方法。"""
        if v is None:
            return None

        # 處理單一字串輸入
        if isinstance(v, str):
            v = [v]

        if not isinstance(v, list):
            raise ValueError("methods must be a list of strings")

        # 若包含 '*'，則它必須是唯一的方法
        if "*" in v and len(v) > 1:
            raise ValueError("Method '*' cannot be mixed with other HTTP methods.")

        # 驗證每個方法
        validated_methods = []
        for method in v:
            method_str = str(method).upper().strip() if method != "*" else "*"
            try:
                validated_methods.append(HTTPMethod(method_str))
            except ValueError as exc:
                valid_methods = [m.value for m in HTTPMethod]
                raise ValueError(
                    f"Invalid HTTP method '{method}'. Valid methods: {', '.join(valid_methods)}"
                ) from exc

        # 在保留順序的前提下移除重複值
        seen = set()
        unique_methods = []
        for method in validated_methods:
            if method not in seen:
                seen.add(method)
                unique_methods.append(method)

        return unique_methods if unique_methods else None

    @model_validator(mode="after")
    def validate_config_consistency(self) -> "MCPConfigModel":
        """驗證整體組態的一致性。"""
        # 若 expose 為 False，其他設定雖然影響較小，但仍要驗證
        if self.expose is False:
            # 若 expose=False 時仍設定其他欄位，未來可在此加入警告
            pass

        # 驗證此設定中的 prompt 名稱是否唯一
        if self.prompts:
            prompt_names = []
            for prompt in self.prompts:
                if prompt.name:
                    prompt_names.append(prompt.name)

            # 檢查是否有重複名稱
            if len(prompt_names) != len(set(prompt_names)):
                duplicates = [
                    name for name in prompt_names if prompt_names.count(name) > 1
                ]
                raise ValueError(f"Duplicate prompt names found: {set(duplicates)}")

        return self

    def to_dict(self) -> dict[str, Any]:
        """轉成與現有程式碼相容的字典格式。"""
        return self.model_dump(exclude_none=True)


def validate_mcp_config(
    config_dict: dict[str, Any], *, strict: bool = True
) -> MCPConfigModel:
    """驗證 MCP 組態字典。

    參數
    ----------
    config_dict
        要驗證的組態字典。
    strict
        若為 True，則直接拋出驗證錯誤；若為 False，則記錄警告並回傳盡力而為的模型。

    回傳
    -------
    MCPConfigModel
        驗證後的 MCPConfigModel 實例。

    拋出
    ----
    ValidationError
        當驗證失敗且 strict=True 時拋出。
    """
    try:
        return MCPConfigModel.model_validate(config_dict)
    except Exception as exc:  # pylint: disable=broad-except
        if strict:
            raise exc from exc
        logger.warning("MCP config validation failed ->", exc_info=exc)
        return MCPConfigModel()


def is_valid_mcp_config(config_dict: dict[str, Any]) -> bool | Exception:
    """檢查組態字典是否合法，且不拋出例外。

    參數
    ----------
    config_dict
        要檢查的組態字典。

    回傳
    -------
    bool | Exception
        合法時回傳 True；否則回傳對應的例外物件。
    """
    try:
        validate_mcp_config(config_dict, strict=True)
        return True
    except Exception as exc:
        return exc
