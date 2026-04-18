# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
"""
Temperature configuration management for different task types and platforms.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Literal
from enum import Enum

class TaskType(str, Enum):
    """Task types that use temperature parameter"""
    TRANSLATION = "translation"
    GLOSSARY_GENERATION = "glossary_generation"
    ANONYMIZATION = "anonymization"
    SUMMARIZATION = "summarization"
    ANALYSIS = "analysis"

class TemperaturePreset(str, Enum):
    """Predefined temperature presets"""
    CONSERVATIVE = "conservative"  # 0.1-0.3: High accuracy, low creativity
    BALANCED = "balanced"         # 0.4-0.6: Balanced accuracy and creativity
    CREATIVE = "creative"         # 0.7-0.9: High creativity, more variation
    EXPERIMENTAL = "experimental" # 0.9-1.0: Maximum creativity

@dataclass
class TemperatureConfig:
    """Temperature configuration for a specific task type"""
    task_type: TaskType
    default_value: float
    min_value: float = 0.0
    max_value: float = 2.0
    step: float = 0.1
    description: str = ""
    recommended_presets: Dict[TemperaturePreset, float] = None
    
    def __post_init__(self):
        if self.recommended_presets is None:
            self.recommended_presets = {
                TemperaturePreset.CONSERVATIVE: 0.2,
                TemperaturePreset.BALANCED: 0.5,
                TemperaturePreset.CREATIVE: 0.7,
                TemperaturePreset.EXPERIMENTAL: 0.9,
            }

@dataclass
class PlatformTemperatureConfig:
    """Platform-specific temperature configuration"""
    platform: str
    default_temperature: float
    task_overrides: Dict[TaskType, float] = None
    description: str = ""
    
    def get_temperature_for_task(self, task_type: TaskType) -> float:
        """Get temperature for specific task type on this platform"""
        if self.task_overrides and task_type in self.task_overrides:
            return self.task_overrides[task_type]
        return self.default_temperature

class TemperatureManager:
    """Centralized temperature configuration management"""
    
    def __init__(self):
        self._task_configs = self._initialize_task_configs()
        self._platform_configs = self._initialize_platform_configs()
    
    def _initialize_task_configs(self) -> Dict[TaskType, TemperatureConfig]:
        """Initialize task-specific temperature configurations"""
        return {
            TaskType.TRANSLATION: TemperatureConfig(
                task_type=TaskType.TRANSLATION,
                default_value=0.3,
                description="Translation tasks - balanced accuracy and fluency"
            ),
            TaskType.GLOSSARY_GENERATION: TemperatureConfig(
                task_type=TaskType.GLOSSARY_GENERATION,
                default_value=0.2,
                description="Glossary generation - high accuracy for terminology"
            ),
            TaskType.ANONYMIZATION: TemperatureConfig(
                task_type=TaskType.ANONYMIZATION,
                default_value=0.1,
                description="Anonymization - maximum consistency"
            ),
            TaskType.SUMMARIZATION: TemperatureConfig(
                task_type=TaskType.SUMMARIZATION,
                default_value=0.5,
                description="Summarization - balanced conciseness and completeness"
            ),
            TaskType.ANALYSIS: TemperatureConfig(
                task_type=TaskType.ANALYSIS,
                default_value=0.4,
                description="Analysis tasks - structured and accurate"
            ),
        }
    
    def _initialize_platform_configs(self) -> Dict[str, PlatformTemperatureConfig]:
        """Initialize platform-specific temperature configurations"""
        return {
            "openai": PlatformTemperatureConfig(
                platform="openai",
                default_temperature=0.3,
                description="OpenAI models work well with standard temperature ranges"
            ),
            "anthropic": PlatformTemperatureConfig(
                platform="anthropic",
                default_temperature=0.3,
                description="Anthropic models prefer slightly lower temperature"
            ),
            "google": PlatformTemperatureConfig(
                platform="google",
                default_temperature=0.3,
                task_overrides={
                    TaskType.TRANSLATION: 0.3,  # Google models are good at translation
                }
            ),
            "deepseek": PlatformTemperatureConfig(
                platform="deepseek",
                default_temperature=0.3,
                description="DeepSeek models work well with moderate temperature"
            ),
            "zhipu": PlatformTemperatureConfig(
                platform="zhipu",
                default_temperature=0.3,
                description="Zhipu models prefer balanced temperature"
            ),
        }
    
    def get_temperature_for_task(self, task_type: TaskType, platform: str = None, 
                               custom_value: float = None) -> float:
        """Get temperature for a specific task and platform"""
        if custom_value is not None:
            return self._validate_temperature(custom_value, task_type)
        
        if platform and platform in self._platform_configs:
            platform_config = self._platform_configs[platform]
            return platform_config.get_temperature_for_task(task_type)
        
        task_config = self._task_configs.get(task_type)
        if task_config:
            return task_config.default_value
        
        return 0.3  # Fallback default
    
    def get_temperature_presets(self, task_type: TaskType) -> Dict[TemperaturePreset, float]:
        """Get recommended temperature presets for a task type"""
        task_config = self._task_configs.get(task_type)
        if task_config:
            return task_config.recommended_presets
        return {}
    
    def get_task_config(self, task_type: TaskType) -> Optional[TemperatureConfig]:
        """Get full configuration for a task type"""
        return self._task_configs.get(task_type)
    
    def get_platform_config(self, platform: str) -> Optional[PlatformTemperatureConfig]:
        """Get full configuration for a platform"""
        return self._platform_configs.get(platform)
    
    def _validate_temperature(self, temperature: float, task_type: TaskType) -> float:
        """Validate and clamp temperature value"""
        task_config = self._task_configs.get(task_type)
        if task_config:
            return max(task_config.min_value, min(task_config.max_value, temperature))
        return max(0.0, min(2.0, temperature))
    
    def get_all_task_types(self) -> list[TaskType]:
        """Get all available task types"""
        return list(self._task_configs.keys())
    
    def get_all_platforms(self) -> list[str]:
        """Get all available platforms"""
        return list(self._platform_configs.keys())

# Global instance
temperature_manager = TemperatureManager()
