import webbrowser
from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry


class GitHubTool(BaseTool):
    """GitHub Browser Launcher Plugin."""

    manifest = ToolManifest(
        name="github",
        display_name="GitHub Portal Launcher",
        description="Launches GitHub repository, search queries, issues, or user profiles in default browser.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="developer",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 10.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Python Webbrowser module ready", dependencies=["webbrowser"])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        action = args.get("action", "open_repo").lower()
        if action not in ["open_repo", "search", "issues", "profile"]:
            return False, f"Invalid GitHub action '{action}'. Supported: open_repo, search, issues, profile."
        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        action = args.get("action", "open_repo").lower()
        repo = args.get("repo", "Sahaj1207/Harika")
        query = args.get("query", "")

        url = f"https://github.com/{repo}"
        if action == "search" and query:
            url = f"https://github.com/search?q={query}"
        elif action == "issues":
            url = f"https://github.com/{repo}/issues"
        elif action == "profile":
            user = args.get("user", "Sahaj1207")
            url = f"https://github.com/{user}"

        if dry_run:
            return {
                "dry_run": True,
                "action": f"github_{action}",
                "url": url,
                "expected_result": f"Launches browser targeting {url}"
            }

        opened = webbrowser.open(url)
        return {"action": action, "url": url, "launched": opened}


github_tool = GitHubTool()
tool_registry.register_tool(github_tool)
