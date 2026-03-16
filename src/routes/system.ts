import { Hono } from "hono";

const system = new Hono();

system.get("/health", (c) => {
  return c.json({
    status: "healthy",
    timestamp: new Date().toISOString(),
    version: "0.1.0",
  });
});

system.get("/status", async (c) => {
  let storageStatus = "connected";
  let stats: Record<string, unknown> = {};

  try {
    const { SQLiteStore } = await import("../rag/storage/sqlite-store.js");
    const store = new SQLiteStore();
    stats = store.getStats();
    store.close();
  } catch (e) {
    storageStatus = `error: ${e instanceof Error ? e.message : String(e)}`;
  }

  return c.json({
    status: "running",
    storage: {
      type: "sqlite",
      status: storageStatus,
      stats,
    },
    timestamp: new Date().toISOString(),
  });
});

export { system };
