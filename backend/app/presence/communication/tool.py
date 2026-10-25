import re
from typing import Any


def format_tool_response(intent: str, engine_output: Any, raw_message: str = "") -> str:
    if intent == "EXECUTION_FEEDBACK":
        is_dict = isinstance(engine_output, dict)
        tool_success = engine_output.get("success", False) if is_dict else False
        tool_verified = engine_output.get("verified", False) if is_dict else False
        p_name = engine_output.get("process_name") or "the application"

        if tool_success and tool_verified:
            return f"I tried again, and {p_name} is open now."
        return "You're right. The launch wasn't successful. The application may not be installed or desktop execution may be unavailable."

    is_dict = isinstance(engine_output, dict)
    tool_success = engine_output.get("success", True) if is_dict else True
    tool_verified = engine_output.get("verified", True) if is_dict else True
    status = engine_output.get("status", "success") if is_dict else "success"
    error_msg = engine_output.get("error") if is_dict else None

    res_payload = engine_output.get("result") if is_dict else engine_output

    if isinstance(res_payload, dict) and "result" in res_payload and isinstance(res_payload["result"], dict):
        tool_data = res_payload["result"]
    elif isinstance(res_payload, dict):
        tool_data = res_payload
    else:
        tool_data = {}

    action = engine_output.get("tool") if is_dict else None
    execution_action = tool_data.get("action") if isinstance(tool_data, dict) else None
    app_name = tool_data.get("app_name") if isinstance(tool_data, dict) else None
    is_close_result = action == "open_application" and execution_action == "close"
    is_website_close = action == "close_website" or execution_action == "close_website"

    if status in ["failed", "error"] or not tool_success or not tool_verified:
        reason = (error_msg or "desktop execution isn't available").rstrip(".")
        if is_website_close:
            return f"I couldn't close that website tab because {reason}."
        if is_close_result:
            return f"I attempted to close {app_name or 'the application'}, but couldn't verify that it terminated because {reason}."
        if action not in (None, "open_application", "open_website"):
            # Tools that explain the problem in a full sentence ("I couldn't find milk on your
            # shopping list") are quoted as they are; short reasons follow "because".
            if reason[:1].isupper():
                return f"{reason}."
            return f"I couldn't complete that because {reason}."
        target_name = (tool_data.get("app_name") or (engine_output.get("process_name") if is_dict else None) or (engine_output.get("tool") if is_dict else None))
        if not target_name and raw_message:
            target_name = raw_message.replace("Open ", "").replace("open ", "").strip()
        return f"I attempted to open {target_name or 'application'}, but couldn't verify that it launched because {reason}."

    # Tools that describe their own outcome know best what they did.
    if isinstance(tool_data, dict) and tool_data.get("summary"):
        return str(tool_data["summary"])

    if is_close_result:
        if tool_success and tool_verified:
            return f"I've closed {app_name or 'the application'}."
        return f"I attempted to close {app_name or 'the application'}, but couldn't verify that it terminated."

    if action == "datetime" or "local_time" in tool_data or "utc_time" in tool_data:
        l_time = tool_data.get("local_time", "")
        tz = tool_data.get("timezone", "IST")
        if l_time:
            try:
                parts = l_time.split(":")
                hr = int(parts[0])
                mn = parts[1]
                ampm = "AM" if hr < 12 else "PM"
                hr12 = hr if hr <= 12 else hr - 12
                if hr12 == 0:
                    hr12 = 12
                tz_abbr = "IST" if "India" in tz or "IST" in tz else tz
                return f"It's {hr12}:{mn} {ampm} {tz_abbr}."
            except Exception:
                return f"Current local time is {l_time}."
        return "Current time retrieved."

    if action == "calculator" or "expression" in tool_data:
        expr = tool_data.get("expression", "")
        calc_val = tool_data.get("result", "")
        if calc_val != "":
            clean_expr = re.sub(r'\s*([\+\-\*\/\%])\s*', r' \1 ', expr).strip() if expr else ""
            return f"{clean_expr} = {calc_val}" if clean_expr else f"Result: {calc_val}"

    if action == "open_website" or "url" in tool_data:
        target = tool_data.get("url") or tool_data.get("target") or (raw_message.replace("Open ", "").replace("open ", "").strip() if raw_message else "website")
        if "google.com/search" in str(target).lower():
            import urllib.parse
            q_match = re.search(r'q=([^&]+)', str(target))
            query_unquoted = urllib.parse.unquote(q_match.group(1)) if q_match else "query"
            return f"I've searched the web for '{query_unquoted}'."
        target_title = "GitHub" if "github" in str(target).lower() else target
        return f"I've opened {target_title}."


    if action == "open_app" or action == "open_application" or (raw_message and "open " in raw_message.lower()):
        app_n = tool_data.get("app_name") or engine_output.get("process_name") or (raw_message.replace("Open ", "").replace("open ", "").strip() if raw_message else "application")
        app_lower = str(app_n).lower()
        app_title = (
            "Calculator" if "calculator" in app_lower or "calc" in app_lower else
            "Chrome" if "chrome" in app_lower else
            "Edge" if "edge" in app_lower or "msedge" in app_lower else
            "GitHub" if "github" in app_lower else
            "Notepad" if "notepad" in app_lower else
            "VS Code" if "code" in app_lower else
            app_n
        )
        return f"I've opened {app_title}."

    if action == "clipboard":
        clip_text = tool_data.get("content", "")
        return f"Clipboard content: {clip_text}" if clip_text else "Clipboard accessed."

    if isinstance(tool_data, dict) and "output" in tool_data:
        return f"Tool result: {tool_data['output']}"

    if raw_message and "open " in raw_message.lower():
        target = raw_message.replace("Open ", "").replace("open ", "").strip()
        target_title = "GitHub" if "github" in target.lower() else ("Notepad" if "notepad" in target.lower() else target)
        return f"I've opened {target_title}."

    return "I've taken care of it."


