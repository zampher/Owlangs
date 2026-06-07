import 'dart:async';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'config_service.dart';

/// Settings save state
enum SaveState { idle, loading, success, error }

/// Unified settings service with debounce and batch saving
class SettingsService {
  factory SettingsService() => _instance;
  SettingsService._internal();
  static final SettingsService _instance = SettingsService._internal();

  final ConfigService _configService = ConfigService();
  final Map<String, dynamic> _pendingChanges = <String, dynamic>{};
  Timer? _debounceTimer;
  final StreamController<SaveState> _saveStateController =
      StreamController<SaveState>.broadcast();

  // Save state stream (for UI listening)
  Stream<SaveState> get saveState => _saveStateController.stream;
  SaveState _currentState = SaveState.idle;

  // Notification context for SnackBar
  BuildContext? _notificationContext;
  StreamSubscription<SaveState>? _stateSubscription;

  // Retry state
  int _retryCount = 0;

  // Track if a save operation is currently in progress
  bool _isSaving = false;

  // Configuration key type mapping
  // Maps setting keys to their configuration type (global/user/sensitive)
  static const Map<String, String> _configTypeMap = <String, String>{
    // Global settings (admin only)
    'ai_platforms_default_platform': 'global',
    'defaultPlatform': 'global',
    'parsingEngine': 'global',
    'translator_convert_engine': 'global',
    'translator_mineru_model_version': 'global',
    'translator_formula_ocr': 'global',
    'translator_table_ocr': 'global',
    'translator_skip_translate': 'global',
    'translator_pdf_split_enabled': 'global',
    'translator_pdf_split_max_pages': 'global',
    'translator_pdf_split_max_workers': 'global',
    'translator_request_retry_count': 'global',

    // User settings (all users)
    'temperature': 'user',
    'thinking': 'user',
    'concurrent': 'user',
    'timeout': 'user',
    'retry': 'user',
    'chunkSize': 'user',
    'translationChunkSize': 'user',
    'translationConcurrent': 'user',
    'translationTimeout': 'user',
    'targetLanguage': 'user',
    'translationEngine': 'user',
    'translationQuality': 'user',
    'useGlossary': 'user',
    'usePrompt': 'user',
    'customPrompt': 'user',
    'translateOutputSuffix': 'user',
    'convertOutputSuffix': 'user',
    'previewFontSize': 'user',
    'editFontSize': 'user',
    'ui_language': 'user',

    // Exclusion defaults (global, admin only)
    'exclusion_defaults': 'global',

    // Sensitive settings (admin only, API keys)
    'platformApiKeys': 'sensitive',
    'api_keys': 'sensitive',
    'mineruToken': 'sensitive',
    'translator_mineru_token': 'sensitive',
    'mineru_local_token': 'sensitive',
  };

  /// Save setting (automatic classification and batch)
  /// [category] is optional prefix for the key (e.g., 'translation', 'parsing')
  /// [key] is the setting key
  /// [value] is the setting value
  Future<void> saveSetting(String category, String key, value) async {
    // Determine full key
    final fullKey = category.isEmpty ? key : '${category}_$key';

    // Determine configuration type
    final configType = _configTypeMap[fullKey] ??
        _configTypeMap[key] ??
        _getConfigTypeByKey(key);

    // Add to pending changes queue
    final queueKey = '${configType}_$fullKey';
    _pendingChanges[queueKey] = <String, dynamic>{
      'type': configType,
      'category': category,
      'key': key,
      'fullKey': fullKey,
      'value': value,
    };

    // Immediately save to local cache (for fast UI response)
    await _saveToLocalCache(category, key, value);

    // Debounce: delay batch save to backend
    // Cancel existing timer and start a new one
    _debounceTimer?.cancel();

    // If already saving, don't start a new debounce timer
    // The pending changes will be automatically flushed after current save completes
    if (_isSaving) {
      if (kDebugMode) {
        print(
          'SettingsService: Save in progress, queuing change for $fullKey (will be saved after current save completes)',
        );
      }
      // Don't start timer, changes will be handled after current save completes
      return;
    }

    // Update UI to show that changes are pending (but don't show loading yet)
    // Only show loading when actual save starts
    if (_currentState == SaveState.idle) {
      // Stay in idle during debounce period
    }

    // Start debounce timer for batch save
    _debounceTimer = Timer(const Duration(milliseconds: 300), () {
      // Only flush if still not saving (might have been started by another timer)
      if (!_isSaving) {
        _flushPendingChanges();
      }
    });
  }

  /// Flush pending changes to backend (batch save)
  Future<void> _flushPendingChanges() async {
    // Cancel any pending debounce timer (we're flushing now)
    _debounceTimer?.cancel();
    _debounceTimer = null;

    if (_pendingChanges.isEmpty) {
      // No pending changes, transition to success then idle
      _isSaving = false;
      if (_currentState == SaveState.loading) {
        // Was loading but no changes to save, transition to success
        _currentState = SaveState.success;
        _saveStateController.add(_currentState);
        // Then to idle after 1 second
        Future.delayed(const Duration(seconds: 1), () {
          if (_currentState == SaveState.success && _pendingChanges.isEmpty) {
            _currentState = SaveState.idle;
            _saveStateController.add(_currentState);
          }
        });
      } else if (_currentState != SaveState.idle &&
          _currentState != SaveState.success) {
        _currentState = SaveState.idle;
        _saveStateController.add(_currentState);
      }
      return;
    }

    // Prevent concurrent saves
    if (_isSaving) {
      if (kDebugMode) {
        print(
          'SettingsService: Save already in progress, will retry after current save completes',
        );
      }
      // Schedule retry after current save (will be handled in finally block)
      return;
    }

    _isSaving = true;

    // Capture current pending changes to save
    final changesToSave = Map<String, dynamic>.from(_pendingChanges);

    // Reset retry count on new flush
    _retryCount = 0;

    _currentState = SaveState.loading;
    _saveStateController.add(_currentState);

    try {
      // Group by type
      final globalChanges = <String, dynamic>{};
      final userChanges = <String, dynamic>{};
      final sensitiveChanges = <String, dynamic>{};

      for (final entry in changesToSave.values) {
        final type = entry['type'] as String;
        final fullKey = entry['fullKey'] as String;
        final value = entry['value'];

        switch (type) {
          case 'global':
            globalChanges[fullKey] = value;
            break;
          case 'user':
            userChanges[fullKey] = value;
            break;
          case 'sensitive':
            sensitiveChanges[fullKey] = value;
            break;
        }
      }

      // Batch save (call different APIs by type)
      final futures = <Future>[];

      if (globalChanges.isNotEmpty) {
        futures.add(_saveGlobalSettings(globalChanges));
      }
      if (userChanges.isNotEmpty) {
        futures.add(_saveUserSettings(userChanges));
      }
      if (sensitiveChanges.isNotEmpty) {
        futures.add(_saveSensitiveSettings(sensitiveChanges));
      }

      await Future.wait(futures);

      // Remove successfully saved changes from pending queue
      for (var key in changesToSave.keys) {
        _pendingChanges.remove(key);
      }

      _isSaving = false;

      // Check if there are more pending changes (added during save)
      final hasMoreChanges = _pendingChanges.isNotEmpty;

      if (hasMoreChanges) {
        // There are more changes pending, but show success briefly first
        // This ensures user always sees feedback that their changes are being saved
        if (kDebugMode) {
          print(
            'SettingsService: More changes pending after save, showing success then continuing',
          );
        }

        // Show success state briefly (even if more changes are pending)
        _currentState = SaveState.success;
        _saveStateController.add(_currentState);

        // Wait 300ms to show success message, then continue with next batch
        await Future.delayed(const Duration(milliseconds: 300));

        // Check again if there are still pending changes
        if (_pendingChanges.isNotEmpty && !_isSaving) {
          // Start a debounce timer for the remaining changes
          _debounceTimer?.cancel();
          _debounceTimer = Timer(const Duration(milliseconds: 500), () {
            if (_pendingChanges.isNotEmpty && !_isSaving) {
              _flushPendingChanges();
            } else if (_pendingChanges.isEmpty) {
              // No more changes, ensure we show idle
              if (_currentState != SaveState.idle) {
                _currentState = SaveState.idle;
                _saveStateController.add(_currentState);
              }
            }
          });
        } else if (_pendingChanges.isEmpty) {
          // All changes were saved while we waited
          // Transition to idle after showing success
          Future.delayed(const Duration(seconds: 1), () {
            if (_currentState == SaveState.success && _pendingChanges.isEmpty) {
              _currentState = SaveState.idle;
              _saveStateController.add(_currentState);
            }
          });
        }
      } else {
        // All changes saved successfully
        _currentState = SaveState.success;
        _saveStateController.add(_currentState);

        // Auto transition to idle after success message (2 seconds)
        Future.delayed(const Duration(seconds: 2), () {
          if (_currentState == SaveState.success && _pendingChanges.isEmpty) {
            _currentState = SaveState.idle;
            _saveStateController.add(_currentState);
          }
        });
      }
    } catch (e) {
      if (kDebugMode) {
        print('SettingsService: Batch save failed: $e');
      }

      _currentState = SaveState.error;
      _saveStateController.add(_currentState);
      _isSaving = false;

      // Auto retry (max 3 times with exponential backoff)
      await _retrySave();
    }
  }

  /// Save global settings
  Future<void> _saveGlobalSettings(Map<String, dynamic> changes) async {
    final success = await _configService.updateSettingsBatch('global', changes);
    if (!success) {
      throw Exception('Failed to save global settings');
    }
  }

  /// Save user settings
  Future<void> _saveUserSettings(Map<String, dynamic> changes) async {
    final success = await _configService.updateSettingsBatch('user', changes);
    if (!success) {
      throw Exception('Failed to save user settings');
    }
  }

  /// Save sensitive settings
  Future<void> _saveSensitiveSettings(Map<String, dynamic> changes) async {
    final success =
        await _configService.updateSettingsBatch('sensitive', changes);
    if (!success) {
      throw Exception('Failed to save sensitive settings');
    }
  }

  /// Save to local cache (immediate)
  Future<void> _saveToLocalCache(String category, String key, value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cacheKey = category.isEmpty ? key : '${category}_$key';
      await prefs.setString(cacheKey, json.encode(value));
    } catch (e) {
      if (kDebugMode) {
        print('SettingsService: Failed to save to local cache: $e');
      }
      // Local cache failure doesn't block the flow
    }
  }

  /// Retry save with exponential backoff
  Future<void> _retrySave() async {
    if (_retryCount >= 3) {
      if (kDebugMode) {
        print('SettingsService: Failed to save settings after 3 retries');
      }
      // Keep error state, user can manually retry or fix the issue
      _isSaving = false;
      return;
    }

    _retryCount++;

    // Exponential backoff: 1s, 2s, 4s
    final delaySeconds = 1 << (_retryCount - 1);
    await Future.delayed(Duration(seconds: delaySeconds));

    // Retry flush (only if still has pending changes and not already saving)
    if (_pendingChanges.isNotEmpty && !_isSaving) {
      await _flushPendingChanges();
    } else {
      _isSaving = false;
    }
  }

  /// Infer configuration type by key
  String _getConfigTypeByKey(String key) {
    // Default rules: infer type from key name
    if (key.contains('api_key') ||
        key.contains('token') ||
        key.contains('secret')) {
      return 'sensitive';
    }
    if (key.contains('platform') &&
        (key.contains('default') ||
            key.contains('url') ||
            key.contains('model'))) {
      return 'global';
    }
    if (key.contains('parsing') ||
        key.contains('translator_convert') ||
        key.contains('translator_mineru')) {
      return 'global';
    }
    // Default: most settings are user settings
    return 'user';
  }

  /// Initialize notification listener (call once in app entry or main layout)
  void initNotificationListener(BuildContext context) {
    _notificationContext = context;

    // Cancel previous subscription if exists
    _stateSubscription?.cancel();

    // Listen to save state changes
    _stateSubscription = saveState.listen((state) {
      if (state == SaveState.idle) {
        // Idle state doesn't show notification
        return;
      }

      final ctx = _notificationContext;
      if (ctx == null) return;

      // Try to show notification, but handle case where context is no longer valid
      try {
        // Check if context is still valid by trying to find ScaffoldMessenger
        final messenger = ScaffoldMessenger.maybeOf(ctx);
        if (messenger == null) {
          // Context is no longer valid, clear it
          _notificationContext = null;
          return;
        }

        // Hide previous notification
        messenger.hideCurrentSnackBar();

        String message;
        Color backgroundColor;
        Duration duration;
        Widget leading;

        switch (state) {
          case SaveState.loading:
            message = '正在保存设置...';
            backgroundColor = Colors.blue;
            duration = const Duration(
              seconds: 5,
            ); // Max 5 seconds, will be replaced by success/error
            leading = const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            );
            break;
          case SaveState.success:
            message = '设置已保存';
            backgroundColor = Colors.green;
            duration = const Duration(seconds: 2);
            leading =
                const Icon(Icons.check_circle, color: Colors.white, size: 20);
            break;
          case SaveState.error:
            message = '保存失败，请重试';
            backgroundColor = Colors.red;
            duration = const Duration(seconds: 4);
            leading = const Icon(Icons.error, color: Colors.white, size: 20);
            break;
          default:
            return;
        }

        messenger.showSnackBar(
          SnackBar(
            content: Row(
              children: <Widget>[
                leading,
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    message,
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
              ],
            ),
            backgroundColor: backgroundColor,
            duration: duration,
            behavior: SnackBarBehavior.floating,
            margin: const EdgeInsets.all(16),
          ),
        );
      } catch (e) {
        // Context is no longer valid, clear it and ignore the error
        _notificationContext = null;
        debugPrint(
          'SettingsService: Context is no longer valid, clearing notification context: $e',
        );
      }
    });
  }

  /// Clear notification context (call when widget is disposed)
  void clearNotificationContext() {
    _notificationContext = null;
  }

  /// Dispose resources
  void dispose() {
    _debounceTimer?.cancel();
    _stateSubscription?.cancel();
    _saveStateController.close();
    _notificationContext = null;
  }

  /// Get current save state
  SaveState get currentState => _currentState;

  /// Check if there are pending changes
  bool get hasPendingChanges => _pendingChanges.isNotEmpty;
}
