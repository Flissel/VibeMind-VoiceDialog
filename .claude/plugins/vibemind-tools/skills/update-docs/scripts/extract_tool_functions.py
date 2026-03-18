#!/usr/bin/env python3
"""Extract public function signatures from Python tool modules for documentation."""

import ast
import re
import sys
from pathlib import Path


def extract_functions(filepath: Path) -> list[dict]:
    """Extract public function names, params, and first-line docstrings."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    functions = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        for m in re.finditer(r'^def\s+(\w+)\s*\(([^)]*)\)', content, re.MULTILINE):
            name = m.group(1)
            if name.startswith('_'):
                continue
            functions.append({"name": name, "params": m.group(2).strip(), "doc": ""})
        return functions

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            args = node.args
            params = []
            defaults_offset = len(args.args) - len(args.defaults)

            for i, arg in enumerate(args.args):
                if arg.arg == 'self':
                    continue
                param = arg.arg
                if arg.annotation and isinstance(arg.annotation, ast.Name):
                    param += f": {arg.annotation.id}"
                default_idx = i - defaults_offset
                if default_idx >= 0 and default_idx < len(args.defaults):
                    d = args.defaults[default_idx]
                    if isinstance(d, ast.Constant) and d.value is None:
                        param += "?"
                params.append(param)

            doc = ast.get_docstring(node) or ""
            if doc:
                doc = doc.split('\n')[0].strip()
                if len(doc) > 80:
                    doc = doc[:77] + "..."

            params_str = ", ".join(params) if params else "--"
            functions.append({"name": node.name, "params": params_str, "doc": doc})

    return functions


def format_table(functions: list[dict]) -> str:
    if not functions:
        return ""
    lines = [
        "| Function | Parameters | Description |",
        "|----------|-----------|-------------|"
    ]
    for f in functions:
        doc = f["doc"].replace("|", "/") if f["doc"] else "--"
        params = f["params"].replace("|", "/")
        lines.append(f"| `{f['name']}()` | {params} | {doc} |")
    return "\n".join(lines)


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    print("## Shared Utility Tools (python/tools/)\n")
    shared_dir = root / "python" / "tools"
    if shared_dir.exists():
        for f in sorted(shared_dir.glob("*.py")):
            if f.name.startswith("_"):
                continue
            funcs = extract_functions(f)
            if funcs:
                section_name = f.stem.replace("_", " ").title()
                print(f"### {section_name}\n")
                print(f"**File:** `python/tools/{f.name}`\n")
                print(format_table(funcs))
                print()

    print("\n## Space-Specific Tools\n")
    spaces_dir = root / "python" / "spaces"
    skip = {"__pycache__", "config", "autogen"}
    if spaces_dir.exists():
        for space_dir in sorted(spaces_dir.iterdir()):
            if not space_dir.is_dir() or space_dir.name in skip or space_dir.name.startswith(("_", ".")):
                continue
            tools_dir = space_dir / "tools"
            if not tools_dir.is_dir():
                continue
            space_name = space_dir.name.replace("_", " ").title()
            for f in sorted(tools_dir.glob("*.py")):
                if f.name.startswith("_"):
                    continue
                funcs = extract_functions(f)
                if funcs:
                    print(f"### {f.stem.replace('_', ' ').title()} ({space_name})\n")
                    print(f"**File:** `python/spaces/{space_dir.name}/tools/{f.name}`\n")
                    print(format_table(funcs))
                    print()


if __name__ == "__main__":
    main()
