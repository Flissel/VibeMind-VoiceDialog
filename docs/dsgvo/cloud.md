# DSGVO: Cloud Services (OpenAI, Anthropic, OpenRouter)

**Tier 3 der Drei-Tier-Architektur — produktiv genutzte Cloud-Anbieter.**

**Stand: 2026-09-22.**

## Was ist dieser Weg?

VibeMind bietet für die LLM-Inferenz drei Bereitstellungswege: lokal, konfigurierbare eigene Endpunkte und Cloud-Dienste. Dieses Dokument beschreibt den Cloud-Weg: OpenAI, Anthropic und OpenRouter, laut interner Einstufung "integriert und produktiv genutzt" (`readme_dsgvo.md`).

In der ausgelieferten Standardkonfiguration (`python/config/llm_models.yml`) läuft der überwiegende Teil der Cloud-Rollen über OpenRouter — einen Vermittlungsdienst, der Zugriff auf Modelle mehrerer Anbieter (u. a. Anthropics Claude, OpenAIs GPT-Modelle) über eine einzige API bündelt (Client-Implementierung: `python/swarm/cloud_client.py`). Einige Rollen sprechen OpenAI direkt an: die Voice-Realtime-API (`voice`, `gpt-4o-realtime-preview`), Spracherkennung (`transcription`/`desktop_stt`, `whisper-1`) und Sprachausgabe (`desktop_tts`, `tts-1`). Anthropic ist zusätzlich als eigener Provider konfiguriert (`ANTHROPIC_API_KEY`, `base_url: https://api.anthropic.com/v1/`) und wird laut `.env.example` u. a. vom Claude-Code-CLI-Runner verwendet sowie — falls kein OpenRouter-Key gesetzt ist — von Rowboat direkt.

Dieser Weg wird nicht einheitlich für das gesamte System genutzt, sondern pro Funktion einzeln konfiguriert: Das Marketing-System etwa nutzt für seine Inbound-Klassifikation bewusst kein externes LLM, sondern lokales Ollama (`spaces/marketing/docs/dsgvo-data-flow.md`).

## Wo verlassen Daten die Maschine?

Ja — bei diesem Weg grundsätzlich immer. Sobald eine Rolle auf OpenAI, Anthropic oder OpenRouter konfiguriert ist, gehen Prompt-Inhalt und der vom System zusammengestellte Kontext über das Internet an die Server dieser Anbieter, alle drei mit Infrastruktur in den USA. Das ist der Grund, warum dieser Ordner existiert, und es soll hier nicht beschönigt werden: bei diesem Bereitstellungsweg verlassen Daten die eigene Maschine und gehen an einen Dritten in einem Drittland.

Dass dieser Transfer real stattfindet und rechtlich noch nicht abschließend abgesichert ist, bestätigt auch eine andere Quelle im Repository: Die AVV-Vorlage eines Teilsystems führt "Anthropic (Claude API)" ausdrücklich als Unterauftragsverarbeiter mit Sitz USA, mit offenem Prüf-Feld "⟨DPF/SCC prüfen und eintragen⟩" (`spaces/sales-claw/docs/07_AVV_VORLAGE.md`).

## Was ist heute umgesetzt

- **OpenRouter-Client**: `python/swarm/cloud_client.py` (`CloudModelClient`), lädt `.env`, ruft OpenRouter über eine OpenAI-kompatible Schnittstelle auf.
- **Direkte Provider-Konfiguration** in `python/config/llm_models.yml`: `openai` (`api_key_env: OPENAI_API_KEY`), `openrouter` (`base_url: https://openrouter.ai/api/v1`, `api_key_env: OPENROUTER_API_KEY`), `anthropic` (`base_url: https://api.anthropic.com/v1/`, `api_key_env: ANTHROPIC_API_KEY`).
- **Konkret produktiv über diese Anbieter konfigurierte Rollen** (Auszug aus `python/config/llm_models.yml`): `voice` (OpenAI, Realtime-API), `transcription`/`desktop_stt` (OpenAI Whisper), `desktop_tts` (OpenAI TTS), `tool_orchestrator`/`desktop_reasoning`/`desktop_vision`/`idea_enrichment`/`rowboat_model` (OpenRouter, `anthropic/claude-sonnet-4`), `claude_worker` (OpenRouter, `anthropic/claude-opus-4-5-20251101`), `mirofish_eval` (OpenAI, `gpt-5.5`).
- **Art. 15/17-Werkzeuge auf Anwendungsebene** existieren im Sales-Teilsystem (`kontakt_auskunft`, `loeschantrag_vermerken`, `spaces/sales-claw/docs/06_DSGVO.md`) — sie exportieren bzw. sperren die in VibeMinds eigener Datenbank gespeicherten Kontaktdaten. Sie sind kein Protokoll darüber, welche Prompt-Inhalte im Einzelfall an OpenAI, Anthropic oder OpenRouter übertragen wurden.

## Was ist nicht umgesetzt

- **In den geprüften Quellen ist kein AVV mit OpenAI oder OpenRouter dokumentiert.** Nur für Anthropic existiert überhaupt ein Eintrag in einer AVV-Vorlage, und der ist mit Platzhalter offen (siehe oben).
- **Kein Protokoll, welche Inhalte an welchen Cloud-Anbieter gingen.** In den geprüften Quellen findet sich kein Audit-Log auf Prompt-Ebene für diesen Weg.
- **Keine Datenschutz-Folgenabschätzung für den Cloud-Weg.** Die einzige vorliegende DSFA-Bewertung (`spaces/marketing/docs/dsgvo-data-flow.md`, Abschnitt 8) gilt nur für das Marketing-System und nennt "Integration externer LLM-APIs (OpenAI etc.)" als zukünftigen Auslöser, der dort "heute nicht der Fall" sei — für andere Systemteile, die bereits über OpenAI, Anthropic oder OpenRouter laufen (Voice, Tool-Orchestrator, Desktop-Automation u. a.), liegt keine eigene DSFA vor.
- Systemweit: keine formale GDPR-Zertifizierung, keine Verschlüsselung at Rest (`readme_dsgvo.md`).

---

Dieses Dokument beschreibt den technischen Implementierungsstand. Es ersetzt keine Rechtsberatung.
