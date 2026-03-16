import type { ServerWebSocket } from "bun";

export interface WebSocketData {
  connectionId: string;
  sessionId?: string;
}

export class ConnectionManager {
  private connections: ReadonlyMap<string, ServerWebSocket<WebSocketData>> = new Map();

  get activeCount(): number {
    return this.connections.size;
  }

  connect(ws: ServerWebSocket<WebSocketData>, connectionId: string): void {
    const newConnections = new Map(this.connections);
    newConnections.set(connectionId, ws);
    this.connections = newConnections;
    console.log(`[ws] Connected: ${connectionId} (total: ${this.activeCount})`);
  }

  disconnect(connectionId: string): void {
    const newConnections = new Map(this.connections);
    newConnections.delete(connectionId);
    this.connections = newConnections;
    console.log(`[ws] Disconnected: ${connectionId} (total: ${this.activeCount})`);
  }

  sendJson(connectionId: string, data: Record<string, unknown>): void {
    const ws = this.connections.get(connectionId);
    if (!ws) {
      console.warn(`[ws] Connection ${connectionId} not found`);
      return;
    }
    try {
      ws.send(JSON.stringify(data));
    } catch (e) {
      console.error(`[ws] Send error on ${connectionId}:`, e);
      this.disconnect(connectionId);
    }
  }

  broadcast(data: Record<string, unknown>): void {
    if (this.connections.size === 0) return;

    const payload = JSON.stringify(data);
    const failed: string[] = [];

    for (const [id, ws] of this.connections) {
      try {
        ws.send(payload);
      } catch {
        failed.push(id);
      }
    }

    if (failed.length > 0) {
      const newConnections = new Map(this.connections);
      for (const id of failed) {
        newConnections.delete(id);
        console.warn(`[ws] Removed failed connection: ${id}`);
      }
      this.connections = newConnections;
    }
  }
}

export const manager = new ConnectionManager();
