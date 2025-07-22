#!/usr/bin/env python3
"""
Script to generate initial golden files for testing.

This script runs the golden project tests and saves the output as golden files.
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    """Generate golden files by running tests with --update-golden flag."""
    # Change to the project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("Generating golden files...")

    # Run the golden project tests with --update-golden flag
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_local_reference_renamer.py::test_golden_project_scan",
            "tests/test_local_reference_renamer.py::test_golden_project_dry_run",
            "tests/test_local_reference_renamer.py::test_golden_project_commit_hash",
            "--update-golden",
            "-v",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✅ Golden files generated successfully!")
        print("\nGenerated files:")
        golden_dir = Path("tests/golden_files")
        for file in golden_dir.glob("*.txt"):
            print(f"  - {file}")
    else:
        print("❌ Failed to generate golden files:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
