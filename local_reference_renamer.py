import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from functools import lru_cache

import re

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider, QualifiedNameProvider
from rope.base import project as rope_project
from rope.refactor.rename import Rename
from tabulate import tabulate


@lru_cache(maxsize=1000)
def parse_module_cached(source: str):
    """Cache parsed modules to avoid re-parsing the same content."""
    return cst.parse_module(source)


def quick_reference_check(source: str, target_module_names: Set[str]) -> bool:
    """
    Quick string-based check to see if a file might contain references to our target modules.
    This avoids expensive LibCST metadata analysis for files that don't need it.
    """
    # Use a single pass through the source to check for all patterns
    for module_name in target_module_names:
        # Check for imports or qualified name usage in one pass
        if (
            f"import {module_name}" in source
            or f"from {module_name}" in source
            or f"{module_name}." in source
        ):
            return True
    return False


def process_file_for_references_optimized(py, defs, module_map, target_module_names):
    """Process a single file for references with early filtering."""
    try:
        source = py.read_text(encoding="utf8")

        # Early filtering: skip files that don't contain potential references
        if not quick_reference_check(source, target_module_names):
            return []

        # Only do expensive metadata analysis if we passed the quick check
        module = parse_module_cached(source)
        wrapper = MetadataWrapper(module, [QualifiedNameProvider, PositionProvider])
    except Exception:
        return []

    collector = SymbolCollector(defs, module_map, py, target_module_names)
    wrapper.visit(collector)
    return collector.refs


def collect_definitions_lightweight(root: Path, targets) -> Tuple[Dict, Dict]:
    """
    Lightweight definition collection using only basic parsing, no metadata.
    Returns:
      defs: dict {module_path: {'funcs': [names], 'globals': [names]}}
      module_map: dict {module_name: module_path}
    """
    defs = {}
    module_map = {}

    for py in targets:
        try:
            source = py.read_text(encoding="utf8")
            module = parse_module_cached(source)
        except Exception:
            continue

        rel = py.relative_to(root).with_suffix("")
        module_name = str(rel).replace(os.sep, ".")
        module_map[module_name] = py

        funcs = []
        globals_ = []

        # Process top-level body items
        for stmt in module.body:
            # Function definitions
            if isinstance(stmt, cst.FunctionDef):
                funcs.append(stmt.name.value)
            # Simple statements for globals
            elif isinstance(stmt, cst.SimpleStatementLine):
                for small in stmt.body:
                    # Simple assignment: name = ...
                    if isinstance(small, cst.Assign):
                        for tgt in small.targets:
                            if isinstance(tgt.target, cst.Name):
                                globals_.append(tgt.target.value)
                            elif isinstance(tgt.target, cst.Tuple):
                                # Handle tuple assignments: a, b = 1, 2
                                for element in tgt.target.elements:
                                    if isinstance(element.value, cst.Name):
                                        globals_.append(element.value.value)
                    # Annotated assignment: name: type = ... or name: type
                    elif isinstance(small, cst.AnnAssign) and isinstance(
                        small.target, cst.Name
                    ):
                        globals_.append(small.target.value)

        defs[py] = {"funcs": funcs, "globals": globals_}

    return defs, module_map


def collect_definitions_and_references(root: Path, targets, search_paths):
    """
    Optimized version that uses two-phase parsing and early filtering.
    Single-threaded approach since GIL makes parallel processing ineffective.
    Returns:
      defs: dict {module_path: {'funcs': [names], 'globals': [names]}}
      module_map: dict {module_name: module_path}
      refs: dict {(def_path, name, sym_type): list of (caller_path, line, col)}
    """
    # Phase 1: Lightweight definition collection
    defs, module_map = collect_definitions_lightweight(root, targets)

    # Initialize refs dict
    refs = {
        (path, name, sym): []
        for path, kinds in defs.items()
        for sym, names in kinds.items()
        for name in names
    }

    # Create a set of all target module names for faster lookup
    target_module_names = set(module_map.keys())

    # Phase 2: Reference collection with early filtering (single-threaded)
    for py in search_paths:
        file_refs = process_file_for_references_optimized(
            py, defs, module_map, target_module_names
        )
        for def_path, name, sym_type, line, col in file_refs:
            refs[(def_path, name, sym_type)].append((py, line, col))

    return defs, module_map, refs


class SymbolCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (QualifiedNameProvider, PositionProvider)

    def __init__(self, definitions, module_map, current_path, target_module_names):
        self.definitions = definitions
        self.module_map = module_map
        self.current_path = current_path
        self.target_module_names = target_module_names
        self.refs = []  # list of (def_path, name, sym_type, line, col)

        # Pre-compute lookup sets for faster checking
        self.target_symbols = {}
        for def_path, kinds in definitions.items():
            for sym_type, names in kinds.items():
                for name in names:
                    self.target_symbols[(def_path, name, sym_type)] = True

    def _record(self, full: str, pos, sym_type: str):
        if "." not in full:
            return
        mod_name, name = full.rsplit(".", 1)

        # Early exit if module is not in our target modules
        if mod_name not in self.target_module_names:
            return

        def_path = self.module_map.get(mod_name)
        if not def_path or def_path == self.current_path:
            return

        # Fast lookup using pre-computed set
        if (def_path, name, sym_type) in self.target_symbols:
            self.refs.append(
                (def_path, name, sym_type, pos.start.line, pos.start.column)
            )

    def visit_Attribute(self, node: cst.Attribute):
        qnames = self.get_metadata(QualifiedNameProvider, node)
        pos = self.get_metadata(PositionProvider, node)
        for qn in qnames:
            self._record(qn.name, pos, "funcs")
            self._record(qn.name, pos, "globals")

    def visit_Name(self, node: cst.Name):
        pos = self.get_metadata(PositionProvider, node)
        qnames = self.get_metadata(QualifiedNameProvider, node)
        for qn in qnames:
            # global or function usage
            self._record(qn.name, pos, "globals")
            # functions caught in call

    def visit_Call(self, node: cst.Call):
        pos = self.get_metadata(PositionProvider, node.func)
        qnames = self.get_metadata(QualifiedNameProvider, node.func)
        for qn in qnames:
            self._record(qn.name, pos, "funcs")


def apply_renames(root: Path, definitions, refs, dry_run=False):
    """
    Rename any symbol (func or global) with zero external refs.
    Globals and funcs are prefixed with '_'.
    """
    if dry_run:
        planned = []
        for (def_path, name, sym_type), occ in refs.items():
            if occ:
                continue
            if name.startswith("_"):
                continue

            if sym_type == "funcs":
                new_name = "_" + name
            else:
                new_name = "_" + name
            planned.append((def_path, name, new_name))
        return planned

    proj = rope_project.Project(root.as_posix())
    planned = []
    for (def_path, name, sym_type), occ in refs.items():
        if occ:
            continue
        if name.startswith("_"):
            continue

        resource = proj.get_file(def_path.relative_to(root.absolute()).as_posix())
        source = resource.read()
        # find declaration offset

        if sym_type == "funcs":
            marker = f"def {name}("
            new_name = "_" + name
            idx = source.find(marker)
            offset = idx + 4  # Position after "def " but before the function name
        else:
            # Try different patterns for global variables
            new_name = "_" + name

            # Try simple assignment: name = ...
            marker = f"{name} ="
            idx = source.find(marker)
            offset = idx

            if idx == -1:
                # Try tuple assignment: name, ... = ...
                marker = f"{name},"
                idx = source.find(marker)
                offset = idx

            if idx == -1:
                # Try annotated form: name: type = ...
                marker = f"{name}:"
                idx = source.find(marker)
                offset = idx

            if idx == -1:
                continue
        rename = Rename(proj, resource, offset)
        changes = rename.get_changes(new_name)
        proj.do(changes)
        planned.append((def_path, name, new_name))
    proj.close()
    return planned


def main():
    p = argparse.ArgumentParser(
        description="Analyze and optionally rename local-only symbols."
    )
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("sources", nargs="*", type=Path)
    p.add_argument("--rename-locals", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--funcs", action="store_true")
    p.add_argument("--globals", action="store_true")
    p.add_argument("--warn-unused", action="store_true")
    args = p.parse_args()

    root = args.root.resolve()
    all_py = [p for p in root.rglob("*.py") if not p.name.startswith("__")]
    targets = [(root / s).resolve() for s in args.sources] if args.sources else all_py

    show_funcs = args.funcs or not args.globals
    show_globals = args.globals or not args.funcs

    print(
        f"Scanning {root}\nDefinitions in: {[t.name for t in targets]}\nReferences in {len(all_py)} files...\n"
    )

    # Use the optimized combined function
    definitions, module_map, refs = collect_definitions_and_references(
        root, targets, all_py
    )

    if show_globals and args.verbose:
        for mod, ks in definitions.items():
            if ks["globals"]:
                print(f"[DEBUG] {mod.name} globals: {ks['globals']}")

    # Prepare data for tabulate
    table_data = []
    unreferenced_symbols_found = False

    for (modpath, name, sym_type), occ in refs.items():
        if modpath not in definitions:
            continue
        if sym_type == "funcs" and not show_funcs:
            continue
        if sym_type == "globals" and not show_globals:
            continue

        tchar = "f" if sym_type == "funcs" else "g"
        table_data.append([name, tchar, modpath.name, len(occ)])

        # Check for unused symbols
        if len(occ) == 0:
            unreferenced_symbols_found = True
            if args.warn_unused:
                print(f"  WARNING: {name} has no external references")

        if args.verbose:
            for src, line, col in occ:
                print(f"  -> {src.relative_to(root)}:{line}:{col}")

    # Print the table using tabulate
    headers = ["Symbol", "Type", "Module", "External Calls"]

    table_output = tabulate(table_data, headers=headers, tablefmt="grid")

    # Print the table linewise to avoid buffering / truncation issues
    lines = table_output.split("\n")
    for i, line in enumerate(lines):
        print(line)

    if args.rename_locals:
        planned = apply_renames(root, definitions, refs, dry_run=args.dry_run)
        if planned:
            if args.dry_run:
                print("\nRenames planned:")
            else:
                print("\nRenames applied:")
            for path, old, new in planned:
                print(f" - {old} -> {new} in {path.relative_to(root)}")
        else:
            if args.dry_run:
                print("\nNo renames planned.")
            else:
                print("\nNo renames applied.")

    # Exit code: 0 if unused symbols found, 1 otherwise
    return 0 if unreferenced_symbols_found else 1


if __name__ == "__main__":
    sys.exit(main())
