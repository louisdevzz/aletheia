"""
Advanced System Prompt Builder

Builds comprehensive system prompts with multiple sections.
"""

from typing import Dict, Any, List, Optional, Protocol
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class PromptSection(Protocol):
    """A section of the system prompt."""

    def name(self) -> str: ...

    def build(self, ctx: "PromptContext") -> str: ...


@dataclass
class PromptContext:
    """Context for building prompts."""

    workspace_dir: Optional[Path] = None
    model_name: str = "unknown"
    tools: Optional[List] = None
    identity_config: Optional[Dict] = None
    dispatcher_instructions: str = ""
    extra_files: Optional[List[str]] = None


class SystemPromptBuilder:
    """
    Comprehensive system prompt builder.

    Builds prompts with multiple sections:
    - Identity (AGENTS.md, SOUL.md, etc.)
    - Tools
    - Safety
    - Workspace
    - Runtime
    - DateTime
    """

    BOOTSTRAP_MAX_CHARS = 20000

    def __init__(self):
        self.sections: List[PromptSection] = []

    @classmethod
    def with_defaults(cls) -> "SystemPromptBuilder":
        """Create builder with default sections."""
        builder = cls()
        builder.sections = [
            IdentitySection(),
            ToolsSection(),
            SafetySection(),
            WorkspaceSection(),
            DateTimeSection(),
            RuntimeSection(),
        ]
        return builder

    def add_section(self, section: PromptSection) -> "SystemPromptBuilder":
        """Add a custom section."""
        self.sections.append(section)
        return self

    def build(self, ctx: PromptContext) -> str:
        """Build the complete system prompt."""
        parts = []

        for section in self.sections:
            try:
                content = section.build(ctx)
                if content and content.strip():
                    parts.append(content.strip())
            except Exception:
                # Skip sections that fail to build
                continue

        return "\n\n".join(parts)


class IdentitySection:
    """Identity section with workspace files."""

    def name(self) -> str:
        return "identity"

    def build(self, ctx: PromptContext) -> str:
        prompt = "## Project Context\n\n"

        # List of identity files to inject
        identity_files = [
            "AGENTS.md",
            "SOUL.md",
            "TOOLS.md",
            "IDENTITY.md",
            "USER.md",
            "HEARTBEAT.md",
            "BOOTSTRAP.md",
            "MEMORY.md",
        ]

        if ctx.workspace_dir:
            for filename in identity_files:
                content = self._read_workspace_file(ctx.workspace_dir, filename)
                if content:
                    prompt += f"### {filename}\n\n"
                    prompt += self._truncate(
                        content, SystemPromptBuilder.BOOTSTRAP_MAX_CHARS
                    )
                    prompt += "\n\n"

        # Extra identity files
        if ctx.extra_files and ctx.workspace_dir:
            for filename in ctx.extra_files:
                if self._is_safe_filename(filename):
                    content = self._read_workspace_file(ctx.workspace_dir, filename)
                    if content:
                        prompt += f"### {filename}\n\n"
                        prompt += self._truncate(
                            content, SystemPromptBuilder.BOOTSTRAP_MAX_CHARS
                        )
                        prompt += "\n\n"

        return prompt

    def _read_workspace_file(self, workspace_dir: Path, filename: str) -> Optional[str]:
        """Read a file from workspace."""
        try:
            path = workspace_dir / filename
            if path.exists():
                return path.read_text()
        except Exception:
            pass
        return None

    def _truncate(self, content: str, max_chars: int) -> str:
        """Truncate content to max chars."""
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + f"\n\n[... truncated at {max_chars} chars]"

    def _is_safe_filename(self, filename: str) -> bool:
        """Check if filename is safe (no path traversal)."""
        return (
            ".." not in filename
            and not filename.startswith("/")
            and not filename.startswith("\\")
        )


class ToolsSection:
    """Tools section listing available tools."""

    def name(self) -> str:
        return "tools"

    def build(self, ctx: PromptContext) -> str:
        out = "## Tools\n\n"

        if ctx.tools:
            for tool in ctx.tools:
                name = getattr(tool, "name", "unknown")
                desc = getattr(tool, "description", "")
                schema = getattr(tool, "parameters_schema", lambda: {})()
                out += f"- **{name}**: {desc}\n"
                if schema:
                    out += f"  Parameters: `{schema}`\n"
                out += "\n"
        else:
            out += "No tools available.\n"

        # Add explicit instructions for tool usage
        out += """
## Tool Usage Instructions

**QUAN TRỌNG - BẠN PHẢI TUÂN THỦ:**

1. **document_search**: KHÔNG BAO GIỜ tự trả lờicâu hỏi về tài liệu mà không dùng tool này.
   - Khi user hỏi về "file", "tài liệu", "document", "PDF", "upload", hoặc nội dung trong file
   - BẠN PHẢI gọi `document_search` TRƯỚC KHI trả lờii
   - Ví dụ: "đọc file", "tìm trong tài liệu", "thông tin này ở đâu" → GỌI document_search

2. **calculator**: Dùng cho các phép tính toán học.
   - Khi cần tính toán chính xác, không dựa vào kiến thức training

**LUÔN gọi tool khi cần thiết, đừng tự trả lờii dựa trên kiến thức training khi user hỏi về file của họ.**
"""

        if ctx.dispatcher_instructions:
            out += f"\n{ctx.dispatcher_instructions}\n"

        return out


class SafetySection:
    """Safety guidelines section."""

    def name(self) -> str:
        return "safety"

    def build(self, ctx: PromptContext) -> str:
        return """## Safety

- Do not exfiltrate private data.
- Do not run destructive commands without asking.
- Do not bypass oversight or approval mechanisms.
- When in doubt, ask before acting externally."""


class WorkspaceSection:
    """Workspace information section."""

    def name(self) -> str:
        return "workspace"

    def build(self, ctx: PromptContext) -> str:
        if ctx.workspace_dir:
            return f"## Workspace\n\nWorking directory: `{ctx.workspace_dir}`"
        return "## Workspace\n\nNo workspace configured."


class RuntimeSection:
    """Runtime environment section."""

    def name(self) -> str:
        return "runtime"

    def build(self, ctx: PromptContext) -> str:
        import platform

        return f"## Runtime\n\nHost: {platform.node()} | OS: {platform.system()} | Model: {ctx.model_name}"


class DateTimeSection:
    """Current date and time section."""

    DATETIME_HEADER = "## Current Date & Time\n\n"

    def name(self) -> str:
        return "datetime"

    def build(self, ctx: PromptContext) -> str:
        now = datetime.now()
        return f"{self.DATETIME_HEADER}{now.strftime('%Y-%m-%d %H:%M:%S')} ({now.strftime('%Z')})"

    @classmethod
    def refresh_datetime(cls, prompt: str) -> str:
        """Update just the datetime in an existing prompt."""
        if cls.DATETIME_HEADER not in prompt:
            return prompt

        start = prompt.find(cls.DATETIME_HEADER) + len(cls.DATETIME_HEADER)
        end = prompt.find("\n", start)
        if end == -1:
            end = len(prompt)

        now = datetime.now()
        new_datetime = f"{now.strftime('%Y-%m-%d %H:%M:%S')} ({now.strftime('%Z')})"

        return prompt[:start] + new_datetime + prompt[end:]


class ChannelMediaSection:
    """Channel media markers section."""

    def name(self) -> str:
        return "channel_media"

    def build(self, ctx: PromptContext) -> str:
        return """## Channel Media Markers

Messages from channels may contain media markers:
- `[Voice] <text>` — Voice message transcribed to text
- `[IMAGE:<path>]` — Image attachment processed by vision
- `[Document: <name>] <path>` — File attachment saved to workspace"""


def create_system_prompt(
    tools: Optional[List] = None,
    workspace_dir: Optional[Path] = None,
    model_name: str = "unknown",
    extra_files: Optional[List[str]] = None,
    include_sections: Optional[List[str]] = None,
    research_context: str = "",
) -> str:
    """
    Convenience function to create a system prompt.

    Args:
        tools: Available tools
        workspace_dir: Workspace directory
        model_name: Model name
        extra_files: Extra identity files
        include_sections: Specific sections to include
        research_context: Research findings to include in prompt

    Returns:
        Complete system prompt
    """
    ctx = PromptContext(
        workspace_dir=workspace_dir,
        model_name=model_name,
        tools=tools,
        extra_files=extra_files,
    )

    builder = SystemPromptBuilder()

    sections_map = {
        "identity": IdentitySection(),
        "tools": ToolsSection(),
        "safety": SafetySection(),
        "workspace": WorkspaceSection(),
        "datetime": DateTimeSection(),
        "runtime": RuntimeSection(),
        "channel_media": ChannelMediaSection(),
    }

    if include_sections:
        for section_name in include_sections:
            if section_name in sections_map:
                builder.add_section(sections_map[section_name])
    else:
        builder = SystemPromptBuilder.with_defaults()

    prompt = builder.build(ctx)

    # Add research context if provided
    if research_context:
        prompt = f"{prompt}\n\n## Research Context\n\n{research_context}"

    return prompt
