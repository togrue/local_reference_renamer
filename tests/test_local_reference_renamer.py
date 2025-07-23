import subprocess
import tempfile
import sys
from pathlib import Path

from .golden_utils import compare_with_golden


def test_golden_project_scan(golden_project, request):
    """Test that the golden project scan works correctly."""
    result = golden_project

    # Check that scan completed successfully
    assert result["scan_returncode"] == 0, f"Scan failed: {result['scan_stderr']}"

    # Check that we got some output
    assert result["scan_output"], "No scan output produced"

    # Compare with golden file
    assert compare_with_golden(
        result["scan_output"],
        "golden_scan_output.txt",
        request,
        "Scan output should match golden file",
    ), "Scan output does not match golden file"


def test_golden_project_dry_run(golden_project, request):
    """Test that dry-run mode works correctly."""
    result = golden_project

    # Check that dry-run completed successfully
    assert result["dry_run_returncode"] == 0, (
        f"Dry-run failed: {result['dry_run_stderr']}"
    )

    # Check that we got some output
    assert result["dry_run_output"], "No dry-run output produced"

    # Compare with golden file
    assert compare_with_golden(
        result["dry_run_output"],
        "golden_dry_run_output.txt",
        request,
        "Dry-run output should match golden file",
    ), "Dry-run output does not match golden file"


def test_golden_project_commit_hash(golden_project, request):
    """Test that we're testing against the expected commit hash."""
    result = golden_project

    # Compare commit hash with golden file
    assert compare_with_golden(
        result["commit_hash"],
        "golden_commit_hash.txt",
        request,
        "Commit hash should match golden file",
    ), "Commit hash does not match golden file"
