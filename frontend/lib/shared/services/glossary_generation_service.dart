import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../app/app_config.dart';
import 'config_service.dart';

/// Service for generating glossaries from documents
class GlossaryGenerationService {
  factory GlossaryGenerationService() => _instance;
  GlossaryGenerationService._internal();
  static final GlossaryGenerationService _instance =
      GlossaryGenerationService._internal();

  final ConfigService _configService = ConfigService();

  /// Generate glossary from document
  /// If taskId is provided, will reuse chunks from Extract phase instead of extracting segments from file
  Future<Map<String, dynamic>> generateGlossary({
    required List<int> fileBytes,
    required String fileName,
    required String targetLanguage,
    String? customPrompt,
    String outputFormat = 'json',
    bool saveToPersonal = false,
    String? taskId,
    String detectionMode = 'uncertain', // 'uncertain' or 'deep'
  }) async {
    try {
      // Get base URL from config
      final appConfig = await _configService.getAppConfig();
      final baseUrl = appConfig?['base_url'] ?? AppConfig.baseUrl;

      // Get translation parameters from global settings
      final translationParams = await _getTranslationParams();

      // Validate required parameters
      final baseUrlParam = translationParams['base_url'] as String?;
      final modelIdParam = translationParams['model_id'] as String?;

      if (baseUrlParam == null || baseUrlParam.isEmpty) {
        throw Exception(
          'base_url is required but not found in translation parameters',
        );
      }
      if (modelIdParam == null || modelIdParam.isEmpty) {
        throw Exception(
          'model_id is required but not found in translation parameters',
        );
      }

      // Prepare request payload
      final payload = <String, dynamic>{
        'file_name': fileName,
        'file_content': base64Encode(fileBytes),
        'to_lang': targetLanguage,
        'base_url': baseUrlParam,
        'api_key': translationParams['api_key'] as String?,
        'model_id': modelIdParam,
        'api_type': translationParams['api_type'] as String? ?? 'openai',  // API protocol type
        'temperature': translationParams['temperature'] ?? 0.3,
        'thinking': translationParams['thinking'] ?? 'disable',
        'concurrent': translationParams['concurrent'] ?? 3,
        'timeout': translationParams['timeout'] ?? 30,
        'retry': translationParams['retry'] ?? 3,
        'chunk_size': translationParams['chunk_size'] ?? 0,
        'custom_prompt': customPrompt,
        'detection_mode': detectionMode, // 'uncertain' or 'deep'
        'output_format': outputFormat,
        'save_to_personal': saveToPersonal,
        if (taskId != null) 'task_id': taskId,
      };

      // Get authentication token
      final authHeader = _getAuthToken();

      // Debug: Log request details (without sensitive data)
      debugPrint(
        '[GLOSSARY_GENERATION] Request URL: $baseUrl/service/generate-glossary',
      );
      debugPrint(
        '[GLOSSARY_GENERATION] Payload keys: ${payload.keys.toList()}',
      );
      debugPrint('[GLOSSARY_GENERATION] base_url: $baseUrlParam');
      debugPrint('[GLOSSARY_GENERATION] model_id: $modelIdParam');
      debugPrint('[GLOSSARY_GENERATION] file_name: $fileName');
      debugPrint('[GLOSSARY_GENERATION] file_size: ${fileBytes.length} bytes');

      // Make API request
      final response = await http.post(
        Uri.parse('$baseUrl/service/generate-glossary'),
        headers: <String, String>{
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
        },
        body: jsonEncode(payload),
      );

      debugPrint(
        '[GLOSSARY_GENERATION] Response status: ${response.statusCode}',
      );
      debugPrint('[GLOSSARY_GENERATION] Response body: ${response.body}');

      if (response.statusCode == 200) {
        final result = jsonDecode(response.body);
        return <String, dynamic>{
          'success': true,
          'data': result,
        };
      } else {
        String errorMessage = 'Unknown error occurred';
        try {
          final errorBody = jsonDecode(response.body);
          errorMessage = errorBody['detail'] ??
              errorBody['message'] ??
              errorBody.toString();
        } catch (_) {
          errorMessage =
              'HTTP ${response.statusCode}: ${response.reasonPhrase ?? 'Unknown error'}';
        }
        debugPrint('[GLOSSARY_GENERATION] Error response: $errorMessage');
        return <String, dynamic>{
          'success': false,
          'error': errorMessage,
        };
      }
    } catch (e, stackTrace) {
      debugPrint('[GLOSSARY_GENERATION] Exception: $e');
      debugPrint('[GLOSSARY_GENERATION] Stack trace: $stackTrace');
      return <String, dynamic>{
        'success': false,
        'error': 'Failed to generate glossary: $e',
      };
    }
  }

  /// Get translation parameters for glossary generation
  Future<Map<String, dynamic>> _getTranslationParams() async {
    try {
      final appConfig = await _configService.getAppConfig();
      final secretsConfig = await _configService.getSecretsConfig();

      if (appConfig == null || secretsConfig == null) {
        debugPrint(
          '[GLOSSARY_GENERATION] App config or secrets config is null, using defaults',
        );
        return _getDefaultParams();
      }

      // Get default platform info
      final defaultPlatform =
          appConfig['default_platform'] as String? ?? 'openai';
      final aiPlatforms = appConfig['ai_platforms'] as Map<String, dynamic>? ??
          <String, dynamic>{};
      final platformInfo =
          aiPlatforms[defaultPlatform] as Map<String, dynamic>? ??
              <String, dynamic>{};
      final platformApiKeys =
          secretsConfig['platform_api_keys'] as Map<String, dynamic>? ??
              <String, dynamic>{};

      // Get API key for default platform
      final apiKey = platformApiKeys[defaultPlatform] as String? ?? '';

      // Validate API key (empty string means not configured)
      if (apiKey.isEmpty) {
        debugPrint(
          '[GLOSSARY_GENERATION] API key is empty (not configured), using defaults',
        );
        return _getDefaultParams();
      }

      // Get translation parameters from global settings
      final globalSettings = await _getGlobalSettings();

      final baseUrl =
          platformInfo['url'] as String? ?? 'https://api.openai.com/v1';
      final modelId = platformInfo['model'] as String? ?? 'gpt-4o';
      // Get API protocol type (default to 'openai' for backward compatibility)
      final apiType = platformInfo['api_protocol'] as String? ??
          platformInfo['api_type'] as String? ??
          'openai';

      // Ensure base_url and model_id are not empty
      if (baseUrl.isEmpty || modelId.isEmpty) {
        debugPrint(
          '[GLOSSARY_GENERATION] base_url or model_id is empty, using defaults',
        );
        return _getDefaultParams();
      }

      debugPrint(
        '[GLOSSARY_GENERATION] Using platform: $defaultPlatform, base_url: $baseUrl, model_id: $modelId, api_type: $apiType',
      );

      return <String, dynamic>{
        'base_url': baseUrl,
        'api_key': apiKey,
        'model_id': modelId,
        'api_type': apiType,  // Pass API protocol type (openai/anthropic/ollama)
        'temperature': globalSettings['temperature'] ?? 0.3,
        'thinking': globalSettings['thinking'] ?? 'disable',
        'concurrent': globalSettings['concurrent'] ?? 3,
        'timeout': globalSettings['timeout'] ?? 30,
        'retry': globalSettings['retry'] ?? 3,
        'chunk_size': globalSettings['chunkSize'] ??
            0, // 0 means unset, will be loaded from backend
      };
    } catch (e, stackTrace) {
      debugPrint('[GLOSSARY_GENERATION] Error getting translation params: $e');
      debugPrint('[GLOSSARY_GENERATION] Stack trace: $stackTrace');
      return _getDefaultParams();
    }
  }

  /// Get default translation parameters
  Map<String, dynamic> _getDefaultParams() => <String, dynamic>{
        'base_url': 'https://api.deepseek.com/v1',
        'api_key': 'sk-dd06eed4dbee4cbbbab1b7b0e920a079',
        'model_id': 'deepseek-chat',
        'temperature': 0.3,
        'thinking': 'disable',
        'concurrent': 3,
        'timeout': 30,
        'retry': 3,
        'chunk_size': 3000,
      };

  /// Get global settings for translation parameters
  Future<Map<String, dynamic>> _getGlobalSettings() async {
    try {
      // Try to get from SharedPreferences
      final prefs = await SharedPreferences.getInstance();
      final settingsJson = prefs.getString('global_settings');

      if (settingsJson != null) {
        final settings = jsonDecode(settingsJson) as Map<String, dynamic>;
        return <String, dynamic>{
          'temperature': settings['temperature'] ?? 0.3,
          'thinking': settings['thinking'] ?? 'disable',
          'concurrent': settings['translationConcurrent'] ?? 3,
          'timeout': settings['translationTimeout'] ?? 30,
          'retry': settings['retry'] ?? 3,
          'chunkSize': settings['translationChunkSize'] ?? 3000,
        };
      }

      return <String, dynamic>{};
    } catch (e) {
      return <String, dynamic>{};
    }
  }

  /// Get authentication token from ConfigService
  String? _getAuthToken() => _configService.authorizationHeader;
}
