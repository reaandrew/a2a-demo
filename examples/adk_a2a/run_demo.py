#!/usr/bin/env python
"""
ADK + A2A Demo Runner

This demo shows PROPER A2A usage as Google intended:

1. Discovery Service allows dynamic agent registration
2. Remote agents are exposed via to_a2a() - the official ADK function
3. Agents register themselves with the Discovery Service on startup
4. Host agent DISCOVERS available agents from the Discovery Service
5. The LLM DECIDES which agent to delegate to based on the task
6. No hardcoded workflow - the model routes dynamically

Architecture:
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│            ┌───────────────────────────────────┐                 │
│            │       DISCOVERY SERVICE           │                 │
│            │   Agents register on startup      │                 │
│            │   Host queries for available      │                 │
│            │   :9999                           │                 │
│            └───────────────────────────────────┘                 │
│                    ▲               │                             │
│                    │ register      │ discover                    │
│                    │               ▼                             │
│                        ┌─────────────┐                           │
│                        │ HOST AGENT  │                           │
│                        │  (Bedrock)  │                           │
│                        └──────┬──────┘                           │
│                               │                                  │
│              LLM decides which agent(s) to call                  │
│                               │                                  │
│              ┌────────────────┼────────────────┐                 │
│              │                │                │                 │
│              ▼                ▼                ▼                 │
│     ┌────────────────┐ ┌────────────┐ ┌────────────────┐        │
│     │ RemoteA2aAgent │ │RemoteA2a   │ │ RemoteA2aAgent │        │
│     │   (research)   │ │Agent(write)│ │   (security)   │        │
│     └───────┬────────┘ └─────┬──────┘ └───────┬────────┘        │
│             │                │                │                  │
│             ▼                ▼                ▼                  │
│     ┌────────────────┐ ┌────────────┐ ┌────────────────┐        │
│     │ Research Agent │ │Writer Agent│ │ Security Agent │        │
│     │ (A2A Server)   │ │(A2A Server)│ │ (A2A Server)   │        │
│     │ :10001         │ │ :10002     │ │ :10003         │        │
│     └────────────────┘ └────────────┘ └────────────────┘        │
│                                                                  │
│   KEY: Discovery Service finds agents, LLM decides what to use! │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

Requirements:
- AWS credentials configured for Bedrock access
- google-adk[a2a] installed
"""

import subprocess
import time
import sys
import os
import asyncio
import warnings

# Suppress experimental warnings from ADK
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")
# Suppress litellm warnings
warnings.filterwarnings("ignore", module="litellm")

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_aws_credentials():
    """Check if AWS credentials are configured for Bedrock."""
    import boto3
    try:
        # Try to create a Bedrock client to verify credentials
        client = boto3.client("bedrock-runtime")
        # Just check if we can create the client (doesn't make a call)
        return True
    except Exception as e:
        print("❌ ERROR: AWS credentials not configured for Bedrock")
        print("")
        print("   To configure AWS credentials:")
        print("   1. Install AWS CLI: pip install awscli")
        print("   2. Run: aws configure")
        print("   3. Or set environment variables:")
        print("      export AWS_ACCESS_KEY_ID='your-key'")
        print("      export AWS_SECRET_ACCESS_KEY='your-secret'")
        print("      export AWS_DEFAULT_REGION='us-east-1'")
        print("")
        print(f"   Error: {e}")
        return False


def start_discovery_service():
    """Start the Discovery Service."""
    print("=" * 70)
    print("🔎 STARTING DISCOVERY SERVICE")
    print("=" * 70)
    print("")
    print("   The Discovery Service allows agents to register themselves")
    print("   and enables the host agent to discover available agents dynamically")
    print("")

    proc = subprocess.Popen(
        [sys.executable, "discovery_service.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    print("📡 Starting Discovery Service on port 9999...")
    time.sleep(2)  # Give Discovery Service time to start

    return proc


def start_remote_agents():
    """Start all remote A2A agent servers."""
    print("")
    print("=" * 70)
    print("🚀 STARTING REMOTE A2A AGENTS")
    print("=" * 70)
    print("")
    print("   These agents are exposed via Google ADK's to_a2a() function")
    print("   Each generates its AgentCard automatically from the Agent definition")
    print("   Each agent registers itself with the Discovery Service on startup")
    print("")

    processes = []
    agents = [
        ("research_agent", 10001, "Research Agent"),
        ("writer_agent", 10002, "Writer Agent"),
        ("security_agent", 10003, "Security Agent"),
    ]

    for module, port, name in agents:
        print(f"📡 Starting {name} on port {port}...")
        # Pass current environment (including AWS credentials) to subprocess
        proc = subprocess.Popen(
            [sys.executable, f"{module}.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),  # Pass AWS credentials to agent subprocesses
        )
        processes.append((proc, name, port))
        time.sleep(5)  # Give each agent time to start and register

    print("")
    print("⏳ Waiting for agents to finish registering...")
    time.sleep(8)  # Extra time for all registrations to complete

    return processes


def stop_servers(processes):
    """Stop all server processes."""
    print("\n" + "=" * 70)
    print("🛑 STOPPING SERVERS")
    print("=" * 70)

    for proc, name, port in processes:
        print(f"   Stopping {name}...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("   All servers stopped.")


async def run_host_agent(task: str):
    """
    Run the host agent with a task.

    This demonstrates the key difference from our previous examples:
    1. The host agent DISCOVERS available agents from the Discovery Service
    2. The LLM decides which agents to call, not hardcoded logic
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types

    from host_agent import create_host_agent_with_discovery

    print("\n" + "=" * 70)
    print("🎯 RUNNING HOST AGENT")
    print("=" * 70)
    print(f"\nTask: {task}")
    print("\n" + "-" * 70)
    print("First, discovering available agents from Discovery Service...")
    print("-" * 70 + "\n")

    # Create host agent with dynamic discovery
    host_agent = await create_host_agent_with_discovery()

    print("\n" + "-" * 70)
    print("Now watch as the LLM decides which agents to delegate to...")
    print("-" * 70 + "\n")

    # Create a runner for the host agent
    runner = Runner(
        agent=host_agent,
        app_name="adk_a2a_demo",
        session_service=InMemorySessionService(),
    )

    # Create a session
    session = await runner.session_service.create_session(
        app_name="adk_a2a_demo",
        user_id="demo_user",
    )

    # Run the agent with the task
    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=task)],
    )

    final_response = ""
    last_author = None

    async for event in runner.run_async(
        user_id="demo_user",
        session_id=session.id,
        new_message=content,
    ):
        author = event.author

        # Print clear section headers when agent changes
        if author != last_author and author:
            if author == "host_agent":
                print("\n" + "=" * 70)
                print("🎯 HOST AGENT (orchestrating)")
                print("=" * 70)
            elif "research" in author.lower():
                print("\n" + "-" * 70)
                print("🔍 RESEARCH AGENT activated")
                print("-" * 70)
            elif "writer" in author.lower():
                print("\n" + "-" * 70)
                print("✍️  WRITER AGENT activated")
                print("-" * 70)
            elif "security" in author.lower():
                print("\n" + "-" * 70)
                print("🛡️  SECURITY AGENT activated")
                print("-" * 70)
            else:
                print(f"\n[{author}]")
            last_author = author

        # Print event content
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    text = part.text.strip()
                    if text:
                        # Truncate long outputs for readability
                        if len(text) > 500:
                            print(f"{text[:500]}...")
                            print(f"   [... {len(text) - 500} more characters]")
                        else:
                            print(text)

                        if author == "host_agent":
                            final_response = part.text

    return final_response


def main():
    """Main demo entry point."""
    print("\n" + "=" * 70)
    print("🌟 ADK + A2A DEMO")
    print("   Google's Intended Way to Use A2A")
    print("=" * 70)
    print("""
This demo shows PROPER A2A usage:

1. Discovery Service for dynamic agent registration
   - Agents register themselves on startup
   - Host agent queries to discover available agents
   - No hardcoded agent URLs!

2. Remote agents exposed via to_a2a()
   - Automatic AgentCard generation
   - Proper A2A protocol implementation
   - Tools become agent capabilities

3. Host agent with RemoteA2aAgent sub-agents
   - Dynamically discovers agents from Discovery Service
   - Remote agents wrapped as local sub-agents
   - LLM sees all agents and their descriptions
   - Model DECIDES which agent to delegate to

4. Dynamic routing (not hardcoded!)
   - No "if task needs research, call research agent"
   - The LLM understands the task and chooses agents
   - Can call agents in any order or combination
""")

    if not check_aws_credentials():
        return

    # Demo task
    demo_task = """Create a comprehensive guide about storing API credentials
securely in Python applications. Research the best practices, write a
clear guide, and verify the content doesn't accidentally include any
real secrets."""

    # Allow custom task from command line
    if len(sys.argv) > 1:
        demo_task = " ".join(sys.argv[1:])

    print(f"📋 Task: {demo_task}")

    discovery_proc = None
    processes = []

    try:
        # Start Discovery Service first
        discovery_proc = start_discovery_service()

        # Start remote agents (they will register with Discovery Service)
        processes = start_remote_agents()

        print("\n" + "=" * 70)
        print("✅ SERVICES RUNNING")
        print("=" * 70)
        print("""
Discovery Service:
- http://localhost:9999/agents - List all registered agents
- http://localhost:9999/docs   - API documentation

A2A Agents available (exposed via to_a2a, registered with Discovery):
- Research Agent (:10001) - http://localhost:10001/.well-known/agent-card.json
- Writer Agent (:10002)   - http://localhost:10002/.well-known/agent-card.json
- Security Agent (:10003) - http://localhost:10003/.well-known/agent-card.json

The Host Agent will now:
1. Query the Discovery Service to find available agents
2. Create RemoteA2aAgent wrappers for each discovered agent
3. Present them to the LLM as available sub-agents
4. Let the LLM decide which to call and in what order
""")

        # Run the host agent
        result = asyncio.run(run_host_agent(demo_task))

        print("\n" + "=" * 70)
        print("🎉 DEMO COMPLETE")
        print("=" * 70)
        print("\nFinal Result:")
        print("-" * 70)
        if result:
            print(result[:3000] if len(result) > 3000 else result)
            if len(result) > 3000:
                print(f"\n... (truncated, full result is {len(result)} chars)")

    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Stop all processes
        stop_servers(processes)

        # Stop Discovery Service
        if discovery_proc:
            print("   Stopping Discovery Service...")
            discovery_proc.terminate()
            try:
                discovery_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                discovery_proc.kill()


if __name__ == "__main__":
    main()
