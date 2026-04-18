# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Anthropic Claude protocol adapter.

Anthropic API has unique features:
- Separate 'system' parameter (not in messages array)
- 200K token context window
- Different response format
- Uses 'x-api-key' header instead of Bearer token
"""

from typing import Dict, Any, Tuple, List, Optional

from .base import LLMProtocol


class AnthropicProtocol(LLMProtocol):
    """
    Anthropic Claude API protocol adapter.
    
    API Format:
        POST /v1/messages
        {
            "model": "claude-3-5-sonnet-20241022",
            "system": "You are a helpful assistant.",  // Separate from messages
            "messages": [
                {"role": "user", "content": "..."}
            ],
            "max_tokens": 4096,
            "temperature": 0.7
        }
    
    Authentication:
        Uses 'x-api-key' header instead of 'Authorization: Bearer'
    
    Key Differences from OpenAI:
        1. System prompt is a top-level parameter, not in messages
        2. Response format: content[0].text instead of choices[0].message.content
        3. Header: 'x-api-key' instead of 'Authorization: Bearer'
        4. Stop reason field name differs
    """
    
    @property
    def protocol_name(self) -> str:
        return "anthropic"
    
    def get_chat_endpoint(self, base_url: str) -> str:
        """Get Anthropic messages endpoint."""
        base = base_url.rstrip('/')
        # Anthropic API version is v1
        if '/v1' in base:
            return f"{base}/messages"
        return f"{base}/v1/messages"
    
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
        Prepare Anthropic-compatible request.
        
        Args:
            base_url: Anthropic API base URL
            model: Claude model (e.g., 'claude-3-5-sonnet-20241022')
            messages: List of messages (user/assistant roles only)
            temperature: Sampling temperature
            max_tokens: Max response tokens (required for Anthropic)
            api_key: API key for x-api-key header
            system_prompt: System prompt (goes in separate 'system' field)
        """
        # Anthropic uses 'x-api-key' header
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",  # API version
        }
        
        if api_key:
            headers["x-api-key"] = api_key
        
        # Filter messages - Anthropic only supports 'user' and 'assistant' roles
        # System messages should be extracted and put in 'system' field
        filtered_messages = []
        extracted_system = system_prompt
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "system":
                # If multiple system messages, concatenate them
                if extracted_system:
                    extracted_system = f"{extracted_system}\n\n{content}"
                else:
                    extracted_system = content
            elif role in ("user", "assistant"):
                filtered_messages.append({
                    "role": role,
                    "content": content,
                })
            # Skip other roles
        
        # Prepare request body
        data: Dict[str, Any] = {
            "model": model,
            "messages": filtered_messages,
            "temperature": temperature,
            # Anthropic requires max_tokens
            "max_tokens": max_tokens if max_tokens and max_tokens > 0 else 4096,
        }
        
        # Add system prompt if we have one
        if extracted_system:
            data["system"] = extracted_system
        
        return headers, data
    
    def parse_response(self, response_data: Dict[str, Any]) -> Tuple[str, str, int, int]:
        """
        Parse Anthropic response.
        
        Response format:
        {
            "id": "msg_...",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "..."
                }
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",  // Note: 'stop_reason' not 'finish_reason'
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50
            }
        }
        """
        # Validate response structure
        if "content" not in response_data:
            raise ValueError(f"Invalid Anthropic response: missing 'content'. Response: {response_data}")
        
        content_list = response_data["content"]
        if not content_list or not isinstance(content_list, list):
            raise ValueError(f"Invalid Anthropic response: 'content' is empty. Response: {response_data}")
        
        # Extract text from first content block
        first_block = content_list[0]
        if isinstance(first_block, dict):
            content = first_block.get("text", "")
        else:
            content = str(first_block)
        
        # Extract stop reason
        # Anthropic uses 'stop_reason' instead of 'finish_reason'
        stop_reason = response_data.get("stop_reason", "unknown")
        
        # Map Anthropic stop reasons to standard format
        reason_mapping = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
        }
        finish_reason = reason_mapping.get(stop_reason, stop_reason)
        
        # Extract token usage
        input_tokens, output_tokens = self.extract_usage_tokens(response_data)
        
        return content, finish_reason, input_tokens, output_tokens
    
    def extract_usage_tokens(self, response_data: Dict[str, Any]) -> Tuple[int, int]:
        """Extract token usage from Anthropic response."""
        usage = response_data.get("usage", {})
        
        # Anthropic uses 'input_tokens' and 'output_tokens'
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        
        return input_tokens, output_tokens
    
    def requires_auth(self) -> bool:
        """Anthropic API requires authentication."""
        return True
    
    def convert_stop_reason(self, anthropic_reason: str) -> str:
        """
        Convert Anthropic stop reason to standard format.
        
        Anthropic reasons:
            - end_turn: Natural stop
            - max_tokens: Hit token limit
            - stop_sequence: Hit custom stop sequence
        
        Standard reasons:
            - stop: Normal completion
            - length: Token limit reached
        """
        mapping = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
        }
        return mapping.get(anthropic_reason, anthropic_reason)
