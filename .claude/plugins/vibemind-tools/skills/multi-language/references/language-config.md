# Language Configuration Reference

## Supported Languages

| Code | Language | EU Standard | Locale | Rachel Voice (OpenAI) |
|------|----------|------------|--------|----------------------|
| `de` | German | DE | `de-DE` | `alloy` / `ash` |
| `en` | English | EN | `en-GB` | `alloy` / `shimmer` |
| `fr` | French | FR | `fr-FR` | `alloy` / `coral` |

## Future EU Expansion (Planned)

| Code | Language | EU Standard | Priority |
|------|----------|------------|----------|
| `es` | Spanish | ES | High |
| `it` | Italian | IT | High |
| `nl` | Dutch | NL | Medium |
| `pt` | Portuguese | PT | Medium |
| `pl` | Polish | PL | Medium |
| `sv` | Swedish | SE | Low |
| `da` | Danish | DK | Low |
| `cs` | Czech | CZ | Low |

## .env Configuration

```bash
# Language setting
VIBEMIND_LANGUAGE=de          # de | en | fr
VIBEMIND_FALLBACK_LANGUAGE=en # Fallback if detection fails

# Auto-detect from voice input (overrides VIBEMIND_LANGUAGE)
VIBEMIND_AUTO_LANGUAGE=false  # true = detect language from first utterance
```

## Language Module Structure

```
python/
├── i18n/
│   ├── __init__.py              # get_language(), get_strings()
│   ├── language_config.py       # Language registry + detection
│   ├── strings/
│   │   ├── __init__.py
│   │   ├── de.py                # German strings
│   │   ├── en.py                # English strings
│   │   └── fr.py                # French strings
│   ├── classifier_prompts/
│   │   ├── __init__.py
│   │   ├── de.py                # German classifier prompt
│   │   ├── en.py                # English classifier prompt
│   │   └── fr.py                # French classifier prompt
│   └── rachel_prompts/
│       ├── __init__.py
│       ├── de.py                # German Rachel prompt
│       ├── en.py                # English Rachel prompt
│       └── fr.py                # French Rachel prompt
```

## Language String Module Format

Each `strings/<lang>.py` file exports a dict:

```python
# python/i18n/strings/de.py
STRINGS = {
    # Rachel
    "greeting": "Hallo! Ich bin Rachel, deine VibeMind Assistentin. Was soll ich für dich tun?",
    "confirm_short": ["Mach ich!", "Ich schau mal...", "Moment..."],
    "result_success": "So, {detail}!",
    "result_error": "Hmm, das hat leider nicht geklappt — {detail}",
    "result_info": "Du hast übrigens {detail}.",
    "no_news": "Nein, noch nichts Neues. Ich sag Bescheid sobald was kommt.",
    "has_news": "Ja! {detail}",

    # Clarification
    "clarification": [
        "Kannst du das genauer erklären?",
        "Was genau meinst du damit?",
        "Ich brauche mehr Details dazu.",
    ],

    # Tool descriptions (for OpenAI Realtime)
    "send_intent_desc": (
        "Sende den Wunsch des Users an das VibeMind System zur Ausführung. "
        "Die Ausführung läuft asynchron — du erhältst das Ergebnis automatisch "
        "sobald es fertig ist. Verwende dieses Tool für ALLE Aktionen."
    ),
    "check_results_desc": (
        "Prüfe ob neue Ergebnisse von laufenden Aufgaben vorliegen. "
        "Verwende dieses Tool wenn der User fragt 'Gibt es Neuigkeiten?'"
    ),
}
```

## Integration Points

### 1. intent_classifier.py

```python
# Before (hardcoded DE):
CLASSIFIER_PROMPT_TEMPLATE = """Du bist der Intent-Klassifizierer..."""

# After (language-aware):
from i18n.classifier_prompts import get_classifier_prompt
CLASSIFIER_PROMPT_TEMPLATE = get_classifier_prompt()  # reads VIBEMIND_LANGUAGE
```

### 2. rachel_agent.py

```python
# Before (hardcoded DE):
RACHEL_VOICE_PROMPT = """Du bist Rachel..."""

# After (language-aware):
from i18n.rachel_prompts import get_rachel_prompt
from i18n import get_strings
strings = get_strings()

config = UserAgentConfig(
    greeting=strings["greeting"],
    clarification_phrases=strings["clarification"],
)
RACHEL_VOICE_PROMPT = get_rachel_prompt()
```

### 3. session_config.py

```python
# Before (hardcoded DE):
SEND_INTENT_TOOL = {"description": "Sende den Wunsch..."}

# After (language-aware):
from i18n import get_strings
strings = get_strings()

SEND_INTENT_TOOL = {
    "type": "function",
    "name": "send_intent",
    "description": strings["send_intent_desc"],
    ...
}
```

### 4. base.py (clarification phrases)

```python
# Before:
CLARIFICATION_PHRASES_DE = [...]
CLARIFICATION_PHRASES_EN = [...]

# After: keep for backward compat, but add:
from i18n import get_strings
def get_clarification_phrases():
    return get_strings()["clarification"]
```

## Language Detection Strategy

For `VIBEMIND_AUTO_LANGUAGE=true`:

1. First user utterance arrives via OpenAI Realtime transcription
2. Detect language from transcript (simple heuristic or `langdetect` library)
3. Set session language → reload classifier prompt + Rachel prompt
4. All subsequent interactions use detected language

Simple heuristic (no dependency):
```python
def detect_language(text: str) -> str:
    text_lower = text.lower()
    fr_markers = ["je", "tu", "nous", "les", "des", "est", "une", "que", "pas"]
    de_markers = ["ich", "du", "wir", "die", "der", "das", "ein", "ist", "nicht"]
    en_markers = ["the", "is", "are", "you", "my", "what", "how", "can"]

    scores = {"fr": 0, "de": 0, "en": 0}
    words = text_lower.split()
    for w in words:
        if w in fr_markers: scores["fr"] += 1
        if w in de_markers: scores["de"] += 1
        if w in en_markers: scores["en"] += 1

    return max(scores, key=scores.get) if max(scores.values()) > 0 else "en"
```