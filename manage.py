#!/usr/bin/env python3
"""
Unified Management Script

Common operations for the project:
- test: Run comprehensive tests
- coordinate: Auto-coordinate tasks
- scratchpad: Interact with scratchpad
- scheduler: Manage scheduled tasks
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests():
    """Run comprehensive tests for both agents."""
    print("\n" + "="*60)
    print("Running Comprehensive Tests")
    print("="*60 + "\n")
    
    base_dir = Path(__file__).parent
    import os
    mcp_url = os.environ.get("MCP_URL", "https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp")
    
    # Test Anthropic Agent
    print("Testing Anthropic Agent...")
    print(f"MCP URL: {mcp_url}\n")
    anthropic_dir = base_dir / "ANTHROPIC_AGENT"
    if (anthropic_dir / "test_agent_comprehensive.py").exists():
        subprocess.run(
            [sys.executable, "test_agent_comprehensive.py", "--mcp-url", mcp_url],
            cwd=anthropic_dir
        )
    else:
        print("⚠️  test_agent_comprehensive.py not found in ANTHROPIC_AGENT")
    
    print("\n" + "-"*60 + "\n")
    
    # Test MCP Agent
    print("Testing MCP Agent...")
    print(f"MCP URL: {mcp_url}\n")
    mcp_dir = base_dir / "MCP_AGENT"
    if (mcp_dir / "test_agent_comprehensive.py").exists():
        subprocess.run(
            [sys.executable, "test_agent_comprehensive.py", "--mcp-url", mcp_url, "--provider", "anthropic"],
            cwd=mcp_dir
        )
    else:
        print("⚠️  test_agent_comprehensive.py not found in MCP_AGENT")
    
    print("\n" + "="*60)
    print("Tests Complete!")
    print("="*60 + "\n")


def run_coordinate():
    """Run auto-coordination of tasks."""
    print("\n" + "="*60)
    print("Auto-Coordinating Tasks")
    print("="*60 + "\n")
    
    base_dir = Path(__file__).parent
    coord_script = base_dir / "auto_coordinate_tasks.py"
    
    if coord_script.exists():
        subprocess.run([sys.executable, str(coord_script)])
    else:
        print("❌ auto_coordinate_tasks.py not found")


def run_scratchpad(args):
    """Interact with scratchpad."""
    base_dir = Path(__file__).parent
    scratchpad_script = base_dir / "agent_scratchpad.py"
    
    if not scratchpad_script.exists():
        print("❌ agent_scratchpad.py not found")
        return
    
    # Build command
    cmd = [sys.executable, str(scratchpad_script)]
    
    if args.agent:
        cmd.extend(["--agent", args.agent])
    
    if args.summary:
        cmd.append("--summary")
    elif args.list_tasks:
        cmd.append("--list-tasks")
    elif args.read_notes:
        cmd.append("--read-notes")
    elif args.note:
        cmd.extend(["--note", args.note])
        if args.priority:
            cmd.extend(["--priority", args.priority])
        if args.tags:
            cmd.extend(["--tags", args.tags])
    
    subprocess.run(cmd)


def run_scheduler(args):
    """Manage scheduled tasks."""
    try:
        from agent_coordination.scheduler import TaskScheduler
        import asyncio
        
        scheduler = TaskScheduler()
        
        if args.list:
            tasks = scheduler.get_tasks()
            if tasks:
                print("\n📋 Scheduled Tasks:\n")
                for task in tasks:
                    status_icon = "✓" if task.status.value == "active" else "⏸" if task.status.value == "paused" else "✗"
                    print(f"{status_icon} {task.name} ({task.schedule_type.value})")
                    print(f"   Status: {task.status.value}")
                    if task.next_run:
                        print(f"   Next run: {task.next_run}")
                    print()
            else:
                print("No scheduled tasks")
        
        elif args.add_recurring:
            name, func, interval = args.add_recurring
            task_id = scheduler.schedule_recurring(name, func, int(interval))
            print(f"✓ Scheduled recurring task: {task_id}")
        
        elif args.add_milestone:
            name, func, condition = args.add_milestone
            task_id = scheduler.schedule_milestone(name, func, condition)
            print(f"✓ Scheduled milestone task: {task_id}")
        
        elif args.run_once:
            asyncio.run(scheduler.run_once())
            print("✓ Scheduler check complete")
        
        elif args.start:
            print("Starting scheduler (Ctrl+C to stop)...")
            asyncio.run(scheduler.run_loop())
        
        else:
            summary = scheduler.get_summary()
            print(f"\n📊 Scheduler Summary:")
            print(f"   Total tasks: {summary['total_tasks']}")
            print(f"   Active: {summary['active_tasks']}")
            print(f"   Running: {summary['running']}\n")
    
    except ImportError as e:
        print(f"❌ Error importing scheduler: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified management script for the project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 manage.py test                    # Run all tests
  python3 manage.py coordinate               # Auto-coordinate tasks
  python3 manage.py scratchpad --summary    # Show scratchpad summary
  python3 manage.py scheduler --list        # List scheduled tasks
  python3 manage.py scheduler --add-recurring "Auto-coord" "auto_coordinate_tasks" 300
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run comprehensive tests")
    
    # Coordinate command
    coord_parser = subparsers.add_parser("coordinate", help="Auto-coordinate tasks")
    
    # Scratchpad command
    scratchpad_parser = subparsers.add_parser("scratchpad", help="Interact with scratchpad")
    scratchpad_parser.add_argument("--agent", help="Agent name")
    scratchpad_parser.add_argument("--summary", action="store_true", help="Show summary")
    scratchpad_parser.add_argument("--list-tasks", action="store_true", help="List tasks")
    scratchpad_parser.add_argument("--read-notes", action="store_true", help="Read notes")
    scratchpad_parser.add_argument("--note", help="Leave a note")
    scratchpad_parser.add_argument("--priority", choices=["low", "normal", "high"], help="Note priority")
    scratchpad_parser.add_argument("--tags", help="Comma-separated tags")
    
    # Scheduler command
    scheduler_parser = subparsers.add_parser("scheduler", help="Manage scheduled tasks")
    scheduler_parser.add_argument("--list", action="store_true", help="List scheduled tasks")
    scheduler_parser.add_argument("--add-recurring", nargs=3, metavar=("NAME", "FUNCTION", "INTERVAL"), help="Add recurring task")
    scheduler_parser.add_argument("--add-milestone", nargs=3, metavar=("NAME", "FUNCTION", "CONDITION"), help="Add milestone task")
    scheduler_parser.add_argument("--run-once", action="store_true", help="Run scheduler once")
    scheduler_parser.add_argument("--start", action="store_true", help="Start scheduler loop")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "test":
        run_tests()
    elif args.command == "coordinate":
        run_coordinate()
    elif args.command == "scratchpad":
        run_scratchpad(args)
    elif args.command == "scheduler":
        run_scheduler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
