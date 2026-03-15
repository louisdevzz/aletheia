"""
Aletheia

Complete agent with:
- Tool-call loop with detection
- History compaction
- Research phase
- Session management
- Dynamic prompt building
- Timeout and approval
"""

from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass, field
import time
import json
import logging
from datetime import datetime

from aletheia.tools.base import Tool, ToolCall, ToolResult

logger = logging.getLogger(__name__)
from aletheia.tools.registry import ToolRegistry
from aletheia.providers.base import Provider, ChatMessage, ChatRequest, ChatResponse

from .dispatcher import ToolDispatcher, NativeToolDispatcher
from .loop import LoopContext, LoopConfig
from .loop.detection import LoopDetector, LoopDetectionConfig, LoopVerdict
from .loop.execution import ToolExecutor, ExecutionConfig
from .loop.history import HistoryManager
from .research import ResearchPhase, ResearchResult
from .session import Session, SessionManager
from .prompt import create_system_prompt
from aletheia.config.settings import get_workspace_dir
from .memory_store import get_memory_store, SQLiteMemoryStore


@dataclass
class AgentConfig:
    """Configuration for Aletheia."""

    max_iterations: int = 5
    temperature: float = 0.7
    enable_research: bool = True
    enable_loop_detection: bool = True
    enable_history_compaction: bool = True
    max_history_messages: int = 20
    tool_timeout_seconds: float = 30.0


class Agent:
    """
    Full-featured agent with tool calling.
    """

    def __init__(
        self,
        provider: Provider,
        tools: List[Tool],
        dispatcher: ToolDispatcher,
        config: AgentConfig,
        session_manager: Optional[SessionManager] = None,
    ):
        self.provider = provider
        self.tool_registry = ToolRegistry()
        self.dispatcher = dispatcher
        self.config = config
        self.session_manager = session_manager or SessionManager()

        # Register tools
        for tool in tools:
            self.tool_registry.register(tool)

        # Initialize components
        self.loop_detector = LoopDetector(LoopDetectionConfig())
        self.tool_executor = ToolExecutor(self.tool_registry, ExecutionConfig())
        self.history_manager = HistoryManager(
            max_messages=config.max_history_messages,
            compaction_threshold=config.max_history_messages // 2,
        )
        self.research_phase = ResearchPhase()

        # Initialize memory store
        self.memory_store = get_memory_store()

        # State
        self.messages: List[ChatMessage] = []
        self.current_session: Optional[Session] = None
        self.stats = {
            "total_requests": 0,
            "tool_calls": 0,
            "compactions": 0,
            "loops_detected": 0,
        }

    async def chat(self, user_message: str, session_id: Optional[str] = None) -> str:
        """
        Process a user message through the full agent loop.

        Args:
            user_message: User input
            session_id: Optional session ID for persistence

        Returns:
            Final response text
        """
        self.stats["total_requests"] += 1
        start_time = time.time()
        logger.info(f"📝 Agent received message: {user_message[:100]}...")

        # Get or create session
        if session_id:
            self.current_session = self.session_manager.get_session(session_id)
        if not self.current_session:
            self.current_session = self.session_manager.create_session()

        # Initialize messages if empty
        if not self.messages:
            await self._initialize_conversation(user_message)
        else:
            self.messages.append(ChatMessage(role="user", content=user_message))
            self.current_session.add_message("user", user_message)

        # Main tool-call loop
        final_response = ""
        iteration = 0

        try:
            for iteration in range(self.config.max_iterations):
                # Check loop detection
                if self.config.enable_loop_detection:
                    verdict, warning = self.loop_detector.check()
                    if verdict == LoopVerdict.HARD_STOP:
                        final_response = warning or "Loop detected. Stopping."
                        break
                    elif verdict == LoopVerdict.INJECT_WARNING:
                        # Add warning to context
                        self.messages.append(
                            ChatMessage(role="system", content=warning)
                        )

                # Maybe compact history
                if self.config.enable_history_compaction:
                    compaction = self.history_manager.maybe_compact(self.messages)
                    if compaction.success:
                        self.stats["compactions"] += 1

                # Build request
                tools = self.tool_registry.get_all_specs()
                logger.info(
                    f"🔧 Tools available ({len(tools)}): {[t['function']['name'] for t in tools]}"
                )
                request = ChatRequest(
                    messages=self.messages,
                    tools=tools if tools else None,
                    temperature=self.config.temperature,
                )

                # Call LLM
                logger.info(f"🤖 Calling provider with {len(self.messages)} messages")
                response = await self.provider.chat(request)
                logger.info(
                    f"📥 Provider response: has_tools={bool(response.tool_calls)}, text_len={len(response.text or '')}"
                )

                # Handle response
                if not response.tool_calls:
                    # No tools needed - we have final answer
                    final_response = response.text or ""
                    logger.info(
                        f"✅ No tools needed. Final response: {final_response[:150]}..."
                    )
                    self.messages.append(
                        ChatMessage(role="assistant", content=final_response)
                    )
                    self.current_session.add_message("assistant", final_response)
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

                # Add assistant message with tool calls
                self.messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.text or "",
                        tool_calls=response.tool_calls,
                    )
                )

                # Execute tools
                self.stats["tool_calls"] += len(tool_calls)
                logger.info(
                    f"🔨 Executing {len(tool_calls)} tool(s): {[tc.name for tc in tool_calls]}"
                )
                exec_results = await self.tool_executor.execute_many(tool_calls)
                for i, result in enumerate(exec_results):
                    status = "✓" if result.result.success else "✗"
                    if result.result.success:
                        # Split multi-line results and show first few lines with truncation
                        output_lines = result.result.output.split("\n")
                        preview_lines = []
                        total_chars = 0
                        for line in output_lines[:10]:  # Show max 10 lines
                            if total_chars + len(line) > 300:
                                preview_lines.append(
                                    line[: (300 - total_chars)] + "..."
                                )
                                break
                            preview_lines.append(line)
                            total_chars += len(line) + 1
                        output = "\n    ".join(preview_lines)
                        if len(output_lines) > 10:
                            output += f"\n    ... ({len(output_lines) - 10} more lines)"
                    else:
                        output = result.result.error[:200]
                    logger.info(
                        f"  {status} Tool {result.call.name} output:\n    {output}"
                    )

                # Record for loop detection
                for call, exec_result in zip(tool_calls, exec_results):
                    self.loop_detector.record_call(
                        call.name, call.arguments, exec_result.result, iteration
                    )

                # Add tool results
                for exec_result in exec_results:
                    result = exec_result.result
                    content = (
                        result.output if result.success else f"Error: {result.error}"
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
                final_response = "I wasn't able to complete the request in time. Please try rephrasing."

        except Exception as e:
            final_response = f"Error: {str(e)}"

        # Update session
        duration_ms = (time.time() - start_time) * 1000
        self.current_session.metadata["last_duration_ms"] = duration_ms

        logger.info(
            f"✅ Agent completed in {duration_ms:.0f}ms. Final response: {final_response[:150]}..."
        )

        # Save important interaction to memory
        await self._save_interaction_memory(user_message, final_response)

        return final_response

    async def _save_interaction_memory(self, user_message: str, response: str):
        """Save important interaction details to memory store."""
        try:
            # Save user query as conversation memory
            await self.memory_store.store(
                key=f"user_query_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                content=user_message,
                category="conversation",
                session_id=self.current_session.id if self.current_session else None,
                metadata={"type": "user_query", "response_preview": response[:100]},
            )

            # If this contains important facts, also save as core memory
            if any(
                keyword in user_message.lower()
                for keyword in [
                    "name is",
                    "i am",
                    "my name",
                    "remember that",
                    "don't forget",
                ]
            ):
                await self.memory_store.store(
                    key="user_identity_fact",
                    content=f"User mentioned: {user_message}",
                    category="core",
                    session_id=self.current_session.id
                    if self.current_session
                    else None,
                    metadata={"type": "identity_fact", "extracted_from": user_message},
                )
                logger.info("💾 Saved identity fact to core memory")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save memory: {e}")

    async def _initialize_conversation(self, user_message: str):
        """Initialize conversation with system prompt and research."""
        # Research phase
        research_context = ""
        if self.config.enable_research:
            research_result = await self.research_phase.conduct_research(
                query=user_message,
                tools=list(self.tool_registry._tools.values()),
                provider=self.provider,
            )
            if research_result.success:
                research_context = self.research_phase.format_findings(
                    research_result.findings
                )

        # Build system prompt with identity files
        workspace_dir = get_workspace_dir() / "workspace"
        system_prompt = create_system_prompt(
            tools=list(self.tool_registry._tools.values()),
            workspace_dir=workspace_dir,
            research_context=research_context,
        )

        # Initialize messages
        self.messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        # Record in session
        self.current_session.add_message("user", user_message)

    def get_session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self.current_session.id if self.current_session else None

    def clear(self):
        """Clear conversation state."""
        self.messages.clear()
        self.current_session = None
        self.loop_detector = LoopDetector(LoopDetectionConfig())

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            **self.stats,
            "history_length": len(self.messages),
            "session_id": self.get_session_id(),
        }


class AgentBuilder:
    """Builder for Agent."""

    def __init__(self):
        self._provider: Optional[Provider] = None
        self._tools: List[Tool] = []
        self._dispatcher: Optional[ToolDispatcher] = None
        self._config: AgentConfig = AgentConfig()
        self._session_manager: Optional[SessionManager] = None

    def provider(self, provider: Provider) -> "AgentBuilder":
        """Set LLM provider."""
        self._provider = provider
        return self

    def add_tool(self, tool: Tool) -> "AgentBuilder":
        """Add a tool."""
        self._tools.append(tool)
        return self

    def tools(self, tools: List[Tool]) -> "AgentBuilder":
        """Set all tools."""
        self._tools = tools
        return self

    def dispatcher(self, dispatcher: ToolDispatcher) -> "AgentBuilder":
        """Set tool dispatcher."""
        self._dispatcher = dispatcher
        return self

    def config(self, config: AgentConfig) -> "AgentBuilder":
        """Set configuration."""
        self._config = config
        return self

    def session_manager(self, manager: SessionManager) -> "AgentBuilder":
        """Set session manager."""
        self._session_manager = manager
        return self

    def max_iterations(self, n: int) -> "AgentBuilder":
        """Set max tool iterations."""
        self._config.max_iterations = n
        return self

    def temperature(self, temp: float) -> "AgentBuilder":
        """Set temperature."""
        self._config.temperature = temp
        return self

    def enable_research(self, enabled: bool = True) -> "AgentBuilder":
        """Enable/disable research phase."""
        self._config.enable_research = enabled
        return self

    def build(self) -> Agent:
        """Build the agent."""
        if not self._provider:
            raise ValueError("Provider is required")

        if not self._dispatcher:
            self._dispatcher = NativeToolDispatcher()

        return Agent(
            provider=self._provider,
            tools=self._tools,
            dispatcher=self._dispatcher,
            config=self._config,
            session_manager=self._session_manager,
        )
