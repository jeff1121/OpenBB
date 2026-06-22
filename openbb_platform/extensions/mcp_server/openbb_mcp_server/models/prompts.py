"""FastMCP 的自訂 Prompt 類別。"""

from typing import Any

from fastmcp.exceptions import PromptError
from fastmcp.prompts import Prompt
from mcp.types import PromptMessage, TextContent


class StaticPrompt(Prompt):
    """以靜態字串樣板為基礎的 prompt。"""

    content: str
    argument_defaults: dict[str, Any] = {}

    async def render(
        self,
        arguments: dict[str, Any] | None = None,
    ) -> list[PromptMessage]:
        """使用參數渲染 prompt。"""
        # 先套用預設值，再覆蓋呼叫端提供的值
        args = {**self.argument_defaults, **(arguments or {})}

        # 驗證必要參數
        if self.arguments:
            required = {arg.name for arg in self.arguments if arg.required}
            provided = set(args)
            missing = required - provided
            if missing:
                raise PromptError(f"Missing required arguments: {missing}")

        try:
            rendered_content = self.content.format(**args) if self.arguments or args else self.content
            return [PromptMessage(role="user", content=TextContent(type="text", text=rendered_content))]
        except KeyError as e:
            raise PromptError(f"Missing argument for formatting: {e}") from e
