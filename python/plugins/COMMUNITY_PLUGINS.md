# Community Plugins - Setup & Workflow

## Erstmaliges Einbinden des VibeMind Plugin-Repos

```bash
cd VibeMind-VoiceDialog
git subtree add --prefix=python/plugins/community https://github.com/org/VibeMind main --squash
```

## Updates holen

```bash
git subtree pull --prefix=python/plugins/community https://github.com/org/VibeMind main --squash
```

## Struktur im VibeMind-Repo

Jeder Space ist ein Ordner mit `plugin.json`:

```
VibeMind/
  marketing/
    plugin.json          # Pflicht - Plugin-Manifest
    agents/
      marketing_agent.py # BaseBackendAgent subclass
    tools/
      marketing_tools.py
  video/
    plugin.json
    agents/
      video_agent.py
    tools/
      video_tools.py
```

## Plugin-Manifest Pflichtfelder

```json
{
  "id": "marketing",
  "version": "1.0.0",
  "name": "Marketing Suite",
  "description": "Kampagnen planen, Content generieren, Analytics",
  "agent_module": "plugins.community.marketing.agents.marketing_agent",
  "agent_class": "MarketingAgent",
  "agent_factory": "get_marketing_agent",
  "stream": "events:tasks:marketing",
  "event_routes": {
    "marketing.create": "events:tasks:marketing",
    "marketing.list": "events:tasks:marketing"
  }
}
```

**Wichtig:** `agent_module` muss den vollen Importpfad ab `plugins.community.*` verwenden,
da der Code unter `python/plugins/community/` landet.

## Optionale Felder

```json
{
  "author": "Dein Name",
  "category": "marketing",
  "changelog": "Was ist neu in dieser Version",
  "classifier_hints": {
    "keywords_de": ["kampagne", "marketing", "content"],
    "keywords_en": ["campaign", "marketing", "content"],
    "example_utterances": [
      {"text": "Erstelle eine Marketing-Kampagne", "event_type": "marketing.create"}
    ]
  },
  "env_flag": "MARKETING_ENABLED",
  "dependencies": ["requests", "jinja2"]
}
```

## Agent-Template

```python
# plugins/community/marketing/agents/marketing_agent.py

from swarm.backend_agents.base_agent import BaseBackendAgent
from typing import Dict, Callable, Optional

class MarketingAgent(BaseBackendAgent):
    EVENT_TO_TOOL = {
        "marketing.create": "create_campaign",
        "marketing.list": "list_campaigns",
    }

    PARAM_MAPPING = {
        "marketing.create": {"name": "title"},
    }

    @property
    def stream(self) -> str:
        return "events:tasks:marketing"

    @property
    def name(self) -> str:
        return "MarketingAgent"

    def _load_tools(self) -> Dict[str, Callable]:
        tools = {}
        try:
            from plugins.community.marketing.tools.marketing_tools import (
                create_campaign, list_campaigns,
            )
            tools.update({
                "create_campaign": create_campaign,
                "list_campaigns": list_campaigns,
            })
        except ImportError as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not load tools: {e}")
        return tools

    def _get_tool_name(self, event_type: str) -> Optional[str]:
        return self.EVENT_TO_TOOL.get(event_type)


_agent = None

def get_marketing_agent():
    global _agent
    if _agent is None:
        _agent = MarketingAgent()
    return _agent
```

## Was beim User passiert

1. User updated die App (git pull / auto-update)
2. Neue Plugins erscheinen im ClawPort Dashboard unter "Plugins"
3. Neue Plugins zeigen "NEW" Badge
4. User klickt "Aktivieren" oder "Nicht jetzt"
5. Nur aktivierte Plugins werden geladen und routen Events

## Checkliste vor dem Push

- [ ] `plugin.json` hat alle Pflichtfelder
- [ ] `agent_module` Pfad stimmt (`plugins.community.<name>.agents.<name>_agent`)
- [ ] Agent erbt von `BaseBackendAgent`
- [ ] `_load_tools()` gibt Dict zurueck
- [ ] `event_routes` Keys matchen die `EVENT_TO_TOOL` Keys im Agent
- [ ] Tools geben `{"success": True/False, "message": "..."}` zurueck
- [ ] Version in `plugin.json` bei jedem Update hochzaehlen
