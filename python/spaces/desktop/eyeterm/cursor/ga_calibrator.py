"""GeneticCalibrator — evolve the 2x3 affine calibration matrix using click samples.

The genetic algorithm optimises the 6 parameters of the affine matrix
that maps normalised gaze coordinates to screen pixels:

    [sx_x, sx_y, tx]     screen_x = sx_x * gaze_x + sx_y * gaze_y + tx
    [sy_x, sy_y, ty]     screen_y = sy_x * gaze_x + sy_y * gaze_y + ty

Fitness is the negative mean Euclidean residual across all collected
click samples (lower residual = higher fitness).

The GA runs in a background thread so it never blocks the gaze loop.
When a better calibration is found, it is offered to the headless
controller via a thread-safe callback.
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("eyeterm.ga_calibrator")

CALIBRATION_DIR = Path(os.getenv("EYETERM_DATA_DIR", ""))
if not CALIBRATION_DIR.name:
    CALIBRATION_DIR = Path.home() / ".eyeterm"


@dataclass
class ClickPair:
    """A single (gaze_input → actual_click) observation."""
    gaze_x: float   # normalised gaze ratio fed into GazeToScreen
    gaze_y: float
    click_x: int     # actual screen pixel where user clicked
    click_y: int


@dataclass
class _Individual:
    """One candidate calibration matrix (6 genes)."""
    genes: np.ndarray  # shape (6,)
    fitness: float = float("-inf")

    @property
    def matrix(self) -> np.ndarray:
        """Return the 2x3 affine matrix."""
        return self.genes.reshape(2, 3)


class GeneticCalibrator:
    """Evolve the affine calibration matrix from implicit click samples.

    Parameters
    ----------
    screen_w, screen_h : int
        Screen dimensions in pixels.
    pop_size : int
        Population size (default 80).
    elite_frac : float
        Fraction of population preserved as elites (default 0.15).
    mutation_rate : float
        Probability of mutating each gene (default 0.25).
    mutation_scale : float
        Std-dev of Gaussian mutation as fraction of gene magnitude (default 0.08).
    crossover_rate : float
        Probability of uniform crossover per gene (default 0.5).
    min_samples : int
        Minimum click samples before GA starts evolving (default 8).
    evolve_interval : float
        Seconds between evolution cycles (default 2.0).
    improvement_threshold : float
        Minimum improvement (px) to accept new calibration (default 5.0).
    """

    def __init__(
        self,
        screen_w: int = 1920,
        screen_h: int = 1080,
        pop_size: int = 80,
        elite_frac: float = 0.15,
        mutation_rate: float = 0.25,
        mutation_scale: float = 0.08,
        crossover_rate: float = 0.5,
        min_samples: int = 8,
        evolve_interval: float = 2.0,
        improvement_threshold: float = 5.0,
    ) -> None:
        self._sw = screen_w
        self._sh = screen_h
        self._pop_size = pop_size
        self._elite_count = max(2, int(pop_size * elite_frac))
        self._mutation_rate = mutation_rate
        self._mutation_scale = mutation_scale
        self._crossover_rate = crossover_rate
        self._min_samples = min_samples
        self._evolve_interval = evolve_interval
        self._improvement_threshold = improvement_threshold

        # Thread-safe sample buffer
        self._lock = threading.Lock()
        self._samples: List[ClickPair] = []
        self._max_samples = 500

        # Population
        self._population: List[_Individual] = []
        self._best: Optional[_Individual] = None
        self._generation = 0
        self._applied_fitness = float("-inf")

        # Callback when a better calibration is found
        self._on_improved: Optional[Callable[[np.ndarray, float], None]] = None

        # Background thread
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Sample collection (called from gaze tick thread)
    # ------------------------------------------------------------------

    def add_sample(self, gaze_x: float, gaze_y: float, click_x: int, click_y: int) -> None:
        """Add a click observation. Thread-safe."""
        with self._lock:
            self._samples.append(ClickPair(gaze_x, gaze_y, click_x, click_y))
            if len(self._samples) > self._max_samples:
                # Keep the most recent samples
                self._samples = self._samples[-self._max_samples:]

    @property
    def sample_count(self) -> int:
        with self._lock:
            return len(self._samples)

    # ------------------------------------------------------------------
    # Fitness evaluation
    # ------------------------------------------------------------------

    def _evaluate(self, ind: _Individual, samples: List[ClickPair]) -> float:
        """Compute fitness = negative mean residual in pixels."""
        mat = ind.matrix  # (2, 3)
        total = 0.0
        for s in samples:
            vec = np.array([s.gaze_x, s.gaze_y, 1.0])
            mapped = mat @ vec
            dx = mapped[0] - s.click_x
            dy = mapped[1] - s.click_y
            total += math.hypot(dx, dy)
        mean_residual = total / len(samples)
        return -mean_residual  # higher fitness = lower residual

    # ------------------------------------------------------------------
    # Population initialisation
    # ------------------------------------------------------------------

    def _init_population(self) -> None:
        """Create initial population seeded around a sensible default."""
        self._population = []

        # Seed 1: identity-like mapping (gaze 0..1 → screen 0..W/H)
        default_genes = np.array([
            self._sw, 0.0, 0.0,   # screen_x = sw * gaze_x + 0
            0.0, self._sh, 0.0,   # screen_y = sh * gaze_y + 0
        ], dtype=np.float64)
        self._population.append(_Individual(genes=default_genes.copy()))

        # Seed 2: typical webcam range (gaze ~0.2-0.8 → full screen)
        # This means: screen_x = sw/(0.8-0.2) * (gaze_x - 0.2) = sw/0.6 * gaze_x - sw*0.2/0.6
        rx, ry = 0.6, 0.5
        range_genes = np.array([
            self._sw / rx, 0.0, -self._sw * 0.2 / rx,
            0.0, self._sh / ry, -self._sh * 0.25 / ry,
        ], dtype=np.float64)
        self._population.append(_Individual(genes=range_genes.copy()))

        # Seed 3: load previously saved best if exists
        saved = self._load_best()
        if saved is not None:
            self._population.append(_Individual(genes=saved.flatten().copy()))

        # Fill rest with random variations around the seeds
        while len(self._population) < self._pop_size:
            base = random.choice(self._population[:3] if saved else self._population[:2])
            noise = np.random.normal(0, 0.1, size=6) * np.abs(base.genes).clip(1.0)
            child = _Individual(genes=base.genes + noise)
            self._population.append(child)

        logger.info("GA population initialized: %d individuals", len(self._population))

    # ------------------------------------------------------------------
    # Genetic operators
    # ------------------------------------------------------------------

    def _select_parent(self, ranked: List[_Individual]) -> _Individual:
        """Tournament selection (size 3)."""
        contestants = random.sample(ranked, min(3, len(ranked)))
        return max(contestants, key=lambda i: i.fitness)

    def _crossover(self, p1: _Individual, p2: _Individual) -> _Individual:
        """Uniform crossover."""
        child_genes = np.empty(6, dtype=np.float64)
        for i in range(6):
            if random.random() < self._crossover_rate:
                child_genes[i] = p1.genes[i]
            else:
                child_genes[i] = p2.genes[i]
        return _Individual(genes=child_genes)

    def _mutate(self, ind: _Individual) -> None:
        """Gaussian mutation with adaptive scale."""
        for i in range(6):
            if random.random() < self._mutation_rate:
                scale = max(abs(ind.genes[i]) * self._mutation_scale, 1.0)
                ind.genes[i] += random.gauss(0, scale)

    # ------------------------------------------------------------------
    # Evolution cycle
    # ------------------------------------------------------------------

    def _evolve_one_generation(self, samples: List[ClickPair]) -> None:
        """Run one generation of the GA."""
        # Evaluate fitness
        for ind in self._population:
            ind.fitness = self._evaluate(ind, samples)

        # Sort by fitness (best first)
        self._population.sort(key=lambda i: i.fitness, reverse=True)

        # Track best
        if self._best is None or self._population[0].fitness > self._best.fitness:
            self._best = _Individual(
                genes=self._population[0].genes.copy(),
                fitness=self._population[0].fitness,
            )

        # Elitism: keep top individuals
        new_pop = [_Individual(genes=ind.genes.copy(), fitness=ind.fitness)
                   for ind in self._population[:self._elite_count]]

        # Fill rest via crossover + mutation
        while len(new_pop) < self._pop_size:
            p1 = self._select_parent(self._population)
            p2 = self._select_parent(self._population)
            child = self._crossover(p1, p2)
            self._mutate(child)
            new_pop.append(child)

        self._population = new_pop
        self._generation += 1

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def start(self, on_improved: Optional[Callable[[np.ndarray, float], None]] = None) -> None:
        """Start the background evolution thread.

        Args:
            on_improved: Callback ``(matrix_2x3, mean_residual_px)`` called
                         when a significantly better calibration is found.
        """
        if self._running:
            return
        self._on_improved = on_improved
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="GA-Calibrator",
            daemon=True,
        )
        self._thread.start()
        logger.info("GeneticCalibrator started")

    def stop(self) -> None:
        """Stop the background thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("GeneticCalibrator stopped (gen=%d)", self._generation)

    def _run_loop(self) -> None:
        """Main evolution loop (runs in background thread)."""
        self._init_population()

        while self._running:
            # Wait for enough samples
            with self._lock:
                n = len(self._samples)
                samples_snapshot = list(self._samples) if n >= self._min_samples else []

            if not samples_snapshot:
                time.sleep(self._evolve_interval)
                continue

            # Run one generation
            self._evolve_one_generation(samples_snapshot)

            # Check if we found a significant improvement
            if self._best is not None:
                best_residual = -self._best.fitness  # convert back to positive px
                applied_residual = -self._applied_fitness if self._applied_fitness > float("-inf") else float("inf")
                improvement = applied_residual - best_residual

                if improvement >= self._improvement_threshold or self._applied_fitness == float("-inf"):
                    self._applied_fitness = self._best.fitness
                    matrix = self._best.matrix.copy()

                    logger.info(
                        "GA gen=%d: new best residual=%.1fpx (improved %.1fpx), applying calibration",
                        self._generation, best_residual, improvement,
                    )
                    self._save_best(matrix)

                    if self._on_improved:
                        try:
                            self._on_improved(matrix, best_residual)
                        except Exception as e:
                            logger.error("on_improved callback failed: %s", e)

            # Log progress periodically
            if self._generation % 25 == 0 and self._best:
                logger.info(
                    "GA gen=%d samples=%d best_residual=%.1fpx",
                    self._generation, len(samples_snapshot), -self._best.fitness,
                )

            time.sleep(self._evolve_interval)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_best(self, matrix: np.ndarray) -> None:
        """Save the best calibration matrix to disk."""
        try:
            CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
            path = CALIBRATION_DIR / "ga_calibration.json"
            data = {
                "matrix": matrix.tolist(),
                "generation": self._generation,
                "fitness": float(self._best.fitness) if self._best else 0,
                "sample_count": self.sample_count,
                "timestamp": time.time(),
            }
            path.write_text(json.dumps(data, indent=2))
            logger.debug("Saved GA calibration to %s", path)
        except Exception as e:
            logger.warning("Failed to save GA calibration: %s", e)

    def _load_best(self) -> Optional[np.ndarray]:
        """Load previously saved best calibration matrix."""
        try:
            path = CALIBRATION_DIR / "ga_calibration.json"
            if path.exists():
                data = json.loads(path.read_text())
                matrix = np.array(data["matrix"], dtype=np.float64)
                if matrix.shape == (2, 3):
                    logger.info(
                        "Loaded saved GA calibration (gen=%d, residual=%.1fpx)",
                        data.get("generation", 0), -data.get("fitness", 0),
                    )
                    return matrix
        except Exception as e:
            logger.warning("Failed to load GA calibration: %s", e)
        return None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def best_residual(self) -> Optional[float]:
        if self._best is None:
            return None
        return -self._best.fitness

    @property
    def is_running(self) -> bool:
        return self._running

    def status(self) -> dict:
        """Return current GA status for debugging / UI."""
        return {
            "running": self._running,
            "generation": self._generation,
            "samples": self.sample_count,
            "best_residual_px": round(-self._best.fitness, 1) if self._best else None,
            "applied_residual_px": round(-self._applied_fitness, 1) if self._applied_fitness > float("-inf") else None,
        }
