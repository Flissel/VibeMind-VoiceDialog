"""
Test script for Vibemind Workspace Tools
Verifies tools work with ElevenLabs-style parameter format.
"""

import sys
sys.path.insert(0, '.')

from tools.workspace_tools import (
    capture_idea, list_ideas, get_idea, score_idea,
    create_project, list_projects, promote_idea, update_project,
    add_to_canvas, list_canvas
)


def main():
    print('Testing Vibemind Workspace Tools...')
    print()

    # Test capture_idea (ElevenLabs format - params dict)
    result = capture_idea({
        'title': 'Voice command automation',
        'description': 'Automate desktop tasks with voice commands',
        'tags': ['automation', 'voice', 'productivity']
    })
    print(f'[capture_idea] {result}')

    # Test list_ideas
    result = list_ideas({})
    print(f'[list_ideas] {result}')

    # Test get_idea
    result = get_idea({'title': 'Voice command'})
    print(f'[get_idea] {result}')

    # Test score_idea
    result = score_idea({
        'title': 'Voice command',
        'feasibility': 8,
        'impact': 9,
        'novelty': 6,
        'urgency': 7
    })
    print(f'[score_idea] {result}')

    # Test create_project
    result = create_project({
        'name': 'Direct project',
        'description': 'A project created directly, not from idea'
    })
    print(f'[create_project] {result}')

    # Test list_projects
    result = list_projects({})
    print(f'[list_projects] {result}')

    # Test promote_idea
    result = promote_idea({'title': 'Voice command'})
    print(f'[promote_idea] {result}')

    # Test add_to_canvas
    result = add_to_canvas({'project_name': 'Voice command automation'})
    print(f'[add_to_canvas] {result}')

    # Test list_canvas
    result = list_canvas({})
    print(f'[list_canvas] {result}')

    print()
    print('=' * 50)
    print('All workspace tools working correctly!')
    print('=' * 50)


if __name__ == '__main__':
    main()
