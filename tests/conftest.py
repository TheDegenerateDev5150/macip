import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"

# Make `import macip_lib` work for both the library tests and the tool wrappers.
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


@pytest.fixture(autouse=True)
def isolated_macip_state(tmp_path, monkeypatch):
    """Reset dry-run mode and point saved-state files at a temp dir per test."""
    import macip_lib

    macip_lib.set_dry_run(False)
    monkeypatch.setattr(macip_lib, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(macip_lib, "_BACKEND", "ip")
    yield
    macip_lib.set_dry_run(False)
