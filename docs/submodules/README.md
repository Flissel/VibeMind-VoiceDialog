# Submodules

VibeMind uses 6 git submodules for external dependencies. Each submodule is an independent repository integrated into the VibeMind project tree.

## Submodule Directory

| Submodule | Path | Space | Upstream | Status |
|-----------|------|-------|----------|--------|
| Coding_engine | `python/spaces/coding/Coding_engine` | Coding | [Flissel/Coding_engine](https://github.com/Flissel/Coding_engine.git) | Active |
| Automation_ui | `python/spaces/desktop/Automation_ui` | Desktop | [Flissel/Automation_ui](https://github.com/Flissel/Automation_ui.git) | Active |
| rowboat | `python/spaces/rowboat/rowboat` | Rowboat | [rowboatlabs/rowboat](https://github.com/rowboatlabs/rowboat.git) | Active |
| swe_desgine | `python/spaces/shuttles/swe_desgine` | Shuttles | [Flissel/swe_desgine](https://github.com/Flissel/swe_desgine.git) | Active |
| minibook | `external/minibook` | Minibook | [c4pt0r/minibook](https://github.com/c4pt0r/minibook.git) | Active |
| zeroclaw | `external/zeroclaw` | Research | [zeroclaw-labs/zeroclaw](https://github.com/zeroclaw-labs/zeroclaw.git) | Empty (needs init) |

## Quick Commands

### Clone with all submodules

```bash
git clone --recurse-submodules https://github.com/Flissel/VibeMind-VoiceDialog.git
```

### Initialize all submodules (after a regular clone)

```bash
git submodule update --init --recursive
```

### Initialize a specific submodule

```bash
git submodule update --init python/spaces/coding/Coding_engine
git submodule update --init python/spaces/desktop/Automation_ui
git submodule update --init python/spaces/rowboat/rowboat
git submodule update --init python/spaces/shuttles/swe_desgine
git submodule update --init external/minibook
git submodule update --init external/zeroclaw
```

### Update all submodules to latest

```bash
git submodule update --remote --merge
```

### Update a specific submodule

```bash
cd python/spaces/coding/Coding_engine && git pull origin main
```

### Check submodule status

```bash
git submodule status
```

## Submodule Locations

Submodules are stored in two locations:

1. **Space-internal** (`python/spaces/<space>/<submodule>/`) -- Submodules that are tightly coupled to a specific space.
2. **External** (`external/<submodule>/`) -- Submodules that are shared across spaces or loosely coupled.

## Individual Submodule Documentation

- [Coding Engine](coding-engine.md)
- [Automation UI](automation-ui.md)
- [Rowboat](rowboat.md)
- [SWE Design](swe-design.md)
- [Minibook](minibook.md)
- [ZeroClaw](zeroclaw.md)

## Troubleshooting

### Submodule directory is empty

Run:
```bash
git submodule update --init <path>
```

### Submodule has detached HEAD

This is normal. Submodules track specific commits, not branches. To update:
```bash
cd <submodule-path>
git checkout main
git pull
cd ../..
git add <submodule-path>
git commit -m "Update <submodule> to latest"
```

### Permission denied on submodule

Ensure you have access to the upstream repository. For private repos (Flissel/*), you need appropriate GitHub credentials.
