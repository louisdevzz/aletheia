import { randomUUID } from "crypto";

export interface SessionMessage {
  readonly role: string;
  readonly content: string;
  readonly timestamp: string;
  readonly [key: string]: unknown;
}

export interface Session {
  readonly id: string;
  readonly createdAt: string;
  updatedAt: string;
  messages: readonly SessionMessage[];
  metadata: Record<string, unknown>;
}

export function createSession(metadata?: Record<string, unknown>): Session {
  const now = new Date().toISOString();
  return {
    id: randomUUID(),
    createdAt: now,
    updatedAt: now,
    messages: [],
    metadata: metadata ?? {},
  };
}

export function addSessionMessage(
  session: Session,
  role: string,
  content: string,
  extra?: Record<string, unknown>,
): Session {
  const message: SessionMessage = {
    role,
    content,
    timestamp: new Date().toISOString(),
    ...extra,
  };
  return {
    ...session,
    updatedAt: new Date().toISOString(),
    messages: [...session.messages, message],
  };
}

export function sessionToDict(session: Session): Record<string, unknown> {
  return {
    id: session.id,
    created_at: session.createdAt,
    updated_at: session.updatedAt,
    messages: session.messages,
    metadata: session.metadata,
  };
}

export function sessionFromDict(data: Record<string, unknown>): Session {
  return {
    id: data.id as string,
    createdAt: data.created_at as string,
    updatedAt: data.updated_at as string,
    messages: (data.messages as readonly SessionMessage[]) ?? [],
    metadata: (data.metadata as Record<string, unknown>) ?? {},
  };
}

export class SessionManager {
  private sessions: ReadonlyMap<string, Session> = new Map();

  createSession(metadata?: Record<string, unknown>): Session {
    const session = createSession(metadata);
    const newSessions = new Map(this.sessions);
    newSessions.set(session.id, session);
    this.sessions = newSessions;
    return session;
  }

  getSession(sessionId: string): Session | null {
    return this.sessions.get(sessionId) ?? null;
  }

  updateSession(session: Session): void {
    const newSessions = new Map(this.sessions);
    newSessions.set(session.id, session);
    this.sessions = newSessions;
  }

  deleteSession(sessionId: string): boolean {
    if (!this.sessions.has(sessionId)) return false;
    const newSessions = new Map(this.sessions);
    newSessions.delete(sessionId);
    this.sessions = newSessions;
    return true;
  }

  listSessions(): readonly Record<string, unknown>[] {
    return [...this.sessions.values()].map((s) => ({
      id: s.id,
      created_at: s.createdAt,
      updated_at: s.updatedAt,
      message_count: s.messages.length,
      metadata: s.metadata,
    }));
  }
}
