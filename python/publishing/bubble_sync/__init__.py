"""Bidirectional sync between VibeMind bubbles (Supabase public.ideas) and the
Rowboat .md vault (~/.rowboat/knowledge/Projects/VibeMind - {title}/).

Modeled on the proven marketing sync (spaces/marketing/sync/). Phase 1 here is
foundation only: stable frontmatter IDs + render + validation (no FS->DB yet).

Layers:
  - _db.py          docker-exec psql access (verbatim from marketing) — Worker B
                    must write back via this (NOT PostgREST) so the loop-prevention
                    session-GUC + the write share one transaction.
  - _frontmatter.py deterministic YAML frontmatter (idea schema).
  - _queries.py     SQL against public.ideas.
  - render_md.py    render_idea_md / render_overview_md (DB -> .md).
  - validate.py     validate_idea_md / parse_idea_md (format checks both ways).
"""
