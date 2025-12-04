# Hub-and-Spoke Pattern Demo

This example demonstrates the **Hub-and-Spoke** architectural pattern for multi-agent systems using Google's A2A (Agent-to-Agent) protocol.

## Architecture Overview

```
┌───────────────────┐
│ Discovery Service │ ◄── Agents register on startup
└─────────┬─────────┘
          │
          ▼
 ┌─────────────────┐
 │  ORCHESTRATOR   │ ◄── Queries Discovery Service
 │   (Central Hub) │     Fetches AgentCards via A2A SDK
 └────────┬────────┘
          │
 ┌────────┼────────────────┐
 │        │                │
 ▼        ▼                ▼
┌────────┐ ┌────────┐ ┌────────┐
│Research│ │ Writer │ │Security│
│ Agent  │ │ Agent  │ │ Agent  │
└────────┘ └────────┘ └────────┘
```

**Key Characteristic**: All communication flows through the central orchestrator. Agents **never** communicate directly with each other.

## How It Adheres to the A2A Protocol

### 1. AgentCard Discovery

Each agent publishes a self-describing **AgentCard** at the well-known path `/.well-known/agent-card.json`. This is the foundation of A2A's discovery mechanism:

```python
from a2a.types import AgentCard, AgentSkill, AgentCapabilities

agent_card = AgentCard(
    name="Research Agent",
    description="Gathers information and provides research findings",
    url="http://localhost:10001/",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(
            id="research",
            name="Research Topic",
            description="Research any topic",
            tags=["research", "analysis"],
        )
    ],
)
```

### 2. A2ACardResolver for Discovery

The orchestrator uses the A2A SDK's `A2ACardResolver` to fetch AgentCards:

```python
from a2a.client.card_resolver import A2ACardResolver

resolver = A2ACardResolver(httpx_client=client, base_url=agent_url)
card = await resolver.get_agent_card()
```

### 3. A2AClient for Communication

Communication uses the A2A SDK's `A2AClient` with proper message types:

```python
from a2a.client import A2AClient
from a2a.types import Message, Part, TextPart, MessageSendParams, SendMessageRequest

client = A2AClient(httpx_client=http_client, agent_card=card)

msg = Message(
    messageId=str(uuid.uuid4()),
    role="user",
    parts=[Part(root=TextPart(text="Your task here"))],
)
request = SendMessageRequest(
    id=str(uuid.uuid4()),
    params=MessageSendParams(message=msg),
)
response = await client.send_message(request)
```

### 4. A2AStarletteApplication for Serving

Agents use the SDK's `A2AStarletteApplication` to serve the A2A protocol:

```python
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler

server = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=request_handler,
)
```

### 5. AgentExecutor for Task Handling

Each agent implements an `AgentExecutor` to handle incoming requests:

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

class ResearchAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Process the request
        result = await self.do_research(context.message)
        # Return result via event queue
        await event_queue.enqueue_event(new_agent_text_message(result))
```

## A2A SDK Components Used

| Component | Purpose |
|-----------|---------|
| `AgentCard` | Self-describing agent manifest |
| `AgentSkill` | Declares agent capabilities with tags |
| `AgentCapabilities` | Declares supported features (streaming, etc.) |
| `A2ACardResolver` | Fetches AgentCards from agents |
| `A2AClient` | Sends messages to agents |
| `A2AStarletteApplication` | HTTP server implementing A2A protocol |
| `DefaultRequestHandler` | Handles incoming A2A requests |
| `AgentExecutor` | Base class for implementing agent logic |
| `InMemoryTaskStore` | Stores task state |
| `EventQueue` | Returns results to callers |
| `Message`, `Part`, `TextPart` | A2A message types |

## How A2A Differs from MCP (Model Context Protocol)

| Aspect | A2A Protocol | MCP Protocol |
|--------|--------------|--------------|
| **Purpose** | Agent-to-Agent communication | Model-to-Tool communication |
| **Discovery** | AgentCards at `/.well-known/agent-card.json` | Tool manifests via capability negotiation |
| **Communication** | HTTP/JSON-RPC between autonomous agents | Stdio/SSE between model and tools |
| **Architecture** | Decentralized peer network | Client-server (model = client, tools = server) |
| **Message Format** | JSON-RPC 2.0 with A2A message types | JSON-RPC 2.0 with MCP-specific types |
| **Capabilities** | Skills with semantic tags | Tools with JSON Schema parameters |
| **State** | Task-based with task IDs | Stateless tool invocations |
| **Streaming** | Built-in streaming support | SSE-based streaming |
| **Use Case** | Multi-agent orchestration | Extending model capabilities |

### Key Conceptual Differences

1. **Autonomy**: A2A agents are autonomous entities that can make decisions. MCP tools are passive capabilities invoked by a model.

2. **Discovery**: A2A uses well-known URIs and semantic skill tags. MCP uses capability negotiation at connection time.

3. **Identity**: A2A agents have rich identities (name, description, provider, icon). MCP tools are identified by name and schema.

4. **Routing**: A2A supports skill-based routing (find agent with "writing" skill). MCP tools are invoked by exact name.

## Running the Demo

```bash
# Install dependencies
pip install -r ../../requirements.txt
pip install a2a-sdk uvicorn httpx fastapi

# Run the demo
python run_demo.py

# Or with a custom task
python run_demo.py "Research Python async best practices and create a tutorial"
```

## Data Flow

1. **Discovery Service** starts on port 9999
2. **Agents** start and register themselves with Discovery Service
3. **Orchestrator** queries Discovery Service for available agents
4. **Orchestrator** fetches each agent's AgentCard using `A2ACardResolver`
5. **Orchestrator** calls Research Agent → receives results
6. **Orchestrator** calls Writer Agent with research → receives written content
7. **Orchestrator** calls Security Agent with content → receives security scan
8. **Orchestrator** combines results and returns to user

## Files

| File | Description |
|------|-------------|
| `run_demo.py` | Entry point - starts all services and runs pipeline |
| `orchestrator.py` | Central hub that coordinates all agents |
| `discovery_service.py` | Agent registration and discovery service |
| `research_agent.py` | Research capability agent |
| `writer_agent.py` | Content writing agent |
| `security_agent.py` | Security scanning agent |
| `base_llm.py` | AWS Bedrock LLM wrapper |

## Why Hub-and-Spoke?

**Advantages:**
- Centralized control and visibility
- Easier debugging (all traffic through one point)
- Simpler agent implementation (no peer discovery needed)
- Clear workflow orchestration

**Disadvantages:**
- Single point of failure
- Orchestrator bottleneck
- Less flexible than peer-to-peer
- Agents can't dynamically collaborate

Compare with the [true_a2a](../true_a2a/) example for a decentralized approach.
