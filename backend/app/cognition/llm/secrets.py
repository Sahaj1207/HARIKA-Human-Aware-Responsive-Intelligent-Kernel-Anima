"""API keys live in the operating system's credential store, never in HARIKA's files.

Windows: Credential Manager. macOS: Keychain. Linux: Secret Service.
"""
import logging
from typing import Optional

logger = logging.getLogger("harika.llm.secrets")

_SERVICE = "HARIKA"


class SecretStoreUnavailable(RuntimeError):
    """No secure credential store is available, so keys cannot be saved."""


def _keyring():
    try:
        import keyring
        from keyring.backends import fail
    except ImportError as exc:
        raise SecretStoreUnavailable("The 'keyring' package is not installed.") from exc
    if isinstance(keyring.get_keyring(), fail.Keyring):
        raise SecretStoreUnavailable("This system has no secure credential store.")
    return keyring


def get_key(service_id: str) -> Optional[str]:
    try:
        return _keyring().get_password(_SERVICE, f"llm:{service_id}")
    except Exception as exc:
        logger.warning(f"[Secrets] Could not read key for {service_id}: {exc}")
        return None


def set_key(service_id: str, key: str) -> None:
    _keyring().set_password(_SERVICE, f"llm:{service_id}", key.strip())


def delete_key(service_id: str) -> None:
    try:
        _keyring().delete_password(_SERVICE, f"llm:{service_id}")
    except Exception:
        pass  # already absent


def has_key(service_id: str) -> bool:
    return bool(get_key(service_id))
