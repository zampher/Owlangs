// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../utils/app_logger.dart';
import 'config_service.dart';

// Conditional import: only use dart:io on non-web platforms
import 'dart:io' if (dart.library.html) '../utils/io_file_stub.dart' show File;

/// Translation statistics data model
class TranslationStats {
  const TranslationStats({
    this.documentCount = 0,
    this.pageCount = 0,
    this.lastUpdated,
  });

  factory TranslationStats.fromJson(Map<String, dynamic> json) =>
      TranslationStats(
        documentCount: json['document_count'] as int? ?? 0,
        pageCount: json['page_count'] as int? ?? 0,
        lastUpdated: json['last_updated'] != null
            ? DateTime.tryParse(json['last_updated'] as String)
            : null,
      );

  final int documentCount;
  final int pageCount;
  final DateTime? lastUpdated;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'document_count': documentCount,
        'page_count': pageCount,
        'last_updated': lastUpdated?.toIso8601String(),
      };

  TranslationStats copyWith({
    int? documentCount,
    int? pageCount,
    DateTime? lastUpdated,
  }) =>
      TranslationStats(
        documentCount: documentCount ?? this.documentCount,
        pageCount: pageCount ?? this.pageCount,
        lastUpdated: lastUpdated ?? this.lastUpdated,
      );
}

/// Service for managing translation statistics
class TranslationStatsService {
  factory TranslationStatsService() => _instance;
  TranslationStatsService._internal();
  static final TranslationStatsService _instance =
      TranslationStatsService._internal();

  void _log(String message, {LogLevel level = LogLevel.debug}) {
    AppLogger.log('TranslationStatsService', message, level: level);
  }

  static const String _recordedFlowsKey = 'recorded_translation_flows';
  TranslationStats? _cachedStats;
  Set<String>? _recordedFlows;
  String? _backendStatsPath; // Cached backend path for static.json

  /// Get current statistics from backend file
  Future<TranslationStats> getStats() async {
    if (_cachedStats != null) {
      return _cachedStats!;
    }

    try {
      if (kIsWeb) {
        // Web: use HTTP API to read from backend
        return await _getStatsFromApi();
      } else {
        // Desktop: use file system
        final file = await _getStatsFile();
        if (await file.exists()) {
          final content = await file.readAsString();
          final Map<String, dynamic> data =
              jsonDecode(content) as Map<String, dynamic>;
          // Extract translation_stats from the JSON structure
          final statsData = data['translation_stats'] as Map<String, dynamic>?;
          if (statsData != null) {
            _cachedStats = TranslationStats.fromJson(statsData);
            // Load recorded flows as well
            final flowsList = data[_recordedFlowsKey] as List<dynamic>?;
            _recordedFlows =
                flowsList?.map((e) => e.toString()).toSet() ?? <String>{};
            return _cachedStats!;
          }
        }

        // If no stats found, return default (backend will initialize file on startup)
        _log(
          'Stats file not found, using defaults (backend will initialize on startup)',
        );
        return const TranslationStats();
      }
    } catch (e) {
      _log('Error loading stats: $e', level: LogLevel.error);
      return const TranslationStats();
    }
  }

  /// Get statistics from backend API (Web only)
  Future<TranslationStats> _getStatsFromApi({int maxRetries = 2}) async {
    // Reuse ConfigService's shared Dio to avoid creating redundant HTTP connections
    // that compete for Chrome's limited per-origin connection pool.
    final dio = ConfigService().dio;

    // Retry logic for startup requests (backend may not be ready immediately)
    for (int attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        final response = await dio.get('/api/settings/static-json');
        if (response.statusCode == 200 &&
            response.data is Map<String, dynamic>) {
          final data = response.data as Map<String, dynamic>;
          if (data['ok'] == true) {
            final statsData =
                data['translation_stats'] as Map<String, dynamic>?;
            if (statsData != null) {
              _cachedStats = TranslationStats.fromJson(statsData);
              // Load recorded flows
              final flowsList = data[_recordedFlowsKey] as List<dynamic>?;
              _recordedFlows =
                  flowsList?.map((e) => e.toString()).toSet() ?? <String>{};
              return _cachedStats!;
            }
          }
        }
      } catch (e) {
        // Log error for this attempt
        if (attempt < maxRetries) {
          _log(
            'Failed to get stats from API (attempt ${attempt + 1}/${maxRetries + 1}): $e. Retrying...',
            level: LogLevel.warn,
          );
          // Wait before retry (exponential backoff: 2s, 4s)
          // Increased delay to give backend more time to initialize
          await Future.delayed(Duration(seconds: (attempt + 1) * 2));
        } else {
          // Last attempt failed
          _log(
            'Failed to get stats from API after ${maxRetries + 1} attempts: $e',
            level: LogLevel.warn,
          );
        }
      }
    }
    // All retries exhausted, return default stats
    return const TranslationStats();
  }

  /// Save statistics to backend file
  Future<void> saveStats(TranslationStats stats) async {
    try {
      _cachedStats = stats;

      if (kIsWeb) {
        // Web: use HTTP API to write to backend
        await _saveStatsToApi(stats);
      } else {
        // Desktop: use file system
        final file = await _getStatsFile();

        // Read existing file to preserve other data (like recorded flows)
        Map<String, dynamic> data;
        if (await file.exists()) {
          final content = await file.readAsString();
          data = jsonDecode(content) as Map<String, dynamic>;
        } else {
          data = <String, dynamic>{};
        }

        // Update translation_stats (backend does not store app version in static.json)
        data['translation_stats'] = stats.toJson();
        data[_recordedFlowsKey] = (_recordedFlows ?? <String>{}).toList();

        // Ensure directory exists
        await file.parent.create(recursive: true);

        // Write to backend file
        await file.writeAsString(
          const JsonEncoder.withIndent('  ').convert(data),
        );
        _log('Statistics saved successfully to backend file');
      }
    } catch (e) {
      _log('Error saving stats: $e', level: LogLevel.error);
    }
  }

  /// Save statistics to backend API (Web only)
  Future<void> _saveStatsToApi(TranslationStats stats) async {
    try {
      final dio = ConfigService().dio;

      // Read current data first to preserve other fields
      Map<String, dynamic> data;
      try {
        final getResponse = await dio.get('/api/settings/static-json');
        if (getResponse.statusCode == 200 &&
            getResponse.data is Map<String, dynamic>) {
          final getData = getResponse.data as Map<String, dynamic>;
          if (getData['ok'] == true) {
            data = Map<String, dynamic>.from(getData);
            // Remove 'ok' field if present
            data.remove('ok');
          } else {
            data = <String, dynamic>{};
          }
        } else {
          data = <String, dynamic>{};
        }
      } catch (e) {
        _log(
          'Failed to read current stats from API, using empty: $e',
          level: LogLevel.warn,
        );
        data = <String, dynamic>{};
      }

      // Update translation_stats (backend strips version on save; no need to send it)
      data['translation_stats'] = stats.toJson();
      data[_recordedFlowsKey] = (_recordedFlows ?? <String>{}).toList();

      // Write updated data
      final response = await dio.put('/api/settings/static-json', data: data);
      if (response.statusCode == 200 && response.data is Map<String, dynamic>) {
        final responseData = response.data as Map<String, dynamic>;
        if (responseData['ok'] == true) {
          _log('Statistics saved successfully via API');
        } else {
          throw Exception('API returned ok=false: ${responseData['error']}');
        }
      } else {
        throw Exception('Unexpected response status: ${response.statusCode}');
      }
    } catch (e) {
      _log('Failed to save stats via API: $e', level: LogLevel.error);
      rethrow;
    }
  }

  /// Clear cache to force reload
  void clearCache() {
    _cachedStats = null;
    _recordedFlows = null;
  }

  /// Get backend static.json path from API
  Future<String?> _getBackendStatsPath() async {
    if (_backendStatsPath != null) {
      return _backendStatsPath;
    }

    try {
      final dio = ConfigService().dio;

      final response = await dio.get('/api/settings/paths');
      if (response.statusCode == 200 && response.data is Map<String, dynamic>) {
        final data = response.data as Map<String, dynamic>;
        if (data['ok'] == true && data['static_json_path'] != null) {
          _backendStatsPath = data['static_json_path'] as String;
          _log('Got backend stats path: $_backendStatsPath');
          return _backendStatsPath;
        }
      }
    } catch (e) {
      _log('Failed to get backend stats path: $e', level: LogLevel.warn);
    }

    return null;
  }

  /// Get stats file path from backend (Desktop only)
  /// Always uses backend path for shared multi-user statistics
  /// Helper function to create File instance (handles web/desktop differences)
  /// Note: This should only be called when kIsWeb is false
  File _createFile(String path) {
    if (kIsWeb) {
      throw UnsupportedError('File operations not supported on web');
    }
    // File(path) works on desktop (dart:io) and stub (accepts optional path)
    return File(path);
  }

  /// Backend handles file initialization on startup
  /// Note: This method should only be called when kIsWeb is false
  Future<File> _getStatsFile() async {
    // This should never be called on Web, but add a check for safety
    if (kIsWeb) {
      throw UnsupportedError(
        'File operations not supported on Web. Use API methods instead.',
      );
    }

    // Get backend path (shared across all users)
    final backendPath = await _getBackendStatsPath();
    if (backendPath != null) {
      final file = _createFile(backendPath);
      // Backend initializes file on startup, so we don't need to initialize here
      // Just return the file path
      return file;
    }

    // If backend path unavailable, throw error (should not happen in normal operation)
    throw Exception(
      'Backend stats path not available. Please ensure backend is running.',
    );
  }

  /// Get recorded flows from backend file
  Future<Set<String>> _getRecordedFlows() async {
    if (_recordedFlows != null) {
      return _recordedFlows!;
    }

    try {
      if (kIsWeb) {
        // Web: flows are loaded together with stats in _getStatsFromApi
        // If not loaded yet, try to get from API
        if (_cachedStats == null) {
          await _getStatsFromApi();
        }
        return _recordedFlows ?? <String>{};
      } else {
        // Desktop: use file system
        final file = await _getStatsFile();
        if (await file.exists()) {
          final content = await file.readAsString();
          final Map<String, dynamic> data =
              jsonDecode(content) as Map<String, dynamic>;
          final flowsList = data[_recordedFlowsKey] as List<dynamic>?;
          if (flowsList != null) {
            _recordedFlows = flowsList.map((e) => e.toString()).toSet();
            return _recordedFlows!;
          }
        }
      }
    } catch (e) {
      _log('Error loading recorded flows: $e', level: LogLevel.warn);
    }

    _recordedFlows = <String>{};
    return _recordedFlows!;
  }

  /// Save recorded flows to backend file
  Future<void> _saveRecordedFlows(Set<String> flows) async {
    try {
      _recordedFlows = flows;

      if (kIsWeb) {
        // Web: save via API (flows are saved together with stats)
        // Just update the cache, actual save happens in saveStats
        return;
      } else {
        // Desktop: use file system
        final file = await _getStatsFile();

        // Read existing file to preserve other data
        Map<String, dynamic> data;
        if (await file.exists()) {
          final content = await file.readAsString();
          data = jsonDecode(content) as Map<String, dynamic>;
        } else {
          data = <String, dynamic>{
            'translation_stats': const TranslationStats().toJson(),
          };
        }

        data[_recordedFlowsKey] = flows.toList();

        // Ensure directory exists
        await file.parent.create(recursive: true);

        await file.writeAsString(
          const JsonEncoder.withIndent('  ').convert(data),
        );
      }
    } catch (e) {
      _log('Error saving recorded flows: $e', level: LogLevel.error);
    }
  }

  /// Update statistics (add document and pages) for a specific flow
  /// Only records once per flow to avoid duplicate counting
  Future<void> recordTranslationFlow({
    required String flowId,
    int pageCount = 0,
  }) async {
    try {
      final recordedFlows = await _getRecordedFlows();

      // Check if this flow has already been recorded
      if (recordedFlows.contains(flowId)) {
        _log('Flow $flowId already recorded, skipping');
        return;
      }

      // Record this flow
      recordedFlows.add(flowId);
      await _saveRecordedFlows(recordedFlows);

      // Update statistics
      final currentStats = await getStats();
      final updatedStats = currentStats.copyWith(
        documentCount: currentStats.documentCount + 1,
        pageCount: currentStats.pageCount + pageCount,
        lastUpdated: DateTime.now(),
      );
      await saveStats(updatedStats);
      _log('Recorded translation flow $flowId: +1 document, +$pageCount pages');
    } catch (e) {
      _log('Error recording translation flow: $e', level: LogLevel.error);
    }
  }

  /// Update statistics (add document and pages)
  /// Deprecated: Use recordTranslationFlow instead to avoid duplicate counting
  @Deprecated('Use recordTranslationFlow instead')
  Future<void> addTranslation({
    int documentCount = 1,
    int pageCount = 0,
  }) async {
    final currentStats = await getStats();
    final updatedStats = currentStats.copyWith(
      documentCount: currentStats.documentCount + documentCount,
      pageCount: currentStats.pageCount + pageCount,
      lastUpdated: DateTime.now(),
    );
    await saveStats(updatedStats);
  }

  /// Reset statistics
  Future<void> resetStats() async {
    const defaultStats = TranslationStats();
    await saveStats(defaultStats);
  }

  /// Ensure stats file exists (called at app startup)
  /// Note: Backend handles file initialization on startup, this just validates the file
  Future<void> ensureInitialized() async {
    try {
      if (kIsWeb) {
        // Web: just try to load stats from API (will create defaults if needed)
        await _getStatsFromApi();
      } else {
        // Desktop: validate file
        final file = await _getStatsFile();
        if (await file.exists()) {
          // Validate and migrate if needed
          await _validateAndMigrate(file);
        } else {
          // Backend should have initialized the file, but if not, log a warning
          _log(
            'Stats file not found at startup. Backend should initialize it automatically.',
            level: LogLevel.warn,
          );
        }
      }
    } catch (e) {
      _log('Error ensuring stats initialization: $e', level: LogLevel.error);
    }
  }

  /// Validate and migrate stats file if schema changed (Desktop only)
  /// Note: This method should only be called when kIsWeb is false
  Future<void> _validateAndMigrate(File file) async {
    try {
      final content = await file.readAsString();
      final Map<String, dynamic> data =
          jsonDecode(content) as Map<String, dynamic>;

      // Check version and migrate if needed
      final statsData = data['translation_stats'] as Map<String, dynamic>?;

      if (statsData == null) {
        // Missing translation_stats, create it with defaults
        data['translation_stats'] = const TranslationStats().toJson();
        await file.writeAsString(
          const JsonEncoder.withIndent('  ').convert(data),
        );
        _log('Migrated stats file: added missing translation_stats');
      } else {
        // Validate fields and add missing ones with defaults
        final currentStats = TranslationStats.fromJson(statsData);
        final updatedStats = currentStats.copyWith(
          documentCount: currentStats.documentCount,
          pageCount: currentStats.pageCount,
          lastUpdated: currentStats.lastUpdated,
        );

        // Check if any fields are missing or need migration
        final updatedData = updatedStats.toJson();
        bool needsUpdate = false;

        for (final key in updatedData.keys) {
          if (!statsData.containsKey(key)) {
            statsData[key] = updatedData[key];
            needsUpdate = true;
          }
        }

        if (needsUpdate) {
          data['translation_stats'] = statsData;
          await file.writeAsString(
            const JsonEncoder.withIndent('  ').convert(data),
          );
          _log('Migrated stats file: added missing fields');
        }
      }
    } catch (e) {
      _log('Error validating/migrating stats file: $e', level: LogLevel.error);
    }
  }
}
