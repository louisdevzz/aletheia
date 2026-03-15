"""
Main Agent Loop

Comprehensive tool-call loop with:
- Progress tracking and streaming
- Cancellation support
- Memory auto-save
- Tool approval workflows
- Continuation handling
- Deferred action detection
"""

from typing import Dict, Any, List, Optional, Callable, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import time
import re
import json
import asyncio

from aletheia.tools.base import Tool, ToolCall, ToolResult
from aletheia.tools.registry import ToolRegistry
from aletheia.providers.base import Provider, ChatMessage, ChatRequest, ChatResponse

from .loop.detection import LoopDetector, LoopDetectionConfig, LoopVerdict
from .loop.execution import ToolExecutor, ExecutionResult
from .loop.history import HistoryManager


# Constants for agent loop
DEFAULT_MAX_TOOL_ITERATIONS = 20
MAX_TOKENS_CONTINUATION_MAX_ATTEMPTS = 3
MAX_TOKENS_CONTINUATION_MAX_OUTPUT_CHARS = 120_000
AUTOSAVE_MIN_MESSAGE_CHARS = 20
PROGRESS_MIN_INTERVAL_MS = 500

# Deferred action detection patterns
DEFERRED_ACTION_PATTERN = re.compile(
    r"\b(I'll|I will|I am going to|Let me|Let's|We will)\b[^.!?\n]{0,160}\b(check|look|search|browse|open|read|write|run|execute|call|inspect|analyze|verify|list|fetch|try|see|continue)\b",
    re.IGNORECASE,
)


class ProgressType(Enum):
    """Types of progress updates."""

    THINKING = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    STREAMING = auto()
    COMPLETE = auto()
    ERROR = auto()


@dataclass
class ProgressUpdate:
    """A progress update during agent execution."""

    type: ProgressType
    message: str
    iteration: int
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentLoopConfig:
    """Configuration for the main agent loop."""

    max_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS
    enable_loop_detection: bool = True
    enable_progress_tracking: bool = True
    enable_auto_save: bool = True
    enable_continuation: bool = True
    tool_timeout_seconds: float = 30.0
    progress_interval_ms: int = PROGRESS_MIN_INTERVAL_MS


@dataclass
class LoopResult:
    """Result from running the agent loop."""

    text: str
    iterations: int
    tool_calls: int
    duration_ms: float
    completed: bool
    error: Optional[str] = None


class AgentLoop:
    """
    Main agentic tool-call loop.

    Orchestrates the entire conversation flow:
    1. Initialize with system prompt
    2. Run tool-call iterations
    3. Execute tools
    4. Handle loop detection
    5. Manage history compaction
    6. Stream progress
    """

    def __init__(
        self,
        provider: Provider,
        tool_registry: ToolRegistry,
        config: AgentLoopConfig,
        history_manager: Optional[HistoryManager] = None,
        loop_detector: Optional[LoopDetector] = None,
    ):
        self.provider = provider
        self.tool_registry = tool_registry
        self.config = config
        self.history_manager = history_manager or HistoryManager()
        self.loop_detector = loop_detector or LoopDetector(LoopDetectionConfig())
        self.tool_executor = ToolExecutor(tool_registry)

        # State
        self.messages: List[ChatMessage] = []
        self.iteration = 0
        self.start_time = 0.0
        self.cancelled = False

        # Progress tracking
        self.last_progress_time = 0.0
        self.progress_callbacks: List[Callable[[ProgressUpdate], None]] = []

    def on_progress(self, callback: Callable[[ProgressUpdate], None]):
        """Register a progress callback."""
        self.progress_callbacks.append(callback)

    def emit_progress(self, update: ProgressUpdate):
        """Emit a progress update."""
        now = time.time() * 1000
        if now - self.last_progress_time >= self.config.progress_interval_ms:
            for callback in self.progress_callbacks:
                callback(update)
            self.last_progress_time = now

    async def run(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> LoopResult:
        """
        Run the main agent loop.

        Args:
            user_message: User input
            system_prompt: Optional system prompt
            cancellation_token: Optional cancellation event

        Returns:
            LoopResult with final response
        """
        self.start_time = time.time()
        self.iteration = 0
        self.cancelled = False

        # Initialize messages
        self.messages = []
        if system_prompt:
            self.messages.append(ChatMessage(role="system", content=system_prompt))
        self.messages.append(ChatMessage(role="user", content=user_message))

        # Auto-save to memory if enabled
        if (
            self.config.enable_auto_save
            and len(user_message) >= AUTOSAVE_MIN_MESSAGE_CHARS
        ):
            await self._auto_save_to_memory(user_message)

        final_response = ""
        total_tool_calls = 0

        try:
            for self.iteration in range(self.config.max_iterations):
                # Check cancellation
                if cancellation_token and cancellation_token.is_set():
                    self.cancelled = True
                    return LoopResult(
                        text="Operation cancelled by user.",
                        iterations=self.iteration,
                        tool_calls=total_tool_calls,
                        duration_ms=(time.time() - self.start_time) * 1000,
                        completed=False,
                        error="Cancelled",
                    )

                # Loop detection
                if self.config.enable_loop_detection:
                    verdict, warning = self.loop_detector.check()
                    if verdict == LoopVerdict.HARD_STOP:
                        final_response = warning or "Loop detected. Stopping."
                        break
                    elif verdict == LoopVerdict.INJECT_WARNING:
                        self.messages.append(
                            ChatMessage(role="system", content=warning)
                        )
                        self.emit_progress(
                            ProgressUpdate(
                                type=ProgressType.THINKING,
                                message=warning,
                                iteration=self.iteration,
                            )
                        )

                # Maybe compact history
                compaction = self.history_manager.maybe_compact(self.messages)
                if compaction.success:
                    self.emit_progress(
                        ProgressUpdate(
                            type=ProgressType.THINKING,
                            message=f"Compacted {compaction.messages_removed} messages",
                            iteration=self.iteration,
                        )
                    )

                # Build request
                tools = self.tool_registry.get_all_specs()
                request = ChatRequest(
                    messages=self.messages,
                    tools=tools if tools else None,
                    temperature=0.7,
                )

                self.emit_progress(
                    ProgressUpdate(
                        type=ProgressType.THINKING,
                        message=f"Thinking... (iteration {self.iteration + 1})",
                        iteration=self.iteration,
                    )
                )

                # Call LLM
                response = await self.provider.chat(request)

                # Check for tool calls
                if not response.tool_calls:
                    # No tools needed - final answer
                    final_response = response.text or ""

                    # Check for deferred action without tool call
                    if self._detect_deferred_action(final_response):
                        self.emit_progress(
                            ProgressUpdate(
                                type=ProgressType.THINKING,
                                message="Detected deferred action, requesting tool call",
                                iteration=self.iteration,
                            )
                        )
                        self.messages.append(
                            ChatMessage(role="assistant", content=final_response)
                        )
                        self.messages.append(
                            ChatMessage(
                                role="system",
                                content="Internal correction: your last reply indicated you were about to take an action, but no valid tool call was emitted. If a tool is needed, emit it now. If no tool is needed, provide the complete final answer now and do not defer action.",
                            )
                        )
                        continue

                    self.messages.append(
                        ChatMessage(role="assistant", content=final_response)
                    )
                    break

                # Execute tools
                tool_calls = [
                    ToolCall(
                        name=tc["name"],
                        arguments=json.loads(tc["arguments"]),
                        call_id=tc["id"],
                    )
                    for tc in response.tool_calls
                ]

                total_tool_calls += len(tool_calls)

                # Add assistant message with tool calls
                self.messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.text or "",
                        tool_calls=response.tool_calls,
                    )
                )

                # Execute tools
                self.emit_progress(
                    ProgressUpdate(
                        type=ProgressType.TOOL_CALL,
                        message=f"Executing {len(tool_calls)} tool(s)...",
                        iteration=self.iteration,
                        metadata={"tools": [tc.name for tc in tool_calls]},
                    )
                )

                exec_results = await self.tool_executor.execute_many(tool_calls)

                # Record for loop detection
                for call, exec_result in zip(tool_calls, exec_results):
                    self.loop_detector.record_call(
                        call.name, call.arguments, exec_result.result, self.iteration
                    )

                # Add tool results
                for exec_result in exec_results:
                    result = exec_result.result
                    content = (
                        result.output if result.success else f"Error: {result.error}"
                    )

                    self.emit_progress(
                        ProgressUpdate(
                            type=ProgressType.TOOL_RESULT,
                            message=f"Tool '{exec_result.call.name}' completed",
                            iteration=self.iteration,
                            metadata={
                                "tool": exec_result.call.name,
                                "success": result.success,
                                "duration_ms": exec_result.duration_ms,
                            },
                        )
                    )

                    self.messages.append(
                        ChatMessage(
                            role="tool",
                            content=content,
                            tool_call_id=exec_result.call.call_id,
                        )
                    )

            else:
                # Max iterations reached
                final_response = "I wasn't able to complete the request within the iteration limit. Please try rephrasing or breaking it into smaller steps."

        except Exception as e:
            final_response = f"Error: {str(e)}"
            return LoopResult(
                text=final_response,
                iterations=self.iteration,
                tool_calls=total_tool_calls,
                duration_ms=(time.time() - self.start_time) * 1000,
                completed=False,
                error=str(e),
            )

        duration_ms = (time.time() - self.start_time) * 1000

        return LoopResult(
            text=final_response,
            iterations=self.iteration + 1,
            tool_calls=total_tool_calls,
            duration_ms=duration_ms,
            completed=True,
        )

    def _detect_deferred_action(self, text: str) -> bool:
        """Detect if response contains deferred action without tool call."""
        return bool(DEFERRED_ACTION_PATTERN.search(text))

    async def _auto_save_to_memory(self, message: str):
        """Auto-save user message to memory."""
        # In real implementation, would save to memory system
        pass


class StreamingAgentLoop(AgentLoop):
    """Agent loop with streaming support."""

    async def run_streaming(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> AsyncIterator[str]:
        """
        Run agent loop with streaming output.

        Yields:
            Text chunks as they become available
        """
        result = await self.run(user_message, system_prompt, cancellation_token)

        # Yield final response (in real impl, would stream tokens)
        yield result.text
