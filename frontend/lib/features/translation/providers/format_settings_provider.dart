// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../shared/services/translation_service.dart';

/// Format settings state for a task
/// Manages table_body_format and equation_format settings
class FormatSettings {
  const FormatSettings({
    this.tableFormat,
    this.equationFormat,
  });

  /// Table format: 'html' or 'image'
  /// Default: 'html' for non-PDF; 'image' for PDF layout workflow
  final String? tableFormat;

  /// Equation format: 'text', 'latex', or 'image'
  /// UI radios use 'text' for LaTeX; default is 'text' (LaTeX)
  final String? equationFormat;

  /// Get table format with default fallback
  String getTableFormat({bool isPdfWorkflow = false}) =>
      tableFormat ?? (isPdfWorkflow ? 'image' : 'html');

  /// Get equation format with default fallback (UI radio values: text=LaTeX, image=Image)
  String getEquationFormat({bool isPdfWorkflow = false}) {
    final String? stored = equationFormat;
    if (stored != null) {
      // Backend may store 'latex'; UI radios use 'text' for LaTeX
      if (stored == 'latex') return 'text';
      return stored;
    }
    // LaTeX default (stored/sent as 'text' in UI; backend also accepts 'latex')
    return 'text';
  }

  FormatSettings copyWith({
    String? tableFormat,
    String? equationFormat,
    bool clearTableFormat = false,
    bool clearEquationFormat = false,
  }) =>
      FormatSettings(
        tableFormat:
            clearTableFormat ? null : (tableFormat ?? this.tableFormat),
        equationFormat: clearEquationFormat
            ? null
            : (equationFormat ?? this.equationFormat),
      );

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FormatSettings &&
          runtimeType == other.runtimeType &&
          tableFormat == other.tableFormat &&
          equationFormat == other.equationFormat;

  @override
  int get hashCode => tableFormat.hashCode ^ equationFormat.hashCode;
}

/// Notifier for managing format settings per task
class FormatSettingsNotifier extends StateNotifier<FormatSettings> {
  FormatSettingsNotifier({this.taskId}) : super(const FormatSettings()) {
    _loadFromFlowOrDefaults();
  }

  final String? taskId;

  /// Load format settings from Flow state or user defaults
  /// Priority: Flow state > User defaults > Code defaults
  Future<void> _loadFromFlowOrDefaults() async {
    if (taskId == null) {
      // No taskId, load from user defaults only
      await _loadFromUserDefaults();
      return;
    }

    try {
      // Try to load from Flow state (backend task_state)
      final TranslationService translationService = TranslationService();
      final Map<String, dynamic> flowSettings =
          await translationService.getFormatSettings(taskId!);

      final String? tableFormat = flowSettings['table_body_format'] as String?;
      final String? equationFormat = flowSettings['equation_format'] as String?;

      if (tableFormat != null || equationFormat != null) {
        state = FormatSettings(
          tableFormat: tableFormat,
          equationFormat: equationFormat,
        );
        return; // Use Flow state settings
      }
    } catch (e) {
      // If loading from Flow state fails, fall back to user defaults
      // Silently fail to avoid disrupting user experience
    }

    // Fallback to user defaults
    await _loadFromUserDefaults();
  }

  /// Reload format settings from Flow state
  /// This is useful when taskId changes or when format settings may have been updated
  Future<void> reloadFromFlowState() async {
    await _loadFromFlowOrDefaults();
  }

  /// Load format settings from user defaults (SharedPreferences)
  Future<void> _loadFromUserDefaults() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String? tableFormat =
          prefs.getString('format_settings_table_default');
      final String? equationFormat =
          prefs.getString('format_settings_equation_default');

      if (tableFormat != null || equationFormat != null) {
        state = FormatSettings(
          tableFormat: tableFormat,
          equationFormat: equationFormat,
        );
      }
      // If no user defaults, use code defaults (already set in super constructor)
    } catch (e) {
      // If loading fails, use code defaults (already set in super constructor)
      // Silently fail to avoid disrupting user experience
    }
  }

  /// Save current settings as user global defaults
  Future<void> saveAsUserDefaults() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      if (state.tableFormat != null) {
        await prefs.setString(
          'format_settings_table_default',
          state.tableFormat!,
        );
      } else {
        // Clear if set to null (use code default)
        await prefs.remove('format_settings_table_default');
      }
      if (state.equationFormat != null) {
        await prefs.setString(
          'format_settings_equation_default',
          state.equationFormat!,
        );
      } else {
        // Clear if set to null (use code default)
        await prefs.remove('format_settings_equation_default');
      }
    } catch (e) {
      // Silently fail to avoid disrupting user experience
    }
  }

  /// Set table format
  void setTableFormat(String format) {
    if (format != 'html' && format != 'image') {
      return; // Invalid format
    }
    state = state.copyWith(tableFormat: format);
  }

  /// Set equation format
  void setEquationFormat(String format) {
    if (format != 'text' && format != 'latex' && format != 'image') {
      return; // Invalid format
    }
    state = state.copyWith(equationFormat: format);
  }

  /// Set both formats
  void setFormats({
    String? tableFormat,
    String? equationFormat,
  }) {
    state = state.copyWith(
      tableFormat: tableFormat,
      equationFormat: equationFormat,
    );
    // Save to Flow state if taskId is available
    if (taskId != null) {
      _saveToFlowState(tableFormat, equationFormat);
    }
  }

  /// Save format settings to Flow state (backend task_state)
  Future<void> _saveToFlowState(
    String? tableFormat,
    String? equationFormat,
  ) async {
    if (taskId == null) {
      return; // No taskId, cannot save to Flow state
    }

    try {
      final TranslationService translationService = TranslationService();
      await translationService.updateFormatSettings(
        taskId!,
        tableBodyFormat: tableFormat,
        equationFormat: equationFormat,
      );
    } catch (e) {
      // Silently fail to avoid disrupting user experience
      // Format settings will still work locally, but won't persist to Flow state
    }
  }

  /// Clear table format (use default)
  void clearTableFormat() {
    state = state.copyWith(clearTableFormat: true);
  }

  /// Clear equation format (use default)
  void clearEquationFormat() {
    state = state.copyWith(clearEquationFormat: true);
  }

  /// Reset all settings to defaults
  void reset() {
    state = const FormatSettings();
  }
}

/// Provider for format settings per task
/// Uses taskId as the family parameter to scope settings per task
final StateNotifierProviderFamily<FormatSettingsNotifier, FormatSettings,
        String> formatSettingsProviderFamily =
    StateNotifierProvider.family<FormatSettingsNotifier, FormatSettings,
        String>(
  (StateNotifierProviderRef<FormatSettingsNotifier, FormatSettings> ref,
      String taskId,) {
    // Keep provider alive to persist settings during task lifecycle
    ref.keepAlive();
    return FormatSettingsNotifier(taskId: taskId);
  },
);
