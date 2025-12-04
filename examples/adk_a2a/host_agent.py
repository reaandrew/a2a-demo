"""
Host Agent - Orchestrates Remote A2A Agents via Google ADK

THIS IS THE KEY DIFFERENCE FROM OUR PREVIOUS EXAMPLES!

This host agent uses Google ADK's RemoteA2aAgent to:
1. DISCOVER available agents via the Discovery Service
2. Connect to remote A2A agents via their AgentCards
3. Treat them as SUB-AGENTS that the LLM can invoke
4. Let the LLM DECIDE which agent to call based on the task

The LLM sees all available agents (dynamically discovered!) as tools
and autonomously decides when to delegate to each one.

Key concepts demonstrated:
- Discovery Service: Dynamically finds available agents
- RemoteA2aAgent: Wraps remote A2A agents as local sub-agents
- LLM-driven routing: The model decides which agent to call
- Multi-agent orchestration: Automatic agent selection
- Transparent delegation: Remote calls look like local function calls
"""

import warnings
# Suppress experimental warnings from ADK
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH

from discovery_service import discover_agents, RegisteredAgent

# Use AWS Bedrock Claude via LiteLLM (EU region model)
BEDROCK_MODEL = LiteLlm(model="bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0")


async def create_host_agent_with_discovery() -> Agent:
    """
    Create the host agent by dynamically discovering available A2A agents.

    This queries the Discovery Service to find all registered agents,
    then creates RemoteA2aAgent instances for each one. The LLM can
    then decide to delegate tasks to any of these agents.
    """
    print("🔍 Discovering available agents from Discovery Service...")

    # Query the Discovery Service for all registered agents
    discovered_agents = await discover_agents()

    if not discovered_agents:
        print("⚠️  No agents discovered! Make sure agents are running and registered.")
        print("    Falling back to empty sub-agents list.")
        sub_agents = []
    else:
        print(f"✅ Discovered {len(discovered_agents)} agent(s):")

        # Create RemoteA2aAgent instances for each discovered agent
        sub_agents = []
        for agent_info in discovered_agents:
            print(f"   - {agent_info.name}: {agent_info.description[:60]}...")

            # Create a RemoteA2aAgent wrapper for each discovered agent
            remote_agent = RemoteA2aAgent(
                name=agent_info.name,
                description=agent_info.description,
                agent_card=f"{agent_info.url.rstrip('/')}{AGENT_CARD_WELL_KNOWN_PATH}",
            )
            sub_agents.append(remote_agent)

    # Build a dynamic instruction based on discovered agents
    agent_descriptions = "\n".join([
        f"- **{a.name}**: {a.description}"
        for a in discovered_agents
    ]) if discovered_agents else "No agents currently available."

    # Create the host agent with all discovered agents as sub-agents
    host = Agent(
        name="host_agent",
        description="Orchestrates tasks by delegating to dynamically discovered specialized agents.",
        model=BEDROCK_MODEL,  # Using AWS Bedrock Claude via LiteLLM
        instruction=f"""You are a Host Agent that orchestrates tasks by delegating to specialized agents.

You have access to the following agents (dynamically discovered):

{agent_descriptions}

Your job is to:
1. Understand what the user wants
2. Break down the task into steps
3. Delegate to the appropriate agent(s) based on their descriptions
4. Combine their outputs into a final result

Choose which agents to use based on the task requirements. Not all tasks need all agents.
The agents available may change over time as new agents are registered or removed.

Always explain what you're doing and why you're delegating to each agent.""",
        sub_agents=sub_agents,
    )

    return host


def create_host_agent_static() -> Agent:
    """
    Create the host agent with statically-defined remote agents.

    This is a fallback for when the Discovery Service is not available.
    Use create_host_agent_with_discovery() for dynamic agent discovery.
    """

    # Create RemoteA2aAgent instances for each remote agent
    research_agent = RemoteA2aAgent(
        name="research_agent",
        description="Researches topics and provides comprehensive findings. Use this agent when you need to gather information, analyze topics, or research best practices.",
        agent_card=f"http://localhost:10001{AGENT_CARD_WELL_KNOWN_PATH}",
    )

    writer_agent = RemoteA2aAgent(
        name="writer_agent",
        description="Creates polished, well-structured content. Use this agent when you need to transform research into guides, tutorials, documentation, or any written content.",
        agent_card=f"http://localhost:10002{AGENT_CARD_WELL_KNOWN_PATH}",
    )

    security_agent = RemoteA2aAgent(
        name="security_agent",
        description="Scans content for secrets, credentials, and security issues. Use this agent to verify content is safe to publish and doesn't contain exposed secrets.",
        agent_card=f"http://localhost:10003{AGENT_CARD_WELL_KNOWN_PATH}",
    )

    host = Agent(
        name="host_agent",
        description="Orchestrates content creation by delegating to specialized agents.",
        model=BEDROCK_MODEL,  # Using AWS Bedrock Claude via LiteLLM
        instruction="""You are a Host Agent that orchestrates content creation tasks.

You have access to three specialized agents:

1. **research_agent**: For gathering information and researching topics
2. **writer_agent**: For creating polished written content
3. **security_agent**: For scanning content for security issues

Your job is to:
1. Understand what the user wants
2. Break down the task into steps
3. Delegate to the appropriate agent(s)
4. Combine their outputs into a final result

For a typical content creation task:
1. First, delegate to research_agent to gather information
2. Then, delegate to writer_agent to create polished content
3. Finally, delegate to security_agent to verify the content is safe

You decide which agents to use based on the task. Not all tasks need all agents.
For example:
- "Research X" → Just use research_agent
- "Write about X" → Use research_agent then writer_agent
- "Check this for secrets" → Just use security_agent
- "Create a guide about X" → Use all three agents in sequence

Always explain what you're doing and why you're delegating to each agent.""",
        sub_agents=[research_agent, writer_agent, security_agent],
    )

    return host


# For backwards compatibility - static agent (used by adk web)
host_agent = create_host_agent_static()

if __name__ == "__main__":
    # For direct testing with ADK's web interface
    print("🎯 Host Agent (ADK Orchestrator)")
    print("   This agent orchestrates remote A2A agents")
    print("   Run with: adk web examples/adk_a2a")
    print("")
    print("   Or run programmatically - see run_demo.py")
