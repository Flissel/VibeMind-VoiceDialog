"""
OpenRouter Client - Unified LLM API für verschiedene Modelle

Unterstützt:
- claude-sonnet-4 (Reasoning/Planning + Vision)
- gemini-2.0-flash (Schnelle Vision Alternative)
- claude-3.5-sonnet (Quick Actions)

Portiert von MoireTracker v2 für VibeMind Integration.
"""

import asyncio
import aiohttp
import json
import base64
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum

# Load .env from VibeMind python directory
try:
    from dotenv import load_dotenv
    # Try multiple paths for .env
    env_paths = [
        Path(__file__).parent.parent.parent / '.env',  # python/.env
        Path(__file__).parent.parent.parent.parent / '.env',  # project root/.env
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            logging.getLogger(__name__).info(f"Loaded .env from {env_path}")
            break
except ImportError:
    pass  # dotenv not installed, rely on system environment variables

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Verfügbare Modelle via OpenRouter."""
    REASONING = "anthropic/claude-sonnet-4"  # Beste Qualität für Planung
    VISION = "anthropic/claude-sonnet-4"  # Claude Sonnet 4 hat exzellente Vision
    VISION_FAST = "google/gemini-2.0-flash-exp:free"  # Schnelle kostenlose Alternative
    QUICK = "anthropic/claude-3.5-sonnet"  # Schnell für einfache Aufgaben


@dataclass
class LLMResponse:
    """Antwort vom LLM."""
    content: str
    model: str
    usage: Dict[str, int]
    raw_response: Optional[Dict[str, Any]] = None


class OpenRouterClient:
    """
    OpenRouter Client für LLM-Aufrufe.
    
    Verwendet OpenRouter API für Zugriff auf verschiedene Modelle:
    - Claude Sonnet 4 für Reasoning
    - GPT-4o für Vision
    - Claude 3.5 Sonnet für schnelle Aktionen
    """
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            logger.warning("No OPENROUTER_API_KEY found - LLM calls will fail")
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
        self._total_tokens = 0
    
    async def _ensure_session(self):
        """Erstellt Session wenn nötig."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://vibemind.local",
                    "X-Title": "VibeMind MoireTracker Agent System"
                }
            )
    
    async def close(self):
        """Schließt die Session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Union[ModelType, str] = ModelType.REASONING,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_mode: bool = False
    ) -> LLMResponse:
        """
        Sendet Chat-Anfrage an OpenRouter.
        """
        if not self.api_key:
            raise ValueError("No API key configured")
        
        await self._ensure_session()
        
        model_name = model.value if isinstance(model, ModelType) else model
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        try:
            async with self.session.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload
            ) as response:
                self._request_count += 1
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenRouter error {response.status}: {error_text}")
                    raise Exception(f"OpenRouter API error: {response.status} - {error_text}")
                
                data = await response.json()
                
                content = data['choices'][0]['message']['content'] or ""
                usage = data.get('usage', {})
                self._total_tokens += usage.get('total_tokens', 0)
                
                return LLMResponse(
                    content=content,
                    model=model_name,
                    usage=usage,
                    raw_response=data
                )
        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error: {e}")
            raise
    
    async def chat_with_vision(
        self,
        prompt: str,
        image_data: Union[str, bytes],
        image_base64: Optional[str] = None,
        model: Union[ModelType, str] = ModelType.VISION,
        system_prompt: Optional[str] = None,
        json_mode: bool = False
    ) -> LLMResponse:
        """
        Sendet Chat mit Bild an OpenRouter.
        """
        # Verwende image_base64 wenn image_data nicht bytes ist
        if image_base64 and not isinstance(image_data, bytes):
            image_data = image_base64
        
        # Konvertiere Bytes zu Base64 wenn nötig
        if isinstance(image_data, bytes):
            image_b64 = base64.b64encode(image_data).decode('utf-8')
        else:
            image_b64 = image_data
        
        # Entferne Data-URL-Präfix wenn vorhanden
        if image_b64.startswith('data:'):
            image_b64 = image_b64.split(',')[1]
        
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        model_name = model.value if isinstance(model, ModelType) else model
        
        # Claude verwendet anderes Format für Bilder als OpenAI
        if "anthropic" in model_name or "claude" in model_name.lower():
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            })
        else:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                            "detail": "high"
                        }
                    }
                ]
            })
        
        return await self.chat(messages, model=model, json_mode=json_mode)
        
    async def plan_actions(
        self,
        goal: str,
        screen_state: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Plant Aktionen für ein Ziel basierend auf Screen-State.
        """
        system_prompt = """Du bist ein UI-Automation Experte. Analysiere das Ziel und den Bildschirmzustand.
Erstelle einen präzisen Aktionsplan als JSON-Array.

Verfügbare Aktionen:
- press_key: Taste drücken (key: "win", "enter", "tab", "escape", etc.)
- type: Text eingeben (text: "...")
- click: Klick auf Position (x, y) oder Element-Beschreibung
- wait: Warten (duration: Sekunden)
- verify: Überprüfen ob Bedingung erfüllt (condition: "...")

Antworte NUR mit einem JSON-Array:
[
  {"action": "press_key", "key": "win", "description": "Windows-Taste drücken"},
  {"action": "wait", "duration": 0.5, "description": "Warten auf Startmenü"},
  ...
]"""

        history_text = ""
        if history:
            history_text = f"\n\nBisherige Aktionen:\n{json.dumps(history, indent=2)}"

        user_prompt = f"""Ziel: {goal}

Bildschirmzustand:
{json.dumps(screen_state, indent=2, ensure_ascii=False)[:3000]}
{history_text}

Erstelle den Aktionsplan als JSON-Array:"""

        response = await self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=ModelType.REASONING,
            temperature=0.2,
            json_mode=True
        )
        
        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            actions = json.loads(content)
            
            if isinstance(actions, dict) and 'actions' in actions:
                actions = actions['actions']
            
            if not isinstance(actions, list):
                logger.error(f"Invalid action plan format: {type(actions)}")
                return []
            
            return actions
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse action plan: {e}\nResponse: {response.content}")
            return []
    
    async def analyze_screenshot(
        self,
        screenshot: Union[str, bytes],
        query: str = "Beschreibe alle UI-Elemente die du siehst"
    ) -> Dict[str, Any]:
        """
        Analysiert einen Screenshot mit GPT-4o.
        """
        system_prompt = """Du bist ein UI-Analyse-Experte. Analysiere den Screenshot präzise.
Identifiziere alle interaktiven Elemente (Buttons, Eingabefelder, Icons, Links).
Beschreibe deren Position (oben/unten/links/rechts/mitte) und mögliche Aktionen.

Antworte als JSON:
{
  "analysis": "Kurze Beschreibung der Szene",
  "elements": [
    {"type": "button", "text": "...", "position": "...", "action": "..."},
    ...
  ],
  "suggestions": ["Mögliche nächste Aktionen..."]
}"""

        response = await self.chat_with_vision(
            prompt=query,
            image_data=screenshot,
            model=ModelType.VISION,
            system_prompt=system_prompt
        )
        
        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            
            return json.loads(content)
        except:
            return {
                "analysis": response.content,
                "elements": [],
                "suggestions": []
            }
    
    async def validate_action_result(
        self,
        action: Dict[str, Any],
        before_screenshot: Union[str, bytes],
        after_screenshot: Union[str, bytes],
        expected_change: str
    ) -> Dict[str, Any]:
        """
        Validiert ob eine Aktion das erwartete Ergebnis hatte.
        """
        prompt = f"""Vergleiche diese zwei Screenshots (vorher/nachher).

Ausgeführte Aktion: {json.dumps(action)}
Erwartete Veränderung: {expected_change}

Analysiere:
1. Hat sich der Bildschirm verändert?
2. Entspricht die Veränderung der Erwartung?
3. War die Aktion erfolgreich?

Antworte als JSON:
{{"success": true/false, "confidence": 0.0-1.0, "description": "..."}}"""

        response = await self.chat_with_vision(
            prompt=prompt,
            image_data=after_screenshot,
            model=ModelType.VISION
        )
        
        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except:
            return {
                "success": True,
                "confidence": 0.5,
                "description": response.content
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Gibt Nutzungsstatistiken zurück."""
        return {
            "request_count": self._request_count,
            "total_tokens": self._total_tokens
        }


# Singleton
_client_instance: Optional[OpenRouterClient] = None


def get_openrouter_client(api_key: Optional[str] = None) -> OpenRouterClient:
    """Gibt Singleton-Instanz des OpenRouter Clients zurück."""
    global _client_instance
    if _client_instance is None:
        _client_instance = OpenRouterClient(api_key)
    return _client_instance


async def cleanup_openrouter():
    """Schließt den OpenRouter Client."""
    global _client_instance
    if _client_instance:
        await _client_instance.close()
        _client_instance = None