"""Quick E2E test for n8n workflow generator."""
import os, sys, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

os.environ.setdefault('FORCE_SYNC_MODE', 'true')

print("=== Config ===")
print(f"OPENAI_API_KEY set: {bool(os.getenv('OPENAI_API_KEY'))}")
print(f"N8N_API_URL: {os.getenv('N8N_API_URL')}")
print(f"N8N_GENERATOR_MODEL: {os.getenv('N8N_GENERATOR_MODEL')}")

# Health check
from spaces.n8n.tools.n8n_api_client import get_n8n_client
client = get_n8n_client()
health = client.health_check()
print(f"n8n health: {health}")

# Generate workflow
print("\n=== Generating Workflow ===")
from spaces.n8n.tools.n8n_workflow_tools import generate_workflow
result = generate_workflow(
    'Ein AI Agent mit Webhook-Trigger der Kundendaten aus einer PostgreSQL Datenbank liest und per Chat antwortet'
)
print(json.dumps(result, indent=2, ensure_ascii=False))
