"""Utilities for test result comparison and output tracking."""

import difflib
from pathlib import Path
from typing import Union, Optional


def get_results_dir():
    """Get the path to the test results directory."""
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    return results_dir


def save_test_output(test_name: str, content: str, filename: str = None):
    """
    Save test output to a file in the results directory.

    Args:
        test_name: Name of the test (used for directory/subdirectory creation)
        content: The content to save
        filename: Optional filename, defaults to test_name.txt
    """
    results_dir = get_results_dir()

    if filename is None:
        filename = f"{test_name}.txt"

    output_path = results_dir / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_diff_file(
    test_name: str, actual_content: str, expected_content: str, filename: str = None
):
    """
    Create a diff file showing differences between actual and expected content.

    Args:
        test_name: Name of the test
        actual_content: The actual output content
        expected_content: The expected output content
        filename: Optional filename, defaults to test_name.diff

    Returns:
        Path to the created diff file
    """
    results_dir = get_results_dir()

    if filename is None:
        filename = f"{test_name}.diff"

    diff_path = results_dir / filename
    diff_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate unified diff
    diff_lines = difflib.unified_diff(
        expected_content.splitlines(keepends=True),
        actual_content.splitlines(keepends=True),
        fromfile=f"expected_{test_name}",
        tofile=f"actual_{test_name}",
        lineterm="",
    )

    diff_content = "".join(diff_lines)
    diff_path.write_text(diff_content, encoding="utf-8")

    return diff_path


def create_directory_diff(
    test_name: str, actual_dir: Union[str, Path], expected_dir: Union[str, Path]
):
    """
    Create a diff for entire directories and save to a subdirectory.

    Args:
        test_name: Name of the test
        actual_dir: Path to actual directory
        expected_dir: Path to expected directory

    Returns:
        Path to the created diff directory
    """
    results_dir = get_results_dir()
    diff_dir = results_dir / test_name
    diff_dir.mkdir(parents=True, exist_ok=True)

    actual_path = Path(actual_dir)
    expected_path = Path(expected_dir)

    # Get all files in both directories
    actual_files = set(actual_path.rglob("*")) if actual_path.exists() else set()
    expected_files = set(expected_path.rglob("*")) if expected_path.exists() else set()

    all_files = actual_files | expected_files

    for file_path in all_files:
        if file_path.is_file():
            # Determine relative paths
            rel_path = file_path.relative_to(
                actual_path if file_path in actual_files else expected_path
            )

            actual_file = actual_path / rel_path
            expected_file = expected_path / rel_path

            # Create diff for this file
            if actual_file.exists() and expected_file.exists():
                actual_content = actual_file.read_text(encoding="utf-8")
                expected_content = expected_file.read_text(encoding="utf-8")

                if actual_content != expected_content:
                    diff_file = diff_dir / f"{rel_path}.diff"
                    diff_file.parent.mkdir(parents=True, exist_ok=True)

                    diff_lines = difflib.unified_diff(
                        expected_content.splitlines(keepends=True),
                        actual_content.splitlines(keepends=True),
                        fromfile=f"expected/{rel_path}",
                        tofile=f"actual/{rel_path}",
                        lineterm="",
                    )

                    diff_content = "".join(diff_lines)
                    diff_file.write_text(diff_content, encoding="utf-8")

            elif actual_file.exists():
                # File exists only in actual
                diff_file = diff_dir / f"{rel_path}.only_in_actual"
                diff_file.parent.mkdir(parents=True, exist_ok=True)
                diff_file.write_text(f"File only exists in actual: {rel_path}")

            elif expected_file.exists():
                # File exists only in expected
                diff_file = diff_dir / f"{rel_path}.only_in_expected"
                diff_file.parent.mkdir(parents=True, exist_ok=True)
                diff_file.write_text(f"File only exists in expected: {rel_path}")

    return diff_dir


def check_test_result_against_golden(
    test_name: str, result: str, golden_file_name: str, normalize: bool = True
) -> bool:
    """
    Check test result against golden file and save outputs.

    Args:
        test_name: Name of the test
        result: The actual test result/output
        golden_file_name: Name of the golden file to compare against
        normalize: Whether to normalize the output (remove dynamic paths, etc.)

    Returns:
        bool: True if results match, False if different
    """
    from .golden_utils import read_golden_file, normalize_output

    # Always save the current result
    save_test_output(test_name, result)

    # Read golden file
    golden_content = read_golden_file(golden_file_name)

    if golden_content is None:
        print(f"Warning: Golden file {golden_file_name} not found")
        return False

    # Normalize content if requested
    actual_content = normalize_output(result) if normalize else result
    expected_content = normalize_output(golden_content) if normalize else golden_content

    # Compare content
    if actual_content == expected_content:
        return True
    else:
        # Create diff file when content differs
        create_diff_file(test_name, actual_content, expected_content)
        return False


def check_test_result_against_golden_with_directory(
    test_name: str,
    result: str,
    golden_file_name: str,
    actual_dir: Optional[Union[str, Path]] = None,
    expected_dir: Optional[Union[str, Path]] = None,
    normalize: bool = True,
) -> bool:
    """
    Check test result against golden file and optionally create directory diffs.

    Args:
        test_name: Name of the test
        result: The actual test result/output
        golden_file_name: Name of the golden file to compare against
        actual_dir: Optional path to actual directory for directory diff
        expected_dir: Optional path to expected directory for directory diff
        normalize: Whether to normalize the output

    Returns:
        bool: True if results match, False if different
    """
    # Check the main result
    result_matches = check_test_result_against_golden(
        test_name, result, golden_file_name, normalize
    )

    # If directory comparison is requested and directories exist
    if actual_dir and expected_dir:
        actual_path = Path(actual_dir)
        expected_path = Path(expected_dir)

        if actual_path.exists() and expected_path.exists():
            create_directory_diff(test_name, actual_path, expected_path)

    return result_matches


def save_test_result_with_metadata(
    test_name: str, result: str, metadata: dict = None, filename: str = None
):
    """
    Save test result with additional metadata.

    Args:
        test_name: Name of the test
        result: The test result/output
        metadata: Optional dictionary of metadata to include
        filename: Optional filename
    """
    if metadata:
        # Create a formatted output with metadata
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append(f"Test: {test_name}")
        output_lines.append(
            f"Timestamp: {__import__('datetime').datetime.now().isoformat()}"
        )
        output_lines.append("=" * 80)
        output_lines.append("")

        # Add metadata
        if metadata:
            output_lines.append("METADATA:")
            for key, value in metadata.items():
                output_lines.append(f"  {key}: {value}")
            output_lines.append("")

        output_lines.append("RESULT:")
        output_lines.append("-" * 40)
        output_lines.append(result)

        content = "\n".join(output_lines)
    else:
        content = result

    return save_test_output(test_name, content, filename)
