"""
Orchestrator - Central Hub for Hub-and-Spoke Pattern

This is the CENTRAL COORDINATOR that:
1. Discovers all available agents via the Discovery Service
2. Fetches their AgentCards to understand capabilities
3. Decides which agents to call and in what order
4. Passes data between agents (agents don't talk to each other!)
5. Maintains the workflow state

KEY DIFFERENCE FROM TRUE A2A:
- In hub-and-spoke: Orchestrator -> Agent A -> Orchestrator -> Agent B -> Orchestrator -> Agent C
- In TRUE A2A: Agent A -> Agent B -> Agent C (agents call each other directly)
"""

import asyncio
import uuid
import httpx
from a2a.client import A2AClient
from a2a.client.card_resolver import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    SendMessageRequest,
    Message,
    Part,
    TextPart,
)

from discovery_service import discover_agents, get_agent_urls, DISCOVERY_SERVICE_URL


class Orchestrator:
    """
    Central orchestrator that coordinates all agent interactions.

    This is the HUB in hub-and-spoke - all communication flows through here.
    """

    def __init__(self):
        self.discovered_agents: dict[str, AgentCard] = {}
        self.agent_clients: dict[str, A2AClient] = {}

    async def discover_agents_from_registry(self):
        """
        Discover all agents via the Discovery Service.

        This is a two-step process:
        1. Query the Discovery Service for registered agent URLs
        2. Fetch each agent's AgentCard using the A2A SDK's A2ACardResolver
        """
        print("\n" + "=" * 70)
        print("🔍 ORCHESTRATOR: Discovering agents via Discovery Service...")
        print("=" * 70)

        # Step 1: Get agent URLs from Discovery Service
        agent_urls = await get_agent_urls()

        if not agent_urls:
            print("   ⚠️  No agents registered with Discovery Service")
            print(f"      Make sure Discovery Service is running at {DISCOVERY_SERVICE_URL}")
            return

        print(f"   📋 Discovery Service returned {len(agent_urls)} agent(s)")

        # Step 2: Fetch AgentCards using A2A SDK
        async with httpx.AsyncClient() as client:
            for url in agent_urls:
                try:
                    # Use A2A SDK's A2ACardResolver to fetch the AgentCard
                    resolver = A2ACardResolver(httpx_client=client, base_url=url)
                    card = await resolver.get_agent_card()
                    self.discovered_agents[url] = card

                    # Create persistent A2A client for this agent
                    self.agent_clients[url] = A2AClient(
                        httpx_client=httpx.AsyncClient(timeout=120.0),
                        agent_card=card,
                    )

                    skills = [s.name for s in card.skills] if card.skills else []
                    print(f"   ✅ {card.name} at {url}")
                    print(f"      Skills: {', '.join(skills)}")

                except Exception as e:
                    print(f"   ❌ Failed to fetch AgentCard from {url}: {e}")

        print(f"\n   Discovered {len(self.discovered_agents)} agents")

    def find_agent_by_skill(self, skill_tag: str) -> tuple[str, AgentCard] | None:
        """Find an agent that has a specific skill tag."""
        for url, card in self.discovered_agents.items():
            if card.skills:
                for skill in card.skills:
                    if skill.tags and skill_tag in skill.tags:
                        return (url, card)
        return None

    async def call_agent(self, url: str, message: str) -> str:
        """Send a message to an agent and get the response."""
        client = self.agent_clients.get(url)
        card = self.discovered_agents.get(url)

        if not client or not card:
            return f"Error: Agent at {url} not discovered"

        print(f"\n   📤 Orchestrator calling {card.name}...")

        try:
            msg = Message(
                messageId=str(uuid.uuid4()),
                role="user",
                parts=[Part(root=TextPart(text=message))],
            )
            request = SendMessageRequest(
                id=str(uuid.uuid4()),
                params=MessageSendParams(message=msg),
            )

            response = await client.send_message(request)

            # Extract response text
            result_text = ""
            if hasattr(response, 'root') and response.root:
                resp = response.root
                if hasattr(resp, 'result') and resp.result:
                    result = resp.result
                    if hasattr(result, 'parts'):
                        for part in result.parts or []:
                            if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                result_text += part.root.text

            if not result_text:
                result_text = str(response)

            print(f"   📥 Orchestrator received response from {card.name} ({len(result_text)} chars)")
            return result_text

        except Exception as e:
            error_msg = f"Error calling {card.name}: {e}"
            print(f"   ❌ {error_msg}")
            return error_msg

    async def run_pipeline(self, task: str) -> str:
        """
        Run the full pipeline: Research -> Writer -> Security

        ALL coordination happens here in the orchestrator.
        Agents do NOT communicate with each other.
        """
        print("\n" + "=" * 70)
        print("🎯 ORCHESTRATOR: Starting pipeline")
        print("=" * 70)
        print(f"\nTask: {task}")

        # Step 1: Call Research Agent
        print("\n" + "-" * 70)
        print("STEP 1: Research")
        print("-" * 70)
        research_agent = self.find_agent_by_skill("research")
        if not research_agent:
            return "Error: No research agent found"

        research_url, research_card = research_agent
        research_result = await self.call_agent(research_url, task)

        # Step 2: Orchestrator passes research to Writer Agent
        print("\n" + "-" * 70)
        print("STEP 2: Writing (orchestrator passes research findings)")
        print("-" * 70)
        writer_agent = self.find_agent_by_skill("writing")
        if not writer_agent:
            return f"Research complete but no writer agent found.\n\n{research_result}"

        writer_url, writer_card = writer_agent
        writer_task = f"""Based on the following research findings, please write a well-structured guide.

RESEARCH FINDINGS:
---
{research_result}
---

Please create a polished, reader-friendly guide from this research."""

        writer_result = await self.call_agent(writer_url, writer_task)

        # Step 3: Orchestrator passes written content to Security Agent
        print("\n" + "-" * 70)
        print("STEP 3: Security scan (orchestrator passes written content)")
        print("-" * 70)
        security_agent = self.find_agent_by_skill("security")
        if not security_agent:
            return f"Writing complete but no security agent found.\n\n{writer_result}"

        security_url, security_card = security_agent
        security_task = f"""Please scan the following content for any exposed secrets, credentials, API keys, or sensitive data.

CONTENT TO SCAN:
---
{writer_result}
---

Provide a security assessment and confirm if it's safe to publish."""

        security_result = await self.call_agent(security_url, security_task)

        # Combine final result
        final_result = f"""## Hub-and-Spoke Pipeline Complete

### Flow: Orchestrator -> Research -> Orchestrator -> Writer -> Orchestrator -> Security

---

### Research Summary:
{research_result[:500]}...

---

### Written Content:
{writer_result}

---

### Security Scan:
{security_result}"""

        return final_result


async def main():
    """Main entry point."""
    print("\n" + "=" * 70)
    print("🌟 HUB-AND-SPOKE PATTERN DEMO")
    print("   Central Orchestrator Coordinates All Agents")
    print("=" * 70)
    print("""
This demo shows the HUB-AND-SPOKE pattern:

┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│     ┌───────────────────┐                                       │
│     │ Discovery Service │ ◄── Agents register on startup       │
│     └─────────┬─────────┘                                       │
│               │                                                 │
│               ▼                                                 │
│      ┌─────────────────┐                                        │
│      │  ORCHESTRATOR   │ ◄── Queries Discovery Service         │
│      │   (Central Hub) │                                        │
│      └────────┬────────┘                                        │
│               │                                                 │
│  ┌────────────┼────────────────┐                                │
│  │            │                │                                │
│  ▼            ▼                ▼                                │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│ │ Research │ │  Writer  │ │ Security │                         │
│ │  Agent   │ │  Agent   │ │  Agent   │                         │
│ └──────────┘ └──────────┘ └──────────┘                         │
│                                                                 │
│   Agents do NOT talk to each other!                            │
│   All data flows through the orchestrator.                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
""")

    orchestrator = Orchestrator()

    # Discover agents via Discovery Service
    await orchestrator.discover_agents_from_registry()

    # Run the pipeline
    task = """Research best practices for storing API credentials in Python applications,
then create a guide about it."""

    result = await orchestrator.run_pipeline(task)

    print("\n" + "=" * 70)
    print("🎉 PIPELINE COMPLETE")
    print("=" * 70)
    print("\nFinal Result:")
    print("-" * 70)
    print(result[:3000] if len(result) > 3000 else result)


if __name__ == "__main__":
    asyncio.run(main())
