---
name: apply-theme
description: This skill should be used when the user asks to "apply theme", "update styling", "fix colors", "make it warmer", "space colors", "theme the UI", "match 3D colors", "game-style UI", or mentions adjusting the visual identity of any VibeMind space. Applies the warm-spacy-loveable computer-game theme across all UI layers (3D renderer, renderer CSS, dashboard tokens, React components) with per-space accent colors that match each space's 3D entry point.
---

# Apply VibeMind Theme

Apply the warm, spacy, loveable computer-game theme to the VibeMind UI. Every space gets its own visual identity that flows from its 3D planet/object into all flat UI panels.

## Reference

Read `references/space-theme-map.md` in this skill directory FIRST. It contains the full space-to-color mapping, CSS token structure, and file targets.

## Safety Rules

- **Never delete existing CSS rules** — override or extend them
- **Preserve all existing functionality** — colors are cosmetic, never change selectors or layout
- **Keep 3D hex colors in sync** with CSS `--space-*` tokens (they are the same values)
- **Test the Electron app** after changes: `cd electron-app && npm start`

## Workflow

### 1. Read the Theme Map

```
Read: .claude/plugins/vibemind-tools/skills/apply-theme/references/space-theme-map.md
```

Understand the 8 spaces, their hex colors, moods, and which files to touch.

### 2. Assess Current State

Check which parts of the theme are already applied vs. still using old cold-black defaults:

```
Grep for: "#000000", "rgba(20, 25, 40", "rgba(20, 20, 30", "#050510", "0x4488ff"
In: electron-app/renderer/styles.css, electron-app/dashboard/src/styles/globals.css
```

Compare against the token structure in the theme map. Identify gaps.

### 3. Apply Global Warm Base (renderer/styles.css)

Replace cold backgrounds with warm space tones:

| Old Value | New Value | Purpose |
|-----------|-----------|---------|
| `#050510` | `#0a0812` | Body background — warm near-black |
| `rgba(20, 20, 30, 0.95)` | `rgba(16, 14, 28, 0.95)` | Titlebar — warmer |
| `rgba(20, 25, 40, 0.85)` | `rgba(16, 14, 28, 0.85)` | Voice panel, info panel — warm glass |
| `rgba(20, 25, 40, 0.9)` | `rgba(16, 14, 28, 0.90)` | Transcript panel — warm glass |
| `rgba(100, 150, 255, 0.3)` | `rgba(var(--space-accent-rgb, 100,150,255), 0.25)` | Border accents — space-aware |
| `linear-gradient(135deg, #0a0a15 0%, #151530 50%, #0a0a15 100%)` | `linear-gradient(135deg, #0a0812 0%, #12101e 50%, #0a0812 100%)` | App bg gradient — warm |

Add the VibeMind CSS custom properties block at the TOP of `:root` or at the top of `styles.css`:

```css
/* === VibeMind Space Theme === */
:root {
  --space-accent-rgb: 68, 136, 255;  /* default: Ideas blue */
  --space-accent: #4488ff;
  --vm-bg-deep: #0a0812;
  --vm-bg-mid: #12101e;
  --vm-bg-surface: rgba(20, 18, 32, 0.92);
  --vm-bg-elevated: rgba(30, 27, 48, 0.88);
  --vm-text-primary: #f0e8ff;
  --vm-text-secondary: rgba(230, 220, 245, 0.65);
  --vm-text-muted: rgba(200, 190, 220, 0.40);
  --vm-panel-bg: rgba(16, 14, 28, 0.85);
  --vm-panel-border: rgba(var(--space-accent-rgb), 0.20);
  --vm-glow-spread: 40px;
  --vm-status-ok: #5eff8a;
  --vm-status-warn: #ffc145;
  --vm-status-error: #ff5a6e;
  --vm-status-info: #6eb8ff;
}
```

### 4. Add Per-Space Tab Accents (renderer/styles.css)

Currently only `projects` and `swedesign` have custom tab colors. Add ALL 8 spaces:

```css
/* === Per-Space Tab Accents === */
.space-tab[data-space="ideas"].active {
  background: rgba(68, 136, 255, 0.2);
  border-color: rgba(68, 136, 255, 0.4);
  color: rgba(150, 190, 255, 1);
}
.space-tab[data-space="ideas"]:hover {
  background: rgba(68, 136, 255, 0.1);
  color: rgba(150, 190, 255, 0.9);
}

.space-tab[data-space="projects"].active {
  background: rgba(68, 255, 136, 0.2);
  border-color: rgba(68, 255, 136, 0.4);
  color: rgba(150, 255, 200, 1);
}
.space-tab[data-space="projects"]:hover {
  background: rgba(68, 255, 136, 0.1);
  color: rgba(150, 255, 200, 0.9);
}

.space-tab[data-space="desktop"].active {
  background: rgba(255, 136, 68, 0.2);
  border-color: rgba(255, 136, 68, 0.4);
  color: rgba(255, 200, 150, 1);
}
.space-tab[data-space="desktop"]:hover {
  background: rgba(255, 136, 68, 0.1);
  color: rgba(255, 200, 150, 0.9);
}

.space-tab[data-space="roarboot"].active {
  background: rgba(34, 204, 170, 0.2);
  border-color: rgba(34, 204, 170, 0.4);
  color: rgba(150, 235, 215, 1);
}
.space-tab[data-space="roarboot"]:hover {
  background: rgba(34, 204, 170, 0.1);
  color: rgba(150, 235, 215, 0.9);
}

.space-tab[data-space="swedesign"].active {
  background: rgba(255, 102, 51, 0.2);
  border-color: rgba(255, 102, 51, 0.4);
  color: rgba(255, 180, 130, 1);
}
.space-tab[data-space="swedesign"]:hover {
  background: rgba(255, 102, 51, 0.1);
  color: rgba(255, 180, 130, 0.9);
}

.space-tab[data-space="clawport"].active {
  background: rgba(136, 102, 255, 0.2);
  border-color: rgba(136, 102, 255, 0.4);
  color: rgba(190, 170, 255, 1);
}
.space-tab[data-space="clawport"]:hover {
  background: rgba(136, 102, 255, 0.1);
  color: rgba(190, 170, 255, 0.9);
}

.space-tab[data-space="agentfarm"].active {
  background: rgba(136, 170, 68, 0.2);
  border-color: rgba(136, 170, 68, 0.4);
  color: rgba(200, 225, 150, 1);
}
.space-tab[data-space="agentfarm"]:hover {
  background: rgba(136, 170, 68, 0.1);
  color: rgba(200, 225, 150, 0.9);
}

.space-tab[data-space="thebrain"].active {
  background: rgba(255, 102, 170, 0.2);
  border-color: rgba(255, 102, 170, 0.4);
  color: rgba(255, 180, 215, 1);
}
.space-tab[data-space="thebrain"]:hover {
  background: rgba(255, 102, 170, 0.1);
  color: rgba(255, 180, 215, 0.9);
}
```

### 5. Wire Dynamic Accent Switching (multiverse.js)

In the `navigateToSpace(spaceKey)` method, add the `applySpaceTheme` call so the CSS accent follows the 3D navigation:

```javascript
// Add inside navigateToSpace(), after setting this.currentSpace
const SPACE_COLORS = {
  ideas:     '68,136,255',
  projects:  '68,255,136',
  desktop:   '255,136,68',
  roarboot:  '34,204,170',
  swedesign: '255,102,51',
  clawport:  '136,102,255',
  agentfarm: '136,170,68',
  thebrain:  '255,102,170',
};
const rgb = SPACE_COLORS[spaceKey] || SPACE_COLORS.ideas;
document.documentElement.style.setProperty('--space-accent-rgb', rgb);
document.documentElement.style.setProperty('--space-accent', this.spaces[spaceKey]?.color
  ? '#' + this.spaces[spaceKey].color.toString(16).padStart(6, '0')
  : '#4488ff');
```

### 6. Update Dashboard Tokens (dashboard/src/styles/globals.css)

Replace the cold Apple Dark Mode base with the warm VibeMind palette:

| Token | Old | New |
|-------|-----|-----|
| `--bg` | `#000000` | `#0a0812` |
| `--bg-secondary` | `rgba(28,28,30,1)` | `rgba(20,18,32,1)` |
| `--bg-tertiary` | `rgba(44,44,46,1)` | `rgba(34,30,52,1)` |
| `--material-regular` | `rgba(28,28,30,0.92)` | `rgba(20,18,32,0.92)` |
| `--material-thick` | `rgba(22,22,24,0.96)` | `rgba(14,12,24,0.96)` |
| `--text-primary` | `#FFFFFF` | `#f0e8ff` |
| `--accent` | `#0A84FF` | `var(--space-accent, #4488ff)` |

Add the `--space-accent-rgb` and per-space tokens to the dashboard `:root` as well so components can reference them.

### 7. Update Agent Status Colors (AgentStatus.tsx)

Replace `AGENT_META` colors with space-matched tokens:

```typescript
const AGENT_META: Record<string, { label: string; icon: string; color: string }> = {
  bubbles:  { label: 'Bubbles',  icon: '\u{1F4AD}', color: '#4488ff' },  // Ideas blue
  ideas:    { label: 'Ideas',    icon: '\u{1F4A1}', color: '#4488ff' },  // Ideas blue
  coding:   { label: 'Coding',   icon: '\u{1F9EC}', color: '#44ff88' },  // Projects green
  desktop:  { label: 'Desktop',  icon: '\u{1F5A5}', color: '#ff8844' },  // Desktop amber
  roarboot: { label: 'Rowboat',  icon: '\u{1F6A3}', color: '#22ccaa' },  // Rowboat teal
  zeroclaw: { label: 'Research', icon: '\u{1F50D}', color: '#ff6633' },  // SWE orange
  minibook: { label: 'Minibook', icon: '\u{1F4D6}', color: '#ff66aa' },  // Brain pink
  schedule: { label: 'Schedule', icon: '\u{23F0}',  color: '#8866ff' },  // Dashboard violet
}
```

### 8. Warm Up the 3D Scene (multiverse.js)

Update the Three.js scene background and fog to use warm tones instead of cold black:

```javascript
// Scene background — warm deep space instead of cold black
this.scene.background = new THREE.Color(0x0a0812);
this.scene.fog = new THREE.FogExp2(0x0a0812, 0.015);
```

If the renderer `setClearColor` is used, update it too:
```javascript
this.renderer.setClearColor(0x0a0812);
```

### 9. Verify

After all changes:

1. **Build the dashboard**: `cd electron-app && npm run dashboard:build`
2. **Start the app**: `cd electron-app && npm start`
3. **Navigate each space** — confirm the tab, titlebar, and panel borders shift to the space accent
4. **Check the 3D scene** — background should feel warm, not cold
5. **Open ClawPort dashboard** — text should be warm lavender-white, not cold white

## Incremental Application

If applying the full theme at once is too large, apply in this order:

1. **Global warm base** (steps 3 + 8) — biggest visual impact, lowest risk
2. **Space tab accents** (step 4) — per-space identity in nav
3. **Dynamic switching** (step 5) — panels react to navigation
4. **Dashboard tokens** (step 6) — ClawPort warmth
5. **Agent colors** (step 7) — consistency with 3D
