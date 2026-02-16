"""MCP-based Jira client using the official Atlassian MCP server.

Connects through mcp-remote which handles OAuth 2.1 authentication.
No API tokens needed -- authenticates via browser on first use, cached after.

Usage:
    # Single session (sequential calls)
    async with mcp_session() as ctx:
        result = await ctx.call("searchJiraIssuesUsingJql", jql="...", ...)

    # Pool of sessions (parallel calls)
    async with MCPPool(concurrency=3) as pool:
        results = await pool.map("createJiraIssue", [args1, args2, ...])
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

MCP_SERVER_URL = "https://mcp.atlassian.com/v1/mcp"
DEFAULT_CONCURRENCY = 3


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MCPToolError(Exception):
    """Raised when an MCP tool call returns an error."""
    pass


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def parse_result(result) -> Any:
    """Parse a CallToolResult into a Python object."""
    if result.isError:
        texts = [c.text for c in result.content if hasattr(c, "text")]
        raise MCPToolError("\n".join(texts) or "Unknown MCP tool error")
    texts = [c.text for c in result.content if hasattr(c, "text")]
    combined = "\n".join(texts)
    if not combined:
        return None
    try:
        return json.loads(combined)
    except json.JSONDecodeError:
        return combined


# ---------------------------------------------------------------------------
# Session wrapper with cloud ID caching
# ---------------------------------------------------------------------------


class MCPContext:
    """Wraps a ClientSession with convenience methods and cloud ID caching."""

    def __init__(self, session: ClientSession):
        self.session = session
        self._cloud_id: str | None = None

    async def call(self, tool_name: str, **kwargs: Any) -> Any:
        """Call an MCP tool and return the parsed result."""
        result = await self.session.call_tool(tool_name, kwargs)
        return parse_result(result)

    async def cloud_id(self) -> str:
        """Get the Atlassian cloud ID (discovered once, then cached)."""
        if self._cloud_id:
            return self._cloud_id
        resources = await self.call("getAccessibleAtlassianResources")
        if isinstance(resources, list) and resources:
            self._cloud_id = resources[0].get("id", "")
            return self._cloud_id
        raise MCPToolError("No accessible Atlassian resources found. Check OAuth.")

    async def list_tools(self) -> list[dict]:
        """List all available MCP tools."""
        result = await self.session.list_tools()
        return [{"name": t.name, "description": t.description} for t in result.tools]

    @property
    def project_key(self) -> str:
        return os.environ.get("JIRA_PROJECT_KEY", "")

    @property
    def base_url(self) -> str:
        return os.environ.get("JIRA_BASE_URL", "")


# ---------------------------------------------------------------------------
# Single session context manager
# ---------------------------------------------------------------------------


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command="npx",
        args=["-y", "mcp-remote", MCP_SERVER_URL],
    )


@asynccontextmanager
async def mcp_session():
    """Create a single MCP session connected to the Atlassian MCP server.

    On first use, opens a browser for OAuth 2.1 login. Token is cached for
    subsequent runs by mcp-remote.

    Usage:
        async with mcp_session() as ctx:
            issues = await ctx.call("searchJiraIssuesUsingJql",
                                    cloudId=await ctx.cloud_id(), jql="...")
    """
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield MCPContext(session)


# ---------------------------------------------------------------------------
# Session pool for parallel calls
# ---------------------------------------------------------------------------


class MCPPool:
    """Pool of MCP sessions for parallel tool calls.

    Opens N concurrent mcp-remote processes. The first session is created
    first (may trigger OAuth browser popup), then the rest are created
    in parallel (reuse cached token).

    Usage:
        async with MCPPool(concurrency=3) as pool:
            results = await pool.map("createJiraIssue", [
                {"cloudId": cid, "projectKey": "PROJ", "summary": "Task 1", ...},
                {"cloudId": cid, "projectKey": "PROJ", "summary": "Task 2", ...},
            ])
    """

    def __init__(self, concurrency: int = DEFAULT_CONCURRENCY):
        self.concurrency = concurrency
        self._stack: AsyncExitStack | None = None
        self._queue: asyncio.Queue[MCPContext] = asyncio.Queue()
        self._cloud_id: str | None = None

    async def __aenter__(self) -> "MCPPool":
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        # First session -- may open browser for OAuth
        first = await self._create_context()
        self._cloud_id = await first.cloud_id()
        await self._queue.put(first)

        # Remaining sessions -- reuse cached OAuth token
        for _ in range(self.concurrency - 1):
            ctx = await self._create_context()
            ctx._cloud_id = self._cloud_id
            await self._queue.put(ctx)

        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._stack:
            await self._stack.__aexit__(*exc)

    async def _create_context(self) -> MCPContext:
        read, write = await self._stack.enter_async_context(
            stdio_client(_server_params())
        )
        session = await self._stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()
        return MCPContext(session)

    async def cloud_id(self) -> str:
        """Return the cached cloud ID (discovered during pool init)."""
        if self._cloud_id:
            return self._cloud_id
        raise MCPToolError("Pool not initialized")

    async def call(self, tool_name: str, **kwargs: Any) -> Any:
        """Call a tool on the next available session."""
        ctx = await self._queue.get()
        try:
            return await ctx.call(tool_name, **kwargs)
        finally:
            await self._queue.put(ctx)

    async def map(self, tool_name: str, args_list: list[dict]) -> list[Any]:
        """Call a tool with different kwargs, distributed across pool sessions.

        Returns a list of results (or exceptions) in the same order as args_list.
        """
        async def _one(kwargs: dict) -> Any:
            return await self.call(tool_name, **kwargs)

        tasks = [_one(a) for a in args_list]
        return await asyncio.gather(*tasks, return_exceptions=True)


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def run_async(coro):
    """Run an async coroutine from a sync entry point."""
    return asyncio.run(coro)
