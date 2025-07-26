import subprocess
import tempfile
import sys
from pathlib import Path

from .golden_utils import compare_with_golden
from .test_result_utils import check_test_result_against_golden


def test_golden_project_scan(golden_project, request):
    """Test that the golden project scan works correctly."""
    result = golden_project

    # Check that scan completed and found naming convention violations (return code 1)
    assert result["scan_returncode"] == 1, (
        f"Scan should find violations but returned {result['scan_returncode']}: {result['scan_stderr']}"
    )

    # Check that we got some output
    assert result["scan_output"], "No scan output produced"

    # Use new test result comparison that saves outputs and creates diffs
    assert check_test_result_against_golden(
        "golden_project_scan",
        result["scan_output"],
        "golden_scan_output.txt",
    ), "Scan output does not match golden file"


def test_golden_project_dry_run(golden_project, request):
    """Test that dry-run mode works correctly."""
    result = golden_project

    # Check that dry-run completed successfully (return code 0 for successful renames)
    assert result["dry_run_returncode"] == 0, (
        f"Dry-run failed: {result['dry_run_stderr']}"
    )

    # Check that we got some output
    assert result["dry_run_output"], "No dry-run output produced"

    # Use new test result comparison that saves outputs and creates diffs
    assert check_test_result_against_golden(
        "golden_project_dry_run",
        result["dry_run_output"],
        "golden_dry_run_output.txt",
    ), "Dry-run output does not match golden file"


def test_golden_project_commit_hash(golden_project, request):
    """Test that we're testing against the expected commit hash."""
    result = golden_project

    # Use new test result comparison that saves outputs and creates diffs
    assert check_test_result_against_golden(
        "golden_project_commit_hash",
        result["commit_hash"],
        "golden_commit_hash.txt",
    ), "Commit hash does not match golden file"
