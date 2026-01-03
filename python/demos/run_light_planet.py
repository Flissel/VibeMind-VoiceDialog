#!/usr/bin/env python
"""
Run Light Planet Server

Startet den Desktop Automation Space mit Light Planet Visualisierung.

Usage:
    python run_light_planet.py [--no-browser] [--hand-detection]
    
Options:
    --no-browser      Browser nicht automatisch öffnen
    --hand-detection  Webcam Hand-Erkennung aktivieren
"""

import sys
import asyncio
from pathlib import Path

# Füge python/ zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent))


async def main():
    """Hauptfunktion."""
    # Argumente parsen
    open_browser = "--no-browser" not in sys.argv
    enable_hand_detection = "--hand-detection" in sys.argv
    
    # Importiere nach Pfad-Setup
    from spaces.desktop_automation.light_planet_server import get_server
    
    server = get_server()
    
    # Hand Detection starten wenn gewünscht
    if enable_hand_detection:
        print("[INFO] Hand Detection wird aktiviert...")
        # Starte in separatem Task
        asyncio.create_task(server.start_hand_detection(camera_index=0))
    
    # Server starten
    await server.run(open_browser=open_browser)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║         VIBEMIND - LIGHT PLANET SERVER                   ║
║         Desktop Automation Space                         ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[INFO] Server beendet.")
    except ImportError as e:
        print(f"\n[ERROR] Import-Fehler: {e}")
        print("[INFO] Installiere fehlende Abhängigkeiten mit:")
        print("       pip install websockets")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        raise