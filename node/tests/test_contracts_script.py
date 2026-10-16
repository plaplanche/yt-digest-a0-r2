"""scripts/contracts.sh --check, run on a copy of the contracts and of the generated files."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "contracts.sh"
TS_DIR = Path("worker/src/contracts")
PY_DIR = Path("node/src/yt_digest_node/contracts")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for part in (Path("contracts"), TS_DIR, PY_DIR):
        shutil.copytree(REPO / part, tmp_path / part, ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def check(root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ | {"CONTRACTS_ROOT": str(root)}
    return subprocess.run(
        [str(SCRIPT), "--check"], env=env, capture_output=True, text=True, check=False
    )


def test_check_passes_on_committed_files(root: Path) -> None:
    run = check(root)
    assert run.returncode == 0, run.stderr


def test_check_fails_on_a_hand_edited_file(root: Path) -> None:
    edited = TS_DIR / "transcript-result.ts"
    with open(root / edited, "a") as file:
        file.write("// edited by hand\n")
    run = check(root)
    assert run.returncode == 1
    assert str(edited) in run.stderr
    assert "log-event.ts" not in run.stderr


def test_check_fails_when_a_schema_changes_without_regeneration(root: Path) -> None:
    schema = root / "contracts" / "log-event.schema.json"
    schema.write_text(schema.read_text().replace('"sponsorblock.call"', '"sponsorblock.call", "x"'))
    run = check(root)
    assert run.returncode == 1
    assert str(TS_DIR / "log-event.ts") in run.stderr
    assert str(PY_DIR / "log_event_schema.py") in run.stderr
    assert "transcript" not in run.stderr
