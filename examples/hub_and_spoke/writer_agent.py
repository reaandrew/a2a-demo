"""
Writer Agent - A2A Server (Hub-and-Spoke Pattern)

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


WRITER_SYSTEM_PROMPT = """You are a Writer Agent specialized in creating polished, engaging content.

Your responsibilities:
- Transform information into well-written content
- Create summaries, articles, guides, and formatted text
- Adapt tone and style to the request
- Ensure clarity and readability
- Structure content logically

When given a writing task:
1. Understand the purpose and audience
2. Organize the content effectively
3. Use clear, engaging language
4. Polish the final output

You may receive context from other agents (like research findings). Use this context to create comprehensive, accurate content.

Always aim for:
- Clear structure (intro, body, conclusion when appropriate)
- Engaging and professional tone
- Accurate representation of provided information"""


class WriterAgentExecutor(AgentExecutor):
    """
    Executes writing tasks.

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
            user_message = "No writing task provided"

        print(f"\n✍️  WRITER AGENT received task from orchestrator")
        print(f"   Task: {user_message[:100]}...")

        # Do our writing work
        print(f"   📝 Writing content...")
        written_content = await self.llm.invoke(WRITER_SYSTEM_PROMPT, user_message)
        print(f"   ✅ Writing complete ({len(written_content)} chars)")

        # Return result to orchestrator (NOT to another agent)
        print(f"   📤 Returning result to orchestrator")
        await event_queue.enqueue_event(new_agent_text_message(written_content))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Cancel not supported")


def create_writer_agent_card(port: int = 10002) -> AgentCard:
    """Create the AgentCard for discovery."""
    return AgentCard(
        name="Writer Agent",
        description="Creates polished content, summaries, documentation, and well-formatted text.",
        url=f"http://localhost:{port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="write_content",
                name="Write Content",
                description="Create well-written content on any topic",
                tags=["writing", "content", "documentation"],
                examples=[
                    "Write a quick-start guide",
                    "Create a blog post introduction",
                    "Write documentation for an API",
                ],
            ),
            AgentSkill(
                id="summarize",
                name="Summarize",
                description="Create concise summaries of provided information",
                tags=["writing", "summary", "condensing", "executive summary"],
                examples=[
                    "Summarize the research findings",
                    "Create an executive summary",
                ],
            ),
            AgentSkill(
                id="format",
                name="Format Content",
                description="Format and structure content for clarity",
                tags=["writing", "formatting", "structure", "organization"],
                examples=[
                    "Format this information as a tutorial",
                    "Structure this as a how-to guide",
                ],
            ),
        ],
    )


def run_server(port: int = 10002):
    """Run the Writer Agent as an A2A server."""
    agent_card = create_writer_agent_card(port)
    agent_url = f"http://localhost:{port}/"

    request_handler = DefaultRequestHandler(
        agent_executor=WriterAgentExecutor(),
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

    print(f"✍️  Writer Agent starting on port {port}")
    print(f"   AgentCard available at: http://localhost:{port}/.well-known/agent-card.json")
    print(f"   Pattern: Hub-and-Spoke (waits for orchestrator calls)")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
