# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
OpenAI-compatible protocol adapter.

This is the industry standard API format used by:
- OpenAI (GPT-4, GPT-3.5)
- DeepSeek
- Qwen (DashScope)
- Doubao (VolcEngine)
- Together AI
- Groq
- Most cloud providers
"""

from typing import Dict, Any, Tuple, List, Optional

from .base import LLMProtocol


class OpenAIProtocol(LLMProtocol):
    """
    OpenAI-compatible API protocol adapter.
    
    API Format:
        POST /v1/chat/completions
        {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."}
            ],
            "temperature": 0.7,
            "max_tokens": 4096
        }
    """
    
    @property
    def protocol_name(self) -> str:
        return "openai"
    
    def get_chat_endpoint(self, base_url: str) -> str:
        """Get chat completions endpoint."""
        base = base_url.rstrip('/')
        # If base_url already ends with /v1, don't add it again
        if base.endswith('/v1'):
            return f"{base}/chat/completions"
        # VolcEngine Ark (Doubao) uses /api/v3/chat/completions, not /v1
        if 'ark.cn-beijing.volces.com' in base or base.endswith('/api/v3'):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"
    
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
        Prepare OpenAI-compatible request.
        
        Args:
            base_url: API base URL
            model: Model name (e.g., 'gpt-4', 'deepseek-chat')
            messages: List of messages
            temperature: Sampling temperature
            max_tokens: Max response tokens
            api_key: API key for Bearer auth
            system_prompt: System prompt (will be prepended to messages)
        """
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
        }
        
        # Add authorization if key provided
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Prepare request body
        request_messages = []
        
        # Add system prompt if provided
        if system_prompt:
            request_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        # Add user messages
        request_messages.extend(messages)
        
        data: Dict[str, Any] = {
            "model": model,
            "messages": request_messages,
            "temperature": temperature,
            "stream": False,
        }
        
        # Add max_tokens if specified
        if max_tokens is not None and max_tokens > 0:
            data["max_tokens"] = max_tokens
        
        return headers, data
    
    def parse_response(self, response_data: Dict[str, Any]) -> Tuple[str, str, int, int]:
        """
        Parse OpenAI-compatible response.
        
        Response format:
        {
            "choices": [{
                "message": {"content": "..."},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50
            }
        }
        """
        # Zhipu / BigModel and some gateways return HTTP 200 with a business error envelope
        # (code, msg, success) instead of OpenAI-shaped {choices: [...]}.
        if response_data.get("success") is False and "msg" in response_data:
            code = response_data.get("code", "unknown")
            msg = response_data.get("msg", "")
            raise ValueError(
                f"Upstream API error (provider envelope, not OpenAI chat shape): "
                f"code={code}, msg={msg!r}. Full response: {response_data}"
            )

        # Validate response structure
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError(f"Invalid OpenAI response: missing 'choices'. Response: {response_data}")
        
        choice = response_data["choices"][0]
        
        # Extract content. Providers may set "content": null; normalize to "".
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError(
                f"Invalid OpenAI response: missing 'message' object in choice. "
                f"Response: {response_data}"
            )

        content = message.get("content")
        # Key present with JSON null → .get default is skipped; normalize to "".
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)
        
        # Extract finish reason
        finish_reason = choice.get("finish_reason") or "unknown"
        
        # Extract token usage
        input_tokens, output_tokens = self.extract_usage_tokens(response_data)
        
        return content, finish_reason, input_tokens, output_tokens
    
    def extract_usage_tokens(self, response_data: Dict[str, Any]) -> Tuple[int, int]:
        """Extract token usage from OpenAI response."""
        usage = response_data.get("usage") if isinstance(response_data, dict) else None
        if not isinstance(usage, dict):
            return 0, 0
        
        # Standard OpenAI format
        input_tokens = usage.get("prompt_tokens", 0) or 0
        output_tokens = usage.get("completion_tokens", 0) or 0
        
        # Some providers use different field names
        if input_tokens == 0:
            input_tokens = usage.get("input_tokens", 0) or 0
        if output_tokens == 0:
            output_tokens = usage.get("output_tokens", 0) or 0
        
        return input_tokens, output_tokens
    
    def requires_auth(self) -> bool:
        """OpenAI API requires authentication."""
        return True
