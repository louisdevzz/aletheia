import type { ServerWebSocket } from "bun";
import type { WebSocketData } from "./manager.js";
import { Agent, AgentBuilder } from "../agent/agent.js";
import { NativeToolDispatcher } from "../agent/dispatcher.js";
import { RAGTool } from "../tools/rag-tool.js";
import { CalculatorTool } from "../tools/calculator-tool.js";
import { KimiProvider } from "../providers/kimi.js";

const sessions: Map<string, Agent> = new Map();

function createAgent(): Agent {
  return new AgentBuilder()
    .provider(new KimiProvider())
    .tools([new RAGTool(), new CalculatorTool()])
    .dispatcher(new NativeToolDispatcher())
    .enableResearch(true)
    .build();
}

function getOrCreateAgent(sessionId: string): Agent {
  let agent = sessions.get(sessionId);
  if (!agent) {
    console.log(`[ws-chat] Creating agent for session ${sessionId.slice(0, 8)}`);
    agent = createAgent();
    sessions.set(sessionId, agent);
  }
  return agent;
}

function chunkMsg(content: string, done: boolean, sources?: unknown[]): string {
  const payload: Record<string, unknown> = { content, done };
  if (done && sources) {
    payload.sources = sources;
  }
  return JSON.stringify({ type: "chat.chunk", payload });
}

function errorMsg(message: string): string {
  return JSON.stringify({ type: "error", payload: { message } });
}

export async function handleWebSocketMessage(
  ws: ServerWebSocket<WebSocketData>,
  raw: string,
): Promise<void> {
  let frame: Record<string, unknown>;
  try {
    frame = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    ws.send(errorMsg("Invalid JSON"));
    return;
  }

  if (frame.type !== "chat.message") {
    ws.send(errorMsg("Expected 'chat.message' type"));
    return;
  }

  const payload = (frame.payload ?? {}) as Record<string, unknown>;
  const userMessage = ((payload.message as string) ?? "").trim();
  const sessionId = (payload.session_id as string) ?? ws.data.connectionId;

  if (!userMessage) {
    ws.send(errorMsg("Message cannot be empty"));
    return;
  }

  console.log(`[ws-chat] Message: "${userMessage.slice(0, 50)}" (session=${sessionId.slice(0, 8)})`);

  const agent = getOrCreateAgent(sessionId);

  try {
    const response = await agent.chat(userMessage, sessionId);
    ws.send(chunkMsg(response, false));
    ws.send(chunkMsg("", true));
  } catch (e) {
    console.error(`[ws-chat] Agent error:`, e);
    ws.send(errorMsg(`Error: ${e instanceof Error ? e.message : String(e)}`));
  }
}
