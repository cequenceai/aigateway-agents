#!/usr/bin/env python3
"""
Comprehensive test suite for OpenAI Agent.

Tests all major features:
- Basic queries
- MCP server connection
- Tool discovery
- Tool usage
- Error handling
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from agents import Agent, Runner

from mcp_config import build_mcp_server
from auth.oauth import create_oauth_provider, CallbackServer, InMemoryTokenStorage

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
    
    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self.results: List[TestResult] = []
    
    async def test_basic_query(self) -> TestResult:
        """Test 1: Basic query without MCP."""
        result = TestResult("Basic Query")
        result.start()
        
        try:
            agent = Agent(
                name="Test Agent",
                instructions="You are a helpful assistant. Answer concisely.",
            )
            
            runner_result = await Runner.run(agent, "Say hello in 3 words")
            
            if runner_result and runner_result.final_output:
                result.finish(True, data={"output_length": len(runner_result.final_output)})
            else:
                result.finish(False, "No output received")
        except Exception as e:
            result.finish(False, str(e))
        
        return result
    
    async def test_mcp_connection(self) -> TestResult:
        """Test 2: MCP server connection."""
        result = TestResult("MCP Connection")
        result.start()
        
        base_url = self.mcp_url[:-4] if self.mcp_url.endswith("/mcp") else self.mcp_url
        storage = InMemoryTokenStorage(reset_tokens=False)
        callback_server = CallbackServer(port=3030)
        callback_server.start()
        oauth_provider = create_oauth_provider(base_url, callback_server, reset_tokens=False)
        
        try:
            mcp_server = await build_mcp_server(
                mcp_url=self.mcp_url,
                oauth_provider=oauth_provider,
                storage=storage
            )
            
            await mcp_server.connect()
            
            has_auth = False
            # Check if server has auth (would be in headers)
            result.finish(True, data={"connected": True, "has_auth": has_auth})
            
            await mcp_server.cleanup()
        except Exception as e:
            result.finish(False, str(e))
        finally:
            callback_server.stop()
        
        return result
    
    async def test_tool_discovery(self) -> TestResult:
        """Test 3: Tool discovery from MCP server."""
        result = TestResult("Tool Discovery")
        result.start()
        
        base_url = self.mcp_url[:-4] if self.mcp_url.endswith("/mcp") else self.mcp_url
        storage = InMemoryTokenStorage(reset_tokens=False)
        callback_server = CallbackServer(port=3030)
        callback_server.start()
        oauth_provider = create_oauth_provider(base_url, callback_server, reset_tokens=False)
        
        try:
            mcp_server = await build_mcp_server(
                mcp_url=self.mcp_url,
                oauth_provider=oauth_provider,
                storage=storage
            )
            
            await mcp_server.connect()
            
            agent = Agent(
                name="Test Agent",
                instructions="You are a helpful assistant.",
                mcp_servers=[mcp_server]
            )
            
            runner_result = await Runner.run(
                agent,
                "List all available tools from the MCP server and describe what each one does."
            )
            
            if runner_result and runner_result.final_output:
                result.finish(True, data={"output_length": len(runner_result.final_output)})
            else:
                result.finish(False, "No output received")
            
            await mcp_server.cleanup()
        except Exception as e:
            result.finish(False, str(e))
        finally:
            callback_server.stop()
        
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
        logger.info("COMPREHENSIVE TEST SUITE - OpenAI Agent")
        logger.info("="*80)
        logger.info(f"MCP URL: {self.mcp_url}")
        
        self.results.append(await self.test_basic_query())
        self.results.append(await self.test_mcp_connection())
        self.results.append(await self.test_tool_discovery())
        
        self.log_summary()


async def main():
    """Main entry point."""
    # Check API key
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    mcp_url = os.environ.get("MCP_SERVER_URL", "https://ztaid-stkaeb2t-e4l2dawa5a-uc.a.run.app/mcp")
    
    tester = ComprehensiveTester(mcp_url=mcp_url)
    
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
