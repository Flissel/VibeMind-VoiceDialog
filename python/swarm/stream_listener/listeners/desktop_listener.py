"""Desktop Space StreamListener — App automation, messaging, web, screen."""

import logging

from ..base_listener import BaseStreamListener

logger = logging.getLogger(__name__)


class DesktopStreamListener(BaseStreamListener):

    @property
    def name(self) -> str:
        return "desktop"

    @property
    def event_types_description(self) -> str:
        return """Du steuerst den Desktop, oeffnest Apps, klickst, tippst, und sendest Nachrichten.

DESKTOP-AUTOMATION:
- desktop.open_app: "Oeffne Chrome", "Starte VS Code", "Starte Spotify" → payload: {app_name: "Chrome"}
- desktop.click: "Klick auf [ELEMENT]", "Drueck auf OK" → payload: {element_description: "OK"}
- desktop.type: "Tippe [TEXT]", "Gib ein [TEXT]" → payload: {text: "..."}
- desktop.press_key: "Druecke Enter", "Strg+C", "Tab" → payload: {key: "Enter"}
- desktop.screenshot: "Screenshot", "Bildschirmfoto"
- desktop.scroll: "Scroll runter", "Scroll hoch"
- desktop.task: "Geh auf YouTube und spiele..." → payload: {task_description: "..."}

TASK MANAGEMENT:
- desktop.task.create: "Erstelle Aufgabe [NAME]" → payload: {title: "..."}
- desktop.task.list: "Zeig meine Aufgaben"

MOIRE VISION:
- desktop.moire.scan: "Scanne den Bildschirm"
- desktop.moire.find: "Finde [ELEMENT]" → payload: {element_description: "..."}

MESSAGING:
- messaging.send: "Schreib meiner Mutter dass ich spaeter komme", "Sende an Peter: ..." → payload: {recipient: "...", message: "...", platform: "auto"}
- messaging.whatsapp: "Schicke WhatsApp an Max: Hallo" → payload: {recipient: "Max", message: "Hallo"}
- messaging.telegram: "Telegram an @user: Text"
- messaging.read: "Gibt es neue Nachrichten?", "Was hat Mutter geschrieben?"

WEB:
- web.search: "Such im Web nach X", "Google X" → payload: {query: "X"}
- web.fetch: "Hol mir den Inhalt von [URL]" → payload: {url: "..."}

OPENCLAW:
- openclaw.status: "Clawdbot Status", "Gateway Status"
- openclaw.notifications: "Zeig meine Benachrichtigungen"

WICHTIG: Alles was mit Desktop-Steuerung, Apps oeffnen, Klicken, Tippen, Nachrichten senden, WhatsApp, Telegram, Screenshots zu tun hat ist dein Bereich. Auch "Schreib meiner Mutter" = Nachricht senden (NICHT Idee erstellen)."""
