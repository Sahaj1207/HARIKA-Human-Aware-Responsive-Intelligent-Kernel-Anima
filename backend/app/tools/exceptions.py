class ToolEngineError(Exception):
    """Base exception class for all Tool Engine errors."""
    pass


class ToolNotFoundError(ToolEngineError):
    """Raised when a requested tool is not found in registry."""
    pass


class ToolDisabledError(ToolEngineError):
    """Raised when an execution is attempted on a disabled tool."""
    pass


class PermissionDeniedError(ToolEngineError):
    """Raised when execution violates security permissions or policy."""
    pass


class InvalidArgumentsError(ToolEngineError):
    """Raised when tool input validation fails prior to execution."""
    pass


class ToolTimeoutError(ToolEngineError):
    """Raised when tool execution exceeds timeout limit."""
    pass


class ToolBusyError(ToolEngineError):
    """Raised when another tool execution lock is active."""
    pass
