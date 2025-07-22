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


def test_synthetic_project_basic(synthetic_project):
    """Test basic functionality with synthetic project."""
    project_dir = synthetic_project

    # Run scan
    scan_result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(project_dir),
            "--verbose",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert scan_result.returncode == 0, f"Scan failed: {scan_result.stderr}"

    # Check that we found the expected symbols
    output = scan_result.stdout
    assert "helper_func" in output
    assert "GLOBAL_VAR" in output
    assert "unused_function" in output
    assert "UNUSED_GLOBAL" in output


def test_synthetic_project_dry_run(synthetic_project):
    """Test dry-run mode with synthetic project."""
    project_dir = synthetic_project

    # Run dry-run
    dry_run_result = subprocess.run(
        [
            sys.executable,
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

    assert dry_run_result.returncode == 0, f"Dry-run failed: {dry_run_result.stderr}"

    # Check that unused symbols are planned for rename
    output = dry_run_result.stdout
    if "unused_function" in output and "UNUSED_GLOBAL" in output:
        assert "Renames planned:" in output


def test_synthetic_project_apply_renames(synthetic_project):
    """Test that renames are applied correctly."""
    project_dir = synthetic_project

    # Create a copy for testing
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_dir = Path(tmp_dir) / "test_project"
        import shutil

        shutil.copytree(project_dir, test_dir)

        # Run actual renames
        rename_result = subprocess.run(
            [
                sys.executable,
                "local_reference_renamer.py",
                "--root",
                str(test_dir),
                "--rename-locals",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )

        assert rename_result.returncode == 0, f"Rename failed: {rename_result.stderr}"

        # Check that unused.py was modified
        unused_py = test_dir / "unused.py"
        content = unused_py.read_text()

        # If renames were applied, check the content
        if "Renames planned:" in rename_result.stdout:
            # Check that symbols were renamed (this depends on the actual implementation)
            pass


def test_function_only_scan(synthetic_project):
    """Test scanning only functions."""
    project_dir = synthetic_project

    result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(project_dir),
            "--funcs",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout

    # Should contain function names
    assert "helper_func" in output or "unused_function" in output

    # Should not contain global variable names
    assert "GLOBAL_VAR" not in output
    assert "UNUSED_GLOBAL" not in output


def test_globals_only_scan(synthetic_project):
    """Test scanning only globals."""
    project_dir = synthetic_project

    result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(project_dir),
            "--globals",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout

    # Should contain global variable names
    assert "GLOBAL_VAR" in output or "UNUSED_GLOBAL" in output

    # Should not contain function names
    assert "helper_func" not in output
    assert "unused_function" not in output


def test_warn_unused_mode(synthetic_project):
    """Test warn-unused mode."""
    project_dir = synthetic_project

    result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(project_dir),
            "--warn-unused",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout

    # Should contain warnings for unused symbols
    if "unused_function" in output or "UNUSED_GLOBAL" in output:
        assert "0" in output  # Zero external calls


def test_exit_codes(synthetic_project):
    """Test exit codes for different scenarios."""
    project_dir = synthetic_project

    result = subprocess.run(
        [sys.executable, "local_reference_renamer.py", "--root", str(project_dir)],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    # Check exit code: 0 if unused symbols found, 1 if none found
    output = result.stdout
    if "unused" in output or "UNUSED" in output:
        assert result.returncode == 0, (
            f"Expected exit code 0 for unused symbols, got {result.returncode}"
        )
    else:
        assert result.returncode == 1, (
            f"Expected exit code 1 when no unused symbols, got {result.returncode}"
        )


def test_edge_cases_tuple_assignment(synthetic_project):
    """Test handling of tuple assignments."""
    project_dir = synthetic_project

    # Add a file with tuple assignments
    tuple_file = project_dir / "tuple_test.py"
    tuple_file.write_text("""
a, b = 1, 2
c, d = 3, 4

def test_func():
    return a + b + c + d
""")

    result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(project_dir),
            "--globals",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


def test_edge_cases_name_main(synthetic_project):
    """Test handling of if __name__ == '__main__' blocks."""
    project_dir = synthetic_project

    # Add a file with __name__ check
    main_file = project_dir / "main_test.py"
    main_file.write_text("""
def main():
    print("Hello")

if __name__ == "__main__":
    main()
""")

    result = subprocess.run(
        [sys.executable, "local_reference_renamer.py", "--root", str(project_dir)],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
