"""
Video Production Tools — Wraps vibevideo + vibevideo-deepfake CLIs.

Provides tool functions for the VideoBackendAgent to call via event routing.
Each tool delegates to the underlying CLI scripts in the submodules.
"""

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VIBEVIDEO_DIR = Path(__file__).parent.parent / "vibevideo"
DEEPFAKE_DIR = Path(__file__).parent.parent / "vibevideo_deepfake"


def _run_cli(script: Path, args: List[str], cwd: Path = None) -> Dict[str, Any]:
    """Run a CLI script and return structured result."""
    if not script.exists():
        return {"success": False, "message": f"Script not found: {script}"}

    cmd = [sys.executable, str(script)] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd or script.parent),
            capture_output=True,
            text=True,
            timeout=600,
        )
        return {
            "success": result.returncode == 0,
            "message": result.stdout.strip() if result.returncode == 0 else result.stderr.strip(),
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Command timed out (600s)"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── Team Video Pipeline ──────────────────────────────────────

def team_pipeline_status() -> Dict[str, Any]:
    """Get status of the team video pipeline (available steps, outputs)."""
    steps = ["analyze", "backgrounds", "composite", "build", "split", "final"]
    available = VIBEVIDEO_DIR.exists()
    return {
        "success": True,
        "message": "Team video pipeline status",
        "available": available,
        "steps": steps,
        "vibevideo_path": str(VIBEVIDEO_DIR),
    }


def team_run_step(step: str = "all", **kwargs) -> Dict[str, Any]:
    """Run a team video pipeline step."""
    valid = ["analyze", "backgrounds", "composite", "build", "split", "final", "all"]
    if step not in valid:
        return {"success": False, "message": f"Invalid step '{step}'. Valid: {valid}"}
    return _run_cli(VIBEVIDEO_DIR / "vibevideo.py", ["team", step], cwd=VIBEVIDEO_DIR)


# ── Vision Video (Sora AI) ───────────────────────────────────

def vision_generate(**kwargs) -> Dict[str, Any]:
    """Generate a Her-style vision video with Sora AI scenes."""
    args = ["vision", "--all"]
    if kwargs.get("generate_sora"):
        args = ["vision", "--generate-sora"]
    elif kwargs.get("generate_tts"):
        args = ["vision", "--generate-tts"]
    elif kwargs.get("build_only"):
        args = ["vision", "--build"]
    return _run_cli(VIBEVIDEO_DIR / "vibevideo.py", args, cwd=VIBEVIDEO_DIR)


# ── Product Demo ─────────────────────────────────────────────

def demo_analyze(input_file: str, target_duration: int = 60, **kwargs) -> Dict[str, Any]:
    """Analyze a screenrecording for demo video production."""
    args = ["demo", "analyze", input_file, "--target", str(target_duration)]
    return _run_cli(VIBEVIDEO_DIR / "vibevideo.py", args, cwd=VIBEVIDEO_DIR)


def demo_build(config_path: str, **kwargs) -> Dict[str, Any]:
    """Build a demo video from a scene config."""
    args = ["demo", "build", "-c", config_path]
    return _run_cli(VIBEVIDEO_DIR / "vibevideo.py", args, cwd=VIBEVIDEO_DIR)


# ── Lip Sync (Deepfake) ──────────────────────────────────────

def lipsync_run(person: str = None, **kwargs) -> Dict[str, Any]:
    """Run MuseTalk lip sync on team videos."""
    args = ["lipsync", "run"]
    if person:
        args += ["--only", person]
    return _run_cli(DEEPFAKE_DIR / "deepfake.py", args, cwd=DEEPFAKE_DIR)


def lipsync_analyze(**kwargs) -> Dict[str, Any]:
    """Run quality analysis on lip sync results."""
    return _run_cli(DEEPFAKE_DIR / "deepfake.py", ["lipsync", "analyze"], cwd=DEEPFAKE_DIR)


# ── Voice Cloning ────────────────────────────────────────────

def voice_clone(**kwargs) -> Dict[str, Any]:
    """Clone team voices via ElevenLabs."""
    return _run_cli(DEEPFAKE_DIR / "deepfake.py", ["voice", "clone"], cwd=DEEPFAKE_DIR)


def voice_tts(person: str = None, **kwargs) -> Dict[str, Any]:
    """Generate TTS voiceover per person."""
    args = ["voice", "tts"]
    if person:
        args += ["--only", person]
    return _run_cli(DEEPFAKE_DIR / "deepfake.py", args, cwd=DEEPFAKE_DIR)


# ── Status / Info ────────────────────────────────────────────

def video_status(**kwargs) -> Dict[str, Any]:
    """Get overall video space status (installed tools, submodules)."""
    vibevideo_ok = (VIBEVIDEO_DIR / "vibevideo.py").exists()
    deepfake_ok = (DEEPFAKE_DIR / "deepfake.py").exists()

    tools = []
    if vibevideo_ok:
        tools.extend(["team", "vision", "demo"])
    if deepfake_ok:
        tools.extend(["lipsync", "voice"])

    return {
        "success": True,
        "message": f"Video space: {len(tools)} tools available",
        "vibevideo_installed": vibevideo_ok,
        "deepfake_installed": deepfake_ok,
        "available_tools": tools,
    }


# ── Video Gallery (scan outputs) ────────────────────────────

def _categorize_root(filepath: Path) -> str:
    """Categorize root-level vibevideo mp4 files by name."""
    name = filepath.stem.lower()
    if "team" in name:
        return "Team"
    if "product" in name:
        return "Product"
    if "final" in name:
        return "Final"
    if "application" in name:
        return "Application"
    if "vision" in name:
        return "Vision"
    return "Other"


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def scan_video_outputs(**kwargs) -> Dict[str, Any]:
    """Scan vibevideo + vibevideo_deepfake output directories for .mp4 files."""
    videos: List[Dict[str, Any]] = []

    scan_dirs: List[tuple] = []

    if VIBEVIDEO_DIR.exists():
        scan_dirs.extend([
            (VIBEVIDEO_DIR, _categorize_root),
            (VIBEVIDEO_DIR / "lip_sync", lambda _f: "Lipsync"),
            (VIBEVIDEO_DIR / "composited", lambda _f: "Composited"),
            (VIBEVIDEO_DIR / "backgrounds", lambda _f: "Background"),
            (VIBEVIDEO_DIR / "vision", lambda _f: "Vision"),
            (VIBEVIDEO_DIR / "output", lambda _f: "Output"),
        ])

    if DEEPFAKE_DIR.exists():
        scan_dirs.extend([
            (DEEPFAKE_DIR / "lip_sync", lambda _f: "Deepfake Lipsync"),
        ])

    for directory, categorizer in scan_dirs:
        if not directory.exists():
            continue
        for mp4 in directory.glob("*.mp4"):
            if not mp4.is_file():
                continue
            stat = mp4.stat()
            videos.append({
                "path": str(mp4.resolve()),
                "filename": mp4.name,
                "size_bytes": stat.st_size,
                "size_human": _human_size(stat.st_size),
                "category": categorizer(mp4),
                "modified": stat.st_mtime,
                "modified_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    videos.sort(key=lambda v: v["modified"], reverse=True)

    return {
        "success": True,
        "message": f"Found {len(videos)} video(s)",
        "videos": videos,
    }
