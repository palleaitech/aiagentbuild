import os
import asyncio
import sys
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClientManager:
    def __init__(self):
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_script_path: str):
        """Starts the MCP server as a subprocess and establishes a stdio session."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script_path],
            env=os.environ  # 👈 Pass current container environment variables down to the subprocess!
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()

    async def list_available_tools(self):
        """Dynamically fetches tools exposed by the MCP server."""
        if not self.session:
            raise RuntimeError("MCP Client is not connected.")
        response = await self.session.list_tools()
        return response.tools

    async def call_tool(self, tool_name: str, arguments: dict):
        """Executes a tool on the MCP server remotely."""
        if not self.session:
            raise RuntimeError("MCP Client is not connected.")
        result = await self.session.call_tool(tool_name, arguments)
        return result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.exit_stack.aclose()