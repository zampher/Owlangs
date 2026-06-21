// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../shared/services/translation_service.dart';

/// Format settings state for a task
/// Manages table_body_format, equation_format, and chart_body_format settings
class FormatSettings {
  const FormatSettings({
    this.tableFormat,
    this.equationFormat,
    this.chartFormat,
    this.bilingualExport,
    this.bilingualOrder,
    this.sourceTextItalic,
    this.sourceTextColor,
    this.targetTextItalic,
    this.targetTextColor,
    this.coverColorMode,
  });

  /// Table format: 'html' or 'image'
  /// Default: 'html' for all workflows (PDF/PNG included)
  final String? tableFormat;

  /// Equation format: 'text', 'latex', or 'image'
  /// UI radios use 'text' for LaTeX; default is 'text' (LaTeX)
  final String? equationFormat;

  /// Chart format: 'html' or 'image'
  /// Default: 'image' for safety (preserves chart appearance)
  final String? chartFormat;

  /// Bilingual export: true or false
  /// When true, both source and target text are exported
  final bool? bilingualExport;

  /// Bilingual order: 'target_after_source' or 'target_before_source'
  final String? bilingualOrder;

  /// Source text italic: true or false
  /// When true, source text paragraphs are rendered in italic
  final bool? sourceTextItalic;

  /// Source text color: preset name ('gray', 'blue', 'red', 'green', 'orange', 'black')
  final String? sourceTextColor;

  /// Target text italic: true or false
  /// When true, target text paragraphs are rendered in italic
  final bool? targetTextItalic;

  /// Target text color: preset name ('gray', 'blue', 'red', 'green', 'orange', 'black')
  final String? targetTextColor;

  /// Image overlay erase fill: 'max' (brightest strip pixel) or 'min' (darkest)
  final String? coverColorMode;

  /// Get table format with default fallback
  String getTableFormat({bool isPdfWorkflow = false}) =>
      tableFormat ?? 'html';

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

  /// Get chart format with default fallback
  /// Default is 'image' for safety (preserves original chart appearance)
  String getChartFormat({bool isPdfWorkflow = false}) =>
      chartFormat ?? (isPdfWorkflow ? 'image' : 'image');

  /// Image overlay erase background color pick mode.
  String getCoverColorMode() => coverColorMode ?? 'max';

  FormatSettings copyWith({
    String? tableFormat,
    String? equationFormat,
    String? chartFormat,
    bool? bilingualExport,
    String? bilingualOrder,
    bool? sourceTextItalic,
    String? sourceTextColor,
    bool? targetTextItalic,
    String? targetTextColor,
    String? coverColorMode,
    bool clearTableFormat = false,
    bool clearEquationFormat = false,
    bool clearChartFormat = false,
    bool clearBilingualExport = false,
    bool clearBilingualOrder = false,
    bool clearSourceTextItalic = false,
    bool clearSourceTextColor = false,
    bool clearTargetTextItalic = false,
    bool clearTargetTextColor = false,
    bool clearCoverColorMode = false,
  }) =>
      FormatSettings(
        tableFormat:
            clearTableFormat ? null : (tableFormat ?? this.tableFormat),
        equationFormat: clearEquationFormat
            ? null
            : (equationFormat ?? this.equationFormat),
        chartFormat: clearChartFormat
            ? null
            : (chartFormat ?? this.chartFormat),
        bilingualExport: clearBilingualExport
            ? null
            : (bilingualExport ?? this.bilingualExport),
        bilingualOrder: clearBilingualOrder
            ? null
            : (bilingualOrder ?? this.bilingualOrder),
        sourceTextItalic: clearSourceTextItalic
            ? null
            : (sourceTextItalic ?? this.sourceTextItalic),
        sourceTextColor: clearSourceTextColor
            ? null
            : (sourceTextColor ?? this.sourceTextColor),
        targetTextItalic: clearTargetTextItalic
            ? null
            : (targetTextItalic ?? this.targetTextItalic),
        targetTextColor: clearTargetTextColor
            ? null
            : (targetTextColor ?? this.targetTextColor),
        coverColorMode: clearCoverColorMode
            ? null
            : (coverColorMode ?? this.coverColorMode),
      );

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FormatSettings &&
          runtimeType == other.runtimeType &&
          tableFormat == other.tableFormat &&
          equationFormat == other.equationFormat &&
          chartFormat == other.chartFormat &&
          bilingualExport == other.bilingualExport &&
          bilingualOrder == other.bilingualOrder &&
          sourceTextItalic == other.sourceTextItalic &&
          sourceTextColor == other.sourceTextColor &&
          targetTextItalic == other.targetTextItalic &&
          targetTextColor == other.targetTextColor &&
          coverColorMode == other.coverColorMode;

  @override
  int get hashCode =>
      tableFormat.hashCode ^
      equationFormat.hashCode ^
      chartFormat.hashCode ^
      bilingualExport.hashCode ^
      bilingualOrder.hashCode ^
      sourceTextItalic.hashCode ^
      sourceTextColor.hashCode ^
      targetTextItalic.hashCode ^
      targetTextColor.hashCode ^
      coverColorMode.hashCode;
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
      final String? chartFormat = flowSettings['chart_body_format'] as String?;
      final bool? bilingualExport = flowSettings['bilingual_export'] as bool?;
      final String? bilingualOrder = flowSettings['bilingual_order'] as String?;
      final bool? sourceTextItalic = flowSettings['source_text_italic'] as bool?;
      final String? sourceTextColor = flowSettings['source_text_color'] as String?;
      final bool? targetTextItalic = flowSettings['target_text_italic'] as bool?;
      final String? targetTextColor = flowSettings['target_text_color'] as String?;
      final String? coverColorMode = flowSettings['cover_color_mode'] as String?;

      if (tableFormat != null || equationFormat != null || chartFormat != null || bilingualExport != null || bilingualOrder != null || sourceTextItalic != null || sourceTextColor != null || targetTextItalic != null || targetTextColor != null || coverColorMode != null) {
        state = FormatSettings(
          tableFormat: tableFormat,
          equationFormat: equationFormat,
          chartFormat: chartFormat,
          bilingualExport: bilingualExport,
          bilingualOrder: bilingualOrder,
          sourceTextItalic: sourceTextItalic,
          sourceTextColor: sourceTextColor,
          targetTextItalic: targetTextItalic,
          targetTextColor: targetTextColor,
          coverColorMode: coverColorMode,
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
      final String? chartFormat =
          prefs.getString('format_settings_chart_default');
      final bool? bilingualExport =
          prefs.getBool('format_settings_bilingual_export_default');
      final String? bilingualOrder =
          prefs.getString('format_settings_bilingual_order_default');
      final bool? sourceTextItalic =
          prefs.getBool('format_settings_source_text_italic_default');
      final String? sourceTextColor =
          prefs.getString('format_settings_source_text_color_default');
      final bool? targetTextItalic =
          prefs.getBool('format_settings_target_text_italic_default');
      final String? targetTextColor =
          prefs.getString('format_settings_target_text_color_default');
      final String? coverColorMode =
          prefs.getString('format_settings_cover_color_mode_default');

      if (tableFormat != null || equationFormat != null || chartFormat != null || bilingualExport != null || bilingualOrder != null || sourceTextItalic != null || sourceTextColor != null || targetTextItalic != null || targetTextColor != null || coverColorMode != null) {
        state = FormatSettings(
          tableFormat: tableFormat,
          equationFormat: equationFormat,
          chartFormat: chartFormat,
          bilingualExport: bilingualExport,
          bilingualOrder: bilingualOrder,
          sourceTextItalic: sourceTextItalic,
          sourceTextColor: sourceTextColor,
          targetTextItalic: targetTextItalic,
          targetTextColor: targetTextColor,
          coverColorMode: coverColorMode,
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
      if (state.chartFormat != null) {
        await prefs.setString(
          'format_settings_chart_default',
          state.chartFormat!,
        );
      } else {
        // Clear if set to null (use code default)
        await prefs.remove('format_settings_chart_default');
      }
      if (state.bilingualExport != null) {
        await prefs.setBool(
          'format_settings_bilingual_export_default',
          state.bilingualExport!,
        );
      } else {
        await prefs.remove('format_settings_bilingual_export_default');
      }
      if (state.bilingualOrder != null) {
        await prefs.setString(
          'format_settings_bilingual_order_default',
          state.bilingualOrder!,
        );
      } else {
        await prefs.remove('format_settings_bilingual_order_default');
      }
      if (state.sourceTextItalic != null) {
        await prefs.setBool(
          'format_settings_source_text_italic_default',
          state.sourceTextItalic!,
        );
      } else {
        await prefs.remove('format_settings_source_text_italic_default');
      }
      if (state.sourceTextColor != null) {
        await prefs.setString(
          'format_settings_source_text_color_default',
          state.sourceTextColor!,
        );
      } else {
        await prefs.remove('format_settings_source_text_color_default');
      }
      if (state.targetTextItalic != null) {
        await prefs.setBool(
          'format_settings_target_text_italic_default',
          state.targetTextItalic!,
        );
      } else {
        await prefs.remove('format_settings_target_text_italic_default');
      }
      if (state.targetTextColor != null) {
        await prefs.setString(
          'format_settings_target_text_color_default',
          state.targetTextColor!,
        );
      } else {
        await prefs.remove('format_settings_target_text_color_default');
      }
      if (state.coverColorMode != null) {
        await prefs.setString(
          'format_settings_cover_color_mode_default',
          state.coverColorMode!,
        );
      } else {
        await prefs.remove('format_settings_cover_color_mode_default');
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

  /// Set chart format
  void setChartFormat(String format) {
    if (format != 'html' && format != 'image') {
      return; // Invalid format
    }
    state = state.copyWith(chartFormat: format);
  }

  /// Set bilingual export enabled
  void setBilingualExport(bool enabled) {
    state = state.copyWith(bilingualExport: enabled);
  }

  /// Set bilingual order
  void setBilingualOrder(String order) {
    if (order != 'target_after_source' && order != 'target_before_source') {
      return; // Invalid order
    }
    state = state.copyWith(bilingualOrder: order);
  }

  /// Set source text italic
  void setSourceTextItalic(bool enabled) {
    state = state.copyWith(sourceTextItalic: enabled);
  }

  /// Set source text color
  void setSourceTextColor(String color) {
    final validColors = <String>{'gray', 'blue', 'red', 'green', 'orange', 'black'};
    // Empty string means default (no color override)
    if (color.isNotEmpty && !validColors.contains(color)) {
      return; // Invalid color
    }
    state = state.copyWith(sourceTextColor: color);
  }

  /// Set target text italic
  void setTargetTextItalic(bool enabled) {
    state = state.copyWith(targetTextItalic: enabled);
  }

  /// Set target text color
  void setTargetTextColor(String color) {
    final validColors = <String>{'gray', 'blue', 'red', 'green', 'orange', 'black'};
    if (!validColors.contains(color)) {
      return; // Invalid color
    }
    state = state.copyWith(targetTextColor: color);
  }

  /// Set image overlay erase background color mode
  void setCoverColorMode(String mode) {
    if (mode != 'max' && mode != 'min' && mode != 'avg') {
      return;
    }
    state = state.copyWith(coverColorMode: mode);
    if (taskId != null) {
      _saveToFlowState(
        state.tableFormat,
        state.equationFormat,
        state.chartFormat,
        state.bilingualExport,
        state.bilingualOrder,
        state.sourceTextItalic,
        state.sourceTextColor,
        state.targetTextItalic,
        state.targetTextColor,
        mode,
      );
    }
  }

  /// Set both formats
  void setFormats({
    String? tableFormat,
    String? equationFormat,
    String? chartFormat,
    bool? bilingualExport,
    String? bilingualOrder,
    bool? sourceTextItalic,
    String? sourceTextColor,
    bool? targetTextItalic,
    String? targetTextColor,
    String? coverColorMode,
  }) {
    state = state.copyWith(
      tableFormat: tableFormat,
      equationFormat: equationFormat,
      chartFormat: chartFormat,
      bilingualExport: bilingualExport,
      bilingualOrder: bilingualOrder,
      sourceTextItalic: sourceTextItalic,
      sourceTextColor: sourceTextColor,
      targetTextItalic: targetTextItalic,
      targetTextColor: targetTextColor,
      coverColorMode: coverColorMode,
    );
    // Save to Flow state if taskId is available
    if (taskId != null) {
      _saveToFlowState(tableFormat, equationFormat, chartFormat, bilingualExport, bilingualOrder, sourceTextItalic, sourceTextColor, targetTextItalic, targetTextColor, coverColorMode);
    }
  }

  /// Save format settings to Flow state (backend task_state)
  Future<void> _saveToFlowState(
    String? tableFormat,
    String? equationFormat,
    String? chartFormat,
    bool? bilingualExport,
    String? bilingualOrder,
    bool? sourceTextItalic,
    String? sourceTextColor,
    bool? targetTextItalic,
    String? targetTextColor,
    String? coverColorMode,
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
        chartBodyFormat: chartFormat,
        bilingualExport: bilingualExport,
        bilingualOrder: bilingualOrder,
        sourceTextItalic: sourceTextItalic,
        sourceTextColor: sourceTextColor,
        targetTextItalic: targetTextItalic,
        targetTextColor: targetTextColor,
        coverColorMode: coverColorMode,
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

  /// Clear chart format (use default)
  void clearChartFormat() {
    state = state.copyWith(clearChartFormat: true);
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
