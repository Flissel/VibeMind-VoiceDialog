#!/usr/bin/env python
"""
VibeMind Agent Simulation CLI

Runs complex multi-turn conversation scenarios through the swarm backend
and generates comprehensive reports.

Usage:
    python run_agent_simulation.py                    # Run all scenarios
    python run_agent_simulation.py --quick            # Run quick scenarios only
    python run_agent_simulation.py --scenario "Feature Design"
    python run_agent_simulation.py --output report.md
    python run_agent_simulation.py --verbose
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime

# Add python directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


async def run_simulation(args):
    """Run the simulation with given arguments."""
    from swarm.simulation import ScenarioRunner, SimulationReportGenerator
    from swarm.simulation.scenarios import (
        ALL_SCENARIOS,
        QUICK_SCENARIOS,
        CORE_SCENARIOS,
        get_scenario_by_name,
        get_scenarios_by_tag,
    )

    print("=" * 60)
    print("   VibeMind Agent Simulation")
    print("=" * 60)

    # Determine which scenarios to run
    scenarios = []

    if args.scenario:
        # Single scenario by name
        try:
            scenarios = [get_scenario_by_name(args.scenario)]
            print(f"\nRunning scenario: {args.scenario}")
        except ValueError as e:
            print(f"\nError: {e}")
            print("\nAvailable scenarios:")
            for s in ALL_SCENARIOS:
                print(f"  - {s.name}")
            return 1

    elif args.tag:
        # Scenarios by tag
        scenarios = get_scenarios_by_tag(args.tag)
        if not scenarios:
            print(f"\nNo scenarios found with tag: {args.tag}")
            print("\nAvailable tags:")
            all_tags = set()
            for s in ALL_SCENARIOS:
                all_tags.update(s.tags)
            for tag in sorted(all_tags):
                print(f"  - {tag}")
            return 1
        print(f"\nRunning {len(scenarios)} scenarios with tag '{args.tag}'")

    elif args.quick:
        scenarios = QUICK_SCENARIOS
        print(f"\nRunning {len(scenarios)} quick scenarios")

    elif args.core:
        scenarios = CORE_SCENARIOS
        print(f"\nRunning {len(scenarios)} core scenarios")

    else:
        scenarios = ALL_SCENARIOS
        print(f"\nRunning all {len(scenarios)} scenarios")

    # Show scenario list
    print("\nScenarios to run:")
    for s in scenarios:
        print(f"  - {s.name} ({len(s.turns)} turns)")

    # Initialize runner
    print("\nInitializing orchestrator...")
    runner = ScenarioRunner(verbose=args.verbose)

    # Run scenarios
    print(f"\nStarting simulation...")
    print("(This may take a few minutes)\n")

    results = await runner.run_all(scenarios)

    # Generate report
    report_gen = SimulationReportGenerator()

    # Console summary
    print(report_gen.generate_console_summary(results))

    # Save markdown report if requested
    if args.output:
        report_md = report_gen.generate(results)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"\nReport saved to: {args.output}")

    # Also save to default location
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = f"simulation_report_{timestamp}.md"
    report_md = report_gen.generate(results)

    # Ensure output directory exists
    reports_dir = os.path.join(os.path.dirname(__file__), "evaluation_reports")
    os.makedirs(reports_dir, exist_ok=True)

    report_path = os.path.join(reports_dir, default_output)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"Full report saved to: {report_path}")

    # Return exit code based on results
    all_passed = all(r.success for r in results)
    return 0 if all_passed else 1


def list_scenarios():
    """List all available scenarios."""
    from swarm.simulation.scenarios import ALL_SCENARIOS

    print("\nAvailable Scenarios:")
    print("-" * 40)

    for scenario in ALL_SCENARIOS:
        tags_str = ", ".join(scenario.tags) if scenario.tags else "none"
        print(f"\n  {scenario.name}")
        print(f"    Description: {scenario.description}")
        print(f"    Turns: {len(scenario.turns)}")
        print(f"    Tags: {tags_str}")

    print("\n")


def main():
    parser = argparse.ArgumentParser(
        description="VibeMind Agent Simulation - Test complex conversations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent_simulation.py                    Run all scenarios
  python run_agent_simulation.py --quick            Run quick scenarios only
  python run_agent_simulation.py --core             Run core scenarios only
  python run_agent_simulation.py --scenario "Feature Design"
  python run_agent_simulation.py --tag "context"    Run scenarios with tag
  python run_agent_simulation.py --output report.md
  python run_agent_simulation.py --verbose          Show turn details
  python run_agent_simulation.py --list             List all scenarios
        """
    )

    parser.add_argument(
        "--scenario", "-s",
        help="Run a specific scenario by name"
    )
    parser.add_argument(
        "--tag", "-t",
        help="Run scenarios with a specific tag"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick scenarios only (faster)"
    )
    parser.add_argument(
        "--core", "-c",
        action="store_true",
        help="Run core scenarios only"
    )
    parser.add_argument(
        "--output", "-o",
        help="Save report to specified file"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed turn output"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available scenarios"
    )

    args = parser.parse_args()

    # Check for list command
    if args.list:
        list_scenarios()
        return 0

    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set!")
        print("Please set it in .env or export OPENROUTER_API_KEY=sk-or-xxx")
        return 1

    # Run simulation
    try:
        exit_code = asyncio.run(run_simulation(args))
        return exit_code
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted.")
        return 130
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
