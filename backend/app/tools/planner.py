import re
from typing import Dict, Any, List, Optional
from app.tools.schemas import ActionPlan, SingleAction


class ActionPlanner:
    """Parses user input directives to generate structured ActionPlan objects without calling tools directly."""

    def plan_capability(
        self,
        capability: str,
        action: str,
        target: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ActionPlan:
        """Plan an already-normalized capability request without reparsing user language."""
        args = dict(arguments or {})
        if capability == "open_application":
            args.update({"app_name": target or args.get("app_name"), "action": "close" if action == "close" else "launch"})
            tool_name = "open_application"
        elif capability == "open_website":
            args.update({"target": target or args.get("target")})
            tool_name = "open_website"
        elif capability == "close_website":
            args.update({"target": target or args.get("target")})
            tool_name = "close_website"
        else:
            tool_name = self._tool_for_capability(capability) or capability
            if target is not None:
                args["target"] = target
            if action:
                args["operation"] = action

        if not args.get("app_name") and not args.get("target") and capability not in {"calculator", "datetime"}:
            return ActionPlan(is_tool_action=False, actions=[], confidence=0.0)
        return ActionPlan(
            is_tool_action=True,
            actions=[SingleAction(tool_name=tool_name, arguments=args, reasoning="Normalized capability request." )],
            confidence=0.95,
        )

    @staticmethod
    def _tool_for_capability(capability: str) -> Optional[str]:
        """Find the registered tool that declares this capability."""
        from app.tools.registry import tool_registry
        for tool in tool_registry.list_tools():
            if capability in tool.manifest.capabilities:
                return tool.manifest.name
        return None

    def plan_action(self, user_message: str) -> ActionPlan:
        msg = user_message.strip()
        msg_lower = msg.lower()

        # 1. Calculator Trigger
        calc_match = re.search(r"(?:calculate|eval|compute|math|what is)\s+([0-9\+\-\*\/\(\)\^\.\s\w]+)", msg_lower)
        if calc_match and any(op in calc_match.group(1) for op in ['+', '-', '*', '/', 'sqrt', '^']):
            expr = calc_match.group(1).strip()
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="calculator", arguments={"expression": expr}, reasoning="User requested math calculation.")],
                confidence=0.95
            )

        # Standalone direct math expressions like "25*18" or "sqrt(81)"
        if re.match(r"^[\d\.\s\+\-\*\/\(\)\^sqrt]+$", msg_lower) and any(op in msg_lower for op in ['+', '-', '*', '/', 'sqrt']):
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="calculator", arguments={"expression": msg}, reasoning="Direct math expression detected.")],
                confidence=0.95
            )

        # 2. Date & Time Trigger
        if any(kw in msg_lower for kw in ["what time is it", "current time", "what is the date", "today's date", "current date"]):
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="datetime", arguments={}, reasoning="User requested current date/time.")],
                confidence=0.95
            )

        # 2.5 Web Search Trigger
        search_match = re.search(r"(?:search\s+(?:web\s+)?for|google)\s+(.+)", msg_lower)
        if search_match and not any(k in msg_lower for k in ["open ", "launch ", "visit "]):
            query_str = search_match.group(1).strip()
            import urllib.parse
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query_str)}"
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="open_website", arguments={"target": search_url, "query": query_str}, reasoning=f"User requested web search for '{query_str}'.")],
                confidence=0.95
            )

        # 3. Close Website Trigger
        close_web_match = re.search(r"(?:close|kill|terminate|stop)\s+(google|github|youtube|twitter|reddit|stackoverflow|chatgpt|https?://[^\s]+|[^\s]+\.[a-z]{2,})", msg_lower)
        if close_web_match:
            target = close_web_match.group(1).strip()
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="close_website", arguments={"target": target}, reasoning="User requested closing a browser website/tab.")],
                confidence=0.90
            )

        # 3. Open Website Trigger
        web_match = re.search(r"(?:(?:open|launch|visit)\s+)?(google|github|youtube|twitter|reddit|stackoverflow|chatgpt|https?://[^\s]+)", msg_lower)

        if web_match:
            target = web_match.group(1).strip()
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="open_website", arguments={"target": target}, reasoning="User requested opening website.")],
                confidence=0.90
            )


        # 4. Close Application Trigger
        close_match = re.search(r"(?:close|kill|terminate|stop)\s+(chrome|edge|vs code|vscode|notepad|calculator|cmd|terminal|command prompt)", msg_lower)
        if close_match:
            app_name = close_match.group(1).strip()
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="open_application", arguments={"app_name": app_name, "action": "close"}, reasoning="User requested application termination.")],
                confidence=0.90
            )

        # 4.5 Open Application Trigger
        app_match = re.search(r"(?:(?:open|launch|start|run)\s+)?(chrome|edge|vs code|vscode|notepad|calculator|cmd|terminal|command prompt)", msg_lower)
        if app_match:
            app_name = app_match.group(1).strip()
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="open_application", arguments={"app_name": app_name, "action": "launch"}, reasoning="User requested application launch.")],
                confidence=0.90
            )



        # 5. Clipboard Trigger
        if "clipboard" in msg_lower:
            if "read" in msg_lower or "get" in msg_lower or "show" in msg_lower:
                return ActionPlan(
                    is_tool_action=True,
                    actions=[SingleAction(tool_name="clipboard", arguments={"action": "read"}, reasoning="User requested reading clipboard.")],
                    confidence=0.90
                )
            elif "copy" in msg_lower or "write" in msg_lower:
                content = msg.replace("copy", "").replace("clipboard", "").strip()
                return ActionPlan(
                    is_tool_action=True,
                    actions=[SingleAction(tool_name="clipboard", arguments={"action": "write", "text": content}, reasoning="User requested clipboard write.")],
                    confidence=0.90
                )

        # 6. Terminal Command Trigger
        cmd_match = re.search(r"(?:run|exec|execute)\s+(pwd|dir|ls|whoami|echo\s+.*|python --version|git status)", msg_lower)
        if cmd_match:
            command = cmd_match.group(1).strip()
            return ActionPlan(
                is_tool_action=True,
                actions=[SingleAction(tool_name="terminal", arguments={"command": command}, reasoning="User requested safe terminal command execution.")],
                confidence=0.90
            )

        # Default: No tool action planned
        return ActionPlan(is_tool_action=False, actions=[], confidence=0.0)


action_planner = ActionPlanner()
