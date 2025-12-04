"""
Research Agent - A2A Server with TRUE Agent-to-Agent Communication

This agent:
1. Registers itself with the Discovery Service on startup
2. Receives research requests
3. Does its research work
4. Queries the Discovery Service to find a Writer Agent
5. CALLS the Writer Agent directly (TRUE A2A!)
6. Returns the final chain result

This demonstrates TRUE A2A - agents discover and call each other directly,
without going through a central orchestrator.
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
from a2a_client_mixin import A2AClientMixin
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


class ResearchAgentExecutor(AgentExecutor, A2AClientMixin):
    """
    Executes research tasks and CHAINS to the Writer Agent.

    This demonstrates TRUE A2A - this agent discovers and calls
    another agent directly, without going through an orchestrator.
    """

    def __init__(self):
        AgentExecutor.__init__(self)
        A2AClientMixin.__init__(self)
        self.llm = BedrockLLM()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Extract the user's message from the request
        user_message = ""
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, "root") and hasattr(part.root, "text"):
                    user_message += part.root.text

        if not user_message:
            user_message = "No research topic provided"

        print(f"\n🔍 RESEARCH AGENT received task")
        print(f"   Task: {user_message[:100]}...")

        # Step 1: Do our research work
        print(f"   📚 Researching topic...")
        research_result = await self.llm.invoke(RESEARCH_SYSTEM_PROMPT, user_message)
        print(f"   ✅ Research complete ({len(research_result)} chars)")

        # Step 2: TRUE A2A - Discover and call the Writer Agent!
        print(f"\n   🔗 AGENT-TO-AGENT: Querying Discovery Service for a writing agent...")

        writer_url = await self.find_agent_with_skill("writing")

        if writer_url:
            print(f"   🎯 Found Writer Agent! Delegating writing task...")

            # Prepare the task for the Writer Agent
            writer_task = f"""Based on the following research findings, please write a well-structured guide.

RESEARCH FINDINGS:
---
{research_result}
---

Please create a polished, reader-friendly guide from this research."""

            # TRUE A2A: Call the Writer Agent directly!
            writer_response = await self.call_agent(writer_url, writer_task)

            # Return the chained result
            final_result = f"""## Research Agent -> Writer Agent (A2A Chain Complete)

### Original Research:
{research_result[:500]}...

### Writer Agent's Polished Output:
{writer_response}"""

            print(f"\n🔍 RESEARCH AGENT: Chain complete, returning result")
            await event_queue.enqueue_event(new_agent_text_message(final_result))

        else:
            # No writer agent found, return just our research
            print(f"   ⚠️  No Writer Agent found, returning research only")
            await event_queue.enqueue_event(new_agent_text_message(research_result))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Cancel not supported")


def create_research_agent_card(port: int = 10001) -> AgentCard:
    """Create the AgentCard for discovery."""
    return AgentCard(
        name="Research Agent",
        description="Gathers information, analyzes topics, and provides factual research findings. Can chain to Writer Agent for polished output.",
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
    print(f"   Pattern: TRUE A2A (can discover and call other agents)")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
