#!/usr/bin/env python3
"""
Scan VibeMind codebase for hardcoded German strings that should be
moved to the i18n module.

Searches for common German patterns in Python files:
- String literals containing German words (ist, und, oder, nicht, etc.)
- Hardcoded prompts with German text
- German error messages and UI strings

Usage:
    python scripts/scan_hardcoded_strings.py [--path python/]

Output: List of files and lines containing hardcoded German strings.
"""

import argparse
import os
import re
import sys

# German marker words (high-confidence indicators)
GERMAN_MARKERS = [
    r'\bist\b', r'\bund\b', r'\boder\b', r'\bnicht\b',
    r'\bfuer\b', r'\bfür\b', r'\büber\b', r'\bueber\b',
    r'\bdein[e]?\b', r'\bdas\b', r'\bder\b', r'\bdie\b', r'\bein[e]?\b',
    r'\bkann\b', r'\bwenn\b', r'\bwird\b', r'\bhat\b', r'\bmit\b',
    r'\bBubble[s]?\b', r'\bIdee[n]?\b', r'\bBereich\b', r'\bErstelle\b',
    r'\bZeig\b', r'\b[Oo]effne\b', r'\böffne\b',
    r'\bLoeschen?\b', r'\blöschen?\b', r'\bSuche\b',
    r'\bAntwort\b', r'\bErgebnis\b', r'\bAufgabe\b',
]

# Files to skip (already known / not translatable)
SKIP_PATTERNS = [
    'i18n/',           # Already in i18n module
    '__pycache__',
    '.pyc',
    'test_',           # Test files
    'migration',       # DB migrations
]

# Only scan strings (inside quotes)
STRING_PATTERN = re.compile(r'''(?:"|'|""")(.+?)(?:"|'|""")''', re.DOTALL)


def is_german_string(text: str) -> list[str]:
    """Check if a string contains German marker words. Returns matched markers."""
    matches = []
    for marker in GERMAN_MARKERS:
        if re.search(marker, text, re.IGNORECASE):
            matches.append(marker.replace(r'\b', '').replace('?', '').replace('[e]', 'e').replace('[n]', 'n').replace('[s]', 's'))
    return matches


def should_skip(filepath: str) -> bool:
    """Check if file should be skipped."""
    return any(skip in filepath for skip in SKIP_PATTERNS)


def scan_file(filepath: str) -> list[dict]:
    """Scan a single Python file for hardcoded German strings."""
    findings = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except (OSError, IOError):
        return findings

    for line_num, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue

        # Find all string literals in the line
        for match in STRING_PATTERN.finditer(line):
            text = match.group(1)
            if len(text) < 10:  # Skip short strings
                continue

            markers = is_german_string(text)
            if len(markers) >= 2:  # At least 2 German markers = likely German
                findings.append({
                    'file': filepath,
                    'line': line_num,
                    'text': text[:120] + ('...' if len(text) > 120 else ''),
                    'markers': markers[:5],
                })

    return findings


def scan_directory(root_path: str) -> list[dict]:
    """Scan all Python files in directory for hardcoded German strings."""
    all_findings = []

    for dirpath, _, filenames in os.walk(root_path):
        for filename in filenames:
            if not filename.endswith('.py'):
                continue

            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, root_path)

            if should_skip(rel_path):
                continue

            findings = scan_file(filepath)
            all_findings.extend(findings)

    return all_findings


def main():
    parser = argparse.ArgumentParser(description='Scan for hardcoded German strings')
    parser.add_argument('--path', default='python/', help='Root path to scan')
    args = parser.parse_args()

    if not os.path.isdir(args.path):
        print(f"Error: {args.path} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {args.path} for hardcoded German strings...\n")

    findings = scan_directory(args.path)

    if not findings:
        print("No hardcoded German strings found.")
        return

    # Group by file
    by_file = {}
    for f in findings:
        by_file.setdefault(f['file'], []).append(f)

    print(f"Found {len(findings)} hardcoded German strings in {len(by_file)} files:\n")

    for filepath, file_findings in sorted(by_file.items()):
        rel = os.path.relpath(filepath)
        print(f"## {rel} ({len(file_findings)} findings)")
        for finding in file_findings:
            markers_str = ', '.join(finding['markers'])
            print(f"  L{finding['line']}: \"{finding['text']}\"")
            print(f"         markers: [{markers_str}]")
        print()

    print(f"\nTotal: {len(findings)} strings across {len(by_file)} files")


if __name__ == '__main__':
    main()
