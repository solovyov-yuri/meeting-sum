"""Shared test fixtures.

The suite asserts on config defaults, so it must not inherit the developer's own ``RECAP_*``
environment (env beats config.yaml in the resolution order — a real
``RECAP_SUMMARIZATION_MODEL_API_KEY`` on the dev machine would both fail the defaults tests and
print the live key into pytest output). Tests that want an env var set it themselves via
``monkeypatch.setenv``, which runs after this fixture.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _isolate_recap_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in [k for k in os.environ if k.startswith("RECAP_")]:
        monkeypatch.delenv(name, raising=False)
    yield
