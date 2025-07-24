#!/usr/bin/env python3
"""
Setup script for HDL-FSM-Editor test project.
This script manages the original and golden versions of the project for testing.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configuration
REPO_URL = "https://github.com/matthiasschweikart/HDL-FSM-Editor.git"
EXPECTED_COMMIT = "182a2179d333161fa224cf868fe0ef2ae973531e"
PROJECTS_DIR = Path(__file__).parent
ORIGINAL_DIR = PROJECTS_DIR / "hdl_fsm_editor_original"
GOLDEN_DIR = PROJECTS_DIR / "hdl_fsm_editor_golden"


def run_command(cmd, cwd=None, check=True):
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {result.stderr}")
        sys.exit(1)
    return result


def setup_original_project():
    """Set up the original HDL-FSM-Editor project."""
    if ORIGINAL_DIR.exists():
        print(f"Original project already exists at {ORIGINAL_DIR}")
        return

    print(f"Cloning HDL-FSM-Editor to {ORIGINAL_DIR}")

    # Clone the repository
    run_command(["git", "clone", REPO_URL, str(ORIGINAL_DIR)])

    # Checkout the specific commit
    run_command(["git", "checkout", EXPECTED_COMMIT], cwd=ORIGINAL_DIR)

    # Verify we have the correct commit
    result = run_command(["git", "rev-parse", "HEAD"], cwd=ORIGINAL_DIR, check=False)
    actual_commit = result.stdout.strip()

    if actual_commit != EXPECTED_COMMIT:
        print(f"Warning: Expected commit {EXPECTED_COMMIT}, got {actual_commit}")
    else:
        print(f"Successfully checked out commit {EXPECTED_COMMIT}")


def setup_golden_project():
    """Set up the golden version of the project."""
    if GOLDEN_DIR.exists():
        print(f"Golden project already exists at {GOLDEN_DIR}")
        return

    print(f"Creating golden project at {GOLDEN_DIR}")

    # Copy the original project
    shutil.copytree(ORIGINAL_DIR, GOLDEN_DIR)

    print("Golden project created successfully")


def run_tool_on_original():
    """Run the local reference renamer on the original project."""
    print("Running local reference renamer on original project...")

    # Get the path to the main script
    main_script = Path(__file__).parent.parent.parent / "local_reference_renamer.py"

    # Run the tool
    result = run_command(
        [
            sys.executable,
            str(main_script),
            "--root",
            str(ORIGINAL_DIR),
            "--rename-locals",
            "--dry-run",
        ],
        check=False,
    )

    print(f"Tool exit code: {result.returncode}")
    if result.stdout:
        print("Tool output:")
        print(result.stdout)
    if result.stderr:
        print("Tool errors:")
        print(result.stderr)

    return result


def generate_diff():
    """Generate a diff between original and golden projects."""
    if not ORIGINAL_DIR.exists() or not GOLDEN_DIR.exists():
        print("Both original and golden projects must exist to generate diff")
        return

    print("Generating diff between original and golden projects...")

    # Use git diff for better output
    result = run_command(
        ["git", "diff", "--no-index", str(ORIGINAL_DIR), str(GOLDEN_DIR)], check=False
    )

    if result.stdout:
        print("Diff output:")
        print(result.stdout)
    else:
        print("No differences found between original and golden projects")


def main():
    """Main setup function."""
    print("Setting up HDL-FSM-Editor test projects...")

    # Ensure projects directory exists
    PROJECTS_DIR.mkdir(exist_ok=True)

    # Set up original project
    setup_original_project()

    # Set up golden project
    setup_golden_project()

    # Run the tool on original project
    tool_result = run_tool_on_original()

    # Generate diff
    generate_diff()

    print("Setup complete!")
    print(f"Original project: {ORIGINAL_DIR}")
    print(f"Golden project: {GOLDEN_DIR}")


if __name__ == "__main__":
    main()
