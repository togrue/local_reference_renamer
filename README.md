# Local Reference Renamer

A Python tool that analyzes Python codebases to find and optionally rename local-only symbols (functions and global variables that are not used outside their module).

This tool renames local functions and globals to start with an `_`.
It has helped me a lot in a medium sized stand-alone project with many module-level functions and globals.

<details>
<summary><strong>What it handles and doesn't handle</strong></summary>

The tool works at the moment for:
- global functions
- global variables

But it does not handle:
- class types (feel free to contribute)
- class methods
- class attributes
- class variables

(As far i can think classes are tricky to implement as python can be very dynamic).
</details>

## Features

- **Symbol Analysis**: Scans Python files to identify functions and global variables
- **Reference Tracking**: Finds external references to symbols across modules
- **Selective Scanning**: Scan only functions, only globals, or both
- **Dry-run Mode**: Preview planned renames without applying them
- **Warning Mode**: Get warnings for unused symbols
- **Exit Codes**: Proper exit codes for CI integration

<details>
<summary><strong>Installation</strong></summary>

```bash
# Clone the repository
git clone <repository-url>
cd local_reference_renamer

# Install dependencies using uv
uv sync

# Or install manually
pip install libcst
```
</details>

## Usage

### Basic Scanning

Scan a project to see all symbols and their external reference counts:

```bash
python local_reference_renamer.py --root /path/to/your/project
```

### Selective Scanning

Scan only functions:
```bash
python local_reference_renamer.py --root /path/to/your/project --funcs
```

Scan only global variables:
```bash
python local_reference_renamer.py --root /path/to/your/project --globals
```

### Dry-run Mode

Preview what renames would be applied without actually making changes:

```bash
python local_reference_renamer.py --root /path/to/your/project --rename-locals --dry-run
```

### Apply Renames

Actually rename local-only symbols (prefixes them with `_`):

```bash
python local_reference_renamer.py --root /path/to/your/project --rename-locals
```

### Warning Mode

Get warnings for symbols with zero total references:

```bash
python local_reference_renamer.py --root /path/to/your/project --warn-unused
```

### Verbose Output

Get detailed information including file locations of references:

```bash
python local_reference_renamer.py --root /path/to/your/project --verbose
```

### Scan Specific Files

Scan only specific Python files instead of the entire project:

```bash
python local_reference_renamer.py --root /path/to/your/project src/main.py src/utils.py
```

<details>
<summary><strong>Output Format</strong></summary>

The tool outputs a table showing:
- **Symbol**: Name of the function or global variable
- **Type**: `f` for functions, `g` for globals
- **Module**: The file containing the symbol
- **Count**: Number of references from other modules

Example output:
```
+-------------------------+--------+------------+---------+
| Symbol                  | Type   | Module     |   Count |
+=========================+========+============+=========+
| helper_func             | f      | helpers.py |       2 |
+-------------------------+--------+------------+---------+
| unused_function         | f      | unused.py  |       0 |
+-------------------------+--------+------------+---------+
| GLOBAL_VAR              | g      | utils.py   |       1 |
+-------------------------+--------+------------+---------+
| UNUSED_GLOBAL           | g      | unused.py  |       0 |
+-------------------------+--------+------------+---------+
```
</details>

<details>
<summary><strong>Exit Codes</strong></summary>

- `0`: Unused symbols were found
- `1`: No unused symbols found

This makes the tool suitable for CI integration to detect unused code.
</details>

<details>
<summary><strong>Examples</strong></summary>

### Example 1: Basic Project Analysis

```bash
$ python local_reference_renamer.py --root ./my_project
+-------------------------+--------+------------+---------+
| Symbol                  | Type   | Module     |   Count |
+=========================+========+============+=========+
| main                    | f      | main.py    |       0 |
+-------------------------+--------+------------+---------+
| helper_func             | f      | utils.py   |       1 |
+-------------------------+--------+------------+---------+
| unused_function         | f      | unused.py  |       0 |
+-------------------------+--------+------------+---------+
| GLOBAL_VAR              | g      | utils.py   |       1 |
+-------------------------+--------+------------+---------+
| UNUSED_GLOBAL           | g      | unused.py  |       0 |
+-------------------------+--------+------------+---------+
```

### Example 2: Dry-run with Renames

```bash
$ python local_reference_renamer.py --root ./my_project --rename-locals --dry-run
+-------------------------+--------+------------+---------+
| Symbol                  | Type   | Module     |   Count |
+=========================+========+============+=========+
| main                    | f      | main.py    |       0 |
+-------------------------+--------+------------+---------+
| helper_func             | f      | utils.py   |       1 |
+-------------------------+--------+------------+---------+
| unused_function         | f      | unused.py  |       0 |
+-------------------------+--------+------------+---------+
| GLOBAL_VAR              | g      | utils.py   |       1 |
+-------------------------+--------+------------+---------+
| UNUSED_GLOBAL           | g      | unused.py  |       0 |
+-------------------------+--------+------------+---------+

Planned renames:
 - main -> _main in main.py
 - unused_function -> _unused_function in unused.py
 - UNUSED_GLOBAL -> _UNUSED_GLOBAL in unused.py
```

### Example 3: Warning Mode

```bash
$ python local_reference_renamer.py --root ./my_project --warn-unused
Unused: main in /path/to/my_project/main.py
Unused: unused_function in /path/to/my_project/unused.py
Unused: UNUSED_GLOBAL in /path/to/my_project/unused.py

+-------------------------+--------+------------+---------+
| Symbol                  | Type   | Module     |   Count |
+=========================+========+============+=========+
| main                    | f      | main.py    |       0 |
+-------------------------+--------+------------+---------+
| helper_func             | f      | utils.py   |       1 |
+-------------------------+--------+------------+---------+
| unused_function         | f      | unused.py  |       0 |
+-------------------------+--------+------------+---------+
| GLOBAL_VAR              | g      | utils.py   |       1 |
+-------------------------+--------+------------+---------+
| UNUSED_GLOBAL           | g      | unused.py  |       0 |
+-------------------------+--------+------------+---------+
```
</details>

<details>
<summary><strong>Edge Cases Handled</strong></summary>

The tool handles various Python constructs:

- **Tuple assignments**: `a, b = 1, 2`
- **Annotated assignments**: `value: int = 10`
- **`if __name__ == '__main__'` blocks**
- **Import aliases**
- **Already prefixed symbols** (skips `_private_func`)
</details>

<details>
<summary><strong>Testing</strong></summary>

Run the test suite:

```bash
# Install test dependencies
uv sync --extra test

# Run tests
uv run python -m pytest tests/ -v

# Run with coverage
uv run python -m pytest tests/ --cov=local_reference_renamer
```

### Regression Testing

The project uses two types of regression testing:

#### 1. Test Projects

Located in `tests/test_projects/`, these contain:
- `original/` - Project files before renaming
- `renamed/` - Expected project files after renaming

These test projects contain known patterns of public/private functions and variables to verify the tool works correctly.

#### 2. Golden Files Testing

The project also uses golden files testing against the HDL-FSM-Editor repository to ensure consistent behavior across changes. Golden files contain expected output from scanning the reference project.

#### Initial Setup

Generate initial golden files:

```bash
# Run the golden file generation script
python tests/generate_golden_files.py
```

#### Updating Golden Files

When you make changes that affect the tool's output format or behavior, update the golden files:

```bash
# Run tests with --update-golden flag
uv run python -m pytest tests/ -k "golden" --update-golden

# Or run the generation script
python tests/generate_golden_files.py
```

#### Golden Files

The following files are maintained in `tests/golden_files/`:
- `golden_scan_output.txt` - Expected output from scanning the golden project
- `golden_dry_run_output.txt` - Expected output from dry-run mode
- `golden_commit_hash.txt` - The commit hash of the golden project version being tested against

## Interpreting Test Failures

If tests fail, check:

1. **Import errors**: Ensure all dependencies are installed
2. **Permission errors**: Make sure you have write access to test directories
3. **Git clone failures**: Check network connectivity for golden project tests
4. **Encoding issues**: The tool uses ASCII arrows (`->`) for compatibility
</details>

<details>
<summary><strong>Contributing</strong></summary>

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request
</details>

<details>
<summary><strong>License</strong></summary>

[Add your license information here]
</details>
