import httpx

from agents.agent import Agent, AgentConfig


def test_ollama_endpoint_detection_and_headers():
    """
    Ensure that Agent detects Ollama from base_url and uses /api/chat without Authorization header.
    """
    config = AgentConfig(
        base_url="http://localhost:11434",
        api_key=None,
        model_id="test-model",
    )
    agent = Agent(config)

    # Ollama detection
    assert agent.api_type == "ollama"

    # Request preparation
    headers, data = agent._prepare_request_data("hello", "system")
    assert "Authorization" not in headers
    assert data["model"] == "test-model"
    assert data["messages"][-1]["content"] == "hello"
    assert data.get("stream") is False

    # Endpoint resolution
    endpoint = agent._get_chat_endpoint()
    assert endpoint == "http://localhost:11434/api/chat"


def test_openai_style_endpoint_unchanged():
    """
    Ensure that non-Ollama platforms still use /chat/completions and Authorization header.
    """
    config = AgentConfig(
        base_url="https://api.deepseek.com/v1",
        api_key="sk-test",
        model_id="deepseek-chat",
    )
    agent = Agent(config)

    assert agent.api_type == "openai"

    headers, data = agent._prepare_request_data("hello", "system")
    assert headers.get("Authorization") == "Bearer sk-test"
    assert data["model"] == "deepseek-chat"

    endpoint = agent._get_chat_endpoint()
    assert endpoint == "https://api.deepseek.com/v1/chat/completions"

