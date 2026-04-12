"""Create E-Ticketing test bubble with 7 child ideas for evaluation testing."""
import sys, os, uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.supabase_database import Database

db = Database()
gen_id = lambda: uuid.uuid4().hex[:8]

parent_id = gen_id()
db.execute(
    "INSERT INTO ideas (id, title, description, source, created_at, score, status, parent_id, tags, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (
        parent_id,
        "E-Ticketing Deutschland",
        "Mobiles Ticketing-System fuer den deutschen OEPNV. Account-basiertes System mit QR/NFC-Validierung, GDPR-konform, cloud-skaliert. Ziel: Nationwide Deployment mit sicherer Zahlung und Offline-Faehigkeit.",
        "text",
        datetime.now().isoformat(),
        0.0,
        "raw",
        None,
        "[]",
        "{}",
    ),
)
print(f"Created parent bubble: {parent_id}")

children = [
    {
        "title": "Legal & Regulatory Framework (GDPR/DSGVO)",
        "description": (
            "Deutschlands GDPR (DSGVO) und nationale Datenschutzgesetze regeln jedes E-Ticketing streng. "
            "Nur die minimal notwendigen personenbezogenen Daten duerfen erhoben werden (Datenminimierung).\n\n"
            "Rechtliche Grundlage: Art.6(1)(b) DSGVO - Vertragserfuellung fuer Buchungs- und Zahlungsdaten.\n"
            "Aufbewahrungsfristen: 10 Jahre fuer Rechnungen (deutsches Steuerrecht), 3 Jahre fuer Betrugspraevention.\n"
            "GPS-Tracking: Besonders sensibel - Standortdaten sind personenbezogene Daten, erfordern Zweckbindung, Einwilligung, Transparenz und Sicherheit.\n"
            "DSFA erforderlich: Data Protection Impact Assessment bei grossflaechigem GPS-Tracking.\n\n"
            "Massnahmen: Datenverschluesselung, Nutzerrechte (Auskunft, Loeschung), keine Speicherung ueber gesetzliche Pflicht hinaus.\n"
            "Zahlungsregulierung: PSD2/SCA Compliance, PCI-DSS fuer Kartendaten."
        ),
    },
    {
        "title": "Mobile Ticketing Architektur",
        "description": (
            "Account-basiertes Ticketing-Modell:\n"
            "- User Login via OAuth2, Kauf eines Tarifs oder Aktivierung einer Zahlungsmethode\n"
            "- Pro Fahrt: zeitlich begrenzter sicherer Token (QR-Code oder NFC-Token)\n\n"
            "Technologie: VDV MOTICS Standard - kryptographischer Kopierschutz im Barcode/NFC-Chip.\n"
            "Check-In: QR-Scan am Drehkreuz loggt Fahrtbeginn. QR enthaelt statische Geraete-ID (SCE-ID) + dynamische Signatur.\n"
            "Offline-Validierung: QR vom Backend signiert mit Ablaufzeit. Drehkreuz verifiziert Signatur ohne Live-Backend.\n"
            "App cached vorab gueltige One-Time-Tokens fuer Offline-Betrieb.\n"
            "Check-Out: Erneuter QR-Scan am Ausgang beendet Fahrt, berechnet entfernungsbasierten Tarif.\n\n"
            "Architektur: Mobile App <-> HTTPS APIs <-> Backend (Microservices/DBs) <-> Gate Controller.\n"
            "APIs: REST oder gRPC mit TLS zwischen App, Servern und Gate-Controllern.\n"
            "Prinzipien: Offline-Token-Support, kryptographisch geschuetzte Barcodes, Echtzeit Check-In/Out Logik."
        ),
    },
    {
        "title": "Security Measures",
        "description": (
            "Ticket-Sicherheit:\n"
            "- Kryptographisch signierter QR verhindert Klonen. VDV-Ansatz: QR aus sicherem Krypto-Modul, gebunden an Geraete-SCE-ID.\n"
            "- Gate-Scanner verifiziert Signatur + Geraete-ID, lehnt Kopien ab.\n"
            "- Anti-Fraud-Checks: Mehrfache gleichzeitige Nutzung einer Ticket-ID wird blockiert.\n"
            "- Gate-Systeme loggen jeden Scan-Event und blockieren Wiederverwendung.\n\n"
            "Zahlungssicherheit:\n"
            "- Zahlungsverarbeitung an PCI-DSS Level 1 zertifizierte Gateways auslagern (Stripe, PayPal).\n"
            "- Tokenisierung: App sendet Zahlungsinfos direkt an Provider, Backend nutzt nur Token.\n"
            "- Daten kommen nie mit unserem System in Kontakt.\n"
            "- GDPR-konforme Prozesse des Zahlungsanbieters nutzen.\n\n"
            "Gate/Geraetesicherheit:\n"
            "- Manipulationssichere Hardware, gehaertete Firmware, Backend-Authentifizierung.\n"
            "- Starke TLS fuer alle Kommunikation.\n"
            "- Login-Versuchsbegrenzung, sichere Passwortspeicherung, Device Attestation.\n"
            "- SCA bei Transaktionen ueber 30 EUR."
        ),
    },
    {
        "title": "Data Storage, GPS & Privacy",
        "description": (
            "Datenspeicherung:\n"
            "- Nutzerprofile (PII) in verschluesselter Datenbank mit strikten Zugriffskontrollen.\n"
            "- Fahrtdaten (Ein-/Ausstiegszeiten, Stations-IDs, Routensegmente) pseudonymisiert wo moeglich.\n"
            "- Standortdaten: System erfasst primaer 'Station X betreten um T' und 'Station Y verlassen um U'.\n\n"
            "GPS-Tracking:\n"
            "- Live-GPS fuer exakte Routen nur bei expliziter Nutzer-Einwilligung (Opt-In).\n"
            "- GDPR-Prinzipien: Zweckbindung (nur fuer Fahrt/Abrechnung), Minimierung, Transparenz, Sicherheit.\n\n"
            "Datenbankentwurf:\n"
            "- Abrechnungsdaten (bis zu 10 Jahre) getrennt von sensiblen Identitaetsdaten.\n"
            "- Encryption-at-Rest, regelmaessige Audits, Nutzerrechte (Profil loeschen bei Kuendigung).\n"
            "- Datenaufbewahrungsrichtlinien: alte Scan-Logs nach Pflichtfrist loeschen.\n"
            "- Systemzugriff loggen ohne PII preiszugeben; Reisedaten-Besitzer nur verschluesselt in Analytics."
        ),
    },
    {
        "title": "Scalability & Infrastructure",
        "description": (
            "Cloud-native Microservices-Architektur fuer landesweiten Betrieb:\n"
            "- Container-Orchestrierung (Kubernetes auf AWS/Azure/GCP) mit Auto-Scaling.\n"
            "- Globale Load-Balancer und CDNs fuer statische Inhalte.\n"
            "- Hochverfuegbare Datenbank-Cluster (Master-Master oder Master-Replica) in mehreren Zonen.\n"
            "- Caching (Redis/Memcached) fuer haeufig abgefragte Daten (Fahrplaene, aktive Tickets).\n\n"
            "Resilienz:\n"
            "- Redundante Server und Failover (Active-Active Rechenzentren).\n"
            "- Regelmaessige Backups mit geo-repliziertem Storage.\n"
            "- Graceful Degradation: lokale Drehkreuze nutzen gecachte Gueltigkeitsdaten bei Systemausfall.\n"
            "- System-Monitoring und Alerting.\n\n"
            "Gate-Hardware:\n"
            "- Netzwerk- und Stromredundanz.\n"
            "- USV (Unterbrechungsfreie Stromversorgung) an jedem Drehkreuz.\n"
            "- Industrietaugliche Geraete fuer oeffentliche Raeume."
        ),
    },
    {
        "title": "Payment Integration (PCI-DSS/PSD2)",
        "description": (
            "PCI-DSS Compliance:\n"
            "- Zahlungsverarbeitung ausschliesslich ueber PCI-DSS Level 1 zertifizierte Provider.\n"
            "- Stripe/PayPal bieten Tokenisierung: App sendet Zahlungsdaten direkt an Provider.\n"
            "- Backend erhaelt nur Payment-Token, nie Rohdaten der Karte.\n"
            "- Verschluesselung der Kartendaten durch Provider - kein Kontakt mit eigenem System.\n\n"
            "PSD2/SCA Requirements:\n"
            "- Strong Customer Authentication fuer Transaktionen ueber 30 EUR.\n"
            "- OAuth-Flows fuer Kontoverknuepfung.\n"
            "- Wiederkehrende Zahlungen nur mit GDPR-konformer Einwilligung.\n\n"
            "Integration:\n"
            "- REST API zu Payment Gateway mit TLS.\n"
            "- Webhook-basierte Benachrichtigung bei erfolgreicher/fehlgeschlagener Zahlung.\n"
            "- Audit-Trail fuer alle Transaktionen."
        ),
    },
    {
        "title": "Gate Hardware & Charging Security",
        "description": (
            "Drehkreuz-Hardware:\n"
            "- Zuverlaessige 2D-Kamera oder NFC-Reader mit verschluesselter Kommunikation zum Zentralsystem.\n"
            "- Minimierung von False Positives, Geschwindigkeitsoptimierung.\n"
            "- Bei NFC: Smartphone emuliert Secure Element.\n"
            "- Bei QR: Barcode-Display aktiv und kontraststark halten.\n\n"
            "Ladestation-Sicherheit:\n"
            "- Ladepunkte muessen reine Charging-Only Ports sein.\n"
            "- Datenleitungen deaktivieren oder USB-Data-Blocking-Kabel verwenden.\n"
            "- Schutz gegen Juice-Jacking Malware-Angriffe.\n"
            "- USB-C Ports oder Qi Wireless Pads die nur Strom liefern (keine Datenverbindung).\n"
            "- Physische Sicherung der Ladepunkte.\n\n"
            "Wartung:\n"
            "- Regelmaessige Firmware-Updates.\n"
            "- Sicherheitsreviews durchfuehren.\n"
            "- Gehaertete Firmware, Authentifizierung zum Backend, Manipulationsschutz."
        ),
    },
]

for child in children:
    child_id = gen_id()
    db.execute(
        "INSERT INTO ideas (id, title, description, source, created_at, score, status, parent_id, tags, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            child_id,
            child["title"],
            child["description"],
            "text",
            datetime.now().isoformat(),
            0.0,
            "raw",
            parent_id,
            "[]",
            "{}",
        ),
    )
    print(f"  Created: {child['title'][:50]}... ({len(child['description'])} chars)")

print(f"\nDone. Parent={parent_id}, {len(children)} children created.")
print(f"Total content: {sum(len(c['description']) for c in children)} chars")
