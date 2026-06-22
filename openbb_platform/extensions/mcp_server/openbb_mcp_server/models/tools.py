"""MCP 伺服器的工具模型。"""

from pydantic import BaseModel


class ToolInfo(BaseModel):
    """單一工具的資訊。"""

    name: str
    active: bool
    description: str


class SubcategoryInfo(BaseModel):
    """工具子分類的中繼資料。"""

    name: str
    tool_count: int


class CategoryInfo(BaseModel):
    """工具分類的中繼資料。"""

    name: str
    subcategories: list[SubcategoryInfo]
    total_tools: int
