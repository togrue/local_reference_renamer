"""
Demo test file showing the new test result comparison functionality.
This file demonstrates how to use the check_test_result_against_golden function.
"""

import pytest
from .test_result_utils import (
    check_test_result_against_golden,
    check_test_result_against_golden_with_directory,
    save_test_result_with_metadata,
)


def test_demo_successful_comparison():
    """Demo test that should pass - output matches golden file."""
    # Simulate a test that produces some output
    test_output = """+-------------------------+--------+------------+---------+
| Symbol                  | Type   | Module     |   Count |
+=========================+========+============+=========+
| helper_func             | f      | helpers.py |       2 |
+-------------------------+--------+------------+---------+
| unused_function         | f      | unused.py  |       0 |
+-------------------------+--------+------------+---------+"""

    # This should pass if the golden file exists and matches
    # The output will be saved to tests/results/test_demo_successful_comparison.txt
    result = check_test_result_against_golden(
        "test_demo_successful_comparison",
        test_output,
        "golden_scan_output.txt",  # This should exist from other tests
    )

    # Note: This test might fail if the golden file doesn't match exactly
    # That's okay - the diff will be saved to tests/results/test_demo_successful_comparison.diff
    print(f"Comparison result: {result}")


def test_demo_failed_comparison():
    """Demo test that should fail - output doesn't match golden file."""
    # Simulate a test that produces different output
    test_output = """+-------------------------+--------+------------+---------+
| Symbol                  | Type   | Module     |   Count |
+=========================+========+============+=========+
| different_function      | f      | different.py |       1 |
+-------------------------+--------+------------+---------+"""

    # This should fail and create a diff file
    result = check_test_result_against_golden(
        "test_demo_failed_comparison", test_output, "golden_scan_output.txt"
    )

    # The output will be saved to tests/results/test_demo_failed_comparison.txt
    # The diff will be saved to tests/results/test_demo_failed_comparison.diff
    print(f"Comparison result: {result}")


def test_demo_with_metadata():
    """Demo test showing how to save test results with metadata."""
    test_output = "This is a test output with some data"

    metadata = {
        "test_type": "demo_metadata",
        "python_version": "3.9.0",
        "platform": "linux",
        "custom_field": "custom_value",
    }

    # Save the test result with metadata
    output_path = save_test_result_with_metadata(
        "test_demo_with_metadata", test_output, metadata
    )

    print(f"Test result saved to: {output_path}")

    # The output file will contain both the metadata and the result
    assert output_path.exists()


def test_demo_directory_comparison(tmp_path):
    """Demo test showing directory comparison functionality."""
    # Create some test files
    actual_dir = tmp_path / "actual"
    expected_dir = tmp_path / "expected"

    actual_dir.mkdir()
    expected_dir.mkdir()

    # Create files in actual directory
    (actual_dir / "file1.txt").write_text("content1")
    (actual_dir / "file2.txt").write_text("content2")

    # Create files in expected directory (with one difference)
    (expected_dir / "file1.txt").write_text("content1")
    (expected_dir / "file2.txt").write_text("different_content")

    # This will create directory diffs in tests/results/test_demo_directory_comparison/
    result = check_test_result_against_golden_with_directory(
        "test_demo_directory_comparison",
        "Directory comparison test",
        "dummy_golden.txt",  # Won't be used since we're doing directory diff
        actual_dir=actual_dir,
        expected_dir=expected_dir,
    )

    print(f"Directory comparison result: {result}")
