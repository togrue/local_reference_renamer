"""
Regression tests using test projects with known before/after states.
"""

import subprocess
import tempfile
import sys
import shutil
from pathlib import Path

import pytest


def test_project_scan_output():
    """Test that scanning the original project produces expected output."""
    original_dir = Path(__file__).parent / "test_projects" / "original"

    # Run scan on original project
    result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(original_dir),
            "--verbose",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Scan failed: {result.stderr}"

    output = result.stdout

    # Check that we found the expected symbols
    assert "public_function" in output
    assert "private_function" in output
    assert "GLOBAL_CONSTANT" in output
    assert "local_config" in output
    assert "unused_function" in output
    assert "UNUSED_GLOBAL" in output

    # Check that external calls are correct
    assert "public_function" in output and "1" in output  # Used externally
    assert "helper_func" in output and "1" in output  # Used externally
    assert "unused_function" in output and "0" in output  # Not used externally


def test_project_dry_run():
    """Test that dry-run mode shows expected renames."""
    original_dir = Path(__file__).parent / "test_projects" / "original"

    # Run dry-run on original project
    result = subprocess.run(
        [
            sys.executable,
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

    assert result.returncode == 0, f"Dry-run failed: {result.stderr}"

    output = result.stdout

    # Check that renames are planned for unused symbols
    assert "Planned renames:" in output
    assert "private_function -> _private_function" in output
    assert "local_config -> _local_config" in output
    assert "unused_function -> _unused_function" in output
    assert "UNUSED_GLOBAL -> _UNUSED_GLOBAL" in output
    assert "another_public_function -> _another_public_function" in output
    assert "process_data -> _process_data" in output

    # Check that public symbols that are actually used externally are not renamed
    # Look specifically in the "Planned renames:" section
    renames_section = (
        output.split("Planned renames:")[1] if "Planned renames:" in output else ""
    )
    # Use word boundaries to avoid partial matches
    import re

    assert not re.search(r"\bpublic_function\s*->", renames_section)
    assert not re.search(r"\bGLOBAL_CONSTANT\s*->", renames_section)
    assert not re.search(r"\bhelper_func\s*->", renames_section)


def test_project_apply_renames():
    """Test that applying renames produces the expected result."""
    original_dir = Path(__file__).parent / "test_projects" / "original"
    expected_dir = Path(__file__).parent / "test_projects" / "renamed"

    # Create a temporary copy for testing
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_dir = Path(tmp_dir) / "test_project"
        shutil.copytree(original_dir, test_dir)

        # Run actual renames
        result = subprocess.run(
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

        assert result.returncode == 0, f"Rename failed: {result.stderr}"

        # Compare each file with expected result
        for file_name in ["main.py", "utils.py", "helpers.py", "unused.py"]:
            actual_file = test_dir / file_name
            expected_file = expected_dir / file_name

            assert actual_file.exists(), f"File {file_name} was not created"
            assert expected_file.exists(), f"Expected file {file_name} not found"

            actual_content = actual_file.read_text()
            expected_content = expected_file.read_text()

            assert actual_content == expected_content, (
                f"File {file_name} content does not match expected result.\n"
                f"Expected:\n{expected_content}\n"
                f"Actual:\n{actual_content}"
            )


def test_project_function_only_scan():
    """Test scanning only functions."""
    original_dir = Path(__file__).parent / "test_projects" / "original"

    result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(original_dir),
            "--funcs",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout

    # Should contain function names
    assert "public_function" in output
    assert "private_function" in output
    assert "unused_function" in output

    # Should not contain global variable names
    assert "GLOBAL_CONSTANT" not in output
    assert "local_config" not in output
    assert "UNUSED_GLOBAL" not in output


def test_project_globals_only_scan():
    """Test scanning only globals."""
    original_dir = Path(__file__).parent / "test_projects" / "original"

    result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(original_dir),
            "--globals",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout

    # Should contain global variable names
    assert "GLOBAL_CONSTANT" in output
    assert "local_config" in output
    assert "UNUSED_GLOBAL" in output

    # Should not contain function names
    assert "public_function" not in output
    assert "private_function" not in output
    assert "unused_function" not in output


def test_project_warn_unused():
    """Test warn-unused mode."""
    original_dir = Path(__file__).parent / "test_projects" / "original"

    result = subprocess.run(
        [
            sys.executable,
            "local_reference_renamer.py",
            "--root",
            str(original_dir),
            "--warn-unused",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout

    # Should contain warnings for unused symbols
    assert "0" in output  # Zero external calls for unused symbols
