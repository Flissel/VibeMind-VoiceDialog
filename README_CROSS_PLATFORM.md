# 🌍 MoireTracker Cross-Platform Migration

**Transform voice_dialog from Windows-only to multi-platform support!**

---

## 📖 Quick Navigation

- **Planning**: See [CROSS_PLATFORM_PREPARATION.md](CROSS_PLATFORM_PREPARATION.md) for full migration strategy
- **Status**: See [CROSS_PLATFORM_STATUS.md](CROSS_PLATFORM_STATUS.md) for current progress
- **Original**: See [CLAUDE.md](CLAUDE.md) for Windows implementation details

---

## 🎯 Goal

Enable voice_dialog + MoireTracker to run on:
- ✅ **Windows** (current)
- 🔄 **Linux** (in progress - Phase 1 complete)
- 🔄 **macOS** (in progress - Phase 1 complete)

---

## ✅ What's Been Done (Phase 1)

### IPC Abstraction Layer Created

**New Files:**
```
python/tools/
├── ipc_backend.py       # Abstract IPC interface ✅
├── ipc_factory.py       # Platform detection ✅
└── ipc_unix.py          # Unix socket client ✅
```

**Benefits:**
- Clean separation of platform code
- Easy to test on different OSes
- Future-proof for new platforms

---

## 🔄 What's Next

### Phase 1 Remaining (voice_dialog)
1. Extract Windows code into `ipc_windows.py`
2. Update `moire_client.py` to use factory pattern
3. Test on Windows (ensure no regressions)

### Phase 2 (MoireTracker C++)
1. Create C++ IPC abstraction
2. Implement Unix domain socket server
3. Build on Linux/macOS

### Phase 3 (Desktop Detection)
1. Add Tesseract OCR (cross-platform)
2. Linux: X11 tools integration
3. macOS: Accessibility API

---

## 🚀 Quick Test

**Check platform detection:**
```bash
cd python/tools
python ipc_factory.py
```

**Expected output on Windows:**
```
Platform Information:
  system: Windows
  ...
Selected IPC Backend: Windows Shared Memory IPC
```

**Expected output on Linux/macOS:**
```
Platform Information:
  system: Linux (or Darwin)
  ...
Selected IPC Backend: Unix Domain Socket IPC
```

---

## 📊 Architecture Comparison

### Before (Windows Only)
```
voice_dialog
    ↓ (Windows Shared Memory)
MoireTracker.exe
```

### After (Cross-Platform)
```
voice_dialog
    ↓ (Abstract IPC)
    ├─ Windows → Shared Memory → MoireTracker.exe
    ├─ Linux   → Unix Socket   → moire-tracker
    └─ macOS   → Unix Socket   → moire-tracker
```

---

## 💡 Key Design Decisions

### Why Unix Domain Sockets?
- Fast (in-kernel data transfer)
- Secure (filesystem permissions)
- Native Linux/macOS support
- Reliable (TCP-like semantics)

### Why Abstract Factory Pattern?
- Platform-specific code isolated
- Easy to add new platforms
- Testable (can mock backends)
- Clean codebase

---

## 📝 For Contributors

**Want to help?**

1. **Test on Linux**: Build MoireTracker with Unix socket support
2. **Test on macOS**: Verify everything works on macOS 13+
3. **Add tests**: Cross-platform integration tests
4. **Documentation**: Improve cross-platform setup guides

---

## 🎯 Timeline

| Phase | Task | ETA | Status |
|-------|------|-----|--------|
| **Phase 1** | IPC Abstraction (Python) | 2-3 days | 🟡 80% Complete |
| **Phase 2** | MoireTracker C++ (Unix) | 1-2 weeks | ⏳ Pending |
| **Phase 3** | Desktop Detection | 1-2 weeks | ⏳ Pending |
| **Phase 4** | CI/CD + Release | 1 week | ⏳ Pending |

**Total:** ~1 month for full cross-platform support

---

## 🛠️ Technical Stack

### Current (Windows)
- Windows shared memory (`mmap`)
- DirectX 11 (graphics)
- Windows.Media.Ocr (OCR)
- Visual Studio 2022 (build)

### Target (Cross-Platform)
- Unix domain sockets (Linux/macOS)
- Vulkan/OpenGL (graphics)
- Tesseract OCR (all platforms)
- CMake (build - all platforms)

---

## 📚 Documentation

- **Full Migration Guide**: [CROSS_PLATFORM_PREPARATION.md](CROSS_PLATFORM_PREPARATION.md)
- **Current Status**: [CROSS_PLATFORM_STATUS.md](CROSS_PLATFORM_STATUS.md)
- **Original Docs**: [CLAUDE.md](CLAUDE.md)
- **Implementation**: See `python/tools/ipc_*.py` files

---

## ❓ FAQ

**Q: Will Windows support break?**
A: No! Windows shared memory remains the default for Windows. The abstraction adds cross-platform without removing Windows features.

**Q: When can I use this on Linux?**
A: Python client is ready now (Phase 1). Waiting for MoireTracker C++ Unix socket server (Phase 2).

**Q: What about performance?**
A: Unix sockets are fast (in-kernel). Performance should be similar to Windows shared memory.

**Q: Can I help?**
A: Yes! See "For Contributors" section above. Test, document, or improve the code!

---

## 🎉 Benefits

1. **Wider Adoption**: Works on developer's preferred OS
2. **Better Testing**: CI/CD on Windows, Linux, macOS
3. **Community Growth**: More contributors can join
4. **Future-Proof**: Not locked into Windows
5. **Flexibility**: Deploy anywhere

---

**Ready to contribute?** Start with `CROSS_PLATFORM_PREPARATION.md`!
