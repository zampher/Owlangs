# SPDX-FileCopyrightText: 2025 QinHan
# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import asyncio
import itertools
import logging
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal, Callable, Any, Optional
from urllib.parse import urlparse

import httpx

from global_values import USE_PROXY
from logger import unified_logger
from logger.logger import LogModule
from utils.utils import get_httpx_proxies
from .protocols import ProtocolFactory, LLMProtocol

MAX_REQUESTS_PER_ERROR = 15

ThinkingMode = Literal["enable", "disable", "default"]


class AgentResultError(ValueError):
    """A special exception used to indicate that the result was returned normally by AI, but the returned result has issues. This error is not counted in the total error count"""

    def __init__(self, message):
        super().__init__(message)


class PartialAgentResultError(ValueError):
    """A special exception used to indicate that the result is incomplete but contains partially successful data to trigger retry. This error is not counted in the total error count"""

    def __init__(self, message, partial_result: dict):
        super().__init__(message)
        self.partial_result = partial_result


@dataclass(kw_only=True)
class AgentConfig:
    logger: logging.Logger = unified_logger  # Keep for compatibility, but logs use unified_logger directly
    base_url: str
    api_key: str | None = None
    model_id: str
    temperature: float = 0.3
    concurrent: int = 30
    connect_timeout: int = 15  # HTTP connect timeout (seconds), configurable via app_config.translator_connect_timeout
    timeout: int = 120  # Unit (seconds), this value is the read value in httpx.TimeOut, not the total timeout time
    write_timeout: Optional[int] = None  # HTTP write timeout (seconds), configurable per platform; 0 or None → 300 fallback
    thinking: ThinkingMode = "default"
    retry: int = 5
    max_tokens: int | None = None  # Max tokens for API response (None means use platform default)
    api_type: str = "openai"


class TotalErrorCounter:
    def __init__(self, logger: logging.Logger, max_errors_count=10):
        self.lock = Lock()
        self.count = 0
        self.logger = logger
        self.max_errors_count = max_errors_count

    def add(self):
        with self.lock:
            self.count += 1
            if self.count > self.max_errors_count:
                unified_logger.info(LogModule.TRANS, f"Too many error responses")
            return self.reach_limit()

    def reach_limit(self):
        return self.count > self.max_errors_count


# Only used for counting in multi-threading
class PromptsCounter:
    def __init__(self, total: int, logger: logging.Logger, progress_callback=None):
        self.lock = Lock()
        self.count = 0
        self.total = total
        self.logger = logger
        self.progress_callback = progress_callback

    def add(self):
        with self.lock:
            self.count += 1
            progress_percent = int((self.count / self.total) * 100) if self.total > 0 else 0
            unified_logger.info(LogModule.TRANS, f"Multi-threading - Completed: {self.count}/{self.total} ({progress_percent}%)")
            
            # Call progress callback if provided
            if self.progress_callback:
                try:
                    self.progress_callback(self.count, self.total, progress_percent)
                except Exception as e:
                    unified_logger.warning(LogModule.TRANS, f"Progress callback failed: {e}")


def extract_token_info(response_data: dict) -> tuple[int, int, int, int]:
    """
    Extract token information from API response

    Supports multiple response formats:
    1. Format 1: usage.input_tokens_details.cached_tokens and usage.output_tokens_details.reasoning_tokens
    2. Format 2: usage.prompt_tokens_details.cached_tokens
    3. Format 3: usage.prompt_cache_hit_tokens and usage.completion_tokens_details.reasoning_tokens

    Args:
        response_data: API response data

    Returns:
        tuple: (input_tokens, cached_tokens, output_tokens, reasoning_tokens)
    """
    if "usage" not in response_data:
        return 0, 0, 0, 0

    usage = response_data["usage"]
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    # Initialize token detailed statistics
    cached_tokens = 0
    reasoning_tokens = 0

    # Try to get cached_tokens from different formats
    # Format 1: input_tokens_details.cached_tokens
    if (
            "input_tokens_details" in usage
            and "cached_tokens" in usage["input_tokens_details"]
    ):
        cached_tokens = usage["input_tokens_details"]["cached_tokens"]
    # Format 2: prompt_tokens_details.cached_tokens
    elif (
            "prompt_tokens_details" in usage
            and "cached_tokens" in usage["prompt_tokens_details"]
    ):
        cached_tokens = usage["prompt_tokens_details"]["cached_tokens"]
    # Format 3: prompt_cache_hit_tokens (directly under usage)
    elif "prompt_cache_hit_tokens" in usage:
        cached_tokens = usage["prompt_cache_hit_tokens"]

    # Try to get reasoning_tokens from different formats
    # Format 1: output_tokens_details.reasoning_tokens
    if (
            "output_tokens_details" in usage
            and "reasoning_tokens" in usage["output_tokens_details"]
    ):
        reasoning_tokens = usage["output_tokens_details"]["reasoning_tokens"]
    # Format 2: completion_tokens_details.reasoning_tokens
    elif (
            "completion_tokens_details" in usage
            and "reasoning_tokens" in usage["completion_tokens_details"]
    ):
        reasoning_tokens = usage["completion_tokens_details"]["reasoning_tokens"]

    return input_tokens, cached_tokens, output_tokens, reasoning_tokens


class TokenCounter:
    def __init__(self, logger: logging.Logger):
        self.lock = Lock()
        self.input_tokens = 0
        self.cached_tokens = 0
        self.output_tokens = 0
        self.reasoning_tokens = 0
        self.total_tokens = 0
        self.logger = logger

    def add(
            self,
            input_tokens: int,
            cached_tokens: int,
            output_tokens: int,
            reasoning_tokens: int,
    ):
        with self.lock:
            self.input_tokens += input_tokens
            self.cached_tokens += cached_tokens
            self.output_tokens += output_tokens
            self.reasoning_tokens += reasoning_tokens
            self.total_tokens += input_tokens + output_tokens
            # self.logger.debug(
            #     f"Token usage statistics - Input: {self.input_tokens}(including cached: {self.cached_tokens}), "
            #     f"Output: {self.output_tokens}(including reasoning: {self.reasoning_tokens}), Total: {self.total_tokens}"
            # )

    def get_stats(self):
        with self.lock:
            return {
                "input_tokens": self.input_tokens,
                "cached_tokens": self.cached_tokens,
                "output_tokens": self.output_tokens,
                "reasoning_tokens": self.reasoning_tokens,
                "total_tokens": self.total_tokens,
            }

    def reset(self):
        with self.lock:
            self.input_tokens = 0
            self.cached_tokens = 0
            self.output_tokens = 0
            self.reasoning_tokens = 0
            self.total_tokens = 0


PreSendHandlerType = Callable[[str, str], tuple[str, str]]
ResultHandlerType = Callable[[str, str, logging.Logger], Any]
ErrorResultHandlerType = Callable[[str, logging.Logger], Any]


class Agent:
    # Platform-specific max_tokens limits (API constraints)
    # These are hard limits enforced by the API, not configuration values
    _platform_max_tokens_limits = {
        "api.deepseek.com": 8192,  # DeepSeek API limit
        "deepseek": 8192,  # DeepSeek platform key
    }
    
    _think_factory = {
        "open.bigmodel.cn": ("thinking", {"type": "enabled"}, {"type": "disabled"}),
        "dashscope.aliyuncs.com": (
            "extra_body",
            {"enable_thinking": True},
            {"enable_thinking": False},
        ),
        "ark.cn-beijing.volces.com": (
            "thinking",
            {"type": "enabled"},
            {"type": "disabled"},
        ),
        "generativelanguage.googleapis.com": (
            "extra_body",
            {
                "google": {
                    "thinking_config": {"thinking_budget": -1, "include_thoughts": True}
                }
            },
            {
                "google": {
                    "thinking_config": {"thinking_budget": 0, "include_thoughts": False}
                }
            },
        ),
        "api.siliconflow.cn": ("enable_thinking", True, False),
    }
    
    def _get_platform_max_tokens_limit(self) -> int | None:
        """
        Get the maximum allowed max_tokens for the current platform.
        
        Returns:
            Maximum allowed max_tokens, or None if no limit is known
        """
        # Check by domain first (exact match)
        if self.domain in self._platform_max_tokens_limits:
            return self._platform_max_tokens_limits[self.domain]
        
        # Check by domain substring (for subdomains)
        domain_lower = self.domain.lower()
        for domain_key, limit in self._platform_max_tokens_limits.items():
            if isinstance(domain_key, str) and domain_key in domain_lower:
                return limit
        
        # Check by platform key (if we can determine it)
        try:
            from backend.app.services.platform import platform_service
            platform_key = platform_service.determine_platform_key(self.baseurl, self.model_id)
            if platform_key and platform_key in self._platform_max_tokens_limits:
                return self._platform_max_tokens_limits[platform_key]
        except Exception:
            pass
        
        return None

    def __init__(self, config: AgentConfig):

        self.baseurl = config.base_url.strip()
        if self.baseurl.endswith("/"):
            self.baseurl = self.baseurl[:-1]
        # Use TokenHub OpenAI-compatible endpoint when legacy Hunyuan hosts are configured
        # (hunyuan.tencentcloudapi.com requires TC3 headers; TokenHub uses Bearer + sk- keys)
        _tokenhub_openai_base = "https://tokenhub.tencentmaas.com/v1"
        if "hunyuan.tencentcloudapi.com" in self.baseurl or "api.hunyuan.cloud.tencent.com" in self.baseurl:
            self.baseurl = _tokenhub_openai_base
            unified_logger.debug(
                LogModule.TRANS,
                "[HUNYUAN] Using TokenHub OpenAI-compatible endpoint (tokenhub.tencentmaas.com/v1) "
                "instead of legacy Hunyuan host",
            )
        self.domain = urlparse(self.baseurl).netloc
        
        # Detect API type from config or infer from base_url patterns
        # Support both 'api_protocol' (new) and 'api_type' (legacy) field names
        _explicit_api_protocol = getattr(config, "api_protocol", None)
        _explicit_api_type = getattr(config, "api_type", None)
        api_type_value = _explicit_api_protocol or _explicit_api_type or "openai"
        self.api_type = api_type_value.lower()
        
        # Initialize protocol adapter using factory
        try:
            # Map legacy api_type to new protocol names
            protocol_name = self.api_type
            if protocol_name in ("claude", "anthropic"):
                protocol_name = "anthropic"
            elif protocol_name == "openai":
                # Auto-detect Ollama only when the user did NOT explicitly set api_protocol/api_type.
                # If the user explicitly chose "openai" (e.g. Ollama with OpenAI-compatible API),
                # respect that choice instead of overriding to native Ollama protocol.
                if not _explicit_api_protocol and not _explicit_api_type:
                    baseurl_lower = self.baseurl.lower()
                    if ":11434" in baseurl_lower or "ollama" in baseurl_lower or "/api/chat" in baseurl_lower:
                        protocol_name = "ollama"
                        self.api_type = "ollama"
                        # Determine which pattern matched for logging
                        matched_patterns = []
                        if ":11434" in baseurl_lower:
                            matched_patterns.append("port:11434")
                        if "ollama" in baseurl_lower:
                            matched_patterns.append("hostname:ollama")
                        if "/api/chat" in baseurl_lower:
                            matched_patterns.append("path:/api/chat")
                        unified_logger.info(
                            LogModule.TRANS,
                            f"[OLLAMA DETECT] Auto-detected Ollama from base_url='{self.baseurl}', "
                            f"matched patterns: {', '.join(matched_patterns)}"
                        )
            
            # Use protocol factory
            if ProtocolFactory.is_supported(protocol_name):
                self._protocol = ProtocolFactory.get_protocol(protocol_name)
                unified_logger.debug(
                    LogModule.TRANS,
                    f"[PROTOCOL] Using {self._protocol.protocol_name} adapter for {self.baseurl}"
                )
            else:
                # Fallback to openai if protocol not recognized
                unified_logger.warning(
                    LogModule.TRANS,
                    f"[PROTOCOL] Unknown protocol '{protocol_name}', falling back to openai"
                )
                self._protocol = ProtocolFactory.get_protocol("openai")
                
        except Exception as e:
            unified_logger.error(
                LogModule.TRANS,
                f"[PROTOCOL] Failed to initialize protocol adapter: {e}, falling back to openai"
            )
            self._protocol = ProtocolFactory.get_protocol("openai")

        # Resolve API key using latest backend secrets configuration whenever a new Agent is created.
        # This ensures that updates to platform API keys (via settings UI or direct file edits)
        # take effect for new translation / retry requests without needing to recreate flows.
        resolved_key: str | None = None
        try:
            platform_key = getattr(config, "platform_key", None)
            if not platform_key:
                # Infer platform key from base_url + model_id when possible
                try:
                    from backend.app.services.platform import platform_service

                    platform_key = platform_service.determine_platform_key(
                        self.baseurl,
                        config.model_id,
                    )
                except Exception:
                    platform_key = None

            if platform_key:
                try:
                    from backend.config.config_loader import get_unified_config

                    unified_config = get_unified_config()
                    backend_key = unified_config.get_platform_api_key(platform_key)
                    if backend_key:
                        resolved_key = backend_key.strip()
                        unified_logger.debug(
                            LogModule.TRANS,
                            f"[API_KEY_RESOLVE] Using API key from secrets for platform={platform_key}",
                        )
                except Exception as e:
                    unified_logger.warning(
                        LogModule.TRANS,
                        f"[API_KEY_RESOLVE] Failed to resolve API key from unified config for platform={platform_key}: {e}",
                    )
        except Exception:
            # Fallback to config.api_key below
            pass

        # Fallback: use config.api_key when no backend-managed key is available.
        # This keeps custom / local endpoints (e.g. Ollama) working as before.
        if not resolved_key and config.api_key:
            resolved_key = config.api_key.strip()

        self.key = resolved_key if resolved_key else "xx"
        self.model_id = config.model_id.strip()
        self.system_prompt = ""
        self.temperature = config.temperature
        self.max_concurrent = config.concurrent
        connect_timeout = getattr(config, 'connect_timeout', 15)
        write_timeout_val = getattr(config, 'write_timeout', None)
        write_timeout = 300 if (write_timeout_val is None or write_timeout_val == 0) else write_timeout_val
        self.timeout = httpx.Timeout(connect=connect_timeout, read=config.timeout, write=write_timeout, pool=10)
        self.thinking = config.thinking
        self.logger = config.logger
        # Log timeout configuration (DEBUG level to reduce verbosity for retranslation)
        unified_logger.debug(
            LogModule.TRANS,
            f"[TIMEOUT_CONFIG] Timeout settings: connect={connect_timeout}s, read={config.timeout}s, write={write_timeout}s, pool=10s, concurrent={config.concurrent}"
        )
        self.total_error_counter = TotalErrorCounter(logger=self.logger)
        # New: for counting final unresolved errors
        self.unresolved_error_lock = Lock()
        self.unresolved_error_count = 0
        # Optional: task_id and task_state for updating task status on errors
        self.task_id = None
        self.task_state = None
        # New: for counting token usage
        self.token_counter = TokenCounter(logger=self.logger)

        self.retry = config.retry
        self.max_tokens = config.max_tokens

    def _update_task_state_for_http_error(self, status_code: int, response_text: str) -> None:
        """
        Update task state message for critical HTTP errors (e.g., insufficient balance, 404).
        This ensures users see the actual LLM platform error instead of a generic message.
        """
        if not self.task_id or not self.task_state:
            return
        
        response_lower = response_text.lower() if response_text else ""
        
        # Detect payment/balance/auth related errors and common configuration errors
        is_critical_error = False
        error_message = None
        
        if status_code == 402:
            is_critical_error = True
            error_message = "Insufficient balance on LLM platform. Please check your account and add funds."
        elif status_code == 429:
            # Check for balance-related 429 errors (common on some platforms like Zhipu)
            if any(keyword in response_lower for keyword in ["余额不足", "insufficient balance", "无可用资源包", "quota exceeded"]):
                is_critical_error = True
                error_message = "Insufficient balance or quota exceeded on LLM platform. Please check your account and add funds."
        elif status_code == 401:
            if any(keyword in response_lower for keyword in ["invalid api key", "authentication", "词元密钥已过期", "验证不正确"]):
                is_critical_error = True
                error_message = "Invalid API key or authentication failed. Please check your API key in Settings."
        elif status_code == 404:
            is_critical_error = True
            error_message = f"Model or API endpoint not found (HTTP 404). Please check the Base URL and Model ID in platform settings. Response: {response_text[:200]}"
        
        if is_critical_error and error_message:
            try:
                from backend.app.services.task import task_manager
                current_message = self.task_state.get("message", "")
                # Only update if message doesn't already contain this specific error
                if error_message not in current_message:
                    self.task_state["message"] = f"Translation failed: {error_message}"
                    self.task_state["llm_error"] = error_message
                    task_manager.add_log(
                        self.task_id,
                        "error",
                        f"LLM platform error (HTTP {status_code}): {response_text[:200]}"
                    )
            except Exception as update_error:
                unified_logger.warning(
                    LogModule.TRANS,
                    f"Failed to update task state for HTTP error: {update_error}"
                )

    def _get_chat_endpoint(self) -> str:
        """
        Get chat completion endpoint using protocol adapter.
        
        Falls back to legacy logic if protocol adapter not available.
        """
        # Use protocol adapter if available
        if hasattr(self, '_protocol') and self._protocol:
            return self._protocol.get_chat_endpoint(self.baseurl)
        
        # Legacy fallback
        if self.api_type == "ollama":
            return f"{self.baseurl}/api/chat"
        return f"{self.baseurl}/chat/completions"

    def _add_thinking_mode(self, data: dict):
        if self.domain not in self._think_factory:
            return
        field_thinking, val_enable, val_disable = self._think_factory[self.domain]
        if self.thinking == "enable":
            data[field_thinking] = val_enable
        elif self.thinking == "disable":
            data[field_thinking] = val_disable

    def _apply_ollama_thinking(self, data: dict[str, Any]) -> None:
        """Map Agent thinking mode to Ollama native `think` parameter (Qwen3, DeepSeek-R1, etc.)."""
        if self.thinking == "enable":
            data["think"] = True
        elif self.thinking == "disable":
            data["think"] = False

    def _prepare_request_data(
            self, prompt: str, system_prompt: str, temperature=None, top_p=0.9
    ):
        if temperature is None:
            temperature = self.temperature
        
        # Use protocol adapter if available
        if hasattr(self, '_protocol') and self._protocol:
            messages = [{"role": "user", "content": prompt}]
            
            # Get API key (handle placeholder)
            api_key = self.key if self.key != "xx" else None
            
            headers, data = self._protocol.prepare_request(
                base_url=self.baseurl,
                model=self.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
                system_prompt=system_prompt,
                **({"thinking": self.thinking} if self.api_type == "ollama" else {}),
            )
            
            # Add top_p for OpenAI-compatible protocols
            if self.api_type not in ("ollama", "anthropic") and top_p is not None:
                data["top_p"] = top_p

            if self.api_type != "ollama" and self.thinking != "default":
                self._add_thinking_mode(data)

            return headers, data
        
        # Legacy fallback logic
        headers = {
            "Content-Type": "application/json",
        }
        # For non-Ollama platforms, always send Authorization header when key is not placeholder
        if self.api_type != "ollama" and self.key and self.key != "xx":
            headers["Authorization"] = f"Bearer {self.key}"

        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self.api_type == "ollama":
            # Ollama chat API format
            data = {
                "model": self.model_id,
                "messages": messages,
                "stream": False,
            }
            options: dict[str, Any] = {}
            if temperature is not None:
                options["temperature"] = temperature
            # Ollama uses num_predict instead of max_tokens
            if self.max_tokens is not None and self.max_tokens > 0:
                options["num_predict"] = self.max_tokens
            if options:
                data["options"] = options
            self._apply_ollama_thinking(data)
        else:
            # OpenAI-compatible chat completions format
            data = {
                "model": self.model_id,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
            }
        
        # Estimate actual input tokens and log warning if exceeds reasonable limit
        try:
            from utils.token_estimator import estimate_chunk_input_tokens
            estimated_input_tokens = estimate_chunk_input_tokens(
                prompt, 
                system_prompt=system_prompt,
                system_prompt_approx=None  # Use actual system_prompt for accurate estimation
            )
            # Log token estimation for debugging
            unified_logger.debug(
                LogModule.TRANS,
                f"[TOKEN_CHECK] Estimated input tokens: {estimated_input_tokens} "
                f"(prompt: {len(prompt)} chars, system: {len(system_prompt) if system_prompt else 0} chars)"
            )
            # Warn if input tokens exceed 8000 (common context window minimum)
            # This helps identify token calculation issues
            if estimated_input_tokens > 8000:
                unified_logger.warning(
                    LogModule.TRANS,
                    f"[TOKEN_CHECK] Estimated input tokens ({estimated_input_tokens}) exceeds 8000. "
                    f"This may cause API errors. Prompt length: {len(prompt)}, System prompt length: {len(system_prompt) if system_prompt else 0}"
                )
            # For small chunk sizes, also warn if estimated tokens significantly exceed chunk_size
            # This helps catch token calculation inaccuracies
            if hasattr(self, 'chunk_size') and self.chunk_size and estimated_input_tokens > self.chunk_size * 1.2:
                unified_logger.warning(
                    LogModule.TRANS,
                    f"[TOKEN_CHECK] Estimated input tokens ({estimated_input_tokens}) significantly exceeds "
                    f"chunk_size ({self.chunk_size}). This may indicate token calculation inaccuracy. "
                    f"Prompt: {len(prompt)} chars, System: {len(system_prompt) if system_prompt else 0} chars"
                )
        except Exception as e:
            unified_logger.debug(
                LogModule.TRANS, f"[TOKEN_CHECK] Failed to estimate input tokens: {e}"
            )
        
        # Add max_tokens if configured (prevents response truncation)
        # Validate against platform-specific API limits (OpenAI-compatible only)
        if self.api_type != "ollama":
            if self.max_tokens is not None:
                platform_limit = self._get_platform_max_tokens_limit()
                if platform_limit is not None and self.max_tokens > platform_limit:
                    unified_logger.warning(
                        LogModule.TRANS,
                        f"[MAX_TOKENS] Clamping max_tokens from {self.max_tokens} to {platform_limit} "
                        f"(platform limit for {self.domain})"
                    )
                    data["max_tokens"] = platform_limit
                else:
                    data["max_tokens"] = self.max_tokens
            if self.thinking != "default":
                self._add_thinking_mode(data)
        return headers, data

    def _write_llm_call_debug(
        self,
        chunk_index: int,
        system_prompt: str | None,
        user_prompt: str,
        raw_response: str,
    ) -> None:
        """Write one debug file per LLM call (request + raw response) under temp for troubleshooting.
        
        Uses append mode so that multiple calls with the same chunk_index (e.g. main body + textbox)
        are all preserved in the same file instead of overwriting each other.
        """
        task_id = getattr(self, "task_id", None) or getattr(self, "_task_id", None)
        if not task_id:
            return
        try:
            tmp_dir = Path(tempfile.gettempdir()) / "owlangs_llm_api_debug"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            path = tmp_dir / f"{task_id}_llm_chunk_{chunk_index}.txt"
            
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            
            lines = [
                f"\n{'='*80}",
                f"CALL TIMESTAMP: {timestamp}",
                f"Task ID: {task_id}",
                f"Chunk index: {chunk_index}",
                "--- System prompt (full) ---",
                system_prompt if system_prompt else "(none)",
                "--- User prompt / request body (full) ---",
                user_prompt,
                "--- Raw LLM response content (full) ---",
                raw_response if raw_response else "(empty)",
                f"{'='*80}\n",
            ]
            # Append instead of overwrite so multiple stages (main body, textbox, etc.) are preserved
            with path.open("a", encoding="utf-8", errors="replace") as f:
                f.write("\n".join(lines))
            unified_logger.debug(
                LogModule.TRANS,
                f"[AGENT] Wrote/appended LLM call debug file: {path}",
            )
        except Exception as e:
            unified_logger.debug(
                LogModule.TRANS,
                f"[AGENT] Failed to write LLM call debug file: {e}",
            )

    async def send_async(
            self,
            client: httpx.AsyncClient,
            prompt: str,
            system_prompt: None | str = None,
            retry=True,
            retry_count=0,
            pre_send_handler: PreSendHandlerType = None,
            result_handler: ResultHandlerType = None,
            error_result_handler: ErrorResultHandlerType = None,
            best_partial_result: dict | None = None,
            chunk_index: int | None = None,
    ) -> Any:
        if system_prompt is None:
            system_prompt = self.system_prompt
        
        # Log system prompt and prompt preview for debugging translation issues (async version)
        if chunk_index is not None and chunk_index < 3:  # Only log first 3 chunks to avoid spam
            from logger.logger import format_content_for_log
            unified_logger.debug(
                LogModule.TRANS,
                f"[AGENT-ASYNC] Chunk #{chunk_index} - System prompt length: {len(system_prompt) if system_prompt else 0}, "
                f"System prompt preview: {format_content_for_log(system_prompt or 'None', max_length=200)}"
            )
            unified_logger.debug(
                LogModule.TRANS,
                f"[AGENT-ASYNC] Chunk #{chunk_index} - Prompt length: {len(prompt)}, "
                f"Prompt preview: {format_content_for_log(prompt, max_length=200)}"
            )
        
        if pre_send_handler:
            system_prompt, prompt = pre_send_handler(system_prompt, prompt)
            # Log after pre_send_handler (may modify system_prompt, e.g., add glossary)
            if chunk_index is not None and chunk_index < 3:
                unified_logger.debug(
                    LogModule.TRANS,
                    f"[AGENT-ASYNC] Chunk #{chunk_index} - After pre_send_handler, system prompt length: {len(system_prompt) if system_prompt else 0}"
                )

        headers, data = self._prepare_request_data(prompt, system_prompt)
        should_retry = False
        is_hard_error = False  # New flag to distinguish whether it's a hard error
        current_partial_result = None
        input_tokens = 0
        output_tokens = 0

        endpoint = self._get_chat_endpoint()

        try:
            response = await client.post(
                endpoint,
                json=data,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response_data = response.json()
            
            # Parse response using protocol adapter if available
            if hasattr(self, '_protocol') and self._protocol:
                try:
                    result, finish_reason, input_tokens, output_tokens = self._protocol.parse_response(response_data)
                except ValueError as e:
                    raise ValueError(f"Protocol {self._protocol.protocol_name} failed to parse response: {e}")
            else:
                # Legacy response parsing
                if self.api_type == "ollama":
                    # Check for Ollama error responses first (e.g., {"error": "model 'xxx' not found"})
                    if "error" in response_data:
                        error_msg = response_data["error"]
                        raise ValueError(f"Ollama API error: {error_msg}")
                    if "message" not in response_data or "content" not in response_data.get("message", {}):
                        raise ValueError(f"Invalid Ollama API response format: {response_data}")
                    result = response_data["message"]["content"]
                    finish_reason = response_data.get("done_reason", "unknown")
                else:
                    if "choices" not in response_data or len(response_data["choices"]) == 0:
                        raise ValueError(f"Invalid API response: missing or empty 'choices' field. Response: {response_data}")
                    choice = response_data["choices"][0]
                    result = choice["message"]["content"]
                    finish_reason = choice.get("finish_reason", "unknown")
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            
            # Log detailed response info when result is suspiciously short or finish_reason indicates issues
            # Also log when finish_reason is 'length' (output truncated) to help diagnose partial translations
            if not result or len(result) < 10 or finish_reason not in ["stop", "length"] or finish_reason == "length":
                unified_logger.warning(
                    LogModule.TRANS,
                    f"{chunk_info}API response issue detected\n"
                    f"  API URL: {endpoint}\n"
                    f"  Model: {self.model_id}\n"
                    f"  Finish reason: {finish_reason}\n"
                    f"  Input tokens: {input_tokens}\n"
                    f"  Output tokens: {output_tokens}\n"
                    f"  Result length: {len(result) if result else 0}\n"
                    f"  Result preview: {str(result)[:500] if result else 'None'}\n"
                    f"  Full response_data (first 2000 chars): {str(response_data)[:2000]}"
                )
            
            if not result or not isinstance(result, str):
                unified_logger.warning(
                    LogModule.TRANS,
                    f"{chunk_info}AI returned empty or invalid result\n"
                    f"  API URL: {endpoint}\n"
                    f"  Model: {self.model_id}\n"
                    f"  Response type: {type(result).__name__}\n"
                    f"  Finish reason: {finish_reason}\n"
                    f"  Response preview: {str(result)[:200] if result else 'None'}\n"
                    f"  Full response_data (first 2000 chars): {str(response_data)[:2000]}"
                )
            
            # Note: Removed verbose response logs to reduce log verbosity
            # Only log errors and warnings for normal translation flow

            # Get token usage information (already extracted above)
            input_tokens, cached_tokens, output_tokens, reasoning_tokens = (
                extract_token_info(response_data)
            )

            # Update token counter
            self.token_counter.add(
                input_tokens, cached_tokens, output_tokens, reasoning_tokens
            )

            if retry_count > 0:
                chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                unified_logger.info(
                    LogModule.TRANS,
                    f"{chunk_info}Retry successful (attempt {retry_count}/{self.retry}).\n"
                    f"  API URL: {endpoint}\n"
                    f"  Model: {self.model_id}"
                )

            # Write LLM call debug file when task_id is set (e.g. MD translator) for troubleshooting single-segment returns
            task_id_for_debug = getattr(self, "task_id", None) or getattr(self, "_task_id", None)
            if task_id_for_debug and chunk_index is not None and result is not None:
                self._write_llm_call_debug(chunk_index, system_prompt, prompt, result)

            # print(f"result:=============================================================\n{result}\n================\n")
            return (
                result
                if result_handler is None
                else result_handler(result, prompt, self.logger)
            )

        except AgentResultError as e:
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            from logger.logger import format_content_for_log
            unified_logger.error(
                LogModule.TRANS,
                f"{chunk_info}AI returned incorrect result: {e}\n"
                f"  API URL: {endpoint}\n"
                f"  Model: {self.model_id}\n"
                f"  Prompt preview ({len(prompt)} chars): {format_content_for_log(prompt, max_length=100)}"
            )
            should_retry = True
        # Specifically catch partial translation errors (soft errors)
        except PartialAgentResultError as e:
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            unified_logger.warning(
                LogModule.TRANS,
                f"{chunk_info}Received partial result, will retry: {e}\n"
                f"  API URL: {endpoint}\n"
                f"  Model: {self.model_id}\n"
                f"  Partial result keys: {list(e.partial_result.keys()) if e.partial_result else 'None'}"
            )
            current_partial_result = e.partial_result
            should_retry = True
            # is_hard_error remains False

        # Catch hard errors
        except httpx.HTTPStatusError as e:
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            from logger.logger import format_content_for_log
            error_detail = {
                "chunk_index": chunk_index,
                "status_code": e.response.status_code,
                "response_text": e.response.text[:500] if e.response.text else None,
                "api_url": endpoint,
                "model_id": self.model_id,
                "retry_count": retry_count,
                "prompt_length": len(prompt),
                "prompt_preview": None,  # Will format using format_content_for_log
            }
            unified_logger.error(
                LogModule.TRANS,
                f"{chunk_info}AI request HTTP status error (async): {e.response.status_code}\n"
                f"  API URL: {error_detail['api_url']}\n"
                f"  Model: {error_detail['model_id']}\n"
                f"  Response: {error_detail['response_text']}\n"
                f"  Prompt preview ({error_detail['prompt_length']} chars): {format_content_for_log(prompt, max_length=100)}"
            )
            self._update_task_state_for_http_error(e.response.status_code, error_detail['response_text'])
            should_retry = True
            is_hard_error = True
        except httpx.RequestError as e:
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            from logger.logger import format_content_for_log
            error_detail = {
                "chunk_index": chunk_index,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "api_url": endpoint,
                "model_id": self.model_id,
                "retry_count": retry_count,
                "prompt_length": len(prompt),
                "prompt_preview": None,  # Will format using format_content_for_log
            }
            # Check if it's a timeout error
            is_timeout = "timeout" in str(e).lower() or "ReadTimeout" in error_detail['error_type']
            timeout_info = ""
            if is_timeout:
                timeout_info = f"\n  ⏱️  Timeout settings: connect=5s, read={self.timeout.read}s, write={self.timeout.write}s"
                # Update task state if available
                if self.task_id and self.task_state:
                    try:
                        from backend.app.services.task import task_manager
                        timeout_seconds = self.timeout.read
                        timeout_message = (
                            f"Translation timeout detected (current timeout: {timeout_seconds}s). "
                            f"If it happens frequently, please go to Settings -> Translation and increase the Timeout value "
                            f"(recommended: {max(timeout_seconds * 2, 60)}s or higher)."
                        )
                        # Only update message if it doesn't already contain timeout info (avoid overwriting)
                        current_message = self.task_state.get("message", "")
                        if "timeout" not in current_message.lower():
                            self.task_state["message"] = timeout_message
                            task_manager.add_log(
                                self.task_id,
                                "warning",
                                f"Translation timeout error (current timeout: {timeout_seconds}s). "
                                f"Please increase timeout in Settings -> Translation."
                            )
                    except Exception as update_error:
                        # Don't fail translation if status update fails
                        unified_logger.warning(
                            LogModule.TRANS, f"Failed to update task state for timeout error: {update_error}"
                        )
            
            unified_logger.error(
                LogModule.TRANS,
                f"{chunk_info}AI request connection error (async): {error_detail['error_type']}\n"
                f"  API URL: {error_detail['api_url']}\n"
                f"  Model: {error_detail['model_id']}\n"
                f"  Error: {error_detail['error_message']}{timeout_info}\n"
                f"  Prompt preview ({error_detail['prompt_length']} chars): {format_content_for_log(prompt, max_length=100)}"
            )
            should_retry = True
            is_hard_error = True
        except (KeyError, IndexError, ValueError) as e:
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            error_detail = {
                "chunk_index": chunk_index,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "api_url": endpoint,
                "model_id": self.model_id,
                "retry_count": retry_count,
            }
            unified_logger.error(
                LogModule.TRANS,
                f"{chunk_info}AI response format or value error (async): {error_detail['error_type']}\n"
                f"  API URL: {error_detail['api_url']}\n"
                f"  Model: {error_detail['model_id']}\n"
                f"  Error: {error_detail['error_message']}"
            )
            should_retry = True
            is_hard_error = True

        if current_partial_result:
            best_partial_result = current_partial_result

        if should_retry and retry and retry_count < self.retry:
            # Allow retries to proceed - error counting happens after all retries are exhausted
            # This ensures each chunk can use its full retry quota before being counted as an error
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            unified_logger.info(LogModule.TRANS, f"{chunk_info}Retrying attempt {retry_count + 1}/{self.retry}...")
            unified_logger.debug(
                LogModule.TRANS,
                f"{chunk_info}Retry details:\n"
                f"  API URL: {endpoint}\n"
                f"  Model: {self.model_id}\n"
                f"  Error type: {'Hard error' if is_hard_error else 'Soft error'}\n"
                f"  Previous attempt: {retry_count}\n"
                f"  Max retries: {self.retry}\n"
                f"  Has partial result: {best_partial_result is not None}\n"
                f"  Prompt length: {len(prompt)} chars\n"
                f"  Waiting 0.5s before retry..."
            )
            await asyncio.sleep(0.5)
            return await self.send_async(
                client,
                prompt,
                system_prompt,
                retry=True,
                retry_count=retry_count + 1,
                pre_send_handler=pre_send_handler,
                result_handler=result_handler,
                error_result_handler=error_result_handler,
                best_partial_result=best_partial_result,
                chunk_index=chunk_index,
            )
        else:
            if should_retry:
                chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                unified_logger.error(
                    LogModule.TRANS,
                    f"{chunk_info}All retries failed, reached retry limit ({self.retry} attempts).\n"
                    f"  API URL: {endpoint}\n"
                    f"  Model: {self.model_id}\n"
                    f"  Final prompt length: {len(prompt)} chars"
                )
                # Output full prompt content for debugging translation failures
                unified_logger.error(
                    LogModule.TRANS,
                    f"{chunk_info}=== FULL PROMPT CONTENT (Chunk #{chunk_index}) ===\n"
                    f"{prompt}\n"
                    f"{chunk_info}=== END OF PROMPT CONTENT ==="
                )
                # New: increase unresolved error count after all retries fail
                with self.unresolved_error_lock:
                    self.unresolved_error_count += 1
                
                # Increment total error counter only after all retries are exhausted
                # This allows each chunk to use its full retry quota (e.g., 5 retries)
                if is_hard_error:
                    error_count_after = self.total_error_counter.add()
                    if error_count_after:
                        chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                        unified_logger.warning(
                            LogModule.TRANS,
                            f"{chunk_info}Total error limit reached ({self.total_error_counter.count}/{self.total_error_counter.max_errors_count}). "
                            f"Subsequent chunks may skip retries."
                        )

            if best_partial_result:
                chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                unified_logger.info(
                    LogModule.TRANS,f"{chunk_info}All retries failed, but partial translation result exists, will use it.")
                # Log partial result content for debugging
                if best_partial_result:
                    sample_items = list(best_partial_result.items())[:5]
                    unified_logger.debug(
                        LogModule.TRANS,
                        f"{chunk_info}Using partial translation result (first 5 items): {dict(sample_items)}"
                    )
                return best_partial_result

            return (
                prompt
                if error_result_handler is None
                else error_result_handler(prompt, self.logger)
            )

    async def send_prompts_async(
            self,
            prompts: list[str],
            system_prompt: str | None = None,
            max_concurrent: int | None = None,
            pre_send_handler: PreSendHandlerType = None,
            result_handler: ResultHandlerType = None,
            error_result_handler: ErrorResultHandlerType = None,
            progress_callback=None,
    ) -> list[Any]:
        max_concurrent = (
            self.max_concurrent if max_concurrent is None else max_concurrent
        )
        total = len(prompts)
        # Reduce log verbosity: use DEBUG for single-segment retranslation, INFO for batch translation
        # Use unified_logger with (module, message) so it works whether self.logger is wrapped or raw
        if total == 1:
            unified_logger.debug(
                LogModule.TRANS,
                f"base-url:{self.baseurl},model-id:{self.model_id},concurrent:{max_concurrent},temperature:{self.temperature}"
            )
            unified_logger.debug(
                LogModule.TRANS,
                f"[TIMEOUT] Timeout settings: connect=5s, read={self.timeout.read}s, write={self.timeout.write}s, pool={self.timeout.pool}s"
            )
            unified_logger.debug(LogModule.TRANS, f"Planned to send {total} requests, concurrent requests: {max_concurrent}")
        else:
            unified_logger.info(
                LogModule.TRANS,
                f"base-url:{self.baseurl},model-id:{self.model_id},concurrent:{max_concurrent},temperature:{self.temperature}"
            )
            unified_logger.info(
                LogModule.TRANS,
                f"[TIMEOUT] Timeout settings: connect=5s, read={self.timeout.read}s, write={self.timeout.write}s, pool={self.timeout.pool}s"
            )
            unified_logger.info(LogModule.TRANS, f"Planned to send {total} requests, concurrent requests: {max_concurrent}")
        # Set max errors count: allow at least 1 error per chunk, but limit for very large batches
        # For small batches, this ensures retries can proceed
        max_errors = max(1, len(prompts) // MAX_REQUESTS_PER_ERROR)
        self.total_error_counter.max_errors_count = max_errors
        self.total_error_counter.count = 0  # Reset counter for new batch
        unified_logger.debug(
            LogModule.TRANS, f"Error counter limit set to {max_errors} for {len(prompts)} chunks (formula: max(1, {len(prompts)} // {MAX_REQUESTS_PER_ERROR}))"
        )

        # New: reset counter before each batch send
        self.unresolved_error_count = 0
        # Reset token counter
        self.token_counter.reset()

        count = 0
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = []

        proxies = get_httpx_proxies() if USE_PROXY else None

        limits = httpx.Limits(
            max_connections=self.max_concurrent * 2,  # Reserve space for retries and concurrency
            max_keepalive_connections=self.max_concurrent,  # Keep alive connections
        )

        async with httpx.AsyncClient(
                trust_env=False, proxy=proxies, verify=False, limits=limits
        ) as client:
            async def send_with_semaphore(p_text: str, idx: int):
                async with semaphore:
                    result = await self.send_async(
                        client=client,
                        prompt=p_text,
                        system_prompt=system_prompt,
                        pre_send_handler=pre_send_handler,
                        result_handler=result_handler,
                        error_result_handler=error_result_handler,
                        chunk_index=idx,
                    )
                    nonlocal count
                    count += 1
                    progress_percent = int((count / total) * 100) if total > 0 else 0
                    
                    # Only log DEBUG when progress actually changes (count or progress_percent)
                    # Use closure to track last logged progress
                    if not hasattr(send_with_semaphore, '_last_logged_progress'):
                        send_with_semaphore._last_logged_progress = {'count': -1, 'progress_percent': -1}
                    
                    if (count != send_with_semaphore._last_logged_progress['count'] or 
                        progress_percent != send_with_semaphore._last_logged_progress['progress_percent']):
                        # Log at INFO level only when progress_percent changes to avoid spamming
                        # the log with 500+ lines for large batches.
                        if progress_percent != send_with_semaphore._last_logged_progress['progress_percent']:
                            unified_logger.info(
                                LogModule.TRANS, f"Translation progress: {count}/{total} chunks ({progress_percent}%)"
                            )
                        else:
                            unified_logger.debug(
                                LogModule.TRANS, f"Translation progress: {count}/{total} chunks ({progress_percent}%)"
                            )
                        send_with_semaphore._last_logged_progress['count'] = count
                        send_with_semaphore._last_logged_progress['progress_percent'] = progress_percent
                    
                    # Call progress callback if provided
                    if progress_callback:
                        try:
                            progress_callback(count, total, progress_percent)
                        except Exception as e:
                            unified_logger.warning(LogModule.TRANS, f"Progress callback failed: {e}")
                    
                    return result

            # Log concurrent processing start
            unified_logger.debug(
                LogModule.TRANS, f"[CONCURRENT] Starting concurrent processing of {len(prompts)} chunks with max_concurrent={max_concurrent}"
            )

            # Notify start of batch processing so the caller knows total chunk count
            # before any individual chunk completes.
            if progress_callback:
                try:
                    progress_callback(0, total, 0)
                except Exception as e:
                    unified_logger.warning(LogModule.TRANS, f"Progress callback failed at start: {e}")

            for idx, p_text in enumerate(prompts):
                task = asyncio.create_task(send_with_semaphore(p_text, idx))
                tasks.append(task)
                unified_logger.debug(
                    LogModule.TRANS,f"[CONCURRENT] Created task for chunk #{idx}")

            results = await asyncio.gather(*tasks, return_exceptions=False)

            # Log concurrent processing completion
            unified_logger.debug(
                LogModule.TRANS, f"[CONCURRENT] Completed concurrent processing of {len(prompts)} chunks"
            )

            # New: print total unresolved errors after all tasks complete
            if self.unresolved_error_count > 0:
                unified_logger.warning(
                    LogModule.TRANS,
                    f"⚠️  Translation completed with {self.unresolved_error_count} unresolved errors "
                    f"({self.unresolved_error_count}/{total} chunks failed, {((self.unresolved_error_count/total)*100):.1f}% failure rate)"
                )
            else:
                unified_logger.info(
                    LogModule.TRANS,
                    f"✅ All requests processed successfully. Total unresolved errors: {self.unresolved_error_count}"
                )

            # New: print token usage statistics
            token_stats = self.token_counter.get_stats()
            unified_logger.info(
                LogModule.TRANS,
                f"Token usage statistics - Input: {token_stats['input_tokens'] / 1000:.2f}K(including cached: {token_stats['cached_tokens'] / 1000:.2f}K), "
                f"Output: {token_stats['output_tokens'] / 1000:.2f}K(including reasoning: {token_stats['reasoning_tokens'] / 1000:.2f}K), "
                f"Total: {token_stats['total_tokens'] / 1000:.2f}K"
            )

            return results

    def send(
            self,
            client: httpx.Client,
            prompt: str,
            system_prompt: None | str = None,
            retry=True,
            retry_count=0,
            pre_send_handler=None,
            result_handler=None,
            error_result_handler=None,
            best_partial_result: dict | None = None,
            chunk_index: int | None = None,
    ) -> Any:
        if system_prompt is None:
            system_prompt = self.system_prompt
        
        # Log system prompt and prompt preview for debugging translation issues
        if chunk_index is not None and chunk_index < 3:  # Only log first 3 chunks to avoid spam
            from logger.logger import format_content_for_log
            unified_logger.debug(
                LogModule.TRANS,
                f"[AGENT] Chunk #{chunk_index} - System prompt length: {len(system_prompt) if system_prompt else 0}, "
                f"System prompt preview: {format_content_for_log(system_prompt or 'None', max_length=200)}"
            )
            unified_logger.debug(
                LogModule.TRANS,
                f"[AGENT] Chunk #{chunk_index} - Prompt length: {len(prompt)}, "
                f"Prompt preview: {format_content_for_log(prompt, max_length=200)}"
            )

        if pre_send_handler:
            system_prompt, prompt = pre_send_handler(system_prompt, prompt)
            # Log after pre_send_handler (may modify system_prompt, e.g., add glossary)
            if chunk_index is not None and chunk_index < 3:
                unified_logger.debug(
                    LogModule.TRANS,
                    f"[AGENT] Chunk #{chunk_index} - After pre_send_handler, system prompt length: {len(system_prompt) if system_prompt else 0}"
                )

        headers, data = self._prepare_request_data(prompt, system_prompt)
        should_retry = False
        is_hard_error = False  # New flag to distinguish whether it's a hard error
        current_partial_result = None
        input_tokens = 0
        output_tokens = 0

        endpoint = self._get_chat_endpoint()

        try:
            response = client.post(
                endpoint,
                json=data,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response_data = response.json()
            
            # Parse response using protocol adapter if available
            if hasattr(self, '_protocol') and self._protocol:
                try:
                    result, finish_reason, input_tokens, output_tokens = self._protocol.parse_response(response_data)
                except ValueError as e:
                    raise ValueError(f"Protocol {self._protocol.protocol_name} failed to parse response: {e}")
            else:
                # Legacy response parsing
                if self.api_type == "ollama":
                    # Check for Ollama error responses first (e.g., {"error": "model 'xxx' not found"})
                    if "error" in response_data:
                        error_msg = response_data["error"]
                        raise ValueError(f"Ollama API error: {error_msg}")
                    if "message" not in response_data or "content" not in response_data.get("message", {}):
                        raise ValueError(f"Invalid Ollama API response format: {response_data}")
                    result = response_data["message"]["content"]
                else:
                    if "choices" not in response_data or len(response_data["choices"]) == 0:
                        raise ValueError(f"Invalid API response: missing or empty 'choices' field. Response: {response_data}")
                    result = response_data["choices"][0]["message"]["content"]
            
            if not result or not isinstance(result, str):
                chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                unified_logger.warning(
                    LogModule.TRANS,
                    f"{chunk_info}AI returned empty or invalid result\n"
                    f"  API URL: {endpoint}\n"
                    f"  Model: {self.model_id}\n"
                    f"  Response type: {type(result).__name__}\n"
                    f"  Response preview: {str(result)[:200] if result else 'None'}"
                )

            # Note: Removed verbose response logs to reduce log verbosity
            # Only log errors and warnings for normal translation flow

            # Get token usage information (already extracted above)
            input_tokens, cached_tokens, output_tokens, reasoning_tokens = (
                extract_token_info(response_data)
            )

            # Update token counter
            self.token_counter.add(
                input_tokens, cached_tokens, output_tokens, reasoning_tokens
            )

            if retry_count > 0:
                chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                unified_logger.info(
                    LogModule.TRANS,
                    f"{chunk_info}Retry successful (attempt {retry_count}/{self.retry}).\n"
                    f"  API URL: {endpoint}\n"
                    f"  Model: {self.model_id}"
                )

            return (
                result
                if result_handler is None
                else result_handler(result, prompt, self.logger)
            )
        except AgentResultError as e:
            unified_logger.error(LogModule.TRANS, f"AI returned incorrect result: {e}")
            should_retry = True
        # Specifically catch partial translation errors (soft errors)
        except PartialAgentResultError as e:
            unified_logger.error(LogModule.TRANS, f"Received partial translation result, will retry: {e}")
            # Log partial result content for debugging
            if e.partial_result:
                sample_items = list(e.partial_result.items())[:5]
                chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                unified_logger.debug(
                    LogModule.TRANS,
                    f"{chunk_info}Partial translation result (first 5 items): {dict(sample_items)}"
                )
            current_partial_result = e.partial_result
            should_retry = True
            # is_hard_error remains False

        # Catch hard errors
        except httpx.HTTPStatusError as e:
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            from logger.logger import format_content_for_log
            error_detail = {
                "chunk_index": chunk_index,
                "status_code": e.response.status_code,
                "response_text": e.response.text[:500] if e.response.text else None,
                "api_url": endpoint,
                "model_id": self.model_id,
                "retry_count": retry_count,
                "prompt_length": len(prompt),
                "prompt_preview": None,  # Will format using format_content_for_log
            }
            unified_logger.error(
                LogModule.TRANS,
                f"{chunk_info}AI request HTTP status error (sync): {e.response.status_code}\n"
                f"  API URL: {error_detail['api_url']}\n"
                f"  Model: {error_detail['model_id']}\n"
                f"  Response: {error_detail['response_text']}\n"
                f"  Prompt preview ({error_detail['prompt_length']} chars): {format_content_for_log(prompt, max_length=100)}"
            )
            self._update_task_state_for_http_error(e.response.status_code, error_detail['response_text'])
            should_retry = True
            is_hard_error = True
        except httpx.RequestError as e:
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            from logger.logger import format_content_for_log
            error_detail = {
                "chunk_index": chunk_index,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "api_url": endpoint,
                "model_id": self.model_id,
                "retry_count": retry_count,
                "prompt_length": len(prompt),
                "prompt_preview": None,  # Will format using format_content_for_log
            }
            unified_logger.error(
                LogModule.TRANS,
                f"{chunk_info}AI request connection error (sync): {error_detail['error_type']}\n"
                f"  API URL: {error_detail['api_url']}\n"
                f"  Model: {error_detail['model_id']}\n"
                f"  Error: {error_detail['error_message']}\n"
                f"  Prompt preview ({error_detail['prompt_length']} chars): {format_content_for_log(prompt, max_length=100)}"
            )
            should_retry = True
            is_hard_error = True
        except (KeyError, IndexError, ValueError) as e:
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            error_detail = {
                "chunk_index": chunk_index,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "api_url": endpoint,
                "model_id": self.model_id,
                "retry_count": retry_count,
            }
            unified_logger.error(
                LogModule.TRANS,
                f"{chunk_info}AI response format or value error (sync): {error_detail['error_type']}\n"
                f"  API URL: {error_detail['api_url']}\n"
                f"  Model: {error_detail['model_id']}\n"
                f"  Error: {error_detail['error_message']}"
            )
            should_retry = True
            is_hard_error = True

        if current_partial_result:
            best_partial_result = current_partial_result

        if should_retry and retry and retry_count < self.retry:
            # Allow retries to proceed - error counting happens after all retries are exhausted
            # This ensures each chunk can use its full retry quota before being counted as an error
            chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
            unified_logger.info(LogModule.TRANS, f"{chunk_info}Retrying attempt {retry_count + 1}/{self.retry}...")
            unified_logger.debug(
                LogModule.TRANS,
                f"{chunk_info}Retry details:\n"
                f"  API URL: {endpoint}\n"
                f"  Model: {self.model_id}\n"
                f"  Error type: {'Hard error' if is_hard_error else 'Soft error'}\n"
                f"  Previous attempt: {retry_count}\n"
                f"  Max retries: {self.retry}\n"
                f"  Has partial result: {best_partial_result is not None}\n"
                f"  Prompt length: {len(prompt)} chars\n"
                f"  Waiting 0.5s before retry..."
            )
            time.sleep(0.5)
            return self.send(
                client,
                prompt,
                system_prompt,
                retry=True,
                retry_count=retry_count + 1,
                pre_send_handler=pre_send_handler,
                result_handler=result_handler,
                error_result_handler=error_result_handler,
                best_partial_result=best_partial_result,
                chunk_index=chunk_index,
            )
        else:
            if should_retry:
                chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                unified_logger.error(
                    LogModule.TRANS,
                    f"{chunk_info}All retries failed, reached retry limit ({self.retry} attempts).\n"
                    f"  API URL: {endpoint}\n"
                    f"  Model: {self.model_id}\n"
                    f"  Final prompt length: {len(prompt)} chars"
                )
                # Output full prompt content for debugging translation failures
                unified_logger.error(
                    LogModule.TRANS,
                    f"{chunk_info}=== FULL PROMPT CONTENT (Chunk #{chunk_index}) ===\n"
                    f"{prompt}\n"
                    f"{chunk_info}=== END OF PROMPT CONTENT ==="
                )
                # New: increase unresolved error count after all retries fail
                with self.unresolved_error_lock:
                    self.unresolved_error_count += 1
                
                # Increment total error counter only after all retries are exhausted
                # This allows each chunk to use its full retry quota (e.g., 5 retries)
                if is_hard_error:
                    error_count_after = self.total_error_counter.add()
                    if error_count_after:
                        chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                        unified_logger.warning(
                            LogModule.TRANS,
                            f"{chunk_info}Total error limit reached ({self.total_error_counter.count}/{self.total_error_counter.max_errors_count}). "
                            f"Subsequent chunks may skip retries."
                        )

            if best_partial_result:
                chunk_info = f"[Chunk #{chunk_index}] " if chunk_index is not None else ""
                unified_logger.info(
                    LogModule.TRANS,f"{chunk_info}All retries failed, but partial translation result exists, will use it.")
                # Log partial result content for debugging
                if best_partial_result:
                    sample_items = list(best_partial_result.items())[:5]
                    unified_logger.debug(
                        LogModule.TRANS,
                        f"{chunk_info}Using partial translation result (first 5 items): {dict(sample_items)}"
                    )
                return best_partial_result

            return (
                prompt
                if error_result_handler is None
                else error_result_handler(prompt, self.logger)
            )

    def _send_prompt_count(
            self,
            client: httpx.Client,
            prompt: str,
            system_prompt: None | str,
            count: PromptsCounter,
            pre_send_handler,
            result_handler,
            error_result_handler,
            chunk_index: int | None = None,
    ) -> Any:
        result = self.send(
            client,
            prompt,
            system_prompt,
            pre_send_handler=pre_send_handler,
            result_handler=result_handler,
            error_result_handler=error_result_handler,
            chunk_index=chunk_index,
        )
        count.add()
        return result

    def send_prompts(
            self,
            prompts: list[str],
            system_prompt: str | None = None,
            pre_send_handler: PreSendHandlerType = None,
            result_handler: ResultHandlerType = None,
            error_result_handler: ErrorResultHandlerType = None,
            progress_callback=None,
    ) -> list[Any]:
        # Reduce log verbosity: use DEBUG for single-segment retranslation, INFO for batch translation
        total = len(prompts)
        log_level = self.logger.debug if total == 1 else self.logger.info
        log_level(
            f"base-url:{self.baseurl},model-id:{self.model_id},concurrent:{self.max_concurrent},temperature:{self.temperature}"
        )
        log_level(
            f"Planned to send {total} requests, concurrent requests: {self.max_concurrent}"
        )
        # Set max errors count: allow at least 1 error per chunk, but limit for very large batches
        # For small batches, this ensures retries can proceed
        max_errors = max(1, len(prompts) // MAX_REQUESTS_PER_ERROR)
        self.total_error_counter.max_errors_count = max_errors
        self.total_error_counter.count = 0  # Reset counter for new batch
        unified_logger.debug(
            LogModule.TRANS, f"Error counter limit set to {max_errors} for {len(prompts)} chunks (formula: max(1, {len(prompts)} // {MAX_REQUESTS_PER_ERROR}))"
        )

        # New: reset counter before each batch send
        self.unresolved_error_count = 0
        # Reset token counter
        self.token_counter.reset()

        counter = PromptsCounter(len(prompts), self.logger, progress_callback)

        system_prompts = itertools.repeat(system_prompt, len(prompts))
        counters = itertools.repeat(counter, len(prompts))
        pre_send_handlers = itertools.repeat(pre_send_handler, len(prompts))
        result_handlers = itertools.repeat(result_handler, len(prompts))
        error_result_handlers = itertools.repeat(error_result_handler, len(prompts))
        chunk_indices = list(range(len(prompts)))  # Add chunk indices
        limits = httpx.Limits(
            max_connections=self.max_concurrent * 2,  # Allow connection reuse
            max_keepalive_connections=self.max_concurrent,  # Keep active connections
        )
        proxies = get_httpx_proxies() if USE_PROXY else None
        with httpx.Client(
                trust_env=False, proxies=proxies, verify=False, limits=limits
        ) as client:
            clients = itertools.repeat(client, len(prompts))
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                results_iterator = executor.map(
                    self._send_prompt_count,
                    clients,
                    prompts,
                    system_prompts,
                    counters,
                    pre_send_handlers,
                    result_handlers,
                    error_result_handlers,
                    chunk_indices,  # Pass chunk indices
                )
                output_list = list(results_iterator)

        # New: print total unresolved errors after all tasks complete
        if self.unresolved_error_count > 0:
            unified_logger.warning(
                LogModule.TRANS,
                f"⚠️  Translation completed with {self.unresolved_error_count} unresolved errors "
                f"({self.unresolved_error_count}/{len(prompts)} chunks failed, {((self.unresolved_error_count/len(prompts))*100):.1f}% failure rate)"
            )
        else:
            unified_logger.info(
                LogModule.TRANS,
                f"✅ All requests processed successfully. Total unresolved errors: {self.unresolved_error_count}"
            )

        # New: print token usage statistics
        token_stats = self.token_counter.get_stats()
        unified_logger.info(
            LogModule.TRANS,
            f"Token usage statistics - Input: {token_stats['input_tokens'] / 1000:.2f}K(including cached: {token_stats['cached_tokens'] / 1000:.2f}K), "
            f"Output: {token_stats['output_tokens'] / 1000:.2f}K(including reasoning: {token_stats['reasoning_tokens'] / 1000:.2f}K), "
            f"Total: {token_stats['total_tokens'] / 1000:.2f}K"
        )

        return output_list


if __name__ == "__main__":
    pass
