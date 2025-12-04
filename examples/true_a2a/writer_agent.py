"""
Writer Agent - A2A Server with TRUE Agent-to-Agent Communication

This agent:
1. Registers itself with the Discovery Service on startup
2. Receives writing requests (possibly from Research Agent via A2A!)
3. Does its writing work
4. Queries the Discovery Service to find a Security Agent
5. CALLS the Security Agent directly (TRUE A2A!)
6. Returns the security-verified result

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


class WriterAgentExecutor(AgentExecutor, A2AClientMixin):
    """
    Executes writing tasks and CHAINS to the Security Agent.

    This demonstrates TRUE A2A - this agent:
    - May be called BY the Research Agent (A2A inbound)
    - Calls the Security Agent directly (A2A outbound)
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
            user_message = "No writing task provided"

        print(f"\n✍️  WRITER AGENT received task")
        print(f"   Task: {user_message[:100]}...")

        # Step 1: Do our writing work
        print(f"   📝 Writing content...")
        written_content = await self.llm.invoke(WRITER_SYSTEM_PROMPT, user_message)
        print(f"   ✅ Writing complete ({len(written_content)} chars)")

        # Step 2: TRUE A2A - Discover and call the Security Agent!
        print(f"\n   🔗 AGENT-TO-AGENT: Querying Discovery Service for a security agent...")

        security_url = await self.find_agent_with_skill("security")

        if security_url:
            print(f"   🎯 Found Security Agent! Requesting security scan...")

            # Prepare the task for the Security Agent
            security_task = f"""Please scan the following content for any exposed secrets, credentials, API keys, or sensitive data.

CONTENT TO SCAN:
---
{written_content}
---

Provide a security assessment and confirm if it's safe to publish."""

            # TRUE A2A: Call the Security Agent directly!
            security_response = await self.call_agent(security_url, security_task)

            # Return the chained result
            final_result = f"""## Writer Agent -> Security Agent (A2A Chain Complete)

### Written Content:
{written_content}

---

### Security Scan Result:
{security_response}"""

            print(f"\n✍️  WRITER AGENT: Chain complete, returning result")
            await event_queue.enqueue_event(new_agent_text_message(final_result))

        else:
            # No security agent found, return just our writing
            print(f"   ⚠️  No Security Agent found, returning content without security scan")
            await event_queue.enqueue_event(new_agent_text_message(written_content))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Cancel not supported")


def create_writer_agent_card(port: int = 10002) -> AgentCard:
    """Create the AgentCard for discovery."""
    return AgentCard(
        name="Writer Agent",
        description="Creates polished content, summaries, documentation, and well-formatted text. Can chain to Security Agent for verification.",
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
    print(f"   Pattern: TRUE A2A (can discover and call other agents)")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
