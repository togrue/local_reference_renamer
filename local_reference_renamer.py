import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from functools import lru_cache

import re

import libcst as cst
import libcst.matchers as m
from libcst.metadata import MetadataWrapper, PositionProvider, QualifiedNameProvider
from rope.base import project as rope_project
from rope.refactor.rename import Rename
from tabulate import tabulate


@lru_cache(maxsize=1000)
def parse_module_cached(source: str):
    """Cache parsed modules to avoid re-parsing the same content."""
    return cst.parse_module(source)


def parse_module_uncached(source: str):
    """Non-cached version for debugging."""
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


def process_file_for_references_matcher(py, defs, module_map, target_module_names):
    """
    Process a single file using LibCST matchers - much faster than full visitors.
    This is the recommended LibCST approach for targeted pattern matching.
    """
    try:
        source = py.read_text(encoding="utf8")

        # Early filtering: skip files that don't contain potential references
        if not quick_reference_check(source, target_module_names):
            return []

        module = parse_module_cached(source)

        # Use matchers instead of full metadata analysis
        refs = []

        # Find all attribute accesses (module.function, module.variable)
        for node in m.findall(module, m.Attribute()):
            if isinstance(node.value, cst.Name):
                module_name = node.value.value
                if module_name in target_module_names:
                    attr_name = node.attr.value
                    def_path = module_map.get(module_name)
                    if def_path and def_path != py:
                        # Check if this is a function call
                        if isinstance(node.parent, cst.Call):
                            if attr_name in defs.get(def_path, {}).get("funcs", []):
                                refs.append(
                                    (def_path, attr_name, "funcs", 0, 0)
                                )  # Position not available without metadata
                        else:
                            # Check both functions and globals
                            if attr_name in defs.get(def_path, {}).get("funcs", []):
                                refs.append((def_path, attr_name, "funcs", 0, 0))
                            if attr_name in defs.get(def_path, {}).get("globals", []):
                                refs.append((def_path, attr_name, "globals", 0, 0))

        # Find all name references that might be qualified imports
        for node in m.findall(module, m.Name()):
            # This is a simplified check - in practice you'd need more sophisticated logic
            # to determine if a name refers to an imported symbol
            pass

    except Exception:
        return []

    return refs


def process_file_for_references_unoptimized(py, defs, module_map, target_module_names):
    """Process a single file for references without early filtering."""
    try:
        source = py.read_text(encoding="utf8")
        module = parse_module_uncached(source)
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


def collect_definitions_and_references_unoptimized(root: Path, targets, search_paths):
    """
    Unoptimized version that processes all files without early filtering.
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

    # Phase 2: Reference collection without early filtering (single-threaded)
    for py in search_paths:
        file_refs = process_file_for_references_unoptimized(
            py, defs, module_map, target_module_names
        )
        for def_path, name, sym_type, line, col in file_refs:
            refs[(def_path, name, sym_type)].append((py, line, col))

    return defs, module_map, refs


def collect_definitions_and_references_matcher(root: Path, targets, search_paths):
    """
    Ultra-fast version using LibCST matchers instead of full metadata analysis.
    This is the recommended approach for performance-critical applications.
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

    # Phase 2: Reference collection using matchers (much faster)
    for py in search_paths:
        file_refs = process_file_for_references_matcher(
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

    planned = []
    for (def_path, name, sym_type), occ in refs.items():
        if occ:
            continue
        if name.startswith("_"):
            continue

        new_name = "_" + name
        planned.append((def_path, name, new_name))

        if not dry_run:
            # Read the file
            source = def_path.read_text(encoding="utf8")

            # Create a transformer to rename the symbol
            transformer = SymbolRenamer(name, new_name)
            module = cst.parse_module(source)
            modified_module = module.visit(transformer)

            # Write back the modified content
            def_path.write_text(modified_module.code, encoding="utf8")

    return planned


class SymbolRenamer(cst.CSTTransformer):
    """LibCST transformer to rename symbols."""

    def __init__(self, old_name: str, new_name: str):
        self.old_name = old_name
        self.new_name = new_name

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        """Rename variable names."""
        if original_node.value == self.old_name:
            return updated_node.with_changes(value=self.new_name)
        return updated_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Rename function names."""
        if original_node.name.value == self.old_name:
            return updated_node.with_changes(
                name=updated_node.name.with_changes(value=self.new_name)
            )
        return updated_node


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
    p.add_argument("--no-optimizations", action="store_true")
    p.add_argument("--test-matcher", action="store_true")
    args = p.parse_args()

    root = args.root.resolve()
    all_py = [p for p in root.rglob("*.py") if not p.name.startswith("__")]
    targets = [(root / s).resolve() for s in args.sources] if args.sources else all_py

    show_funcs = args.funcs or not args.globals
    show_globals = args.globals or not args.funcs

    print(
        f"Scanning {root}\nDefinitions in: {[t.name for t in targets]}\nReferences in {len(all_py)} files...\n"
    )

    if args.test_matcher:
        definitions, module_map, refs = collect_definitions_and_references_matcher(
            root, targets, all_py
        )
    elif args.no_optimizations:
        definitions, module_map, refs = collect_definitions_and_references_unoptimized(
            root, targets, all_py
        )
    else:
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
