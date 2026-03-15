"""
Tool Execution - Execute tools with timeout and approval

Handles tool execution with:
- Timeout management
- Approval workflows
- Parallel execution
- Error handling
"""

import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import time

from aletheia.tools.base import Tool, ToolCall, ToolResult
from aletheia.tools.registry import ToolRegistry


@dataclass
class ExecutionResult:
    """Result of tool execution."""

    call: ToolCall
    result: ToolResult
    duration_ms: float
    approved: bool = True


@dataclass
class ExecutionConfig:
    """Configuration for tool execution."""

    timeout_seconds: float = 30.0
    enable_approval: bool = False
    parallel_execution: bool = True


class ToolExecutor:
    """Executes tools with timeout and approval support."""

    def __init__(
        self, registry: ToolRegistry, config: Optional[ExecutionConfig] = None
    ):
        self.registry = registry
        self.config = config or ExecutionConfig()

    async def execute_single(
        self, call: ToolCall, timeout: Optional[float] = None
    ) -> ExecutionResult:
        """
        Execute a single tool call with timeout.

        Args:
            call: ToolCall to execute
            timeout: Override timeout (seconds)

        Returns:
            ExecutionResult
        """
        timeout = timeout or self.config.timeout_seconds
        start_time = time.time()

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self.registry.execute(call), timeout=timeout
            )

            duration_ms = (time.time() - start_time) * 1000

            return ExecutionResult(
                call=call, result=result, duration_ms=duration_ms, approved=True
            )

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return ExecutionResult(
                call=call,
                result=ToolResult(
                    success=False,
                    output="",
                    error=f"Tool execution timed out after {timeout}s",
                ),
                duration_ms=duration_ms,
                approved=True,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ExecutionResult(
                call=call,
                result=ToolResult(
                    success=False, output="", error=f"Execution error: {str(e)}"
                ),
                duration_ms=duration_ms,
                approved=True,
            )

    async def execute_many(
        self, calls: List[ToolCall], timeout: Optional[float] = None
    ) -> List[ExecutionResult]:
        """
        Execute multiple tool calls.

        Args:
            calls: List of ToolCalls
            timeout: Override timeout per tool

        Returns:
            List of ExecutionResults
        """
        if self.config.parallel_execution and len(calls) > 1:
            # Execute in parallel
            tasks = [self.execute_single(call, timeout) for call in calls]
            return await asyncio.gather(*tasks)
        else:
            # Execute sequentially
            results = []
            for call in calls:
                result = await self.execute_single(call, timeout)
                results.append(result)
            return results

    def format_results_for_llm(
        self, results: List[ExecutionResult]
    ) -> List[Dict[str, Any]]:
        """
        Format execution results for LLM context.

        Returns:
            List of tool result messages
        """
        messages = []
        for exec_result in results:
            call = exec_result.call
            result = exec_result.result

            content = result.output if result.success else f"Error: {result.error}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id
                    or f"call_{results.index(exec_result)}",
                    "name": call.name,
                    "content": content,
                }
            )

        return messages


class ApprovalManager:
    """Manages tool approval workflows."""

    def __init__(self):
        self.approved_tools: set = set()
        self.denied_tools: set = set()

    def is_approved(self, tool_name: str, arguments: Dict) -> bool:
        """Check if tool is pre-approved."""
        # For now, simple implementation
        # In real app, would check user preferences
        return tool_name not in self.denied_tools

    def approve_tool(self, tool_name: str):
        """Mark tool as approved."""
        self.approved_tools.add(tool_name)
        self.denied_tools.discard(tool_name)

    def deny_tool(self, tool_name: str):
        """Mark tool as denied."""
        self.denied_tools.add(tool_name)
        self.approved_tools.discard(tool_name)
