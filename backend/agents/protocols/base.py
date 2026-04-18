# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Base protocol interface and factory for LLM adapters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List, Optional, Type


class LLMProtocol(ABC):
    """
    Abstract base class for LLM protocol adapters.
    
    Each protocol implementation must handle:
    - Endpoint URL construction
    - Request headers and body preparation
    - Response parsing
    - Authentication requirements
    """
    
    @property
    @abstractmethod
    def protocol_name(self) -> str:
        """Return the protocol identifier name."""
        pass
    
    @abstractmethod
    def get_chat_endpoint(self, base_url: str) -> str:
        """
        Get the chat completion endpoint URL.
        
        Args:
            base_url: The base URL of the API
            
        Returns:
            Full URL for chat completions endpoint
        """
        pass
    
    @abstractmethod
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
        Prepare request headers and body.
        
        Args:
            base_url: The base URL of the API
            model: Model identifier
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response (None for default)
            api_key: API key for authentication (None if not required)
            system_prompt: Optional system-level instruction
            
        Returns:
            Tuple of (headers, request_body)
        """
        pass
    
    @abstractmethod
    def parse_response(self, response_data: Dict[str, Any]) -> Tuple[str, str, int, int]:
        """
        Parse API response.
        
        Args:
            response_data: Raw JSON response from API
            
        Returns:
            Tuple of (content, finish_reason, input_tokens, output_tokens)
            - content: The generated text content
            - finish_reason: Why generation stopped (e.g., 'stop', 'length')
            - input_tokens: Number of input tokens used
            - output_tokens: Number of output tokens used
        """
        pass
    
    @abstractmethod
    def requires_auth(self) -> bool:
        """
        Check if this protocol requires authentication.
        
        Returns:
            True if API key is required, False otherwise
        """
        pass
    
    def extract_usage_tokens(self, response_data: Dict[str, Any]) -> Tuple[int, int]:
        """
        Extract token usage from response. Override if format differs.
        
        Args:
            response_data: Raw JSON response
            
        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        usage = response_data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return input_tokens, output_tokens


class ProtocolFactory:
    """
    Factory for creating protocol adapters.
    
    Usage:
        protocol = ProtocolFactory.get_protocol("openai")
        protocol = ProtocolFactory.get_protocol("anthropic")
    """
    
    _protocols: Dict[str, Type[LLMProtocol]] = {}
    
    @classmethod
    def register(cls, protocol_name: str, protocol_class: Type[LLMProtocol]) -> None:
        """
        Register a protocol adapter.
        
        Args:
            protocol_name: Protocol identifier (lowercase)
            protocol_class: Protocol adapter class
        """
        cls._protocols[protocol_name.lower()] = protocol_class
    
    @classmethod
    def get_protocol(cls, protocol_name: str) -> LLMProtocol:
        """
        Get a protocol adapter instance.
        
        Args:
            protocol_name: Protocol identifier (e.g., 'openai', 'anthropic')
            
        Returns:
            Protocol adapter instance
            
        Raises:
            ValueError: If protocol is not registered
        """
        protocol_class = cls._protocols.get(protocol_name.lower())
        if not protocol_class:
            available = ", ".join(cls.list_protocols())
            raise ValueError(
                f"Unsupported protocol: '{protocol_name}'. "
                f"Available protocols: {available}"
            )
        return protocol_class()
    
    @classmethod
    def list_protocols(cls) -> List[str]:
        """
        List all registered protocol names.
        
        Returns:
            List of protocol identifiers
        """
        return list(cls._protocols.keys())
    
    @classmethod
    def is_supported(cls, protocol_name: str) -> bool:
        """
        Check if a protocol is supported.
        
        Args:
            protocol_name: Protocol identifier
            
        Returns:
            True if protocol is registered
        """
        return protocol_name.lower() in cls._protocols
