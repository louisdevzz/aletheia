import { Hono } from "hono";
import { cors } from "hono/cors";
import { randomUUID } from "crypto";
import { existsSync, mkdirSync, readFileSync } from "fs";
import { join } from "path";
import { system } from "./routes/system.js";
import { documents, setBroadcast } from "./routes/documents.js";
import { chat } from "./routes/chat.js";
import { manager } from "./websocket/manager.js";
import type { WebSocketData } from "./websocket/manager.js";
import { handleWebSocketMessage } from "./websocket/chat.js";
import { getWorkspaceDir } from "./config/settings.js";
import { getServerConfig } from "./config/server.js";

// Initialize workspace
function initializeWorkspace(): void {
  const workspaceDir = join(getWorkspaceDir(), "workspace");
  const memoryDir = join(getWorkspaceDir(), "memory");

  if (!existsSync(workspaceDir)) mkdirSync(workspaceDir, { recursive: true });
  if (!existsSync(memoryDir)) mkdirSync(memoryDir, { recursive: true });

  const identityFiles = ["AGENTS.md", "SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "BOOTSTRAP.md"];
  let created = 0;

  for (const filename of identityFiles) {
    const targetPath = join(workspaceDir, filename);
    if (!existsSync(targetPath)) {
      // Try to find template
      const templatePath = join(import.meta.dir, "..", filename);
      if (existsSync(templatePath)) {
        const content = readFileSync(templatePath, "utf-8");
        Bun.write(targetPath, content);
        created++;
        console.log(`  Created ${filename}`);
      }
    }
  }

  if (created > 0) {
    console.log(`  Created ${created} identity files in ${workspaceDir}`);
  }
}

// Create Hono app
const app = new Hono();

// CORS middleware
const serverConfig = getServerConfig();
app.use(
  "*",
  cors({
    origin: [...serverConfig.corsOrigins],
    credentials: true,
    allowMethods: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
  }),
);

// Mount routes
app.route("/api/v1", system);
app.route("/api/v1", documents);
app.route("/api/v1", chat);

// Wire up broadcast for document ingestion notifications
setBroadcast((data) => manager.broadcast(data));

// Initialize
console.log("\nStarting Aletheia Daemon...");
initializeWorkspace();

// Start Bun server with WebSocket support
const server = Bun.serve<WebSocketData>({
  port: serverConfig.port,
  hostname: serverConfig.host,
  fetch: (req, server) => {
    const url = new URL(req.url);

    // WebSocket upgrade
    if (url.pathname === "/ws/chat") {
      const connectionId = randomUUID();
      const upgraded = server.upgrade(req, {
        data: { connectionId },
      });
      if (upgraded) return undefined;
      return new Response("WebSocket upgrade failed", { status: 400 });
    }

    // Handle HTTP requests via Hono
    return app.fetch(req, { ip: server.requestIP(req) });
  },
  websocket: {
    open(ws) {
      manager.connect(ws, ws.data.connectionId);
    },
    async message(ws, message) {
      const raw = typeof message === "string" ? message : new TextDecoder().decode(message);
      await handleWebSocketMessage(ws, raw);
    },
    close(ws) {
      manager.disconnect(ws.data.connectionId);
    },
  },
});

console.log(`
╔══════════════════════════════════════════════════╗
║            Aletheia Daemon                       ║
╠══════════════════════════════════════════════════╣
║  Host:   ${serverConfig.host.padEnd(35)}  ║
║  Port:   ${String(serverConfig.port).padEnd(35)}  ║
║  URL:    http://${serverConfig.host}:${serverConfig.port}${" ".repeat(Math.max(0, 26 - serverConfig.host.length - String(serverConfig.port).length))}  ║
╚══════════════════════════════════════════════════╝
`);

export { app, server };
