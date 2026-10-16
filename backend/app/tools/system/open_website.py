import re
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
        platforms=["windows", "linux", "darwin"],
        capabilities=["open_website", "close_website"],
        target_aliases={
            "google": ["google", "google.com"],
            "github": ["github", "github.com"],
            "youtube": ["youtube", "youtube.com"],
            "twitter": ["twitter", "x"],
            "reddit": ["reddit", "reddit.com"],
            "stackoverflow": ["stackoverflow", "stackoverflow.com"],
            "chatgpt": ["chatgpt", "chatgpt.com"],
        },
        operations={"open": "open_website", "close": "close_website"},
        target_description="a well-known website name (google, github, youtube, reddit, ...) or a domain such as wikipedia.org",
    )

    _DOMAIN = re.compile(r"^(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?$", re.I)

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        canonical, score = super().match_target(requested, operation)
        if score < 0.9 and self._DOMAIN.match((requested or "").strip()):
            return requested.strip().lower(), 0.9
        return canonical, score
    timeout_seconds = 10.0

    URL_MAP = {
        "google": "https://www.google.com",
        "github": "https://github.com",
        "youtube": "https://www.youtube.com",
        "twitter": "https://twitter.com",
        "reddit": "https://www.reddit.com",
        "stackoverflow": "https://stackoverflow.com",
        "chatgpt": "https://chatgpt.com",
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

        try:
            opened = webbrowser.open(url)
            from app.tools.process_verifier import verify_os_process
            v_chrome, p_chrome, _, _ = verify_os_process("chrome")
            v_edge, p_edge, _, _ = verify_os_process("msedge")
            v_firefox, p_ff, _, _ = verify_os_process("firefox")

            verified = bool(opened)
            pid = p_chrome or p_edge or p_ff
            proc_name = "chrome.exe" if v_chrome else ("msedge.exe" if v_edge else "browser")

            return {
                "target": target,
                "url": url,
                "launched": opened,
                "success": opened,
                "verified": verified,
                "pid": pid,
                "process_name": proc_name,
                "error": None if opened else "Browser launch command failed"
            }
        except Exception as e:
            return {
                "target": target,
                "url": url,
                "launched": False,
                "success": False,
                "verified": False,
                "pid": None,
                "process_name": "browser",
                "error": f"Failed to open website '{url}': {str(e)}"
            }



open_website_tool = OpenWebsiteTool()
tool_registry.register_tool(open_website_tool)
