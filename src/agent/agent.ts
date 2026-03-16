import type { BaseTool, ToolCall } from "../tools/base.js";
import { ToolRegistry } from "../tools/registry.js";
import type { Provider, ChatMessage, ChatRequest } from "../providers/base.js";
import type { ToolDispatcher } from "./dispatcher.js";
import { NativeToolDispatcher } from "./dispatcher.js";
import { LoopDetector, LoopVerdict } from "./loop/detection.js";
import { ToolExecutor } from "./loop/execution.js";
import { HistoryManager } from "./loop/history.js";
import { ResearchPhase } from "./research.js";
import { SessionManager, addSessionMessage } from "./session.js";
import type { Session } from "./session.js";
import { createSystemPrompt } from "./prompt.js";
import { getWorkspaceDir } from "../config/settings.js";
import { getMemoryStore } from "./memory-store.js";
import type { SQLiteMemoryStore } from "./memory-store.js";
import { join } from "path";

export interface AgentConfig {
  readonly maxIterations: number;
  readonly temperature: number;
  readonly enableResearch: boolean;
  readonly enableLoopDetection: boolean;
  readonly enableHistoryCompaction: boolean;
  readonly maxHistoryMessages: number;
  readonly toolTimeoutSeconds: number;
}

const DEFAULT_AGENT_CONFIG: AgentConfig = {
  maxIterations: 5,
  temperature: 0.7,
  enableResearch: true,
  enableLoopDetection: true,
  enableHistoryCompaction: true,
  maxHistoryMessages: 20,
  toolTimeoutSeconds: 30.0,
};

export class Agent {
  private readonly provider: Provider;
  private readonly toolRegistry: ToolRegistry;
  private readonly dispatcher: ToolDispatcher;
  private readonly config: AgentConfig;
  private readonly sessionManager: SessionManager;
  private readonly loopDetector: LoopDetector;
  private readonly toolExecutor: ToolExecutor;
  private readonly historyManager: HistoryManager;
  private readonly researchPhase: ResearchPhase;
  private readonly memoryStore: SQLiteMemoryStore;

  private messages: readonly ChatMessage[] = [];
  private currentSession: Session | null = null;
  private stats = {
    totalRequests: 0,
    toolCalls: 0,
    compactions: 0,
    loopsDetected: 0,
  };

  constructor(
    provider: Provider,
    tools: readonly BaseTool[],
    dispatcher: ToolDispatcher,
    config: AgentConfig,
    sessionManager?: SessionManager,
  ) {
    this.provider = provider;
    this.toolRegistry = new ToolRegistry();
    this.dispatcher = dispatcher;
    this.config = config;
    this.sessionManager = sessionManager ?? new SessionManager();

    for (const tool of tools) {
      this.toolRegistry.register(tool);
    }

    this.loopDetector = new LoopDetector();
    this.toolExecutor = new ToolExecutor(this.toolRegistry);
    this.historyManager = new HistoryManager(
      config.maxHistoryMessages,
      Math.floor(config.maxHistoryMessages / 2),
    );
    this.researchPhase = new ResearchPhase();
    this.memoryStore = getMemoryStore();
  }

  async chat(userMessage: string, sessionId?: string): Promise<string> {
    this.stats = { ...this.stats, totalRequests: this.stats.totalRequests + 1 };
    const startTime = performance.now();
    console.log(`[agent] Received message: ${userMessage.slice(0, 100)}...`);

    // Get or create session
    if (sessionId) {
      this.currentSession = this.sessionManager.getSession(sessionId);
    }
    if (!this.currentSession) {
      this.currentSession = this.sessionManager.createSession();
    }

    // Initialize messages if empty
    if (this.messages.length === 0) {
      await this.initializeConversation(userMessage);
    } else {
      this.messages = [...this.messages, { role: "user", content: userMessage }];
      this.currentSession = addSessionMessage(this.currentSession, "user", userMessage);
      this.sessionManager.updateSession(this.currentSession);
    }

    let finalResponse = "";

    try {
      for (let iteration = 0; iteration < this.config.maxIterations; iteration++) {
        // Check loop detection
        if (this.config.enableLoopDetection) {
          const { verdict, message } = this.loopDetector.check();
          if (verdict === LoopVerdict.HARD_STOP) {
            finalResponse = message ?? "Loop detected. Stopping.";
            this.stats = { ...this.stats, loopsDetected: this.stats.loopsDetected + 1 };
            break;
          }
          if (verdict === LoopVerdict.INJECT_WARNING && message) {
            this.messages = [...this.messages, { role: "system", content: message }];
          }
        }

        // Maybe compact history
        if (this.config.enableHistoryCompaction) {
          const compaction = this.historyManager.maybeCompact(this.messages);
          if (compaction.result.success) {
            this.messages = compaction.messages;
            this.stats = { ...this.stats, compactions: this.stats.compactions + 1 };
          }
        }

        // Build request
        const toolSpecs = this.toolRegistry.getAllSpecs();
        const request: ChatRequest = {
          messages: [...this.messages],
          tools: toolSpecs.length > 0 ? toolSpecs : undefined,
          temperature: this.config.temperature,
        };

        // Call LLM
        console.log(`[agent] Calling provider with ${this.messages.length} messages`);
        const response = await this.provider.chat(request);

        // No tool calls - final answer
        if (!response.toolCalls || response.toolCalls.length === 0) {
          finalResponse = response.text ?? "";
          this.messages = [...this.messages, { role: "assistant", content: finalResponse }];
          this.currentSession = addSessionMessage(this.currentSession, "assistant", finalResponse);
          this.sessionManager.updateSession(this.currentSession);
          break;
        }

        // Parse tool calls
        const toolCalls: ToolCall[] = response.toolCalls.map((tc) => ({
          name: tc.name as string,
          arguments: JSON.parse(tc.arguments as string) as Record<string, unknown>,
          callId: tc.id as string,
        }));

        // Add assistant message with tool calls
        this.messages = [
          ...this.messages,
          {
            role: "assistant",
            content: response.text ?? "",
            toolCalls: response.toolCalls,
          },
        ];

        // Execute tools
        this.stats = { ...this.stats, toolCalls: this.stats.toolCalls + toolCalls.length };
        console.log(`[agent] Executing ${toolCalls.length} tool(s): ${toolCalls.map((tc) => tc.name).join(", ")}`);
        const execResults = await this.toolExecutor.executeMany(toolCalls);

        // Record for loop detection
        for (let i = 0; i < toolCalls.length; i++) {
          this.loopDetector.recordCall(
            toolCalls[i].name,
            toolCalls[i].arguments,
            execResults[i].result,
            iteration,
          );
        }

        // Add tool results to messages
        const toolMessages: ChatMessage[] = execResults.map((execResult) => ({
          role: "tool" as const,
          content: execResult.result.success
            ? execResult.result.output
            : `Error: ${execResult.result.error}`,
          toolCallId: execResult.call.callId,
        }));
        this.messages = [...this.messages, ...toolMessages];

        // Check if this is the last iteration
        if (iteration === this.config.maxIterations - 1) {
          finalResponse = "I wasn't able to complete the request in time. Please try rephrasing.";
        }
      }
    } catch (e) {
      finalResponse = `Error: ${e instanceof Error ? e.message : String(e)}`;
    }

    // Update session
    const durationMs = performance.now() - startTime;
    if (this.currentSession) {
      this.currentSession = {
        ...this.currentSession,
        metadata: { ...this.currentSession.metadata, last_duration_ms: durationMs },
      };
      this.sessionManager.updateSession(this.currentSession);
    }

    console.log(`[agent] Completed in ${durationMs.toFixed(0)}ms`);

    // Save interaction to memory
    await this.saveInteractionMemory(userMessage, finalResponse);

    return finalResponse;
  }

  private async saveInteractionMemory(userMessage: string, response: string): Promise<void> {
    try {
      await this.memoryStore.store(
        `user_query_${new Date().toISOString().replace(/[:.]/g, "_")}`,
        userMessage,
        "conversation",
        this.currentSession?.id,
        { type: "user_query", response_preview: response.slice(0, 100) },
      );

      const coreKeywords = ["name is", "i am", "my name", "remember that", "don't forget"];
      if (coreKeywords.some((kw) => userMessage.toLowerCase().includes(kw))) {
        await this.memoryStore.store(
          "user_identity_fact",
          `User mentioned: ${userMessage}`,
          "core",
          this.currentSession?.id,
          { type: "identity_fact", extracted_from: userMessage },
        );
      }
    } catch (e) {
      console.warn(`[agent] Failed to save memory: ${e}`);
    }
  }

  private async initializeConversation(userMessage: string): Promise<void> {
    let researchContext = "";
    if (this.config.enableResearch) {
      const tools = this.toolRegistry.getAll();
      const result = await this.researchPhase.conductResearch(userMessage, tools);
      if (result.success) {
        researchContext = this.researchPhase.formatFindings(result.findings);
      }
    }

    const workspaceDir = join(getWorkspaceDir(), "workspace");
    const systemPrompt = createSystemPrompt({
      tools: this.toolRegistry.getAll(),
      workspaceDir,
      researchContext,
    });

    this.messages = [
      { role: "system", content: systemPrompt },
      { role: "user", content: userMessage },
    ];

    if (this.currentSession) {
      this.currentSession = addSessionMessage(this.currentSession, "user", userMessage);
      this.sessionManager.updateSession(this.currentSession);
    }
  }

  getSessionId(): string | null {
    return this.currentSession?.id ?? null;
  }

  clear(): void {
    this.messages = [];
    this.currentSession = null;
  }

  getStats(): Record<string, unknown> {
    return {
      ...this.stats,
      history_length: this.messages.length,
      session_id: this.getSessionId(),
    };
  }
}

export class AgentBuilder {
  private _provider: Provider | null = null;
  private _tools: BaseTool[] = [];
  private _dispatcher: ToolDispatcher | null = null;
  private _config: AgentConfig = DEFAULT_AGENT_CONFIG;
  private _sessionManager: SessionManager | null = null;

  provider(provider: Provider): AgentBuilder {
    return Object.assign(Object.create(Object.getPrototypeOf(this)), {
      ...this,
      _provider: provider,
    }) as AgentBuilder;
  }

  addTool(tool: BaseTool): AgentBuilder {
    return Object.assign(Object.create(Object.getPrototypeOf(this)), {
      ...this,
      _tools: [...this._tools, tool],
    }) as AgentBuilder;
  }

  tools(tools: BaseTool[]): AgentBuilder {
    return Object.assign(Object.create(Object.getPrototypeOf(this)), {
      ...this,
      _tools: tools,
    }) as AgentBuilder;
  }

  dispatcher(dispatcher: ToolDispatcher): AgentBuilder {
    return Object.assign(Object.create(Object.getPrototypeOf(this)), {
      ...this,
      _dispatcher: dispatcher,
    }) as AgentBuilder;
  }

  config(config: Partial<AgentConfig>): AgentBuilder {
    return Object.assign(Object.create(Object.getPrototypeOf(this)), {
      ...this,
      _config: { ...this._config, ...config },
    }) as AgentBuilder;
  }

  sessionManager(manager: SessionManager): AgentBuilder {
    return Object.assign(Object.create(Object.getPrototypeOf(this)), {
      ...this,
      _sessionManager: manager,
    }) as AgentBuilder;
  }

  maxIterations(n: number): AgentBuilder {
    return this.config({ maxIterations: n });
  }

  temperature(temp: number): AgentBuilder {
    return this.config({ temperature: temp });
  }

  enableResearch(enabled = true): AgentBuilder {
    return this.config({ enableResearch: enabled });
  }

  build(): Agent {
    if (!this._provider) {
      throw new Error("Provider is required");
    }

    return new Agent(
      this._provider,
      this._tools,
      this._dispatcher ?? new NativeToolDispatcher(),
      this._config,
      this._sessionManager ?? undefined,
    );
  }
}
