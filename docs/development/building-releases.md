# Building Releases

## Electron Builds

### Windows (NSIS Installer)

```bash
cd electron-app
npm run build:win
# Output: electron-app/dist/VibeMind Setup X.X.X.exe
```

### macOS (DMG)

```bash
cd electron-app
npm run build:mac
# Output: electron-app/dist/VibeMind-X.X.X.dmg
```

### Linux (AppImage)

```bash
cd electron-app
npm run build:linux
# Output: electron-app/dist/VibeMind-X.X.X.AppImage
```

## What Gets Bundled

The Electron build includes:
- `electron-app/` — all JS, HTML, CSS
- `python/` — entire Python backend (excluding `__pycache__`, `.pyc`)
- `rowboat-renderer/` — Rowboat UI if built

Configured in `electron-app/package.json` under `build.extraResources`.

## Version Bumping

1. Update `VERSION` file in repo root
2. Update `electron-app/package.json` version
3. Update `CHANGELOG.md` with release notes
4. Tag: `git tag v1.x.x && git push --tags`

## Release Checklist

- [ ] All tests pass
- [ ] CHANGELOG.md updated
- [ ] VERSION file updated
- [ ] package.json version matches
- [ ] No secrets in codebase
- [ ] Builds succeed on target platforms
- [ ] Git tag created
- [ ] GitHub Release with notes and artifacts
