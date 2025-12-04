#!/usr/bin/env python
"""
Hub-and-Spoke Demo Runner

This demo shows the HUB-AND-SPOKE pattern where:
- A Discovery Service allows agents to register themselves
- A central ORCHESTRATOR queries the Discovery Service to find agents
- The ORCHESTRATOR discovers and calls all agents via A2A protocol
- Agents do NOT communicate with each other
- All data flows through the orchestrator

Flow: User -> Orchestrator -> Research -> Orchestrator -> Writer -> Orchestrator -> Security -> Orchestrator -> User
"""

import subprocess
import time
import sys
import os
import asyncio

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import Orchestrator


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
    print("🚀 STARTING AGENT SERVERS (Hub-and-Spoke Pattern)")
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


async def run_orchestrator(task: str):
    """Run the orchestrator pipeline."""
    orchestrator = Orchestrator()
    await orchestrator.discover_agents_from_registry()
    return await orchestrator.run_pipeline(task)


def main():
    """Main demo entry point."""
    print("\n" + "=" * 70)
    print("🌟 HUB-AND-SPOKE PATTERN DEMO")
    print("   Central Orchestrator Coordinates All Agents")
    print("=" * 70)
    print("""
This demo shows the HUB-AND-SPOKE pattern with dynamic agent discovery:

┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│     ┌───────────────────┐                                       │
│     │ Discovery Service │ ◄── Agents register on startup       │
│     └─────────┬─────────┘                                       │
│               │                                                 │
│               ▼                                                 │
│      ┌─────────────────┐                                        │
│      │  ORCHESTRATOR   │ ◄── Queries Discovery Service         │
│      │   (Central Hub) │                                        │
│      └────────┬────────┘                                        │
│               │                                                 │
│  ┌────────────┼────────────────┐                                │
│  │            │                │                                │
│  ▼            ▼                ▼                                │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│ │ Research │ │  Writer  │ │ Security │                         │
│ │  Agent   │ │  Agent   │ │  Agent   │                         │
│ └──────────┘ └──────────┘ └──────────┘                         │
│                                                                 │
│   KEY: Agents do NOT talk to each other!                       │
│   All data flows through the orchestrator.                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
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
- Discovery Service (:9999)  - central agent registry
- Research Agent (:10001)    - registered with Discovery Service
- Writer Agent (:10002)      - registered with Discovery Service
- Security Agent (:10003)    - registered with Discovery Service

The ORCHESTRATOR will now:
1. Query the Discovery Service to find available agents
2. Fetch AgentCards from each agent using A2A SDK
3. Coordinate the workflow through each agent
""")

        # Run the orchestrator
        result = asyncio.run(run_orchestrator(demo_task))

        print("\n" + "=" * 70)
        print("🎉 PIPELINE COMPLETE")
        print("=" * 70)
        print("\nFinal Result:")
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
