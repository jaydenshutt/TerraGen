"""Pytest configuration and shared fixtures for TerraGen tests."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "terraform: requires terraform or tofu on PATH for init/validate",
    )
    config.addinivalue_line(
        "markers",
        "live_aws: optional read-only AWS API tests (skip without credentials)",
    )


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    return EXAMPLES
