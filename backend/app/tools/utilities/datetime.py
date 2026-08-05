import time
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry


class DateTimeTool(BaseTool):
    """Current Date, Time, and Timezone Provider Plugin."""

    manifest = ToolManifest(
        name="datetime",
        display_name="Date & Time Engine",
        description="Provides current date, local time, UTC time, day of week, and timezone information.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="utilities",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 2.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="System Clock active", dependencies=["datetime"])

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            return {
                "dry_run": True,
                "action": "get_datetime",
                "expected_result": "Current date and time payload"
            }

        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now()

        return {
            "date": now_local.strftime("%Y-%m-%d"),
            "local_time": now_local.strftime("%H:%M:%S"),
            "utc_time": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "day_of_week": now_local.strftime("%A"),
            "timezone": time.tzname[0] if time.tzname else "Local Time"
        }


datetime_tool = DateTimeTool()
tool_registry.register_tool(datetime_tool)
