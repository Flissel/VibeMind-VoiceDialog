---
name: multi-language
description: This skill should be used when the user asks to "add a language", "translate VibeMind", "add multi-language support", "internationalize", "i18n", "localization", "l10n", "add French", "add English", "add German", "switch language", "language support", "EU languages", or mentions translating classifier prompts, Rachel prompts, or voice interface strings. Covers DE, EN, FR with EU expansion path.
---

# VibeMind Multi-Language Support

Add and manage multi-language support for VibeMind's voice interface. Currently supports **German (DE)**, **English (EN)**, and **French (FR)** as initial EU languages, with an expansion path for all standard EU countries.

## Architecture Overview

VibeMind has **5 translation layers** that must stay synchronized:

| Layer | Current Location | What Gets Translated |
|-------|-----------------|---------------------|
| Classifier Prompt | `python/swarm/orchestrator/intent_classifier.py` | Space descriptions, keywords, example utterances, disambiguation rules |
| Rachel Voice Prompt | `python/spaces/ideas/agents/rachel_agent.py` | Role, async behavior examples, personality |
| Tool Descriptions | `python/voice/session_config.py` | `send_intent` and `check_results` descriptions for OpenAI Realtime |
| Clarification Phrases | `python/swarm/user_agents/base.py` | Fallback questions when intent is unclear |
| Agent Greeting | `python/spaces/ideas/agents/rachel_agent.py` | First spoken sentence |

## Implementation Workflow

### Step 1: Create the i18n Module

Create the language module structure under `python/i18n/`:

```
python/i18n/
├── __init__.py              # get_language(), get_strings()
├── language_config.py       # Registry, detection, VIBEMIND_LANGUAGE
├── strings/{de,en,fr}.py    # UI strings per language
├── classifier_prompts/{de,en,fr}.py  # Full classifier prompts
└── rachel_prompts/{de,en,fr}.py      # Full Rachel voice prompts
```

The `__init__.py` must export:
- `get_language() -> str` -- reads `VIBEMIND_LANGUAGE` from env (default: `de`)
- `get_strings() -> dict` -- returns string dict for current language
- `get_classifier_prompt() -> str` -- returns classifier prompt for current language
- `get_rachel_prompt() -> str` -- returns Rachel prompt for current language

### Step 2: Extract Current German Strings

Move existing hardcoded German text into `python/i18n/strings/de.py`, `classifier_prompts/de.py`, and `rachel_prompts/de.py`. The current German content lives in:

- `CLASSIFIER_PROMPT_TEMPLATE` in `intent_classifier.py` (~300 lines)
- `RACHEL_VOICE_PROMPT` in `rachel_agent.py` (~50 lines)
- `SEND_INTENT_TOOL` / `CHECK_RESULTS_TOOL` descriptions in `session_config.py`
- `CLARIFICATION_PHRASES_DE` in `base.py`

### Step 3: Create EN and FR Translations

Translate each extracted module. Consult `references/translation-map.md` for pre-built translations of all event types, keywords, example utterances, and UI phrases.

Critical translation rules:
- **Event types stay English** -- `bubble.create`, `idea.list` etc. never change
- **Parameter names stay English** -- `title`, `bubble_name`, `query` etc.
- **Only natural language gets translated** -- prompts, examples, descriptions, keywords
- **Preserve classifier structure** -- section headers, formatting, numbering
- **Match disambiguation rules** per language (see `references/translation-map.md` section 6 -- Disambiguation Rules)

### Step 4: Wire Integration Points

Replace hardcoded strings with language-aware imports:

**intent_classifier.py:**
```python
from i18n import get_classifier_prompt
CLASSIFIER_PROMPT_TEMPLATE = get_classifier_prompt()
```

**rachel_agent.py:**
```python
from i18n import get_strings, get_rachel_prompt
strings = get_strings()
# Use strings["greeting"], strings["clarification"] in config
RACHEL_VOICE_PROMPT = get_rachel_prompt()
```

**session_config.py:**
```python
from i18n import get_strings
strings = get_strings()
# Use strings["send_intent_desc"], strings["check_results_desc"]
```

See `references/language-config.md` for full integration code patterns.

### Step 5: Add .env Configuration

Add to `.env.example`:
```bash
VIBEMIND_LANGUAGE=de              # de | en | fr
VIBEMIND_FALLBACK_LANGUAGE=en     # Fallback if auto-detect fails
VIBEMIND_AUTO_LANGUAGE=false      # Auto-detect from first utterance
```

### Step 6: Test Each Language

For each language (de, en, fr), verify:
1. Rachel greets in the correct language
2. Classifier recognizes utterances in that language
3. Tool descriptions are in the correct language
4. Clarification phrases match the language
5. Event types and params remain English regardless of language

Run the scanner to check for remaining hardcoded strings:
```bash
cd python && python -m scripts.scan_hardcoded_strings --path .
```

Test classification accuracy by sending 5+ utterances per language through the orchestrator and verifying correct event type mapping.

## Adding a New EU Language

To add a new language (e.g., Spanish `es`):

1. Create `python/i18n/strings/es.py` with translated string dict
2. Create `python/i18n/classifier_prompts/es.py` with translated classifier prompt
3. Create `python/i18n/rachel_prompts/es.py` with translated Rachel prompt
4. Register `es` in `python/i18n/language_config.py`
5. Add example utterances for each event type in Spanish
6. Test classifier accuracy with Spanish inputs

## Key Constraints

- **Rachel adapts to user language** -- Rachel's prompt already says "answer in the language the user speaks". The classifier prompt must match.
- **One language per session** -- Language is set at startup or detected from first utterance. Mid-session switching is not supported.
- **Classifier accuracy** -- Each language needs sufficient example utterances per event type. Minimum 2-3 examples per event for reliable classification.
- **No translation library dependency** -- All strings are static Python dicts. No runtime translation API calls.

## Additional Resources

### Reference Files
- **`references/translation-map.md`** -- Complete translation tables for all event types, keywords, utterances, and UI strings across DE/EN/FR
- **`references/language-config.md`** -- Module structure, .env config, integration code patterns, language detection strategy, and future EU expansion plan

### Scripts
- **`scripts/scan_hardcoded_strings.py`** -- Scan codebase for remaining hardcoded German strings that should be moved to i18n