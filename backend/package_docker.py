#!/usr/bin/env python3
"""
Package Lambda functions using Docker for AWS compatibility.
Runs each agent's package_docker.py script.

Usage:
    uv run package_docker.py              # Package ALL agents
    uv run package_docker.py tagger       # Package only tagger
    uv run package_docker.py reporter charter  # Package reporter and charter
    uv run package_docker.py --list       # List available agents
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

ALL_AGENTS = ["tagger", "reporter", "charter", "retirement", "planner"]


def run_packaging(agent_name):
    """Run packaging for a specific agent."""
    agent_dir = Path(__file__).parent / agent_name
    package_script = agent_dir / "package_docker.py"

    if not package_script.exists():
        print(f"  ❌ {agent_name}: Missing package_docker.py")
        return False

    print(f"\n📦 Packaging {agent_name.upper()} agent...")
    print(f"  Running: cd {agent_dir} && uv run package_docker.py")

    try:
        result = subprocess.run(
            ["uv", "run", "package_docker.py"], cwd=str(agent_dir), capture_output=True, text=True
        )

        if result.returncode == 0:
            # Look for the created zip file
            zip_files = list(agent_dir.glob("*.zip"))
            if zip_files:
                zip_file = zip_files[0]
                size_mb = zip_file.stat().st_size / (1024 * 1024)
                print(f"  ✅ Created: {zip_file.name} ({size_mb:.1f} MB)")
                return True
            else:
                print(f"  ⚠️  Warning: No zip file found after packaging")
                return True
        else:
            print(
                f"  ❌ Error with {agent_name.upper()}:\nPlease note that warnings about uv environment can be ignored:\n{result.stderr}\nOutput from script is:\n{result.stdout}"
            )
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Package Lambda functions - all or individually."""
    parser = argparse.ArgumentParser(
        description="Package Lambda functions using Docker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run package_docker.py                    # Package ALL agents
  uv run package_docker.py tagger             # Package only tagger
  uv run package_docker.py reporter charter   # Package reporter and charter
  uv run package_docker.py --list             # List available agents
        """,
    )
    parser.add_argument(
        "agents",
        nargs="*",
        help=f"Agent(s) to package. If not specified, packages all. Choices: {', '.join(ALL_AGENTS)}",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_agents",
        help="List all available agents",
    )
    args = parser.parse_args()

    if args.list_agents:
        print("Available agents:")
        for agent in ALL_AGENTS:
            agent_dir = Path(__file__).parent / agent
            has_script = (agent_dir / "package_docker.py").exists()
            has_zip = list(agent_dir.glob("*.zip"))
            status = "📦" if has_zip else "  "
            script_status = "✅" if has_script else "❌"
            print(f"  {status} {agent.ljust(12)} {script_status} package_docker.py", end="")
            if has_zip:
                size_mb = has_zip[0].stat().st_size / (1024 * 1024)
                print(f"  ({has_zip[0].name}, {size_mb:.1f} MB)", end="")
            print()
        return 0

    # Determine which agents to package
    if args.agents:
        # Validate agent names
        agents_to_package = []
        for agent in args.agents:
            agent_lower = agent.lower()
            if agent_lower not in ALL_AGENTS:
                print(f"❌ Unknown agent: '{agent}'. Available: {', '.join(ALL_AGENTS)}")
                return 1
            agents_to_package.append(agent_lower)
    else:
        agents_to_package = ALL_AGENTS

    label = ", ".join(a.upper() for a in agents_to_package)
    print("=" * 60)
    print(f"PACKAGING LAMBDA FUNCTIONS: {label}")
    print("=" * 60)

    results = {}
    for agent in agents_to_package:
        success = run_packaging(agent)
        results[agent] = success

    print("\n" + "=" * 60)
    print("PACKAGING SUMMARY")
    print("=" * 60)

    success_count = sum(1 for s in results.values() if s)
    total_count = len(results)

    for agent, success in results.items():
        status = "✅ Success" if success else "❌ Failed"
        print(f"{agent.ljust(12)}: {status}")

    print("\n" + "=" * 60)
    print(f"Packaged: {success_count}/{total_count}")

    if success_count == total_count:
        print("\n✅ ALL REQUESTED LAMBDA FUNCTIONS PACKAGED SUCCESSFULLY!")
        print("\nNext steps:")
        print("1. Deploy infrastructure: cd terraform/6_agents && terraform apply")
        print("2. Deploy Lambda functions: cd backend && uv run deploy_all_lambdas.py")
        return 0
    else:
        print(f"\n⚠️  {total_count - success_count} agents failed to package")
        return 1


if __name__ == "__main__":
    sys.exit(main())
