# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TypeVar, Any, Optional

from agents.agent import AgentConfig
from agents.glossary_agent import GlossaryAgentConfig, GlossaryAgent
from ir.document import Document
from translator.base import Translator, TranslatorConfig
from logger import LogModule


@dataclass(kw_only=True)
class AiTranslatorConfig(TranslatorConfig, AgentConfig):
    base_url: str | None = field(default=None,
                                 metadata={"description": "OpenAI compatible address, required when skip_translate is False"})
    model_id: str | None = field(default=None, metadata={"description": "Required when skip_translate is False"})
    to_lang: str = "English"
    custom_prompt: str | None = None
    chunk_size: int = 3000
    glossary_dict: dict[str:str] | None = field(default=None)
    glossary_generate_enable: bool = False
    glossary_agent_config: GlossaryAgentConfig | None = None
    skip_translate: bool = False  # When skip_translate is False, base_url and model_id are required
    deep_split: bool = True


T = TypeVar('T', bound=Document)


class AiTranslator(Translator[T]):
    """
    Translate intermediate text (in-place replacement), Translator does not perform format conversion
    """

    def __init__(self, config: AiTranslatorConfig):
        super().__init__(config=config)
        self.skip_translate = config.skip_translate
        self.glossary_agent = None
        self.glossary_dict_gen = None
        if not self.skip_translate and (config.base_url is None or config.api_key is None or config.model_id is None):
            raise ValueError("When skip_translate is not false, base_url, api_key, and model_id are required")
        
        # Wrap logger to automatically add module=LogModule.TRANS to all log calls
        original_logger = self.logger
        
        class TranslatorLoggerWrapper:
            def __getattr__(self, name):
                method = getattr(original_logger, name)
                if name in ['debug', 'info', 'warning', 'error', 'critical', 'success', 'trace']:
                    def wrapper(*args, **kwargs):
                        # UnifiedLogger uses (module, message). Pass (LogModule.TRANS, *args) for legacy single-arg calls.
                        if 'module' not in kwargs and not (args and isinstance(args[0], LogModule)):
                            return method(LogModule.TRANS, *args, **kwargs)
                        return method(*args, **kwargs)
                    return wrapper
                return method
        
        self.logger = TranslatorLoggerWrapper()

        if config.glossary_generate_enable:
            # Use translation parameters directly for glossary generation
            glossary_agent_config = GlossaryAgentConfig(
                to_lang=config.to_lang,
                base_url=config.base_url,
                api_key=config.api_key,
                model_id=config.model_id,
                api_type=getattr(config, 'api_type', None) or getattr(config, 'api_protocol', None) or 'openai',
                temperature=config.temperature,
                thinking=config.thinking,
                concurrent=config.concurrent,
                connect_timeout=getattr(config, 'connect_timeout', 15),
                timeout=config.timeout,
                logger=self.logger,
                retry=config.retry
            )
            self.glossary_agent = GlossaryAgent(glossary_agent_config)

    @abstractmethod
    def translate(self, document: T) -> Document:
        ...

    @abstractmethod
    async def translate_async(self, document: T) -> Document:
        ...
