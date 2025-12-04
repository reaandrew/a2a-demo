# ADK + A2A: Google's Intended Pattern

This example demonstrates **how Google intended A2A to be used** with their Agent Development Kit (ADK). This is fundamentally different from the other examples in this repository.

## The Key Difference

| Previous Examples | This Example (ADK + A2A) |
|-------------------|--------------------------|
| Hardcoded workflow: research → writer → security | LLM decides the workflow dynamically |
| Manual A2A client calls | `RemoteA2aAgent` wraps remote agents as sub-agents |
| Hardcoded agent URLs | **Dynamic agent discovery via Discovery Service** |
| `AgentExecutor` subclasses | ADK `Agent` with tools and instructions |
| We controlled the routing | The model controls the routing |

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│            ┌───────────────────────────────────┐                 │
│            │       DISCOVERY SERVICE           │                 │
│            │   Agents register on startup      │                 │
│            │   Host queries for available      │                 │
│            │   :9999                           │                 │
│            └───────────────────────────────────┘                 │
│                    ▲               │                             │
│                    │ register      │ discover                    │
│                    │               ▼                             │
│                        ┌─────────────┐                           │
│                        │ HOST AGENT  │                           │
│                        │  (Bedrock)  │                           │
│                        └──────┬──────┘                           │
│                               │                                  │
│              LLM decides which agent(s) to call                  │
│              based on task understanding                         │
│                               │                                  │
│              ┌────────────────┼────────────────┐                 │
│              │                │                │                 │
│              ▼                ▼                ▼                 │
│     ┌────────────────┐ ┌────────────┐ ┌────────────────┐        │
│     │ RemoteA2aAgent │ │RemoteA2a   │ │ RemoteA2aAgent │        │
│     │   (research)   │ │Agent(write)│ │   (security)   │        │
│     └───────┬────────┘ └─────┬──────┘ └───────┬────────┘        │
│             │ A2A            │ A2A            │ A2A              │
│             ▼                ▼                ▼                  │
│     ┌────────────────┐ ┌────────────┐ ┌────────────────┐        │
│     │ Research Agent │ │Writer Agent│ │ Security Agent │        │
│     │   to_a2a()     │ │  to_a2a()  │ │   to_a2a()     │        │
│     │   :10001       │ │  :10002    │ │   :10003       │        │
│     └────────────────┘ └────────────┘ └────────────────┘        │
│                                                                  │
│   KEY: Discovery Service finds agents, LLM decides what to use! │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Discovery Service

The A2A protocol doesn't include a discovery mechanism - you must know agent URLs upfront. This example includes a **Discovery Service** that allows:

1. **Agents register themselves on startup** - Each agent POSTs to `/register` with its URL
2. **Host agent queries for available agents** - The host calls GET `/agents` to discover registered agents
3. **Dynamic sub-agent creation** - The host creates `RemoteA2aAgent` instances for each discovered agent

This separation means:
- **Discovery Service** determines which agents EXIST (infrastructure layer)
- **Host Agent's LLM** decides which agents to CALL (application layer)

In production, this could be replaced with Consul, Kubernetes service discovery, AWS Cloud Map, etc.

## What Makes This "True" ADK + A2A

### 1. `to_a2a()` - Official Way to Expose Agents

```python
from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# Define agent with ADK (using Bedrock via LiteLLM)
research_agent = Agent(
    name="research_agent",
    description="Researches topics...",
    model=LiteLlm(model="bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
    instruction="You are a Research Agent...",
    tools=[research_topic],  # Tools become agent capabilities
)

# Expose via A2A - automatically generates AgentCard
app = to_a2a(research_agent, host="localhost", port=10001)
```

**What `to_a2a()` does:**
- Generates `AgentCard` from agent definition (name, description, tools)
- Sets up A2A JSON-RPC endpoints
- Handles message conversion between ADK and A2A formats
- Serves the card at `/.well-known/agent-card.json`

### 2. `RemoteA2aAgent` - Transparent Remote Agents

```python
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH

# Wrap remote A2A agent as a local sub-agent
research = RemoteA2aAgent(
    name="research_agent",
    description="Researches topics...",
    agent_card=f"http://localhost:10001{AGENT_CARD_WELL_KNOWN_PATH}",
)

# Use as sub-agent - LLM can now delegate to it
host = Agent(
    name="host",
    model=LiteLlm(model="bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
    sub_agents=[research, writer, security],  # Remote agents look local!
)
```

**What `RemoteA2aAgent` does:**
- Fetches and validates the AgentCard
- Sets up A2A client communication
- Converts ADK events to/from A2A messages
- Makes remote agents appear as local sub-agents

### 3. LLM-Driven Routing (The Key Innovation)

In our previous examples:
```python
# Hardcoded routing - WE decide the workflow
research_result = await call_research_agent(task)
writer_result = await call_writer_agent(research_result)
security_result = await call_security_agent(writer_result)
```

In ADK + A2A:
```python
# LLM routing - THE MODEL decides the workflow
host = Agent(
    instruction="You have access to research, writer, and security agents...",
    sub_agents=[research, writer, security],
)
# The LLM reads the task, understands sub-agent capabilities, and decides:
# - Which agents to call
# - In what order
# - What to pass between them
```

## ADK Components Used

| Component | Purpose |
|-----------|---------|
| `Agent` | Define agents with model, instruction, and tools |
| `to_a2a()` | Expose ADK agent as A2A server |
| `RemoteA2aAgent` | Wrap remote A2A agent as sub-agent |
| `Runner` | Execute agent with session management |
| `InMemorySessionService` | Manage conversation sessions |
| `AGENT_CARD_WELL_KNOWN_PATH` | Standard path for AgentCards |

## A2A Protocol Features Used

| Feature | How It's Used |
|---------|---------------|
| AgentCard | Auto-generated from Agent definition via `to_a2a()` |
| Well-known path | `/.well-known/agent-card.json` served automatically |
| JSON-RPC messages | Handled by `A2aAgentExecutor` |
| Task state | Managed by `InMemoryTaskStore` |
| Message conversion | ADK ↔ A2A via converters |

## Running the Demo

### Prerequisites

1. **AWS Credentials** (for Bedrock via LiteLLM):
   ```bash
   # Configure AWS credentials with access to Bedrock
   aws configure
   # Or use aws-vault:
   aws-vault exec <profile> -- python run_demo.py
   ```

2. **Install dependencies**:
   ```bash
   pip install "google-adk[a2a]" litellm
   ```

### Run

```bash
cd examples/adk_a2a
aws-vault exec <profile> -- python run_demo.py
```

Or with a custom task:
```bash
aws-vault exec <profile> -- python run_demo.py "Research Python async patterns and write a tutorial"
```

### Alternative: ADK Web Interface

```bash
# Start remote agents manually in separate terminals
python research_agent.py
python writer_agent.py
python security_agent.py

# Then run with ADK's web interface
adk web .
```

## Why This Matters

### The Problem with Our Previous Examples

We built A2A clients manually and hardcoded the workflow:
1. Always call research first
2. Always pass to writer second
3. Always send to security third

This is **just HTTP with extra steps**. The A2A protocol was being used, but not its value.

### The ADK + A2A Solution

With `RemoteA2aAgent`, remote agents become transparent sub-agents that the LLM can invoke. The model:

1. **Understands the task** - "Create a guide about API security"
2. **Knows available agents** - Research, Writer, Security (from their descriptions)
3. **Plans the workflow** - "I should research first, then write, then verify"
4. **Executes dynamically** - Calls agents in the order it determines

### Adaptive by Design

Add a new agent (e.g., spell-checker):
```python
spell_checker = RemoteA2aAgent(
    name="spell_checker",
    description="Checks and corrects spelling and grammar",
    agent_card="http://localhost:10004/.well-known/agent-card.json",
)

host = Agent(
    sub_agents=[research, writer, security, spell_checker],  # Just add it!
)
```

The LLM will **automatically** consider using the spell-checker when appropriate, because it can read the description and understand when it's relevant.

## Comparison: MCP vs A2A

| Aspect | MCP (Model Context Protocol) | A2A (Agent-to-Agent) |
|--------|------------------------------|----------------------|
| **Who calls** | Model calls tools | Agent calls agents |
| **Intelligence** | Tools are passive functions | Agents are intelligent entities |
| **Routing** | Model selects tool by name/schema | LLM understands agent capabilities |
| **Chaining** | Model orchestrates tool sequence | Agents can orchestrate other agents |
| **Discovery** | Static tool manifest | Dynamic AgentCard discovery |
| **State** | Stateless tool calls | Task-based with state tracking |
| **Use case** | Extend model with capabilities | Build multi-agent systems |

**Key insight**: MCP extends what a model can DO. A2A extends what agents can DELEGATE.

## Files

| File | Description |
|------|-------------|
| `discovery_service.py` | Agent Discovery Service - agents register here, host queries here |
| `research_agent.py` | Research agent exposed via `to_a2a()`, registers with Discovery Service |
| `writer_agent.py` | Writer agent exposed via `to_a2a()`, registers with Discovery Service |
| `security_agent.py` | Security agent exposed via `to_a2a()`, registers with Discovery Service |
| `host_agent.py` | Host agent - discovers agents dynamically, uses `RemoteA2aAgent` sub-agents |
| `run_demo.py` | Demo runner - starts Discovery Service, then agents, then runs host |

## References

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [ADK A2A Documentation](https://google.github.io/adk-docs/a2a/)
- [A2A Protocol Specification](https://github.com/google/A2A)
- [Official A2A Samples](https://github.com/a2aproject/a2a-samples)
