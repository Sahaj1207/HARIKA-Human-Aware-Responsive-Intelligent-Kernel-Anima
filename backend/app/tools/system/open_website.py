import webbrowser
from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry


class OpenWebsiteTool(BaseTool):
    """Web Browser Website Launcher Plugin."""

    manifest = ToolManifest(
        name="open_website",
        display_name="Website Launcher",
        description="Launches websites (Google, GitHub, YouTube, or custom URLs) in default browser.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 10.0

    URL_MAP = {
        "google": "https://www.google.com",
        "github": "https://github.com",
        "youtube": "https://www.youtube.com",
        "twitter": "https://twitter.com",
        "reddit": "https://www.reddit.com",
        "stackoverflow": "https://stackoverflow.com",
    }

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Python Webbrowser module ready", dependencies=["webbrowser"])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        target = args.get("target") or args.get("url")
        if not target or not isinstance(target, str) or not target.strip():
            return False, "Website target/url is required and cannot be empty."
        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        target = (args.get("target") or args.get("url")).strip().lower()

        url = self.URL_MAP.get(target, target)
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        if dry_run:
            return {
                "dry_run": True,
                "action": "open_url_in_browser",
                "target_url": url,
                "expected_result": f"Launches browser targeting {url}"
            }

        opened = webbrowser.open(url)
        return {"target": target, "url": url, "launched": opened}


open_website_tool = OpenWebsiteTool()
tool_registry.register_tool(open_website_tool)
