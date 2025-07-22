"""Utilities for golden file testing."""

import os
import pytest
from pathlib import Path


def get_golden_files_dir():
    """Get the path to the golden files directory."""
    return Path(__file__).parent / "golden_files"


def get_golden_file_path(filename):
    """Get the path to a specific golden file."""
    return get_golden_files_dir() / filename


def read_golden_file(filename):
    """Read a golden file and return its contents."""
    file_path = get_golden_file_path(filename)
    if file_path.exists():
        return file_path.read_text()
    return None


def write_golden_file(filename, content):
    """Write content to a golden file."""
    file_path = get_golden_file_path(filename)
    file_path.parent.mkdir(exist_ok=True)
    file_path.write_text(content)


def should_update_golden(request):
    """Check if golden files should be updated based on pytest configuration."""
    return request.config.getoption("--update-golden", default=False)


def normalize_output(content):
    """Normalize output content by replacing dynamic paths with placeholders."""
    import re

    # Replace Windows temp paths with placeholder
    content = re.sub(
        r"C:\\Users\\[^\\]+\\AppData\\Local\\Temp\\[^\\]+", "<TEMP_DIR>", content
    )

    # Replace Unix temp paths with placeholder
    content = re.sub(r"/tmp/[^/]+", "<TEMP_DIR>", content)

    # Replace any other temp directory patterns
    content = re.sub(r"tmp[0-9a-zA-Z]+", "<TEMP_DIR>", content)

    return content


def compare_with_golden(actual_content, golden_filename, request, description=""):
    """
    Compare actual content with golden file content.

    Args:
        actual_content: The actual output content
        golden_filename: Name of the golden file to compare against
        request: pytest request object for configuration access
        description: Description for the assertion message

    Returns:
        bool: True if content matches, False otherwise
    """
    # Normalize the actual content
    normalized_actual = normalize_output(actual_content)

    golden_content = read_golden_file(golden_filename)

    if golden_content is None:
        if should_update_golden(request):
            write_golden_file(golden_filename, normalized_actual)
            return True
        else:
            pytest.fail(
                f"Golden file {golden_filename} not found and --update-golden not specified"
            )

    if should_update_golden(request):
        write_golden_file(golden_filename, normalized_actual)
        return True

    # Normalize the golden content for comparison
    normalized_golden = normalize_output(golden_content)

    return normalized_actual == normalized_golden
