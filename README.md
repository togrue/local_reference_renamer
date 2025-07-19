# Local Reference Renamer

A Python tool that analyzes Python codebases to find and optionally rename local-only symbols (functions and global variables that are not used outside their module).

## Features

- **Symbol Analysis**: Scans Python files to identify functions and global variables
- **Reference Tracking**: Finds external references to symbols across modules
- **Selective Scanning**: Scan only functions, only globals, or both
- **Dry-run Mode**: Preview planned renames without applying them
- **Warning Mode**: Get warnings for unused symbols
- **Exit Codes**: Proper exit codes for CI integration

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd local_reference_renamer

# Install dependencies using uv
uv sync

# Or install manually
pip install libcst rope
```

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

## Output Format

The tool outputs a table showing:
- **Symbol**: Name of the function or global variable
- **Type**: `f` for functions, `g` for globals
- **Module**: The file containing the symbol
- **External Calls**: Number of references from other modules

Example output:
```
Symbol                Type     Module                   External Calls
------                ----     ------                   --------------
helper_func          f    utils.py                  1
unused_function      f    unused.py                 0
GLOBAL_VAR           g    utils.py                  1
UNUSED_GLOBAL        g    unused.py                 0
```

## Exit Codes

- `0`: Unused symbols were found
- `1`: No unused symbols found

This makes the tool suitable for CI integration to detect unused code.

## Examples

### Example 1: Basic Project Analysis

```bash
$ python local_reference_renamer.py --root ./my_project
Scanning /path/to/my_project
Definitions in: ['main.py', 'utils.py', 'unused.py']
References in 3 files...

Symbol                Type     Module                   External Calls
------                ----     ------                   --------------
main                  f    main.py                   0
helper_func          f    utils.py                  1
unused_function      f    unused.py                 0
GLOBAL_VAR           g    utils.py                  1
UNUSED_GLOBAL        g    unused.py                 0
```

### Example 2: Dry-run with Renames

```bash
$ python local_reference_renamer.py --root ./my_project --rename-locals --dry-run
# ... scan output ...

Renames planned:
 - unused_function -> _unused_function in unused.py
 - UNUSED_GLOBAL -> _UNUSED_GLOBAL in unused.py
```

### Example 3: Warning Mode

```bash
$ python local_reference_renamer.py --root ./my_project --warn-unused
# ... scan output ...
  WARNING: unused_function has no external references
  WARNING: UNUSED_GLOBAL has no external references
```

## Edge Cases Handled

The tool handles various Python constructs:

- **Tuple assignments**: `a, b = 1, 2`
- **Annotated assignments**: `value: int = 10`
- **`if __name__ == '__main__'` blocks**
- **Import aliases**
- **Already prefixed symbols** (skips `_private_func`)

## Testing

Run the test suite:

```bash
# Install test dependencies
uv sync --extra test

# Run tests
uv run python -m pytest tests/ -v

# Run with coverage
uv run python -m pytest tests/ --cov=local_reference_renamer
```

## Interpreting Test Failures

If tests fail, check:

1. **Import errors**: Ensure all dependencies are installed
2. **Permission errors**: Make sure you have write access to test directories
3. **Git clone failures**: Check network connectivity for golden project tests
4. **Encoding issues**: The tool uses ASCII arrows (`->`) for compatibility

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

[Add your license information here]
