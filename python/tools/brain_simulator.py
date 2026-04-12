"""User-Simulator for systematic Brain training.

Reads training_variants.yml, generates variants by substituting placeholders,
and sends (text, correct_event_type) pairs to the Brain's supervised training
endpoint. Falls back to event-name heuristics for events without YAML entries.
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

def _load_event_space_map() -> dict:
    """Load EVENT_SPACE_MAP by parsing the module directly (avoids transitive imports)."""
    candidates = [
        Path(__file__).resolve().parents[3] / "brain" / "the_brain" / "core" / "space_routing_head.py",
        Path(__file__).resolve().parents[4] / "brain" / "the_brain" / "core" / "space_routing_head.py",
    ]
    for p in candidates:
        if p.exists():
            import ast
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name) and tgt.id == "EVENT_SPACE_MAP":
                            return ast.literal_eval(node.value)
    return {}


EVENT_SPACE_MAP = _load_event_space_map()


DEFAULT_VARIANTS_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "training_variants.yml"
)

_HEURISTIC_VERB_DE = {
    "create": ["Erstelle", "Mach", "Lege an", "Baue"],
    "delete": ["Loesche", "Entferne", "Weg mit"],
    "list": ["Zeig", "Liste", "Was gibts bei"],
    "status": ["Status von", "Wie steht es um", "Zeig Status"],
    "update": ["Aendere", "Update", "Modifiziere"],
    "find": ["Finde", "Such", "Wo ist"],
    "start": ["Starte", "Beginne"],
    "stop": ["Stoppe", "Halt an", "Beende"],
    "run": ["Fuehre aus", "Starte Lauf von"],
    "generate": ["Generiere", "Erzeuge", "Erstelle"],
    "activate": ["Aktiviere"],
    "deactivate": ["Deaktiviere"],
    "search": ["Suche", "Finde"],
    "show": ["Zeig", "Anzeigen"],
    "scan": ["Scanne", "Durchsuche"],
    "evaluate": ["Bewerte", "Evaluiere"],
    "predict": ["Sage voraus", "Prediction fuer"],
    "simulate": ["Simuliere"],
    "summarize": ["Fasse zusammen", "Zusammenfassung von"],
    "query": ["Frage", "Hole Info zu"],
    "modify": ["Aendere", "Modifiziere"],
    "expand": ["Erweitere"],
    "explain": ["Erklaere"],
    "connect": ["Verbinde", "Verknuepfe"],
    "recommend": ["Empfehle", "Gib Empfehlung fuer"],
    "accept": ["Akzeptiere"],
    "snooze": ["Verschiebe", "Snooze"],
    "cancel": ["Brich ab", "Canceln"],
    "send": ["Sende"],
    "read": ["Lies"],
    "click": ["Klicke"],
    "type": ["Tippe"],
    "open": ["Oeffne"],
    "screenshot": ["Screenshot von", "Screenshot"],
    "scroll": ["Scrolle"],
    "enter": ["Gehe in", "Betrete"],
    "exit": ["Verlasse", "Raus aus"],
}


def _post_json(url: str, payload: dict, timeout: float = 5.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _get_json(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


class UserSimulator:
    def __init__(
        self,
        brain_url: str = "http://localhost:5000",
        variants_path: Path | None = None,
        delay_ms: int = 10,
    ):
        self.brain_url = brain_url.rstrip("/")
        self.delay_ms = delay_ms
        path = variants_path or DEFAULT_VARIANTS_PATH
        with open(path, "r", encoding="utf-8") as f:
            self.variants = yaml.safe_load(f) or {}
        self.event_space_map = dict(EVENT_SPACE_MAP)

    def events_for_space(self, space: str) -> list[str]:
        return [ev for ev, sp in self.event_space_map.items() if sp == space]

    def all_spaces(self) -> list[str]:
        return sorted(set(self.event_space_map.values()))

    def generate_variants(self, event_type: str) -> list[str]:
        entry = self.variants.get(event_type)
        if entry and isinstance(entry, dict) and entry.get("variants"):
            return self._expand(entry["variants"], entry.get("placeholders") or {})
        return self._heuristic_variants(event_type)

    @staticmethod
    def _expand(templates: list[str], placeholders: dict[str, list[str]]) -> list[str]:
        results: list[str] = []
        for tmpl in templates:
            keys = [k for k in placeholders if "{" + k + "}" in tmpl]
            if not keys:
                results.append(tmpl)
                continue
            values_lists = [placeholders[k] for k in keys]
            for combo in _cartesian(values_lists):
                s = tmpl
                for k, v in zip(keys, combo):
                    s = s.replace("{" + k + "}", v)
                results.append(s)
        return results

    def _heuristic_variants(self, event_type: str) -> list[str]:
        parts = event_type.split(".")
        domain = parts[0]
        action = parts[-1]
        verbs = _HEURISTIC_VERB_DE.get(action, [action.capitalize()])
        noun = domain.capitalize()
        out = []
        for v in verbs:
            out.append(f"{v} {noun}")
            out.append(f"{v} die {noun}")
        out.append(f"{noun} {action}")
        out.append(f"{event_type.replace('.', ' ')}")
        return out

    def train_one(self, text: str, event_type: str) -> bool:
        try:
            r = _post_json(
                f"{self.brain_url}/api/cortex/classify/train",
                {"user_text": text, "correct_event_type": event_type},
                timeout=5.0,
            )
            return bool(r.get("ok"))
        except (urllib.error.URLError, TimeoutError, OSError):
            return False
        except Exception:
            return False

    def classify(self, text: str) -> dict:
        try:
            return _post_json(
                f"{self.brain_url}/api/cortex/classify",
                {"user_text": text},
                timeout=5.0,
            )
        except Exception as e:
            return {"error": str(e)}

    def train_space(
        self, space: str, repetitions: int = 5, verbose: bool = True
    ) -> dict[str, Any]:
        events = self.events_for_space(space)
        if not events:
            return {"space": space, "events": 0, "samples": 0}
        total_samples = 0
        per_event: dict[str, int] = {}
        t0 = time.time()
        for event in events:
            variants = self.generate_variants(event)
            sent = 0
            for variant in variants:
                for _ in range(repetitions):
                    if self.train_one(variant, event):
                        sent += 1
                        total_samples += 1
                    if self.delay_ms:
                        time.sleep(self.delay_ms / 1000.0)
            per_event[event] = sent
            if verbose:
                print(f"  [{space}] {event}: {sent} samples ({len(variants)} variants)")
        return {
            "space": space,
            "events": len(events),
            "samples": total_samples,
            "per_event": per_event,
            "duration_sec": round(time.time() - t0, 1),
        }

    def train_all(self, repetitions: int = 5) -> dict[str, Any]:
        report: dict[str, Any] = {
            "spaces": {},
            "total_samples": 0,
            "total_events": 0,
        }
        t0 = time.time()
        for space in self.all_spaces():
            r = self.train_space(space, repetitions=repetitions)
            report["spaces"][space] = r
            report["total_samples"] += r["samples"]
            report["total_events"] += r["events"]
        report["duration_sec"] = round(time.time() - t0, 1)
        return report

    def train_space_adaptive(
        self,
        space: str,
        base_reps: int = 5,
        max_reps: int = 30,
        target_accuracy: float = 0.75,
        verify_samples: int = 5,
        verbose: bool = True,
    ) -> dict[str, Any]:
        """Train each event with base_reps, measure accuracy, pump weak events.

        Weak events (< target_accuracy) get extra rounds of base_reps until
        they either pass the target or hit max_reps total.
        """
        events = self.events_for_space(space)
        if not events:
            return {"space": space, "events": 0, "samples": 0}
        total_samples = 0
        per_event: dict[str, dict[str, Any]] = {}
        t0 = time.time()

        for event in events:
            variants = self.generate_variants(event)
            reps_used = 0
            sent = 0
            accuracy = 0.0

            while reps_used < max_reps:
                chunk = min(base_reps, max_reps - reps_used)
                for variant in variants:
                    for _ in range(chunk):
                        if self.train_one(variant, event):
                            sent += 1
                            total_samples += 1
                        if self.delay_ms:
                            time.sleep(self.delay_ms / 1000.0)
                reps_used += chunk

                # Measure accuracy on verify_samples
                hits = 0
                for v in variants[:verify_samples]:
                    r = self.classify(v)
                    if (r.get("event_type") or r.get("primary_event") or "") == event:
                        hits += 1
                accuracy = hits / max(1, min(verify_samples, len(variants)))

                if accuracy >= target_accuracy:
                    break

            per_event[event] = {
                "samples": sent,
                "reps_used": reps_used,
                "accuracy": round(accuracy, 2),
                "variants": len(variants),
            }
            if verbose:
                status = "ok" if accuracy >= target_accuracy else "WEAK"
                print(
                    f"  [{space}] {event}: {sent} samples, "
                    f"reps={reps_used}, acc={accuracy:.0%} [{status}]"
                )

        return {
            "space": space,
            "events": len(events),
            "samples": total_samples,
            "per_event": per_event,
            "duration_sec": round(time.time() - t0, 1),
        }

    def validate_space(self, space: str, samples_per_event: int = 3) -> dict[str, Any]:
        events = self.events_for_space(space)
        results: dict[str, dict[str, Any]] = {}
        weak: list[str] = []
        for event in events:
            variants = self.generate_variants(event)[:samples_per_event]
            hits = 0
            confidences: list[float] = []
            for v in variants:
                r = self.classify(v)
                got = r.get("event_type") or r.get("primary_event") or ""
                conf = float(r.get("confidence", 0.0) or 0.0)
                confidences.append(conf)
                if got == event:
                    hits += 1
            total = max(1, len(variants))
            acc = hits / total
            avg_conf = sum(confidences) / max(1, len(confidences))
            results[event] = {
                "accuracy": round(acc, 2),
                "avg_confidence": round(avg_conf, 2),
                "samples": len(variants),
            }
            if acc < 0.67:
                weak.append(event)
        return {"space": space, "events": results, "weak_events": weak}

    def brain_stats(self) -> dict:
        try:
            return _get_json(f"{self.brain_url}/api/cortex/classify/stats", timeout=5.0)
        except Exception as e:
            return {"error": str(e)}


def _cartesian(lists: list[list[str]]) -> list[tuple]:
    if not lists:
        return [()]
    out = [()]
    for L in lists:
        out = [prev + (v,) for prev in out for v in L]
    return out


if __name__ == "__main__":
    sim = UserSimulator()
    print(f"Spaces: {sim.all_spaces()}")
    print(f"Total events: {len(sim.event_space_map)}")
    print(f"YAML-covered events: {len(sim.variants)}")
