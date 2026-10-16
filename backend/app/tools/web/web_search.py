import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools import recent_results
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest
from app.tools.web import sources


class WebSearchTool(BaseTool):
    """Searches the web, shows results in the browser, and can open a result by position."""

    manifest = ToolManifest(
        name="web_search",
        display_name="Web Search",
        description="Searches the web for a query, and opens an item from the most recent list of web or file results.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="web",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["web_search", "open_search_result"],
        operations={"search": "web_search", "open": "open_search_result"},
        ability="search the web",
        free_text_operations=["search"],
        # Positions are the only "open" targets this tool owns; search queries are free text.
        target_aliases={
            "1": ["first result", "first link", "top result", "1st result", "first one", "result 1"],
            "2": ["second result", "second link", "2nd result", "second one", "result 2"],
            "3": ["third result", "third link", "3rd result", "third one", "result 3"],
        },
        target_description="for search: the search query; for open: which result (e.g. 'first result')",
    )
    timeout_seconds = 15.0

    def __init__(self):
        self.last_query: Optional[str] = None
        self.last_results: List[Dict[str, str]] = []

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="HTTP search available", dependencies=["httpx", "webbrowser"])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not str(args.get("target") or "").strip():
            return False, "A search query or result position is required."
        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        if args.get("operation") == "open":
            return self._open_result(str(args.get("target")), dry_run)
        return await self._search(str(args.get("target")).strip(), dry_run)

    async def _search(self, query: str, dry_run: bool) -> Dict[str, Any]:
        search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        if dry_run:
            return {"dry_run": True, "action": "web_search", "query": query, "url": search_url}

        results = await self._fetch_results(query)
        self.last_query, self.last_results = query, results
        recent_results.remember("web", results[:10])
        opened = webbrowser.open(search_url)
        top = "; ".join(f"{i}. {r['title']}" for i, r in enumerate(results[:3], 1))
        summary = f"I searched the web for {query}."
        if top:
            summary += f" Top results: {top}."
        return {
            "action": "web_search",
            "query": query,
            "url": search_url,
            "results": results[:5],
            "success": bool(opened),
            "verified": bool(opened),
            "summary": summary if opened else None,
            "error": None if opened else "the browser could not be opened",
        }

    def _open_result(self, position: str, dry_run: bool) -> Dict[str, Any]:
        """Open an item from whatever HARIKA listed last (web results or files)."""
        index = int(position) - 1 if position.isdigit() else 0
        if recent_results.count() == 0:
            return {
                "action": "open_search_result",
                "success": False,
                "verified": False,
                "error": "there are no recent results to open, so try searching first",
            }
        result = recent_results.get(index)
        if result is None:
            return {
                "action": "open_search_result",
                "success": False,
                "verified": False,
                "error": f"the last list only had {recent_results.count()} results",
            }
        if dry_run:
            return {"dry_run": True, "action": "open_search_result", "item": result}
        if "path" in result:
            from app.tools.system.files import files_tool
            return files_tool.open_path(Path(result["path"]), f"Opened {result['title']}.")
        opened = webbrowser.open(result["url"])
        return {
            "action": "open_search_result",
            "url": result["url"],
            "title": result["title"],
            "success": bool(opened),
            "verified": bool(opened),
            "summary": f"I opened {result['title']}." if opened else None,
            "error": None if opened else "the browser could not be opened",
        }

    async def _fetch_results(self, query: str) -> List[Dict[str, str]]:
        return await sources.search(query, limit=10)

    @staticmethod
    def _real_url(href: str) -> str:
        return sources._real_url(href)


web_search_tool = WebSearchTool()
tool_registry.register_tool(web_search_tool)
