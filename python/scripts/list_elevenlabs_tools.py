"""List all ElevenLabs tools and check for duplicates."""
from deploy_tools import load_env, get_api_key, list_tools
from collections import defaultdict

output = []

def log(msg):
    print(msg, flush=True)
    output.append(msg)

load_env()
api_key = get_api_key()

tools = list_tools(api_key)
log(f'Total tools: {len(tools)}')
log('')

# Group by name
by_name = defaultdict(list)
for t in tools:
    config = t.get('tool_config', {})
    name = config.get('name', 'unknown')
    by_name[name].append({
        'id': t.get('id'),
        'description': config.get('description', '')[:80]
    })

log('=' * 60)
log('TOOL LIST')
log('=' * 60)

for name, items in sorted(by_name.items()):
    if len(items) > 1:
        log(f'\n[DUPLICATE] {name} ({len(items)} copies):')
        for item in items:
            log(f'  - {item["id"][:20]}...')
            log(f'    {item["description"]}...')
    else:
        log(f'{name}: {items[0]["id"][:16]}...')

# Check for list_ideas and list_bubbles specifically
log('')
log('=' * 60)
log('LIST_IDEAS vs LIST_BUBBLES Check')
log('=' * 60)

for name in ['list_ideas', 'list_bubbles']:
    if name in by_name:
        log(f'\n{name}:')
        for item in by_name[name]:
            log(f'  ID: {item["id"]}')
            log(f'  Description: {item["description"]}')
    else:
        log(f'\n{name}: NOT FOUND!')

# Write to file
with open('elevenlabs_tools_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))
log('\nOutput saved to elevenlabs_tools_output.txt')