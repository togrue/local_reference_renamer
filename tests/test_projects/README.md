# Test Projects

This directory contains test projects for regression testing the local reference renamer tool.

## Structure

- `original/` - Original project files before renaming
- `renamed/` - Expected project files after renaming
- `test_project.py` - A simple test project with local-only symbols

## Test Project

The test project contains:
- Functions that are used externally (should not be renamed)
- Functions that are only used locally (should be renamed with `_` prefix)
- Global variables that are used externally (should not be renamed)
- Global variables that are only used locally (should be renamed with `_` prefix)

## Usage

Tests compare the output of running the renamer on the original project against the expected renamed state.