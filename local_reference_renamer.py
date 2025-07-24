import argparse
import os
import sys
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import time

import libcst as cst
from libcst.metadata import QualifiedNameProvider, PositionProvider, MetadataWrapper
from tabulate import tabulate

# Constants
MAX_CACHE_SIZE = 1000

defaultdict_float = lambda: 0.0
# Global timing accumulators
timings: Dict[str, float] = defaultdict(defaultdict_float)
counts: Dict[str, int] = defaultdict(int)


@lru_cache(maxsize=MAX_CACHE_SIZE)
def parse_module(source: str) -> cst.Module:
    """Parse and cache a CPS source string into a LibCST Module."""
    return cst.parse_module(source)


def quick_reference_check(source: str, targets: Set[str]) -> bool:
    """
    Quickly scan source for any import or attribute usage matching targets.
    """
    return any(
        f"import {name}" in source or f"from {name}" in source or f"{name}." in source
        for name in targets
    )


def process_file(
    file_path: Path,
    definitions: Dict[Path, Dict[str, List[str]]],
    module_map: Dict[str, Path],
    targets: Set[str],
) -> List[Tuple[Path, str, str, int, int]]:
    """
    Read a file and, if it passes quick checks, collect symbol references using metadata.
    Also records timing for each phase.
    """
    t_start = time.perf_counter()

    # Read file
    t0 = time.perf_counter()
    try:
        src = file_path.read_text(encoding="utf8")
    except OSError:
        return []
    timings["read_file"] += time.perf_counter() - t0
    counts["read_file"] += 1

    # Quick reference check
    t1 = time.perf_counter()
    if not quick_reference_check(src, targets):
        timings["quick_check"] += time.perf_counter() - t1
        counts["quick_check"] += 1
        return []
    timings["quick_check"] += time.perf_counter() - t1
    counts["quick_check"] += 1

    # Parse + metadata setup
    t2 = time.perf_counter()
    try:
        module = parse_module(src)
        wrapper = MetadataWrapper(module, (QualifiedNameProvider, PositionProvider))
    except Exception:
        return []
    timings["parse_metadata"] += time.perf_counter() - t2
    counts["parse_metadata"] += 1

    # Visit
    collector = SymbolCollector(definitions, module_map, file_path, targets)
    t3 = time.perf_counter()
    wrapper.visit(collector)
    timings["visit"] += time.perf_counter() - t3
    counts["visit"] += 1

    timings["process_file_total"] += time.perf_counter() - t_start
    counts["process_file_total"] += 1

    return collector.refs


def collect_definitions(
    root: Path, files: List[Path]
) -> Tuple[Dict[Path, Dict[str, List[str]]], Dict[str, Path]]:
    """
    Collect top-level function and global names from each Python file.
    Returns definitions and a mapping from module name to file Path.
    Also records timing.
    """
    t0 = time.perf_counter()
    definitions: Dict[Path, Dict[str, List[str]]] = {}
    module_map: Dict[str, Path] = {}

    for path in files:
        try:
            src = path.read_text(encoding="utf8")
            module = parse_module(src)
        except Exception:
            continue

        rel = path.relative_to(root).with_suffix("")
        mod_name = str(rel).replace(os.sep, ".")
        module_map[mod_name] = path

        funcs: List[str] = []
        globals_: List[str] = []
        for node in module.body:
            if isinstance(node, cst.FunctionDef):
                funcs.append(node.name.value)
            elif isinstance(node, cst.SimpleStatementLine):
                for small in node.body:
                    if isinstance(small, cst.Assign):
                        for t in small.targets:
                            target = t.target
                            if isinstance(target, cst.Name):
                                globals_.append(target.value)
                            elif isinstance(target, cst.Tuple):
                                globals_.extend(
                                    e.value.value
                                    for e in target.elements
                                    if isinstance(e.value, cst.Name)
                                )
                    elif isinstance(small, cst.AnnAssign) and isinstance(
                        small.target, cst.Name
                    ):
                        globals_.append(small.target.value)

        definitions[path] = {"funcs": funcs, "globals": globals_}

    timings["collect_definitions"] += time.perf_counter() - t0
    counts["collect_definitions"] += 1
    return definitions, module_map


class SymbolCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (QualifiedNameProvider, PositionProvider)

    def __init__(
        self,
        definitions: Dict[Path, Dict[str, List[str]]],
        module_map: Dict[str, Path],
        current_file: Path,
        targets: Set[str],
    ):
        self.definitions = definitions
        self.module_map = module_map
        self.current_file = current_file
        self.targets = targets
        self.refs: List[Tuple[Path, str, str, int, int]] = []

        # build symbol index once per collector
        self.symbol_index = {
            (path, name, kind)
            for path, kinds in definitions.items()
            for kind, names in kinds.items()
            for name in names
        }

    def _add_ref(self, full_name: str, pos, kind: str) -> None:
        if "." not in full_name:
            return
        mod, name = full_name.rsplit(".", 1)
        if mod not in self.targets:
            return
        path = self.module_map.get(mod)
        if not path or path == self.current_file:
            return
        key = (path, name, kind)
        if key in self.symbol_index:
            self.refs.append((path, name, kind, pos.start.line, pos.start.column))

    def visit_Attribute(self, node: cst.Attribute) -> None:
        pos = self.get_metadata(PositionProvider, node)
        for qn in self.get_metadata(QualifiedNameProvider, node):
            self._add_ref(qn.name, pos, "funcs")
            self._add_ref(qn.name, pos, "globals")

    def visit_Call(self, node: cst.Call) -> None:
        pos = self.get_metadata(PositionProvider, node.func)
        for qn in self.get_metadata(QualifiedNameProvider, node.func):
            self._add_ref(qn.name, pos, "funcs")

    def visit_Name(self, node: cst.Name) -> None:
        pos = self.get_metadata(PositionProvider, node)
        for qn in self.get_metadata(QualifiedNameProvider, node):
            self._add_ref(qn.name, pos, "funcs")
            self._add_ref(qn.name, pos, "globals")


def _find_first_occurrence(path: Path, ident: str) -> int | None:
    """Return 1‑based line number of the first occurrence of *ident* in *path* (best‑effort)."""
    try:
        src = path.read_text(encoding="utf8")
        mod = parse_module(src)
        wrapper = MetadataWrapper(mod, (PositionProvider,))
        for node in mod.deep_children():
            if isinstance(node, cst.Name) and node.value == ident:
                pos = wrapper.get_metadata(PositionProvider, node)
                return pos.start.line
    except Exception:
        pass
    return None


def apply_renames(
    definitions: Dict[Path, Dict[str, List[str]]],
    refs: Dict[Tuple[Path, str, str], List[Tuple[Path, int, int]]],
    *,
    dry_run: bool = False,
) -> List[Tuple[Path, str, str]]:
    """Batch‑rename local‑only symbols.

    Skips a rename if the intended *new* name already exists in that file and issues a warning.
    Returns the list of successfully planned/applied renames.
    """
    t0 = time.perf_counter()
    planned: List[Tuple[Path, str, str]] = []
    warnings: List[str] = []

    # Group by file so we parse/transform once per file
    renames_by_file: Dict[Path, List[Tuple[str, str]]] = defaultdict(list)

    for (path, name, _kind), occurrences in refs.items():
        # Skip symbols that are referenced, start with underscore, or collide with an existing name
        if occurrences or name.startswith("_"):
            continue
        new = f"_{name}"

        # Detect collision with an existing top‑level name in the same file
        existing = set(definitions[path]["funcs"]) | set(definitions[path]["globals"])
        if new in existing:
            line = _find_first_occurrence(path, new)
            loc = f"{path}:{line}" if line else str(path)
            warnings.append(
                f"Skip rename {name!r} → {new!r}: name already exists at {loc}"
            )
            continue

        planned.append((path, name, new))
        renames_by_file[path].append((name, new))

    # Apply per‑file transformers
    if not dry_run:
        for path, pairs in renames_by_file.items():
            src = path.read_text(encoding="utf8")
            mod = cst.parse_module(src)
            transformer = MultiSymbolRenamer(pairs)
            result = mod.visit(transformer)
            path.write_text(result.code, encoding="utf8")

    timings["apply_renames"] += time.perf_counter() - t0
    counts["apply_renames"] += 1

    # Emit warnings
    if warnings:
        print("\nRename warnings:")
        for w in warnings:
            print("  •", w)

    return planned


class MultiSymbolRenamer(cst.CSTTransformer):
    def __init__(self, pairs: List[Tuple[str, str]]):
        self.pairs = pairs

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        for old, new in self.pairs:
            if original_node.value == old:
                return updated_node.with_changes(value=new)
        return updated_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        for old, new in self.pairs:
            if original_node.name.value == old:
                return updated_node.with_changes(
                    name=updated_node.name.with_changes(value=new)
                )
        return updated_node


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze and optionally rename local-only symbols."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("sources", nargs="*", type=Path)
    parser.add_argument("--rename-locals", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--funcs", action="store_true")
    parser.add_argument("--globals", action="store_true")
    parser.add_argument("--warn-unused", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    all_files = [p for p in root.rglob("*.py") if not p.name.startswith("__")]
    targets = (
        [root.joinpath(s).resolve() for s in args.sources]
        if args.sources
        else all_files
    )

    show_funcs = args.funcs or not args.globals
    show_globals = args.globals or not args.funcs

    if args.warn_unused:
        args.verbose = True

    # Collect definitions
    definitions, module_map = collect_definitions(root, targets)

    # Initialize refs
    refs: Dict[Tuple[Path, str, str], List[Tuple[Path, int, int]]] = {
        (path, n, k): []
        for path, kinds in definitions.items()
        for k, names in kinds.items()
        for n in names
    }
    targets_set = set(module_map.keys())

    # Process each file
    for file in all_files:
        for ref in process_file(file, definitions, module_map, targets_set):
            key = (ref[0], ref[1], ref[2])
            refs[key].append((file, ref[3], ref[4]))

    # Display results
    table = []
    local_only = False
    for (path, name, kind), occ in refs.items():
        if kind == "funcs" and not show_funcs:
            continue
        if kind == "globals" and not show_globals:
            continue
        table.append([name, kind[0], path.name, len(occ)])
        if not occ:
            local_only = True
            if args.verbose:
                print(f"Local-only: {name} in {path}")

    print(
        tabulate(table, headers=["Symbol", "Type", "Module", "Count"], tablefmt="grid")
    )

    if args.rename_locals:
        plan = apply_renames(definitions, refs, dry_run=args.dry_run)
        label = "Planned renames" if args.dry_run else "Applied renames"
        print(f"\n{label}:")
        for p, old, new in plan:
            print(f" - {old} -> {new} in {p.relative_to(root)}")

    # # Print timing summary
    # print("\nTiming summary:")
    # for key, total in timings.items():
    #     count = counts.get(key, 0)
    #     avg = total / count if count else 0
    #     print(f" {key}: total={total:.3f}s, count={count}, avg={avg:.4f}s")

    return 0 if local_only else 1


if __name__ == "__main__":
    sys.exit(main())
