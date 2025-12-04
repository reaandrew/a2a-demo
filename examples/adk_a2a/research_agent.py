"""
Research Agent - Exposed via Google ADK's to_a2a()

This agent is built using Google's Agent Development Kit (ADK) and exposed
as an A2A server using the official to_a2a() function.

Key ADK/A2A concepts demonstrated:
- Agent with tools (research_topic tool)
- Automatic AgentCard generation from agent definition
- Proper A2A server exposure via to_a2a()
"""

import warnings
# Suppress experimental warnings from ADK
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# Use AWS Bedrock Claude via LiteLLM (EU region model)
BEDROCK_MODEL = LiteLlm(model="bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0")

# Define the research tool
def research_topic(topic: str) -> str:
    """
    Research a topic and return findings.

    Args:
        topic: The topic to research

    Returns:
        Research findings as a structured string
    """
    # In a real implementation, this would call APIs, search engines, etc.
    # For demo purposes, we return a structured response that the LLM will expand on
    return f"""
Research findings for: {topic}

Key Areas Identified:
1. Best Practices - Industry-standard approaches
2. Security Considerations - Important security aspects
3. Implementation Patterns - Common ways to implement
4. Tools and Libraries - Relevant tooling
5. Common Pitfalls - Things to avoid

Please synthesize these areas into comprehensive research findings.
"""


# Create the Research Agent using ADK
research_agent = Agent(
    name="research_agent",
    description="Researches topics and provides comprehensive findings. Specializes in technical research, best practices analysis, and information gathering.",
    model=BEDROCK_MODEL,  # Using AWS Bedrock Claude via LiteLLM
    instruction="""You are a Research Agent specialized in gathering and analyzing information.

Your responsibilities:
- Provide factual, well-researched information
- Analyze topics thoroughly
- Present findings in a clear, structured format
- Be objective and balanced in your analysis

When given a research task:
1. Use the research_topic tool to gather initial findings
2. Expand on the findings with your knowledge
3. Structure the response clearly with sections
4. Highlight key takeaways

Always be thorough but concise.""",
    tools=[research_topic],
)

# Create the A2A application using to_a2a()
# This automatically:
# 1. Generates an AgentCard from the agent definition
# 2. Sets up the A2A server endpoints
# 3. Handles message conversion between ADK and A2A formats
app = to_a2a(
    research_agent,
    host="localhost",
    port=10001,
)

if __name__ == "__main__":
    import asyncio
    import uvicorn
    from discovery_service import register_with_discovery

    PORT = 10001
    AGENT_URL = f"http://localhost:{PORT}/"

    class RegistrationServer(uvicorn.Server):
        """Custom uvicorn server that registers with discovery service after startup."""

        async def startup(self, sockets=None):
            await super().startup(sockets)
            # Register after server is fully started
            asyncio.create_task(self._register())

        async def _register(self):
            await asyncio.sleep(1.0)  # Small delay to ensure server is ready
            registered = await register_with_discovery(AGENT_URL)
            if registered:
                print(f"   ✅ Registered with Discovery Service", flush=True)
            else:
                print(f"   ⚠️  Could not register (Discovery Service not running?)", flush=True)

    print("🔍 Research Agent (ADK + A2A)")
    print(f"   Port: {PORT}")
    print(f"   AgentCard: {AGENT_URL}.well-known/agent-card.json")
    print("   Built with: Google ADK + to_a2a()")

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = RegistrationServer(config)
    asyncio.run(server.serve())
