// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:dio/dio.dart';
import 'config_service.dart';
import '../../features/settings/models/language_model_config.dart';
import '../../app/app_config.dart';

class AnonymizationSettingsService {
  static final String _baseUrl = AppConfig.baseUrl;

  Dio _buildAuthedDio() {
    final ConfigService cfg = ConfigService();
    final String? authHeader = cfg.authorizationHeader;
    return Dio(
      BaseOptions(
        baseUrl: _baseUrl,
        headers: <String, dynamic>{
          'Content-Type': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
        },
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
      ),
    );
  }

  /// Get all language model configurations
  Future<Map<String, dynamic>> getLanguageModels() async {
    try {
      final Dio dio = _buildAuthedDio();
      final Response<dynamic> response =
          await dio.get('/api/settings/anonymize/models');
      final Map<String, dynamic> data = response.data as Map<String, dynamic>;
      return <String, dynamic>{
        'success': true,
        'models': data['models'] ?? <dynamic, dynamic>{},
        'options': data['options'] ?? <dynamic, dynamic>{},
        'model_status': data['model_status'] ??
            <dynamic, dynamic>{}, // Include model_status in response
      };
    } catch (e) {
      return <String, dynamic>{
        'success': false,
        'message': 'Error loading language models: $e',
      };
    }
  }

  /// Save language model configuration
  Future<Map<String, dynamic>> saveLanguageModel(
    String language,
    LanguageModelConfig config,
  ) async {
    try {
      final Dio dio = _buildAuthedDio();
      final Map<String, Object?> payload = <String, Object?>{
        'language': language,
        'preferred': config.preferred,
        'models_dir': config.modelsDir,
        'fallback': config.fallback,
      };

      final Response<dynamic> response =
          await dio.post('/api/settings/anonymize/models', data: payload);
      final Map<String, dynamic> data = response.data as Map<String, dynamic>;
      return <String, dynamic>{
        'success': data['ok'] ?? false,
        'message': data['ok'] == true
            ? 'Saved successfully'
            : (data['message'] ?? 'Save failed'),
      };
    } catch (e) {
      return <String, dynamic>{
        'success': false,
        'message': 'Error saving language model: $e',
      };
    }
  }

  /// Test model
  Future<Map<String, dynamic>> testModel(
    String language,
    String modelName,
    String? modelsDir,
    String? testText,
  ) async {
    try {
      final Dio dio = _buildAuthedDio();
      final Map<String, String> payload = <String, String>{
        'model_name': modelName,
        if (modelsDir != null) 'models_dir': modelsDir,
        if (testText != null) 'text': testText,
      };

      final Response<dynamic> response =
          await dio.post('/api/settings/anonymize/test', data: payload);
      final Map<String, dynamic> data = response.data as Map<String, dynamic>;
      return <String, dynamic>{
        'success': data['ok'] ?? false,
        'message': data['message'] ?? '',
        'entitiesCount': data['entitiesCount'],
        'remediation': data['remediation'],
      };
    } catch (e) {
      return <String, dynamic>{
        'success': false,
        'message': 'Error testing model: $e',
      };
    }
  }

  /// Download model
  Future<Map<String, dynamic>> downloadModel(
    String language,
    String modelName,
    String? modelsDir, {
    Function(double)? onProgress,
  }) async {
    try {
      final Dio dio = _buildAuthedDio();
      final Map<String, String> payload = <String, String>{
        'language': language,
        'model_name': modelName,
        if (modelsDir != null) 'models_dir': modelsDir,
      };

      // Note: Backend API might not support progress callback
      // For now, we'll simulate progress or wait for completion
      final Response<dynamic> response = await dio.post(
        '/api/settings/anonymize/download',
        data: payload,
        onSendProgress: onProgress != null
            ? (int sent, int total) {
                if (total > 0) {
                  onProgress((sent / total * 100).clamp(0, 100));
                }
              }
            : null,
      );
      final Map<String, dynamic> data = response.data as Map<String, dynamic>;
      return <String, dynamic>{
        'success': data['ok'] ?? false,
        'message': data['message'] ?? '',
        'status': data['status'], // 'exists' or 'downloaded'
        'dir': data['dir'],
      };
    } catch (e) {
      return <String, dynamic>{
        'success': false,
        'message': 'Error downloading model: $e',
      };
    }
  }
}
