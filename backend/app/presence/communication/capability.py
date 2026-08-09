from typing import Any
from app.presence.capability_manager import capability_manager


def format_capability_response(engine_output: Any = None, raw_message: str = "") -> str:
    return capability_manager.format_capability_summary()


