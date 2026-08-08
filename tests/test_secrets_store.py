from __future__ import annotations

import pytest

import secrets_store


class PasswordDeleteError(Exception):
    pass


class FakeKeyring:
    """In-memory stand-in for the ``keyring`` module."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, name: str, value: str) -> None:
        self.store[(service, name)] = value

    def get_password(self, service: str, name: str) -> str | None:
        return self.store.get((service, name))

    def delete_password(self, service: str, name: str) -> None:
        try:
            del self.store[(service, name)]
        except KeyError as exc:
            raise PasswordDeleteError() from exc


@pytest.fixture()
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    fake = FakeKeyring()
    monkeypatch.setattr(secrets_store, "_keyring", lambda: fake)
    return fake


def test_set_get_has(fake_keyring: FakeKeyring) -> None:
    assert secrets_store.has_api_key("openai") is False
    secrets_store.set_api_key("openai", "sk-secret")
    assert secrets_store.get_api_key("openai") == "sk-secret"
    assert secrets_store.has_api_key("openai") is True


def test_delete_existing(fake_keyring: FakeKeyring) -> None:
    secrets_store.set_api_key("xai", "key")
    secrets_store.delete_api_key("xai")
    assert secrets_store.has_api_key("xai") is False


def test_delete_missing_is_idempotent(fake_keyring: FakeKeyring) -> None:
    # Must not raise even though the entry does not exist.
    secrets_store.delete_api_key("openai")
    assert secrets_store.has_api_key("openai") is False


def test_set_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken:
        def set_password(self, *a: object) -> None:
            raise RuntimeError("backend locked")

    monkeypatch.setattr(secrets_store, "_keyring", lambda: Broken())
    with pytest.raises(secrets_store.KeychainError):
        secrets_store.set_api_key("openai", "x")
