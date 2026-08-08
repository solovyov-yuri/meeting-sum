"""API-key storage backed by the OS keychain (Windows Credential Manager via ``keyring``).

Secrets never touch ``config.yaml``, the history JSON, or logs. ``keyring`` is imported
lazily inside ``_keyring()`` so importing this module (and ``desktop_bridge``) works even
when ``keyring`` is not installed; tests patch ``_keyring`` directly.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SERVICE = "recap-desktop"


class KeychainError(RuntimeError):
    """Raised when the OS keychain cannot be read or written."""


def _keyring():
    try:
        import keyring  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - exercised only without keyring
        raise KeychainError(
            "Хранилище ключей недоступно: пакет 'keyring' не установлен."
        ) from exc
    return keyring


def set_api_key(provider: str, api_key: str) -> None:
    try:
        _keyring().set_password(SERVICE, provider, api_key)
    except KeychainError:
        raise
    except Exception as exc:  # keyring backend errors
        raise KeychainError(f"Не удалось сохранить ключ API: {exc}") from exc


def get_api_key(provider: str) -> str | None:
    try:
        return _keyring().get_password(SERVICE, provider)
    except KeychainError:
        raise
    except Exception as exc:
        raise KeychainError(f"Не удалось прочитать ключ API: {exc}") from exc


def delete_api_key(provider: str) -> None:
    """Idempotent: removing a missing key is not an error."""
    kr = _keyring()
    try:
        kr.delete_password(SERVICE, provider)
    except KeychainError:
        raise
    except Exception as exc:
        # keyring raises PasswordDeleteError when the entry does not exist.
        if type(exc).__name__ == "PasswordDeleteError":
            return
        raise KeychainError(f"Не удалось удалить ключ API: {exc}") from exc


def has_api_key(provider: str) -> bool:
    return get_api_key(provider) is not None
