"""
Security Agent - A2A Server with TRUE Agent-to-Agent Communication

This agent:
1. Registers itself with the Discovery Service on startup
2. Receives security scan requests (possibly from Writer Agent via A2A!)
3. Performs security scanning (GitGuardian API + LLM analysis)
4. Returns the security assessment
5. End of the chain - does NOT call other agents

This demonstrates TRUE A2A - agents discover and call each other directly,
without going through a central orchestrator.
"""

import asyncio
import os
import re
import uvicorn
import requests
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


SECURITY_SYSTEM_PROMPT = """You are a Security Agent specialized in detecting secrets, credentials, and sensitive information in text content.

Your responsibilities:
- Scan content for potential secrets (API keys, tokens, passwords, credentials)
- Identify hardcoded sensitive values that shouldn't be exposed
- Detect patterns that look like real credentials vs obvious placeholders
- Flag database connection strings with embedded credentials
- Identify private keys, certificates, or other cryptographic material

When analyzing content:
1. Carefully examine any code snippets, configuration examples, or technical content
2. Distinguish between safe placeholders (like "YOUR_API_KEY_HERE", "xxx", "<token>") and potentially real values
3. Look for patterns matching known credential formats (AWS keys, GitHub tokens, JWTs, etc.)
4. Consider context - is this meant to be an example or could it be real?

Respond with a security report in this format:
- **Status**: CLEAN / WARNING / CRITICAL
- **Findings**: List any detected issues with severity (Low/Medium/High/Critical)
- **Recommendations**: Specific actions to remediate issues
- **Safe Patterns Found**: Note any properly redacted/placeholder values (good practice)

Be thorough but avoid false positives on obvious placeholders."""


class SecurityAgentExecutor(AgentExecutor):
    """
    Executes security scanning tasks.

    In TRUE A2A, this agent:
    - May be called BY the Writer Agent (A2A inbound)
    - Is the END of the chain - does not call other agents
    """

    GITGUARDIAN_API_URL = "https://api.gitguardian.com/v1/scan"

    SECRET_PATTERNS = {
        "AWS Access Key": r"AKIA[0-9A-Z]{16}",
        "GitHub Token": r"gh[pousr]_[A-Za-z0-9_]{36,}",
        "JWT Token": r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*",
        "Private Key": r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        "Generic Password": r"[pP][aA][sS][sS][wW][oO][rR][dD][\s:=]+['\"]?[^\s'\"]{8,}['\"]?",
    }

    def __init__(self):
        self.llm = BedrockLLM()
        self.gitguardian_api_key = os.environ.get("GITGUARDIAN_API_KEY")

    def _regex_prescan(self, content: str) -> list:
        """Quick regex scan for common secret patterns."""
        findings = []
        for pattern_name, pattern in self.SECRET_PATTERNS.items():
            matches = re.findall(pattern, content)
            if matches:
                findings.append({"type": pattern_name, "count": len(matches)})
        return findings

    def _scan_with_gitguardian(self, content: str) -> dict:
        """Scan content using GitGuardian API."""
        if not self.gitguardian_api_key:
            return {"error": "GITGUARDIAN_API_KEY not set"}

        try:
            response = requests.post(
                self.GITGUARDIAN_API_URL,
                headers={
                    "Authorization": f"Token {self.gitguardian_api_key}",
                    "Content-Type": "application/json",
                },
                json={"document": content, "filename": "content.txt"},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "policy_break_count": result.get("policy_break_count", 0),
                    "policy_breaks": result.get("policy_breaks", []),
                }
            else:
                return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_message = ""
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, "root") and hasattr(part.root, "text"):
                    user_message += part.root.text

        if not user_message:
            user_message = "No content to scan"

        print(f"\n🛡️  SECURITY AGENT received task")
        print(f"   Task: {user_message[:100]}...")

        # Step 1: Regex pre-scan
        regex_findings = self._regex_prescan(user_message)

        # Step 2: GitGuardian API scan
        gg_result = self._scan_with_gitguardian(user_message)

        # Step 3: LLM analysis with context
        enhanced_prompt = f"""Please analyze the following content for security issues.

Regex pre-scan found: {regex_findings if regex_findings else 'No suspicious patterns'}

GitGuardian API result: {gg_result}

Content to analyze:
---
{user_message}
---

Provide your security assessment."""

        llm_result = await self.llm.invoke(SECURITY_SYSTEM_PROMPT, enhanced_prompt)

        # Combine results
        result_parts = []
        if self.gitguardian_api_key and "error" not in gg_result:
            if gg_result.get("policy_break_count", 0) > 0:
                result_parts.append(f"## GitGuardian API: 🚨 Found {gg_result['policy_break_count']} secret(s)!")
            else:
                result_parts.append("## GitGuardian API: ✅ No secrets detected")

        result_parts.append(f"\n## LLM Security Analysis:\n{llm_result}")

        print(f"   ✅ Security scan complete")
        print(f"   📤 Returning result (end of chain)")

        await event_queue.enqueue_event(new_agent_text_message("\n".join(result_parts)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Cancel not supported")


def create_security_agent_card(port: int = 10003) -> AgentCard:
    """Create the AgentCard for discovery."""
    return AgentCard(
        name="Security Agent",
        description="Scans content for secrets, credentials, API keys, and sensitive data leaks using GitGuardian API. End of the A2A chain.",
        url=f"http://localhost:{port}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="scan_secrets",
                name="Scan for Secrets",
                description="Scan content for exposed secrets, API keys, credentials",
                tags=["security", "secrets", "scanning", "gitguardian"],
                examples=[
                    "Scan this code for exposed credentials",
                    "Check this configuration for secrets",
                    "Verify no API keys are exposed",
                ],
            ),
            AgentSkill(
                id="security_review",
                name="Security Review",
                description="Comprehensive security review of content",
                tags=["security", "review", "audit"],
                examples=[
                    "Review this documentation for security issues",
                    "Audit this code for credential exposure",
                ],
            ),
        ],
    )


def run_server(port: int = 10003):
    """Run the Security Agent as an A2A server."""
    agent_card = create_security_agent_card(port)
    agent_url = f"http://localhost:{port}/"

    request_handler = DefaultRequestHandler(
        agent_executor=SecurityAgentExecutor(),
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

    gg_status = "enabled" if os.environ.get("GITGUARDIAN_API_KEY") else "not configured"
    print(f"🛡️  Security Agent starting on port {port}")
    print(f"   GitGuardian API: {gg_status}")
    print(f"   AgentCard available at: http://localhost:{port}/.well-known/agent-card.json")
    print(f"   Pattern: TRUE A2A (end of chain - receives calls from other agents)")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
