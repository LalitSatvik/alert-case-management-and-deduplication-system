"""Local pytest config for the repo-root e2e suite.

The backend suite (rootdir ``backend/``) never collects this directory; when it
is run on its own from the repo root there is no ``pyproject.toml`` in scope, so
register the marker here to keep the run warning-free.
"""

from __future__ import annotations


def pytest_configure(config: object) -> None:
    config.addinivalue_line(  # type: ignore[attr-defined]
        "markers",
        "e2e: end-to-end smoke test against the full docker compose stack; set ACMS_E2E=1 to run",
    )
