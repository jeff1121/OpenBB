"""供工具探索使用的輕量分類索引。

維護唯讀的階層式對應：
``category → subcategory → [tool_name]``，
讓探索型管理工具可以提供可瀏覽的目錄。
所有啟用、停用與可見性狀態都委由 FastMCP 原生可見性系統處理。
"""

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field


def _first_sentence(text: str) -> str:
    """擷取 *text* 的第一句，作為簡短摘要。

    會先移除 API 文件標頭（**Query Parameters**、**Responses**）之後的內容，
    再回傳第一句（以換行、句點或字串結尾為界）。
    若找不到句點，則退回第一行。
    """
    if not text:
        return ""
    # 先移除 API 文件區塊
    brief, *_ = re.split(r"\n{2,}\*\*(?:Query Parameters|Responses):", text, maxsplit=1)
    brief = brief.strip()
    if not brief:
        return ""
    # 取出第一句（句點後接空白或字串結尾）
    m = re.search(r"^(.+?\.)(\s|$)", brief, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 若沒有句點，改取第一行
    return brief.split("\n", 1)[0].strip()


@dataclass
class CategoryIndex:
    """將工具對應到分類/子分類，供探索瀏覽使用。

    這是一個在啟動時填充一次的**唯讀索引**。
    它不保存啟用/停用狀態；該責任屬於 FastMCP 的
    `mcp.enable()` / `mcp.disable()`，
    以及每個 session 的
    `ctx.enable_components()` / `ctx.disable_components()`。
    """

    _by_category: dict[str, dict[str, set[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(set))
    )
    _all_names: set[str] = field(default_factory=set)
    _descriptions: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # 填充資料（建立伺服器時，每個工具呼叫一次）
    # ------------------------------------------------------------------

    def register(
        self,
        *,
        category: str,
        subcategory: str,
        tool_name: str,
        description: str = "",
    ) -> None:
        """在 ``category / subcategory`` 之下註冊工具名稱。

        *description* 會以一行短摘要形式保存，
        供工具尚未啟用時的探索清單顯示使用。
        """
        self._by_category[category][subcategory].add(tool_name)
        self._all_names.add(tool_name)
        self._descriptions[tool_name] = _first_sentence(description)

    # ------------------------------------------------------------------
    # 查詢
    # ------------------------------------------------------------------

    def get_categories(self) -> Mapping[str, Mapping[str, set[str]]]:
        """回傳完整的 ``category → subcategory → {tool_names}`` 對應。"""
        return self._by_category

    def get_category_names(self, category: str) -> set[str]:
        """回傳屬於 *category* 的所有工具名稱（包含所有子分類）。"""
        return {
            name
            for subcat_names in self._by_category.get(category, {}).values()
            for name in subcat_names
        }

    def get_subcategory_names(self, category: str, subcategory: str) -> set[str]:
        """回傳特定子分類中的工具名稱。"""
        return self._by_category.get(category, {}).get(subcategory, set())

    def get_subcategories(self, category: str) -> Mapping[str, set[str]] | None:
        """回傳 *category* 的所有子分類；若不存在則回傳 *None*。"""
        return self._by_category.get(category)

    def all_tool_names(self) -> set[str]:
        """回傳所有已註冊的工具名稱。"""
        return set(self._all_names)

    def has_tool(self, tool_name: str) -> bool:
        """若 *tool_name* 已註冊則回傳 *True*。"""
        return tool_name in self._all_names

    def get_description(self, tool_name: str) -> str:
        """回傳快取的簡短描述，否則回傳預設值。"""
        return self._descriptions.get(tool_name, "No description available")

    def clear(self) -> None:
        """清空索引。"""
        self._by_category.clear()
        self._all_names.clear()
        self._descriptions.clear()
