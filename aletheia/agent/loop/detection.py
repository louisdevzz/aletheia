"""
Loop Detection - Detect and prevent unproductive looping

Detects three patterns:
1. No-progress repeat - same tool + args + output
2. Ping-pong - two calls alternating (A→B→A→B)
3. Consecutive failure streak - same tool failing repeatedly
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import hashlib
import json

from aletheia.tools.base import ToolResult


class LoopVerdict(Enum):
    """Action to take after loop detection check."""

    CONTINUE = auto()  # No loop detected - proceed normally
    INJECT_WARNING = auto()  # First detection - inject warning
    HARD_STOP = auto()  # Pattern persisted - terminate loop


@dataclass
class ToolCallRecord:
    """Record of a tool invocation."""

    tool_name: str
    args_hash: str
    result_hash: str
    success: bool
    iteration: int


@dataclass
class LoopDetectionConfig:
    """Configuration for loop detection."""

    # Identical repetitions before triggering
    no_progress_threshold: int = 3
    # Full A-B cycles before triggering ping-pong
    ping_pong_cycles: int = 2
    # Consecutive failures of same tool
    failure_streak_threshold: int = 3


class LoopDetector:
    """Detects unproductive looping patterns in tool calls."""

    def __init__(self, config: Optional[LoopDetectionConfig] = None):
        self.config = config or LoopDetectionConfig()
        self.history: List[ToolCallRecord] = []
        self.warning_injected: bool = False

    def record_call(
        self, tool_name: str, arguments: Dict, result: ToolResult, iteration: int
    ):
        """Record a completed tool invocation."""
        args_hash = self._hash_dict(arguments)
        result_hash = self._hash_result(result)

        record = ToolCallRecord(
            tool_name=tool_name.lower(),
            args_hash=args_hash,
            result_hash=result_hash,
            success=result.success,
            iteration=iteration,
        )
        self.history.append(record)

    def check(self) -> Tuple[LoopVerdict, Optional[str]]:
        """
        Check for loop patterns.

        Returns:
            (verdict, warning_message or None)
        """
        if len(self.history) < 2:
            return LoopVerdict.CONTINUE, None

        # Check for no-progress repeats
        verdict, message = self._check_no_progress()
        if verdict != LoopVerdict.CONTINUE:
            return verdict, message

        # Check for ping-pong
        verdict, message = self._check_ping_pong()
        if verdict != LoopVerdict.CONTINUE:
            return verdict, message

        # Check for failure streak
        verdict, message = self._check_failure_streak()
        if verdict != LoopVerdict.CONTINUE:
            return verdict, message

        return LoopVerdict.CONTINUE, None

    def _check_no_progress(self) -> Tuple[LoopVerdict, Optional[str]]:
        """Check for identical tool calls with same output."""
        if (
            self.config.no_progress_threshold == 0
            or len(self.history) < self.config.no_progress_threshold
        ):
            return LoopVerdict.CONTINUE, None

        # Look at last N calls
        recent = self.history[-self.config.no_progress_threshold :]

        # Check if all are the same
        first = recent[0]
        if all(
            r.tool_name == first.tool_name
            and r.args_hash == first.args_hash
            and r.result_hash == first.result_hash
            for r in recent
        ):
            if not self.warning_injected:
                self.warning_injected = True
                return LoopVerdict.INJECT_WARNING, self._warning_no_progress(
                    first.tool_name
                )
            else:
                return LoopVerdict.HARD_STOP, self._hard_stop_no_progress(
                    first.tool_name
                )

        return LoopVerdict.CONTINUE, None

    def _check_ping_pong(self) -> Tuple[LoopVerdict, Optional[str]]:
        """Check for A-B-A-B pattern."""
        if (
            self.config.ping_pong_cycles == 0
            or len(self.history) < self.config.ping_pong_cycles * 2
        ):
            return LoopVerdict.CONTINUE, None

        # Look for alternating pattern
        recent = self.history[-self.config.ping_pong_cycles * 2 :]

        if len(recent) >= 4:
            tools = [r.tool_name for r in recent]
            # Check if alternating between 2 tools
            if len(set(tools)) == 2 and tools[0] != tools[1]:
                # Check pattern: A,B,A,B
                pattern = tools[:2]
                is_ping_pong = all(
                    tools[i] == pattern[i % 2] for i in range(len(tools))
                )
                if is_ping_pong:
                    if not self.warning_injected:
                        self.warning_injected = True
                        return LoopVerdict.INJECT_WARNING, self._warning_ping_pong(
                            pattern[0], pattern[1]
                        )
                    else:
                        return LoopVerdict.HARD_STOP, self._hard_stop_ping_pong()

        return LoopVerdict.CONTINUE, None

    def _check_failure_streak(self) -> Tuple[LoopVerdict, Optional[str]]:
        """Check for same tool failing repeatedly."""
        if self.config.failure_streak_threshold == 0:
            return LoopVerdict.CONTINUE, None

        # Check last N failures of same tool
        failures_by_tool: Dict[str, int] = {}

        for record in reversed(self.history):
            if not record.success:
                failures_by_tool[record.tool_name] = (
                    failures_by_tool.get(record.tool_name, 0) + 1
                )
            else:
                # Reset on success
                break

        for tool, count in failures_by_tool.items():
            if count >= self.config.failure_streak_threshold:
                if not self.warning_injected:
                    self.warning_injected = True
                    return LoopVerdict.INJECT_WARNING, self._warning_failure_streak(
                        tool, count
                    )
                else:
                    return LoopVerdict.HARD_STOP, self._hard_stop_failure_streak(tool)

        return LoopVerdict.CONTINUE, None

    def _hash_dict(self, d: Dict) -> str:
        """Create hash of dictionary."""
        return hashlib.md5(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]

    def _hash_result(self, result: ToolResult) -> str:
        """Create hash of tool result."""
        content = result.output if result.success else (result.error or "")
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _warning_no_progress(self, tool: str) -> str:
        return (
            f"⚠️ Warning: Tool '{tool}' was called {self.config.no_progress_threshold} times "
            f"with the same arguments and produced identical results. "
            f"This suggests a loop. Please reconsider your approach or provide different parameters."
        )

    def _hard_stop_no_progress(self, tool: str) -> str:
        return (
            f"❌ Loop detected: Tool '{tool}' continues to be called with the same arguments "
            f"without making progress. Stopping to prevent infinite loop."
        )

    def _warning_ping_pong(self, tool_a: str, tool_b: str) -> str:
        return (
            f"⚠️ Warning: Detected ping-pong pattern between '{tool_a}' and '{tool_b}'. "
            f"The tools appear to be calling each other without converging. "
            f"Please break this cycle with a direct answer."
        )

    def _hard_stop_ping_pong(self) -> str:
        return (
            f"❌ Ping-pong loop detected. The conversation is cycling between tools "
            f"without resolution. Terminating to prevent infinite loop."
        )

    def _warning_failure_streak(self, tool: str, count: int) -> str:
        return (
            f"⚠️ Warning: Tool '{tool}' has failed {count} consecutive times. "
            f"Consider alternative approaches or ask for clarification."
        )

    def _hard_stop_failure_streak(self, tool: str) -> str:
        return (
            f"❌ Tool '{tool}' continues to fail. Stopping to prevent further errors."
        )


import json
