# week_9/tests/test_server.py
from mcp_server import analyze_text_length, get_app_settings

def test_analyze_text_length():
    result = analyze_text_length("Hello MCP protocol")
    assert result["word_count"] == 3
    assert result["character_count"] == 18
    assert result["status"] == "success"

def test_get_app_settings():
    settings = get_app_settings()
    assert "Development" in settings