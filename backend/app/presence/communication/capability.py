from typing import Any


def describe_abilities() -> str:
    """A plain-language answer to "what can you do?", built from what each tool declares."""
    from app.tools.registry import tool_registry

    abilities = [t.manifest.ability for t in tool_registry.list_tools() if t.manifest.enabled and t.manifest.ability]
    abilities.append("answer questions and remember things you tell me")
    listed = ", ".join(abilities[:-1]) + f", and {abilities[-1]}" if len(abilities) > 1 else abilities[0]
    return (
        f"I can {listed}. "
        "Just ask in your own words, for example \"play some lofi\" or \"remind me to stretch in 20 minutes\"."
    )


def format_capability_response(engine_output: Any = None, raw_message: str = "") -> str:
    return describe_abilities()
