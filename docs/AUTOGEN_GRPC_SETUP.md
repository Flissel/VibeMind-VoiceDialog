# AutoGen gRPC Integration - Complete Setup Guide

## Overview

This guide explains how to use **AutoGen gRPC distributed runtime** with your **ElevenLabs Conversational AI agents**. This integration enables your voice agents to leverage powerful distributed computing capabilities for complex tasks.

## Architecture

```
User Voice Input
    ↓
ElevenLabs Conversational Memory Agent (Rachel)
    ↓ [transfer_to_agent]
ElevenLabs Project Manager (Alice)
    ↓ [decides on task type]
ElevenLabs Desktop Worker/Project Writer (Adam/Antoni)
    ↓ [calls client tool]
AutoGen Bridge (autogen_bridge.py)
    ↓ [sends RPC request]
gRPC Host (grpc_host.py on localhost:50051)
    ↓ [routes to worker]
AutoGen Knowledge Worker (knowledge_worker.py)
    ↓ [processes request]
Returns Response
    ↓
Agent speaks result to user
```

## What Was Created

### Core Infrastructure

**1. gRPC Host Service**
- **File:** [python/grpc_host.py](python/grpc_host.py)
- **Purpose:** Central coordinator for AutoGen workers
- **Port:** localhost:50051
- **Features:**
  - Agent registration and discovery
  - Message routing between workers
  - Pub/sub topic management

**2. Knowledge Worker**
- **File:** [python/workers/knowledge_worker.py](python/workers/knowledge_worker.py)
- **Purpose:** Advanced knowledge retrieval and processing
- **Capabilities:**
  - URL fetching and content extraction
  - HTML parsing and text cleaning
  - Multi-level summarization (brief/medium/detailed)
  - Web search (placeholder for API integration)

**3. AutoGen Bridge**
- **File:** [python/tools/autogen_bridge.py](python/tools/autogen_bridge.py)
- **Purpose:** Connect ElevenLabs client tools to AutoGen workers
- **Functions:**
  - `fetch_url_knowledge(url, summary_length)` - Fetch and process URLs
  - `search_web_knowledge(query, max_results)` - Web search

### Client Tool Configurations

**4. AutoGen URL Knowledge Tool**
- **File:** [docs/agents/autogen_url_knowledge_tool.json](docs/agents/autogen_url_knowledge_tool.json)
- **Function:** `fetch_url_knowledge()` from autogen_bridge.py
- **Use Case:** Deep URL processing with better extraction than simple fetching

**5. AutoGen Web Search Tool**
- **File:** [docs/agents/autogen_web_search_tool.json](docs/agents/autogen_web_search_tool.json)
- **Function:** `search_web_knowledge()` from autogen_bridge.py
- **Use Case:** Research and web information retrieval

## Installation

### Step 1: Install Dependencies

Already done in requirements.txt, but to verify:

```bash
cd /c/Users/User/Desktop/Voice_dialog_vibemind/VibeMind-VoiceDialog
python -m pip install -r requirements.txt
```

Key dependencies:
- `autogen-core>=0.4.0`
- `autogen-ext[grpc]>=0.4.0`
- `beautifulsoup4>=4.12.0`

### Step 2: Configure Client Tools in Dashboard

Go to https://elevenlabs.io/app/conversational-ai

**For Desktop Worker OR Project Manager:**

1. Click on the agent
2. Tools → Client Tools → Add Client Tool
3. Copy JSON from `docs/agents/autogen_url_knowledge_tool.json`
4. Paste and Save
5. Repeat with `docs/agents/autogen_web_search_tool.json`

**Recommendation:** Add these tools to Desktop Worker since it handles "tasks"

## Running the System

### Start Order (3 Terminal Windows)

**Terminal 1: Start gRPC Host**
```bash
cd python
python grpc_host.py
```

Output:
```
INFO - Starting AutoGen gRPC host on localhost:50051
INFO - ✓ gRPC host successfully started on localhost:50051
INFO - Waiting for worker connections...
INFO - Press Ctrl+C to stop
```

**Terminal 2: Start Knowledge Worker**
```bash
cd python
python workers/knowledge_worker.py
```

Output:
```
INFO - Starting Knowledge Worker...
INFO - Connecting to gRPC host at localhost:50051
INFO - ✓ Connected to gRPC host
INFO - ✓ KnowledgeWorker registered and ready
INFO - Press Ctrl+C to stop
```

**Terminal 3: Start Voice Dialog**
```bash
cd python
python voice_dialog_main.py
```

Now you can speak to your agents!

## Testing

### Test 1: URL Knowledge Fetching

**Voice command:**
> "Learn from this URL: https://microsoft.github.io/autogen"

**Expected flow:**
1. Conversational Memory → Project Manager
2. Project Manager → Desktop Worker
3. Desktop Worker calls `fetch_url_knowledge()` client tool
4. Tool → AutoGen Bridge → gRPC Host → Knowledge Worker
5. Knowledge Worker fetches URL, extracts text, generates summary
6. Response flows back through chain
7. Desktop Worker speaks: "I've fetched knowledge from [URL]. The page is titled '...' and contains [N] words. Here's a medium summary: ..."

**Verify in logs:**
- Terminal 1 (host): Message routing activity
- Terminal 2 (worker): "Processing URL request: ..." and "✓ Successfully processed..."
- Terminal 3 (voice): Agent voice response

### Test 2: Web Search (Placeholder)

**Voice command:**
> "Search the web for AutoGen examples"

**Expected:**
Agent responds with: "Search failed: Web search not yet implemented. Add search API integration."

**To implement:** Add search API in `knowledge_worker.py` (Bing, Google, DuckDuckGo)

## How It Works

### Message Flow Detail

1. **User speaks** "Learn from this URL"
2. **ElevenLabs agent** recognizes this matches `fetch_url_knowledge` tool
3. **ElevenLabs SDK** calls Python function `fetch_url_knowledge(url)`
4. **autogen_bridge.py** creates `URLRequest` message
5. **AutoGen bridge** sends RPC through gRPC runtime
6. **gRPC host** routes message to `KnowledgeWorker` agent
7. **Knowledge worker** processes request:
   - Fetches URL with requests
   - Parses HTML with BeautifulSoup
   - Extracts and cleans text
   - Generates summary
8. **Response** flows back through chain
9. **Bridge** formats response as human-readable string
10. **ElevenLabs agent** speaks the result

### Request/Response Types

**URLRequest** (Bridge → Worker):
```python
@dataclass
class URLRequest:
    url: str
    summary_length: str  # "brief", "medium", "detailed"
    user_context: Optional[str]
```

**URLResponse** (Worker → Bridge):
```python
@dataclass
class URLResponse:
    url: str
    title: str
    content: str
    summary: str
    word_count: int
    success: bool
    error: Optional[str]
```

## Advanced Features

### Adding More Workers

Create new worker in `python/workers/`:

```python
# python/workers/research_worker.py
from autogen_core import RoutedAgent, message_handler, default_subscription

@default_subscription
class ResearchWorker(RoutedAgent):
    @message_handler
    async def handle_research_request(self, message: ResearchRequest, ctx: MessageContext):
        # Your logic here
        return ResearchResponse(...)

# Register in main():
await ResearchWorker.register(runtime, "research_worker", lambda: ResearchWorker())
```

### Adding More Bridge Functions

Extend `autogen_bridge.py`:

```python
def analyze_code(code: str, language: str) -> str:
    """New client tool function"""
    bridge = get_bridge()
    response = asyncio.run(bridge.analyze_code_via_worker(code, language))
    return f"Code analysis: {response.analysis}"
```

Create corresponding JSON in `docs/agents/`:

```json
{
  "type": "client",
  "name": "analyze_code",
  "description": "Analyze code using AutoGen worker",
  ...
}
```

### Distributed Across Machines

To run workers on different machines:

**Machine 1 (Host):**
```python
# Change address in grpc_host.py
host = GrpcWorkerAgentRuntimeHost(address="0.0.0.0:50051")
```

**Machine 2 (Worker):**
```python
# Change address in knowledge_worker.py
runtime = GrpcWorkerAgentRuntime(host_address="192.168.1.100:50051")
```

**Machine 3 (Voice):**
```python
# Change address in autogen_bridge.py
bridge = AutoGenBridge(host_address="192.168.1.100:50051")
```

### Telemetry and Monitoring

Add OpenTelemetry tracing:

```python
from opentelemetry import trace

runtime = GrpcWorkerAgentRuntime(
    host_address="localhost:50051",
    tracer_provider=trace.get_tracer_provider()
)
```

## Troubleshooting

### Worker can't connect to host

**Symptoms:**
```
ERROR - Failed to connect to gRPC host
```

**Solutions:**
1. Verify host is running: Check Terminal 1 for "✓ gRPC host successfully started"
2. Check port 50051 is not in use: `netstat -an | findstr 50051`
3. Firewall: Ensure localhost:50051 is allowed
4. Try restarting host first, then worker

### Client tool times out

**Symptoms:**
Agent says "Tool execution timed out"

**Solutions:**
1. Increase `response_timeout_secs` in tool JSON (currently 60s for URL fetch)
2. Check worker is running: Terminal 2 should show "✓ KnowledgeWorker registered"
3. Check worker logs for errors
4. Test URL manually: `curl [URL]` to verify it's accessible

### Bridge initialization fails

**Symptoms:**
```
ERROR - Failed to connect AutoGen bridge
```

**Solutions:**
1. Ensure host is running before starting voice dialog
2. Check `autogen_bridge.py` has correct host address
3. Verify `autogen-ext[grpc]` is installed: `pip list | grep autogen`
4. Check firewall settings

### URL fetching fails

**Symptoms:**
```
ERROR - Error fetching URL
```

**Solutions:**
1. Check URL is valid and accessible
2. Verify internet connection
3. Some sites block bots - check `User-Agent` in `knowledge_worker.py`
4. Try a different URL to isolate the issue

## File Reference

### Core Files
- `python/grpc_host.py` - gRPC host coordinator
- `python/workers/knowledge_worker.py` - Knowledge retrieval agent
- `python/tools/autogen_bridge.py` - ElevenLabs ↔ AutoGen connector

### Configuration Files
- `docs/agents/autogen_url_knowledge_tool.json` - URL fetch tool config
- `docs/agents/autogen_web_search_tool.json` - Web search tool config

### Documentation
- This file: `AUTOGEN_GRPC_SETUP.md` - Complete setup guide
- `CLIENT_TOOLS_SETUP.md` - Client tools general guide
- `CLIENT_TOOLS_QUICKSTART.md` - Quick reference

### Logs
- `grpc_host.log` - Host service logs
- `knowledge_worker.log` - Worker logs
- `voice_dialog.log` - Main application logs

## Comparison: Simple vs AutoGen

### Simple URL Tool (url_knowledge_tool.json)
- Direct HTTP request in main process
- Basic text extraction
- No distributed processing
- Faster for simple cases
- Less robust error handling

### AutoGen URL Tool (autogen_url_knowledge_tool.json)
- Distributed processing via gRPC worker
- Advanced HTML parsing with BeautifulSoup
- Multi-level summarization
- Better for complex content
- Scalable to multiple machines
- Can handle long-running tasks

**Use Simple Tool When:**
- URL is fast to fetch (<5s)
- Content is straightforward
- No complex processing needed

**Use AutoGen Tool When:**
- URL is slow or large
- Need advanced text extraction
- Want distributed processing
- Building complex knowledge base

## Next Steps

### 1. Implement Web Search

Edit `knowledge_worker.py`:

```python
@message_handler
async def handle_web_search(self, message: WebSearchRequest, ctx: MessageContext):
    # Add Bing Search API integration
    api_key = os.getenv("BING_SEARCH_API_KEY")
    response = requests.get(
        "https://api.bing.microsoft.com/v7.0/search",
        headers={"Ocp-Apim-Subscription-Key": api_key},
        params={"q": message.query, "count": message.max_results}
    )
    # Process and return results
```

### 2. Add More Workers

Create specialized workers:
- **CodeAnalysisWorker** - Analyze and review code
- **DataProcessingWorker** - Heavy data transformations
- **ResearchWorker** - Deep research with multiple sources
- **DatabaseWorker** - Complex database queries

### 3. Persistent Knowledge Base

Add vector database for RAG (Retrieval Augmented Generation):

```python
# python/workers/knowledge_worker.py
from chromadb import Client

class KnowledgeWorker(RoutedAgent):
    def __init__(self):
        super().__init__("Knowledge Worker")
        self.vector_db = Client()
        self.collection = self.vector_db.create_collection("knowledge")

    async def handle_url_request(self, message, ctx):
        # Fetch content
        content = await self.fetch_url(message.url)

        # Store in vector DB
        self.collection.add(
            documents=[content],
            metadatas=[{"url": message.url}],
            ids=[message.url]
        )

        # Return response
        return URLResponse(...)
```

### 4. Multi-Worker Orchestration

Create orchestrator worker that delegates to multiple specialized workers:

```python
class OrchestratorWorker(RoutedAgent):
    @message_handler
    async def handle_complex_task(self, message, ctx):
        # Delegate to multiple workers in parallel
        results = await asyncio.gather(
            self.send_message(SubTask1(), worker1_id),
            self.send_message(SubTask2(), worker2_id),
            self.send_message(SubTask3(), worker3_id)
        )

        # Combine results
        return CombinedResult(results)
```

## Summary

**What's Working:**
✅ gRPC host for worker coordination
✅ Knowledge worker for URL fetching
✅ AutoGen bridge connecting ElevenLabs to workers
✅ Client tool JSON configurations
✅ Documentation and examples

**Your Next Actions:**
1. Start the 3 services (host, worker, voice)
2. Configure client tools in ElevenLabs dashboard
3. Test with voice commands
4. (Optional) Implement web search API
5. (Optional) Add more workers for your use cases

**Test Commands:**
- "Learn from this URL: https://microsoft.github.io/autogen"
- "Fetch knowledge from https://example.com/docs"

**Expected Result:**
Agent successfully fetches URL, processes content, and speaks a summary!

---

🎉 **Phase 2 Complete!** You now have a distributed voice agent system powered by AutoGen gRPC.
