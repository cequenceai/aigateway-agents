"""
Agent tracking and KPI reporting module.
Tracks tool usage, agent thinking, and provides summary reports.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict


@dataclass
class ToolCall:
    """Represents a single tool call."""
    tool_name: str
    arguments: Dict[str, Any]
    timestamp: float
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    result_preview: Optional[str] = None  # First 200 chars of result


@dataclass
class AgentThought:
    """Represents agent reasoning/thinking."""
    content: str
    timestamp: float
    source: str = "agent"  # "agent", "system", "user"


@dataclass
class AgentSession:
    """Tracks a complete agent session."""
    agent_name: str
    start_time: float
    end_time: Optional[float] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    thoughts: List[AgentThought] = field(default_factory=list)
    clarification_requests: List[Dict[str, Any]] = field(default_factory=list)
    task: Optional[str] = None
    final_output: Optional[str] = None
    success: bool = False
    error: Optional[str] = None
    
    def add_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        duration: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None,
        result_preview: Optional[str] = None
    ):
        """Add a tool call to the session."""
        call = ToolCall(
            tool_name=tool_name,
            arguments=arguments,
            timestamp=time.time(),
            duration=duration,
            success=success,
            error=error,
            result_preview=result_preview
        )
        self.tool_calls.append(call)
    
    def add_thought(self, content: str, source: str = "agent"):
        """Add an agent thought/reasoning."""
        thought = AgentThought(
            content=content,
            timestamp=time.time(),
            source=source
        )
        self.thoughts.append(thought)
    
    def add_clarification(self, question: str, response: Optional[str] = None):
        """Record a clarification request."""
        self.clarification_requests.append({
            "question": question,
            "response": response,
            "timestamp": time.time()
        })
    
    def get_duration(self) -> float:
        """Get total session duration."""
        end = self.end_time or time.time()
        return end - self.start_time
    
    def get_tool_usage_summary(self) -> Dict[str, Any]:
        """Get summary of tool usage."""
        tool_counts = defaultdict(int)
        tool_durations = defaultdict(list)
        tool_errors = defaultdict(int)
        
        for call in self.tool_calls:
            tool_counts[call.tool_name] += 1
            if call.duration:
                tool_durations[call.tool_name].append(call.duration)
            if not call.success:
                tool_errors[call.tool_name] += 1
        
        summary = {
            "total_calls": len(self.tool_calls),
            "unique_tools": len(tool_counts),
            "tool_counts": dict(tool_counts),
            "tool_errors": dict(tool_errors),
            "tool_avg_durations": {}
        }
        
        # Calculate average durations
        for tool_name, durations in tool_durations.items():
            if durations:
                summary["tool_avg_durations"][tool_name] = sum(durations) / len(durations)
        
        return summary


class AgentTracker:
    """Main tracker for agent sessions."""
    
    def __init__(self):
        self.sessions: List[AgentSession] = []
        self.current_session: Optional[AgentSession] = None
    
    def start_session(self, agent_name: str, task: Optional[str] = None) -> AgentSession:
        """Start a new agent session."""
        session = AgentSession(
            agent_name=agent_name,
            start_time=time.time(),
            task=task
        )
        self.sessions.append(session)
        self.current_session = session
        return session
    
    def end_session(self, success: bool = True, error: Optional[str] = None, final_output: Optional[str] = None):
        """End the current session."""
        if self.current_session:
            self.current_session.end_time = time.time()
            self.current_session.success = success
            self.current_session.error = error
            self.current_session.final_output = final_output
            self.current_session = None
    
    def get_current_session(self) -> Optional[AgentSession]:
        """Get the current active session."""
        return self.current_session
    
    def print_kpi_summary(self, session: Optional[AgentSession] = None):
        """Print a formatted KPI summary."""
        if session is None:
            session = self.current_session
        
        if session is None:
            print("⚠️  No session data available")
            return
        
        print("\n" + "=" * 80)
        print(f"📊 AGENT SESSION KPI SUMMARY - {session.agent_name.upper()}")
        print("=" * 80)
        print()
        
        # Basic Info
        print("📋 BASIC INFO:")
        print(f"   Task: {session.task or 'N/A'}")
        print(f"   Duration: {session.get_duration():.2f} seconds")
        print(f"   Status: {'✅ SUCCESS' if session.success else '❌ FAILED'}")
        if session.error:
            print(f"   Error: {session.error}")
        print()
        
        # Tool Usage
        tool_summary = session.get_tool_usage_summary()
        print("🔧 TOOL USAGE:")
        print(f"   Total Tool Calls: {tool_summary['total_calls']}")
        print(f"   Unique Tools Used: {tool_summary['unique_tools']}")
        if tool_summary['tool_counts']:
            print("   Tool Breakdown:")
            for tool_name, count in sorted(tool_summary['tool_counts'].items(), key=lambda x: x[1], reverse=True):
                error_count = tool_summary['tool_errors'].get(tool_name, 0)
                avg_duration = tool_summary['tool_avg_durations'].get(tool_name, 0)
                error_str = f" ({error_count} errors)" if error_count > 0 else ""
                duration_str = f" [avg: {avg_duration:.2f}s]" if avg_duration > 0 else ""
                print(f"      • {tool_name}: {count} calls{error_str}{duration_str}")
        print()
        
        # Agent Thoughts
        if session.thoughts:
            print("💭 AGENT THINKING:")
            for i, thought in enumerate(session.thoughts[:10], 1):  # Show first 10
                timestamp = datetime.fromtimestamp(thought.timestamp).strftime("%H:%M:%S")
                content = thought.content[:200] + "..." if len(thought.content) > 200 else thought.content
                print(f"   [{timestamp}] {content}")
            if len(session.thoughts) > 10:
                print(f"   ... and {len(session.thoughts) - 10} more thoughts")
            print()
        
        # Clarifications
        if session.clarification_requests:
            print("❓ CLARIFICATIONS:")
            for i, clar in enumerate(session.clarification_requests, 1):
                timestamp = datetime.fromtimestamp(clar['timestamp']).strftime("%H:%M:%S")
                print(f"   [{timestamp}] Q: {clar['question']}")
                if clar['response']:
                    print(f"      A: {clar['response']}")
            print()
        
        # Final Output Preview
        if session.final_output:
            print("📝 FINAL OUTPUT:")
            preview = session.final_output[:500] + "..." if len(session.final_output) > 500 else session.final_output
            print(f"   {preview}")
            print()
        
        print("=" * 80)
        print()


# Global tracker instance
_global_tracker = AgentTracker()


def get_tracker() -> AgentTracker:
    """Get the global tracker instance."""
    return _global_tracker
