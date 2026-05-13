"""Force-directed auto-layout for canvas nodes in a bubble.

Runs whenever a bubble is entered. If the layout looks broken — many nodes
overlap, or many lack x/y — re-runs a Fruchterman-Reingold simulation,
applies a rect-separation pass to guarantee no two boxes overlap, and
persists the resulting positions back to canvas_nodes.

Box dimensions reflect the renderer's `.canvas-node` CSS rule
(min-width: 200, max-width: 350, height varies with content). We pick
360 x 140 to leave a small breathing gap. This means the layout is dense
without ever colliding visually.

This module is intentionally pure-Python with no Supabase/HTTP coupling —
the caller passes in a list of node dicts and an edge list, and gets back
the same dicts with `.x` and `.y` populated.
"""
from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Sequence, Tuple

logger = logging.getLogger(__name__)


# Renderer CSS bounds (see voice/electron-app/renderer/styles/canvas.css):
#   .canvas-node { min-width: 200px; max-width: 350px; }
# Plus header + content padding ~ 110-130px tall in typical use.
BOX_W = 360
BOX_H = 140
PAD_X = 30
PAD_Y = 25
MIN_DIST_X = BOX_W + PAD_X   # 390 — no horizontal overlap with this much gap
MIN_DIST_Y = BOX_H + PAD_Y   # 165


def _needs_layout(nodes: Sequence[Dict[str, Any]]) -> bool:
    """Heuristic: relayout when nodes lack positions, when many sit on top
    of each other, or when more than ~30% of pairs overlap."""
    if not nodes:
        return False
    # Any node missing x or y → relayout
    missing = sum(1 for n in nodes if not n.get("x") or not n.get("y"))
    if missing >= len(nodes) * 0.3:
        return True
    # Otherwise count overlapping pairs
    overlaps = 0
    total_pairs = 0
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            total_pairs += 1
            a_x, a_y = nodes[i].get("x") or 0, nodes[i].get("y") or 0
            b_x, b_y = nodes[j].get("x") or 0, nodes[j].get("y") or 0
            if abs(a_x - b_x) < MIN_DIST_X and abs(a_y - b_y) < MIN_DIST_Y:
                overlaps += 1
    if total_pairs == 0:
        return False
    # Even one overlap is bad UX; relayout
    return overlaps > 0


def compute_layout(
    nodes: Sequence[Dict[str, Any]],
    edges: Sequence[Tuple[str, str]],
    *,
    iterations: int = 500,
    seed: int = 42,
) -> Dict[str, Tuple[int, int]]:
    """Run force-directed simulation + rect-separation. Returns
    {node_id: (x, y)} for every node in input."""
    if not nodes:
        return {}

    rng = random.Random(seed)
    node_ids = [n["id"] for n in nodes]
    node_id_set = set(node_ids)

    # Identify cluster parents (≥2 outgoing edges to other nodes in our set)
    out_count: Dict[str, int] = {}
    parent_of: Dict[str, str] = {}
    valid_edges: List[Tuple[str, str]] = []
    for a, b in edges:
        if a in node_id_set and b in node_id_set and a != b:
            valid_edges.append((a, b))
            out_count[a] = out_count.get(a, 0) + 1
            parent_of.setdefault(b, a)
    parents = sorted(
        (nid for nid in out_count if out_count[nid] >= 2),
        key=lambda nid: -out_count[nid],
    )

    # ─── Init: parents around a circle, children near their parent ──
    positions: Dict[str, List[float]] = {}
    parent_anchors: Dict[str, Tuple[float, float]] = {}
    n_parents = max(1, len(parents))
    parent_radius = max(400.0, 80.0 * n_parents)
    for i, pid in enumerate(parents):
        ang = (i / n_parents) * 2 * math.pi - math.pi / 2
        ax, ay = math.cos(ang) * parent_radius, math.sin(ang) * parent_radius
        parent_anchors[pid] = (ax, ay)
        positions[pid] = [ax, ay]
    # Place children in a fan around their parent
    children_per_parent: Dict[str, List[str]] = {pid: [] for pid in parents}
    for child, par in parent_of.items():
        if par in children_per_parent and child not in positions:
            children_per_parent[par].append(child)
    child_radius = 320.0
    for par, children in children_per_parent.items():
        pa_x, pa_y = parent_anchors[par]
        pang = math.atan2(pa_y, pa_x)
        n = len(children)
        if n == 0:
            continue
        span = math.pi * 0.7
        start = pang - span / 2
        for k, cid in enumerate(children):
            ang = start + (k / max(1, n - 1)) * span if n > 1 else pang
            positions[cid] = [
                pa_x + math.cos(ang) * child_radius,
                pa_y + math.sin(ang) * child_radius,
            ]
    # Orphans → small random offsets near center
    for nid in node_ids:
        if nid not in positions:
            positions[nid] = [rng.uniform(-150, 150), rng.uniform(-150, 150)]

    # ─── Force-directed loop ────────────────────────────────────
    SPRING_LEN = 320.0
    REPULSION = 80000.0
    SPRING_K = 0.06
    CENTERING = 0.008
    DAMPING = 0.78
    MAX_VEL = 25.0

    velocities = {nid: [0.0, 0.0] for nid in positions}

    for _ in range(iterations):
        forces = {nid: [0.0, 0.0] for nid in positions}
        # Repulsion
        for i, a in enumerate(node_ids):
            ax, ay = positions[a]
            for b in node_ids[i + 1:]:
                bx, by = positions[b]
                dx, dy = ax - bx, ay - by
                dist_sq = dx * dx + dy * dy + 1.0
                dist = math.sqrt(dist_sq)
                f = REPULSION / dist_sq
                fx, fy = f * dx / dist, f * dy / dist
                forces[a][0] += fx; forces[a][1] += fy
                forces[b][0] -= fx; forces[b][1] -= fy
        # Spring attraction along edges
        for a, b in valid_edges:
            ax, ay = positions[a]
            bx, by = positions[b]
            dx, dy = bx - ax, by - ay
            dist = math.sqrt(dx * dx + dy * dy) + 0.1
            f = SPRING_K * (dist - SPRING_LEN)
            fx, fy = f * dx / dist, f * dy / dist
            forces[a][0] += fx; forces[a][1] += fy
            forces[b][0] -= fx; forces[b][1] -= fy
        # Centering pull
        for nid in node_ids:
            forces[nid][0] -= positions[nid][0] * CENTERING
            forces[nid][1] -= positions[nid][1] * CENTERING
        # Integrate with velocity cap
        for nid in node_ids:
            vx = (velocities[nid][0] + forces[nid][0]) * DAMPING
            vy = (velocities[nid][1] + forces[nid][1]) * DAMPING
            v = math.sqrt(vx * vx + vy * vy)
            if v > MAX_VEL:
                vx *= MAX_VEL / v
                vy *= MAX_VEL / v
            velocities[nid] = [vx, vy]
            positions[nid][0] += vx
            positions[nid][1] += vy

    # ─── Rect-separation: guarantees no overlap ─────────────────
    def overlap(p1: List[float], p2: List[float]) -> bool:
        return abs(p1[0] - p2[0]) < MIN_DIST_X and abs(p1[1] - p2[1]) < MIN_DIST_Y

    for _ in range(500):
        moved = 0
        for i, a in enumerate(node_ids):
            pa = positions[a]
            for b in node_ids[i + 1:]:
                pb = positions[b]
                if overlap(pa, pb):
                    dx = pa[0] - pb[0]
                    dy = pa[1] - pb[1]
                    ovx = MIN_DIST_X - abs(dx)
                    ovy = MIN_DIST_Y - abs(dy)
                    if ovx < ovy:
                        push = ovx * 0.55 + 2
                        s = 1 if dx >= 0 else -1
                        pa[0] += s * push
                        pb[0] -= s * push
                    else:
                        push = ovy * 0.55 + 2
                        s = 1 if dy >= 0 else -1
                        pa[1] += s * push
                        pb[1] -= s * push
                    moved += 1
        if moved == 0:
            break

    # Shift so min coords are at (100, 100) — keeps canvas pannable from origin
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    shift_x = 100 - min(xs)
    shift_y = 100 - min(ys)

    return {
        nid: (int(round(p[0] + shift_x)), int(round(p[1] + shift_y)))
        for nid, p in positions.items()
    }


def relayout_if_needed(
    nodes: Sequence[Dict[str, Any]],
    edges: Sequence[Tuple[str, str]],
) -> Dict[str, Tuple[int, int]]:
    """Convenience: only run layout when the current state is broken.
    Returns {} when layout looks fine (caller should keep existing x/y)."""
    if not _needs_layout(nodes):
        return {}
    logger.info(
        f"[auto_layout] computing layout for {len(nodes)} nodes, "
        f"{len(edges)} edges (some overlap or positions missing)"
    )
    return compute_layout(nodes, edges)
