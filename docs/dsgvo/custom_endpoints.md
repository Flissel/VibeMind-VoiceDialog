# DSGVO: Eigene Endpunkte (Custom Endpoints)

**Tier 2 der Drei-Tier-Architektur — konfigurierbare API-Endpunkte statt fest verdrahteter Anbieter.**

**Stand: 2026-09-22.**

## Was ist dieser Weg?

VibeMind bietet für die LLM-Inferenz drei Bereitstellungswege: lokal, konfigurierbare eigene Endpunkte und Cloud-Dienste (OpenAI, Anthropic, OpenRouter). Dieses Dokument beschreibt den Weg über eigene, konfigurierbare Endpunkte.

Jede LLM-Rolle im System (Klassifikation, Antwortgenerierung, Orchestrierung, Bildanalyse usw.) bezieht Anbieter, Modell, Basis-URL und API-Key zentral aus `python/config/llm_models.yml`, ausgewertet über `python/llm_config.py`. Fünf Anbieter sind dort hinterlegt (`openai`, `openrouter`, `anthropic`, `claude-code`, `ollama`), jeweils mit eigenem `base_url` und `api_key_env`. Der Betreiber kann jede Rolle umkonfigurieren, ohne Code zu ändern — per Umgebungsvariable (`LLM_MODEL_<ROLLE>`) oder durch Ändern der YAML. Welche Keys aktiv sind, steuert `.env` (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, siehe `.env.example`); für Rowboat ist dort explizit eine Prioritätsreihenfolge dokumentiert: `OPENROUTER_API_KEY` > `OPENAI_API_KEY` > `ANTHROPIC_API_KEY`.

Die Provider-Liste ist im Code nicht auf diese fünf Namen hartkodiert: `get_client()`/`get_async_client()` in `python/llm_config.py` bauen für jeden Provider außer `claude-code` einen Standard-Client (`openai.OpenAI(api_key=..., base_url=...)`). Ein zusätzlicher, selbst betriebener oder EU-ansässiger OpenAI-kompatibler Endpunkt (z. B. vLLM, LM Studio, Azure OpenAI) ließe sich architektonisch über einen weiteren Eintrag im `providers:`-Abschnitt der YAML anbinden. Das ist eine Eigenschaft des Codes, keine dokumentierte, getestete Produktfunktion — belegt ist nur der Betrieb mit den fünf hinterlegten Anbietern.

## Wo verlassen Daten die Maschine?

Immer dann, wenn die für eine Rolle konfigurierte `base_url` nicht auf den lokalen Ollama-Host zeigt. Welcher Anbieter die Daten tatsächlich empfängt, ist bei diesem Tier keine feste Systemeigenschaft, sondern eine Konfigurationsentscheidung: Standardmäßig sind die meisten Rollen in `python/config/llm_models.yml` auf `openrouter` (`https://openrouter.ai/api/v1`) gesetzt — ein Drittanbieter mit eigener Infrastruktur, an den Prompt und Kontext gehen, sobald diese Rolle aufgerufen wird. Ob ein vom Betreiber selbst eingetragener Endpunkt tatsächlich in der EU liegt oder in einem Drittland, prüft das System nicht — das bleibt Aufgabe der Konfiguration, nicht der Software.

## Was ist heute umgesetzt

- **Zentrale, rollenbasierte Konfiguration**: `python/llm_config.py` (`get_model()`, `get_provider()`, `get_api_key()`, `get_base_url()`) liest pro Rolle aus `python/config/llm_models.yml`, mit Override-Priorität Umgebungsvariable > YAML > Fallback.
- **Automatischer Fallback**: Fehlt der primäre API-Key einer Rolle, springt das System auf `OPENROUTER_API_KEY` um, sofern gesetzt (`_resolve_credentials()`, `python/llm_config.py`) — auch das zeigt: welche Adresse eine Anfrage tatsächlich erreicht, hängt vom vorhandenen Schlüssel ab, nicht von einer festen Zuordnung.
- **Dokumentierte Env-Variablen**: `.env.example` listet `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` als die Stellschrauben dieses Wegs.

## Was ist nicht umgesetzt

- **Keine Prüfung, ob ein konfigurierter Endpunkt in der EU liegt**, oder ob ein Auftragsverarbeitungsvertrag (AVV, Art. 28 DSGVO) mit dessen Betreiber besteht — das System validiert nur, ob ein API-Key vorhanden ist, nicht wo die Daten ankommen.
- **Keine AVV-Vorlage für Custom-Endpoints im Hauptsystem.** Es existiert eine AVV-Vorlage in einem Teilsystem (`spaces/sales-claw/docs/07_AVV_VORLAGE.md`), die aber das Verhältnis Betreiber↔Team-Mitglied regelt, nicht die LLM-Anbindung — und selbst dort ist der Eintrag zum Unterauftragsverarbeiter Anthropic noch mit Platzhalter offen: "USA — ⟨DPF/SCC prüfen und eintragen⟩".
- Systemweit: keine formale GDPR-Zertifizierung, keine Verschlüsselung at Rest (`readme_dsgvo.md`).

---

Dieses Dokument beschreibt den technischen Implementierungsstand. Es ersetzt keine Rechtsberatung.
