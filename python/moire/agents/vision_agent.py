"""
Vision Agent - Analysiert Screenshots mit Multi-Modal Vision

Verantwortlich für:
- Screenshot-Analyse bei Hard Cases (niedrige OCR-Qualität)
- Element-Erkennung basierend auf Vision
- UI-Element Lokalisierung mit gpt-4o/Claude

Portiert von MoireTracker v2 für VibeMind Integration.
"""

import logging
import asyncio
import base64
from io import BytesIO
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

# Optional imports
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Import OpenRouter client from same package
try:
    from ..core.openrouter_client import OpenRouterClient, get_openrouter_client
    HAS_OPENROUTER = True
except ImportError:
    HAS_OPENROUTER = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class VisionAnalysisResult:
    """Ergebnis der Vision-Analyse."""
    success: bool
    description: str
    detected_elements: List[Dict[str, Any]]
    suggested_actions: List[Dict[str, Any]]
    raw_response: Optional[str] = None
    error: Optional[str] = None
    
    def to_context(self) -> str:
        """Erzeugt Kontext-String für andere Agents."""
        if not self.success:
            return f"Vision-Analyse fehlgeschlagen: {self.error}"
        
        lines = [
            "=== Vision-Analyse Ergebnis ===",
            "",
            self.description,
            "",
            "Erkannte Elemente:",
        ]
        
        for elem in self.detected_elements[:15]:
            elem_type = elem.get('type', 'unknown')
            text = elem.get('text', '')
            location = elem.get('location', 'unbekannt')
            lines.append(f"  • [{elem_type}] {text} @ {location}")
        
        if self.suggested_actions:
            lines.append("")
            lines.append("Vorgeschlagene Aktionen:")
            for action in self.suggested_actions[:5]:
                lines.append(f"  → {action.get('description', 'Unbekannt')}")
        
        return "\n".join(lines)


@dataclass
class ElementLocation:
    """Ergebnis der Element-Lokalisierung."""
    found: bool
    x: int
    y: int
    confidence: float
    description: str
    element_type: str
    error: Optional[str] = None


class VisionAnalystAgent:
    """
    Vision Agent für Multi-Modal Screenshot-Analyse.
    
    Verwendet gpt-4o/Claude via OpenRouter für:
    - Analyse von Screenshots bei niedriger OCR-Qualität
    - Erkennung von UI-Elementen die OCR nicht erfassen konnte
    - Kontextuelle Beschreibung des Bildschirminhalts
    - Lokalisierung von UI-Elementen anhand von Beschreibungen
    """
    
    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4",
        max_tokens: int = 2000
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.openrouter_client: Optional[OpenRouterClient] = None
        
        # Initialize OpenRouter client
        if HAS_OPENROUTER:
            try:
                self.openrouter_client = get_openrouter_client()
                logger.info(f"Vision Agent initialized with OpenRouter ({self.model})")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter: {e}")
    
    def is_available(self) -> bool:
        """Prüft ob Vision-Analyse verfügbar ist."""
        return self.openrouter_client is not None and HAS_PIL
    
    async def find_element(
        self,
        image: 'PILImage.Image',
        element_description: str,
        context: str = ""
    ) -> ElementLocation:
        """
        Findet ein UI-Element anhand einer Beschreibung.
        
        Args:
            image: PIL Image des Screenshots
            element_description: Beschreibung des gesuchten Elements
            context: Zusätzlicher Kontext
        
        Returns:
            ElementLocation mit Koordinaten oder Fehler
        """
        if not self.is_available():
            return ElementLocation(
                found=False,
                x=0, y=0,
                confidence=0,
                description="",
                element_type="unknown",
                error="Vision not available"
            )
        
        try:
            # Resize image if needed
            max_size = 1568
            original_size = image.size
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, PILImage.Resampling.LANCZOS)
            
            # Convert to base64
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Build prompt
            prompt = f"""Analysiere diesen Screenshot und finde das folgende UI-Element:

GESUCHTES ELEMENT: {element_description}
{f"KONTEXT: {context}" if context else ""}

WICHTIG: Gib die EXAKTEN Pixel-Koordinaten zurück, wo ein Benutzer klicken sollte.

Das Bild hat die Dimensionen: {image.size[0]}x{image.size[1]} Pixel

Antworte NUR im folgenden JSON-Format:
{{
    "found": true/false,
    "x": <X-Koordinate des Klickpunkts>,
    "y": <Y-Koordinate des Klickpunkts>,
    "confidence": <Konfidenz 0.0-1.0>,
    "element_type": "<button/link/textfield/icon/menu/checkbox/other>",
    "description": "<kurze Beschreibung was gefunden wurde>"
}}

Wenn das Element NICHT gefunden wird:
{{
    "found": false,
    "x": 0,
    "y": 0,
    "confidence": 0,
    "element_type": "unknown",
    "description": "Element nicht gefunden: <Grund>"
}}"""

            response = await self.openrouter_client.chat_with_vision(
                prompt=prompt,
                image_base64=base64_image,
                json_mode=True
            )
            
            if response and response.content:
                import json
                try:
                    result = json.loads(response.content)
                    
                    # Scale coordinates back if image was resized
                    x = result.get('x', 0)
                    y = result.get('y', 0)
                    
                    if max(original_size) > max_size:
                        scale = original_size[0] / image.size[0]
                        x = int(x * scale)
                        y = int(y * scale)
                    
                    return ElementLocation(
                        found=result.get('found', False),
                        x=x,
                        y=y,
                        confidence=result.get('confidence', 0),
                        description=result.get('description', ''),
                        element_type=result.get('element_type', 'unknown')
                    )
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse vision response: {response.content[:200]}")
            
            return ElementLocation(
                found=False,
                x=0, y=0,
                confidence=0,
                description="",
                element_type="unknown",
                error="No valid response from vision model"
            )
        
        except Exception as e:
            logger.error(f"find_element failed: {e}")
            return ElementLocation(
                found=False,
                x=0, y=0,
                confidence=0,
                description="",
                element_type="unknown",
                error=str(e)
            )
    
    async def find_element_from_screenshot(
        self,
        screenshot_bytes: bytes,
        element_description: str,
        context: str = ""
    ) -> ElementLocation:
        """
        Convenience-Methode: Findet Element direkt aus Screenshot-Bytes.
        """
        if not HAS_PIL:
            return ElementLocation(
                found=False, x=0, y=0, confidence=0,
                description="", element_type="unknown",
                error="PIL not available"
            )
        
        try:
            image = PILImage.open(BytesIO(screenshot_bytes))
            return await self.find_element(image, element_description, context)
        except Exception as e:
            return ElementLocation(
                found=False, x=0, y=0, confidence=0,
                description="", element_type="unknown",
                error=f"Failed to load image: {e}"
            )
    
    async def analyze_screen_for_task(
        self,
        image: 'PILImage.Image',
        task_description: str
    ) -> Dict[str, Any]:
        """
        Analysiert Screen für einen bestimmten Task.
        
        Returns:
            Dict mit suggested_action, target_element, alternative_actions
        """
        if not self.is_available():
            return {"error": "Vision not available"}
        
        try:
            # Resize if needed
            max_size = 1568
            original_size = image.size
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, PILImage.Resampling.LANCZOS)
            
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            prompt = f"""Analysiere diesen Screenshot und bestimme die beste Aktion für folgende Aufgabe:

AUFGABE: {task_description}

Bildgröße: {image.size[0]}x{image.size[1]} Pixel

Antworte als JSON:
{{
    "current_state": "<Was ist aktuell auf dem Bildschirm zu sehen>",
    "suggested_action": {{
        "type": "<click/type/press_key/scroll/wait>",
        "x": <X-Koordinate falls click>,
        "y": <Y-Koordinate falls click>,
        "text": "<Text falls type>",
        "key": "<Taste falls press_key>",
        "description": "<Beschreibung der Aktion>"
    }},
    "target_element": {{
        "description": "<Was wird angeklickt/interagiert>",
        "element_type": "<button/textfield/link/icon/etc>",
        "confidence": <0.0-1.0>
    }},
    "alternative_actions": [
        {{
            "type": "<Aktionstyp>",
            "description": "<Alternative Aktion>"
        }}
    ],
    "task_completable": true/false,
    "reason": "<Warum task_completable true/false>"
}}"""

            response = await self.openrouter_client.chat_with_vision(
                prompt=prompt,
                image_base64=base64_image,
                json_mode=True
            )
            
            if response and response.content:
                import json
                try:
                    result = json.loads(response.content)
                    
                    # Scale coordinates back
                    if 'suggested_action' in result and 'x' in result['suggested_action']:
                        if max(original_size) > max_size:
                            scale = original_size[0] / image.size[0]
                            result['suggested_action']['x'] = int(result['suggested_action']['x'] * scale)
                            result['suggested_action']['y'] = int(result['suggested_action']['y'] * scale)
                    
                    return result
                except json.JSONDecodeError:
                    pass
            
            return {"error": "No valid response from vision model"}
        
        except Exception as e:
            logger.error(f"analyze_screen_for_task failed: {e}")
            return {"error": str(e)}
    
    async def analyze_screenshot(
        self,
        image: 'PILImage.Image',
        context: str = "",
        focus_area: Optional[Dict[str, int]] = None
    ) -> VisionAnalysisResult:
        """
        Analysiert einen Screenshot mit Vision.
        """
        if not self.is_available():
            return VisionAnalysisResult(
                success=False,
                description="",
                detected_elements=[],
                suggested_actions=[],
                error="Vision not available (OpenRouter or PIL missing)"
            )
        
        try:
            # Crop to focus area if specified
            if focus_area:
                image = image.crop((
                    focus_area['x'],
                    focus_area['y'],
                    focus_area['x'] + focus_area['width'],
                    focus_area['y'] + focus_area['height']
                ))
            
            # Resize large images
            max_size = 1568
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, PILImage.Resampling.LANCZOS)
            
            # Convert to base64
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Build prompt
            prompt = self._build_analysis_prompt(context)
            
            response = await self.openrouter_client.chat_with_vision(
                prompt=prompt,
                image_base64=base64_image
            )
            
            if response and response.content:
                return self._parse_vision_response(response.content)
            
            return VisionAnalysisResult(
                success=False,
                description="",
                detected_elements=[],
                suggested_actions=[],
                error="No response from vision model"
            )
        
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return VisionAnalysisResult(
                success=False,
                description="",
                detected_elements=[],
                suggested_actions=[],
                error=str(e)
            )
    
    def _build_analysis_prompt(self, context: str) -> str:
        """Erstellt den Analyse-Prompt."""
        prompt = """Analysiere diesen Desktop-Screenshot für UI-Automation.

Bitte identifiziere und beschreibe:

1. **Anwendung/Fenster**: Welche Anwendung ist zu sehen?

2. **UI-Elemente**: Liste alle sichtbaren UI-Elemente auf:
   - Buttons (mit Text wenn vorhanden)
   - Menüs und Menüpunkte
   - Textfelder und Eingabefelder
   - Icons und deren wahrscheinliche Funktion

3. **Texte**: Alle lesbaren Texte im Bild

4. **Aktionen**: Welche Aktionen sind möglich?

5. **Fokus**: Was ist aktuell im Fokus oder aktiv?

Formatiere die Antwort strukturiert."""

        if context:
            prompt += f"\n\nKontext: {context}"
        
        return prompt
    
    def _parse_vision_response(self, response: str) -> VisionAnalysisResult:
        """Parst die Vision-Antwort."""
        detected_elements = []
        suggested_actions = []
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line_lower = line.lower().strip()
            
            if 'button' in line_lower or 'schaltfläche' in line_lower:
                current_section = 'button'
            elif 'menü' in line_lower or 'menu' in line_lower:
                current_section = 'menu'
            elif 'textfeld' in line_lower or 'eingabe' in line_lower:
                current_section = 'input'
            elif 'icon' in line_lower:
                current_section = 'icon'
            elif 'aktion' in line_lower or 'action' in line_lower:
                current_section = 'action'
            
            if line.strip().startswith('-') or line.strip().startswith('•'):
                item_text = line.strip().lstrip('-•').strip()
                
                if current_section == 'action':
                    suggested_actions.append({
                        'description': item_text,
                        'confidence': 0.7
                    })
                elif current_section:
                    detected_elements.append({
                        'type': current_section,
                        'text': item_text,
                        'location': 'from vision',
                        'confidence': 0.7
                    })
        
        return VisionAnalysisResult(
            success=True,
            description=response[:500],
            detected_elements=detected_elements,
            suggested_actions=suggested_actions,
            raw_response=response
        )


# Singleton
_vision_agent_instance: Optional[VisionAnalystAgent] = None


def get_vision_agent() -> VisionAnalystAgent:
    """Gibt Singleton-Instanz des Vision Agents zurück."""
    global _vision_agent_instance
    if _vision_agent_instance is None:
        _vision_agent_instance = VisionAnalystAgent()
    return _vision_agent_instance


def reset_vision_agent():
    """Setzt Vision Agent zurück."""
    global _vision_agent_instance
    _vision_agent_instance = None