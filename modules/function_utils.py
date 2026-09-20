from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------


def _expand(path: str) -> Path:
    """Expand ~ and environment variables in `path`, then resolve to an absolute Path."""
    return Path(os.path.expandvars(os.path.expanduser(path))).resolve()

# ---------------------------------------------------------------------
# SOURCE COLLECTION
# ---------------------------------------------------------------------


def collect_usage_sources(check_folders, check_files, module_folder):
    """
    Collect Python sources to scan for function usage.

    Returns:
        (external_sources, internal_sources) as de-duplicated Path lists.
    """
    external = []
    internal = []
    for folder in check_folders or []:
        d = _expand(folder)
        if d.is_dir():
            external.extend(
                p for p in d.rglob("*.py")
                if p.is_file() and p.name != "__init__.py"
            )
    for file in check_files or []:
        p = _expand(file)
        if p.is_file() and p.suffix == ".py":
            external.append(p)
    mod_dir = _expand(module_folder)
    if mod_dir.is_dir():
        internal.extend(
            p for p in mod_dir.rglob("*.py")
            if p.is_file() and p.name != "__init__.py"
        )
    return list(dict.fromkeys(external)), list(dict.fromkeys(internal))

# ---------------------------------------------------------------------
# MODULE PARSING
# ---------------------------------------------------------------------


def load_module_functions(module_folder: str, job: str) -> Dict:
    """
    Parse a module file and return its top-level function AST nodes keyed by name.

    Example:
        fns = load_module_functions("./modules", "display_utils.py")
    """
    import ast
    module_path = Path(os.path.expandvars(os.path.expanduser(module_folder))) / job
    tree = ast.parse(module_path.read_text(encoding="utf-8", errors="replace"))
    return {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
    }


def load_module_function_docs(module_folder: str, job: str) -> Dict[str, str]:
    """
    Parse a module file and return {function_name: docstring} for top-level functions.

    Example:
        docs = load_module_function_docs("./modules", "display_utils.py")
    """
    import ast
    module_path = Path(os.path.expandvars(os.path.expanduser(module_folder))) / job
    tree = ast.parse(module_path.read_text(encoding="utf-8", errors="replace"))
    docs: Dict[str, str] = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            doc = ast.get_docstring(n) or ""
            docs[n.name] = doc.strip()
    return docs

# ---------------------------------------------------------------------
# USAGE SCANNING
# ---------------------------------------------------------------------


def scan_function_usage(module_functions: dict, check_folders, check_files, module_folder):
    """
    Scan configured external and internal Python sources for references
    to functions defined in a module.

    External sources include:
    - configured check folders
    - configured check files

    Internal sources include:
    - Python files under ModuleFolder
    """
    import ast
    external_sources, internal_sources = collect_usage_sources(check_folders, check_files, module_folder)
    used = {fn: set() for fn in module_functions}
    for src in external_sources + internal_sources:
        usage_type = "INTERNAL" if src in internal_sources else "EXTERNAL"
        try:
            tree = ast.parse(src.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in used:
                    used[node.func.id].add((str(src), node.lineno, usage_type))
                elif isinstance(node.func, ast.Attribute) and node.func.attr in used:
                    used[node.func.attr].add((str(src), node.lineno, usage_type))
            elif isinstance(node, ast.Name) and node.id in used:
                used[node.id].add((str(src), node.lineno, usage_type))
            elif isinstance(node, ast.Attribute) and node.attr in used:
                used[node.attr].add((str(src), node.lineno, usage_type))
    return {
        "usage": used,
        "sources": [str(s) for s in external_sources + internal_sources],
    }


def detect_usage(scan_result: dict) -> bool:
    """Return True if any function has at least one recorded usage location."""
    usage = scan_result["usage"]
    return any(locations for locations in usage.values())

# ---------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------


def print_usage_summary(job: str, scan_result: dict) -> None:
    """
    Print function usage split into:
      - EXTERNAL usage
      - INTERNAL-only usage
      - UNUSED
    """
    usage = scan_result["usage"]
    sources = scan_result.get("sources", [])
    print(f"\nFunction usage summary for job: {job}")
    print("\nScanned source files:")
    for src in sources:
        print(f"  - {src}")
    external = {}
    internal_only = {}
    unused = []
    for func_name, locations in usage.items():
        if not locations:
            unused.append(func_name)
            continue
        has_external = any(u_type == "EXTERNAL" for _, _, u_type in locations)
        if has_external:
            external[func_name] = locations
        else:
            internal_only[func_name] = locations
    if external:
        print("\n[EXTERNAL USAGE]")
        for func_name, locations in external.items():
            print(f"  {func_name}")
            for file, line, _ in sorted(locations):
                print(f"    ↳ {file}:{line}")
    if internal_only:
        print("\n[INTERNAL ONLY]")
        for func_name, locations in internal_only.items():
            print(f"  {func_name}")
            for file, line, _ in sorted(locations):
                print(f"    ↳ {file}:{line}")
    if unused:
        print("\n[UNUSED]")
        for func_name in sorted(unused):
            print(f"  {func_name}")


def print_functions_summary(job: str, fn_docs: Dict[str, str]) -> None:
    """Print module functions with aligned multi-line docstrings."""
    title = f"Functions for module: {job}"
    print(f"\n{title}")
    print("-" * len(title))
    print()
    if not fn_docs:
        print("  (no top-level functions found)")
        return
    name_width = max(len(name) for name in fn_docs)
    prefix = " " * (name_width + 3)
    for name in sorted(fn_docs):
        doc = fn_docs[name] or "(no docstring)"
        lines = doc.splitlines()
        print(f"{name.ljust(name_width)} : {lines[0]}")
        for line in lines[1:]:
            print(f"{prefix}{line}")
        print()
