# DSGVO: Lokale Modelle (Ollama)

**Tier 1 der Drei-Tier-Architektur — Datenverarbeitung ausschließlich auf der eigenen Maschine.**

**Stand: 2026-09-22.**

## Was ist dieser Weg?

VibeMind bietet für die LLM-Inferenz drei Bereitstellungswege: lokal, konfigurierbare eigene Endpunkte und Cloud-Dienste (OpenAI, Anthropic, OpenRouter). Dieses Dokument beschreibt den lokalen Weg.

Beim lokalen Weg läuft die Sprachmodell-Inferenz über Ollama, einen selbst gehosteten Inferenz-Server auf derselben Maschine wie VibeMind. Der Wrapper-Client liegt in `python/swarm/ollama_client.py`. Standardmodell ist `llama3.1:8b` (gewählt wegen Function-Calling-Unterstützung; laut Code-Kommentar für Systeme mit wenig RAM ist `qwen2.5:3b` über die Umgebungsvariable `OLLAMA_MODEL` vorgesehen). Der Ollama-Server wird standardmäßig unter `http://localhost:11434` erwartet, konfigurierbar über `OLLAMA_HOST`.

## Wo verlassen Daten die Maschine?

Nirgendwo. Bei diesem Weg bleiben Prompt, Konversationskontext und Antwort auf dem Rechner, auf dem VibeMind läuft. Auch der interne Fallback — falls die primäre Ollama-Anbindung fehlschlägt — wechselt nicht auf einen Cloud-Endpunkt, sondern spricht weiterhin denselben lokalen Host über eine OpenAI-kompatible Schnittstelle an (`{host}/v1`, siehe `_create_openai_compatible_client()` in `python/swarm/ollama_client.py`). Dieser Client enthält keinen Codepfad, der bei einem lokalen Fehler automatisch an einen externen Anbieter ausweicht.

Das ist der Punkt, für den dieser Ordner existiert: mit diesem Bereitstellungsweg konfiguriert, verlässt kein Nutzerdatum die eigene Infrastruktur.

## Was ist heute umgesetzt

- **Ollama-Client-Wrapper**: `python/swarm/ollama_client.py` — Singleton (`get_ollama_client()`), Lazy-Initialisierung, Health-Check gegen `/api/tags` (`health_check()`).
- **Zentrale Konfiguration**: Die Rolle `local` ist in `python/config/llm_models.yml` fest auf `provider: ollama`, `model: llama3.1:8b`, `base_url: http://localhost:11434`, `api_key_env: null` gesetzt — kein API-Key nötig.
- **Mehrere Systemfunktionen laufen bereits standardmäßig lokal**, nicht nur die Rolle `local`: `drope_resolver` (Referenzauflösung, `SakanaAI/DroPE-SmolLM-135M-32K`), `mirofish` (Simulation, `qwen2.5:32b`), `mirofish_embedding` (`nomic-embed-text`), `messaging_relevance` (WhatsApp/Telegram-Relevanzfilter, `qwen2.5:3b`), `wizard_ollama` (`qwen2.5:3b`) — alle mit `provider: ollama` in `python/config/llm_models.yml`.
- **Produktiver Einsatz außerhalb von Voice bestätigt**: Das Marketing-System klassifiziert eingehende Antworten lokal über Ollama, ausdrücklich ohne externes LLM ("POST /api/n8n/classify_helper/ollama (LOCAL Ollama, kein external LLM)", `spaces/marketing/docs/dsgvo-data-flow.md`).

## Was ist nicht umgesetzt

- **Kein systemweiter "nur lokal"-Schalter.** Die Zuordnung Provider→Rolle steht pro Rolle einzeln in `python/config/llm_models.yml`; die meisten der übrigen, hier nicht genannten Rollen sind dort standardmäßig auf `openrouter` (Cloud) gesetzt. Wer eine vollständig lokale Installation will, muss das für jede relevante Rolle einzeln auf `ollama` umstellen und prüfen — dafür existiert heute kein einzelner Schalter.
- **"Basis-Client"**, so die eigene Einstufung (`readme_dsgvo.md`) — der Client selbst bietet keine Modellverwaltung (Download, Wechsel im laufenden Betrieb).
- Systemweit gilt unabhängig vom Bereitstellungsweg: keine formale GDPR-Zertifizierung, keine Verschlüsselung at Rest (`readme_dsgvo.md`).

---

Dieses Dokument beschreibt den technischen Implementierungsstand. Es ersetzt keine Rechtsberatung.
