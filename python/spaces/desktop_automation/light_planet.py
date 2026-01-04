"""
Light Planet Visualization

Der Licht-Planet ist das zentrale visuelle Element des Desktop Automation Space.
Seine Form ändert sich basierend auf Hand-Bewegungen des Users.

Konzept:
- Ein leuchtender Planet/Stern in der Mitte des Space
- Gravitations-Effekt zieht nahe Elemente an
- Shape morpht basierend auf Hand-Gesten
- Pulsiert rhythmisch wie ein lebender Organismus
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import math


@dataclass
class LightPlanetConfig:
    """Konfiguration für den Licht-Planeten."""
    
    # Grundeigenschaften
    radius: float = 1.5
    core_color: int = 0xffaa44  # Warmes Orange/Gold
    glow_color: int = 0xff8844  # Außenglühen
    
    # Animation
    pulsation_speed: float = 0.5  # Puls-Geschwindigkeit
    pulsation_amplitude: float = 0.1  # Puls-Stärke (0-1)
    rotation_speed: float = 0.2
    
    # Gravitations-Effekt
    gravity_enabled: bool = True
    gravity_strength: float = 1.0
    gravity_range: float = 5.0  # Reichweite des Gravitations-Effekts
    
    # Hand-Interaktion
    hand_morph_sensitivity: float = 1.0
    max_morph_deformation: float = 0.3  # Max. Verformung (0-1)
    
    # Partikel
    particle_count: int = 1000
    particle_speed: float = 0.5
    particle_color: int = 0xffcc66


@dataclass
class HandGesture:
    """Repräsentiert eine erkannte Hand-Geste."""
    gesture_type: str  # "open", "closed", "pointing", "spread"
    position: Dict[str, float]  # x, y, z
    velocity: Dict[str, float]  # Bewegungsgeschwindigkeit
    confidence: float  # 0-1


@dataclass
class PlanetMorphState:
    """Aktueller Morph-Zustand des Planeten."""
    
    # Verformung pro Achse
    deform_x: float = 0.0
    deform_y: float = 0.0
    deform_z: float = 0.0
    
    # Noise-basierte Detail-Verformung
    noise_seed: float = 0.0
    noise_scale: float = 0.5
    
    # Aktuelle Phase
    pulse_phase: float = 0.0
    
    def apply_hand_gesture(self, gesture: HandGesture, config: LightPlanetConfig):
        """
        Passe den Morph-Zustand basierend auf einer Hand-Geste an.
        
        Args:
            gesture: Die erkannte Hand-Geste
            config: Planet-Konfiguration
        """
        sensitivity = config.hand_morph_sensitivity
        max_deform = config.max_morph_deformation
        
        # Position beeinflusst Verformungsrichtung
        pos = gesture.position
        
        # Normalisiere Position auf -1 bis 1
        norm_x = max(-1, min(1, pos.get("x", 0)))
        norm_y = max(-1, min(1, pos.get("y", 0)))
        norm_z = max(-1, min(1, pos.get("z", 0)))
        
        # Berechne Verformung basierend auf Gesten-Typ
        if gesture.gesture_type == "open":
            # Offene Hand = Planet expandiert
            expansion = 0.2 * sensitivity
            self.deform_x = expansion
            self.deform_y = expansion
            self.deform_z = expansion
            
        elif gesture.gesture_type == "closed":
            # Geschlossene Hand = Planet kontrahiert
            contraction = -0.15 * sensitivity
            self.deform_x = contraction
            self.deform_y = contraction
            self.deform_z = contraction
            
        elif gesture.gesture_type == "pointing":
            # Zeigen = Planet streckt sich in Zeige-Richtung
            self.deform_x = norm_x * 0.3 * sensitivity
            self.deform_y = norm_y * 0.3 * sensitivity
            self.deform_z = 0.1 * sensitivity
            
        elif gesture.gesture_type == "spread":
            # Gespreizte Finger = Planet wird zackig
            self.noise_scale = 1.5 * sensitivity
            self.deform_x = norm_x * 0.15 * sensitivity
            self.deform_y = norm_y * 0.15 * sensitivity
        
        # Begrenze Verformung
        self.deform_x = max(-max_deform, min(max_deform, self.deform_x))
        self.deform_y = max(-max_deform, min(max_deform, self.deform_y))
        self.deform_z = max(-max_deform, min(max_deform, self.deform_z))
    
    def update(self, delta_time: float, config: LightPlanetConfig):
        """
        Aktualisiere den Zustand (wird jeden Frame aufgerufen).
        
        Args:
            delta_time: Zeit seit letztem Update in Sekunden
            config: Planet-Konfiguration
        """
        # Puls-Animation
        self.pulse_phase += delta_time * config.pulsation_speed * 2 * math.pi
        if self.pulse_phase > 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
        
        # Noise-Seed für organische Bewegung
        self.noise_seed += delta_time * 0.5
        
        # Langsames Zurückfedern zur Normalform
        decay = 0.95  # Zerfalls-Rate
        self.deform_x *= decay
        self.deform_y *= decay
        self.deform_z *= decay
        self.noise_scale = self.noise_scale * decay + 0.5 * (1 - decay)
    
    def get_current_radius(self, config: LightPlanetConfig) -> float:
        """Berechne aktuellen Radius mit Puls-Effekt."""
        pulse = math.sin(self.pulse_phase) * config.pulsation_amplitude
        avg_deform = (self.deform_x + self.deform_y + self.deform_z) / 3
        return config.radius * (1 + pulse + avg_deform)
    
    def to_shader_uniforms(self) -> Dict[str, Any]:
        """Konvertiere zu Shader-Uniforms für Three.js."""
        return {
            "u_deformX": self.deform_x,
            "u_deformY": self.deform_y,
            "u_deformZ": self.deform_z,
            "u_noiseScale": self.noise_scale,
            "u_noiseSeed": self.noise_seed,
            "u_pulsePhase": self.pulse_phase,
        }


class LightPlanetRenderer:
    """
    Platzhalter für den Three.js Licht-Planet Renderer.
    
    Wird später das WebSocket-Protokoll implementieren um
    den Planet-Zustand an die Three.js Visualisierung zu senden.
    """
    
    def __init__(self, config: Optional[LightPlanetConfig] = None):
        self.config = config or LightPlanetConfig()
        self.state = PlanetMorphState()
        self.is_running = False
        self._websocket = None
    
    async def start(self):
        """Starte den Renderer."""
        self.is_running = True
        print("[LightPlanet] Renderer gestartet (Platzhalter)")
    
    async def stop(self):
        """Stoppe den Renderer."""
        self.is_running = False
        print("[LightPlanet] Renderer gestoppt")
    
    def process_hand_gesture(self, gesture: HandGesture):
        """Verarbeite eine Hand-Geste."""
        if not self.is_running:
            return
        
        self.state.apply_hand_gesture(gesture, self.config)
        # TODO: Update an Three.js senden
    
    def update(self, delta_time: float):
        """Frame-Update."""
        if not self.is_running:
            return
        
        self.state.update(delta_time, self.config)
        # TODO: Update an Three.js senden
    
    def get_three_js_config(self) -> Dict[str, Any]:
        """
        Generiere Konfigurations-Objekt für Three.js.
        
        Returns:
            Dict mit Shader-Uniforms und Geometrie-Parametern
        """
        return {
            "geometry": {
                "type": "icosahedron",
                "radius": self.config.radius,
                "detail": 5,  # Hohe Detail-Stufe für smoothes Morphing
            },
            "material": {
                "type": "shader",
                "coreColor": self.config.core_color,
                "glowColor": self.config.glow_color,
                "transparent": True,
                "blending": "additive",
            },
            "uniforms": {
                **self.state.to_shader_uniforms(),
                "u_time": 0.0,
                "u_coreIntensity": 1.0,
                "u_glowIntensity": 0.5,
            },
            "particles": {
                "count": self.config.particle_count,
                "color": self.config.particle_color,
                "speed": self.config.particle_speed,
                "orbit_radius": self.config.radius * 1.5,
            }
        }


# Globale Instanz
_light_planet: Optional[LightPlanetRenderer] = None


def get_light_planet() -> LightPlanetRenderer:
    """Hole die globale Light Planet Instanz."""
    global _light_planet
    if _light_planet is None:
        _light_planet = LightPlanetRenderer()
    return _light_planet


__all__ = [
    "LightPlanetConfig",
    "HandGesture",
    "PlanetMorphState",
    "LightPlanetRenderer",
    "get_light_planet",
]