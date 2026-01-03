"""Test OpenRouter API Key"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def test_openrouter():
    results = []
    key = os.getenv('OPENROUTER_API_KEY')
    
    if not key:
        results.append("FEHLER: OPENROUTER_API_KEY nicht gefunden in .env")
        with open('test_result.txt', 'w') as f:
            f.write('\n'.join(results))
        return False
    
    results.append(f"Key gefunden: {key[:20]}...")
    
    # Test API Call
    try:
        from openai import OpenAI
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key
        )
        
        results.append("Teste API...")
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'Hello' in one word"}],
            max_tokens=10
        )
        
        result = response.choices[0].message.content
        results.append(f"API Antwort: {result}")
        results.append("SUCCESS: OpenRouter funktioniert!")
        
        with open('test_result.txt', 'w') as f:
            f.write('\n'.join(results))
        return True
        
    except Exception as e:
        results.append(f"FEHLER: {e}")
        with open('test_result.txt', 'w') as f:
            f.write('\n'.join(results))
        return False

if __name__ == "__main__":
    test_openrouter()