import math
import re
from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry


class CalculatorTool(BaseTool):
    """Safe Mathematical Expression Evaluator Plugin."""

    manifest = ToolManifest(
        name="calculator",
        display_name="Calculator Engine",
        description="Evaluates mathematical expressions (arithmetic, sqrt, powers) safely.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="utilities",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 2.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Python Math Engine active", dependencies=["math"])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        expr = args.get("expression")
        if not expr or not isinstance(expr, str) or not expr.strip():
            return False, "Expression argument is required and cannot be empty."

        clean_expr = expr.lower().strip()
        # Reject invalid/dangerous tokens
        if re.search(r"[^\d\.\s\+\-\*\/\(\)\^\,sqrtpowsinabs]", clean_expr):
            return False, f"Invalid characters in math expression: '{expr}'"

        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        expr = args["expression"].strip()

        if dry_run:
            return {
                "dry_run": True,
                "action": "evaluate_expression",
                "expression": expr,
                "expected_result": "Evaluated numeric result"
            }

        # Safe math scope dictionary
        safe_dict = {
            "sqrt": math.sqrt,
            "pow": math.pow,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "abs": abs,
            "pi": math.pi,
            "e": math.e,
        }

        # Replace '^' with '**' for exponentiation
        eval_expr = expr.replace("^", "**")
        val = eval(eval_expr, {"__builtins__": None}, safe_dict)
        return {"expression": expr, "result": val}


calculator_tool = CalculatorTool()
tool_registry.register_tool(calculator_tool)
