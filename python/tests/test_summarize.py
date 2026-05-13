"""Test Summarize Tool mit Datenbank"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

results = []

try:
    # 1. Prüfe API Key
    key = os.getenv('OPENROUTER_API_KEY')
    if key:
        results.append(f"1. API Key: OK ({key[:20]}...)")
    else:
        results.append("1. API Key: FEHLT!")
    
    # 2. Prüfe Datenbank
    from data.supabase_database import Database
    db = Database(os.path.join(os.path.dirname(__file__), '..', 'vibemind.db'))
    bubbles = db.get_all_bubbles()
    results.append(f"2. Bubbles in DB: {len(bubbles)}")
    
    if bubbles:
        # Zeige erste 3 Bubbles
        for i, b in enumerate(bubbles[:3]):
            results.append(f"   - {b.id[:8]}... : {b.label}")
        
        # 3. Teste summarize mit erster Bubble
        results.append(f"\n3. Teste summarize_idea mit: {bubbles[0].label}")
        
        from tools.summary_tools import summarize_idea
        summary_result = summarize_idea({'bubble_id': bubbles[0].id})
        results.append(f"   Ergebnis: {summary_result[:200]}...")
    else:
        results.append("   Keine Bubbles vorhanden")
        
        # 3. Teste mit Dummy-Daten
        results.append("\n3. Teste summarize_idea mit Dummy-Daten...")
        from tools.summary_tools import summarize_idea
        summary_result = summarize_idea({})
        results.append(f"   Ergebnis: {summary_result}")

except Exception as e:
    results.append(f"FEHLER: {type(e).__name__}: {e}")
    import traceback
    results.append(traceback.format_exc())

# Speichere Ergebnisse
output = '\n'.join(results)
print(output)
with open('test_summarize_result.txt', 'w', encoding='utf-8') as f:
    f.write(output)