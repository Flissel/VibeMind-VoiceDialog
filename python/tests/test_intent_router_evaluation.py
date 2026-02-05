"""
VibeMind Intent Router Evaluation Suite (Natural Speech)

Comprehensive evaluation with REALISTIC, CONVERSATIONAL, AMBIGUOUS language.
- EASY (100 Tests): Single intent with natural speech patterns
- MEDIUM (100 Tests): 2-5 intents combined with noisy input
- COMPLEX (100 Tests): 15+ steps with messy voice transcriptions

10 Speech Pattern Categories:
1. Incomplete sentences
2. Filler words
3. Ambiguous requests
4. Mixed German-English
5. Informal speech
6. ASR transcription errors
7. Contextual references
8. Mumbled/unclear
9. Corrections mid-sentence
10. Regional dialects

Runs automatically without user interaction.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

sys.path.insert(0, '.')

# =============================================================================
# SPEECH PATTERN CATEGORIES
# =============================================================================

PATTERNS = [
    "incomplete",    # Unvollstaendige Saetze
    "filler",        # Fuellwoerter
    "ambiguous",     # Mehrdeutig
    "mixed_lang",    # Deutsch-Englisch Mix
    "informal",      # Informell
    "asr_error",     # ASR-Transkriptionsfehler
    "contextual",    # Kontextuelle Referenzen
    "mumbled",       # Genuschelt/Unklar
    "correction",    # Korrekturen im Satz
    "dialect",       # Regionale Dialekte
]

# =============================================================================
# EASY TESTS (100) - Single Intent with Natural Speech
# =============================================================================

EASY_TESTS = [
    # =========================================================================
    # CATEGORY 1: INCOMPLETE SENTENCES (10 tests)
    # =========================================================================
    {"id": "INC_E01", "input": "aeh die ideen... zeigen oder so", "expected": "idea.list", "pattern": "incomplete"},
    {"id": "INC_E02", "input": "kannst du mal die... na du weisst schon... spaces", "expected": "bubble.list", "pattern": "incomplete"},
    {"id": "INC_E03", "input": "mach mal eine... wie heisst das... bubble fuer marketing", "expected": "bubble.create", "pattern": "incomplete"},
    {"id": "INC_E04", "input": "ja also loesch mal das ding da", "expected": "idea.delete", "pattern": "incomplete"},
    {"id": "INC_E05", "input": "verbinde das mit dem... moment... ja mit dem anderen", "expected": "idea.connect", "pattern": "incomplete"},
    {"id": "INC_E06", "input": "geh mal in den... ach wie hiess der... marketing space", "expected": "bubble.enter", "pattern": "incomplete"},
    {"id": "INC_E07", "input": "neue idee und zwar... moment... ja genau so speichern", "expected": "idea.create", "pattern": "incomplete"},
    {"id": "INC_E08", "input": "zusammenfassung von den... also von allem", "expected": "idea.summarize", "pattern": "incomplete"},
    {"id": "INC_E09", "input": "das paper ding... whitepaper mein ich", "expected": "idea.whitepaper", "pattern": "incomplete"},
    {"id": "INC_E10", "input": "tabelle... ja formatieren als tabelle", "expected": "idea.format_table", "pattern": "incomplete"},

    # =========================================================================
    # CATEGORY 2: FILLER WORDS (10 tests)
    # =========================================================================
    {"id": "FIL_E01", "input": "aehm ja also kannst du mir mal eben die spaces zeigen", "expected": "bubble.list", "pattern": "filler"},
    {"id": "FIL_E02", "input": "hmm ja genau also so ne neue idee oder so", "expected": "idea.create", "pattern": "filler"},
    {"id": "FIL_E03", "input": "ja aeh moment mal aeh loesch das mal", "expected": "idea.delete", "pattern": "filler"},
    {"id": "FIL_E04", "input": "oookay also dann geh mal in den space marketing", "expected": "bubble.enter", "pattern": "filler"},
    {"id": "FIL_E05", "input": "ehm ja such mal nach der idee budget", "expected": "idea.find", "pattern": "filler"},
    {"id": "FIL_E06", "input": "aeh ja ne tabelle daraus machen bitte", "expected": "idea.format_table", "pattern": "filler"},
    {"id": "FIL_E07", "input": "hmm wo bin ich denn grade eigentlich", "expected": "idea.current_space", "pattern": "filler"},
    {"id": "FIL_E08", "input": "also aehm verlinke mal die ideen sinnvoll ja", "expected": "idea.auto_link", "pattern": "filler"},
    {"id": "FIL_E09", "input": "ja also so ne zusammenfassung waere gut", "expected": "idea.summarize", "pattern": "filler"},
    {"id": "FIL_E10", "input": "hmm ja genau die statistiken vom space bitte", "expected": "bubble.stats", "pattern": "filler"},

    # =========================================================================
    # CATEGORY 3: AMBIGUOUS REQUESTS (10 tests)
    # =========================================================================
    {"id": "AMB_E01", "input": "mach das weg", "expected": "idea.delete", "pattern": "ambiguous"},
    {"id": "AMB_E02", "input": "zeig mal", "expected": "idea.list", "pattern": "ambiguous"},
    {"id": "AMB_E03", "input": "geh da rein", "expected": "bubble.enter", "pattern": "ambiguous"},
    {"id": "AMB_E04", "input": "verbinde die beiden", "expected": "idea.connect", "pattern": "ambiguous"},
    {"id": "AMB_E05", "input": "das andere format", "expected": "idea.convert_format", "pattern": "ambiguous"},
    {"id": "AMB_E06", "input": "speicher das", "expected": "idea.create", "pattern": "ambiguous"},
    {"id": "AMB_E07", "input": "mach eine liste draus", "expected": "idea.format_action_list", "pattern": "ambiguous"},
    {"id": "AMB_E08", "input": "erweitern bitte", "expected": "idea.expand", "pattern": "ambiguous"},
    {"id": "AMB_E09", "input": "zusammenfassen", "expected": "idea.summarize", "pattern": "ambiguous"},
    {"id": "AMB_E10", "input": "stats", "expected": "bubble.stats", "pattern": "ambiguous"},

    # =========================================================================
    # CATEGORY 4: MIXED GERMAN-ENGLISH (10 tests)
    # =========================================================================
    {"id": "MIX_E01", "input": "delete das mal bitte", "expected": "idea.delete", "pattern": "mixed_lang"},
    {"id": "MIX_E02", "input": "zeig mir die spaces please", "expected": "bubble.list", "pattern": "mixed_lang"},
    {"id": "MIX_E03", "input": "create ne neue idee", "expected": "idea.create", "pattern": "mixed_lang"},
    {"id": "MIX_E04", "input": "link die ideas zusammen", "expected": "idea.auto_link", "pattern": "mixed_lang"},
    {"id": "MIX_E05", "input": "enter den marketing space", "expected": "bubble.enter", "pattern": "mixed_lang"},
    {"id": "MIX_E06", "input": "summary erstellen bitte", "expected": "idea.summarize", "pattern": "mixed_lang"},
    {"id": "MIX_E07", "input": "format das als table", "expected": "idea.format_table", "pattern": "mixed_lang"},
    {"id": "MIX_E08", "input": "mach ein whitepaper daraus please", "expected": "idea.whitepaper", "pattern": "mixed_lang"},
    {"id": "MIX_E09", "input": "find die idee about marketing", "expected": "idea.find", "pattern": "mixed_lang"},
    {"id": "MIX_E10", "input": "update das content von der idee", "expected": "idea.update", "pattern": "mixed_lang"},

    # =========================================================================
    # CATEGORY 5: INFORMAL SPEECH (10 tests)
    # =========================================================================
    {"id": "INF_E01", "input": "zeig mal schnell", "expected": "idea.list", "pattern": "informal"},
    {"id": "INF_E02", "input": "mach weg", "expected": "idea.delete", "pattern": "informal"},
    {"id": "INF_E03", "input": "neue idee reinhauen", "expected": "idea.create", "pattern": "informal"},
    {"id": "INF_E04", "input": "geh rein da", "expected": "bubble.enter", "pattern": "informal"},
    {"id": "INF_E05", "input": "alles zusammenpacken", "expected": "idea.summarize", "pattern": "informal"},
    {"id": "INF_E06", "input": "wo isses", "expected": "idea.find", "pattern": "informal"},
    {"id": "INF_E07", "input": "verbinden tun", "expected": "idea.connect", "pattern": "informal"},
    {"id": "INF_E08", "input": "schnell mal checken", "expected": "bubble.stats", "pattern": "informal"},
    {"id": "INF_E09", "input": "aufhuebschen als tabelle", "expected": "idea.format_table", "pattern": "informal"},
    {"id": "INF_E10", "input": "neuer space anlegen", "expected": "bubble.create", "pattern": "informal"},

    # =========================================================================
    # CATEGORY 6: ASR TRANSCRIPTION ERRORS (10 tests)
    # =========================================================================
    {"id": "ASR_E01", "input": "zeig mir meine idden", "expected": "idea.list", "pattern": "asr_error"},
    {"id": "ASR_E02", "input": "erstele einen neuen speiss", "expected": "bubble.create", "pattern": "asr_error"},
    {"id": "ASR_E03", "input": "gehe in den marketink space", "expected": "bubble.enter", "pattern": "asr_error"},
    {"id": "ASR_E04", "input": "losche die idee", "expected": "idea.delete", "pattern": "asr_error"},
    {"id": "ASR_E05", "input": "verbine die ideen", "expected": "idea.auto_link", "pattern": "asr_error"},
    {"id": "ASR_E06", "input": "zusammnfassung erstellen", "expected": "idea.summarize", "pattern": "asr_error"},
    {"id": "ASR_E07", "input": "formatiren als tabele", "expected": "idea.format_table", "pattern": "asr_error"},
    {"id": "ASR_E08", "input": "weisspapier generiren", "expected": "idea.whitepaper", "pattern": "asr_error"},
    {"id": "ASR_E09", "input": "statistik vom speiss zeigen", "expected": "bubble.stats", "pattern": "asr_error"},
    {"id": "ASR_E10", "input": "aektualisiere die ide", "expected": "idea.update", "pattern": "asr_error"},

    # =========================================================================
    # CATEGORY 7: CONTEXTUAL REFERENCES (10 tests)
    # =========================================================================
    {"id": "CTX_E01", "input": "das da loeschen", "expected": "idea.delete", "pattern": "contextual"},
    {"id": "CTX_E02", "input": "die sache von vorhin zeigen", "expected": "idea.find", "pattern": "contextual"},
    {"id": "CTX_E03", "input": "das letzte nochmal anzeigen", "expected": "idea.list", "pattern": "contextual"},
    {"id": "CTX_E04", "input": "genau das verbinden", "expected": "idea.connect", "pattern": "contextual"},
    {"id": "CTX_E05", "input": "so wie vorher machen tabelle", "expected": "idea.format_table", "pattern": "contextual"},
    {"id": "CTX_E06", "input": "das gleiche fuer den anderen space", "expected": "bubble.enter", "pattern": "contextual"},
    {"id": "CTX_E07", "input": "wieder dahin zurueck", "expected": "bubble.list", "pattern": "contextual"},
    {"id": "CTX_E08", "input": "das ganze drumherum erweitern", "expected": "idea.expand", "pattern": "contextual"},
    {"id": "CTX_E09", "input": "die anderen auch verlinken", "expected": "idea.auto_link", "pattern": "contextual"},
    {"id": "CTX_E10", "input": "davon ne zusammenfassung", "expected": "idea.summarize", "pattern": "contextual"},

    # =========================================================================
    # CATEGORY 8: MUMBLED/UNCLEAR (10 tests)
    # =========================================================================
    {"id": "MUM_E01", "input": "nee andersrum... die ideen zeigen", "expected": "idea.list", "pattern": "mumbled"},
    {"id": "MUM_E02", "input": "warte mal... doch die spaces", "expected": "bubble.list", "pattern": "mumbled"},
    {"id": "MUM_E03", "input": "ach nee... moment... ja genau loeschen", "expected": "idea.delete", "pattern": "mumbled"},
    {"id": "MUM_E04", "input": "hm wie heisst das nochmal... verbinden halt", "expected": "idea.connect", "pattern": "mumbled"},
    {"id": "MUM_E05", "input": "das dings da... weisste... anzeigen ideen", "expected": "idea.list", "pattern": "mumbled"},
    {"id": "MUM_E06", "input": "irgendwie... formatieren als tabelle oder so", "expected": "idea.format_table", "pattern": "mumbled"},
    {"id": "MUM_E07", "input": "wie sagt man... erweitern glaub ich", "expected": "idea.expand", "pattern": "mumbled"},
    {"id": "MUM_E08", "input": "na du weisst schon... das paper ding", "expected": "idea.whitepaper", "pattern": "mumbled"},
    {"id": "MUM_E09", "input": "achso ja genau... in den space gehen", "expected": "bubble.enter", "pattern": "mumbled"},
    {"id": "MUM_E10", "input": "dings... aeh... zusammenfassung machen", "expected": "idea.summarize", "pattern": "mumbled"},

    # =========================================================================
    # CATEGORY 9: CORRECTIONS MID-SENTENCE (10 tests)
    # =========================================================================
    {"id": "COR_E01", "input": "erstelle... nein warte loesche den space", "expected": "bubble.delete", "pattern": "correction"},
    {"id": "COR_E02", "input": "zeig die ideen... ach nee die spaces", "expected": "bubble.list", "pattern": "correction"},
    {"id": "COR_E03", "input": "geh in marketing... quatsch in projekte", "expected": "bubble.enter", "pattern": "correction"},
    {"id": "COR_E04", "input": "loesch... stopp... aktualisiere die idee", "expected": "idea.update", "pattern": "correction"},
    {"id": "COR_E05", "input": "verbinde a mit b... halt nee verlinke alles", "expected": "idea.auto_link", "pattern": "correction"},
    {"id": "COR_E06", "input": "als tabelle... moment als aufgabenliste", "expected": "idea.format_action_list", "pattern": "correction"},
    {"id": "COR_E07", "input": "zusammenfassung... ach whitepaper mein ich", "expected": "idea.whitepaper", "pattern": "correction"},
    {"id": "COR_E08", "input": "erweitern... nee analysieren verbindungen", "expected": "idea.analyze_links", "pattern": "correction"},
    {"id": "COR_E09", "input": "neue idee... stopp suchen mein ich", "expected": "idea.find", "pattern": "correction"},
    {"id": "COR_E10", "input": "space erstellen... warte umbenennen", "expected": "bubble.update", "pattern": "correction"},

    # =========================================================================
    # CATEGORY 10: REGIONAL DIALECTS (10 tests)
    # =========================================================================
    {"id": "DIA_E01", "input": "schaug amoi de ideen an", "expected": "idea.list", "pattern": "dialect"},
    {"id": "DIA_E02", "input": "mach dat weg", "expected": "idea.delete", "pattern": "dialect"},
    {"id": "DIA_E03", "input": "geh ma do nei in den space", "expected": "bubble.enter", "pattern": "dialect"},
    {"id": "DIA_E04", "input": "zeig amoi de spaces", "expected": "bubble.list", "pattern": "dialect"},
    {"id": "DIA_E05", "input": "dat verbinden tun", "expected": "idea.connect", "pattern": "dialect"},
    {"id": "DIA_E06", "input": "mach a neie idee", "expected": "idea.create", "pattern": "dialect"},
    {"id": "DIA_E07", "input": "lueg mal die sache an", "expected": "idea.list", "pattern": "dialect"},
    {"id": "DIA_E08", "input": "des zamfassn bitte", "expected": "idea.summarize", "pattern": "dialect"},
    {"id": "DIA_E09", "input": "loeschens bittschoen die idee", "expected": "idea.delete", "pattern": "dialect"},
    {"id": "DIA_E10", "input": "des paper dings macha", "expected": "idea.whitepaper", "pattern": "dialect"},
]

# =============================================================================
# MEDIUM TESTS (100) - 2-5 Intents with Natural Speech
# =============================================================================

MEDIUM_TESTS = [
    # =========================================================================
    # PATTERN A: NAVIGATE + QUERY (20 tests)
    # =========================================================================
    {"id": "MED_A01", "input": "geh erstmal in den space und dann... ja zeig mal alles",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "incomplete"},
    {"id": "MED_A02", "input": "also aehm reingehn in marketing und zeigen was da is",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "filler"},
    {"id": "MED_A03", "input": "rein da und alles anzeigen",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "ambiguous"},
    {"id": "MED_A04", "input": "enter space projekte and show ideas",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "mixed_lang"},
    {"id": "MED_A05", "input": "reinspringen und alles angucken",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "informal"},
    {"id": "MED_A06", "input": "gehe in den speiss und zeig die idden",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "asr_error"},
    {"id": "MED_A07", "input": "da wieder rein und das zeigen",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "contextual"},
    {"id": "MED_A08", "input": "warte... also erstmal reingehn dann zeigen",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "mumbled"},
    {"id": "MED_A09", "input": "zeig ideen... nee erst in space gehen dann zeigen",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "correction"},
    {"id": "MED_A10", "input": "geh ma do nei und schaug wos drin is",
     "expected_steps": ["bubble.enter", "idea.list"], "pattern": "dialect"},
    {"id": "MED_A11", "input": "spaces zeigen und dann in marketing gehen",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "incomplete"},
    {"id": "MED_A12", "input": "aehm also liste mal spaces und geh dann rein",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "filler"},
    {"id": "MED_A13", "input": "uebersicht und dann da rein",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "ambiguous"},
    {"id": "MED_A14", "input": "show spaces und dann enter marketing",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "mixed_lang"},
    {"id": "MED_A15", "input": "mal gucken was da is und dann rein",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "informal"},
    {"id": "MED_A16", "input": "zeig speisses und geh in marketink",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "asr_error"},
    {"id": "MED_A17", "input": "das von vorhin zeigen und dann dahin",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "contextual"},
    {"id": "MED_A18", "input": "moment... also spaces und dann... ja reingehn",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "mumbled"},
    {"id": "MED_A19", "input": "ideen... nee spaces zeigen dann reingehn",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "correction"},
    {"id": "MED_A20", "input": "schaug amoi de spaces und geh do nei",
     "expected_steps": ["bubble.list", "bubble.enter"], "pattern": "dialect"},

    # =========================================================================
    # PATTERN B: CREATE + MODIFY (20 tests)
    # =========================================================================
    {"id": "MED_B01", "input": "mach mal nen space... und dann ideen rein",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "incomplete"},
    {"id": "MED_B02", "input": "ja also erstell space marketing und fueg idee roadmap hinzu",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "filler"},
    {"id": "MED_B03", "input": "neuer bereich und was reinpacken",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "ambiguous"},
    {"id": "MED_B04", "input": "create space projekte und add idee features",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "mixed_lang"},
    {"id": "MED_B05", "input": "schnell space anlegen und idee reinhauen",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "informal"},
    {"id": "MED_B06", "input": "erstele speiss und fuge ideen hinsu",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "asr_error"},
    {"id": "MED_B07", "input": "so wie vorher neuen machen und das gleiche rein",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "contextual"},
    {"id": "MED_B08", "input": "dings... neuer space... und dann... ja idee dazu",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "mumbled"},
    {"id": "MED_B09", "input": "idee... nee erst space erstellen dann idee",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "correction"},
    {"id": "MED_B10", "input": "mach dat space und pack da wat rein",
     "expected_steps": ["bubble.create", "idea.create"], "pattern": "dialect"},
    {"id": "MED_B11", "input": "neue idee erstellen und als tabelle formatieren",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "incomplete"},
    {"id": "MED_B12", "input": "aehm ja mach ne idee und dann als liste",
     "expected_steps": ["idea.create", "idea.format_action_list"], "pattern": "filler"},
    {"id": "MED_B13", "input": "das speichern und formatieren",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "ambiguous"},
    {"id": "MED_B14", "input": "create idea und format als table please",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "mixed_lang"},
    {"id": "MED_B15", "input": "idee reinhauen und huebsch machen",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "informal"},
    {"id": "MED_B16", "input": "erstele ide und formatir als tabele",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "asr_error"},
    {"id": "MED_B17", "input": "so wie das andere erstellen und gleich formatieren",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "contextual"},
    {"id": "MED_B18", "input": "also... neue idee... dann... ja tabelle draus",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "mumbled"},
    {"id": "MED_B19", "input": "formatieren... nee erst erstellen dann format",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "correction"},
    {"id": "MED_B20", "input": "mach a neie idee und des als tabelle",
     "expected_steps": ["idea.create", "idea.format_table"], "pattern": "dialect"},

    # =========================================================================
    # PATTERN C: QUERY + DELETE (20 tests)
    # =========================================================================
    {"id": "MED_C01", "input": "zeig alles und mach das dann weg",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "ambiguous"},
    {"id": "MED_C02", "input": "liste ideen auf und loesch die ueber budget",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "incomplete"},
    {"id": "MED_C03", "input": "aehm zeig mal und dann das alte weg",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "filler"},
    {"id": "MED_C04", "input": "show ideas and delete the marketing one",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "mixed_lang"},
    {"id": "MED_C05", "input": "gucken was da is und muell raus",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "informal"},
    {"id": "MED_C06", "input": "zeig idden und losch die alte",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "asr_error"},
    {"id": "MED_C07", "input": "das zeigen und dann das loeschen",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "contextual"},
    {"id": "MED_C08", "input": "warte... zeigen erstmal... dann weg damit",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "mumbled"},
    {"id": "MED_C09", "input": "loeschen... nee erst zeigen dann loeschen",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "correction"},
    {"id": "MED_C10", "input": "schaug amoi und mach des dann weg",
     "expected_steps": ["idea.list", "idea.delete"], "pattern": "dialect"},
    {"id": "MED_C11", "input": "such nach budget und loesch das",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "incomplete"},
    {"id": "MED_C12", "input": "hmm find die alte idee und weg damit",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "filler"},
    {"id": "MED_C13", "input": "finden und entfernen",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "ambiguous"},
    {"id": "MED_C14", "input": "find idea marketing and delete it please",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "mixed_lang"},
    {"id": "MED_C15", "input": "raussuchen und wegmachen",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "informal"},
    {"id": "MED_C16", "input": "finde ide und losche die",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "asr_error"},
    {"id": "MED_C17", "input": "das von vorhin suchen und loeschen",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "contextual"},
    {"id": "MED_C18", "input": "also... suchen... und dann weg",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "mumbled"},
    {"id": "MED_C19", "input": "loeschen... stopp erst suchen budget dann loeschen",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "correction"},
    {"id": "MED_C20", "input": "such des und mach weg",
     "expected_steps": ["idea.find", "idea.delete"], "pattern": "dialect"},

    # =========================================================================
    # PATTERN D: GENERATE + FORMAT (20 tests)
    # =========================================================================
    {"id": "MED_D01", "input": "verlink alles und dann zusammenfassung",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "incomplete"},
    {"id": "MED_D02", "input": "aehm ja verlinken und dann ne summary",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "filler"},
    {"id": "MED_D03", "input": "zusammenhaengen und das wichtigste zeigen",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "ambiguous"},
    {"id": "MED_D04", "input": "auto-link und create summary bitte",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "mixed_lang"},
    {"id": "MED_D05", "input": "alles zusammenkleben und ueberblick",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "informal"},
    {"id": "MED_D06", "input": "ferlinke und zamfassung erstelen",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "asr_error"},
    {"id": "MED_D07", "input": "so wie beim letzten mal verlinken und zusammenfassen",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "contextual"},
    {"id": "MED_D08", "input": "also... verlinken... und dann... ja zusammenfassen",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "mumbled"},
    {"id": "MED_D09", "input": "summary... nee erst verlinken dann summary",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "correction"},
    {"id": "MED_D10", "input": "verbind des zam und mach zamfassung",
     "expected_steps": ["idea.auto_link", "idea.summarize"], "pattern": "dialect"},
    {"id": "MED_D11", "input": "zusammenfassung und dann whitepaper",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "incomplete"},
    {"id": "MED_D12", "input": "ja also fass zusammen und mach paper draus",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "filler"},
    {"id": "MED_D13", "input": "ueberblick und dann dokument erstellen",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "ambiguous"},
    {"id": "MED_D14", "input": "summarize und generate whitepaper please",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "mixed_lang"},
    {"id": "MED_D15", "input": "kurz zusammenfassen und paper raushauen",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "informal"},
    {"id": "MED_D16", "input": "zamfassung und dann weisspapier",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "asr_error"},
    {"id": "MED_D17", "input": "das gleiche wie vorhin zusammenfassen und paper machen",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "contextual"},
    {"id": "MED_D18", "input": "dings... zusammenfassen... und paper",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "mumbled"},
    {"id": "MED_D19", "input": "whitepaper... ach erst summary dann paper",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "correction"},
    {"id": "MED_D20", "input": "zamfassn und des paper dings macha",
     "expected_steps": ["idea.summarize", "idea.whitepaper"], "pattern": "dialect"},

    # =========================================================================
    # PATTERN E: MIXED OPERATIONS (20 tests)
    # =========================================================================
    {"id": "MED_E01", "input": "analysier verbindungen und verlink dann",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "incomplete"},
    {"id": "MED_E02", "input": "aeh ja schau welche zusammengehoeren und verbinde die",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "filler"},
    {"id": "MED_E03", "input": "pruefen und dann zusammenfuehren",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "ambiguous"},
    {"id": "MED_E04", "input": "analyze links und auto-link dann",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "mixed_lang"},
    {"id": "MED_E05", "input": "mal checken und dann verknuepfen",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "informal"},
    {"id": "MED_E06", "input": "analysir verlinkungen und verbine dann",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "asr_error"},
    {"id": "MED_E07", "input": "das pruefen und das verbinden",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "contextual"},
    {"id": "MED_E08", "input": "also... pruefen erstmal... dann verlinken",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "mumbled"},
    {"id": "MED_E09", "input": "verlinken... nee erst analysieren dann verlinken",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "correction"},
    {"id": "MED_E10", "input": "schaug wos zsamgehoert und verbind des",
     "expected_steps": ["idea.analyze_links", "idea.auto_link"], "pattern": "dialect"},
    {"id": "MED_E11", "input": "erweitere idee und verlinke mit original",
     "expected_steps": ["idea.expand", "idea.connect"], "pattern": "incomplete"},
    {"id": "MED_E12", "input": "hmm ja mehr ideen generieren und zusammenbinden",
     "expected_steps": ["idea.expand", "idea.auto_link"], "pattern": "filler"},
    {"id": "MED_E13", "input": "mehr davon und verbinden",
     "expected_steps": ["idea.expand", "idea.auto_link"], "pattern": "ambiguous"},
    {"id": "MED_E14", "input": "expand ideas und dann connect bitte",
     "expected_steps": ["idea.expand", "idea.connect"], "pattern": "mixed_lang"},
    {"id": "MED_E15", "input": "mehr draus machen und zusammenhaengen",
     "expected_steps": ["idea.expand", "idea.auto_link"], "pattern": "informal"},
    {"id": "MED_E16", "input": "erwitere und verbine dann",
     "expected_steps": ["idea.expand", "idea.connect"], "pattern": "asr_error"},
    {"id": "MED_E17", "input": "das erweitern und das verbinden",
     "expected_steps": ["idea.expand", "idea.connect"], "pattern": "contextual"},
    {"id": "MED_E18", "input": "also mehr... und dann... verbinden",
     "expected_steps": ["idea.expand", "idea.connect"], "pattern": "mumbled"},
    {"id": "MED_E19", "input": "verbinden... nee erst erweitern dann verbinden",
     "expected_steps": ["idea.expand", "idea.connect"], "pattern": "correction"},
    {"id": "MED_E20", "input": "mach mehr draus und verbind des",
     "expected_steps": ["idea.expand", "idea.connect"], "pattern": "dialect"},
]

# =============================================================================
# COMPLEX TESTS (100) - 15+ Steps with Natural Speech
# =============================================================================

COMPLEX_TESTS = [
    # =========================================================================
    # TYPE 1: PROJECT SETUP WORKFLOWS (20 tests)
    # =========================================================================
    {"id": "CPX_1_01",
     "input": "also mach mal nen space fuer das projekt... dann pack da rein... na halt die ganzen sachen... features und so... roadmap... budget... achja und das team auch... dann verlink das alles... und mach ne zusammenfassung... und am ende noch son whitepaper dings",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 8, "pattern": "incomplete"},
    {"id": "CPX_1_02",
     "input": "aehm ja also erstell space produktentwicklung geh rein mach ideen features roadmap timeline budget team risiken verlink alles zusammenfassung whitepaper bitte",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 10, "pattern": "filler"},
    {"id": "CPX_1_03",
     "input": "neues projekt anlegen da rein alles wichtige speichern verbinden ueberblick und dann paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 6, "pattern": "ambiguous"},
    {"id": "CPX_1_04",
     "input": "create space startup dann enter und add ideas vision mission werte zielgruppe problem loesung usp markt dann auto-link und make whitepaper please",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 10, "pattern": "mixed_lang"},
    {"id": "CPX_1_05",
     "input": "okay mach mal so nen space fuer das projekt da dann hau da rein was wir brauchen also features und so roadmap budget team risiken marktanalyse dann alles zusammenkleben und ne zusammenfassung drueber und zum schluss son paper draus machen",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 10, "pattern": "informal"},
    {"id": "CPX_1_06",
     "input": "erstele speiss projektentwiklung gehe hinein erstele idden features roatmap timelein budjet teem risiken verlinke alles automatich erstelle zusammnfasung und whitepapier",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 10, "pattern": "asr_error"},
    {"id": "CPX_1_07",
     "input": "mach das gleiche wie beim letzten projekt da mit den ganzen sachen also das uebliche und am ende das paper ding und vorher noch die verlinkung wie immer",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "contextual"},
    {"id": "CPX_1_08",
     "input": "also das projekt dings machen... warte wie hiess das... ja space... dann da rein und die sachen... du weisst schon features und so das ganze zeug... dann verknuepfen... und am ende noch das paper teil",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "mumbled"},
    {"id": "CPX_1_09",
     "input": "mach space... warte erstmal ideen zeigen... nee doch space machen dann da rein dann die ideen features roadmap team budget... dann verlinken... und whitepaper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 7, "pattern": "correction"},
    {"id": "CPX_1_10",
     "input": "mach amoi an space fuers projekt geh do nei pack de sachen rein weisst scho features roadmap budget team des verlink zam und am end a paper draus",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 7, "pattern": "dialect"},
    {"id": "CPX_1_11",
     "input": "space sprint-42 erstellen hineingehen user stories erstellen login dashboard profile settings notifications search alle als aufgabenliste formatieren verlinken analysieren zusammenfassung whitepaper als sprint-dokumentation",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.format_action_list", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 12, "pattern": "incomplete"},
    {"id": "CPX_1_12",
     "input": "aehm ja space api-design machen und dann geh rein und erstell ideen fuer endpoints authentication errors validation responses und formatier die alle als specs und verlink das zeug und mach whitepaper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 9, "pattern": "filler"},
    {"id": "CPX_1_13",
     "input": "api dokumentation anlegen alles rein endpoints auth errors formatieren verbinden zusammenfassen paper erstellen",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.format_specs", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 8, "pattern": "ambiguous"},
    {"id": "CPX_1_14",
     "input": "create space documentation enter add ideas introduction basics advanced reference faq format as hierarchy link everything generate whitepaper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.format_hierarchy", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 9, "pattern": "mixed_lang"},
    {"id": "CPX_1_15",
     "input": "schnell space anlegen fuer knowledge base reinspringen ideen reinhauen einfuehrung grundlagen fortgeschritten referenz glossar alles verknuepfen und paper raushauen",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.create", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 8, "pattern": "informal"},
    {"id": "CPX_1_16",
     "input": "erstele speiss dokumentaion gehe rein mache idden einfurung grundlage fortgeshritten referens formatir als hierachie verlinke mache whitepapir",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.create", "idea.format_hierarchy", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 8, "pattern": "asr_error"},
    {"id": "CPX_1_17",
     "input": "so wie beim letzten mal docs aufsetzen da rein die ueblichen sachen grundlagen und so formatieren wie immer verlinken und das paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.format_hierarchy", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 7, "pattern": "contextual"},
    {"id": "CPX_1_18",
     "input": "also... space fuer docs... warte... ja reingehn... dann sachen... du weisst schon... einfuehrung und so... formatieren... verlinken... paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.format_hierarchy", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "mumbled"},
    {"id": "CPX_1_19",
     "input": "whitepaper... nee erstmal space erstellen docs dann reingehn ideen rein grundlagen referenz dann formatieren verlinken dann erst paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.format_hierarchy", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "correction"},
    {"id": "CPX_1_20",
     "input": "mach an space fuer de doku geh nei pack de sachen rein einfuehrung grundlagen referenz des als hierarchie und dann verlink und des paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.create", "idea.create", "idea.format_hierarchy", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 7, "pattern": "dialect"},

    # =========================================================================
    # TYPE 2: IDEA ORGANIZATION WORKFLOWS (20 tests)
    # =========================================================================
    {"id": "CPX_2_01",
     "input": "geh in den space... zeig was da is... format alles als tabelle... verlink... analysier... zusammenfassung... und paper",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "incomplete"},
    {"id": "CPX_2_02",
     "input": "aehm ja also geh in marketing zeig ideen formatier als tabellen verlink alles automatisch analysier verbindungen mach zusammenfassung und whitepaper",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "filler"},
    {"id": "CPX_2_03",
     "input": "reingehn alles anzeigen strukturieren verbinden pruefen zusammenfassen dokument erstellen",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "ambiguous"},
    {"id": "CPX_2_04",
     "input": "enter marketing space list ideas format all as tables auto-link analyze connections create summary and whitepaper",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "mixed_lang"},
    {"id": "CPX_2_05",
     "input": "reinspringen alles angucken aufhuebschen als tabellen zusammenkleben checken zusammenfassen paper raushauen",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "informal"},
    {"id": "CPX_2_06",
     "input": "gehe in speiss zeig idden formatir als tabelen verlinke automatich analysir zusammnfasung und whitepapir",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "asr_error"},
    {"id": "CPX_2_07",
     "input": "da wieder rein das anzeigen so formatieren wie letztens verlinken pruefen zusammenfassen und das paper",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "contextual"},
    {"id": "CPX_2_08",
     "input": "also... reingehn... zeigen... dann formatieren... verlinken... analysieren... zusammenfassen... paper",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "mumbled"},
    {"id": "CPX_2_09",
     "input": "paper... nee erst reingehn zeigen formatieren verlinken analysieren zusammenfassen dann paper",
     "expected_steps": ["bubble.enter", "idea.list", "idea.format_table", "idea.auto_link", "idea.analyze_links", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "correction"},
    {"id": "CPX_2_10",
     "input": "geh amoi do nei und schaug wos drin is dann des zam verlinken und zamfassn und am end a paper draus",
     "expected_steps": ["bubble.enter", "idea.list", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 5, "pattern": "dialect"},
    {"id": "CPX_2_11",
     "input": "liste ideen... erste als tabelle... zweite als aufgabenliste... dritte als pro contra... dann verlinken... whitepaper",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.format_pros_cons", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "incomplete"},
    {"id": "CPX_2_12",
     "input": "hmm also zeig mal ideen formatier erste als tabelle zweite als tasks dritte als pro contra verlink und paper",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.format_pros_cons", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "filler"},
    {"id": "CPX_2_13",
     "input": "alles zeigen verschieden formatieren verbinden dokument",
     "expected_steps": ["idea.list", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 4, "pattern": "ambiguous"},
    {"id": "CPX_2_14",
     "input": "list ideas format first as table second as action list third as pros cons auto-link create whitepaper",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.format_pros_cons", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "mixed_lang"},
    {"id": "CPX_2_15",
     "input": "alles angucken erste aufhuebschen als tabelle zweite als tasks dritte pro contra zusammenkleben paper machen",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.format_pros_cons", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "informal"},
    {"id": "CPX_2_16",
     "input": "zeig idden formatir erste als tabele zweite als aufgaben dritte als pros contras verlink whitepapir",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.format_pros_cons", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "asr_error"},
    {"id": "CPX_2_17",
     "input": "das zeigen so formatieren wie letztens die eine als tabelle die andere als liste verlinken und paper",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "contextual"},
    {"id": "CPX_2_18",
     "input": "also... zeigen... erste formatieren... zweite... dritte... dann verlinken... paper",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.format_pros_cons", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "mumbled"},
    {"id": "CPX_2_19",
     "input": "paper... nee erst zeigen dann formatieren tabelle liste pro contra dann verlinken dann paper",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.format_pros_cons", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "correction"},
    {"id": "CPX_2_20",
     "input": "schaug des an formatir de erste als tabelle de zweite als aufgaben verlink und mach paper",
     "expected_steps": ["idea.list", "idea.format_table", "idea.format_action_list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "dialect"},

    # =========================================================================
    # TYPE 3: FORMATTING & EXPORT WORKFLOWS (20 tests)
    # =========================================================================
    {"id": "CPX_3_01",
     "input": "formatier alles als tabellen... dann einige als listen... andere als specs... verlink... whitepaper",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "incomplete"},
    {"id": "CPX_3_02",
     "input": "aehm ja also formatier ideen als tabelle dann manche als aufgabenliste andere als specs verlink und mach whitepaper",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "filler"},
    {"id": "CPX_3_03",
     "input": "strukturieren verschiedene formate verbinden exportieren als dokument",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 4, "pattern": "ambiguous"},
    {"id": "CPX_3_04",
     "input": "format ideas as table some as action list others as specs auto-link create whitepaper please",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "mixed_lang"},
    {"id": "CPX_3_05",
     "input": "alles aufhuebschen manche als tabellen manche als tasks manche als specs zusammenkleben und paper raus",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "informal"},
    {"id": "CPX_3_06",
     "input": "formatiren alles als tabelen manche als aufgabelisten andere als specks verlinke whitepapir",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "asr_error"},
    {"id": "CPX_3_07",
     "input": "so wie vorher formatieren die einen als tabelle die anderen als liste verlinken und paper",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 4, "pattern": "contextual"},
    {"id": "CPX_3_08",
     "input": "also formatieren... tabelle... liste... specs... verlinken... paper",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "mumbled"},
    {"id": "CPX_3_09",
     "input": "paper... nee erst formatieren tabelle liste specs dann verlinken dann paper",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "correction"},
    {"id": "CPX_3_10",
     "input": "formatir des als tabelle des als aufgaben des als specs verlink und mach paper",
     "expected_steps": ["idea.format_table", "idea.format_action_list", "idea.format_specs", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "dialect"},
    {"id": "CPX_3_11",
     "input": "konvertier alles zu tabellen... dann zurueck zu notizen... dann wieder zu tabellen... verlink... paper",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "incomplete"},
    {"id": "CPX_3_12",
     "input": "ja also konvertier zu tabellen dann zu notizen dann wieder tabellen verlink mach paper",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "filler"},
    {"id": "CPX_3_13",
     "input": "format umwandeln hin und her dann verbinden exportieren",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 4, "pattern": "ambiguous"},
    {"id": "CPX_3_14",
     "input": "convert to tables dann to notes dann tables again auto-link whitepaper",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "mixed_lang"},
    {"id": "CPX_3_15",
     "input": "umwandeln zu tabellen dann notizen dann wieder tabellen zusammenkleben paper",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "informal"},
    {"id": "CPX_3_16",
     "input": "konvertir zu tabelen dann zu notisen dann wieder tabelen verlink whitepapir",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "asr_error"},
    {"id": "CPX_3_17",
     "input": "so wie vorher umwandeln hin und her dann verlinken und paper",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 4, "pattern": "contextual"},
    {"id": "CPX_3_18",
     "input": "konvertieren... tabellen... notizen... wieder tabellen... verlinken... paper",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "mumbled"},
    {"id": "CPX_3_19",
     "input": "paper... nee erst konvertieren tabellen notizen tabellen verlinken dann paper",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "correction"},
    {"id": "CPX_3_20",
     "input": "wandel zu tabellen um dann zu notizen dann wieder tabellen verlink und mach paper",
     "expected_steps": ["idea.convert_format", "idea.format_note", "idea.format_table", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 5, "pattern": "dialect"},

    # =========================================================================
    # TYPE 4: MULTI-SPACE OPERATIONS (20 tests)
    # =========================================================================
    {"id": "CPX_4_01",
     "input": "mach spaces q1 q2 q3 q4... geh in jeden... pack ideen rein... verlink... summary... dann gesamt paper",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "incomplete"},
    {"id": "CPX_4_02",
     "input": "aehm ja erstell spaces q1 q2 q3 q4 geh in jeden fueg ideen hinzu verlink mach zusammenfassung und am ende gesamt whitepaper",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "filler"},
    {"id": "CPX_4_03",
     "input": "mehrere bereiche anlegen in jeden rein sachen speichern verbinden zusammenfassen gesamt dokument",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 7, "pattern": "ambiguous"},
    {"id": "CPX_4_04",
     "input": "create spaces q1 q2 q3 q4 enter each add ideas auto-link summarize then overall whitepaper",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "mixed_lang"},
    {"id": "CPX_4_05",
     "input": "schnell vier spaces anlegen q1 bis q4 reinspringen ideen reinhauen verknuepfen zusammenfassen paper raus",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "informal"},
    {"id": "CPX_4_06",
     "input": "erstele speisses q1 q2 q3 q4 gehe in jeden fuge idden hinsu verlinke zamfasung und whitepapir",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "asr_error"},
    {"id": "CPX_4_07",
     "input": "so wie beim letzten mal vier bereiche anlegen ueberall das gleiche rein verlinken zusammenfassen paper",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "contextual"},
    {"id": "CPX_4_08",
     "input": "spaces machen... vier stueck... reingehn... ideen... verlinken... zusammenfassen... paper",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "mumbled"},
    {"id": "CPX_4_09",
     "input": "paper... nee erst spaces erstellen vier stueck dann reingehn ideen verlinken zusammenfassen dann paper",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "correction"},
    {"id": "CPX_4_10",
     "input": "mach vier spaces q1 q2 q3 q4 geh in jeden pack sachen rein verlink zamfassn und paper",
     "expected_steps": ["bubble.create", "bubble.create", "bubble.create", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "dialect"},
    {"id": "CPX_4_11",
     "input": "spaces zeigen... in jeden reingehn... stats checken... ideen zeigen... verlinken... paper pro space",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "incomplete"},
    {"id": "CPX_4_12",
     "input": "ja also zeig spaces geh in jeden zeig stats liste ideen verlink mach paper fuer jeden",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "filler"},
    {"id": "CPX_4_13",
     "input": "alle bereiche durchgehen statistik anzeigen verbinden dokumentieren",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "ambiguous"},
    {"id": "CPX_4_14",
     "input": "list spaces enter each show stats list ideas auto-link create whitepaper for each",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "mixed_lang"},
    {"id": "CPX_4_15",
     "input": "alle spaces durchgucken in jeden rein stats checken ideen angucken verknuepfen paper machen",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "informal"},
    {"id": "CPX_4_16",
     "input": "zeig speisses gehe in jeden zeig statistik liste idden verlinke mache whitepapir",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "asr_error"},
    {"id": "CPX_4_17",
     "input": "so wie vorher alle durchgehen das anzeigen verlinken und paper",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "contextual"},
    {"id": "CPX_4_18",
     "input": "spaces... reingehn... stats... ideen... verlinken... paper",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "mumbled"},
    {"id": "CPX_4_19",
     "input": "paper... nee erst spaces zeigen reingehn stats ideen verlinken dann paper",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "correction"},
    {"id": "CPX_4_20",
     "input": "schaug de spaces geh in jeden zeig stats de idden verlink und mach paper",
     "expected_steps": ["bubble.list", "bubble.enter", "bubble.stats", "idea.list", "idea.auto_link", "idea.whitepaper"],
     "min_steps": 6, "pattern": "dialect"},

    # =========================================================================
    # TYPE 5: MIXED DOMAIN OPERATIONS (20 tests)
    # =========================================================================
    {"id": "CPX_5_01",
     "input": "space erstellen... ideen rein... als tabellen formatieren... verlinken... stats checken... umbenennen... zusammenfassung... paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "incomplete"},
    {"id": "CPX_5_02",
     "input": "aehm ja space projekt machen reingehn ideen erstellen formatieren als tabellen verlinken stats anzeigen space umbenennen zusammenfassen whitepaper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "filler"},
    {"id": "CPX_5_03",
     "input": "bereich anlegen sachen rein strukturieren verbinden statistik pruefen umbenennen zusammenfassen exportieren",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "ambiguous"},
    {"id": "CPX_5_04",
     "input": "create space enter add ideas format as tables auto-link show stats rename space summarize create whitepaper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "mixed_lang"},
    {"id": "CPX_5_05",
     "input": "space anlegen reinspringen ideen reinhauen aufhuebschen verknuepfen stats checken umbenennen zusammenfassen paper raushauen",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "informal"},
    {"id": "CPX_5_06",
     "input": "erstele speiss gehe rein erstele idden formatir als tabelen verlinke zeig statistik umbenenne zamfassung whitepapir",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "asr_error"},
    {"id": "CPX_5_07",
     "input": "so wie vorher alles aufsetzen formatieren verlinken statistik umbenennen zusammenfassen paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "contextual"},
    {"id": "CPX_5_08",
     "input": "space... reingehn... ideen... formatieren... verlinken... stats... umbenennen... zusammenfassen... paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "mumbled"},
    {"id": "CPX_5_09",
     "input": "paper... nee erst space erstellen reingehn ideen formatieren verlinken stats umbenennen zusammenfassen dann paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "correction"},
    {"id": "CPX_5_10",
     "input": "mach space geh nei pack idden rein formatir verlink zeig stats umbenennen zamfassn und paper",
     "expected_steps": ["bubble.create", "bubble.enter", "idea.create", "idea.format_table", "idea.auto_link", "bubble.stats", "bubble.update", "idea.summarize", "idea.whitepaper"],
     "min_steps": 9, "pattern": "dialect"},
    {"id": "CPX_5_11",
     "input": "spaces loeschen... neuen erstellen... reingehn... ideen von vorher rein... verlinken... als specs formatieren... whitepaper",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "incomplete"},
    {"id": "CPX_5_12",
     "input": "ja also loesch alte spaces erstell neuen geh rein fueg ideen hinzu verlink formatier als specs mach whitepaper",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "filler"},
    {"id": "CPX_5_13",
     "input": "altes weg neues anlegen sachen rein verbinden strukturieren dokumentieren",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "ambiguous"},
    {"id": "CPX_5_14",
     "input": "delete old spaces create new enter add ideas auto-link format as specs whitepaper",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "mixed_lang"},
    {"id": "CPX_5_15",
     "input": "altes rausschmeissen neues anlegen rein ideen rein verknuepfen als specs aufhuebschen paper raushauen",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "informal"},
    {"id": "CPX_5_16",
     "input": "losche speisses erstele neuen gehe rein erstele idden verlinke formatir als specks whitepapir",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "asr_error"},
    {"id": "CPX_5_17",
     "input": "das alte weg neues wie vorher anlegen sachen rein verlinken formatieren paper",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "contextual"},
    {"id": "CPX_5_18",
     "input": "loeschen... neuen... reingehn... ideen... verlinken... formatieren... paper",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "mumbled"},
    {"id": "CPX_5_19",
     "input": "paper... nee erst altes loeschen neues erstellen reingehn ideen verlinken formatieren dann paper",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "correction"},
    {"id": "CPX_5_20",
     "input": "loesch des alte mach neuen space geh nei pack idden rein verlink formatir als specs und paper",
     "expected_steps": ["bubble.delete", "bubble.create", "bubble.enter", "idea.create", "idea.auto_link", "idea.format_specs", "idea.whitepaper"],
     "min_steps": 7, "pattern": "dialect"},
]


# =============================================================================
# EVALUATOR CLASS
# =============================================================================

class IntentRouterEvaluator:
    """Evaluates the RAGIntentClassifier against test cases."""

    def __init__(self):
        self.classifier = None
        self.enhancer = None
        self.results = []
        self.start_time = None
        self.use_enhancement = os.getenv("USE_ENHANCEMENT_PIPELINE", "true").lower() == "true"

    def load_classifier(self):
        """Load the RAGIntentClassifier with fresh rules."""
        print("Loading RAGIntentClassifier...")
        try:
            # Reset the singleton to force re-initialization with latest rules
            import data.intent_rule_repository as irr
            irr._repository = None  # Reset singleton

            from swarm.orchestrator.rag_intent_classifier import RAGIntentClassifier
            self.classifier = RAGIntentClassifier()

            # Force seed with latest rules
            repo = irr.get_intent_rule_repository()
            repo._initialized = False  # Force re-seed
            count = repo.seed_default_rules()
            print(f"  [OK] Classifier loaded, {count} rules seeded")

            # Load enhancement pipeline
            if self.use_enhancement:
                try:
                    from swarm.agents.intent_enhancer import get_intent_enhancer, reset_intent_enhancer
                    reset_intent_enhancer()
                    self.enhancer = get_intent_enhancer()
                    print(f"  [OK] Enhancer loaded, {len(self.enhancer.rules.rules)} enhancement rules")
                except Exception as e:
                    print(f"  [WARN] Enhancement pipeline not available: {e}")
                    self.enhancer = None

            return True
        except Exception as e:
            print(f"  [FAIL] Could not load classifier: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def enhance_input(self, text: str) -> str:
        """Apply enhancement pipeline to input text."""
        if not self.enhancer:
            return text
        try:
            result = await self.enhancer.enhance(text, {})
            return result.normalized_text
        except Exception:
            return text

    async def run_easy_test(self, test: Dict) -> Dict:
        """Run a single EASY test (single intent)."""
        enhanced_input = await self.enhance_input(test["input"])
        result = await self.classifier.classify(enhanced_input)

        passed = result.event_type == test["expected"]
        # Lower confidence threshold for noisy speech
        confidence_threshold = 0.5 if test.get("pattern") in ["asr_error", "dialect", "mumbled", "ambiguous"] else 0.6
        confidence_ok = result.confidence >= confidence_threshold

        return {
            "test_id": test["id"],
            "input": test["input"][:60] + "..." if len(test["input"]) > 60 else test["input"],
            "expected_intent": test["expected"],
            "actual_intent": result.event_type,
            "confidence": result.confidence,
            "pattern": test.get("pattern", "unknown"),
            "status": "PASS" if (passed and confidence_ok) else "FAIL",
            "reasoning": f"Match: {passed}, Conf: {result.confidence:.2f}"
        }

    async def run_medium_test(self, test: Dict) -> Dict:
        """Run a MEDIUM test (2-5 intents)."""
        enhanced_input = await self.enhance_input(test["input"])
        result = await self.classifier.classify(enhanced_input)

        expected_steps = test["expected_steps"]
        is_multi = result.is_multi_step
        actual_steps = [s.get("event_type", s.get("intent_type", "")) for s in result.steps] if is_multi and result.steps else [result.event_type]

        # Check if first step matches
        first_step_match = (
            (is_multi and len(actual_steps) > 0 and actual_steps[0] == expected_steps[0]) or
            (not is_multi and result.event_type == expected_steps[0])
        )

        # Check step coverage
        steps_found = sum(1 for step in expected_steps if step in actual_steps)

        passed = first_step_match and (is_multi or len(expected_steps) == 1)

        return {
            "test_id": test["id"],
            "input": test["input"][:60] + "..." if len(test["input"]) > 60 else test["input"],
            "expected_intent": expected_steps[0],
            "actual_intent": result.event_type,
            "confidence": result.confidence,
            "pattern": test.get("pattern", "unknown"),
            "is_multi_step": is_multi,
            "expected_steps": expected_steps,
            "actual_steps": actual_steps,
            "step_count": len(actual_steps),
            "expected_count": len(expected_steps),
            "steps_found": steps_found,
            "status": "PASS" if passed else "PARTIAL" if first_step_match else "FAIL",
            "reasoning": f"Multi: {is_multi}, First: {'Y' if first_step_match else 'N'}, Steps: {steps_found}/{len(expected_steps)}"
        }

    async def run_complex_test(self, test: Dict) -> Dict:
        """Run a COMPLEX test (15+ steps)."""
        enhanced_input = await self.enhance_input(test["input"])
        result = await self.classifier.classify(enhanced_input)

        expected_steps = test["expected_steps"]
        min_steps = test.get("min_steps", 5)
        is_multi = result.is_multi_step
        actual_steps = [s.get("event_type", s.get("intent_type", "")) for s in result.steps] if is_multi and result.steps else [result.event_type]

        # Check if first step matches
        first_step_match = (
            (is_multi and len(actual_steps) > 0 and actual_steps[0] == expected_steps[0]) or
            (not is_multi and result.event_type == expected_steps[0])
        )

        # Check step count relative to expected
        step_ratio = len(actual_steps) / min_steps if min_steps else 0

        # Count unique step types found
        unique_expected = set(expected_steps)
        unique_actual = set(actual_steps)
        coverage = len(unique_expected & unique_actual) / len(unique_expected) if unique_expected else 0

        # Complex tests pass if they detect multi-step and get reasonable coverage
        passed = is_multi and step_ratio >= 0.3 and coverage >= 0.3

        return {
            "test_id": test["id"],
            "input": test["input"][:60] + "..." if len(test["input"]) > 60 else test["input"],
            "expected_intent": expected_steps[0] if expected_steps else None,
            "actual_intent": result.event_type,
            "confidence": result.confidence,
            "pattern": test.get("pattern", "unknown"),
            "is_multi_step": is_multi,
            "expected_steps": expected_steps[:5] + ["..."] if len(expected_steps) > 5 else expected_steps,
            "actual_steps": actual_steps[:8] + ["..."] if len(actual_steps) > 8 else actual_steps,
            "min_steps": min_steps,
            "expected_count": len(expected_steps),
            "actual_count": len(actual_steps),
            "step_ratio": round(step_ratio, 2),
            "coverage": round(coverage, 2),
            "status": "PASS" if passed else "PARTIAL" if is_multi else "FAIL",
            "reasoning": f"Multi: {is_multi}, Ratio: {step_ratio:.1%}, Coverage: {coverage:.1%}"
        }

    async def run_all_tests(self) -> Dict:
        """Run all test suites and return results."""
        self.start_time = time.time()
        self.results = {
            "easy": [],
            "medium": [],
            "complex": []
        }

        # Run EASY tests
        print("\n" + "=" * 70)
        print("EASY TESTS (100) - Single Intent with Natural Speech")
        print("=" * 70)
        for test in EASY_TESTS:
            result = await self.run_easy_test(test)
            self.results["easy"].append(result)
            status_icon = "[OK]" if result["status"] == "PASS" else "[FAIL]"
            print(f"  {test['id']}: {status_icon} {result['actual_intent']} ({result['pattern']})")

        # Run MEDIUM tests
        print("\n" + "=" * 70)
        print("MEDIUM TESTS (100) - 2-5 Intents Combined")
        print("=" * 70)
        for test in MEDIUM_TESTS:
            result = await self.run_medium_test(test)
            self.results["medium"].append(result)
            status_icon = "[OK]" if result["status"] == "PASS" else "[PART]" if result["status"] == "PARTIAL" else "[FAIL]"
            multi_info = f"multi={result['is_multi_step']}, steps={result['step_count']}"
            print(f"  {test['id']}: {status_icon} ({multi_info}, {result['pattern']})")

        # Run COMPLEX tests
        print("\n" + "=" * 70)
        print("COMPLEX TESTS (100) - 15+ Steps per Request")
        print("=" * 70)
        for test in COMPLEX_TESTS:
            result = await self.run_complex_test(test)
            self.results["complex"].append(result)
            status_icon = "[OK]" if result["status"] == "PASS" else "[PART]" if result["status"] == "PARTIAL" else "[FAIL]"
            print(f"  {test['id']}: {status_icon} steps={result['actual_count']}/{result['min_steps']} cov={result['coverage']:.0%} ({result['pattern']})")

        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate summary report with pattern breakdown."""
        elapsed = time.time() - self.start_time

        # Calculate stats per category
        categories = {}
        for category in ["easy", "medium", "complex"]:
            results = self.results[category]
            passed = sum(1 for r in results if r["status"] == "PASS")
            partial = sum(1 for r in results if r["status"] == "PARTIAL")
            failed = sum(1 for r in results if r["status"] == "FAIL")
            total = len(results)

            # Pattern breakdown
            pattern_stats = defaultdict(lambda: {"passed": 0, "total": 0})
            for r in results:
                pattern = r.get("pattern", "unknown")
                pattern_stats[pattern]["total"] += 1
                if r["status"] == "PASS":
                    pattern_stats[pattern]["passed"] += 1

            categories[category] = {
                "passed": passed,
                "partial": partial,
                "failed": failed,
                "total": total,
                "pass_rate": passed / total if total > 0 else 0,
                "pattern_breakdown": dict(pattern_stats)
            }

        total_passed = sum(c["passed"] for c in categories.values())
        total_tests = sum(c["total"] for c in categories.values())

        # Adjusted thresholds for natural speech
        thresholds = {
            "easy": 0.90,    # Was 1.00
            "medium": 0.75,  # Was 0.90
            "complex": 0.65  # Was 0.80
        }

        meets_requirements = {
            cat: stats["pass_rate"] >= thresholds[cat]
            for cat, stats in categories.items()
        }

        return {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": round(elapsed, 1),
            "total_tests": total_tests,
            "total_passed": total_passed,
            "overall_pass_rate": total_passed / total_tests if total_tests > 0 else 0,
            "categories": categories,
            "thresholds": thresholds,
            "meets_requirements": meets_requirements,
            "detailed_results": self.results
        }


def print_report(report: Dict):
    """Print formatted report to console."""
    print("\n" + "=" * 70)
    print("INTENT ROUTER EVALUATION REPORT (Natural Speech)")
    print("=" * 70)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Duration: {report['duration_seconds']}s")
    print(f"Total Tests: {report['total_tests']}")
    print(f"Total Passed: {report['total_passed']}")
    print(f"Overall Pass Rate: {report['overall_pass_rate']:.1%}")

    print("\n--- Category Results ---")
    for category, stats in report["categories"].items():
        threshold = report["thresholds"][category]
        meets = report["meets_requirements"][category]
        status = "[OK] MEETS" if meets else "[X] BELOW"
        print(f"\n{category.upper()}:")
        print(f"  Passed: {stats['passed']}/{stats['total']} ({stats['pass_rate']:.1%})")
        print(f"  Partial: {stats['partial']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Threshold: {threshold:.0%} -> {status}")

        # Pattern breakdown
        if stats.get("pattern_breakdown"):
            print(f"  By Pattern:")
            for pattern, pstats in sorted(stats["pattern_breakdown"].items()):
                rate = pstats["passed"] / pstats["total"] if pstats["total"] > 0 else 0
                print(f"    {pattern:12}: {pstats['passed']:2}/{pstats['total']:2} ({rate:.0%})")

    # Overall verdict
    all_met = all(report["meets_requirements"].values())
    print("\n" + "=" * 70)
    if all_met:
        print("VERDICT: [OK] ALL THRESHOLDS MET - Intent Router PASSED")
    else:
        failed_cats = [c for c, m in report["meets_requirements"].items() if not m]
        print(f"VERDICT: [X] THRESHOLDS NOT MET for: {', '.join(failed_cats)}")
    print("=" * 70)


def save_report(report: Dict, filename: str = "intent_router_evaluation_report.json"):
    """Save detailed report to JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed report saved to: {filename}")


async def main():
    """Main entry point."""
    print("=" * 70)
    print("VibeMind Intent Router Evaluation Suite (Natural Speech)")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tests: {len(EASY_TESTS)} Easy + {len(MEDIUM_TESTS)} Medium + {len(COMPLEX_TESTS)} Complex = {len(EASY_TESTS) + len(MEDIUM_TESTS) + len(COMPLEX_TESTS)} Total")
    print(f"Speech Patterns: {len(PATTERNS)} categories")

    evaluator = IntentRouterEvaluator()

    if not evaluator.load_classifier():
        print("\nFATAL: Could not load classifier. Exiting.")
        sys.exit(1)

    report = await evaluator.run_all_tests()
    print_report(report)
    save_report(report)

    # Exit with appropriate code
    all_met = all(report["meets_requirements"].values())
    sys.exit(0 if all_met else 1)


if __name__ == "__main__":
    asyncio.run(main())
