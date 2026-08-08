"""The CUDA versions the portable downloader hardcodes must equal the ones the lock resolves.

``cuda_support.CUDA_PACKAGES`` pins exact cuBLAS/cuDNN versions because the downloaded DLLs have to
match the SONAMEs ctranslate2 was built against, while ``pyproject.toml`` declares them with ``>=``.
Nothing but this test stops a lock refresh from raising the resolved version and leaving the
downloader behind — a drift that only shows up as a broken GPU mode on a user's machine.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from cuda_support import CUDA_PACKAGES

_ROOT = Path(__file__).resolve().parent.parent


def _locked_versions() -> dict[str, str]:
    lock = tomllib.loads((_ROOT / "uv.lock").read_text(encoding="utf-8"))
    return {pkg["name"]: pkg["version"] for pkg in lock["package"]}


def test_cuda_packages_match_the_lock() -> None:
    locked = _locked_versions()
    assert {pkg: ver for pkg, ver in CUDA_PACKAGES} == {pkg: locked[pkg] for pkg, _ in CUDA_PACKAGES}


def test_cuda_packages_are_declared_as_dependencies() -> None:
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = " ".join(pyproject["project"]["dependencies"])
    for pkg, _ in CUDA_PACKAGES:
        assert pkg in declared
