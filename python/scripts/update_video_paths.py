"""One-time script: update video DB paths from Desktop/Video_Team to .rowboat/knowledge/Videos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.video_repository import VideoRepository

repo = VideoRepository()
videos = repo.list_all(limit=500)

old_base = r'C:\Users\User\Desktop\Video_Team'
new_base = os.path.join(os.path.expanduser('~'), '.rowboat', 'knowledge', 'Videos')

print(f'Old base: {old_base}')
print(f'New base: {new_base}')
print(f'Videos: {len(videos)}')

updated = 0
for v in videos:
    old_path = v['file_path']
    if old_base in old_path:
        new_path = old_path.replace(old_base, new_base)
        repo.db.execute(
            'UPDATE videos SET file_path = ?, source_dir = ? WHERE id = ?',
            (new_path, new_base, v['id'])
        )
        updated += 1
        print(f'  {v["filename"]}: OK')

print(f'\nUpdated {updated}/{len(videos)} paths')

# Verify
sample = repo.list_all(limit=3)
for s in sample:
    print(f'  -> {s["file_path"]}')
