"""
Agent Discovery Service - Central Registry for A2A Agents

This service provides a central registry where agents can:
1. REGISTER themselves on startup
2. DISCOVER other agents by querying the registry

This is a lightweight implementation that complements the A2A protocol's
self-describing AgentCard mechanism. While A2A agents publish their cards
at /.well-known/agent-card.json, this registry provides a way to discover
WHICH agents exist without knowing their URLs upfront.

In production, this could be replaced with:
- Consul / etcd / ZooKeeper
- Kubernetes service discovery
- AWS Cloud Map
- A dedicated agent registry service
"""

import asyncio
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from a2a.client.card_resolver import A2ACardResolver
from a2a.types import AgentCard

# Default port for the discovery service
DISCOVERY_SERVICE_PORT = 9999
DISCOVERY_SERVICE_URL = f"http://localhost:{DISCOVERY_SERVICE_PORT}"


class AgentRegistration(BaseModel):
    """Request to register an agent with the discovery service."""
    url: str  # Base URL of the agent (e.g., "http://localhost:10001/")


class RegisteredAgent(BaseModel):
    """An agent registered in the discovery service."""
    url: str
    name: str
    description: str
    skills: list[str]  # Skill tags for capability-based discovery


# In-memory registry (in production, use a persistent store)
_registered_agents: dict[str, RegisteredAgent] = {}

app = FastAPI(
    title="A2A Agent Discovery Service",
    description="Central registry for discovering A2A agents",
    version="1.0.0",
)


@app.post("/register")
async def register_agent(registration: AgentRegistration) -> RegisteredAgent:
    """
    Register an agent with the discovery service.

    The service will fetch the agent's AgentCard to validate it exists
    and extract its metadata (name, description, skills).
    """
    url = registration.url.rstrip("/") + "/"

    try:
        # Fetch the agent's AgentCard using the A2A SDK
        async with httpx.AsyncClient(timeout=10.0) as client:
            resolver = A2ACardResolver(httpx_client=client, base_url=url)
            card: AgentCard = await resolver.get_agent_card()

        # Extract skill tags
        skill_tags = []
        if card.skills:
            for skill in card.skills:
                if skill.tags:
                    skill_tags.extend(skill.tags)

        # Register the agent
        registered = RegisteredAgent(
            url=url,
            name=card.name,
            description=card.description or "",
            skills=list(set(skill_tags)),  # Deduplicate
        )
        _registered_agents[url] = registered

        print(f"[Discovery] Registered: {card.name} at {url}")
        print(f"            Skills: {', '.join(skill_tags)}")

        return registered

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to register agent at {url}: {str(e)}"
        )


@app.delete("/unregister")
async def unregister_agent(url: str) -> dict:
    """Unregister an agent from the discovery service."""
    url = url.rstrip("/") + "/"
    if url in _registered_agents:
        agent = _registered_agents.pop(url)
        print(f"[Discovery] Unregistered: {agent.name}")
        return {"status": "unregistered", "agent": agent.name}
    raise HTTPException(status_code=404, detail=f"Agent not found: {url}")


@app.get("/agents")
async def list_agents() -> list[RegisteredAgent]:
    """List all registered agents."""
    return list(_registered_agents.values())


@app.get("/agents/by-skill/{skill_tag}")
async def find_agents_by_skill(skill_tag: str) -> list[RegisteredAgent]:
    """Find agents that have a specific skill tag."""
    return [
        agent for agent in _registered_agents.values()
        if skill_tag in agent.skills
    ]


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "registered_agents": len(_registered_agents)}


# ============================================================================
# Client functions for agents to use
# ============================================================================

async def register_with_discovery(agent_url: str, discovery_url: str = DISCOVERY_SERVICE_URL) -> bool:
    """
    Register this agent with the discovery service.

    Call this on agent startup to make the agent discoverable.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{discovery_url}/register",
                json={"url": agent_url},
            )
            if response.status_code == 200:
                return True
            print(f"[Discovery] Registration failed: {response.text}")
            return False
    except Exception as e:
        print(f"[Discovery] Could not reach discovery service: {e}")
        return False


async def discover_agents(discovery_url: str = DISCOVERY_SERVICE_URL) -> list[RegisteredAgent]:
    """
    Get all registered agents from the discovery service.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{discovery_url}/agents")
            if response.status_code == 200:
                return [RegisteredAgent(**a) for a in response.json()]
    except Exception as e:
        print(f"[Discovery] Could not reach discovery service: {e}")
    return []


async def discover_agent_by_skill(
    skill_tag: str,
    discovery_url: str = DISCOVERY_SERVICE_URL
) -> RegisteredAgent | None:
    """
    Find an agent with a specific skill tag.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{discovery_url}/agents/by-skill/{skill_tag}")
            if response.status_code == 200:
                agents = response.json()
                if agents:
                    return RegisteredAgent(**agents[0])
    except Exception as e:
        print(f"[Discovery] Could not reach discovery service: {e}")
    return None


async def get_agent_urls(discovery_url: str = DISCOVERY_SERVICE_URL) -> list[str]:
    """
    Get URLs of all registered agents.
    """
    agents = await discover_agents(discovery_url)
    return [a.url for a in agents]


# ============================================================================
# Run as standalone service
# ============================================================================

def run_discovery_service(port: int = DISCOVERY_SERVICE_PORT):
    """Run the discovery service."""
    print("=" * 70)
    print("A2A AGENT DISCOVERY SERVICE")
    print("=" * 70)
    print(f"""
This service allows A2A agents to:
  - Register themselves: POST /register
  - Discover other agents: GET /agents
  - Find agents by skill: GET /agents/by-skill/{{skill_tag}}

Endpoints:
  - http://localhost:{port}/register     (POST)
  - http://localhost:{port}/agents       (GET)
  - http://localhost:{port}/agents/by-skill/{{tag}} (GET)
  - http://localhost:{port}/health       (GET)
  - http://localhost:{port}/docs         (Swagger UI)
""")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    run_discovery_service()
