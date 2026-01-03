"""
Seed bubbles from req-orchestrator projects.

Creates VibeMind bubbles (ideas) from req-orchestrator project .md files,
with each .md file stored as a scrollable whitepaper node inside the bubble.
Optionally syncs shuttle state from req-orchestrator API.

Usage:
    python seed_projects.py [--clear] [--source-dir PATH] [--sync-shuttles]

Options:
    --clear          Delete existing req-orchestrator bubbles before seeding
    --source-dir     Path to req-orchestrator public directory (default from env)
    --sync-shuttles  Also create shuttles synced to req-orchestrator pipeline state
"""

import os
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from data import IdeasRepository, CanvasRepository, ShuttlesRepository, ProjectsRepository


# Source directory for .md files
REQ_ORCHESTRATOR_PUBLIC = Path(os.getenv(
    "REQ_ORCHESTRATOR_PUBLIC",
    r"C:\Users\User\Desktop\-req-orchestrator\public"
))

# Project files to seed
PROJECT_FILES = [
    "Abrechnung.md",
    "Auftragsmanagement.md",
    "Benutzer_Rollenverwaltung.md",
    "Disposition.md",
    "Geschaeftspartner.md",
    "Integration_API_Gateway.md",
    "POD_Management.md",
    "port_manager_requirements.md",
    "Transport_Tracking.md",
]


def extract_title_from_markdown(content: str, filename: str) -> str:
    """
    Extract title from first # heading in markdown content.
    Falls back to filename without extension if no heading found.
    """
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    # Fallback: use filename
    return filename.replace('.md', '').replace('_', ' ')


def count_requirements_in_markdown(content: str) -> int:
    """
    Estimate number of requirements by counting bullet points and numbered items.
    """
    count = 0
    for line in content.split('\n'):
        line = line.strip()
        # Count bullet points
        if line.startswith('- ') or line.startswith('* '):
            count += 1
        # Count numbered items
        elif line and line[0].isdigit() and '. ' in line[:4]:
            count += 1
    return count


def seed_bubble_from_file(
    filepath: Path,
    ideas_repo: IdeasRepository,
    canvas_repo: CanvasRepository,
    shuttles_repo: ShuttlesRepository = None
):
    """
    Create a bubble with whitepaper content from .md file.
    Optionally sync shuttle state from req-orchestrator API.

    Args:
        filepath: Path to the .md file
        ideas_repo: Ideas repository instance
        canvas_repo: Canvas repository instance
        shuttles_repo: Optional shuttles repository for syncing shuttle state

    Returns:
        Created Idea or existing Idea if already seeded
    """
    content = filepath.read_text(encoding='utf-8')
    filename = filepath.name
    title = extract_title_from_markdown(content, filename)
    req_count = count_requirements_in_markdown(content)

    # Check if already exists (by metadata.source_file)
    existing = ideas_repo.find_by_metadata_key("source_file", filename)
    if existing:
        print(f"  Skipping {filename} - already exists as '{existing.title}'")
        # Still try to sync shuttle if requested
        if shuttles_repo:
            _sync_shuttle_for_idea(existing, shuttles_repo, title)
        return existing

    # 1. Create the bubble/idea
    idea = ideas_repo.create(
        title=title,
        description=f"Requirements specification from {filename} (~{req_count} items)",
        source="req-orchestrator",
        metadata={
            "source_file": filename,
            "source_path": str(filepath),
            "content_length": len(content),
            "estimated_requirements": req_count,
        }
    )
    print(f"  Created bubble: {idea.title} ({idea.id})")

    # 2. Create whitepaper node inside bubble
    node = canvas_repo.create_node(
        node_type="whitepaper",
        title=filename,
        content=content,
        x=200,
        y=100,
        linked_idea_id=idea.id,
        metadata={
            "source": "req-orchestrator",
            "scrollable": True,
            "markdown": True,
            "char_count": len(content),
        }
    )
    print(f"    + Added whitepaper node: {node.id} ({len(content)} chars)")

    # 3. Sync shuttle from req-orchestrator if repository provided
    if shuttles_repo:
        _sync_shuttle_for_idea(idea, shuttles_repo, title)

    return idea


def _sync_shuttle_for_idea(idea, shuttles_repo: ShuttlesRepository, title: str):
    """
    Sync or create shuttle for an idea from req-orchestrator API state.
    Also creates a project in Projects Space with status="shuttling".
    """
    try:
        from tools.summary_tools import _fetch_orchestrator_project_state
        project_state = _fetch_orchestrator_project_state(project_name=title)

        if not project_state:
            print(f"    ! No orchestrator project found for '{title}'")
            return

        # Extract state
        orchestrator_stage = project_state.get("current_stage", "mining")
        validation = project_state.get("validation_summary", {})
        total = validation.get("total", project_state.get("requirements_count", 0))
        avg_score = validation.get("avg_score", 0.0)
        passed = validation.get("passed", 0)
        failed = validation.get("failed", 0)

        # Get or create projects repository
        projects_repo = ProjectsRepository()

        # Check for existing shuttle
        existing_shuttles = shuttles_repo.list(bubble_id=idea.id)

        if existing_shuttles:
            # Update existing shuttle
            shuttle = existing_shuttles[0]
            shuttle.current_stage = orchestrator_stage
            shuttle.score = avg_score
            shuttle.passed_count = passed
            shuttle.failed_count = failed
            shuttle.total_count = total
            shuttle.metadata = shuttle.metadata or {}
            shuttle.metadata["orchestrator_project_id"] = project_state.get("project_id")
            shuttle.metadata["synced_from_orchestrator"] = True
            shuttles_repo.update(shuttle)
            print(f"    + Updated shuttle: {shuttle.shuttle_id} (stage: {orchestrator_stage})")
        else:
            # 1. Create project FIRST with status="shuttling" (Phase 8 requirement)
            project = projects_repo.create(
                name=title,
                description=f"Requirements pipeline from {idea.metadata.get('source_file', 'unknown')}",
                from_idea_id=idea.id,
                status="shuttling",
                metadata={
                    "orchestrator_project_id": project_state.get("project_id"),
                    "source_bubble": idea.id,
                    "requirements_count": total,
                }
            )
            print(f"    + Created project: {project.name} (status=shuttling)")

            # 2. Create shuttle linked to project
            shuttle_id = f"shuttle-{title[:10]}-{int(time.time())}"
            shuttle = shuttles_repo.create(
                shuttle_id=shuttle_id,
                bubble_id=idea.id,
                bubble_name=title,
                total_count=total,
                project_id=project.id,  # Link to project
                metadata={
                    "orchestrator_project_id": project_state.get("project_id"),
                    "synced_from_orchestrator": True
                }
            )
            # Update with stage and score
            shuttle.current_stage = orchestrator_stage
            shuttle.score = avg_score
            shuttle.passed_count = passed
            shuttle.failed_count = failed
            shuttles_repo.update(shuttle)
            print(f"    + Created shuttle: {shuttle.shuttle_id} (stage: {orchestrator_stage})")

    except Exception as e:
        print(f"    ! Shuttle sync failed: {e}")


def seed_all_projects(source_dir: Path = None, clear: bool = False, sync_shuttles: bool = False):
    """
    Seed all project .md files as bubbles.

    Args:
        source_dir: Directory containing .md files (default: REQ_ORCHESTRATOR_PUBLIC)
        clear: If True, delete existing req-orchestrator bubbles first
        sync_shuttles: If True, also create/update shuttles from req-orchestrator state

    Returns:
        List of created/existing Idea objects
    """
    source_dir = source_dir or REQ_ORCHESTRATOR_PUBLIC
    ideas_repo = IdeasRepository()
    canvas_repo = CanvasRepository()
    shuttles_repo = ShuttlesRepository() if sync_shuttles else None

    if clear:
        print("Clearing existing req-orchestrator bubbles...")
        existing = ideas_repo.list_by_source("req-orchestrator")

        # IMPORTANT: Delete order (foreign key constraints):
        # 1. Shuttles (reference both projects and ideas)
        # 2. Projects (reference ideas via from_idea_id)
        # 3. Ideas/Bubbles
        clear_shuttles_repo = shuttles_repo or ShuttlesRepository()
        clear_projects_repo = ProjectsRepository()

        for idea in existing:
            # 1. Delete any shuttles referencing this idea
            idea_shuttles = clear_shuttles_repo.list(bubble_id=idea.id)
            for shuttle in idea_shuttles:
                clear_shuttles_repo.delete(shuttle.id)
                print(f"  Deleted shuttle: {shuttle.shuttle_id}")

            # 2. Delete any projects linked to this idea
            idea_projects = clear_projects_repo.list_by_idea(idea.id)
            for project in idea_projects:
                clear_projects_repo.delete(project.id)
                print(f"  Deleted project: {project.name}")

            # 3. Now safe to delete the idea (cascade deletes canvas nodes)
            ideas_repo.delete_cascade(idea.id)
            print(f"  Deleted bubble: {idea.title}")

        print(f"  Cleared {len(existing)} bubbles.")

    print(f"\nSeeding from: {source_dir}")
    print(f"Files to process: {len(PROJECT_FILES)}")
    if sync_shuttles:
        print("Shuttle sync: ENABLED")
    print("-" * 60)

    created = []
    not_found = []

    for filename in PROJECT_FILES:
        filepath = source_dir / filename
        if filepath.exists():
            idea = seed_bubble_from_file(filepath, ideas_repo, canvas_repo, shuttles_repo)
            created.append(idea)
        else:
            print(f"  WARNING: File not found: {filepath}")
            not_found.append(filename)

    print("-" * 60)
    print(f"Processed: {len(created)} bubbles")
    if not_found:
        print(f"Not found: {len(not_found)} files: {not_found}")

    # Summary
    print("\nBubbles in database:")
    all_ideas = ideas_repo.list_by_source("req-orchestrator")
    for idea in all_ideas:
        req_count = idea.metadata.get("estimated_requirements", "?")
        print(f"  - {idea.title} (id={idea.id}, ~{req_count} reqs)")

    # Shuttle summary
    if sync_shuttles:
        print("\nShuttles synced from req-orchestrator:")
        for shuttle in shuttles_repo.list_active():
            if shuttle.metadata and shuttle.metadata.get("synced_from_orchestrator"):
                print(f"  - {shuttle.bubble_name}: stage={shuttle.current_stage}, score={shuttle.score:.2f}")

    return created


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed VibeMind bubbles from req-orchestrator project files"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete existing req-orchestrator bubbles before seeding"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=REQ_ORCHESTRATOR_PUBLIC,
        help=f"Path to req-orchestrator public directory (default: {REQ_ORCHESTRATOR_PUBLIC})"
    )
    parser.add_argument(
        "--sync-shuttles",
        action="store_true",
        help="Also create/update shuttles synced to req-orchestrator pipeline state"
    )

    args = parser.parse_args()

    if not args.source_dir.exists():
        print(f"ERROR: Source directory not found: {args.source_dir}")
        print("Set REQ_ORCHESTRATOR_PUBLIC env var or use --source-dir")
        sys.exit(1)

    seed_all_projects(
        source_dir=args.source_dir,
        clear=args.clear,
        sync_shuttles=args.sync_shuttles
    )


if __name__ == "__main__":
    main()
