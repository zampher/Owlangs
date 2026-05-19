import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart'
    show kDebugMode, kIsWeb, defaultTargetPlatform, TargetPlatform;
import '../../app/app_config.dart';
import '../utils/app_logger.dart';
import 'ai_platform_test_service.dart';

class ConfigService {
  factory ConfigService() => _instance;
  ConfigService._internal();
  static final ConfigService _instance = ConfigService._internal();

  void _log(String message, {LogLevel level = LogLevel.debug}) {
    AppLogger.log('ConfigService', message, level: level);
  }

  /// When true, backend treats this client as local admin (desktop app from localhost).
  static Map<String, String> get desktopBackendHeaders {
    if (kIsWeb) return <String, String>{};
    if (defaultTargetPlatform == TargetPlatform.windows ||
        defaultTargetPlatform == TargetPlatform.linux ||
        defaultTargetPlatform == TargetPlatform.macOS) {
      return <String, String>{'X-Client': 'desktop'};
    }
    return <String, String>{};
  }

  final Dio _dio = Dio(
    BaseOptions(
      baseUrl: AppConfig.baseUrl,
      // CRITICAL: Increase timeout for startup requests to handle slow backend initialization
      // Connection timeout: allow more time for backend to accept connections
      // Increased to 30 seconds to handle backend startup delays
      connectTimeout: const Duration(seconds: 30),
      // Receive timeout: allow more time for backend to respond (especially during startup)
      // Increased to 30 seconds to handle backend processing delays
      receiveTimeout: const Duration(seconds: 30),
      headers: <String, dynamic>{
        'Content-Type': 'application/json',
        // Prevent Service Worker and browser caching for API requests
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        ...ConfigService.desktopBackendHeaders,
      },
    ),
  );

  bool? _authRequired; // null until loaded

  bool? get authRequired => _authRequired;

  /// Set default auth required value (used when config loading fails or times out)
  void setDefaultAuthRequired(bool value) {
    _authRequired ??= value;
  }

  /// Force reload auth config from backend (use after mutating auth_required).
  Future<void> reloadAuthConfig() async {
    _authRequired = null;
    return loadAuthConfigOnce();
  }

  Future<void> loadAuthConfigOnce() async {
    if (_authRequired != null) return;

    // Desktop builds (Windows, macOS, Linux) run as standalone apps – skip auth entirely
    if (!kIsWeb &&
        (defaultTargetPlatform == TargetPlatform.windows ||
            defaultTargetPlatform == TargetPlatform.linux ||
            defaultTargetPlatform == TargetPlatform.macOS)) {
      _authRequired = false;
      return;
    }

    try {
      final res = await _dio.get('/auth/config');
      if (res.statusCode == 200 && res.data is Map<String, dynamic>) {
        _authRequired = (res.data['auth_required'] as bool?) ?? false;
      }
    } catch (e) {
      // Default to false (no auth) for desktop apps - allow user to proceed
      // This is safer for desktop deployment where auth may not be configured
      _authRequired = false;
    }
  }

  // 设置认证token
  void setAuthToken(String? token) {
    if (token != null) {
      _dio.options.headers['Authorization'] = 'Bearer $token';
    } else {
      _dio.options.headers.remove('Authorization');
    }
  }

  // 获取当前认证头（用于其它服务复用）
  String? get authorizationHeader =>
      _dio.options.headers['Authorization'] as String?;

  // UI文本配置
  Map<String, dynamic>? _uiTexts;

  // Track if we've already logged config load to avoid duplicate logs
  bool _hasLoggedConfigLoad = false;

  /// Get application configuration including AI platforms
  Future<Map<String, dynamic>?> getAppConfig({int maxRetries = 2}) async {
    // Gate by auth config: if web要求登录且未携带token，则不请求，直接返回null
    await loadAuthConfigOnce();
    final needsAuth = _authRequired ?? false;
    final hasToken = _dio.options.headers.containsKey('Authorization');
    if (needsAuth && !hasToken) {
      if (kDebugMode) {
        _log('Auth required but no token, returning null');
      }
      return null;
    }

    // Retry logic for startup requests (backend may not be ready immediately)
    for (int attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        final response = await _dio.get('/auth/app-config');
        if (response.statusCode == 200) {
          final data = response.data;
          // 缓存UI文本
          if (data != null && data['ui_texts'] != null) {
            _uiTexts = data['ui_texts'];
          }
          // Only log once when config is first loaded (avoid duplicate logs)
          if (kDebugMode && !_hasLoggedConfigLoad) {
            _log(
              'Config loaded: ${(data['ai_platforms'] as Map?)?.length ?? 0} platforms',
            );
            _hasLoggedConfigLoad = true;
          }
          return data;
        } else {
          _log(
            'Unexpected status code: ${response.statusCode}',
            level: LogLevel.warn,
          );
          // If not 200, don't retry (likely auth or server error)
          return null;
        }
      } catch (e) {
        // Log error for this attempt
        if (attempt < maxRetries) {
          _log(
            'Error getting app config (attempt ${attempt + 1}/${maxRetries + 1}): $e. Retrying...',
            level: LogLevel.warn,
          );
          // Wait before retry (exponential backoff: 2s, 4s)
          // Increased delay to give backend more time to initialize
          await Future.delayed(Duration(seconds: (attempt + 1) * 2));
        } else {
          // Last attempt failed
          _log('Error getting app config after ${maxRetries + 1} attempts: $e',
              level: LogLevel.error,);
          if (e is DioException && kDebugMode) {
            _log('DioException: ${e.type} - ${e.message}',
                level: LogLevel.error,);
          }
        }
      }
    }
    // All retries exhausted
    return null;
  }

  /// Get UI texts from configuration
  Map<String, dynamic>? getUITexts() => _uiTexts;

  /// Get specific UI text by path (e.g., 'platform_categories.us_platforms')
  String? getUIText(String path) {
    if (_uiTexts == null) return null;

    final parts = path.split('.');
    dynamic current = _uiTexts;

    for (final part in parts) {
      if (current is Map<String, dynamic> && current.containsKey(part)) {
        current = current[part];
      } else {
        return null;
      }
    }

    return current?.toString();
  }

  /// Get secrets configuration including API keys
  Future<Map<String, dynamic>?> getSecretsConfig() async {
    try {
      final response = await _dio.get('/auth/app-config/raw-secrets');
      if (response.statusCode == 200) {
        return response.data;
      }
    } catch (e) {
      _log('Get secrets config error: $e', level: LogLevel.error);
    }
    return null;
  }

  /// Get AI platform test status from backend (single source of truth).
  /// Returns map with "platforms" key: { "platformKey": { "isApiAvailable": bool, "lastTestError": string?, "lastTestedAt": string } }.
  Future<Map<String, dynamic>?> getAiPlatformStatus() async {
    try {
      final response = await _dio.get('/auth/ai-platform-status');
      if (response.statusCode == 200 && response.data is Map<String, dynamic>) {
        return response.data as Map<String, dynamic>;
      }
    } catch (e) {
      _log('Get AI platform status error: $e');
    }
    return null;
  }

  /// Get system settings (e.g. features.show_ads) from system.json via backend.
  Future<Map<String, dynamic>?> getSystemSettings() async {
    try {
      final response = await _dio.get('/api/settings/system');
      if (response.statusCode == 200 && response.data is Map<String, dynamic>) {
        return response.data as Map<String, dynamic>;
      }
    } catch (e) {
      _log('Get system settings error: $e');
    }
    return null;
  }

  /// Update show_ads in system.json. Call after toggle in Settings > General.
  Future<bool> patchSystemShowAds(bool showAds) async {
    try {
      final response = await _dio.patch(
        '/api/settings/system',
        data: <String, dynamic>{
          'features': <String, dynamic>{'show_ads': showAds},
        },
      );
      return response.statusCode == 200;
    } catch (e) {
      _log('Patch system show_ads error: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Update application configuration
  Future<bool> updateAppConfig(Map<String, dynamic> config) async {
    try {
      // Use unified batch settings API as backend no longer supports PUT /auth/app-config
      final response = await _dio.post(
        '/api/v1/auth/settings/batch',
        data: <String, Object>{
          'type': 'global',
          'changes': config,
        },
      );
      return response.statusCode == 200 && (response.data?['success'] == true);
    } catch (e) {
      _log('Update app config error: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Update single setting
  Future<bool> updateSingleSetting(String key, value) async {
    try {
      final response = await _dio.post(
        '/auth/app-config/setting',
        data: <String, dynamic>{
          'key': key,
          'value': value,
        },
      );
      return response.statusCode == 200;
    } catch (e) {
      _log('Update single setting error: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Batch update settings (grouped by type: global/user/sensitive)
  Future<bool> updateSettingsBatch(
    String type,
    Map<String, dynamic> changes,
  ) async {
    try {
      final response = await _dio.post(
        '/api/v1/auth/settings/batch',
        data: <String, Object>{
          'type': type, // 'global' | 'user' | 'sensitive'
          'changes': changes,
        },
      );
      return response.statusCode == 200 && (response.data?['success'] == true);
    } catch (e) {
      if (kDebugMode) {
        _log('Update settings batch error: $e', level: LogLevel.error);
        if (e is DioException) {
          _log(
            'Batch update DioException type: ${e.type}',
            level: LogLevel.error,
          );
          _log(
            'Batch update DioException response: ${e.response?.data}',
            level: LogLevel.error,
          );
          _log(
            'Batch update DioException status: ${e.response?.statusCode}',
            level: LogLevel.error,
          );
        }
      }
      return false;
    }
  }

  /// Test AI platform connection
  Future<Map<String, dynamic>?> testAIPlatform(
    String platform,
    String apiKey, {
    String? baseUrl,
    String? modelName,
  }) async {
    try {
      // 使用真正的API测试服务
      final testService = AIPlatformTestService();
      final result = await testService.testPlatform(
        platform,
        apiKey,
        baseUrl: baseUrl,
        modelName: modelName,
      );
      // 规范化失败信息：若存在 error，则将其映射到 message，避免仅显示 "Connection failed"
      if (result['success'] == false) {
        final error = result['error']?.toString();
        final message = result['message']?.toString();
        if (error != null && error.isNotEmpty) {
          // 返回一个新的map，确保 message 包含具体错误
          return <String, dynamic>{
            ...result,
            'message': error,
          };
        }
        if (message == null || message.isEmpty) {
          return <String, dynamic>{
            ...result,
            'message': 'Unknown error',
          };
        }
      }
      return result;
    } catch (e) {
      _log('Test AI platform error: $e', level: LogLevel.error);
      return <String, dynamic>{
        'success': false,
        'message': 'Test failed: ${e.toString()}',
        'platform': platform,
      };
    }
  }

  /// List available models for an AI platform
  Future<Map<String, dynamic>> listPlatformModels(
    String platform,
    String baseUrl,
    String apiKey, {
    String? apiProtocol,
  }) async {
    try {
      print('[ConfigService] listPlatformModels called with:');
      print('  platform: $platform');
      print('  baseUrl: $baseUrl');
      print('  apiProtocol: $apiProtocol');
      print('  apiKey length: ${apiKey.length}');

      final Map<String, dynamic> body = <String, dynamic>{
        'platform_type': platform,
        'base_url': baseUrl,
        'api_key': apiKey,
      };
      if (apiProtocol != null && apiProtocol.trim().isNotEmpty) {
        body['api_protocol'] = apiProtocol.trim();
      }

      final response = await _dio.post(
        '/auth/ai-platform/list-models',
        data: body,
        options: Options(
          headers: <String, dynamic>{
            'Content-Type': 'application/json',
          },
        ),
      );

      if (response.statusCode == 200 && response.data is Map<String, dynamic>) {
        return response.data as Map<String, dynamic>;
      } else {
        return <String, dynamic>{
          'success': false,
          'error': 'Invalid response format',
          'models': <String>[],
        };
      }
    } catch (e) {
      _log('List platform models error: $e', level: LogLevel.error);
      if (e is DioException && e.response != null) {
        final errorData = e.response!.data;
        return <String, dynamic>{
          'success': false,
          'error': errorData['error'] ??
              errorData['detail'] ??
              'Failed to list models',
          'models': <String>[],
        };
      }
      return <String, dynamic>{
        'success': false,
        'error': 'Failed to list models: ${e.toString()}',
        'models': <String>[],
      };
    }
  }

  /// Get LDAP configuration (admin only; requires auth).
  Future<Map<String, dynamic>?> getLdapConfig() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/auth/ldap-config');
      if (response.statusCode == 200 && response.data != null) {
        return response.data;
      }
    } catch (e) {
      _log('Get LDAP config error: $e', level: LogLevel.error);
    }
    return null;
  }

  /// Save LDAP configuration. If enabling LDAP, body must include ldap_test_validated: true.
  Future<bool> saveLdapConfig(Map<String, dynamic> payload) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/ldap-config',
        data: payload,
      );
      return response.statusCode == 200 &&
          (response.data?['success'] == true || response.data == null);
    } catch (e) {
      _log('Save LDAP config error: $e', level: LogLevel.error);
      rethrow;
    }
  }

  /// Test LDAP connection. Payload: username, password, and optional LDAP overrides.
  Future<Map<String, dynamic>> testLdap(Map<String, dynamic> payload) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/test-ldap',
        data: payload,
      );
      final data = response.data ?? <String, dynamic>{};
      final ok = data['ok'] == true;
      return <String, dynamic>{
        'ok': ok,
        'message': data['message']?.toString() ?? (ok ? 'OK' : 'Unknown error'),
        'test_validated': data['test_validated'] == true,
      };
    } catch (e) {
      if (e is DioException && e.response?.data is Map<String, dynamic>) {
        final d = e.response!.data as Map<String, dynamic>;
        return <String, dynamic>{
          'ok': false,
          'message': d['message']?.toString() ?? e.message ?? 'Test failed',
          'test_validated': false,
        };
      }
      _log('Test LDAP error: $e', level: LogLevel.error);
      return <String, dynamic>{
        'ok': false,
        'message': e.toString(),
        'test_validated': false,
      };
    }
  }

  // ===== Local users management (admin only, Web) =====

  /// List local users.
  ///
  /// Returns a list of user maps without password hashes.
  Future<List<Map<String, dynamic>>> listLocalUsers() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/auth/local-users',
      );
      if (response.statusCode == 200 &&
          response.data != null &&
          response.data!['users'] is List<dynamic>) {
        return (response.data!['users'] as List<dynamic>)
            .whereType<Map<String, dynamic>>()
            .toList();
      }
    } catch (e) {
      _log('List local users error: $e', level: LogLevel.error);
    }
    return <Map<String, dynamic>>[];
  }

  /// Create a local user.
  Future<bool> createLocalUser({
    required String username,
    required String password,
    String role = 'user',
    String? displayName,
    String? email,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/auth/local-users',
        data: <String, dynamic>{
          'username': username,
          'password': password,
          'role': role,
          if (displayName != null) 'display_name': displayName,
          if (email != null) 'email': email,
        },
      );
      return response.statusCode == 200;
    } on DioException catch (e) {
      String message = e.message ?? 'Create local user failed';
      final data = e.response?.data;
      if (data is Map<String, dynamic>) {
        // Backend returns detail for 400 errors like "User already exists"
        message =
            data['detail']?.toString() ?? data['message']?.toString() ?? message;
      }
      _log('Create local user error: $message', level: LogLevel.error);
      throw Exception(message);
    } catch (e) {
      _log('Create local user error: $e', level: LogLevel.error);
      throw Exception(e.toString());
    }
  }

  /// Update local user profile (role / display_name / email).
  Future<bool> updateLocalUser({
    required String username,
    String? role,
    String? displayName,
    String? email,
  }) async {
    try {
      final Map<String, dynamic> payload = <String, dynamic>{};
      if (role != null) payload['role'] = role;
      if (displayName != null) payload['display_name'] = displayName;
      if (email != null) payload['email'] = email;
      final response = await _dio.put<Map<String, dynamic>>(
        '/api/v1/auth/local-users/$username',
        data: payload,
      );
      return response.statusCode == 200;
    } catch (e) {
      _log('Update local user error: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Reset local user's password (cannot reset super admin by backend rule).
  Future<bool> resetLocalUserPassword({
    required String username,
    required String newPassword,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/auth/local-users/$username/reset-password',
        data: <String, dynamic>{'password': newPassword},
      );
      return response.statusCode == 200;
    } catch (e) {
      _log('Reset local user password error: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Delete a local user (backend forbids deleting super admin).
  Future<bool> deleteLocalUser(String username) async {
    try {
      final response = await _dio.delete<Map<String, dynamic>>(
        '/api/v1/auth/local-users/$username',
      );
      return response.statusCode == 200;
    } catch (e) {
      _log('Delete local user error: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Change password for current authenticated user (self-service).
  ///
  /// Backend route: POST /api/v1/auth/local-users/me/change-password
  /// Body: { "current_password": "...", "new_password": "..." }
  /// Throws [Exception] with human-readable message on failure so that UI can display it.
  Future<void> changeOwnPassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/auth/local-users/me/change-password',
        data: <String, dynamic>{
          'current_password': currentPassword,
          'new_password': newPassword,
        },
      );
      final bool okFlag =
          response.data != null && response.data!['ok'] == true;
      if (response.statusCode == 200 && okFlag) {
        return;
      }
      final String message =
          'Failed to change password (status ${response.statusCode})';
      _log(message, level: LogLevel.error);
      throw Exception(message);
    } on DioException catch (e) {
      String message = e.message ?? 'Failed to change password';
      final data = e.response?.data;
      if (data is Map<String, dynamic>) {
        message =
            data['detail']?.toString() ?? data['message']?.toString() ?? message;
      }
      _log('Change own password error: $message', level: LogLevel.error);
      throw Exception(message);
    } catch (e) {
      _log('Change own password error: $e', level: LogLevel.error);
      throw Exception(e.toString());
    }
  }
}

/// AI Platform configuration model
class AIPlatformInfo {
  AIPlatformInfo({
    required this.key,
    required this.name,
    required this.url,
    required this.model,
    required this.maxTokens,
    required this.temperature,
    required this.temperatureMin,
    required this.temperatureMax,
    required this.thinkingModeSupported,
    required this.thinkingMode,
    this.recommendedTokens,
    this.performanceNote,
    this.description,
    this.tokenLink,
    this.apiKey,
    this.isConfigured = false,
    this.isApiAvailable,
    this.platformType = 'llm',
    this.parserSubtype,
    this.apiEndpoints,
    this.lastTestError,
    this.requiresApiKey = true,
    this.apiProtocol = 'openai',
    this.chunkSize = 3000,
    this.concurrent = 5,
  });

  factory AIPlatformInfo.fromJson(
    String key,
    Map<String, dynamic> json, {
    String? apiKey,
    bool? isApiAvailable,
    bool? configured,
  }) {
    // Check if API key is required from platform config (default to true for backward compatibility)
    // For backward compatibility: check both new 'requires_api_key' and old 'api_key_optional' fields
    final bool requiresApiKey = json['requires_api_key'] ?? 
        (json['api_key_optional'] == true ? false : true);
    
    // Get API protocol (default to 'openai' for backward compatibility)
    final apiProtocol = (json['api_protocol'] as String?) ?? 'openai';
    
    // Check if API key is valid (non-empty)
    // Empty string means not configured
    final hasValidApiKey = apiKey != null && apiKey.isNotEmpty;

    final url = (json['url'] ?? '').toString().trim();
    final model = (json['model'] ?? '').toString().trim();
    final hasBasicConfig = url.isNotEmpty && model.isNotEmpty;

    // Prefer using the configured field from backend.
    // If not provided:
    // - Platforms that require API key: based on hasValidApiKey
    // - Platforms that do not require API key (!requiresApiKey): based on hasBasicConfig
    final isConfigured =
        configured ?? (requiresApiKey ? hasValidApiKey : hasBasicConfig);

    return AIPlatformInfo(
      key: key,
      name: json['name'] ?? '',
      url: url,
      model: model,
      maxTokens: _toInt(json['max_tokens'], 4096),
      temperature: _toDouble(json['temperature'], 0.3),
      temperatureMin: _toDouble(json['temperature_min'], 0),
      temperatureMax: _toDouble(json['temperature_max'], 2),
      thinkingModeSupported: json['thinking_mode_supported'] == true,
      thinkingMode: json['thinking_mode'] ?? 'disable',
      recommendedTokens: json['recommended_tokens'] != null ? _toInt(json['recommended_tokens'], null) : null,
      performanceNote: json['performance_note'],
      description: json['description'],
      tokenLink: json['token_link'],
      apiKey: apiKey,
      isConfigured: isConfigured,
      isApiAvailable: isApiAvailable,
      platformType: json['platform_type'] ?? 'llm',
      parserSubtype: json['parser_subtype']?.toString(),
      apiEndpoints: json['api_endpoints'] != null
          ? Map<String, String>.from(
              json['api_endpoints'] as Map<dynamic, dynamic>,
            )
          : null,
      requiresApiKey: requiresApiKey,
      apiProtocol: apiProtocol,
      chunkSize: _toInt(json['chunk_size'], 3000),
      concurrent: _toInt(json['concurrent'], 5),
    );
  }

  // Helper methods for safe type conversion
  static int _toInt(value, int? defaultValue) {
    if (value == null) return defaultValue ?? 0;
    if (value is int) return value;
    if (value is double) return value.toInt();
    if (value is String) return int.tryParse(value) ?? defaultValue ?? 0;
    return defaultValue ?? 0;
  }

  static double _toDouble(value, double defaultValue) {
    if (value == null) return defaultValue;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    if (value is String) return double.tryParse(value) ?? defaultValue;
    return defaultValue;
  }
  final String key;
  final String name;
  final String url;
  final String model;
  final int maxTokens;
  final double temperature;
  final double temperatureMin;
  final double temperatureMax;
  final bool thinkingModeSupported;
  final String thinkingMode; // "enable", "disable", "default"
  final int? recommendedTokens;
  final String? performanceNote;
  final String? description;
  final String? tokenLink;
  final String? apiKey;
  final bool isConfigured;
  final bool? isApiAvailable;
  final String platformType;
  final String? parserSubtype;
  final Map<String, String>? apiEndpoints;
  final String? lastTestError;
  final bool requiresApiKey;
  final String apiProtocol;
  final int chunkSize;
  final int concurrent;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'name': name,
        'url': url,
        'model': model,
        'max_tokens': maxTokens,
        'temperature': temperature,
        'temperature_min': temperatureMin,
        'temperature_max': temperatureMax,
        'thinking_mode_supported': thinkingModeSupported,
        'thinking_mode': thinkingMode,
        'recommended_tokens': recommendedTokens,
        'performance_note': performanceNote,
        'description': description,
        'token_link': tokenLink,
        'platform_type': platformType,
        'parser_subtype': parserSubtype,
        'api_protocol': apiProtocol,
        'requires_api_key': requiresApiKey,
        'api_endpoints': apiEndpoints,
        'chunk_size': chunkSize,
        'concurrent': concurrent,
        // Intentionally exclude lastTestError from persisted JSON
      };

  AIPlatformInfo copyWith({
    String? name,
    String? url,
    String? model,
    int? maxTokens,
    double? temperature,
    double? temperatureMin,
    double? temperatureMax,
    bool? thinkingModeSupported,
    String? thinkingMode,
    int? recommendedTokens,
    String? performanceNote,
    String? description,
    String? tokenLink,
    String? apiKey,
    bool? isConfigured,
    bool? isApiAvailable,
    String? platformType,
    String? parserSubtype,
    Map<String, String>? apiEndpoints,
    String? lastTestError,
    bool? requiresApiKey,
    String? apiProtocol,
    int? chunkSize,
    int? concurrent,
  }) =>
      AIPlatformInfo(
        key: key,
        name: name ?? this.name,
        url: url ?? this.url,
        model: model ?? this.model,
        maxTokens: maxTokens ?? this.maxTokens,
        temperature: temperature ?? this.temperature,
        temperatureMin: temperatureMin ?? this.temperatureMin,
        temperatureMax: temperatureMax ?? this.temperatureMax,
        thinkingModeSupported:
            thinkingModeSupported ?? this.thinkingModeSupported,
        thinkingMode: thinkingMode ?? this.thinkingMode,
        recommendedTokens: recommendedTokens ?? this.recommendedTokens,
        performanceNote: performanceNote ?? this.performanceNote,
        description: description ?? this.description,
        tokenLink: tokenLink ?? this.tokenLink,
        apiKey: apiKey ?? this.apiKey,
        isConfigured: isConfigured ?? this.isConfigured,
        isApiAvailable: isApiAvailable ?? this.isApiAvailable,
        platformType: platformType ?? this.platformType,
        parserSubtype: parserSubtype ?? this.parserSubtype,
        apiEndpoints: apiEndpoints ?? this.apiEndpoints,
        lastTestError: lastTestError,
        requiresApiKey: requiresApiKey ?? this.requiresApiKey,
        apiProtocol: apiProtocol ?? this.apiProtocol,
        chunkSize: chunkSize ?? this.chunkSize,
        concurrent: concurrent ?? this.concurrent,
      );
}
