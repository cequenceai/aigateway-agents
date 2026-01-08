#!/usr/bin/env python3
"""
Comprehensive test suite for Claude Agent SDK.

Tests all major features:
- Basic queries
- Tool usage
- File operations
- Error handling
- MCP integration (if available)
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class TestResult:
    """Test result container."""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error: str | None = None
        self.duration: float = 0.0
        self.data: Dict[str, Any] = {}
        self.start_time: float | None = None
    
    def start(self):
        """Start timing the test."""
        import time
        self.start_time = time.time()
        logger.info(f"▶ Starting test: {self.name}")
    
    def finish(self, passed: bool, error: str | None = None, data: Dict[str, Any] | None = None):
        """Finish the test and record results."""
        import time
        if self.start_time:
            self.duration = time.time() - self.start_time
        self.passed = passed
        self.error = error
        if data:
            self.data.update(data)
        
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{status} test: {self.name} (duration: {self.duration:.2f}s)")
        if error:
            logger.error(f"  Error: {error}")


class ComprehensiveTester:
    """Comprehensive test suite."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.test_dir = Path("test_output")
        self.test_dir.mkdir(exist_ok=True)
    
    async def test_simple_query(self) -> TestResult:
        """Test 1: Simple query without tools."""
        result = TestResult("Simple Query")
        result.start()
        
        try:
            messages = []
            async for message in query(prompt="What is 2 + 2? Answer with just the number."):
                messages.append(message)
            
            if len(messages) == 0:
                result.finish(False, "No messages received")
            else:
                result.finish(True, data={"message_count": len(messages)})
        except Exception as e:
            result.finish(False, str(e))
        
        return result
    
    async def test_read_tool(self) -> TestResult:
        """Test 2: Read tool."""
        result = TestResult("Read Tool")
        result.start()
        
        try:
            test_file = self.test_dir / "read_test.txt"
            test_file.write_text("Hello, World!")
            
            options = ClaudeAgentOptions(
                allowed_tools=["Read"],
                permission_mode="acceptEdits",
                max_turns=3
            )
            
            messages = []
            async for message in query(
                prompt=f"Read {test_file} and tell me what it contains.",
                options=options
            ):
                messages.append(message)
            
            result.finish(True, data={"message_count": len(messages)})
        except Exception as e:
            result.finish(False, str(e))
        
        return result
    
    async def test_edit_tool(self) -> TestResult:
        """Test 3: Edit tool."""
        result = TestResult("Edit Tool")
        result.start()
        
        try:
            test_file = self.test_dir / "edit_test.py"
            test_file.write_text("print('Hello')\n")
            
            options = ClaudeAgentOptions(
                allowed_tools=["Read", "Edit"],
                permission_mode="acceptEdits",
                max_turns=5
            )
            
            messages = []
            async for message in query(
                prompt=f"Edit {test_file} to print 'Hello, World!' instead.",
                options=options
            ):
                messages.append(message)
            
            # Check if file was modified
            content = test_file.read_text()
            modified = "World" in content
            
            result.finish(True, data={
                "message_count": len(messages),
                "file_modified": modified
            })
        except Exception as e:
            result.finish(False, str(e))
        
        return result
    
    async def test_bash_tool(self) -> TestResult:
        """Test 4: Bash tool."""
        result = TestResult("Bash Tool")
        result.start()
        
        try:
            options = ClaudeAgentOptions(
                allowed_tools=["Bash"],
                permission_mode="acceptEdits",
                max_turns=3
            )
            
            messages = []
            async for message in query(
                prompt="Use Bash to run 'echo Hello, World!' and tell me the output.",
                options=options
            ):
                messages.append(message)
            
            result.finish(True, data={"message_count": len(messages)})
        except Exception as e:
            result.finish(False, str(e))
        
        return result
    
    async def test_system_prompt(self) -> TestResult:
        """Test 5: System prompt."""
        result = TestResult("System Prompt")
        result.start()
        
        try:
            options = ClaudeAgentOptions(
                system_prompt="You are a helpful assistant. Always respond in uppercase.",
                max_turns=1
            )
            
            messages = []
            async for message in query(
                prompt="Say hello",
                options=options
            ):
                messages.append(message)
            
            result.finish(True, data={"message_count": len(messages)})
        except Exception as e:
            result.finish(False, str(e))
        
        return result
    
    async def test_max_turns(self) -> TestResult:
        """Test 6: Max turns limit."""
        result = TestResult("Max Turns")
        result.start()
        
        try:
            options = ClaudeAgentOptions(max_turns=1)
            
            messages = []
            async for message in query(
                prompt="Count from 1 to 10, one number per turn.",
                options=options
            ):
                messages.append(message)
            
            result.finish(True, data={"message_count": len(messages)})
        except Exception as e:
            result.finish(False, str(e))
        
        return result
    
    async def test_mcp_integration(self) -> TestResult:
        """Test 7: MCP integration (if configured)."""
        result = TestResult("MCP Integration")
        result.start()
        
        try:
            mcp_url = os.environ.get("MCP_SERVER_URL")
            if not mcp_url:
                result.finish(False, "MCP_SERVER_URL not set (skipping)")
                return result
            
            mcp_servers = {
                "mcp_server": {
                    "transport": "http",
                    "url": mcp_url,
                }
            }
            
            auth_header = os.environ.get("MCP_AUTH_HEADER")
            if auth_header:
                mcp_servers["mcp_server"]["headers"] = {
                    "Authorization": auth_header
                }
            
            options = ClaudeAgentOptions(
                mcp_servers=mcp_servers,
                permission_mode="acceptEdits",
                max_turns=5
            )
            
            messages = []
            async for message in query(
                prompt="List available tools from the MCP server.",
                options=options
            ):
                messages.append(message)
            
            result.finish(True, data={"message_count": len(messages)})
        except Exception as e:
            result.finish(False, str(e))
        
        return result
    
    def log_summary(self):
        """Log test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        total_duration = sum(r.duration for r in self.results)
        
        logger.info("="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Total tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total duration: {total_duration:.2f}s")
        logger.info("="*80)
        
        for result in self.results:
            status = "✓" if result.passed else "✗"
            logger.info(f"{status} {result.name} ({result.duration:.2f}s)")
            if result.error:
                logger.error(f"    Error: {result.error}")
    
    async def run_all_tests(self):
        """Run all tests."""
        logger.info("="*80)
        logger.info("COMPREHENSIVE TEST SUITE")
        logger.info("="*80)
        
        self.results.append(await self.test_simple_query())
        self.results.append(await self.test_read_tool())
        self.results.append(await self.test_edit_tool())
        self.results.append(await self.test_bash_tool())
        self.results.append(await self.test_system_prompt())
        self.results.append(await self.test_max_turns())
        self.results.append(await self.test_mcp_integration())
        
        self.log_summary()


async def main():
    """Main entry point."""
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    tester = ComprehensiveTester()
    
    try:
        await tester.run_all_tests()
    except KeyboardInterrupt:
        logger.info("\n\nTest suite interrupted by user")
    except Exception as e:
        logger.error(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
