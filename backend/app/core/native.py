"""Native libraries that must be loaded in a particular order.

Loading Windows' WinRT bindings (used to read notifications) before onnxruntime (the
meaning model) crashes the whole process; the other way round is fine. So onnxruntime
is loaded first: at start-up, and again just before anything loads WinRT.
"""
import logging

logger = logging.getLogger("harika.native")


def load_in_safe_order() -> None:
    try:
        import onnxruntime  # noqa: F401  (must come before winrt)
    except Exception as exc:  # not installed or unusable: nothing to protect
        logger.info(f"[Native] onnxruntime not loaded: {exc}")
