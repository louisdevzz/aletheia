import { evaluate } from "mathjs";
import { BaseTool, createToolResult } from "./base.js";
import type { ToolResult } from "./base.js";

export class CalculatorTool extends BaseTool {
  readonly name = "calculator";
  readonly description =
    "Perform mathematical calculations safely. Supports basic operations: +, -, *, /, **, parentheses, and mathematical functions.";

  get parametersSchema(): Record<string, unknown> {
    return {
      type: "object",
      properties: {
        expression: {
          type: "string",
          description:
            "Mathematical expression to calculate (e.g., '2 + 2', '(10 * 5) / 2')",
        },
      },
      required: ["expression"],
    };
  }

  async execute(args: Record<string, unknown>): Promise<ToolResult> {
    const expression = args.expression as string | undefined;
    if (!expression) {
      return createToolResult(false, "", "Expression is required");
    }

    try {
      const result = evaluate(expression);
      return createToolResult(true, String(result));
    } catch (e) {
      return createToolResult(false, "", `Calculation error: ${String(e)}`);
    }
  }
}
