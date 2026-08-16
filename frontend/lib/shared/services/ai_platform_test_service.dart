import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'config_service.dart';
import '../../app/app_config.dart';

/// AI平台测试服务（统一走后端代理）
class AIPlatformTestService {
  factory AIPlatformTestService() => _instance;
  AIPlatformTestService._internal();
  static final AIPlatformTestService _instance =
      AIPlatformTestService._internal();

  /// 通过后端统一测试（除 MinerU 外均走此接口）
  Future<Map<String, dynamic>> _testViaBackend({
    required String platformType,
    required String apiKey,
    String? baseUrl,
    String? modelName,
    int? testConnectTimeout,
    int? testRequestTimeout,
  }) async {
    final cfg = ConfigService();
    final authHeader = cfg.authorizationHeader;
    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        headers: <String, dynamic>{
          'Content-Type': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
          ...ConfigService.desktopBackendHeaders,
        },
      ),
    );

    try {
      final payload = <String, dynamic>{
        'platform_type': platformType,
        if (baseUrl != null) 'base_url': baseUrl,
        if (modelName != null) 'model_name': modelName,
        'api_key': apiKey,
        if (testConnectTimeout != null) 'test_connect_timeout': testConnectTimeout,
        if (testRequestTimeout != null) 'test_request_timeout': testRequestTimeout,
      };
      
      // DEBUG: Log payload
      print('[AIPlatformTestService] Sending test request:');
      print('  platform_type: $platformType');
      print('  baseUrl: $baseUrl');
      print('  modelName: $modelName');
      print('  apiKey length: ${apiKey.length}');
      
      final resp =
          await dio.post('/api/v1/auth/test-ai-platform', data: payload);

      final dynamic body = resp.data;
      if (body is Map<String, dynamic>) {
        final Map<String, dynamic> data = Map<String, dynamic>.from(body);
        final bool ok = resp.statusCode == 200 && data['success'] == true;
        final String? error = data['error']?.toString();
        final String message = data['message']?.toString() ??
            (ok ? 'Connection successful' : (error ?? 'Connection failed'));
        return <String, dynamic>{
          ...data,
          'success': ok,
          'message': message,
          if (error != null) 'error': error,
          'platform': platformType,
          'response_time': DateTime.now().millisecondsSinceEpoch,
        };
      }

      final ok = resp.statusCode == 200;
      return <String, dynamic>{
        'success': ok,
        'message': ok ? 'Connection successful' : 'Connection failed',
        'platform': platformType,
        'response_time': DateTime.now().millisecondsSinceEpoch,
      };
    } catch (e) {
      // Handle DioException with response data (e.g., HTTP 400, 500 errors)
      String errorMessage = 'Test failed: $e';
      if (e is DioException && e.response != null) {
        final responseData = e.response!.data;
        if (responseData is Map<String, dynamic>) {
          final detail = responseData['detail']?.toString();
          final errorMsg = responseData['message']?.toString();
          if (detail != null && detail.isNotEmpty) {
            errorMessage = detail;
          } else if (errorMsg != null && errorMsg.isNotEmpty) {
            errorMessage = errorMsg;
          }
        }
      }
      return <String, dynamic>{
        'success': false,
        'message': errorMessage,
        'platform': platformType,
      };
    }
  }

  /// 测试MinerU连接（专用后端代理）
  /// Supports both cloud (mineru) and local (mineru_local) deployments
  Future<Map<String, dynamic>> testMinerU(
    String apiKey, {
    String platformType = 'mineru',
    String? baseUrl,
  }) async {
    try {
      // 通过后端代理测试，避免浏览器跨域与密钥暴露
      final cfg = ConfigService();
      final authHeader = cfg.authorizationHeader;

      final dio = Dio(
        BaseOptions(
          baseUrl: AppConfig.baseUrl,
          headers: <String, dynamic>{
            'Content-Type': 'application/json',
            if (authHeader != null) 'Authorization': authHeader,
            ...ConfigService.desktopBackendHeaders,
          },
        ),
      );

      // Build request payload
      final payload = <String, dynamic>{
        'platform_type': platformType,
        if (apiKey.isNotEmpty) 'api_key': apiKey,
        if (baseUrl != null) 'base_url': baseUrl,
      };

      // Use the unified test endpoint which supports both cloud and local
      final resp = await dio.post(
        '/api/v1/auth/test-ai-platform',
        data: payload,
      );

      final ok = resp.statusCode == 200 && (resp.data?['success'] == true);
      final message = resp.data?['message']?.toString() ??
          (ok ? 'MinerU connection successful' : 'MinerU connection failed');

      return <String, dynamic>{
        'success': ok,
        'message': message,
        if (resp.data?['mineru_version'] != null)
          'mineru_version': resp.data['mineru_version'],
        if (resp.data?['api_version'] != null)
          'api_version': resp.data['api_version'],
        if (resp.data?['model_version'] != null)
          'model_version': resp.data['model_version'],
        'platform': platformType,
        'response_time': DateTime.now().millisecondsSinceEpoch,
      };
    } catch (e) {
      return <String, dynamic>{
        'success': false,
        'message': _parseMinerUError(e),
        'platform': platformType,
      };
    }
  }

  /// 通用AI平台测试方法（统一后端代理）
  Future<Map<String, dynamic>> testPlatform(
    String platform,
    String apiKey, {
    String? baseUrl,
    String? modelName,
    int? testConnectTimeout,
    int? testRequestTimeout,
  }) async {
    final p = platform.toLowerCase();
    // MinerU and PaddleOCR platforms use their own test endpoints
    if (p == 'mineru' || p == 'mineru_local') {
      return testMinerU(apiKey, platformType: p, baseUrl: baseUrl);
    }
    if (p == 'paddle' || p == 'paddle_local') {
      return testPaddleOCR(apiKey, platformType: p, baseUrl: baseUrl);
    }
    return _testViaBackend(
      platformType: p,
      apiKey: apiKey,
      baseUrl: baseUrl,
      modelName: modelName,
      testConnectTimeout: testConnectTimeout,
      testRequestTimeout: testRequestTimeout,
    );
  }

  /// Test PaddleOCR connection (backend proxy)
  Future<Map<String, dynamic>> testPaddleOCR(
    String apiKey, {
    String platformType = 'paddle',
    String? baseUrl,
  }) async {
    // PaddleOCR testing goes through the unified backend endpoint
    return _testViaBackend(
      platformType: platformType,
      apiKey: apiKey,
      baseUrl: baseUrl,
    );
  }

  // 仅保留 MinerU 错误解析，其它平台错误由后端统一处理

  /// 解析MinerU错误信息
  String _parseMinerUError(error) {
    if (error.toString().contains('401')) {
      return 'API Key无效或已过期。请检查您的MinerU API Key是否正确。';
    } else if (error.toString().contains('403')) {
      return 'API Key权限不足。请检查您的MinerU账户权限。';
    } else if (error.toString().contains('429')) {
      return 'API调用频率超限。请稍后再试或检查您的MinerU配额。';
    } else if (error.toString().contains('500')) {
      return 'MinerU服务器内部错误。请稍后再试。';
    } else if (error.toString().contains('SocketException') ||
        error.toString().contains('NetworkException')) {
      return '网络连接失败。请检查您的网络连接。';
    } else if (error.toString().contains('TimeoutException')) {
      return '请求超时。请检查您的网络连接或稍后再试。';
    } else if (error.toString().contains('FormatException')) {
      return 'API Key格式错误。请检查您的MinerU API Key格式。';
    } else {
      return '连接失败。请检查您的API Key和网络连接。';
    }
  }
}
