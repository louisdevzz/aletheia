import { Hono } from "hono";
import { streamSSE } from "hono/streaming";
import { Agent, AgentBuilder } from "../agent/agent.js";
import { NativeToolDispatcher } from "../agent/dispatcher.js";
import { RAGTool } from "../tools/rag-tool.js";
import { CalculatorTool } from "../tools/calculator-tool.js";
import { KimiProvider } from "../providers/kimi.js";
import { SQLiteStore } from "../rag/storage/sqlite-store.js";

const chat = new Hono();

let agentInstance: Agent | null = null;

function getAgent(): Agent {
  if (!agentInstance) {
    agentInstance = new AgentBuilder()
      .provider(new KimiProvider())
      .tools([new RAGTool(), new CalculatorTool()])
      .dispatcher(new NativeToolDispatcher())
      .enableResearch(true)
      .build();
  }
  return agentInstance;
}

chat.post("/chat", async (c) => {
  const body = await c.req.json<{ message: string; session_id?: string; stream?: boolean }>();

  if (!body.message?.trim()) {
    return c.json({ error: "Message cannot be empty" }, 400);
  }

  if (body.stream !== false) {
    // SSE streaming response
    return streamSSE(c, async (stream) => {
      try {
        const agent = getAgent();
        const response = await agent.chat(body.message, body.session_id);

        await stream.writeSSE({
          data: JSON.stringify({ content: response, done: false }),
        });

        await stream.writeSSE({
          data: JSON.stringify({ content: "", done: true }),
        });
      } catch (e) {
        await stream.writeSSE({
          data: JSON.stringify({ error: e instanceof Error ? e.message : String(e) }),
        });
      }
    });
  }

  // Non-streaming
  const agent = getAgent();
  const response = await agent.chat(body.message, body.session_id);
  return c.json({ content: response });
});

chat.get("/chat/history/:sessionId", async (c) => {
  const sessionId = c.req.param("sessionId");

  try {
    const storage = new SQLiteStore();
    const history = storage.getChatHistory(sessionId);
    storage.close();

    return c.json({
      messages: history.map((msg) => ({
        role: msg.role,
        content: msg.content,
        sources: msg.sources ?? null,
      })),
      session_id: sessionId,
    });
  } catch (e) {
    return c.json({ error: String(e) }, 500);
  }
});

export { chat };
