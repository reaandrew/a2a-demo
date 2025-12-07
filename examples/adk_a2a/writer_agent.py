"""
Writer Agent - Exposed via Google ADK's to_a2a()

This agent is built using Google's Agent Development Kit (ADK) and exposed
as an A2A server using the official to_a2a() function.

Key ADK/A2A concepts demonstrated:
- Agent with tools (format_content tool)
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


def format_content(content: str, style: str = "guide") -> str:
    """
    Format content into a specific style.

    Args:
        content: The content to format
        style: The style to use (guide, tutorial, summary, blog)

    Returns:
        Formatting instructions for the content
    """
    styles = {
        "guide": "Format as a comprehensive how-to guide with numbered steps, clear sections, and practical examples.",
        "tutorial": "Format as a step-by-step tutorial with code examples, explanations, and expected outcomes.",
        "summary": "Format as an executive summary with key points, bullet points, and a conclusion.",
        "blog": "Format as an engaging blog post with an introduction, main body, and call to action.",
    }

    format_instruction = styles.get(style, styles["guide"])

    return f"""
Content to format:
---
{content[:500]}...
---

Formatting style: {style}
Instructions: {format_instruction}

Please transform this content following the style guidelines.
"""


# Create the Writer Agent using ADK
writer_agent = Agent(
    name="writer_agent",
    description="Creates polished, well-structured content. Specializes in transforming research and raw information into guides, tutorials, summaries, and documentation.",
    model=BEDROCK_MODEL,  # Using AWS Bedrock Claude via LiteLLM
    instruction="""You are a Writer Agent specialized in creating polished, engaging content.

Your responsibilities:
- Transform information into well-written content
- Create summaries, articles, guides, and formatted text
- Adapt tone and style to the request
- Ensure clarity and readability
- Structure content logically

When given a writing task:
1. Understand the purpose and audience
2. Use the format_content tool if specific formatting is needed
3. Organize the content with clear sections
4. Use engaging but professional language
5. Include examples where helpful

CRITICAL - Code Examples Policy:
- PRESERVE all code examples from the source material EXACTLY as provided
- Do NOT modify, sanitize, or redact any API keys, tokens, or credentials in examples
- If the source includes credentials like AKIAIOSFODNN7EXAMPLE or sk_live_xxx, keep them exactly as-is
- These are intentional examples for educational purposes
- Security scanning is handled by another agent - your job is just to write the content faithfully

Always aim for:
- Clear structure (intro, body, conclusion)
- Engaging and professional tone
- Accurate representation of source material (preserve all code examples verbatim)""",
    tools=[format_content],
)

# Create the A2A application
app = to_a2a(
    writer_agent,
    host="localhost",
    port=10002,
)

if __name__ == "__main__":
    import asyncio
    import uvicorn
    from discovery_service import register_with_discovery

    PORT = 10002
    AGENT_URL = f"http://localhost:{PORT}/"

    class RegistrationServer(uvicorn.Server):
        """Custom uvicorn server that registers with discovery service after startup."""

        async def startup(self, sockets=None):
            await super().startup(sockets)
            asyncio.create_task(self._register())

        async def _register(self):
            await asyncio.sleep(1.0)
            registered = await register_with_discovery(AGENT_URL)
            if registered:
                print(f"   ✅ Registered with Discovery Service", flush=True)
            else:
                print(f"   ⚠️  Could not register (Discovery Service not running?)", flush=True)

    print("✍️  Writer Agent (ADK + A2A)")
    print(f"   Port: {PORT}")
    print(f"   AgentCard: {AGENT_URL}.well-known/agent-card.json")
    print("   Built with: Google ADK + to_a2a()")

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = RegistrationServer(config)
    asyncio.run(server.serve())
