# week_9/tests/test_client.py
import pytest
from mcp_client import MCPClientManager
import os

@pytest.mark.asyncio
async def test_mcp_client_integration():
    server_path = os.path.abspath("mcp_server.py")
    
    async with MCPClientManager() as client:
        await client.connect_to_server(server_path)
        
        # 1. Test tool discovery
        tools = await client.list_available_tools()
        tool_names = [t.name for t in tools]
        assert "analyze_text_length" in tool_names
        
        # 2. Test remote tool execution
        result = await client.call_tool("analyze_text_length", {"text": "Hello MCP architecture"})
        # MCP tool content returns a list of blocks
        content_text = result.content[0].text
        assert "word_count" in content_text