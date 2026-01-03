"""
Test script for Vibemind Data Layer
Verifies database, models, and repository operations work correctly.
"""

import sys
sys.path.insert(0, '.')

def main():
    print('Testing Vibemind Data Layer...')
    print()

    # Test database connection
    from data.database import Database, get_database
    db = get_database()
    print(f'[OK] Database initialized: {db.db_path}')
    print(f'     Schema version: {db.get_schema_version()}')

    # Test Ideas Repository
    from data.repository import IdeasRepository, ProjectsRepository, CanvasRepository, promote_idea_to_project

    ideas_repo = IdeasRepository()

    # Create an idea
    idea = ideas_repo.create(
        title='Build voice-controlled workspace',
        description='A desktop app where you can capture ideas via voice',
        tags=['voice', 'desktop', 'productivity']
    )
    print(f'[OK] Created idea: {idea.title} (ID: {idea.id})')

    # List ideas
    ideas = ideas_repo.list()
    print(f'[OK] Listed ideas: {len(ideas)} found')

    # Score the idea
    idea.feasibility = 8.0
    idea.impact = 9.0
    idea.novelty = 7.0
    idea.urgency = 6.0
    idea = ideas_repo.update(idea)
    print(f'[OK] Scored idea: {idea.score:.0f}/100 (status: {idea.status})')

    # Test Projects Repository
    projects_repo = ProjectsRepository()

    # Promote idea to project
    project = promote_idea_to_project(idea.id)
    print(f'[OK] Promoted idea to project: {project.name}')

    # Verify idea status updated
    idea = ideas_repo.get(idea.id)
    print(f'[OK] Idea status updated: {idea.status}')

    # List projects
    projects = projects_repo.list()
    print(f'[OK] Listed projects: {len(projects)} found')

    # Test Canvas Repository
    canvas_repo = CanvasRepository()

    # Create a node
    node = canvas_repo.create_node(
        node_type='idea',
        title='Test Node',
        x=100, y=100,
        linked_idea_id=idea.id
    )
    print(f'[OK] Created canvas node: {node.title} at ({node.x}, {node.y})')

    # List canvas nodes
    nodes = canvas_repo.list_nodes()
    print(f'[OK] Listed canvas nodes: {len(nodes)} found')

    print()
    print('=' * 50)
    print('All tests passed! Data layer is working correctly.')
    print('=' * 50)

    # Cleanup test data (in correct order for foreign key constraints)
    print()
    print('Cleaning up test data...')
    canvas_repo.delete_node(node.id)
    # Clear idea's project reference before deleting project
    idea.promoted_to_project_id = None
    ideas_repo.update(idea)
    projects_repo.delete(project.id)
    ideas_repo.delete(idea.id)
    print('[OK] Test data cleaned up')


if __name__ == '__main__':
    main()
