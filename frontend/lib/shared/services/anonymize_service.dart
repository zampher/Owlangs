// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../core/models/api_response.dart';
import '../../core/services/api_service.dart';
import '../../app/app_config.dart';
import '../services/config_service.dart';

class AnonymizeService {
  // Use typed ApiService wrapper to keep consistency with app
  final ApiService _api = ApiService();

  /// Create a new anonymize workflow
  /// Returns: { "success": true, "workflow_id": "...", "filename": "...", "file_size": ... }
  Future<Map<String, dynamic>> createWorkflow(
    Uint8List fileBytes,
    String fileName,
  ) async {
    // Use FormData for file upload
    final formData = FormData.fromMap(<String, dynamic>{
      'file': MultipartFile.fromBytes(
        fileBytes,
        filename: fileName,
      ),
    });

    // Backend returns data directly, not in ApiResponse format
    // So we need to use Dio directly to get the raw response
    // Get authentication header from ConfigService
    final configService = ConfigService();
    final authHeader = configService.authorizationHeader;

    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        connectTimeout: AppConfig.longRequestTimeout,
        receiveTimeout: AppConfig.longRequestTimeout,
        headers: <String, dynamic>{
          'Accept': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
        },
      ),
    );

    try {
      final response = await dio.post<Map<String, dynamic>>(
        '/api/anonymize/create-workflow',
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
          receiveTimeout: AppConfig.longRequestTimeout,
          sendTimeout: AppConfig.longRequestTimeout,
        ),
      );

      // Backend returns: {"success": true, "workflow_id": "...", ...}
      // response.data is the direct JSON object
      if (response.data != null && response.data is Map<String, dynamic>) {
        return response.data!;
      }

      debugPrint(
        '[AnonymizeService] createWorkflow: response.data is null or invalid',
      );
      return <String, dynamic>{};
    } catch (e) {
      debugPrint('[AnonymizeService] createWorkflow error: $e');
      rethrow;
    }
  }

  Future<void> runAnonymize(String taskId) async {
    await _api.post('/service/tasks/$taskId/anonymize');
  }

  /// Run anonymize with Quick Settings configuration
  /// workflowId: The anonymize workflow ID
  /// config: Quick Settings configuration (enabled_entities, mode, confidence_threshold, detection_language)
  Future<Map<String, dynamic>> runAnonymizeWithConfig(
    String workflowId, {
    List<String>? enabledEntities,
    String? mode,
    double? confidenceThreshold,
    String? detectionLanguage,
  }) async {
    final payload = <String, dynamic>{};
    if (enabledEntities != null) {
      payload['enabled_entities'] = enabledEntities;
    }
    if (mode != null) {
      payload['mode'] = mode;
    }
    if (confidenceThreshold != null) {
      payload['confidence_threshold'] = confidenceThreshold;
    }
    if (detectionLanguage != null && detectionLanguage != 'auto') {
      payload['detection_language'] = detectionLanguage;
    }

    // Use long timeout for anonymization operation as it may take time
    final response = await _api.post<Map<String, dynamic>>(
      '/api/anonymize/run/$workflowId',
      data: payload.isNotEmpty ? payload : null,
      options: Options(
        receiveTimeout: AppConfig.longRequestTimeout,
      ),
    );

    // Backend returns: {"success": True, "data": {...}} or {"success": False, "message": "..."}
    final responseData = response.data ?? <String, dynamic>{};
    if (responseData['success'] == true && responseData['data'] != null) {
      return responseData['data'] as Map<String, dynamic>;
    } else if (responseData['success'] == false) {
      // Return error structure for caller to handle
      return <String, dynamic>{
        'error': responseData['message'] ?? 'Anonymization failed',
      };
    }
    // Fallback: return raw response (for backward compatibility)
    return responseData;
  }

  /// New unified RUN endpoint (no backward compatibility): returns expanded entities and rebuilt outputs
  /// POST /api/anonymize/run/{workflowId}
  /// Payload: { enabled_entities, mode, confidence_threshold, detection_language, custom_placeholder?, segment_boundaries?, segment_text? }
  /// Returns: { original_text, entities_detected, entities_expanded, mappings, anonymized_text, segments, segment_boundaries, stats }
  Future<Map<String, dynamic>> runUnified(
    String workflowId, {
    required List<String> enabledEntities,
    required String mode,
    double? confidenceThreshold,
    String? detectionLanguage,
    String? customPlaceholder,
    List<int>? segmentBoundaries,
    String? segmentText,
  }) async {
    final payload = <String, dynamic>{
      'enabled_entities': enabledEntities,
      'mode': mode,
      if (confidenceThreshold != null)
        'confidence_threshold': confidenceThreshold,
      if (detectionLanguage != null && detectionLanguage.isNotEmpty)
        'detection_language': detectionLanguage,
      if (customPlaceholder != null && customPlaceholder.isNotEmpty)
        'custom_placeholder': customPlaceholder,
      if (segmentBoundaries != null && segmentBoundaries.isNotEmpty)
        'segment_boundaries': segmentBoundaries,
      if (segmentText != null && segmentText.isNotEmpty)
        'segment_text': segmentText,
    };

    // Backend returns data directly (not wrapped in ApiResponse), so use Dio directly
    final configService = ConfigService();
    final authHeader = configService.authorizationHeader;

    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        connectTimeout: AppConfig.longRequestTimeout,
        receiveTimeout: AppConfig.longRequestTimeout,
        headers: <String, dynamic>{
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
        },
      ),
    );

    try {
      final response = await dio.post<Map<String, dynamic>>(
        '/api/anonymize/run/$workflowId',
        data: payload,
        options: Options(receiveTimeout: AppConfig.longRequestTimeout),
      );
      final data = response.data ?? <String, dynamic>{};
      // Unwrap {success, data} contract
      if (data['success'] == true && data['data'] is Map<String, dynamic>) {
        return data['data'] as Map<String, dynamic>;
      }
      if (data['success'] == false) {
        return <String, dynamic>{
          'error': data['message'] ?? 'Anonymization failed',
        };
      }
      // Fallback to raw data
      return data;
    } catch (e) {
      debugPrint('[AnonymizeService] runUnified error: $e');
      rethrow;
    }
  }

  /// Expand known entities to all occurrences on backend
  /// POST /api/anonymize/expand-entities/{workflowId}
  Future<Map<String, dynamic>> expandEntities(
    String workflowId, {
    required List<Map<String, dynamic>> entities, // [{text,type}]
    String? detectionLanguage,
    List<String>? enabledEntities, // Optional: filter by enabled entity types
  }) async {
    final payload = <String, dynamic>{
      'entities': entities,
      if (detectionLanguage != null && detectionLanguage.isNotEmpty)
        'detection_language': detectionLanguage,
      if (enabledEntities != null && enabledEntities.isNotEmpty)
        'enabled_entities': enabledEntities,
    };
    final res = await _api.post<Map<String, dynamic>>(
      '/api/anonymize/expand-entities/$workflowId',
      data: payload,
      options: Options(receiveTimeout: AppConfig.longRequestTimeout),
    );
    return res.data ?? <String, dynamic>{};
  }

  /// Rebuild anonymized outputs from expanded entities
  /// POST /api/anonymize/rebuild/{workflowId}
  Future<Map<String, dynamic>> rebuildUnified(
    String workflowId, {
    required List<Map<String, dynamic>>
        entitiesExpanded, // [{text,type,start,end}]
    required String mode,
    String? customPlaceholder,
  }) async {
    final payload = <String, dynamic>{
      'entities_expanded': entitiesExpanded,
      'mode': mode,
      if (customPlaceholder != null && customPlaceholder.isNotEmpty)
        'custom_placeholder': customPlaceholder,
    };
    final res = await _api.post<Map<String, dynamic>>(
      '/api/anonymize/rebuild/$workflowId',
      data: payload,
      options: Options(receiveTimeout: AppConfig.longRequestTimeout),
    );
    return res.data ?? <String, dynamic>{};
  }

  Future<void> runDeAnonymize(String taskId) async {
    await _api.post('/service/tasks/$taskId/deanonymize');
  }

  /// Get anonymization progress
  /// Returns raw Map: { workflow_id, percent, phase, message, updated_at }
  Future<Map<String, dynamic>> getProgress(String workflowId) async {
    debugPrint('[AnonymizeService] getProgress begin: workflowId=$workflowId');
    // First try via shared ApiService (_api) with short timeouts (inherits auth/cookies/proxies)
    try {
      final res = await _api.get<Map<String, dynamic>>(
        '/api/anonymize/progress/$workflowId',
        options: Options(
          receiveTimeout: const Duration(seconds: 6),
          sendTimeout: const Duration(seconds: 6),
        ),
      );
      final data = res.data ?? <String, dynamic>{};
      debugPrint('[AnonymizeService] getProgress end (via _api): data=$data');
      // If _api unwrap produced empty {}, fallback to Dio direct to fetch raw dict
      if (data.isNotEmpty) return data;
    } catch (e, st) {
      debugPrint('[AnonymizeService] getProgress via _api failed: $e');
      debugPrint('[AnonymizeService] stackTrace: $st');
    }
    // Fallback to direct Dio with explicit short timeouts
    try {
      final configService = ConfigService();
      final authHeader = configService.authorizationHeader;
      final cancelToken = CancelToken();
      final dio = Dio(
        BaseOptions(
          baseUrl: AppConfig.baseUrl,
          headers: <String, dynamic>{
            'Accept': 'application/json',
            if (authHeader != null) 'Authorization': authHeader,
          },
          connectTimeout: const Duration(seconds: 6),
          receiveTimeout: const Duration(seconds: 6),
        ),
      );
      final res = await dio
          .get<Map<String, dynamic>>(
            '/api/anonymize/progress/$workflowId',
            cancelToken: cancelToken,
          )
          .timeout(const Duration(seconds: 8));
      final data = res.data ?? <String, dynamic>{};
      debugPrint(
        '[AnonymizeService] getProgress end (via Dio): statusCode=${res.statusCode}, data=$data',
      );
      return data;
    } on TimeoutException catch (e, stackTrace) {
      debugPrint('[AnonymizeService] getProgress timeout (via Dio): $e');
      debugPrint('[AnonymizeService] getProgress stackTrace: $stackTrace');
      return <String, dynamic>{};
    } catch (e, stackTrace) {
      debugPrint('[AnonymizeService] getProgress error (via Dio): $e');
      debugPrint('[AnonymizeService] getProgress stackTrace: $stackTrace');
      return <String, dynamic>{};
    }
  }

  /// Cancel anonymization
  Future<bool> cancel(String workflowId) async {
    final configService = ConfigService();
    final authHeader = configService.authorizationHeader;
    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        headers: <String, dynamic>{
          'Accept': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
        },
        receiveTimeout: AppConfig.requestTimeout,
      ),
    );
    final res = await dio
        .post<Map<String, dynamic>>('/api/anonymize/cancel/$workflowId');
    return (res.data?['success'] as bool?) ?? false;
  }

  /// Detect language for a workflow
  /// Returns: { "workflow_id": "...", "detected_language": "zh", "suggested_model": "...", "available_models": [...] }
  Future<Map<String, dynamic>> detectLanguage(String workflowId) async {
    final response = await _api.get<Map<String, dynamic>>(
      '/api/anonymize/detect-language/$workflowId',
    );
    return response.data ?? <String, dynamic>{};
  }

  /// Download anonymized document
  /// Returns: File bytes as Uint8List
  Future<Uint8List> downloadAnonymized(
    String workflowId, {
    String? format,
  }) async {
    // Get authentication header from ConfigService
    final configService = ConfigService();
    final authHeader = configService.authorizationHeader;

    // Use Dio directly for file download with ResponseType.bytes
    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        headers: <String, dynamic>{
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
        },
      ),
    );

    final queryParams =
        format != null ? <String, String>{'format': format} : null;
    final response = await dio.get<List<int>>(
      '/api/anonymize/download-anonymized/$workflowId',
      queryParameters: queryParams,
      options: Options(
        responseType: ResponseType.bytes,
      ),
    );

    return Uint8List.fromList(response.data ?? <int>[]);
  }

  /// Rebuild document from anonymized segments
  /// segments: List of segment data with segment_index and anonymized_text
  /// Returns: File bytes as Uint8List
  Future<Uint8List> rebuildDocumentFromSegments(
    String workflowId,
    List<Map<String, dynamic>> segments,
  ) async {
    // Get authentication header from ConfigService
    final configService = ConfigService();
    final authHeader = configService.authorizationHeader;

    // Use Dio directly for file download with ResponseType.bytes
    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        headers: <String, dynamic>{
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
        },
      ),
    );

    final response = await dio.post<List<int>>(
      '/api/anonymize/rebuild-document/$workflowId',
      data: segments,
      options: Options(
        responseType: ResponseType.bytes,
      ),
    );

    return Uint8List.fromList(response.data ?? <int>[]);
  }
}
