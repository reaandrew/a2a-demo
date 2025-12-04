# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an A2A (Agent-to-Agent) protocol demonstration using Google's A2A Python SDK and Agent Development Kit (ADK). It showcases three architectural patterns for multi-agent systems, culminating in Google's intended approach.

## Running the Demos

Install dependencies:
```bash
pip install -r requirements.txt
pip install "google-adk[a2a]" uvicorn httpx fastapi
```

**ADK + A2A (Recommended - Google's intended pattern):**
```bash
# Requires AWS credentials for Bedrock (uses Claude via LiteLLM)
aws-vault exec <profile> -- python examples/adk_a2a/run_demo.py
# Or with environment variables:
python examples/adk_a2a/run_demo.py
```

Hub-and-spoke demo (central orchestrator):
```bash
python examples/hub_and_spoke/run_demo.py
```

True A2A demo (agents call each other directly):
```bash
python examples/true_a2a/run_demo.py
```

## Architecture

### Three Patterns Demonstrated

**ADK + A2A** (`examples/adk_a2a/`) - **Google's Intended Pattern**:
- Agents exposed via `to_a2a()` - official ADK function
- Host agent uses `RemoteA2aAgent` to wrap remote agents as sub-agents
- **LLM decides** which agent to call based on task understanding
- No hardcoded workflow - dynamic routing by the model
- Uses AWS Bedrock Claude via LiteLLM (requires AWS credentials)

**Hub-and-Spoke** (`examples/hub_and_spoke/`):
- Discovery Service allows agents to register themselves
- Central `Orchestrator` queries Discovery Service, then coordinates workflow
- Hardcoded workflow: Research → Writer → Security
- Uses AWS Bedrock for LLM

**True A2A** (`examples/true_a2a/`):
- Agents discover and call each other directly via the A2A protocol
- Hardcoded chaining: Research calls Writer, Writer calls Security
- Uses AWS Bedrock for LLM

### Key Difference: LLM Routing vs Hardcoded Routing

| Aspect | hub_and_spoke / true_a2a | adk_a2a |
|--------|--------------------------|---------|
| Routing | Hardcoded in code | LLM decides dynamically |
| Adding agents | Requires code changes | Just add to sub_agents list |
| Workflow | Fixed sequence | Model understands and plans |
| A2A usage | Protocol only | Protocol + ADK integration |

### Service Ports
- Discovery Service: 9999 (hub_and_spoke, true_a2a only)
- Research Agent: 10001
- Writer Agent: 10002
- Security Agent: 10003

## ADK + A2A Components

Key Google ADK components:
- `google.adk.agents.Agent` - Define agents with model, instruction, tools
- `google.adk.a2a.utils.agent_to_a2a.to_a2a()` - Expose agent as A2A server
- `google.adk.agents.remote_a2a_agent.RemoteA2aAgent` - Wrap remote A2A agent as sub-agent
- `google.adk.runners.Runner` - Execute agent with session management

## A2A SDK Components

Key A2A SDK components:
- `a2a.types.AgentCard`, `AgentSkill`, `AgentCapabilities` - Agent metadata
- `a2a.client.A2AClient` - Client for calling agents
- `a2a.client.card_resolver.A2ACardResolver` - Fetches AgentCards
- `a2a.server.apps.A2AStarletteApplication` - HTTP server
- `a2a.server.agent_execution.AgentExecutor` - Agent logic base class

## Environment Variables

- AWS credentials: Required for all examples (Bedrock via LiteLLM)
- `GITGUARDIAN_API_KEY`: Optional, enables GitGuardian API secret scanning
