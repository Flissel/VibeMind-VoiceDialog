# VibeMind Multi-Language Translation Map

This reference maps all translatable components across the three initial languages (DE, EN, FR).

## 1. Translation Layers

VibeMind has **5 translation layers** that must stay in sync:

| Layer | File(s) | What to Translate |
|-------|---------|-------------------|
| **Classifier Prompt** | `python/swarm/orchestrator/intent_classifier.py` → `CLASSIFIER_PROMPT_TEMPLATE` | Space descriptions, keywords, example utterances, disambiguation rules |
| **Rachel Voice Prompt** | `python/spaces/ideas/agents/rachel_agent.py` → `RACHEL_VOICE_PROMPT` | Role description, async behaviour examples, personality rules |
| **Tool Descriptions** | `python/voice/session_config.py` → `SEND_INTENT_TOOL`, `CHECK_RESULTS_TOOL` | Tool `description` fields sent to OpenAI Realtime |
| **Clarification Phrases** | `python/swarm/user_agents/base.py` → `CLARIFICATION_PHRASES_*` | Fallback clarification questions |
| **Agent Greeting** | `python/spaces/ideas/agents/rachel_agent.py` → `RachelAgent.__init__` `greeting=` | First spoken sentence when session starts |

## 2. Classifier Prompt — Example Utterances per Language

### Bubble Events

| Event | DE | EN | FR |
|-------|----|----|-----|
| `bubble.list` | "Zeig mir meine Bubbles" | "Show me my bubbles" | "Montre-moi mes bulles" |
| `bubble.create` | "Erstelle Bubble Marketing" | "Create a Marketing bubble" | "Crée une bulle Marketing" |
| `bubble.enter` | "Geh in Marketing" | "Go to Marketing" | "Va dans Marketing" |
| `bubble.exit` | "Zurück", "Raus" | "Back", "Exit" | "Retour", "Sortir" |
| `bubble.delete` | "Lösche Bubble X" | "Delete bubble X" | "Supprime la bulle X" |
| `bubble.find` | "Finde Bubble X" | "Find bubble X" | "Trouve la bulle X" |
| `bubble.stats` | "Wie viele Ideen?" | "How many ideas?" | "Combien d'idées ?" |

### Idea Events

| Event | DE | EN | FR |
|-------|----|----|-----|
| `idea.create` | "Notiere: API Design" | "Note: API Design" | "Note : API Design" |
| `idea.list` | "Zeig alle Ideen" | "Show all ideas" | "Montre toutes les idées" |
| `idea.auto_link` | "Verlinke die Ideen sinnvoll" | "Link the ideas meaningfully" | "Relie les idées intelligemment" |
| `idea.format` | "Formatiere in Aktionslisten" | "Format as action lists" | "Formate en listes d'actions" |
| `idea.summarize` | "Fasse zusammen" | "Summarize" | "Résume" |
| `idea.expand` | "Erweitere die Ideen" | "Expand the ideas" | "Développe les idées" |
| `idea.explain` | "Erkläre die Idee X" | "Explain the idea X" | "Explique l'idée X" |
| `idea.connect` | "Verbinde A mit B" | "Connect A with B" | "Connecte A avec B" |

### Code Events

| Event | DE | EN | FR |
|-------|----|----|-----|
| `code.generate` | "Erstelle eine App für X" | "Create an app for X" | "Crée une appli pour X" |
| `code.status` | "Wie ist der Code-Status?" | "What's the code status?" | "Quel est le statut du code ?" |
| `code.list` | "Zeig Code-Projekte" | "Show code projects" | "Montre les projets code" |

### Desktop Events

| Event | DE | EN | FR |
|-------|----|----|-----|
| `desktop.open_app` | "Öffne Chrome" | "Open Chrome" | "Ouvre Chrome" |
| `desktop.click` | "Klick auf OK" | "Click OK" | "Clique sur OK" |
| `desktop.screenshot` | "Screenshot" | "Screenshot" | "Capture d'écran" |
| `desktop.type` | "Tippe Hallo" | "Type Hello" | "Tape Bonjour" |

### Messaging Events

| Event | DE | EN | FR |
|-------|----|----|-----|
| `messaging.send` | "Schreib meiner Mutter..." | "Write to my mother..." | "Écris à ma mère..." |
| `web.search` | "Such im Web nach X" | "Search the web for X" | "Cherche sur le web X" |

### Research Events

| Event | DE | EN | FR |
|-------|----|----|-----|
| `research.web` | "Recherchiere über X" | "Research X" | "Recherche sur X" |
| `research.scrape` | "Scrape die Seite" | "Scrape the page" | "Scrape la page" |

### Schedule Events

| Event | DE | EN | FR |
|-------|----|----|-----|
| `schedule.create` | "Erinnere mich in 5 Minuten" | "Remind me in 5 minutes" | "Rappelle-moi dans 5 minutes" |
| `schedule.list` | "Zeig meine Termine" | "Show my tasks" | "Montre mes tâches" |

### Roarboot Events

| Event | DE | EN | FR |
|-------|----|----|-----|
| `roarboot.search` | "Durchsuche mein Wissen" | "Search my knowledge" | "Cherche dans mes connaissances" |
| `roarboot.email_draft` | "Schreibe Email an X" | "Draft email to X" | "Rédige un email à X" |

## 3. Classifier Keywords per Language

| Space | DE Keywords | EN Keywords | FR Keywords |
|-------|-----------|-------------|-------------|
| Ideas | Bubble, Bereich, Idee, Notiz, Gedanke, merken | Bubble, area, idea, note, thought, remember | Bulle, domaine, idée, note, pensée, retenir |
| Coding | Code, Projekt, App, programmieren, bauen | Code, project, app, program, build | Code, projet, appli, programmer, construire |
| Desktop | Desktop, öffne, klick, tippe, Screenshot | Desktop, open, click, type, screenshot | Bureau, ouvre, clique, tape, capture |
| Research | recherchiere, web suche, finde heraus | research, web search, find out | recherche, recherche web, découvre |
| Schedule | Termin, erinnere, planen, morgen | appointment, remind, plan, tomorrow | rendez-vous, rappelle, planifier, demain |
| Roarboot | Wissen, Knowledge, Email, Meeting | Knowledge, email, meeting | Connaissances, email, réunion |
| Messaging | Nachricht, senden, schreib an | message, send, write to | message, envoyer, écris à |

## 4. Rachel Voice Prompt Translations

### Greeting

| Lang | Greeting |
|------|----------|
| DE | "Hallo! Ich bin Rachel, deine VibeMind Assistentin. Was soll ich für dich tun?" |
| EN | "Hi! I'm Rachel, your VibeMind assistant. What can I do for you?" |
| FR | "Salut ! Je suis Rachel, ton assistante VibeMind. Qu'est-ce que je peux faire pour toi ?" |

### Async Confirmation Phrases

| Lang | Short Confirmations |
|------|---------------------|
| DE | "Mach ich!", "Ich schau mal...", "Moment..." |
| EN | "On it!", "Let me check...", "One moment..." |
| FR | "C'est parti !", "Je vérifie...", "Un instant..." |

### Result Delivery Phrases

| Lang | Success | Error | Info |
|------|---------|-------|------|
| DE | "So, deine Bubble X ist erstellt!" | "Hmm, das hat leider nicht geklappt." | "Du hast übrigens drei Bubbles." |
| EN | "Done, your bubble X is created!" | "Hmm, that didn't work unfortunately." | "By the way, you have three bubbles." |
| FR | "Voilà, ta bulle X est créée !" | "Hmm, ça n'a pas marché malheureusement." | "Au fait, tu as trois bulles." |

### Clarification Phrases

| Lang | Phrases |
|------|---------|
| DE | "Kannst du das genauer erklären?", "Was genau meinst du damit?", "Ich brauche mehr Details dazu." |
| EN | "Could you explain that more specifically?", "What exactly do you mean?", "I need more details about that." |
| FR | "Peux-tu préciser ?", "Qu'est-ce que tu veux dire exactement ?", "J'ai besoin de plus de détails." |

## 5. Tool Description Translations

### send_intent

| Lang | Description |
|------|-------------|
| DE | "Sende den Wunsch des Users an das VibeMind System zur Ausführung..." |
| EN | "Send the user's request to VibeMind for execution. Runs async — you'll get the result automatically when it's done. Use for ALL actions: managing bubbles, creating ideas, desktop automation, code generation, research, Rowboat projects. The system automatically detects which area is responsible." |
| FR | "Envoie la demande de l'utilisateur au système VibeMind pour exécution. Fonctionne en async — tu recevras le résultat automatiquement. Utilise pour TOUTES les actions : gérer les bulles, créer des idées, automatisation bureau, génération de code, recherche, projets Rowboat. Le système détecte automatiquement le domaine responsable." |

### check_results

| Lang | Description |
|------|-------------|
| DE | "Prüfe ob neue Ergebnisse von laufenden Aufgaben vorliegen..." |
| EN | "Check whether new results from running tasks are available. Use when the user asks 'Any news?', 'What about my request?', or when you haven't heard back in a while. Results also arrive automatically — this tool is for explicit follow-ups." |
| FR | "Vérifie s'il y a de nouveaux résultats des tâches en cours. Utilise quand l'utilisateur demande 'Des nouvelles ?', 'Et ma demande ?' ou quand tu n'as pas eu de retour depuis un moment. Les résultats arrivent aussi automatiquement — cet outil est pour les demandes explicites." |

## 6. Disambiguation Rules per Language

### DE
- "Schreib meiner/meinem [Person]" → `messaging.send`, NICHT `idea.create`
- "Recherchiere X" → `research.web` (externes Web), NICHT `roarboot.search` (internes Wissen)

### EN
- "Write to [Person]" → `messaging.send`, NOT `idea.create`
- "Research X" → `research.web` (external web), NOT `roarboot.search` (internal knowledge)

### FR
- "Écris à [Personne]" → `messaging.send`, PAS `idea.create`
- "Recherche X" → `research.web` (web externe), PAS `roarboot.search` (connaissances internes)