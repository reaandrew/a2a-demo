"""
Research Agent - A2A Server (Hub-and-Spoke Pattern)

This agent runs as an independent HTTP server, discoverable via its AgentCard.
In the hub-and-spoke pattern, the ORCHESTRATOR discovers and calls this agent.
The agent does NOT call other agents directly.

On startup, this agent registers itself with the Discovery Service so that
the orchestrator can dynamically discover it.
"""

import asyncio
import uvicorn
from contextlib import asynccontextmanager
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from base_llm import BedrockLLM
from discovery_service import register_with_discovery


RESEARCH_SYSTEM_PROMPT = """You are a Research Agent specialized in gathering and analyzing information.

Your responsibilities:
- Provide factual, well-researched information
- Analyze topics thoroughly
- Present findings in a clear, structured format
- Be objective and balanced in your analysis

When given a research task:
1. Break down the topic into key aspects
2. Provide relevant facts and insights
3. Highlight important considerations
4. Summarize key findings

Keep your responses focused and informative."""


class ResearchAgentExecutor(AgentExecutor):
    """
    Executes research tasks.

    In hub-and-spoke pattern, this agent:
    - Receives requests FROM the orchestrator
    - Does its work
    - Returns results TO the orchestrator
    - Does NOT call other agents
    """

    def __init__(self):
        self.llm = BedrockLLM()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_message = ""
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, "root") and hasattr(part.root, "text"):
                    user_message += part.root.text

        if not user_message:
            user_message = "No research topic provided"

        print(f"\n🔍 RESEARCH AGENT received task from orchestrator")
        print(f"   Task: {user_message[:100]}...")

        # Do our research work
        print(f"   📚 Researching topic...")
        research_result = await self.llm.invoke(RESEARCH_SYSTEM_PROMPT, user_message)
        print(f"   ✅ Research complete ({len(research_result)} chars)")

        # Return result to orchestrator (NOT to another agent)
        print(f"   📤 Returning result to orchestrator")
        await event_queue.enqueue_event(new_agent_text_message(research_result))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Cancel not supported")


def create_research_agent_card(port: int = 10001) -> AgentCard:
    """Create the AgentCard for discovery."""
    return AgentCard(
        name="Research Agent",
        description="Gathers information, analyzes topics, and provides factual research findings.",
        url=f"http://localhost:{port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="research",
                name="Research Topic",
                description="Research any topic and provide comprehensive findings",
                tags=["research", "analysis", "information", "facts"],
                examples=[
                    "Research best practices for AWS S3",
                    "Analyze microservices architecture patterns",
                    "Gather information about Python async programming",
                ],
            ),
            AgentSkill(
                id="analyze",
                name="Analyze Information",
                description="Analyze provided information and extract insights",
                tags=["analysis", "insights", "evaluation"],
                examples=[
                    "Analyze the pros and cons of serverless",
                    "Evaluate different authentication methods",
                ],
            ),
        ],
    )


def run_server(port: int = 10001):
    """Run the Research Agent as an A2A server."""
    agent_card = create_research_agent_card(port)
    agent_url = f"http://localhost:{port}/"

    request_handler = DefaultRequestHandler(
        agent_executor=ResearchAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    # Create lifespan to register with discovery service on startup
    @asynccontextmanager
    async def lifespan(app):
        # Startup: Register with discovery service
        await asyncio.sleep(0.5)  # Brief delay to ensure server is ready
        registered = await register_with_discovery(agent_url)
        if registered:
            print(f"   ✅ Registered with Discovery Service")
        else:
            print(f"   ⚠️  Could not register with Discovery Service (is it running?)")
        yield
        # Shutdown: Could unregister here if needed

    starlette_app = server.build()
    starlette_app.router.lifespan_context = lifespan

    print(f"🔍 Research Agent starting on port {port}")
    print(f"   AgentCard available at: http://localhost:{port}/.well-known/agent-card.json")
    print(f"   Pattern: Hub-and-Spoke (waits for orchestrator calls)")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
