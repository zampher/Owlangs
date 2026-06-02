import 'package:flutter/foundation.dart';
import 'config_service.dart';
import '../providers/settings_provider.dart';

/// Service for managing translation configuration parameters
class TranslationConfigService {
  factory TranslationConfigService() => _instance;
  TranslationConfigService._internal();
  static final TranslationConfigService _instance =
      TranslationConfigService._internal();

  final ConfigService _configService = ConfigService();
  Map<String, dynamic>? _cachedConfig;

  /// Get translation parameters from settings
  Future<Map<String, dynamic>> getTranslationParams() async {
    if (_cachedConfig != null) {
      return _cachedConfig!;
    }

    try {
      final Map<String, dynamic>? appConfig =
          await _configService.getAppConfig();
      final Map<String, dynamic>? secretsConfig =
          await _configService.getSecretsConfig();

      if (appConfig == null || secretsConfig == null) {
        return _getDefaultParams();
      }

      // Get default platform info
      final String defaultPlatform =
          appConfig['default_platform'] as String? ?? 'openai';
      final Map<String, dynamic> aiPlatforms =
          appConfig['ai_platforms'] as Map<String, dynamic>? ??
              <String, dynamic>{};
      final Map<String, dynamic> platformInfo =
          aiPlatforms[defaultPlatform] as Map<String, dynamic>? ??
              <String, dynamic>{};
      final Map<String, dynamic> platformApiKeys =
          secretsConfig['platform_api_keys'] as Map<String, dynamic>? ??
              <String, dynamic>{};

      // Get API key for default platform
      final String apiKey = platformApiKeys[defaultPlatform] as String? ?? '';

      // Use global settings for detailed parameters
      // Note: In a real implementation, you would get these from the global settings provider
      final Map<String, dynamic> params = <String, dynamic>{
        'base_url': platformInfo['url'] ?? 'https://api.openai.com/v1',
        'api_key': apiKey,
        'model_id': platformInfo['model'] ?? 'gpt-4o',
        'temperature': 0.3, // Will be overridden by global settings
        'thinking': 'disable', // Will be overridden by global settings
        'timeout': 30, // Will be overridden by global settings
        'retry': 3, // Will be overridden by global settings
        'custom_prompt': null, // Will be overridden by global settings
      };

      _cachedConfig = params;
      return params;
    } catch (e) {
      return _getDefaultParams();
    }
  }

  /// Get translation parameters from global settings (preferred method)
  Map<String, dynamic> getTranslationParamsFromSettings(
    GlobalSettings settings,
  ) =>
      <String, dynamic>{
        'temperature': settings.temperature,
        'thinking': settings.thinking,
        'retry': settings.retry,
        'segment_auto_retry_rounds': settings.segmentAutoRetryRounds,
        'custom_prompt': settings.customPrompt,
      };

  /// Get default translation parameters
  Map<String, dynamic> _getDefaultParams() => <String, dynamic>{
        'base_url': 'https://api.openai.com/v1',
        'api_key': '',
        'model_id': 'gpt-4o',
        'temperature': 0.3,
        'thinking': 'disable',
        'retry': 3,
        'custom_prompt': null,
      };

  /// Clear cached config (call when settings change)
  void clearCache() {
    _cachedConfig = null;
  }
}
