# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
LLM Protocol Adapters

This module provides protocol adapters for different LLM API formats.
Supported protocols:
- openai: OpenAI-compatible API (industry standard)
- ollama: Ollama local API
- anthropic: Anthropic Claude API
"""

from .base import LLMProtocol, ProtocolFactory
from .openai_protocol import OpenAIProtocol
from .ollama_protocol import OllamaProtocol
from .anthropic_protocol import AnthropicProtocol

# Register protocol adapters
ProtocolFactory.register("openai", OpenAIProtocol)
ProtocolFactory.register("ollama", OllamaProtocol)
ProtocolFactory.register("anthropic", AnthropicProtocol)

__all__ = [
    'LLMProtocol',
    'ProtocolFactory',
    'OpenAIProtocol',
    'OllamaProtocol',
    'AnthropicProtocol',
]
