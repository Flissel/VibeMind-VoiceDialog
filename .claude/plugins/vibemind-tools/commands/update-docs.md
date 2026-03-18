---
name: update-docs
description: Scan codebase and update documentation to match current code state
---

Run the documentation drift scanner to find outdated docs, then fix them:

1. First run the drift scanner:
```bash
python .claude/plugins/vibemind-tools/skills/update-docs/scripts/doc_drift_scanner.py --root .
```

2. Analyze the drift report output — it shows missing, extra, and outdated documentation grouped by section (spaces, events, tools, db, ipc, agents).

3. For each drift item, read the code source of truth and update the corresponding doc file. Follow these priorities:
   - **Critical**: CLAUDE.md, `docs/api/` reference docs
   - **High**: Space READMEs, architecture docs
   - **Medium**: German docs (`docs/0X_*.md`)

4. After making updates, re-run the scanner to verify zero drift.

For detailed update instructions per section type, consult the skill at `.claude/plugins/vibemind-tools/skills/update-docs/SKILL.md` and the cross-reference map at `.claude/plugins/vibemind-tools/skills/update-docs/references/doc-structure.md`.
