# DSGVO

**Datensouveränität und Privacy-First-Deployment-Infrastruktur für GDPR-Compliance**

**Stand: 2026-09-22.**

## Overview

Das DSGVO-Konzept implementiert Vibeminds Ansatz zur Datensouveränität mit drei Deployment-Pfaden: lokal, Custom Endpoints und Cloud Services. Ziel ist die Erfüllung europäischer Datenschutzstandards bei maximaler Flexibilität.

## Drei-Tier-Architektur

| Tier | Beschreibung | Implementierungsstand |
|------|-------------|----------------------|
| **Lokal** | Ollama-Integration für lokale Inference | Basis-Client vorhanden (`python/swarm/ollama_client.py`, llama3.1:8b) |
| **Custom Endpoints** | Konfigurierbare API-Keys in `.env` | Funktional via OpenRouter und andere Provider |
| **Cloud Services** | OpenAI, Anthropic, OpenRouter | Integriert und produktiv genutzt |

## Aktueller Implementierungsstand

### Implementiert
- **Ollama-Client**: Wrapper für lokale LLM-Inference (`python/swarm/ollama_client.py`)
- **Cloud-Provider-Integration**: OpenAI, Anthropic, OpenRouter über konfigurierbare API-Keys in `python/config.py`
- **Konfigurierbare Endpoints**: `.env`-basierte Konfiguration für verschiedene Provider
- **Auskunft nach Art. 15 DSGVO**: `kontakt_auskunft(lead_id)` erzeugt einen vollständigen Markdown-Export aller zu einer Person gespeicherten Daten — Stammdaten, Protokoll, Entwürfe (`spaces/sales-claw/docs/06_DSGVO.md`, `spaces/sales-claw/sales-mcp/server.py`); die Übergabe an die betroffene Person prüft der Betreiber von Hand
- **Verzeichnis von Verarbeitungstätigkeiten nach Art. 30 DSGVO**: für das Marketing-System geführt, inkl. Audit-Log-Tabellen (`marketing.audit_log`, `marketing.n8n_api_audit`) (`spaces/marketing/docs/dsgvo-data-flow.md`)

### Teilweise implementiert
- **OAuth**: Existiert nur in Submodulen (Coding_engine `src/api/auth/oauth.py`, Rowboat), **nicht im Hauptsystem integriert**
- **Federated Learning**: `FederatedCoordinator`/`FederatedNode`/`DifferentialPrivacy` (FedAvg/FedProx/FedMedian, ε-Differential-Privacy) implementiert und getestet (`brain/the_brain/core/federated_learning.py`, `brain/the_brain/tests/test_advanced_learning.py`), **aber in keine laufende Produktions-Pipeline eingebunden**

### Nicht implementiert
- **Formale GDPR-Zertifizierung**: Keine durchgeführt
- **Datenverschlüsselung at Rest**: Nicht implementiert
- **Automatisiertes Compliance-Dashboard**: Nicht vorhanden

> **Hinweis zur Privacy**: Die Architektur unterstützt Privacy durch die lokale Deployment-Option (Ollama) — Daten verlassen den Rechner des Users nicht. Compliance-Tooling ist implementiert (siehe oben); eine formale GDPR-Zertifizierung steht jedoch noch aus.

## Roadmap

- Phase 1 (Q2 2026): OAuth-Integration im Hauptsystem vervollständigen
- Phase 2 (Q3 2026): Unabhängiges GDPR-Compliance-Audit durchführen
- Phase 3 (Q3 2026): Automatisiertes Compliance-Reporting-Dashboard
- Phase 4 (Q4 2026): Datenverschlüsselung at Rest für alle Storage-Backends
- Phase 5 (2027): Federated-Learning-Workflows
- Phase 6 (2027): Branchenspezifische Compliance-Pakete (HIPAA, FedRAMP, ISO 27001)

## Ecosystem-Fit

Die Drei-Tier-Architektur bedient verschiedene Marktsegmente:
- **Lokal**: Unternehmen und sicherheitsbewusste Institutionen
- **Custom Endpoints**: Organisationen mit bestehender Infrastruktur
- **Cloud Services**: KMUs und Einzelpersonen mit Fokus auf Convenience

Diese Flexibilität schafft mehrere Adoptionspfade und positioniert Vibemind für regulierte Branchen (Healthcare, Finance, Government).
