from data import IdeasRepository

ideas_repo = IdeasRepository()
ideas = ideas_repo.get_all()

print(f'Anzahl der Bubbles: {len(ideas)}')
print()

for idea in ideas[:10]:
    print(f'ID: {idea.id}, Title: {idea.title}, Created: {idea.created_at}')
