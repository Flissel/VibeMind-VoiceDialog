# Intent-to-Tool Test Report

**Generated:** 2026-01-24T06:52:25.295771

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 59 |
| Passed | 22 (37.3%) |
| Failed | 37 |
| Avg Classification | 4375ms |
| Avg Tool Execution | 121ms |
| P95 Classification | 5894ms |
| P95 Tool Execution | 511ms |

## Results by Category

### bubble (13 tests)

| Intent | Status | Classify (ms) | Tool (ms) | Error |
|--------|--------|--------------|-----------|-------|
| bubble.list | PASS | 4818 | 1 | - |
| bubble.list | PASS | 4078 | 2 | - |
| bubble.create | PASS | 3719 | 1 | - |
| bubble.create | PASS | 5894 | 2507 | - |
| bubble.enter | PASS | 9151 | 0 | - |
| bubble.enter | PASS | 4590 | 0 | - |
| bubble.exit | FAIL | 3306 | 0 | - |
| bubble.exit | PASS | 4616 | 511 | - |
| bubble.delete | PASS | 4548 | 0 | - |
| bubble.delete_all_except | FAIL | 5215 | 0 | - |
| bubble.stats | PASS | 5009 | 0 | - |
| bubble.update | FAIL | 5186 | 0 | - |
| bubble.current | FAIL | 2422 | 0 | - |

### idea (20 tests)

| Intent | Status | Classify (ms) | Tool (ms) | Error |
|--------|--------|--------------|-----------|-------|
| idea.create | PASS | 5501 | 0 | - |
| idea.create | PASS | 5804 | 0 | - |
| idea.list | PASS | 3831 | 0 | - |
| idea.list | PASS | 4722 | 0 | - |
| idea.find | PASS | 4280 | 4 | - |
| idea.find | FAIL | 5537 | 0 | - |
| idea.delete | FAIL | 3974 | 0 | - |
| idea.update | FAIL | 5555 | 0 | - |
| idea.update | FAIL | 2237 | 0 | - |
| idea.count | FAIL | 4734 | 0 | - |
| idea.expand | PASS | 5894 | 0 | - |
| idea.move | FAIL | 5079 | 0 | - |
| idea.connect | FAIL | 4555 | 4 | - |
| idea.link_to_root | FAIL | 2764 | 0 | - |
| idea.auto_link | PASS | 5664 | 0 | - |
| idea.auto_link | PASS | 4754 | 0 | - |
| idea.analyze_links | FAIL | 2955 | 0 | - |
| idea.classify | FAIL | 3189 | 0 | - |
| idea.classify | FAIL | 2839 | 0 | - |
| idea.current_space | FAIL | 2255 | 0 | - |

### idea_format (10 tests)

| Intent | Status | Classify (ms) | Tool (ms) | Error |
|--------|--------|--------------|-----------|-------|
| idea.summarize | FAIL | 2322 | 0 | - |
| idea.whitepaper | FAIL | 7323 | 0 | - |
| idea.format_table | FAIL | 2585 | 0 | - |
| idea.format_note | FAIL | 2958 | 0 | - |
| idea.format_action_list | FAIL | 4652 | 0 | - |
| idea.format_pros_cons | FAIL | 4154 | 0 | - |
| idea.format_hierarchy | FAIL | 3230 | 0 | - |
| idea.format_specs | FAIL | 2726 | 0 | - |
| idea.convert_format | FAIL | 2326 | 0 | - |
| idea.list_formats | FAIL | 4555 | 0 | - |

### system (5 tests)

| Intent | Status | Classify (ms) | Tool (ms) | Error |
|--------|--------|--------------|-----------|-------|
| system.status | FAIL | 5115 | 0 | - |
| system.active_tasks | FAIL | 2476 | 0 | - |
| system.queue_status | FAIL | 5219 | 0 | - |
| system.recent_completions | FAIL | 5020 | 0 | - |
| system.check_stuck | FAIL | 2413 | 0 | - |

### task (4 tests)

| Intent | Status | Classify (ms) | Tool (ms) | Error |
|--------|--------|--------------|-----------|-------|
| task.list_today | FAIL | 5382 | 0 | - |
| task.recent | FAIL | 5212 | 0 | - |
| task.search | FAIL | 5160 | 0 | - |
| task.stats | FAIL | 5745 | 0 | - |

### conversation (2 tests)

| Intent | Status | Classify (ms) | Tool (ms) | Error |
|--------|--------|--------------|-----------|-------|
| conversation.greeting | PASS | 3491 | 0 | - |
| conversation.help | FAIL | 5383 | 0 | - |

### natural (5 tests)

| Intent | Status | Classify (ms) | Tool (ms) | Error |
|--------|--------|--------------|-----------|-------|
| idea.list | PASS | 4823 | 0 | - |
| bubble.create | PASS | 4654 | 1 | - |
| idea.create | PASS | 4090 | 0 | - |
| bubble.enter | PASS | 3656 | 0 | - |
| idea.connect | FAIL | 4785 | 4 | - |

## Failed Tests

| Intent | Input | Expected | Actual | Error |
|--------|-------|----------|--------|-------|
| bubble.exit | Zurück zum Multiverse... | bubble.exit | conversation.unknown | mismatch |
| bubble.delete_all_except | Lösche alle Spaces außer Marke... | bubble.delete_all_except |  | mismatch |
| bubble.update | Benenne den Space um zu Sales... | bubble.update | bubble.create | mismatch |
| bubble.current | Wo bin ich gerade?... | bubble.current | conversation.unknown | mismatch |
| idea.find | Suche nach Datenbankstruktur... | idea.find | idea.explore.start | mismatch |
| idea.delete | Lösche die Idee API Design... | idea.delete | idea.delete | mismatch |
| idea.update | Update API Design mit REST End... | idea.update | idea.create | mismatch |
| idea.update | Schreib in die Idee: Das ist d... | idea.update | conversation.unknown | mismatch |
| idea.count | Wie viele Ideen habe ich?... | idea.count | bubble.stats | mismatch |
| idea.move | Verschiebe die Idee nach recht... | idea.move | idea.move | mismatch |
| idea.connect | Verbinde API Design mit Datenb... | idea.connect | idea.connect | mismatch |
| idea.link_to_root | Verknüpfe das mit dem Root... | idea.link_to_root | conversation.unknown | mismatch |
| idea.analyze_links | Analysiere die Verbindungen... | idea.analyze_links | conversation.unknown | mismatch |
| idea.classify | Klassifiziere die Idee... | idea.classify | conversation.unknown | mismatch |
| idea.classify | Send das ans Backend zur Analy... | idea.classify | conversation.unknown | mismatch |
| idea.summarize | Fasse die Idee zusammen... | idea.summarize | conversation.unknown | mismatch |
| idea.whitepaper | Erstelle ein Whitepaper... | idea.whitepaper |  | mismatch |
| idea.format_table | Formatiere das als Tabelle... | idea.format_table | conversation.unknown | mismatch |
| idea.format_note | Formatiere das als Notiz... | idea.format_note | conversation.unknown | mismatch |
| idea.format_action_list | Mach daraus eine Aktionsliste... | idea.format_action_list | conversation.unknown | mismatch |
| idea.format_pros_cons | Erstelle eine Pro-Contra Liste... | idea.format_pros_cons | conversation.unknown | mismatch |
| idea.format_hierarchy | Zeig das hierarchisch an... | idea.format_hierarchy | conversation.unknown | mismatch |
| idea.format_specs | Formatiere das als Spezifikati... | idea.format_specs | conversation.unknown | mismatch |
| idea.convert_format | Konvertiere zu Markdown... | idea.convert_format | conversation.unknown | mismatch |
| idea.list_formats | Welche Formate gibt es?... | idea.list_formats | conversation.unknown | mismatch |
| idea.current_space | In welchem Space bin ich?... | idea.current_space | conversation.unknown | mismatch |
| system.status | Zeig mir den Systemstatus... | system.status | conversation.help | mismatch |
| system.active_tasks | Welche Tasks laufen gerade?... | system.active_tasks | conversation.unknown | mismatch |
| system.queue_status | Wie ist der Queue Status?... | system.queue_status | conversation.help | mismatch |
| system.recent_completions | Zeig die letzten abgeschlossen... | system.recent_completions | idea.list | mismatch |
| system.check_stuck | Gibt es hängende Operationen?... | system.check_stuck | conversation.unknown | mismatch |
| task.list_today | Was steht heute an?... | task.list_today | conversation.help | mismatch |
| task.recent | Zeig mir die letzten Aufgaben... | task.recent | idea.list | mismatch |
| task.search | Suche nach Task Marketing... | task.search | bubble.find | mismatch |
| task.stats | Zeig mir die Task Statistiken... | task.stats | idea.stats | mismatch |
| conversation.help | Was kannst du alles?... | conversation.help | conversation.unknown | mismatch |
| idea.connect | verbinde api desain mit datenb... | idea.connect | idea.connect | mismatch |

## Monitoring Metrics

- **total_operations:** 59
- **errors:** 37
- **error_rate:** 0.63
