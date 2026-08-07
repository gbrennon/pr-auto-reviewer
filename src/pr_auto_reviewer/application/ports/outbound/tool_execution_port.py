"""ToolExecutionPort — execute a tool call against the repository under review."""

from typing import Protocol

from pr_auto_reviewer.domain.agent.tool_call import ToolCall
from pr_auto_reviewer.domain.agent.tool_result import ToolResult


class ToolExecutionPort(Protocol):
    """Execute a ToolCall against the repository and return the result.

    Infrastructure adapters implement this to provide file reading,
    code search, directory listing, and git operations.
    """

    def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute *tool_call* and return the result."""
