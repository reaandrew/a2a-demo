"""
A2A Client Mixin - Enables agents to discover and call other agents directly.

This is the key to TRUE Agent-to-Agent communication:
- Each agent can query the Discovery Service to find other agents
- Each agent can discover other agents via their AgentCards (A2A SDK)
- Each agent can decide to delegate work to other agents
- Agents communicate peer-to-peer, not through a central orchestrator

"""

import httpx
import uuid
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

from discovery_service import get_agent_urls, discover_agent_by_skill, DISCOVERY_SERVICE_URL


class A2AClientMixin:
    """
    Mixin that gives any agent the ability to discover and call other agents.

    This enables TRUE A2A - agents talking directly to agents.

    Uses the Discovery Service to find available agents, then uses the
    A2A SDK's A2ACardResolver to fetch AgentCards and A2AClient to communicate.
    """

    def __init__(self):
        self._discovered_agents: dict[str, AgentCard] = {}
        self._agent_clients: dict[str, A2AClient] = {}

    async def discover_agent(self, agent_url: str) -> AgentCard | None:
        """
        Discover an agent by fetching its AgentCard.

        Args:
            agent_url: Base URL of the agent (e.g., "http://localhost:10002/")

        Returns:
            AgentCard if successful, None otherwise
        """
        if agent_url in self._discovered_agents:
            return self._discovered_agents[agent_url]

        try:
            async with httpx.AsyncClient() as client:
                resolver = A2ACardResolver(
                    httpx_client=client,
                    base_url=agent_url,
                )
                card = await resolver.get_agent_card()

                self._discovered_agents[agent_url] = card
                self._agent_clients[agent_url] = A2AClient(
                    httpx_client=httpx.AsyncClient(timeout=120.0),
                    agent_card=card,
                )

                print(f"      🔍 Discovered agent: {card.name} at {agent_url}")
                return card

        except Exception as e:
            print(f"      ❌ Failed to discover agent at {agent_url}: {e}")
            return None

    async def call_agent(self, agent_url: str, message: str) -> str:
        """
        Send a message to another agent and get the response.

        This is TRUE A2A - one agent directly calling another agent.

        Args:
            agent_url: URL of the agent to call
            message: The message/task to send

        Returns:
            The agent's response text
        """
        # Ensure we've discovered this agent
        if agent_url not in self._agent_clients:
            card = await self.discover_agent(agent_url)
            if not card:
                return f"Error: Could not discover agent at {agent_url}"

        client = self._agent_clients[agent_url]
        card = self._discovered_agents[agent_url]

        print(f"      📤 Calling {card.name}...")

        try:
            # Build A2A message
            msg = Message(
                messageId=str(uuid.uuid4()),
                role="user",
                parts=[Part(root=TextPart(text=message))],
            )
            request = SendMessageRequest(
                id=str(uuid.uuid4()),
                params=MessageSendParams(message=msg),
            )

            # Send to peer agent
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

            print(f"      📥 Received response from {card.name} ({len(result_text)} chars)")
            return result_text

        except Exception as e:
            error_msg = f"Error calling {card.name}: {e}"
            print(f"      ❌ {error_msg}")
            return error_msg

    async def find_agent_with_skill(self, skill_tag: str) -> str | None:
        """
        Find an agent that has a specific skill using the Discovery Service.

        This is the key to dynamic agent discovery in TRUE A2A:
        1. Query the Discovery Service for an agent with the required skill
        2. The Discovery Service returns the agent URL
        3. We can then call that agent directly using the A2A protocol

        Args:
            skill_tag: The skill tag to look for (e.g., "writing", "security")

        Returns:
            URL of an agent with that skill, or None
        """
        # Query Discovery Service for an agent with this skill
        agent = await discover_agent_by_skill(skill_tag)
        if agent:
            print(f"      ✅ Discovery Service found agent with '{skill_tag}' skill: {agent.name}")
            return agent.url

        # Fallback: Search through all registered agents
        print(f"      🔍 Discovery Service direct lookup failed, scanning all agents...")
        agent_urls = await get_agent_urls()
        for url in agent_urls:
            card = await self.discover_agent(url)
            if card and card.skills:
                for skill in card.skills:
                    if skill.tags and skill_tag in skill.tags:
                        print(f"      ✅ Found agent with '{skill_tag}' skill: {card.name}")
                        return url

        print(f"      ❌ No agent found with '{skill_tag}' skill")
        return None
