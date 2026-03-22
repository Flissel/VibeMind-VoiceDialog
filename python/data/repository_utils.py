"""
Vibemind Repository Utilities

Shared helper functions used by all repository classes.
"""

import uuid
import unicodedata


def generate_id() -> str:
    """Generate a unique ID for new entities"""
    return str(uuid.uuid4())[:8]


def normalize_text(text: str) -> str:
    """
    Remove accents and normalize text for fuzzy matching.

    Handles speech recognition artifacts like "evaluiären" vs "evaluieren"
    by decomposing unicode and removing combining marks (accents).
    """
    # NFD: decompose ä → a + ¨ (combining diaeresis)
    text = unicodedata.normalize('NFD', text)
    # Remove combining marks (accents, umlauts decomposed parts)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.lower()


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if chars match, 1 otherwise
            curr_row.append(min(
                prev_row[j + 1] + 1,      # deletion
                curr_row[j] + 1,            # insertion
                prev_row[j] + (c1 != c2),   # substitution
            ))
        prev_row = curr_row
    return prev_row[-1]
