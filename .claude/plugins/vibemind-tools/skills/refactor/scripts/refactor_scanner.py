#!/usr/bin/env python3
"""
Refactor Scanner — Analyzes codebase for large files needing refactoring.

Scans Python (via AST) and JS/TS (via regex) files, computes complexity scores,
identifies functions/classes/sections, maps internal dependencies, and outputs
structured reports for Claude-driven refactoring.

Usage:
    python refactor_scanner.py [--root /path/to/project]
    python refactor_scanner.py --threshold 200
    python refactor_scanner.py --json
    python refactor_scanner.py --yaml REFACTOR_REPORT.yml
"""

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class FunctionInfo:
    name: str
    line_start: int
    line_end: int
    lines: int
    is_async: bool = False
    is_method: bool = False
    parent_class: Optional[str] = None
    decorators: List[str] = field(default_factory=list)

@dataclass
class ClassInfo:
    name: str
    line_start: int
    line_end: int
    lines: int
    method_count: int
    methods: List[str] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)

@dataclass
class SectionInfo:
    name: str
    line_start: int
    line_end: int
    lines: int

@dataclass
class ImportInfo:
    module: str
    names: List[str]
    line: int
    is_internal: bool

@dataclass
class FileAnalysis:
    path: str
    language: str
    total_lines: int
    code_lines: int
    function_count: int
    class_count: int
    max_function_lines: int
    max_function_name: str
    complexity_score: float
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    sections: List[SectionInfo] = field(default_factory=list)
    internal_imports: List[ImportInfo] = field(default_factory=list)
    external_imports: List[ImportInfo] = field(default_factory=list)
    imported_by: List[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv", ".venv312",
    "dist", "build", ".eggs", "worktrees", ".worktrees",
}

SUBMODULE_MARKERS = {"Coding_engine", "Automation_ui", "swe_desgine", "rowboat", "minibook"}

PY_SECTION_RE = re.compile(r"^\s*#\s*[-=]{3,}\s*(.+?)\s*[-=]*\s*$")
JS_SECTION_RE = re.compile(r"^\s*//\s*[-=]{3,}\s*(.+?)\s*[-=]*\s*$")

JS_FUNC_RE = re.compile(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(")
JS_ARROW_RE = re.compile(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?.*?\)?\s*=>")
JS_METHOD_RE = re.compile(r"^\s+(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{")
JS_CLASS_RE = re.compile(r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{")
JS_IMPORT_RE = re.compile(r"""(?:import\s+.*?from\s+['"](.+?)['"]|require\s*\(\s*['"](.+?)['"]\s*\))""")

PATH_TO_DOMAIN = [
    ("spaces/ideas",        "Ideas"),
    ("spaces/coding",       "Coding"),
    ("spaces/desktop",      "Desktop"),
    ("spaces/rowboat",      "Rowboat"),
    ("spaces/research",     "Research"),
    ("spaces/minibook",     "Minibook"),
    ("spaces/schedule",     "Schedule"),
    ("spaces/shuttles",     "Shuttles"),
    ("spaces/roarboot",     "Rowboat"),
    ("spaces/brain",        "Brain"),
    ("spaces/n8n",          "N8n"),
    ("voice/",              "Voice"),
    ("swarm/orchestrator",  "Orchestrator"),
    ("swarm/",              "Swarm"),
    ("workers/",            "Workers"),
    ("publishing/",         "Publishing"),
    ("tools/",              "SharedTools"),
    ("data/",               "Data"),
    ("electron_backend",    "Core"),
    ("electron-app/",       "Electron"),
    ("ipc/",                "IPC"),
    ("tests/",              "Tests"),
]


def classify_domain(filepath: str) -> str:
    normalized = filepath.replace("\\", "/")
    for fragment, domain in PATH_TO_DOMAIN:
        if fragment in normalized:
            return domain
    return "Root"


def is_submodule(filepath: str) -> bool:
    return any(m in filepath for m in SUBMODULE_MARKERS)


# ---------------------------------------------------------------------------
# Python AST Analysis
# ---------------------------------------------------------------------------

def analyze_python(filepath: Path, root: Path) -> Optional[FileAnalysis]:
    """Analyze a Python file using AST."""
    rel = str(filepath.relative_to(root))
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    file_lines = source.splitlines()
    total_lines = len(file_lines)
    code_lines = sum(
        1 for ln in file_lines
        if ln.strip() and not ln.strip().startswith("#")
    )

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return None

    classes: List[ClassInfo] = []
    functions: List[FunctionInfo] = []
    internal_imports: List[ImportInfo] = []
    external_imports: List[ImportInfo] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            end = node.end_lineno or node.lineno
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(f"{getattr(base.value, 'id', '?')}.{base.attr}")
            classes.append(ClassInfo(
                name=node.name, line_start=node.lineno, line_end=end,
                lines=end - node.lineno + 1, method_count=len(methods),
                methods=methods, bases=bases,
            ))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno or node.lineno
            decorators = []
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                elif isinstance(dec, ast.Attribute):
                    decorators.append(dec.attr)

            parent_class = None
            is_method = False
            for cls in classes:
                if cls.line_start <= node.lineno <= cls.line_end:
                    parent_class = cls.name
                    is_method = True
                    break

            functions.append(FunctionInfo(
                name=node.name, line_start=node.lineno, line_end=end,
                lines=end - node.lineno + 1, is_async=isinstance(node, ast.AsyncFunctionDef),
                is_method=is_method, parent_class=parent_class, decorators=decorators,
            ))

        if isinstance(node, ast.Import):
            for alias in node.names:
                external_imports.append(ImportInfo(
                    module=alias.name, names=[alias.asname or alias.name],
                    line=node.lineno, is_internal=False,
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [a.name for a in node.names]
            is_internal = (node.level > 0) or module.split(".")[0] in {
                "data", "swarm", "tools", "voice", "spaces", "workers",
                "memory", "publishing", "electron_backend", "config",
                "debug", "ipc",
            }
            target = internal_imports if is_internal else external_imports
            target.append(ImportInfo(
                module=module, names=names, line=node.lineno, is_internal=is_internal,
            ))

    sections = _extract_sections(file_lines, PY_SECTION_RE)

    max_func = max(functions, key=lambda f: f.lines, default=None)
    max_func_lines = max_func.lines if max_func else 0
    max_func_name = max_func.name if max_func else ""

    score = _compute_score(total_lines, len(functions), len(classes), max_func_lines)

    return FileAnalysis(
        path=rel, language="python", total_lines=total_lines,
        code_lines=code_lines, function_count=len(functions),
        class_count=len(classes), max_function_lines=max_func_lines,
        max_function_name=max_func_name, complexity_score=round(score, 1),
        classes=classes, functions=functions, sections=sections,
        internal_imports=internal_imports, external_imports=external_imports,
    )


# ---------------------------------------------------------------------------
# JS/TS Regex Analysis
# ---------------------------------------------------------------------------

def analyze_js(filepath: Path, root: Path) -> Optional[FileAnalysis]:
    """Analyze a JS/TS file using regex patterns."""
    rel = str(filepath.relative_to(root))
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    file_lines = source.splitlines()
    total_lines = len(file_lines)
    code_lines = sum(
        1 for ln in file_lines
        if ln.strip() and not ln.strip().startswith("//") and not ln.strip().startswith("/*")
    )

    classes: List[ClassInfo] = []
    functions: List[FunctionInfo] = []
    internal_imports: List[ImportInfo] = []
    external_imports: List[ImportInfo] = []

    current_class = None

    for i, line in enumerate(file_lines, 1):
        m = JS_CLASS_RE.search(line)
        if m:
            current_class = m.group(1)
            bases = [m.group(2)] if m.group(2) else []
            classes.append(ClassInfo(
                name=current_class, line_start=i, line_end=i,
                lines=0, method_count=0, methods=[], bases=bases,
            ))

        for pattern in (JS_FUNC_RE, JS_ARROW_RE):
            m = pattern.search(line)
            if m:
                is_async = "async" in line[:m.start()]
                functions.append(FunctionInfo(
                    name=m.group(1), line_start=i, line_end=i,
                    lines=1, is_async=is_async,
                    is_method=False, parent_class=None,
                ))

        if current_class:
            m = JS_METHOD_RE.search(line)
            if m and m.group(1) not in ("if", "for", "while", "switch", "catch"):
                is_async = "async" in line[:m.start()]
                functions.append(FunctionInfo(
                    name=m.group(1), line_start=i, line_end=i,
                    lines=1, is_async=is_async,
                    is_method=True, parent_class=current_class,
                ))
                if classes:
                    classes[-1].method_count += 1
                    classes[-1].methods.append(m.group(1))

        m = JS_IMPORT_RE.search(line)
        if m:
            module = m.group(1) or m.group(2)
            is_internal = module.startswith(".") or module.startswith("/")
            target = internal_imports if is_internal else external_imports
            target.append(ImportInfo(
                module=module, names=[], line=i, is_internal=is_internal,
            ))

    # Approximate class line ranges
    for cls in classes:
        cls.line_end = min(cls.line_start + 500, total_lines)
        cls.lines = cls.line_end - cls.line_start

    sections = _extract_sections(file_lines, JS_SECTION_RE)

    max_func = max(functions, key=lambda f: f.lines, default=None)
    max_func_lines = max_func.lines if max_func else 0
    max_func_name = max_func.name if max_func else ""

    score = _compute_score(total_lines, len(functions), len(classes), max_func_lines)

    return FileAnalysis(
        path=rel, language="javascript", total_lines=total_lines,
        code_lines=code_lines, function_count=len(functions),
        class_count=len(classes), max_function_lines=max_func_lines,
        max_function_name=max_func_name, complexity_score=round(score, 1),
        classes=classes, functions=functions, sections=sections,
        internal_imports=internal_imports, external_imports=external_imports,
    )


# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------

def _extract_sections(lines: list, pattern: re.Pattern) -> List[SectionInfo]:
    """Extract comment-delimited sections from source lines."""
    sections = []
    for i, line in enumerate(lines, 1):
        m = pattern.match(line)
        if m:
            name = m.group(1).strip()
            if len(name) > 2:
                sections.append(SectionInfo(name=name, line_start=i, line_end=i, lines=0))

    for j, sec in enumerate(sections):
        if j + 1 < len(sections):
            sec.line_end = sections[j + 1].line_start - 1
        else:
            sec.line_end = len(lines)
        sec.lines = sec.line_end - sec.line_start + 1

    return sections


def _compute_score(total_lines: int, func_count: int, class_count: int, max_func_lines: int) -> float:
    """Compute complexity score. Higher = more urgent to refactor."""
    line_score = total_lines / 50.0
    func_score = func_count * 0.3
    god_func_score = (max_func_lines / 20.0) if max_func_lines > 50 else 0
    class_score = class_count * 2.0
    return line_score + func_score + god_func_score + class_score


# ---------------------------------------------------------------------------
# Dependency Mapping
# ---------------------------------------------------------------------------

def map_importers(analyses: List[FileAnalysis], root: Path):
    """For each analyzed file, find which other files import it."""
    module_to_file = {}
    for a in analyses:
        if a.language == "python":
            parts = Path(a.path).with_suffix("").parts
            if parts and parts[0] == "python":
                parts = parts[1:]
            module_name = ".".join(parts)
            module_to_file[module_name] = a.path

    for a in analyses:
        for imp in a.internal_imports:
            for target in analyses:
                if target.path == a.path:
                    continue
                target_parts = Path(target.path).with_suffix("").parts
                if target_parts and target_parts[0] == "python":
                    target_parts = target_parts[1:]
                target_name = ".".join(target_parts)
                if imp.module == target_name or imp.module.startswith(target_name + "."):
                    if a.path not in target.imported_by:
                        target.imported_by.append(a.path)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan_codebase(root: Path, threshold: int = 300, include_submodules: bool = False) -> List[FileAnalysis]:
    """Scan codebase and return analyses for files above threshold."""
    results = []

    for filepath in root.rglob("*.py"):
        if any(skip in filepath.parts for skip in SKIP_DIRS):
            continue
        if not include_submodules and is_submodule(str(filepath)):
            continue
        analysis = analyze_python(filepath, root)
        if analysis and analysis.total_lines >= threshold:
            results.append(analysis)

    for ext in ("*.js", "*.ts", "*.tsx"):
        for filepath in root.rglob(ext):
            if any(skip in filepath.parts for skip in SKIP_DIRS):
                continue
            if not include_submodules and is_submodule(str(filepath)):
                continue
            if filepath.stat().st_size > 500_000:
                continue
            if "min." in filepath.name or "bundle." in filepath.name:
                continue
            analysis = analyze_js(filepath, root)
            if analysis and analysis.total_lines >= threshold:
                results.append(analysis)

    map_importers(results, root)
    results.sort(key=lambda a: a.complexity_score, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_report(analyses: List[FileAnalysis], top_n: int = 30):
    """Print human-readable refactor priority report."""
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  REFACTOR SCANNER REPORT")
    print(f"{sep}")
    print(f"  Files above threshold: {len(analyses)}")

    if not analyses:
        print("  No files found above threshold.")
        print(f"\n{sep}\n")
        return

    print(f"  Top complexity score: {analyses[0].complexity_score}")
    print(f"\n  {'Rank':<5} {'Score':<7} {'Lines':<7} {'Funcs':<6} {'Cls':<5} {'MaxF':<6} {'Domain':<14} File")
    print(f"  {'-'*5} {'-'*7} {'-'*7} {'-'*6} {'-'*5} {'-'*6} {'-'*14} {'-'*40}")

    for i, a in enumerate(analyses[:top_n], 1):
        domain = classify_domain(a.path)
        print(f"  {i:<5} {a.complexity_score:<7.1f} {a.total_lines:<7} {a.function_count:<6} "
              f"{a.class_count:<5} {a.max_function_lines:<6} {domain:<14} {a.path}")

    print(f"\n{sep}")
    print(f"  TOP 5 DETAIL VIEW")
    print(f"{sep}")

    for a in analyses[:5]:
        domain = classify_domain(a.path)
        print(f"\n  [{a.path}]")
        print(f"  Domain: {domain} | Lang: {a.language} | Score: {a.complexity_score}")
        print(f"  Lines: {a.total_lines} total, {a.code_lines} code | "
              f"Funcs: {a.function_count} | Classes: {a.class_count}")

        if a.max_function_name:
            print(f"  Largest function: {a.max_function_name}() — {a.max_function_lines} lines")

        if a.classes:
            print(f"  Classes:")
            for cls in a.classes:
                print(f"    {cls.name} (L{cls.line_start}-{cls.line_end}, "
                      f"{cls.method_count} methods, bases: {', '.join(cls.bases) or 'none'})")

        if a.sections:
            print(f"  Sections:")
            for sec in a.sections[:10]:
                print(f"    [{sec.name}] L{sec.line_start}-{sec.line_end} ({sec.lines} lines)")
            if len(a.sections) > 10:
                print(f"    ... +{len(a.sections) - 10} more sections")

        if a.imported_by:
            print(f"  Imported by ({len(a.imported_by)} files):")
            for imp in a.imported_by[:5]:
                print(f"    <- {imp}")
            if len(a.imported_by) > 5:
                print(f"    ... +{len(a.imported_by) - 5} more")

        big_funcs = sorted(a.functions, key=lambda f: f.lines, reverse=True)[:5]
        if big_funcs and big_funcs[0].lines > 20:
            print(f"  Largest functions:")
            for f in big_funcs:
                if f.lines <= 20:
                    break
                prefix = f"{f.parent_class}." if f.parent_class else ""
                async_tag = "async " if f.is_async else ""
                print(f"    {async_tag}{prefix}{f.name}() — {f.lines} lines (L{f.line_start}-{f.line_end})")

    print(f"\n{sep}\n")


def write_json(analyses: List[FileAnalysis]):
    """Output as JSON."""
    print(json.dumps({
        "total_files": len(analyses),
        "files": [asdict(a) for a in analyses],
    }, indent=2, default=str))


def write_yaml(analyses: List[FileAnalysis], output_path: Path):
    """Write YAML report file."""
    lines = [
        "# VibeMind Refactor Scanner Report (auto-generated)",
        "# Re-run refactor_scanner.py to update.",
        "",
        f"total_files: {len(analyses)}",
        "",
        "files:",
    ]

    for a in analyses:
        domain = classify_domain(a.path)
        lines.append(f'  - path: "{a.path}"')
        lines.append(f'    language: "{a.language}"')
        lines.append(f'    domain: "{domain}"')
        lines.append(f"    total_lines: {a.total_lines}")
        lines.append(f"    code_lines: {a.code_lines}")
        lines.append(f"    function_count: {a.function_count}")
        lines.append(f"    class_count: {a.class_count}")
        lines.append(f"    max_function_lines: {a.max_function_lines}")
        lines.append(f'    max_function_name: "{a.max_function_name}"')
        lines.append(f"    complexity_score: {a.complexity_score}")
        lines.append(f"    is_submodule: {is_submodule(a.path)}")

        if a.classes:
            lines.append("    classes:")
            for cls in a.classes:
                lines.append(f'      - name: "{cls.name}"')
                lines.append(f"        lines: {cls.line_start}-{cls.line_end} ({cls.lines} lines)")
                lines.append(f"        methods: {cls.method_count}")
                if cls.bases:
                    lines.append(f'        bases: [{", ".join(cls.bases)}]')

        if a.sections:
            lines.append("    sections:")
            for sec in a.sections:
                lines.append(f'      - name: "{sec.name}"')
                lines.append(f"        lines: {sec.line_start}-{sec.line_end} ({sec.lines} lines)")

        if a.imported_by:
            lines.append(f"    imported_by: [{', '.join(a.imported_by[:10])}]")

        big_funcs = sorted(a.functions, key=lambda f: f.lines, reverse=True)[:5]
        if big_funcs and big_funcs[0].lines > 20:
            lines.append("    largest_functions:")
            for f in big_funcs:
                if f.lines <= 20:
                    break
                prefix = f"{f.parent_class}." if f.parent_class else ""
                lines.append(f'      - name: "{prefix}{f.name}"')
                lines.append(f"        lines: {f.line_start}-{f.line_end} ({f.lines} lines)")
                lines.append(f"        async: {f.is_async}")

        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written {len(analyses)} file analyses to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scan codebase for refactoring candidates")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--threshold", type=int, default=300,
                        help="Minimum lines to include (default: 300)")
    parser.add_argument("--top", type=int, default=30,
                        help="Show top N files in report (default: 30)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--yaml", type=str, default=None, help="Write YAML report to file")
    parser.add_argument("--include-submodules", action="store_true",
                        help="Include git submodule directories")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    analyses = scan_codebase(root, threshold=args.threshold,
                             include_submodules=args.include_submodules)

    if args.json:
        write_json(analyses)
    elif args.yaml:
        write_yaml(analyses, root / args.yaml)
    else:
        print_report(analyses, top_n=args.top)


if __name__ == "__main__":
    main()