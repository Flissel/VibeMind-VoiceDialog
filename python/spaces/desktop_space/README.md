# Desktop Automation Space

Platzhalter für den Desktop Automation Space im VibeMind Multiverse.

## Konzept

Der Desktop Automation Space ist ein interaktiver 3D-Raum für die Steuerung von Desktop-Operationen. Im Zentrum befindet sich ein **Licht-Planet**, dessen Form sich basierend auf Hand-Bewegungen des Users verändert.

```
                    ╭──────────────────────╮
                    │  Desktop Automation   │
                    │       Space           │
                    ╰──────────────────────╯
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        ╭──────────╮    ╭──────────╮    ╭──────────╮
        │  Hand    │    │  Licht-  │    │  Desktop │
        │  Motion  │───▶│  Planet  │───▶│  Actions │
        │Detection │    │          │    │          │
        ╰──────────╯    ╰──────────╯    ╰──────────╯
              │               │               │
              │   Webcam      │   Shape       │   System
              │   Input       │   Morphing    │   Control
```

## Module

### 1. DesktopAutomationSpace (`__init__.py`)

Haupt-Controller für den Space:
- Aktivierung/Deaktivierung
- State Management
- Action Queue

```python
from spaces.desktop_automation import get_desktop_space

space = get_desktop_space()
await space.activate()
```

### 2. LightPlanet (`light_planet.py`)

Der zentrale Licht-Planet:
- Konfigurierbare Farben und Größe
- Pulsations-Animation
- Gravitations-Effekt
- Shape-Morphing basierend auf Gesten

```python
from spaces.desktop_automation.light_planet import get_light_planet, HandGesture

planet = get_light_planet()
await planet.start()

# Geste simulieren
gesture = HandGesture(
    gesture_type="open",
    position={"x": 0.5, "y": 0.5, "z": 0},
    velocity={"x": 0, "y": 0, "z": 0},
    confidence=1.0
)
planet.process_hand_gesture(gesture)
```

### 3. HandMotion (`hand_motion.py`)

Webcam-basierte Handerkennung:
- MediaPipe Integration (geplant)
- Gesten-Erkennung
- Position Tracking
- Velocity Berechnung

```python
from spaces.desktop_automation.hand_motion import get_hand_detector, GestureType

detector = get_hand_detector()
await detector.start(camera_index=0)

# Callback für erkannte Gesten
detector.on_gesture_detected = lambda hand: print(f"Geste: {hand.gesture}")
```

## Erkannte Gesten

| Geste | Beschreibung | Planet-Effekt |
|-------|--------------|---------------|
| `OPEN_HAND` | Offene Hand | Planet expandiert |
| `CLOSED_FIST` | Geschlossene Faust | Planet kontrahiert |
| `POINTING` | Zeigefinger | Planet streckt sich |
| `SPREAD_FINGERS` | Gespreizte Finger | Planet wird zackig |
| `PINCH` | Daumen + Zeigefinger | Feinsteuerung |
| `SWIPE_*` | Wisch-Gesten | Navigation |

## Three.js Integration

Der Licht-Planet wird in Three.js als Custom Shader Mesh gerendert:

```javascript
// Shader Uniforms vom Python Backend
const uniforms = {
    u_deformX: { value: 0.0 },
    u_deformY: { value: 0.0 },
    u_deformZ: { value: 0.0 },
    u_noiseScale: { value: 0.5 },
    u_pulsePhase: { value: 0.0 },
    u_coreColor: { value: new THREE.Color(0xffaa44) },
    u_glowColor: { value: new THREE.Color(0xff8844) },
};

// Vertex Shader für Morphing
const vertexShader = `
    uniform float u_deformX;
    uniform float u_deformY;
    uniform float u_deformZ;
    uniform float u_noiseScale;
    uniform float u_pulsePhase;
    
    varying vec3 vNormal;
    varying vec3 vPosition;
    
    void main() {
        vNormal = normal;
        vPosition = position;
        
        // Deformation anwenden
        vec3 pos = position;
        pos.x *= (1.0 + u_deformX);
        pos.y *= (1.0 + u_deformY);
        pos.z *= (1.0 + u_deformZ);
        
        // Puls-Effekt
        float pulse = sin(u_pulsePhase) * 0.1;
        pos *= (1.0 + pulse);
        
        gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    }
`;
```

## Roadmap

### Phase 1: Platzhalter ✅
- [x] Space-Konfiguration
- [x] Light Planet Config
- [x] Hand Motion Interfaces
- [x] Dokumentation

### Phase 2: MediaPipe Integration
- [ ] Webcam Capture
- [ ] Hand Detection
- [ ] Landmark Extraction
- [ ] Real-time Processing

### Phase 3: Three.js Visualisierung
- [ ] Light Planet Shader
- [ ] Particle System
- [ ] Glow Effects
- [ ] Gravity Simulation

### Phase 4: Desktop Integration
- [ ] Verbindung zu externem Desktop Automation Projekt
- [ ] Action Mapping
- [ ] Feedback Loop

## Dependencies (für vollständige Implementierung)

```txt
# Hand Motion Detection
mediapipe>=0.10.0
opencv-python>=4.8.0

# WebSocket Communication
websockets>=11.0

# Async Processing
asyncio
```

## Architektur-Entscheidungen

1. **Separate Module**: Hand Detection, Planet Rendering und Desktop Actions sind entkoppelt für einfachere Wartung.

2. **Async-First**: Alle I/O-gebundenen Operationen sind asynchron für flüssige 60 FPS.

3. **State Pattern**: Der Planet-Zustand wird als eigenes Objekt verwaltet für einfaches Serialisieren an Three.js.

4. **Callback-basiert**: Event-driven Architektur ermöglicht flexible Integration.

## Verbindung zum VibeMind Multiverse

```
Ideas Space (Rachel) ◄────────────────────► Desktop Automation Space (Adam)
        │                                              │
        │                                              │
        ▼                                              ▼
   Bubbles/Ideas                               Licht-Planet
        │                                              │
        │         ┌───────────────────┐               │
        └────────►│   Alice (Hub)     │◄──────────────┘
                  │   Koordination    │
                  └───────────────────┘
```

Der Space ist erreichbar via Agent-Transfer oder direkte Navigation durch das Multiverse.