"""One-time script: Create VibeMind Team 2025 reference project from existing videos."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.video_project_repository import VideoProjectRepository
from data.video_repository import VideoRepository
from data.supabase_database import get_database, reset_database

VIDEO_TEAM_DIR = r"C:\Users\User\Desktop\Video_Team"

def main():
    reset_database()
    proj_repo = VideoProjectRepository()
    vid_repo = VideoRepository()

    # Create the reference project
    project = proj_repo.create_project("VibeMind Team 2025", "Referenz-Projekt mit dem originalen Team")
    pid = project["id"]
    print(f"Created project: {pid}")

    # Read analysis.json for person data
    analysis_path = os.path.join(VIDEO_TEAM_DIR, "analysis.json")
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    for entry in analysis:
        name = entry["name"]
        role = entry.get("role", "")
        voice_id = entry.get("voice_id", "")
        raw_path = os.path.join(VIDEO_TEAM_DIR, "data", f"{name}.mp4")

        proj_repo.add_person(pid, name, role, raw_path, voice_id)
        print(f"  Added {name} ({role})")

        # Mark steps as completed based on existing files
        step_files = {
            "analyze": "",
            "voice_clone": "",
            "transcript": os.path.join(VIDEO_TEAM_DIR, "transcripts", f"{name}.txt"),
            "tts": os.path.join(VIDEO_TEAM_DIR, "tts", f"{name}.mp3"),
            "lipsync": os.path.join(VIDEO_TEAM_DIR, "lip_sync", f"{name}.mp4"),
            "background": os.path.join(VIDEO_TEAM_DIR, "backgrounds", f"{name}.mp4"),
            "composite": os.path.join(VIDEO_TEAM_DIR, "composited", f"{name}.mp4"),
        }

        # Analyze is always completed (we have the entry)
        proj_repo.update_step(pid, name, "analyze", "completed")

        # Voice clone
        if voice_id:
            proj_repo.update_step(pid, name, "voice_clone", "completed")
        else:
            proj_repo.update_step(pid, name, "voice_clone", "skipped")

        # File-based steps
        for step, fpath in step_files.items():
            if step in ("analyze", "voice_clone"):
                continue
            if fpath and os.path.exists(fpath):
                proj_repo.update_step(pid, name, step, "completed", output_path=fpath)

        # Check skip_lipsync
        if entry.get("skip_lipsync"):
            proj_repo.update_step(pid, name, "lipsync", "skipped")

    # Mark build and final as completed (group steps)
    build_path = os.path.join(VIDEO_TEAM_DIR, "output", "team_shot.mp4")
    final_path = os.path.join(VIDEO_TEAM_DIR, "output", "team_shot_full_ai.mp4")
    for entry in analysis:
        name = entry["name"]
        if os.path.exists(build_path):
            proj_repo.update_step(pid, name, "build", "completed", output_path=build_path)
        if os.path.exists(final_path):
            proj_repo.update_step(pid, name, "final", "completed", output_path=final_path)

    # Update project status
    proj_repo.update_project_status(pid, "completed")

    # Link existing videos to project
    db = get_database()
    db.execute("UPDATE videos SET project_id = ? WHERE source_dir = ?",
               (pid, VIDEO_TEAM_DIR))
    linked = db.fetch_one("SELECT COUNT(*) FROM videos WHERE project_id = ?", (pid,))
    print(f"\nLinked {linked[0]} videos to project")

    # Verify
    matrix = proj_repo.get_pipeline_matrix(pid)
    steps = matrix["steps"]
    header = "              " + "  ".join(f"{s[:5]:>5}" for s in steps)
    print(f"\n{header}")
    for pname in matrix["persons"]:
        psteps = matrix["matrix"].get(pname, {})
        statuses = []
        for s in steps:
            st = psteps.get(s, {}).get("status", "?")
            symbol = {"completed": "done", "skipped": "skip", "pending": "---"}.get(st, st[:4])
            statuses.append(f"{symbol:>5}")
        print(f"  {pname:12s}{'  '.join(statuses)}")

    print(f"\nProject '{project['name']}' created successfully!")


if __name__ == "__main__":
    main()
