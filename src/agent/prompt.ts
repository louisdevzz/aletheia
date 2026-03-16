import { readFileSync, existsSync } from "fs";
import { join } from "path";
import { hostname, platform } from "os";
import type { BaseTool } from "../tools/base.js";

export interface PromptContext {
  readonly workspaceDir?: string;
  readonly modelName: string;
  readonly tools?: readonly BaseTool[];
  readonly extraFiles?: readonly string[];
  readonly dispatcherInstructions?: string;
  readonly researchContext?: string;
}

interface PromptSection {
  name(): string;
  build(ctx: PromptContext): string;
}

const BOOTSTRAP_MAX_CHARS = 20000;

class IdentitySection implements PromptSection {
  name(): string {
    return "identity";
  }

  build(ctx: PromptContext): string {
    let prompt = "## Project Context\n\n";

    const identityFiles = [
      "AGENTS.md",
      "SOUL.md",
      "TOOLS.md",
      "IDENTITY.md",
      "USER.md",
      "HEARTBEAT.md",
      "BOOTSTRAP.md",
      "MEMORY.md",
    ];

    if (ctx.workspaceDir) {
      for (const filename of identityFiles) {
        const content = readWorkspaceFile(ctx.workspaceDir, filename);
        if (content) {
          prompt += `### ${filename}\n\n`;
          prompt += truncate(content, BOOTSTRAP_MAX_CHARS);
          prompt += "\n\n";
        }
      }

      if (ctx.extraFiles) {
        for (const filename of ctx.extraFiles) {
          if (isSafeFilename(filename)) {
            const content = readWorkspaceFile(ctx.workspaceDir, filename);
            if (content) {
              prompt += `### ${filename}\n\n`;
              prompt += truncate(content, BOOTSTRAP_MAX_CHARS);
              prompt += "\n\n";
            }
          }
        }
      }
    }

    return prompt;
  }
}

class ToolsSection implements PromptSection {
  name(): string {
    return "tools";
  }

  build(ctx: PromptContext): string {
    let out = "## Tools\n\n";

    if (ctx.tools && ctx.tools.length > 0) {
      for (const tool of ctx.tools) {
        const schema = tool.parametersSchema;
        out += `- **${tool.name}**: ${tool.description}\n`;
        if (schema && Object.keys(schema).length > 0) {
          out += `  Parameters: \`${JSON.stringify(schema)}\`\n`;
        }
        out += "\n";
      }
    } else {
      out += "No tools available.\n";
    }

    out += `
## Tool Usage Instructions

**IMPORTANT - YOU MUST FOLLOW:**

1. **document_search**: NEVER answer document questions without using this tool first.
   - When user asks about "file", "document", "PDF", "upload", or content in files
   - YOU MUST call \`document_search\` BEFORE answering
   - Example: "read file", "find in document", "where is this info" → CALL document_search

2. **calculator**: Use for mathematical calculations.
   - When exact calculations are needed, don't rely on training knowledge

**ALWAYS call tools when needed. Don't answer from training knowledge when users ask about their files.**
`;

    if (ctx.dispatcherInstructions) {
      out += `\n${ctx.dispatcherInstructions}\n`;
    }

    return out;
  }
}

class SafetySection implements PromptSection {
  name(): string {
    return "safety";
  }

  build(): string {
    return `## Safety

- Do not exfiltrate private data.
- Do not run destructive commands without asking.
- Do not bypass oversight or approval mechanisms.
- When in doubt, ask before acting externally.`;
  }
}

class WorkspaceSection implements PromptSection {
  name(): string {
    return "workspace";
  }

  build(ctx: PromptContext): string {
    if (ctx.workspaceDir) {
      return `## Workspace\n\nWorking directory: \`${ctx.workspaceDir}\``;
    }
    return "## Workspace\n\nNo workspace configured.";
  }
}

class RuntimeSection implements PromptSection {
  name(): string {
    return "runtime";
  }

  build(ctx: PromptContext): string {
    return `## Runtime\n\nHost: ${hostname()} | OS: ${platform()} | Model: ${ctx.modelName}`;
  }
}

class DateTimeSection implements PromptSection {
  static readonly HEADER = "## Current Date & Time\n\n";

  name(): string {
    return "datetime";
  }

  build(): string {
    const now = new Date();
    return `${DateTimeSection.HEADER}${now.toISOString()}`;
  }

  static refreshDateTime(prompt: string): string {
    const header = DateTimeSection.HEADER;
    const idx = prompt.indexOf(header);
    if (idx === -1) return prompt;

    const start = idx + header.length;
    let end = prompt.indexOf("\n", start);
    if (end === -1) end = prompt.length;

    return prompt.slice(0, start) + new Date().toISOString() + prompt.slice(end);
  }
}

export class SystemPromptBuilder {
  private sections: PromptSection[] = [];

  static withDefaults(): SystemPromptBuilder {
    const builder = new SystemPromptBuilder();
    builder.sections = [
      new IdentitySection(),
      new ToolsSection(),
      new SafetySection(),
      new WorkspaceSection(),
      new DateTimeSection(),
      new RuntimeSection(),
    ];
    return builder;
  }

  addSection(section: PromptSection): SystemPromptBuilder {
    return Object.assign(Object.create(Object.getPrototypeOf(this)), {
      sections: [...this.sections, section],
    }) as SystemPromptBuilder;
  }

  build(ctx: PromptContext): string {
    const parts: string[] = [];

    for (const section of this.sections) {
      try {
        const content = section.build(ctx);
        if (content?.trim()) {
          parts.push(content.trim());
        }
      } catch {
        continue;
      }
    }

    return parts.join("\n\n");
  }
}

export { DateTimeSection };

export function createSystemPrompt(options: {
  tools?: readonly BaseTool[];
  workspaceDir?: string;
  modelName?: string;
  extraFiles?: readonly string[];
  researchContext?: string;
}): string {
  const ctx: PromptContext = {
    workspaceDir: options.workspaceDir,
    modelName: options.modelName ?? "unknown",
    tools: options.tools,
    extraFiles: options.extraFiles,
  };

  const builder = SystemPromptBuilder.withDefaults();
  let prompt = builder.build(ctx);

  if (options.researchContext) {
    prompt = `${prompt}\n\n## Research Context\n\n${options.researchContext}`;
  }

  return prompt;
}

function readWorkspaceFile(workspaceDir: string, filename: string): string | null {
  try {
    const path = join(workspaceDir, filename);
    if (existsSync(path)) {
      return readFileSync(path, "utf-8");
    }
  } catch {
    // ignore
  }
  return null;
}

function truncate(content: string, maxChars: number): string {
  if (content.length <= maxChars) return content;
  return content.slice(0, maxChars) + `\n\n[... truncated at ${maxChars} chars]`;
}

function isSafeFilename(filename: string): boolean {
  return !filename.includes("..") && !filename.startsWith("/") && !filename.startsWith("\\");
}
