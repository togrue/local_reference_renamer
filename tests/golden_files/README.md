# Golden Files Testing

This directory contains expected output files for regression testing against the HDL-FSM-Editor project.

## Files

- `golden_scan_output.txt` - Expected output from scanning the golden project
- `golden_dry_run_output.txt` - Expected output from dry-run mode
- `golden_commit_hash.txt` - The commit hash of the golden project version being tested against

## Updating Golden Files

To update the golden files after making changes to the tool:

1. Run the tests with the `--update-golden` flag:
   ```bash
   pytest tests/ -k "golden" --update-golden
   ```

2. Review the changes to ensure they're expected
3. Commit the updated golden files

## Golden Project

The golden project is the HDL-FSM-Editor repository, which provides a real-world Python codebase for testing the reference renamer tool.