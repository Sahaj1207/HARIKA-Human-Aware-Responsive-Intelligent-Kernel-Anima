import re
from typing import Any


def format_tool_response(intent: str, engine_output: Any, raw_message: str = "") -> str:
    if intent == "EXECUTION_FEEDBACK":
        is_dict = isinstance(engine_output, dict)
        tool_success = engine_output.get("success", False) if is_dict else False
        tool_verified = engine_output.get("verified", False) if is_dict else False
        p_name = engine_output.get("process_name") or "the application"
        pid_val = engine_output.get("pid")

        if tool_success and tool_verified:
            pid_str = f" (PID: {pid_val})" if pid_val else ""
            return f"I retried the action and verified {p_name} is active in OS process table{pid_str}."
        return "You're right. The launch wasn't successful. The application may not be installed or desktop execution may be unavailable."

    is_dict = isinstance(engine_output, dict)
    tool_success = engine_output.get("success", True) if is_dict else True
    tool_verified = engine_output.get("verified", True) if is_dict else True
    status = engine_output.get("status", "success") if is_dict else "success"
    error_msg = engine_output.get("error") if is_dict else None

    if status in ["failed", "error"] or not tool_success or not tool_verified:
        reason = error_msg or "desktop execution isn't available"
        target_name = (engine_output.get("tool") or engine_output.get("process_name")) if is_dict else None
        if not target_name and raw_message:
            target_name = raw_message.replace("Open ", "").replace("open ", "").strip()
        return f"I attempted to open {target_name or 'application'}, but couldn't verify that it launched because {reason}."

    res_payload = engine_output.get("result") if is_dict else engine_output

    if isinstance(res_payload, dict) and "result" in res_payload and isinstance(res_payload["result"], dict):
        tool_data = res_payload["result"]
    elif isinstance(res_payload, dict):
        tool_data = res_payload
    else:
        tool_data = {}

    action = engine_output.get("tool") if is_dict else None

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
        app_n = engine_output.get("process_name") or tool_data.get("app_name") or (raw_message.replace("Open ", "").replace("open ", "").strip() if raw_message else "application")
        pid_n = engine_output.get("pid")
        pid_str = f" (PID: {pid_n})" if pid_n else ""
        app_title = "GitHub" if "github" in str(app_n).lower() else ("Notepad" if "notepad" in str(app_n).lower() else app_n)
        return f"I've opened {app_title}{pid_str}."

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


