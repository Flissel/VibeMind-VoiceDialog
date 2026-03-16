# eyeTerm Pixel-Precise Gaze Control

## Problem

eyeTerm's cursor control is too imprecise for desktop interaction. Current state:
- ~10px mean X-axis jitter after all smoothing
- Affine calibration matrix amplifies noise (narrow gaze range -> large coefficients)
- No continuous learning -- calibration degrades with any head/camera movement
- No way to measure or gate on accuracy

**Target:** +-5-10px accuracy, sufficient for clicking buttons and UI elements.

## Design: Hybrid Polynomial + Click-Learning

### Architecture

```
Frame -> GazeEstimator -> GazeFusion -> OneEuro Smooth
                                          |
                                   PolynomialMapper      <- Initial 9-point calibration
                                          |
                                    ResidualGrid          <- Click-learning (continuous)
                                          |
                                   ScreenSmoother         <- OneEuro post-mapping
                                          |
                                   AccuracyGate           <- 75% threshold
                                          |
                                   CursorDriver           <- ON only when AccuracyGate.ready AND CursorDriver.enabled

Parallel:  ClickCollector (WH_MOUSE_LL Hook + message pump thread)
              |
           Compute residual -> Update grid -> Check accuracy -> Switch phase
```

### Component 1: PolynomialMapper

Replaces the current affine matrix (2x3, linear) with a quadratic polynomial (2x6).

**Feature vector:** `[gx^2, gy^2, gx*gy, gx, gy, 1]`

```
screen_x = a . feature_vector    (6 coefficients)
screen_y = b . feature_vector    (6 coefficients)
```

X and Y are fitted independently -- each axis has 6 parameters solved from 9 equations, giving 3 degrees of freedom for residual estimation per axis.

Captures non-linearity of the eye-to-screen mapping, especially at screen edges where affine fails.

**Fitting:** Same 9-point calibration, `np.linalg.lstsq` with 6 features instead of 3. Ridge regularization (Tikhonov) prevents large quadratic coefficients when the gaze range is narrow:

```python
def fit(self, gaze_points, screen_targets, ridge_lambda=0.01):
    A = np.array([self.feature_vector(g[0], g[1]) for g in gaze_points])
    B = np.array(screen_targets)
    # Ridge regression: (A^T A + lambda*I) x = A^T B
    AtA = A.T @ A + ridge_lambda * np.eye(A.shape[1])
    AtB = A.T @ B
    solution = np.linalg.solve(AtA, AtB)
    self._coeff = solution.T.copy()  # (2, 6)
    # Condition number check -- fall back to affine if ill-conditioned
    cond = np.linalg.cond(AtA)
    if cond > 1e6:
        logger.warning("Polynomial fit ill-conditioned (cond=%e), falling back to affine", cond)
        return self._fit_affine_fallback(gaze_points, screen_targets)
    return self._coeff
```

**Persistence:** Coefficients saved to `config/eyeterm_calibration.json` with a `"type"` field:

```json
{"type": "polynomial", "matrix": [[...6 values...], [...6 values...]]}
```

Legacy files without `"type"` field are treated as affine (2x3).

**File:** `python/spaces/desktop/eyeterm/vision/polynomial_mapper.py`

```python
class PolynomialMapper:
    """Quadratic polynomial gaze-to-screen mapping.

    Handles both polynomial (2x6) and legacy affine (2x3) matrices.
    """

    def __init__(self, coefficients: Optional[np.ndarray] = None):
        self._coeff = coefficients  # shape (2, 6) or (2, 3)

    @staticmethod
    def feature_vector(gx: float, gy: float) -> np.ndarray:
        return np.array([gx*gx, gy*gy, gx*gy, gx, gy, 1.0])

    def predict(self, gx: float, gy: float) -> Tuple[float, float]:
        if self._coeff is None:
            raise RuntimeError("No calibration loaded")
        if self._coeff.shape == (2, 6):
            fv = self.feature_vector(gx, gy)
        else:  # (2, 3) affine legacy
            fv = np.array([gx, gy, 1.0])
        mapped = self._coeff @ fv
        return (mapped[0], mapped[1])

    def fit(self, gaze_points, screen_targets, ridge_lambda=0.01): ...
    def _fit_affine_fallback(self, gaze_points, screen_targets): ...

    @classmethod
    def load(cls, path) -> 'PolynomialMapper':
        """Load from JSON, auto-detecting polynomial vs affine."""
        raw = json.loads(path.read_text())
        m = np.array(raw["matrix"], dtype=np.float64)
        # Accept both (2,3) affine and (2,6) polynomial
        if m.shape not in ((2, 3), (2, 6)):
            raise ValueError(f"Unexpected matrix shape {m.shape}")
        return cls(coefficients=m)

    def save(self, path): ...
```

### Component 2: ClickCollector

Captures all mouse clicks system-wide via Windows low-level mouse hook.

**Critical: Windows message pump requirement.** `WH_MOUSE_LL` hooks are dispatched via the thread's message queue. The hook thread MUST run a `GetMessageW` loop or callbacks will never fire. The callback must return within ~300ms (Windows `LowLevelHooksTimeout`) or the hook is silently removed.

**Thread safety:** Prediction data is shared between the eyeTerm tick thread and the hook thread. To avoid torn reads, the prediction is packed into a single immutable tuple and assigned atomically:

```python
# Tick thread (write):
self._prediction = (x, y, valid, time.time())  # single atomic assignment

# Hook thread (read):
pred = self._prediction  # single atomic read
px, py, valid, t = pred
```

**Implementation:**

```python
class ClickCollector:
    """System-wide mouse click collector for implicit calibration.

    Uses WH_MOUSE_LL with a proper Windows message pump thread.
    """

    WH_MOUSE_LL = 14
    WM_LBUTTONDOWN = 0x0201
    WM_QUIT = 0x0012

    def __init__(self, buffer_size: int = 500, max_residual_px: int = 500, max_age_ms: int = 200):
        self._buffer: deque = deque(maxlen=buffer_size)
        self._max_residual = max_residual_px
        self._max_age = max_age_ms / 1000.0
        # Thread-safe prediction: single tuple, atomic assignment
        self._prediction: Tuple[int, int, bool, float] = (0, 0, False, 0.0)
        self._hook = None
        self._thread = None
        self._thread_id = None

    def update_prediction(self, x: int, y: int, valid: bool):
        """Called each frame from _tick(). Atomic tuple assignment."""
        self._prediction = (x, y, valid, time.time())

    def start(self):
        self._thread = threading.Thread(target=self._run_hook, daemon=True, name="click-collector")
        self._thread.start()

    def _run_hook(self):
        """Hook thread with Windows message pump."""
        import ctypes
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        @ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_long, ctypes.POINTER(ctypes.c_long))
        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and wParam == self.WM_LBUTTONDOWN:
                # lParam points to MSLLHOOKSTRUCT: first two fields are x, y
                click_x = lParam[0]
                click_y = lParam[1]
                # Atomic read of prediction
                px, py, valid, t = self._prediction
                age = time.time() - t
                if valid and age < self._max_age:
                    residual = math.hypot(click_x - px, click_y - py)
                    if residual < self._max_residual:
                        self._buffer.append(ClickSample(
                            timestamp=time.time(),
                            click_x=click_x, click_y=click_y,
                            predicted_x=px, predicted_y=py,
                            residual_px=residual,
                        ))
            return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        self._hook = user32.SetWindowsHookExW(self.WH_MOUSE_LL, hook_proc, None, 0)
        # Message pump -- required for WH_MOUSE_LL to fire
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        # Cleanup after WM_QUIT
        user32.UnhookWindowsHookEx(self._hook)

    def stop(self):
        """Post WM_QUIT to break the message pump, then join."""
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, self.WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=3)

    def get_recent(self, n: int) -> List:
        """Return the most recent n click samples (thread-safe via deque)."""
        return list(self._buffer)[-n:]
```

**Hook callback rules:** No file I/O, no locks, no blocking. Only append to the lock-free deque. CSV logging happens from the main tick loop by draining the buffer periodically.

**File:** `python/spaces/desktop/eyeterm/cursor/click_collector.py`

### Component 3: ResidualGrid

5x5 grid over the screen. Each cell stores a correction vector `(dx, dy)`.

**Update (on each valid click):**
```python
cell = grid_cell(predicted_x, predicted_y)
residual = (click_x - predicted_x, click_y - predicted_y)
grid[cell].dx = EMA(grid[cell].dx, residual[0], alpha=0.3)
grid[cell].dy = EMA(grid[cell].dy, residual[1], alpha=0.3)
grid[cell].count += 1
```

**Application (each frame):**
```python
raw = polynomial.predict(gaze_x, gaze_y)
correction = grid.interpolate(raw[0], raw[1])  # bilinear between 4 nearest cells
final = (raw[0] + correction[0], raw[1] + correction[1])
```

**Bilinear interpolation** between the 4 nearest cell centers prevents jumps at cell boundaries.

**Correction cap:** Grid corrections are capped at half the cell size (~192px for 1920/5). If a cell's correction exceeds this, it indicates the polynomial itself is poor. Log a warning and cap the correction. Large corrections should not paper over a bad polynomial fit.

**Minimum samples:** A cell is only active when it has >= 3 clicks. Otherwise polynomial-only.

**Persistence:** Grid saved alongside polynomial coefficients in `eyeterm_calibration.json`.

**File:** `python/spaces/desktop/eyeterm/cursor/residual_grid.py`

```python
class ResidualGrid:
    """Local correction grid for polynomial residuals."""

    def __init__(self, screen_w: int, screen_h: int, grid_size: int = 5):
        self._sw = screen_w
        self._sh = screen_h
        self._gs = grid_size
        self._cell_w = screen_w / grid_size
        self._cell_h = screen_h / grid_size
        self._max_correction = min(self._cell_w, self._cell_h) / 2
        self._dx = np.zeros((grid_size, grid_size))
        self._dy = np.zeros((grid_size, grid_size))
        self._count = np.zeros((grid_size, grid_size), dtype=int)

    def update(self, predicted_x, predicted_y, click_x, click_y, alpha=0.3): ...
    def interpolate(self, screen_x, screen_y) -> Tuple[float, float]: ...
    def reset(self): ...  # Clear all corrections (on drift)
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> 'ResidualGrid': ...
```

### Component 4: AccuracyGate

Controls cursor activation based on measured prediction accuracy.

**Three phases:**

| Phase | Cursor | Entry Condition | Behavior |
|-------|--------|-----------------|----------|
| `learning` | OFF | Startup / drift | Collects click-GT, updates polynomial + grid |
| `ready` | ON | accuracy >= 75% | Cursor active, continues collecting + learning |
| `degraded` | OFF | accuracy < 50% | Drift detected, grid reset, back to learning |

**Cursor precedence:** Cursor moves only when `accuracy_gate.cursor_enabled AND cursor_driver.enabled`. Manual toggle (`toggle_cursor()`) only takes effect when AccuracyGate is in `ready` phase.

**Resolution-independent thresholds:** All pixel thresholds are expressed as fractions of screen diagonal, then converted to pixels at init:

```python
def __init__(self, screen_w, screen_h, threshold_on=0.75, threshold_off=0.50,
             accuracy_radius_frac=0.05, min_clicks=20):
    diag = math.hypot(screen_w, screen_h)
    self._radius = int(accuracy_radius_frac * diag)  # ~110px at 1080p, ~220px at 4K
```

Default `accuracy_radius_frac=0.05` = 5% of screen diagonal. This scales correctly across resolutions.

**File:** `python/spaces/desktop/eyeterm/cursor/accuracy_gate.py`

### Component 5: CSV Click-Learning Log

Separate from the existing frame CSV. One row per click, persists across the whole session.

**Written from the main tick loop** (not from the hook callback) by periodically draining new samples from the ClickCollector buffer. This avoids file I/O in the time-critical hook callback.

**File:** `logs/eyeterm_click_learning.csv`

**Columns:**
```
timestamp, click_x, click_y, predicted_x, predicted_y,
residual_px, accuracy_20, phase, grid_cell_x, grid_cell_y
```

### Drift Detection

Monitors sliding window of last 10 clicks. Uses resolution-independent threshold: if mean residual jumps above `drift_threshold_frac * screen_diagonal` (default 7% = ~154px at 1080p):
- Phase switches to `degraded`
- ResidualGrid is reset (local corrections are now wrong)
- PolynomialMapper is kept (still provides rough orientation)
- Log: `[eyeTerm] Drift detected -- re-learning`

### Configuration

New params in `CursorConfig` / `GazeConfig`:

```python
# AccuracyGate
accuracy_threshold: float = 0.75       # EYETERM_ACCURACY_THRESHOLD
accuracy_off_threshold: float = 0.50   # EYETERM_ACCURACY_OFF
accuracy_radius_frac: float = 0.05     # EYETERM_ACCURACY_RADIUS_FRAC (fraction of screen diagonal)
drift_threshold_frac: float = 0.07     # EYETERM_DRIFT_THRESHOLD_FRAC

# ResidualGrid
grid_size: int = 5                     # EYETERM_GRID_SIZE

# ClickCollector
click_buffer_size: int = 500           # EYETERM_CLICK_BUFFER
click_max_age_ms: int = 200            # EYETERM_CLICK_MAX_AGE
click_max_residual_frac: float = 0.25  # EYETERM_CLICK_MAX_RESIDUAL_FRAC (fraction of diagonal)

# Polynomial
poly_ridge_lambda: float = 0.01       # EYETERM_POLY_RIDGE_LAMBDA
```

### File Summary

| File | Type | Purpose |
|------|------|---------|
| `eyeterm/vision/polynomial_mapper.py` | NEW | Quadratic polynomial mapping + ridge fit + persist |
| `eyeterm/cursor/click_collector.py` | NEW | Windows mouse hook + message pump + ring buffer |
| `eyeterm/cursor/residual_grid.py` | NEW | 5x5 correction grid with bilinear interpolation |
| `eyeterm/cursor/accuracy_gate.py` | NEW | Phase management (learning/ready/degraded) |
| `eyeterm/cursor/__init__.py` | MODIFY | Add lazy imports for new modules |
| `eyeterm/headless.py` | MODIFY | Wire new pipeline, start/stop click collector, CSV |
| `eyeterm/vision/calibrate.py` | MODIFY | Use PolynomialMapper instead of affine lstsq |
| `eyeterm/config.py` | MODIFY | New config params + env vars |

### Cleanup

`ClickCollector.stop()` MUST be called in `EyeTermHeadless._cleanup()` to unhook the Windows hook and stop the message pump thread. Failure to do so leaks the hook and can cause access violations on process exit.

### Verification

1. Start eyeTerm -> phase = `learning`, cursor OFF
2. Use mouse normally for 1-2 minutes
3. CSV shows residuals decreasing over time
4. After ~20 clicks with <5% diagonal residual -> phase switches to `ready`
5. Cursor activates, follows gaze with +-5-10px precision
6. Move laptop -> residuals spike -> phase = `degraded` -> cursor OFF -> re-learns
7. After re-learning -> `ready` again
8. Restart app -> persisted calibration loaded -> fast re-learn (grid already populated)
