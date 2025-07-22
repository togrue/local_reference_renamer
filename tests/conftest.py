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


@pytest.fixture
def golden_project(temp_dir, request):
    """
    Clone HDL-FSM-Editor and prepare it for testing.
    Returns a dict with project info and test results.
    """
    project_dir = temp_dir / "hdl-fsm-editor"

    # Clone the repository
    subprocess.run(
        [
            "git",
            "clone",
            "https://github.com/matthiasschweikart/HDL-FSM-Editor.git",
            str(project_dir),
        ],
        check=True,
        capture_output=True,
    )

    # Checkout a specific commit for consistency
    subprocess.run(
        ["git", "checkout", "main"], cwd=project_dir, check=True, capture_output=True
    )

    # Get the current commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    commit_hash = result.stdout.strip()

    # Find Python files
    python_files = list(project_dir.rglob("*.py"))

    # Get the Python interpreter from the current environment
    python_exe = sys.executable

    # Run reference finder (no renames)
    scan_result = subprocess.run(
        [
            python_exe,
            "local_reference_renamer.py",
            "--root",
            str(project_dir),
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
            str(project_dir),
            "--rename-locals",
            "--dry-run",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    # Save golden files if requested
    from .golden_utils import should_update_golden, write_golden_file

    if should_update_golden(request):
        write_golden_file("golden_scan_output.txt", scan_result.stdout)
        write_golden_file("golden_dry_run_output.txt", dry_run_result.stdout)
        write_golden_file("golden_commit_hash.txt", commit_hash)

    return {
        "project_dir": project_dir,
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
def synthetic_project(temp_dir):
    """Create a synthetic project for testing edge cases."""
    project_dir = temp_dir / "synthetic_project"
    project_dir.mkdir()

    # Create main module
    main_py = project_dir / "main.py"
    main_py.write_text("""
import os
from utils import helper_func, GLOBAL_VAR, _private_func

def public_function():
    return helper_func() + GLOBAL_VAR

def _local_function():
    return "local only"

if __name__ == "__main__":
    public_function()
""")

    # Create utils module
    utils_py = project_dir / "utils.py"
    utils_py.write_text("""
def helper_func():
    return "helper"

def _private_func():
    return "private"

GLOBAL_VAR = 42
_LOCAL_VAR = 100

# Tuple assignment
a, b = 1, 2
c, d = 3, 4

# Annotated assignment
value: int = 10
""")

    # Create unused module
    unused_py = project_dir / "unused.py"
    unused_py.write_text("""
def unused_function():
    return "never called"

UNUSED_GLOBAL = "never used"
""")

    return project_dir
