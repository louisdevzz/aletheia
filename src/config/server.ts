export interface ServerConfig {
  readonly host: string;
  readonly port: number;
  readonly corsOrigins: readonly string[];
}

export function getServerConfig(): ServerConfig {
  return {
    host: Bun.env.HOST ?? "0.0.0.0",
    port: parseInt(Bun.env.PORT ?? "8000", 10),
    corsOrigins: (Bun.env.CORS_ORIGINS ?? "http://localhost:3000,http://localhost:3001").split(","),
  };
}
