from typing import List
from app.planning.schemas import Plan, PlanStep, ValidationReport
from app.tools.registry import tool_registry


class PlanValidator:
    """Validates proposed plans, checking tool availability and safety prior to execution."""

    def validate_plan(self, plan: Plan) -> ValidationReport:
        errors: List[str] = []
        warnings: List[str] = []

        if not plan.steps:
            errors.append("Plan contains no execution steps.")
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        for step in plan.steps:
            if step.tool_name:
                tool = tool_registry.get_tool(step.tool_name)
                if not tool:
                    errors.append(f"Step {step.step_number} requires unregistered tool '{step.tool_name}'.")
                elif not tool.manifest.enabled:
                    errors.append(f"Step {step.step_number} requires disabled tool '{step.tool_name}'.")

        is_valid = len(errors) == 0
        return ValidationReport(is_valid=is_valid, errors=errors, warnings=warnings)


plan_validator = PlanValidator()
