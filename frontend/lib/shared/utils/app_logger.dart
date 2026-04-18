// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/foundation.dart';

enum LogLevel { debug, info, warn, error }

class AppLogger {
  static LogLevel _currentLevel = LogLevel.info;

  /// Get current log level (for external access)
  static LogLevel get currentLevel => _currentLevel;

  static final Map<LogLevel, int> _levelOrder = <LogLevel, int>{
    LogLevel.debug: 0,
    LogLevel.info: 1,
    LogLevel.warn: 2,
    LogLevel.error: 3,
  };

  static void setLevel(LogLevel level) {
    _currentLevel = level;
  }

  static void log(
    String tag,
    String message, {
    LogLevel level = LogLevel.debug,
  }) {
    if (_levelOrder[level]! < _levelOrder[_currentLevel]!) {
      return;
    }

    final String timestamp = DateTime.now().toIso8601String();
    final String levelLabel = level.toString().split('.').last.toUpperCase();
    final String formatted = '[$timestamp][$levelLabel][$tag] $message';

    if (kDebugMode) {
      debugPrint(formatted);
    } else {
      // In release/profile, still use debugPrint to preserve logging capability.
      debugPrint(formatted);
    }
  }
}
