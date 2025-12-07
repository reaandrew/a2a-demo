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
import logging

# Suppress experimental warnings from ADK
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")
# Suppress litellm warnings
warnings.filterwarnings("ignore", module="litellm")
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

# Configure LiteLLM to handle Bedrock message format
import litellm
litellm.modify_params = True

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
    print("\n📡 Starting Discovery Service (:9999)...")

    proc = subprocess.Popen(
        [sys.executable, "discovery_service.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    time.sleep(2)

    return proc


def start_remote_agents():
    """Start all remote A2A agent servers."""
    print("📡 Starting A2A agents...")

    processes = []
    agents = [
        ("research_agent", 10001, "Research Agent"),
        ("writer_agent", 10002, "Writer Agent"),
        ("security_agent", 10003, "Security Agent"),
    ]

    for module, port, name in agents:
        print(f"   - {name} (:{port})")
        proc = subprocess.Popen(
            [sys.executable, f"{module}.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=None,  # Let agent output flow to console
            stderr=subprocess.DEVNULL,  # Suppress stderr noise
            env=os.environ.copy(),
        )
        processes.append((proc, name, port))
        time.sleep(5)

    print("⏳ Waiting for registration...")
    time.sleep(8)

    return processes


def stop_servers(processes):
    """Stop all server processes."""
    print("\n🛑 Stopping servers...")

    for proc, name, port in processes:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("   Done.")


async def run_host_agent(task: str, max_turns: int = 5):
    """
    Run the host agent with a task using explicit multi-turn orchestration.

    This implements the loop:
    1. Ask LLM: "Given these agents and this task, which agent should I use next?"
    2. Call that agent, get the result
    3. Go back to LLM with the result: "Here's what we got. What's next?"
    4. Repeat until LLM says "done" OR we hit max_turns
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types

    from host_agent import create_host_agent_with_discovery

    print("\n" + "=" * 60)
    print("🎯 RUNNING HOST AGENT")
    print("=" * 60)
    print(f"📋 Task: {task[:80]}...")
    print(f"🔄 Max turns: {max_turns}")
    print("")

    # Create host agent with dynamic discovery
    print("📡 Querying Discovery Service...")
    host_agent = await create_host_agent_with_discovery()

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

    # Initial message to the host agent
    current_message = f"""Task: {task}

You must complete this task by delegating to the appropriate agents.
For each step, call ONE agent, wait for its response, then decide what to do next.

Available actions:
- Call an agent by delegating to it
- Say "TASK_COMPLETE" when you have finished all steps

Start by deciding which agent to call first."""

    final_response = ""
    all_outputs = []

    print("\n" + "-" * 60)
    print("🚀 Starting orchestration loop...")
    print("-" * 60)

    for turn in range(max_turns):
        print(f"\n[Turn {turn + 1}/{max_turns}]")
        print("   📤 Calling Bedrock LLM (Host Agent)...")

        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=current_message)],
        )

        turn_response = ""
        agent_called = None
        agent_output = ""
        last_author = None

        async for event in runner.run_async(
            user_id="demo_user",
            session_id=session.id,
            new_message=content,
        ):
            author = event.author

            # Log agent activations (concise)
            if author != last_author and author:
                if author == "host_agent":
                    pass  # Don't log host agent repeatedly
                elif "research" in author.lower():
                    print("   🔍 Research Agent activated")
                    print("      → Bedrock LLM: researching topic...")
                    agent_called = "research_agent"
                elif "writer" in author.lower():
                    print("   ✍️  Writer Agent activated")
                    print("      → Bedrock LLM: writing content...")
                    agent_called = "writer_agent"
                elif "security" in author.lower():
                    print("   🛡️  Security Agent activated")
                    print("      → GitGuardian API: POST /v1/scan")
                    agent_called = "security_agent"
                last_author = author

            # Collect output silently (no printing)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        text = part.text.strip()
                        if text:
                            if author == "host_agent":
                                turn_response += text + "\n"
                            elif agent_called:
                                agent_output += text + "\n"

        # Log agent completion
        if agent_called:
            output_len = len(agent_output)
            print(f"   ✅ {agent_called} completed ({output_len} chars)")

        # Check if task is complete
        if "TASK_COMPLETE" in turn_response.upper():
            print("\n" + "=" * 60)
            print("✅ TASK_COMPLETE - All agents finished")
            print("=" * 60)
            final_response = turn_response
            break

        # If an agent was called, prepare the next turn's message
        if agent_called:
            all_outputs.append({
                "turn": turn + 1,
                "agent": agent_called,
                "output": agent_output
            })

            current_message = f"""The {agent_called} has completed its work.

Here is a summary of what has been done so far:
{chr(10).join([f"- Turn {o['turn']}: {o['agent']} was called" for o in all_outputs])}

Original task: {task}

What should we do next?
- If there are more steps needed, call the next appropriate agent.
- If all steps are complete, respond with "TASK_COMPLETE" and provide a final summary.

Decide your next action:"""

            final_response = turn_response
        else:
            # No agent was called
            if turn > 0:
                print("   ℹ️  No agent called - assuming complete")
                break

    if turn == max_turns - 1 and "TASK_COMPLETE" not in turn_response.upper():
        print(f"\n⏱️  Reached max turns ({max_turns})")

    return final_response


def main():
    """Main demo entry point."""
    print("\n" + "=" * 60)
    print("🌟 ADK + A2A DEMO - Multi-Agent Orchestration")
    print("=" * 60)

    if not check_aws_credentials():
        return

    # Demo task - explicitly asks for anti-pattern examples with realistic credentials
    demo_task = """Create a guide about storing API credentials securely in Python.
Include a "Common Mistakes" section with realistic code examples showing what NOT to do
(use realistic-looking fake API keys like AKIA... or sk_live_... in the bad examples).
Then show the correct approaches. Finally, scan the content for any exposed secrets."""

    # Allow custom task from command line
    if len(sys.argv) > 1:
        demo_task = " ".join(sys.argv[1:])

    print(f"📋 Task: {demo_task[:60]}...")

    discovery_proc = None
    processes = []

    try:
        # Start Discovery Service first
        discovery_proc = start_discovery_service()

        # Start remote agents (they will register with Discovery Service)
        processes = start_remote_agents()

        print("\n✅ All services running")

        # Run the host agent
        result = asyncio.run(run_host_agent(demo_task))

        print("\n🎉 DEMO COMPLETE")

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        stop_servers(processes)
        if discovery_proc:
            discovery_proc.terminate()
            try:
                discovery_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                discovery_proc.kill()


if __name__ == "__main__":
    main()
