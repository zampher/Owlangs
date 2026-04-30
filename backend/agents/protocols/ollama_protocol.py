# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Ollama protocol adapter for local LLM deployment.

Ollama API is designed for running open-source models locally.
No API key required, different request/response format from OpenAI.
"""

import logging
from typing import Dict, Any, Tuple, List, Optional

from .base import LLMProtocol

logger = logging.getLogger(__name__)


class OllamaProtocol(LLMProtocol):
    """
    Ollama API protocol adapter.
    
    API Format:
        POST /api/chat
        {
            "model": "llama3",
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."}
            ],
            "options": {
                "temperature": 0.7,
                "num_predict": 4096
            },
            "stream": false
        }
    
    Note: Ollama uses 'num_predict' instead of 'max_tokens'
          and puts parameters under 'options' key.
    """
    
    @property
    def protocol_name(self) -> str:
        return "ollama"
    
    def get_chat_endpoint(self, base_url: str) -> str:
        """Get Ollama chat endpoint."""
        base = base_url.rstrip('/')
        return f"{base}/api/chat"
    
    def prepare_request(
        self,
        base_url: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        api_key: Optional[str],
        system_prompt: Optional[str] = None,
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        Prepare Ollama-compatible request.
        
        Args:
            base_url: Ollama server URL (e.g., http://localhost:11434)
            model: Model name (e.g., 'llama3', 'qwen', 'mistral')
            messages: List of messages
            temperature: Sampling temperature
            max_tokens: Max tokens (mapped to num_predict)
            api_key: Not used (Ollama doesn't require auth)
            system_prompt: System prompt
        """
        # Ollama doesn't require authentication
        headers = {
            "Content-Type": "application/json",
        }
        
        # Prepare messages
        request_messages = []
        
        # Add system prompt if provided
        if system_prompt:
            request_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        # Add user messages
        request_messages.extend(messages)
        
        # Prepare request body
        data: Dict[str, Any] = {
            "model": model,
            "messages": request_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        
        # Ollama uses 'num_predict' instead of 'max_tokens'
        # Set minimum num_predict to 4096 for thinking-capable models (e.g., Qwen3)
        # These models use significant tokens for reasoning before outputting content
        MIN_NUM_PREDICT = 4096
        if max_tokens is not None and max_tokens > 0:
            data["options"]["num_predict"] = max(max_tokens, MIN_NUM_PREDICT)
        else:
            data["options"]["num_predict"] = MIN_NUM_PREDICT
        
        return headers, data
    
    def parse_response(self, response_data: Dict[str, Any]) -> Tuple[str, str, int, int]:
        """
        Parse Ollama response.
        
        Response format:
        {
            "model": "llama3",
            "message": {
                "role": "assistant",
                "content": "...",
                "thinking": "..."  # Some models (e.g., Qwen3) may include thinking
            },
            "done": true,
            "done_reason": "stop",
            "prompt_eval_count": 100,
            "eval_count": 50
        }
        """
        # Check for Ollama error responses first (e.g., {"error": "model 'xxx' not found"})
        # Ollama returns HTTP 200 with error body when model is missing
        if "error" in response_data:
            error_msg = response_data["error"]
            raise ValueError(f"Ollama API error: {error_msg}")
        
        # Validate response structure
        if "message" not in response_data:
            raise ValueError(f"Invalid Ollama response: missing 'message'. Response: {response_data}")
        
        message = response_data["message"]
        content = message.get("content", "")
        
        # Handle models that return empty content but have thinking (e.g., Qwen3)
        # If content is empty but thinking is present, use thinking as content
        if not content or content.strip() == "":
            thinking = message.get("thinking", "")
            if thinking and thinking.strip():
                logger.warning(
                    f"[OLLAMA] Model returned empty content but has thinking. "
                    f"Finish reason: {response_data.get('done_reason', 'unknown')}. "
                    f"Using thinking content as fallback (may contain reasoning text)."
                )
                content = thinking.strip()
        
        # Extract finish reason
        # Ollama uses 'done_reason' field
        finish_reason = response_data.get("done_reason", "unknown")
        if not finish_reason or finish_reason == "":
            # Fallback: if done is true but no reason, assume stop
            if response_data.get("done", False):
                finish_reason = "stop"
        
        # Extract token usage
        # Ollama uses 'prompt_eval_count' and 'eval_count'
        input_tokens = response_data.get("prompt_eval_count", 0)
        output_tokens = response_data.get("eval_count", 0)
        
        return content, finish_reason, input_tokens, output_tokens
    
    def extract_usage_tokens(self, response_data: Dict[str, Any]) -> Tuple[int, int]:
        """Extract token usage from Ollama response."""
        input_tokens = response_data.get("prompt_eval_count", 0)
        output_tokens = response_data.get("eval_count", 0)
        return input_tokens, output_tokens
    
    def requires_auth(self) -> bool:
        """Ollama doesn't require authentication."""
        return False
