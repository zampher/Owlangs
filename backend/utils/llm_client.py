from __future__ import annotations

"""
Lightweight, shared LLM client built on top of the existing Agent abstraction.

This module provides a minimal chat-style interface that other components
(translators, formula repair, future tools) can reuse without depending
directly on Agent internals.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from agents.agent import Agent, AgentConfig
from logger import unified_logger
from logger.logger import LogModule


@dataclass
class LLMMessage:
    role: str  # "system" | "user"
    content: str


@dataclass
class LLMConfig:
    base_url: str
    model_id: str
    api_key: Optional[str] = None
    temperature: float = 0.1
    concurrent: int = 1
    connect_timeout: int = 5
    timeout: int = 30
    thinking: str = "default"
    retry: int = 3
    max_tokens: Optional[int] = None
    api_type: str = "openai"
    platform_key: Optional[str] = None


def llm_chat(messages: List[LLMMessage], config: LLMConfig) -> str:
    """
    Send a single-turn chat completion request and return assistant text.

    This is deliberately simple:
    - Only supports a single user/system exchange (no streaming, no tools)
    - Uses the existing Agent class for HTTP, retry and platform quirks
    """
    if not messages:
        raise ValueError("llm_chat requires at least one message")

    # Build system + user prompts from messages
    system_prompt_parts: List[str] = []
    user_prompt_parts: List[str] = []
    for m in messages:
        if m.role == "system":
            system_prompt_parts.append(m.content)
        elif m.role == "user":
            user_prompt_parts.append(m.content)
        else:
            # Ignore assistant/other roles for this simple interface
            continue

    system_prompt = "\n".join(p for p in system_prompt_parts if p).strip()
    user_prompt = "\n".join(p for p in user_prompt_parts if p).strip()
    if not user_prompt:
        raise ValueError("llm_chat requires at least one 'user' message with content")

    agent_cfg = AgentConfig(
        logger=unified_logger,
        base_url=config.base_url,
        api_key=config.api_key,
        model_id=config.model_id,
        temperature=config.temperature,
        concurrent=max(config.concurrent, 1),
        connect_timeout=config.connect_timeout,
        timeout=config.timeout,
        thinking=config.thinking,  # type: ignore[arg-type]
        retry=config.retry,
        max_tokens=config.max_tokens,
        api_type=config.api_type,
    )
    agent = Agent(agent_cfg)

    with httpx.Client(trust_env=False, verify=False) as client:
        result = agent.send(
            client=client,
            prompt=user_prompt,
            system_prompt=system_prompt or None,
            retry=True,
        )

    if not isinstance(result, str):
        unified_logger.warning(
            LogModule.TRANS,
            "[LLM-CLIENT] Non-string result from Agent.send: type={t}, preview={preview}",
            t=type(result).__name__,
            preview=str(result)[:200],
        )
        return str(result)

    return result.strip()

