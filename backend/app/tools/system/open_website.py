import platform
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry


class OpenWebsiteTool(BaseTool):
    """Web Browser Website Launcher Plugin."""

    manifest = ToolManifest(
        name="open_website",
        display_name="Website Launcher",
        description="Opens any website, in the default browser or a named one (Chrome, Edge, Firefox, Brave).",
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
        ability="open websites",
        target_description="the website's domain, such as instagram.com or netflix.com (always a domain, not just the name); put a named browser in parameters.browser",
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

        browser = self._find_browser(str(args.get("browser") or ""))
        requested_browser = str(args.get("browser") or "").strip()

        if dry_run:
            return {
                "dry_run": True,
                "action": "open_url_in_browser",
                "target_url": url,
                "browser": browser[0] if browser else "default",
                "expected_result": f"Launches browser targeting {url}"
            }

        site = url.split("://", 1)[-1].split("/", 1)[0].removeprefix("www.")
        try:
            if browser:
                name, command = browser
                # Argument list, no shell: the URL is a single argument.
                subprocess.Popen([*command, url], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                opened, where = True, f" in {name}"
            else:
                opened, where = bool(webbrowser.open(url)), ""
            note = ""
            if requested_browser and not browser and requested_browser.lower() not in ("browser", "default", "web browser"):
                note = f" {requested_browser.title()} isn't installed, so I used your default browser."
            return {
                "target": target,
                "url": url,
                "launched": opened,
                "success": opened,
                "verified": opened,
                "process_name": browser[0] if browser else "browser",
                "summary": f"Opened {site}{where}.{note}" if opened else None,
                "error": None if opened else "the browser could not be opened",
            }
        except Exception as e:
            return {
                "target": target,
                "url": url,
                "launched": False,
                "success": False,
                "verified": False,
                "process_name": "browser",
                "error": f"I couldn't open {site}: {e}",
            }

    # Browsers HARIKA can target by name: display name and executable.
    BROWSERS = {
        "chrome": ("Chrome", "chrome.exe", "Google Chrome"),
        "google chrome": ("Chrome", "chrome.exe", "Google Chrome"),
        "edge": ("Edge", "msedge.exe", "Microsoft Edge"),
        "microsoft edge": ("Edge", "msedge.exe", "Microsoft Edge"),
        "firefox": ("Firefox", "firefox.exe", "Firefox"),
        "brave": ("Brave", "brave.exe", "Brave Browser"),
        "opera": ("Opera", "opera.exe", "Opera"),
        "safari": ("Safari", "", "Safari"),
    }

    def _find_browser(self, name: str) -> Optional[Tuple[str, list]]:
        """(display name, command prefix) for an installed browser, or None for the default browser."""
        entry = self.BROWSERS.get(" ".join(name.lower().split()))
        if entry is None:
            return None
        display, exe, mac_app = entry
        system = platform.system()
        if system == "Darwin":
            return (display, ["open", "-a", mac_app]) if Path(f"/Applications/{mac_app}.app").exists() else None
        if system != "Windows" or not exe:
            return None
        import winreg
        # Windows registers each installed program's full path under "App Paths".
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as key:
                    path = winreg.QueryValue(key, None)
                if path and Path(path.strip('"')).exists():
                    return display, [path.strip('"')]
            except OSError:
                continue
        return None


open_website_tool = OpenWebsiteTool()
tool_registry.register_tool(open_website_tool)
