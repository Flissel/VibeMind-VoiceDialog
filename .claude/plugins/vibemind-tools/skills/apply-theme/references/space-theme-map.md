# VibeMind Space Theme Map

Each space has a unique visual identity rooted in its 3D entry point. The theme system bridges the Three.js multiverse (shader colors, materials, glow) with the flat UI (CSS variables, glassmorphism panels, dashboard tokens).

## Design Philosophy

**Warm + Spacy + Loveable + Computer-Game Feel**

- Deep space backgrounds with warm nebula tones (not cold black)
- Each space is a "planet" with its own atmosphere color bleeding into the UI
- Glassmorphism panels pick up the space's accent as a subtle tint
- Glow effects, particle hints, and soft pulsation create life
- Rounded corners, pill shapes, and friendly typography
- Status indicators use game-style pips and badges, not corporate dots

## Space Definitions

### Ideas Universe (Rachel)
- **3D**: Blue glowing planet with simplex noise deformation, fresnel rim
- **Hex**: `0x4488ff` | **CSS**: `--space-ideas: #4488ff`
- **Atmosphere**: Dreamy blue nebula, soft starfield
- **UI Tint**: Cool blue glassmorphism, cyan highlights
- **Mood**: Calm creativity, floating thoughts

### Project Space (Sofia)
- **3D**: DNA helix, cyan-to-magenta gradient twist
- **Hex**: `0x44ff88` | **CSS**: `--space-projects: #44ff88`
- **Atmosphere**: Bioluminescent green, organic glow
- **UI Tint**: Emerald glassmorphism, mint highlights
- **Mood**: Growth, evolution, living code

### Desktop Automation (Adam)
- **3D**: Golden light planet, warm star
- **Hex**: `0xff8844` | **CSS**: `--space-desktop: #ff8844`
- **Atmosphere**: Warm amber nebula, sunset tones
- **UI Tint**: Amber glassmorphism, golden highlights
- **Mood**: Warm workshop, crafting tools

### Rowboat (Knowledge Navigator)
- **3D**: Boat on water, procedural geometry
- **Hex**: `0x22ccaa` | **CSS**: `--space-roarboot: #22ccaa`
- **Atmosphere**: Teal ocean mist, bioluminescent sea
- **UI Tint**: Aqua glassmorphism, seafoam highlights
- **Mood**: Exploration, calm waters, discovery

### SWE Design Factory
- **3D**: Factory structure, industrial
- **Hex**: `0xff6633` | **CSS**: `--space-swedesign: #ff6633`
- **Atmosphere**: Forge fire orange-red, sparks
- **UI Tint**: Warm coral glassmorphism, ember highlights
- **Mood**: Building, forging, precision craft

### Dashboard (ClawPort)
- **3D**: Purple crystal/orb
- **Hex**: `0x8866ff` | **CSS**: `--space-clawport: #8866ff`
- **Atmosphere**: Deep violet nebula, crystal reflections
- **UI Tint**: Violet glassmorphism, amethyst highlights
- **Mood**: Command center, overview, control

### Agent Farm
- **3D**: Barn with windmill, colored animals
- **Hex**: `0x88aa44` | **CSS**: `--space-agentfarm: #88aa44`
- **Atmosphere**: Pastoral olive-green, warm meadow
- **UI Tint**: Sage glassmorphism, leafy highlights
- **Mood**: Nurturing, organic teamwork, harvest

### The Brain
- **3D**: Neural structure, pink-magenta glow
- **Hex**: `0xff66aa` | **CSS**: `--space-thebrain: #ff66aa`
- **Atmosphere**: Neural pink nebula, synaptic flashes
- **UI Tint**: Rose glassmorphism, magenta highlights
- **Mood**: Intelligence, connections, cognition

## CSS Token Structure

```css
:root {
  /* === VibeMind Warm Space Palette === */

  /* Global warm base (replaces cold #000000) */
  --vm-bg-deep:          #0a0812;      /* warm near-black with purple undertone */
  --vm-bg-mid:           #12101e;      /* slightly lifted */
  --vm-bg-surface:       rgba(20, 18, 32, 0.92);  /* glassmorphism base */
  --vm-bg-elevated:      rgba(30, 27, 48, 0.88);
  --vm-glow-spread:      40px;

  /* Per-space accent tokens */
  --space-ideas:         #4488ff;
  --space-projects:      #44ff88;
  --space-desktop:       #ff8844;
  --space-roarboot:      #22ccaa;
  --space-swedesign:     #ff6633;
  --space-clawport:      #8866ff;
  --space-agentfarm:     #88aa44;
  --space-thebrain:      #ff66aa;

  /* Active space (set dynamically via JS) */
  --space-accent:        var(--space-ideas);       /* default */
  --space-accent-soft:   rgba(var(--space-accent-rgb), 0.15);
  --space-accent-glow:   rgba(var(--space-accent-rgb), 0.25);
  --space-accent-text:   rgba(var(--space-accent-rgb), 0.90);

  /* Game-style UI tokens */
  --vm-panel-bg:         rgba(16, 14, 28, 0.85);
  --vm-panel-border:     rgba(var(--space-accent-rgb), 0.20);
  --vm-panel-glow:       0 0 var(--vm-glow-spread) rgba(var(--space-accent-rgb), 0.08);
  --vm-pill-bg:          rgba(var(--space-accent-rgb), 0.12);
  --vm-pill-text:        rgba(var(--space-accent-rgb), 0.85);

  /* Warm text layers (replaces cold white) */
  --vm-text-primary:     #f0e8ff;       /* warm white with lavender tint */
  --vm-text-secondary:   rgba(230, 220, 245, 0.65);
  --vm-text-muted:       rgba(200, 190, 220, 0.40);

  /* Status (game-style, saturated) */
  --vm-status-ok:        #5eff8a;
  --vm-status-warn:      #ffc145;
  --vm-status-error:     #ff5a6e;
  --vm-status-info:      #6eb8ff;
}
```

## Dynamic Space Switching

When the user navigates to a space, JavaScript sets the active accent:

```javascript
// In multiverse.js navigateToSpace()
function applySpaceTheme(spaceKey) {
  const colors = {
    ideas:     { rgb: '68,136,255',  hex: '#4488ff' },
    projects:  { rgb: '68,255,136',  hex: '#44ff88' },
    desktop:   { rgb: '255,136,68',  hex: '#ff8844' },
    roarboot:  { rgb: '34,204,170',  hex: '#22ccaa' },
    swedesign: { rgb: '255,102,51',  hex: '#ff6633' },
    clawport:  { rgb: '136,102,255', hex: '#8866ff' },
    agentfarm: { rgb: '136,170,68',  hex: '#88aa44' },
    thebrain:  { rgb: '255,102,170', hex: '#ff66aa' },
  };
  const c = colors[spaceKey] || colors.ideas;
  document.documentElement.style.setProperty('--space-accent', c.hex);
  document.documentElement.style.setProperty('--space-accent-rgb', c.rgb);
}
```

## File Targets

| Layer | File | What to change |
|-------|------|---------------|
| 3D Renderer | `electron-app/renderer/multiverse.js` | Space color defs (lines 44-109), shader uniforms, scene fog/background |
| Renderer CSS | `electron-app/renderer/styles.css` | All `rgba(20,25,40,...)` backgrounds, border colors, glows, space tabs |
| Dashboard Tokens | `electron-app/dashboard/src/styles/globals.css` | `:root` block, `--bg`, `--accent`, system colors |
| Agent Status | `electron-app/dashboard/src/features/AgentStatus.tsx` | `AGENT_META` colors (lines 7-16) |
| Schedule Status | `electron-app/dashboard/src/features/ScheduleMonitor.tsx` | `STATUS_COLORS` |
| AgentFarm CSS | `electron-app/agentfarm/src/styles/globals.css` | Same token set as Dashboard |
| Renderer HTML | `electron-app/renderer/index.html` | Any inline styles |
