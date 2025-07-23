import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

import pytest


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Update golden files with current output",
    )


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture(scope="session")
def cached_hdl_project():
    """
    Get the cached HDL-FSM-Editor project for testing.
    Uses pre-cloned projects instead of cloning every time.
    """
    projects_dir = Path(__file__).parent / "projects"
    original_dir = projects_dir / "hdl_fsm_editor_original"
    golden_dir = projects_dir / "hdl_fsm_editor_golden"

    # Check if cached projects exist
    if not original_dir.exists():
        pytest.skip(
            "Cached HDL-FSM-Editor project not found. Run setup_hdl_project.py first."
        )

    # Get the current commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=original_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    commit_hash = result.stdout.strip()

    # Find Python files
    python_files = list(original_dir.rglob("*.py"))

    # Get the Python interpreter from the current environment
    python_exe = sys.executable

    # Run reference finder (no renames)
    scan_result = subprocess.run(
        [
            python_exe,
            "local_reference_renamer.py",
            "--root",
            str(original_dir),
            "--verbose",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    # Run renamer in dry-run mode
    dry_run_result = subprocess.run(
        [
            python_exe,
            "local_reference_renamer.py",
            "--root",
            str(original_dir),
            "--rename-locals",
            "--dry-run",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    return {
        "original_dir": original_dir,
        "golden_dir": golden_dir,
        "commit_hash": commit_hash,
        "python_files": python_files,
        "scan_output": scan_result.stdout,
        "scan_stderr": scan_result.stderr,
        "scan_returncode": scan_result.returncode,
        "dry_run_output": dry_run_result.stdout,
        "dry_run_stderr": dry_run_result.stderr,
        "dry_run_returncode": dry_run_result.returncode,
    }


@pytest.fixture
def golden_project(cached_hdl_project, request):
    """
    Optimized golden project fixture using cached HDL-FSM-Editor.
    """
    result = cached_hdl_project

    # Save golden files if requested
    from .golden_utils import should_update_golden, write_golden_file

    if should_update_golden(request):
        write_golden_file("golden_scan_output.txt", result["scan_output"])
        write_golden_file("golden_dry_run_output.txt", result["dry_run_output"])
        write_golden_file("golden_commit_hash.txt", result["commit_hash"])

    return result
