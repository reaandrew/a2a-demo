"""
Security Agent - Exposed via Google ADK's to_a2a()

This agent is built using Google's Agent Development Kit (ADK) and exposed
as an A2A server using the official to_a2a() function.

Key ADK/A2A concepts demonstrated:
- Agent with tools (scan_for_secrets tool with GitGuardian API)
- Automatic AgentCard generation from agent definition
- Proper A2A server exposure via to_a2a()
"""

import warnings
# Suppress experimental warnings from ADK
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")

import os
import requests
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# Use AWS Bedrock Claude via LiteLLM (EU region model)
BEDROCK_MODEL = LiteLlm(model="bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0")

# GitGuardian API configuration
GITGUARDIAN_API_URL = "https://api.gitguardian.com/v1/scan"


def scan_for_secrets(content: str) -> str:
    """
    Scan content for potential secrets and credentials using GitGuardian API.

    Args:
        content: The content to scan for secrets

    Returns:
        A security scan report with findings from GitGuardian
    """
    import json

    api_key = os.environ.get("GITGUARDIAN_API_KEY")

    if not api_key:
        print("", flush=True)
        print("      ❌ GITGUARDIAN_API_KEY not set", flush=True)
        return "❌ ERROR: GITGUARDIAN_API_KEY environment variable not set. Cannot perform security scan."

    try:
        print("", flush=True)
        print(f"      → GitGuardian API: POST /v1/scan", flush=True)
        print(f"      → Scanning {len(content)} chars of content...", flush=True)

        response = requests.post(
            GITGUARDIAN_API_URL,
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
            },
            json={"document": content, "filename": "content.txt"},
            timeout=30,
        )

        print(f"      ← Status: {response.status_code}", flush=True)

        if response.status_code == 200:
            result = response.json()

            # Print the full API response
            print(f"      ← Response:", flush=True)
            print(f"         {json.dumps(result, indent=2).replace(chr(10), chr(10) + '         ')}", flush=True)

            policy_break_count = result.get("policy_break_count", 0)

            # Build report for the agent
            if policy_break_count > 0:
                report = f"🚨 SECRETS DETECTED: {policy_break_count} policy break(s) found!\n"
                for i, breach in enumerate(result.get("policy_breaks", []), 1):
                    report += f"  Secret #{i}: {breach.get('break_type', 'Unknown')}\n"
                return report
            else:
                return "✅ GitGuardian: No secrets detected!"
        else:
            print(f"      ← Error: {response.status_code} - {response.text[:200]}", flush=True)
            return f"❌ GitGuardian API Error: {response.status_code} - {response.text}"

    except Exception as e:
        print(f"      ← Exception: {str(e)}", flush=True)
        return f"❌ GitGuardian API Error: {str(e)}"


# Create the Security Agent using ADK
security_agent = Agent(
    name="security_agent",
    description="Scans content for exposed secrets, credentials, API keys, and sensitive data. Provides security assessments and recommendations.",
    model=BEDROCK_MODEL,  # Using AWS Bedrock Claude via LiteLLM
    instruction="""You are a Security Agent specialized in detecting secrets, credentials, and sensitive information in text content.

Your responsibilities:
- Scan content for potential secrets (API keys, tokens, passwords, credentials)
- Identify hardcoded sensitive values that shouldn't be exposed
- Detect patterns that look like real credentials vs obvious placeholders
- Flag database connection strings with embedded credentials
- Identify private keys, certificates, or other cryptographic material

When analyzing content:
1. First use the scan_for_secrets tool for automated pattern detection
2. Then manually review for context - is this an example or potentially real?
3. Distinguish between safe placeholders (like "YOUR_API_KEY_HERE", "xxx", "<token>") and suspicious values
4. Consider the context - documentation examples vs production code

Respond with a security report in this format:
- **Status**: CLEAN / WARNING / CRITICAL
- **Automated Scan**: Results from the scan_for_secrets tool
- **Manual Analysis**: Your contextual review
- **Findings**: List any detected issues with severity (Low/Medium/High/Critical)
- **Recommendations**: Specific actions to remediate issues
- **Safe Patterns Found**: Note any properly redacted/placeholder values (good practice)

Be thorough but avoid false positives on obvious placeholders.""",
    tools=[scan_for_secrets],
)

# Create the A2A application
app = to_a2a(
    security_agent,
    host="localhost",
    port=10003,
)

if __name__ == "__main__":
    import asyncio
    import uvicorn
    from discovery_service import register_with_discovery

    PORT = 10003
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

    print("🛡️  Security Agent (ADK + A2A)")
    print(f"   Port: {PORT}")
    print(f"   AgentCard: {AGENT_URL}.well-known/agent-card.json")
    print("   Built with: Google ADK + to_a2a()")

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = RegistrationServer(config)
    asyncio.run(server.serve())
