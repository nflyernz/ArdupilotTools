"""Optional local BIN fixtures for test-only real-log regressions."""

from pathlib import Path

import pytest


def require_logs(*paths: str | Path) -> tuple[Path, ...]:
    """Return local BIN paths or skip with the missing fixture names."""
    logs = tuple(Path(path) for path in paths)
    missing = [str(path) for path in logs if not path.is_file()]
    if missing:
        pytest.skip(f"Missing local BIN fixture(s): {', '.join(missing)}")
    return logs


def require_log(path: str | Path) -> Path:
    """Return one required local BIN path or skip its regression."""
    return require_logs(path)[0]
