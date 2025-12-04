# True A2A (Agent-to-Agent) Pattern Demo

This example demonstrates **True Agent-to-Agent** communication using Google's A2A protocol, where agents discover and call each other directly without a central orchestrator.

## Architecture Overview

```
┌───────────────────┐
│ Discovery Service │ ◄── Agents register and query for peers
└─────────┬─────────┘
          │
 ┌────────┴────────┐
 │                 │
 ▼                 ▼
User ──► Research ──► Writer ──► Security
          Agent        Agent       Agent
            │            │           │
            ▼            ▼           ▼
        Research     Writing     Security
        + Query      + Query     Scan
        Discovery    Discovery   (end)
        + Call A2A   + Call A2A
```

**Key Characteristic**: Agents discover and communicate with each other **directly**. There is no central orchestrator routing messages. Each agent autonomously decides when and how to delegate to other agents.

## How It Adheres to the A2A Protocol

### 1. Self-Registration and Discovery

Agents register themselves with the Discovery Service on startup, and query it to find peers:

```python
from discovery_service import register_with_discovery, discover_agent_by_skill

# On startup
await register_with_discovery("http://localhost:10001/")

# When needing another agent
agent = await discover_agent_by_skill("writing")
```

### 2. AgentCard-Based Capability Discovery

Each agent publishes an **AgentCard** with semantic skill tags that enable capability-based discovery:

```python
from a2a.types import AgentCard, AgentSkill

agent_card = AgentCard(
    name="Writer Agent",
    skills=[
        AgentSkill(
            id="write_content",
            name="Write Content",
            tags=["writing", "content", "documentation"],  # ◄── Semantic tags
        )
    ],
)
```

### 3. A2AClientMixin for Peer-to-Peer Communication

The `A2AClientMixin` enables any agent to discover and call other agents:

```python
from a2a.client import A2AClient
from a2a.client.card_resolver import A2ACardResolver

class A2AClientMixin:
    async def discover_agent(self, agent_url: str) -> AgentCard:
        resolver = A2ACardResolver(httpx_client=client, base_url=agent_url)
        return await resolver.get_agent_card()

    async def call_agent(self, agent_url: str, message: str) -> str:
        client = A2AClient(httpx_client=http_client, agent_card=card)
        response = await client.send_message(request)
        return extract_text(response)

    async def find_agent_with_skill(self, skill_tag: str) -> str | None:
        # Query Discovery Service for agent with this skill
        agent = await discover_agent_by_skill(skill_tag)
        return agent.url if agent else None
```

### 4. Agents as Both Servers AND Clients

In True A2A, each agent is **both** an A2A server (receiving requests) and an A2A client (making requests to peers):

```python
class WriterAgentExecutor(AgentExecutor, A2AClientMixin):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # 1. Do our work
        content = await self.write_content(context.message)

        # 2. Find and call another agent (TRUE A2A!)
        security_url = await self.find_agent_with_skill("security")
        if security_url:
            security_result = await self.call_agent(security_url, content)

        # 3. Return combined result
        await event_queue.enqueue_event(new_agent_text_message(final_result))
```

### 5. Chained Agent Calls

The A2A protocol enables chained workflows where results bubble back through the call stack:

```
User calls Research Agent
  └─► Research Agent calls Writer Agent
        └─► Writer Agent calls Security Agent
              └─► Security returns to Writer
        └─► Writer returns to Research
  └─► Research returns to User
```

## A2A SDK Components Used

| Component | Purpose |
|-----------|---------|
| `AgentCard` | Self-describing agent manifest with skills |
| `AgentSkill` | Declares capabilities with semantic tags |
| `A2ACardResolver` | Fetches AgentCards from peer agents |
| `A2AClient` | Sends A2A messages to peer agents |
| `A2AStarletteApplication` | HTTP server implementing A2A protocol |
| `AgentExecutor` | Base class for agent logic (extended with A2AClientMixin) |
| `EventQueue` | Returns results to callers |
| `Message`, `Part`, `TextPart` | A2A message types |

## How A2A Differs from MCP (Model Context Protocol)

| Aspect | A2A Protocol | MCP Protocol |
|--------|--------------|--------------|
| **Purpose** | Autonomous agent collaboration | Model-controlled tool invocation |
| **Agency** | Agents decide when to call peers | Model decides when to call tools |
| **Discovery** | Dynamic via AgentCards + skill tags | Static tool manifest at startup |
| **Communication** | Peer-to-peer HTTP/JSON-RPC | Client-server (model → tools) |
| **Chaining** | Agents chain to other agents | Tools don't call other tools |
| **Identity** | Rich agent identity (name, provider, icon) | Simple tool name + schema |
| **State** | Task-based with persistence | Stateless invocations |
| **Transport** | HTTP, gRPC, WebSocket | Stdio, SSE |

### Key Philosophical Differences

1. **Autonomy**: A2A agents are autonomous decision-makers. They can choose whether, when, and how to involve other agents. MCP tools are passive - they only execute when invoked by the model.

2. **Peer Relationships**: In A2A, agents are peers that collaborate. In MCP, the model is the controller and tools are subordinate capabilities.

3. **Dynamic Composition**: A2A agents can dynamically discover and compose with other agents based on capabilities. MCP tools are statically configured.

4. **Chaining**: A2A naturally supports agent chains (A → B → C). MCP tools are typically invoked individually by the model.

5. **Protocol vs Interface**: A2A is a protocol for agent interoperability. MCP is an interface for extending model capabilities.

### Contract Differences

**A2A AgentCard** (rich, semantic):
```json
{
  "name": "Writer Agent",
  "description": "Creates polished content",
  "url": "http://localhost:10002/",
  "skills": [
    {
      "id": "write_content",
      "name": "Write Content",
      "description": "Create well-written content",
      "tags": ["writing", "content"]
    }
  ],
  "capabilities": {"streaming": true}
}
```

**MCP Tool Manifest** (schema-focused):
```json
{
  "name": "write_content",
  "description": "Write content",
  "inputSchema": {
    "type": "object",
    "properties": {
      "topic": {"type": "string"},
      "style": {"type": "string"}
    }
  }
}
```

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
2. **All agents** start and register themselves with Discovery Service
3. **User** calls Research Agent directly
4. **Research Agent**:
   - Performs research
   - Queries Discovery Service for "writing" skill
   - Calls Writer Agent directly (A2A!)
5. **Writer Agent**:
   - Writes content based on research
   - Queries Discovery Service for "security" skill
   - Calls Security Agent directly (A2A!)
6. **Security Agent**:
   - Scans content for secrets
   - Returns result to Writer Agent
7. **Writer Agent** returns combined result to Research Agent
8. **Research Agent** returns final result to User

## Files

| File | Description |
|------|-------------|
| `run_demo.py` | Entry point - starts services and triggers chain |
| `discovery_service.py` | Agent registration and discovery service |
| `a2a_client_mixin.py` | Mixin enabling agents to call other agents |
| `research_agent.py` | Research agent (chains to Writer) |
| `writer_agent.py` | Writer agent (chains to Security) |
| `security_agent.py` | Security agent (end of chain) |
| `base_llm.py` | AWS Bedrock LLM wrapper |

## Why True A2A?

**Advantages:**
- Decentralized, no single point of failure
- Agents can dynamically compose workflows
- More flexible collaboration patterns
- Agents can specialize and scale independently
- Natural fit for complex multi-agent systems

**Disadvantages:**
- More complex to debug (distributed tracing needed)
- Agents need discovery capability
- Potential for circular calls if not careful
- Each agent needs to understand when to delegate

Compare with the [hub_and_spoke](../hub_and_spoke/) example for a centralized approach.

## The "True" in True A2A

This pattern is called "True A2A" because it demonstrates the full potential of the A2A protocol:

1. **Agent Autonomy**: Each agent independently decides to collaborate
2. **Dynamic Discovery**: Agents find each other through capability-based search
3. **Direct Communication**: No intermediary routing messages
4. **Peer Relationships**: Agents are equals, not controller/subordinate
5. **Composable Workflows**: Complex behaviors emerge from simple agent interactions

This is what Google designed the A2A protocol for - enabling a world where AI agents from different vendors can discover, communicate, and collaborate autonomously.
