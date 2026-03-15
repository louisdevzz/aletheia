"""
Aletheia - Function Calling Agent

Full implementation with:
- Main agent loop
- Tool dispatchers
- Loop detection and history compaction
- Research phase
- Session management
- Advanced prompt building
- Quota and budget management
- Memory loading with decay and boosting
"""

# Main Agent
from .agent import Agent, AgentBuilder, AgentConfig

# Dispatchers
from .dispatcher import ToolDispatcher, NativeToolDispatcher, XmlToolDispatcher

# Main Loop
from .loop_ import AgentLoop, AgentLoopConfig, LoopResult, ProgressUpdate, ProgressType

# Loop Submodules
from .loop import LoopContext, LoopConfig as LoopContextConfig
from .loop.detection import LoopDetector, LoopDetectionConfig, LoopVerdict
from .loop.execution import ToolExecutor, ExecutionConfig
from .loop.history import HistoryManager

# Memory
from .memory_loader import (
    MemoryLoader,
    DefaultMemoryLoader,
    SimpleMemoryLoader,
    NoOpMemoryLoader,
    MemoryEntry,
    Memory,
    create_memory_loader,
)

# Research
from .research import ResearchPhase, ResearchResult

# Session
from .session import Session, SessionManager

# Prompt Building (Advanced)
from .prompt import (
    SystemPromptBuilder,
    PromptContext,
    PromptSection,
    IdentitySection,
    ToolsSection,
    SafetySection,
    WorkspaceSection,
    RuntimeSection,
    DateTimeSection,
    ChannelMediaSection,
    create_system_prompt,
)

# Quota and Budget
from .quota_aware import (
    QuotaManager,
    QuotaStatus,
    ProviderQuota,
    BudgetTracker,
    BudgetConfig,
    check_quota_before_operation,
)

__all__ = [
    # Main Agent
    "Agent",
    "AgentBuilder",
    "AgentConfig",
    # Main Loop
    "AgentLoop",
    "AgentLoopConfig",
    "LoopResult",
    "ProgressUpdate",
    "ProgressType",
    # Dispatchers
    "ToolDispatcher",
    "NativeToolDispatcher",
    "XmlToolDispatcher",
    # Loop Context
    "LoopContext",
    "LoopContextConfig",
    "LoopDetector",
    "LoopDetectionConfig",
    "LoopVerdict",
    "ToolExecutor",
    "ExecutionConfig",
    "HistoryManager",
    # Memory
    "MemoryLoader",
    "DefaultMemoryLoader",
    "SimpleMemoryLoader",
    "NoOpMemoryLoader",
    "MemoryEntry",
    "Memory",
    "create_memory_loader",
    # Research
    "ResearchPhase",
    "ResearchResult",
    # Session
    "Session",
    "SessionManager",
    # Prompt (Advanced)
    "SystemPromptBuilder",
    "PromptContext",
    "PromptSection",
    "IdentitySection",
    "ToolsSection",
    "SafetySection",
    "WorkspaceSection",
    "RuntimeSection",
    "DateTimeSection",
    "ChannelMediaSection",
    "create_system_prompt",
    # Quota and Budget
    "QuotaManager",
    "QuotaStatus",
    "ProviderQuota",
    "BudgetTracker",
    "BudgetConfig",
    "check_quota_before_operation",
]
