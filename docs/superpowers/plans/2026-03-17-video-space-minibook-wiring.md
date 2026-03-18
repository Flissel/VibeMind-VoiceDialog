# Video Space — Minibook Wiring Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing Video Space (agent, tools, event router already done) into the Minibook enrichment pipeline so voice/text commands route correctly.

**Architecture:** Three integration points: (1) Intent Classifier learns video.* events, (2) Minibook collaboration_tools registers the video space agent + keywords, (3) SpaceRouter + TaskEnricher map video.* prefixes correctly.

**Tech Stack:** Python, existing VibeMind patterns

**Spec:** `docs/superpowers/specs/2026-03-16-video-space-design.md`

---

### Task 1: Add Video to Minibook SPACE_AGENT_REGISTRY + SPACE_KEYWORDS

**Files:**
- Modify: `python/spaces/minibook/tools/collaboration_tools.py:109-133`

- [ ] **Step 1: Add video entry to SPACE_AGENT_REGISTRY**

After the `"n8n"` entry (line 118), add:

```python
    "video": {
        "name": "vibemind_video",
        "domain_prefix": "video.",
        "role": (
            "Video-Produktion und KI-Synthese: Team-Videos bauen, Deepfake-Lipsync, "
            "Stimmen-Klone, Vision Videos mit Sora AI, Demo-Videos. "
            "Zustaendig fuer professionelle Videoproduktion und KI-basierte Video-Synthese."
        ),
    },
```

- [ ] **Step 2: Add video keywords to SPACE_KEYWORDS**

After the `"n8n"` entry (line 132), add:

```python
    "video": ["video", "film", "clip", "schneid", "lipsync", "deepfake", "voice clone",
              "produkt-video", "sora", "team-video", "vision", "voiceover", "stimme"],
```

- [ ] **Step 3: Verify syntax**

Run: `cd python && python -c "from spaces.minibook.tools.collaboration_tools import SPACE_AGENT_REGISTRY, SPACE_KEYWORDS; print('video' in SPACE_AGENT_REGISTRY, 'video' in SPACE_KEYWORDS)"`
Expected: `True True`

- [ ] **Step 4: Commit**

```bash
git add python/spaces/minibook/tools/collaboration_tools.py
git commit -m "feat(video): register Video space in Minibook SPACE_AGENT_REGISTRY + SPACE_KEYWORDS"
```

---

### Task 2: Add Video to SpaceRouter EVENT_TYPE_TO_SPACE

**Files:**
- Modify: `python/spaces/minibook/enrichment/space_router.py:40-51`

- [ ] **Step 1: Add video prefix to EVENT_TYPE_TO_SPACE**

After line 49 (`"schedule.": "schedule"`), add:

```python
    "video.": "video",
```

Also add the missing `"n8n.": "n8n"` entry (pre-existing gap):

```python
    "n8n.": "n8n",
```

- [ ] **Step 2: Verify syntax**

Run: `cd python && python -c "from spaces.minibook.enrichment.space_router import EVENT_TYPE_TO_SPACE; print(EVENT_TYPE_TO_SPACE.get('video.'))`
Expected: `video`

- [ ] **Step 3: Commit**

```bash
git add python/spaces/minibook/enrichment/space_router.py
git commit -m "feat(video): add video.* and n8n.* to SpaceRouter EVENT_TYPE_TO_SPACE"
```

---

### Task 3: Add Video to TaskEnricher defaults + prefix mapping

**Files:**
- Modify: `python/spaces/minibook/enrichment/task_enricher.py:213-240`

- [ ] **Step 1: Add video to _infer_secondary_event_type defaults (line 213-223)**

Add to the `defaults` dict:

```python
            "video": "video.status",
            "n8n": "n8n.list",
```

- [ ] **Step 2: Add video to _space_to_prefix mapping (line 229-239)**

Add to the `prefixes` dict:

```python
        "video": "video.",
        "n8n": "n8n.",
```

- [ ] **Step 3: Verify syntax**

Run: `cd python && python -c "from spaces.minibook.enrichment.task_enricher import TaskEnricher; t = TaskEnricher(); print(t._infer_secondary_event_type('video', 'test'))"`
Expected: `video.status`

- [ ] **Step 4: Commit**

```bash
git add python/spaces/minibook/enrichment/task_enricher.py
git commit -m "feat(video): add video + n8n to TaskEnricher defaults and prefix mapping"
```

---

### Task 4: Add Video Space section to Intent Classifier

**Files:**
- Modify: `python/swarm/orchestrator/intent_classifier.py:395` (after N8N section, before WICHTIGE UNTERSCHEIDUNG)

- [ ] **Step 1: Add VIDEO SPACE section to CLASSIFIER_PROMPT_TEMPLATE**

Insert after line 394 (end of N8N section), before line 396 (WICHTIGE UNTERSCHEIDUNG):

```python
### 9. VIDEO SPACE (Videoproduktion) - Director
Der Bereich fuer Videoproduktion, Deepfake-Synthese und Team-Videobearbeitung.

**Schluesselwoerter:** video, produktion, deepfake, lipsync, stimme, voiceover, team video, sora, vision, demo

**Event-Types:**
- video.status: Gesamtstatus des Video-Space pruefen
  → "Video Status", "Sind die Video-Tools installiert?", "Was kann der Video Space?"
- video.team_status: Status der Team-Video-Pipeline anzeigen
  → "Team-Video Status", "Welche Schritte gibt es?", "Pipeline Status"
- video.team_run: Einen Schritt der Team-Pipeline ausfuehren
  → "Lauf Schritt analyze", "Fuehre Composite aus", "Team Pipeline all"
  → payload: {"step": "analyze|backgrounds|composite|build|split|final|all"}
- video.vision: Vision Video mit Sora AI generieren (Her-Stil)
  → "Generiere ein Vision Video", "Erstelle Sora Video", "Mach ein Vision Video"
  → payload: {"generate_sora": true, "generate_tts": false, "build_only": false}
- video.demo_analyze: Bildschirmaufzeichnung fuer Demo analysieren
  → "Analysiere das Screenrecording", "Demo Analysis"
  → payload: {"input_file": "path/to/video.mp4", "target_duration": 60}
- video.demo_build: Demo-Video aus Config bauen
  → "Baue ein Demo-Video", "Build Demo aus Config"
  → payload: {"config_path": "path/to/config.json"}
- video.lipsync: Lip Sync mit MuseTalk ausfuehren
  → "Mach Lipsync", "Lipsync fuer die Videos", "Lipsync fuer Felix"
  → payload: {"person": "optional_name"}
- video.lipsync_analyze: Qualitaet des Lip Sync pruefen
  → "Analysiere Lipsync Qualitaet", "Wie gut ist der Lipsync?"
- video.voice_clone: Stimmen der Team-Mitglieder klonen (ElevenLabs)
  → "Klone die Stimmen", "Voice Clone", "Stimmen klonen"
- video.voice_tts: Text-to-Speech Voiceover generieren
  → "Generiere Voiceover", "TTS fuer Team", "Voiceover fuer Felix"
  → payload: {"person": "optional_name"}
```

- [ ] **Step 2: Verify the classifier loads without errors**

Run: `cd python && python -c "from swarm.orchestrator.intent_classifier import IntentClassifier; print('Classifier loaded OK')"`
Expected: `Classifier loaded OK`

- [ ] **Step 3: Commit**

```bash
git add python/swarm/orchestrator/intent_classifier.py
git commit -m "feat(video): add 10 video.* event types to Intent Classifier prompt"
```

---

### Task 5: Update spec to reflect actual implementation

**Files:**
- Modify: `docs/superpowers/specs/2026-03-16-video-space-design.md`

- [ ] **Step 1: Update spec status from Draft to Implemented**

Change the header status and update event types to match actual implementation (10 events, not original 6).

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-03-16-video-space-design.md
git commit -m "docs(video): update spec to reflect actual 10-event implementation"
```
