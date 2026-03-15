"""
Calculator Tool

Example tool for mathematical calculations.
"""

from typing import Any, Dict
import ast
import operator
from .base import Tool, ToolResult


class CalculatorTool(Tool):
    """Tool for safe mathematical calculations."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Perform mathematical calculations safely. "
            "Supports basic operations: +, -, *, /, **, parentheses."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to calculate (e.g., '2 + 2', '(10 * 5) / 2')",
                }
            },
            "required": ["expression"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute calculation safely."""
        try:
            expression = arguments.get("expression", "")
            if not expression:
                return ToolResult(
                    success=False, output="", error="Expression is required"
                )

            # Safe evaluation
            result = self._safe_eval(expression)

            return ToolResult(success=True, output=str(result))

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Calculation error: {str(e)}"
            )

    def _safe_eval(self, expr: str) -> float:
        """
        Safely evaluate mathematical expression.
        Only allows basic math operations.
        """
        # Allowed operators
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }

        def eval_node(node):
            if isinstance(node, ast.Num):  # Python 3.7
                return node.n
            elif isinstance(node, ast.Constant):  # Python 3.8+
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError("Only numbers allowed")
            elif isinstance(node, ast.BinOp):
                op_type = type(node.op)
                if op_type not in operators:
                    raise ValueError(f"Unsupported operator: {op_type}")
                return operators[op_type](eval_node(node.left), eval_node(node.right))
            elif isinstance(node, ast.UnaryOp):
                op_type = type(node.op)
                if op_type not in operators:
                    raise ValueError(f"Unsupported unary operator: {op_type}")
                return operators[op_type](eval_node(node.operand))
            elif isinstance(node, ast.Expression):
                return eval_node(node.body)
            else:
                raise ValueError(f"Unsupported expression type: {type(node)}")

        # Parse and evaluate
        parsed = ast.parse(expr.strip(), mode="eval")
        return eval_node(parsed)
