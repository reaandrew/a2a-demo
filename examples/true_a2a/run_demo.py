#!/usr/bin/env python
"""
TRUE A2A Demo Runner - Agents Calling Agents Directly

This demo shows REAL Agent-to-Agent communication:

1. Discovery Service starts and agents register themselves
2. User calls Research Agent
3. Research Agent does research
4. Research Agent queries Discovery Service to find Writer Agent
5. Research Agent CALLS Writer Agent directly (TRUE A2A!)
6. Writer Agent does writing
7. Writer Agent queries Discovery Service to find Security Agent
8. Writer Agent CALLS Security Agent directly (TRUE A2A!)
9. Security Agent scans and returns
10. Result bubbles back up the chain

The KEY difference: Agents discover and call each other directly.
There is NO central orchestrator routing messages.
"""

import subprocess
import time
import sys
import os
import asyncio
import httpx
import uuid

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2a.client import A2AClient
from a2a.client.card_resolver import A2ACardResolver
from a2a.types import MessageSendParams, SendMessageRequest, Message, Part, TextPart


def start_discovery_service():
    """Start the Discovery Service."""
    print("=" * 70)
    print("🌐 STARTING DISCOVERY SERVICE")
    print("=" * 70)

    proc = subprocess.Popen(
        [sys.executable, "-m", "discovery_service"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    print("   Discovery Service starting on port 9999...")
    time.sleep(2)  # Give it time to start

    return proc


def start_agent_servers():
    """Start all agent servers as background processes."""
    print("\n" + "=" * 70)
    print("🚀 STARTING A2A AGENT SERVERS (TRUE A2A Pattern)")
    print("=" * 70)

    processes = []
    agents = [
        ("research_agent", 10001, "Research Agent"),
        ("writer_agent", 10002, "Writer Agent"),
        ("security_agent", 10003, "Security Agent"),
    ]

    for module, port, name in agents:
        print(f"\n📡 Starting {name} on port {port}...")
        proc = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        processes.append((proc, name, port))
        time.sleep(1)

    print("\n⏳ Waiting for agents to register with Discovery Service...")
    time.sleep(3)

    return processes


def stop_all_servers(discovery_proc, agent_processes):
    """Stop all server processes."""
    print("\n\n" + "=" * 70)
    print("🛑 STOPPING ALL SERVERS")
    print("=" * 70)

    for proc, name, port in agent_processes:
        print(f"   Stopping {name}...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("   Stopping Discovery Service...")
    discovery_proc.terminate()
    try:
        discovery_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        discovery_proc.kill()

    print("   All servers stopped.")


async def trigger_a2a_chain(task: str):
    """
    Trigger the A2A chain by calling ONLY the Research Agent.

    The Research Agent will then:
    - Do its work
    - Discover and call the Writer Agent (A2A!)
    - Writer Agent will discover and call Security Agent (A2A!)
    - Result bubbles back

    We only call ONE agent - the chain happens automatically!
    """
    print("\n" + "=" * 70)
    print("🎯 TRIGGERING A2A CHAIN")
    print("=" * 70)
    print(f"\nTask: {task}")
    print("\n📤 Calling Research Agent (it will chain to others via A2A)...\n")

    research_url = "http://localhost:10001/"

    async with httpx.AsyncClient(timeout=300.0) as http_client:
        # Discover Research Agent
        resolver = A2ACardResolver(httpx_client=http_client, base_url=research_url)
        card = await resolver.get_agent_card()
        print(f"✅ Discovered: {card.name}")

        # Create A2A client
        client = A2AClient(
            httpx_client=httpx.AsyncClient(timeout=300.0),
            agent_card=card,
        )

        # Build message
        msg = Message(
            messageId=str(uuid.uuid4()),
            role="user",
            parts=[Part(root=TextPart(text=task))],
        )
        request = SendMessageRequest(
            id=str(uuid.uuid4()),
            params=MessageSendParams(message=msg),
        )

        # Call Research Agent - it will chain to others!
        print("\n" + "-" * 70)
        print("AGENT CHAIN EXECUTION (watch the agent logs above)")
        print("-" * 70 + "\n")

        response = await client.send_message(request)

        # Extract result
        result_text = ""
        if hasattr(response, 'root') and response.root:
            resp = response.root
            if hasattr(resp, 'result') and resp.result:
                result = resp.result
                if hasattr(result, 'parts'):
                    for part in result.parts or []:
                        if hasattr(part, 'root') and hasattr(part.root, 'text'):
                            result_text += part.root.text

        return result_text


def main():
    """Main demo entry point."""
    print("\n" + "=" * 70)
    print("🌟 TRUE A2A (AGENT-TO-AGENT) DEMO")
    print("   Agents Discover and Call Each Other Directly")
    print("=" * 70)
    print("""
This demo shows REAL Agent-to-Agent communication with dynamic discovery:

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   ┌───────────────────┐                                      │
│   │ Discovery Service │ ◄── All agents register here        │
│   └─────────┬─────────┘                                      │
│             │                                                │
│   ┌─────────┴─────────┐                                      │
│   │                   │                                      │
│   ▼                   ▼                                      │
│ User ──► Research ──► Writer ──► Security                    │
│          Agent        Agent       Agent                      │
│            │            │           │                        │
│            ▼            ▼           ▼                        │
│        Research     Writing     Security                     │
│        + Query      + Query     Scan                        │
│        Discovery    Discovery   (end)                        │
│        + Call A2A   + Call A2A                              │
│                                                              │
│   Each agent queries Discovery Service to find the next     │
│   Each agent CALLS the next directly (no orchestrator!)     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
""")

    # Demo task
    demo_task = """Research best practices for storing API credentials in Python applications,
then create a guide about it."""

    # Allow custom task from command line
    if len(sys.argv) > 1:
        demo_task = " ".join(sys.argv[1:])

    print(f"📋 Task: {demo_task}")

    discovery_proc = None
    agent_processes = []

    try:
        # Start Discovery Service first
        discovery_proc = start_discovery_service()

        # Start agent servers (they will register with Discovery Service)
        agent_processes = start_agent_servers()

        print("\n" + "=" * 70)
        print("✅ ALL SERVERS RUNNING")
        print("=" * 70)
        print("""
Services running:
- Discovery Service (:9999)  - agents register here and query for peers
- Research Agent (:10001)    - queries Discovery, calls Writer directly
- Writer Agent (:10002)      - queries Discovery, calls Security directly
- Security Agent (:10003)    - end of chain

Watch as each agent discovers and calls the next in the chain!
""")

        # Run the A2A chain
        result = asyncio.run(trigger_a2a_chain(demo_task))

        print("\n" + "=" * 70)
        print("🎉 A2A CHAIN COMPLETE")
        print("=" * 70)
        print("\nFinal Result (bubbled back through the chain):")
        print("-" * 70)
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
        stop_all_servers(discovery_proc, agent_processes)


if __name__ == "__main__":
    main()
