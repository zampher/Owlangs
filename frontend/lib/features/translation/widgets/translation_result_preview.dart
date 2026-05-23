// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/app_config.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/utils/dialog_helper.dart';
import '../../../l10n/app_localizations.dart';
import '../../settings/screens/ai_platform_settings.dart';
import '../services/translation_content_parser.dart';
import '../services/translation_segments_service.dart';
import '../mixins/segment_height_mixin.dart';
import '../widgets/translation_result/translation_result_toolbar.dart';
import '../widgets/translation_result/translation_merged_preview.dart';
import '../../../../shared/widgets/segment_search_box.dart';
import '../../../../shared/providers/settings_provider.dart';
import '../widgets/translation_result/translation_comparison_panel.dart';
import '../providers/preview_tabs_provider.dart';
import '../providers/translation_refresh_provider.dart';
import '../providers/segment_undo_redo_provider.dart';
import '../providers/translation_state_provider_family.dart';
import '../providers/format_settings_provider.dart';
import '../models/preview_tab.dart';
import '../models/segment_pair.dart';
import '../widgets/pdf_preview.dart';
import '../../../shared/config/pagination_config.dart';
import '../widgets/translation_quick_settings.dart';
import 'translation_preview_tab_widget.dart';
import '../../../shared/utils/pagination.dart';
import '../../../shared/utils/paginated_scroll_manager.dart';
import '../utils/segment_height_cache.dart';
import '../utils/text_utils.dart';
import '../widgets/common/exclusion_panel_widget.dart';
import '../utils/segment_type_utils.dart';

void _translationResultLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('TranslationResultPreview', message, level: level);
}

// Intent classes for keyboard shortcuts
class _GlobalUndoIntent extends Intent {
  const _GlobalUndoIntent();
}

class _GlobalRedoIntent extends Intent {
  const _GlobalRedoIntent();
}

class _ExitFullscreenIntent extends Intent {
  const _ExitFullscreenIntent();
}

/// Translation result preview with source/target comparison
class TranslationResultPreview extends ConsumerStatefulWidget {
  const TranslationResultPreview({
    required this.taskId,
    super.key,
    this.flowId,
    this.initialSourceParagraphs,
    this.initialTargetParagraphs,
    this.downloads,
    this.onDownload,
    this.onTranslationWorkspaceMutation,
    this.fileName,
    this.isTextMode = false,
    this.workflowType,
    this.initialMergedView = false,
  });
  final String taskId;
  final String? flowId; // Optional per-flow scope
  final List<String>? initialSourceParagraphs; // Optional initial paragraphs
  final List<String>? initialTargetParagraphs; // Optional initial paragraphs
  final Map<String, String>? downloads; // Download URLs by file type
  final Function(String fileType, String url)? onDownload; // Download callback
  /// Fired when user edits / undo / redo target text (server updated) so the shell can mark queue-stash dirty.
  final VoidCallback? onTranslationWorkspaceMutation;
  final String? fileName; // Original file name
  final bool isTextMode;
  final String? workflowType;
  /// Start in clean (merged) view when true.
  final bool initialMergedView;

  @override
  ConsumerState<TranslationResultPreview> createState() =>
      _TranslationResultPreviewState();
}

class _TranslationResultPreviewState
    extends ConsumerState<TranslationResultPreview> with SegmentHeightMixin {
  int? highlightedIndex;
  // Use ValueNotifier for efficient highlight state updates
  final ValueNotifier<int?> _highlightedIndexNotifier =
      ValueNotifier<int?>(null);
  // Single scroll controller for the unified comparison panel
  final ScrollController _comparisonScrollController = ScrollController();
  final Map<String, bool> _downloading =
      <String, bool>{}; // Track download state for each file type

  // Scroll manager for maintaining scroll position during pagination
  PaginatedScrollManager? _scrollManager;
  // ignore: unused_field
  SegmentHeightCache? _heightCache; // Used by _scrollManager

  // Keys for each paragraph item to enable precise scrolling (only for target side now)
  @override
  final Map<int, GlobalKey> sourceItemKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};
  @override
  final Map<int, GlobalKey> targetItemKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};

  // Keys for each segment pair (Container containing both source and target)
  // This is the most reliable key for scrolling since it represents the unified height
  final Map<int, GlobalKey> segmentPairKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};

  /// TaskId for which we already fetched on-demand download links (so we only fetch once per task).
  String? _lastTaskIdForOnDemandDownloadsFetch;

  /// Backend task id for API calls.
  ///
  /// Priority (highest first):
  /// 1. [widget.taskId] when it is a concrete taskId (not `'pending'`). This
  ///    prevents a stale [TranslationState.taskId] from a prior pipeline phase
  ///    (e.g. a format-conversion task id lingering after file import) from
  ///    being picked up.
  /// 2. [TranslationState.taskId] from the Riverpod provider — only used when
  ///    [widget.taskId] is still `'pending'` (the real id hasn't arrived yet).
  /// 3. Fallback to [widget.taskId].
  String _apiTaskId() {
    // Timer/async callbacks may run after dispose; ref is invalid then.
    if (!mounted) {
      return widget.taskId;
    }
    // When we have a flowId, always prefer the provider's taskId because it
    // tracks the current phase. The widget.taskId may be the convert-phase ID
    // while the actual translation (and its segments) live under a different
    // workflow taskId.
    if (widget.flowId != null) {
      final dynamic st =
          ref.read(translationStateProviderFamily(widget.flowId!));
      final String? tid = st.taskId as String?;
      if (tid != null && tid.isNotEmpty && tid != 'pending') {
        return tid;
      }
    }
    // Fallback to widget taskId when there is no flowId or provider has no ID.
    if (widget.taskId != 'pending') {
      return widget.taskId;
    }
    return widget.taskId;
  }

  void _notifyTranslationWorkspaceMutation() {
    widget.onTranslationWorkspaceMutation?.call();
  }

  // Cached item heights for accurate scroll calculation (kept for backward compatibility)
  @override
  double? cachedSourceItemHeight;
  @override
  double? cachedTargetItemHeight;

  // Flag to prevent recursive scrolling
  bool _isScrolling = false;

  List<String> _sourceParagraphs = <String>[];
  List<String> _targetParagraphs = <String>[];

  // Merged paragraph preview state
  List<String> _mergedSourceParagraphs = <String>[];
  List<String> _mergedTargetParagraphs = <String>[];
  final Map<int, int> _segmentChunkIds = <int, int>{};
  bool _isMergedView = false;

  bool _isLoading = true;
  String? _loadingError;

  // Search state
  bool _isSearchBoxVisible = false;
  String _searchQuery = '';
  final List<int> _searchMatchIndices = <int>[];
  int _currentSearchMatchIndex = 0;

  // Pagination controller for translation segments
  PagedListController<SegmentPair>? _segmentsPaginationController;

  // Cache for all segment metadata (loaded once from getTranslationSegments)
  final Map<int, Map<String, dynamic>> _allSegmentsMetadata =
      <int, Map<String, dynamic>>{};

  Future<void> _checkPdfFormulas(BuildContext context) async {
    if (_apiTaskId() == 'pending') return;
    try {
      final svc = TranslationService();
      final result = await svc.checkLatexFormulas(_apiTaskId());
      if (!mounted) return;

      final bool pandocAvailable = result['pandoc_available'] == true;
      final List<dynamic> issues =
          result['issues'] as List<dynamic>? ?? <dynamic>[];
      final int snippetCount = result['snippet_count'] as int? ?? 0;

      if (!pandocAvailable) {
        await showDialog<void>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('公式检测'),
            content: const Text('后端未检测到 Pandoc，无法执行公式完整性检测。'),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('关闭'),
              ),
            ],
          ),
        );
        return;
      }

      if (issues.isEmpty) {
        await showDialog<void>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('公式检测'),
            content: Text('已检查 $snippetCount 个公式片段，未发现明显语法问题。'),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('关闭'),
              ),
            ],
          ),
        );
        return;
      }

      // Build a copyable plain-text report
      final StringBuffer reportBuffer = StringBuffer();
      reportBuffer.writeln('公式检测结果（共 ${issues.length} 项）：');
      reportBuffer.writeln();
      for (int i = 0; i < issues.length; i++) {
        final Map<String, dynamic> issue =
            (issues[i] as Map).cast<String, dynamic>();
        final int idx = (issue['snippet_index'] as int?) ?? i;
        final String message = (issue['message'] as String?) ?? '';
        reportBuffer.writeln('片段 #$idx');
        reportBuffer.writeln(message);
        reportBuffer.writeln();
      }
      final String reportText = reportBuffer.toString();

      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('公式检测结果'),
          content: SizedBox(
            width: 600,
            height: 400,
            child: Column(
              children: <Widget>[
                Expanded(
                  child: Scrollbar(
                    child: SingleChildScrollView(
                      child: SelectableText(
                        reportText,
                        style: const TextStyle(fontSize: 13),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: <Widget>[
                    TextButton.icon(
                      onPressed: () {
                        Clipboard.setData(
                          ClipboardData(text: reportText),
                        );
                        MessageService.showInfo(context, '已复制到剪贴板');
                      },
                      icon: const Icon(Icons.copy, size: 16),
                      label: const Text('复制全部'),
                    ),
                  ],
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('关闭'),
            ),
          ],
        ),
      );
    } catch (e) {
      if (!mounted) return;
      final String errorText = '请求公式检测时出错：\n$e';
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('公式检测失败'),
          content: SizedBox(
            width: 500,
            child: SelectableText(errorText),
          ),
          actions: <Widget>[
            TextButton.icon(
              onPressed: () {
                Clipboard.setData(ClipboardData(text: errorText));
                MessageService.showInfo(context, '已复制到剪贴板');
              },
              icon: const Icon(Icons.copy, size: 16),
              label: const Text('复制错误信息'),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('关闭'),
            ),
          ],
        ),
      );
    }
  }

  /// Manual trigger: LLM repair for Pandoc DOCX fragment math (texmath) failures.
  Future<void> _repairDocxMathFragments(BuildContext context) async {
    if (_apiTaskId() == 'pending') return;
    final ScaffoldMessengerState? messenger =
        ScaffoldMessenger.maybeOf(context);
    messenger?.showSnackBar(
      const SnackBar(
        content: Text('正在调用 AI 按 DOCX 路径修复公式片段，请稍候…'),
        duration: Duration(seconds: 12),
      ),
    );
    try {
      final Map<String, dynamic> result =
          await TranslationService().repairDocxMathFragments(_apiTaskId());
      if (!mounted) return;
      messenger?.hideCurrentSnackBar();
      ref.read(translationRefreshProvider.notifier).state++;
      final bool success = result['success'] == true;
      final int updated = (result['segments_updated'] as num?)?.toInt() ?? 0;
      final int issuesAfter =
          (result['issues_after'] as num?)?.toInt() ?? -1;
      final String err = result['error']?.toString() ?? '';
      final String msg = result['message']?.toString() ?? '';
      await showDialog<void>(
        context: context,
        builder: (BuildContext ctx) => AlertDialog(
          title: Text(success ? 'DOCX 公式修复完成' : 'DOCX 公式修复'),
          content: SelectableText(
            success
                ? '已更新片段数: $updated\n仍存疑片段数: $issuesAfter\n（0 表示当前片段级 Pandoc 检测无告警）'
                : (msg.isNotEmpty
                    ? msg
                    : (err.isNotEmpty ? err : '请求失败')),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('关闭'),
            ),
          ],
        ),
      );
    } catch (e) {
      if (!mounted) return;
      messenger?.hideCurrentSnackBar();
      await showDialog<void>(
        context: context,
        builder: (BuildContext ctx) => AlertDialog(
          title: const Text('DOCX 公式修复失败'),
          content: SelectableText('$e'),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('关闭'),
            ),
          ],
        ),
      );
    }
  }

  // Global detected exclusion reason counts from Extract phase (if available).
  // This allows Translate phase Segment Type Filters to align with Extract's
  // detected categories such as language_match, identifier, etc.
  Map<String, int>? _globalDetectedReasonCounts;
  int _totalSegmentsCount = 0;

  // Track modified segments (index -> new text)
  final Map<int, String> _modifiedSegments = <int, String>{};
  // Track which segments are being edited
  final Set<int> _editingSegments = <int>{};

  // Track platform and failure info for each segment (index -> data)
  final Map<int, String?> _segmentPlatforms =
      <int, String?>{}; // Platform key used
  final Map<int, bool> _failedSegments =
      <int, bool>{}; // Whether segment failed
  final Map<int, String?> _failureReasons =
      <int, String?>{}; // Failure reason if failed
  final Map<int, bool> _markedRetrySegments =
      <int, bool>{}; // User manually marked for retry
  final Map<int, bool> _excludedSegments =
      <int, bool>{}; // Whether segment is excluded from translation
  final Set<int> _retranslatingSegments =
      <int>{}; // Segments currently being retranslated
  final Map<int, List<String>> _usedPlatformsForSegment =
      <int, List<String>>{}; // Platforms used for retry rotation
  final Map<int, bool> _imageSegments =
      <int, bool>{}; // Whether segment is an image segment

  // Exclusion panel state
  bool _isExclusionPanelExpanded = false;
  Set<String> _selectedExclusionFilters = <String>{};
  // PERFORMANCE: Drive filter UI updates without rebuilding whole page
  late final ValueNotifier<Set<String>> _selectedExclusionFiltersNotifier =
      ValueNotifier<Set<String>>(<String>{});
  String _filterMode =
      'rebuild'; // Default to 'rebuild' mode for translation result preview

  // PERFORMANCE: Cache filtered segment indices to avoid expensive recalculation
  List<int>? _cachedFilteredIndices;
  Set<String>? _cachedFilteredIndicesFilters;
  int? _cachedFilteredIndicesTotalCount;

  // PERFORMANCE: Prevent duplicate refresh calls during filter changes
  bool _isRefreshingForFilter = false;

  // PERFORMANCE: Cache exclusion counts to avoid expensive recalculation on every rebuild
  Map<String, int>? _cachedExclusionCounts;
  int? _cachedExclusionCountsTotalSegments;
  int? _cachedExclusionCountsMetadataSize;

  bool _loadingHtmlPreview = false;
  // Format settings are now managed by formatSettingsProviderFamily
  // Removed: String? _selectedTableFormat;
  // Removed: String? _selectedEquationFormat;

  int? _lastRefreshTrigger;
  Timer? _sourcePreviewTimer;
  int _sourcePreviewPolls = 0;
  Timer? _translationStatusTimer; // Timer for polling translation completion
  String? _lastKnownStatus; // Track last known status to detect completion
  bool _isFullscreen = false;
  OverlayEntry? _fullscreenOverlayEntry;
  Map<String, int>? _tokenUsage; // Cached token usage from status API
  Map<String, Map<String, String>> _imageDataMap =
      <String, Map<String, String>>{};
  bool _formatDialogShown = false; // Track if format dialog has been shown
  bool _isConvertOnly = false; // True when task is convert-only (skip translation)

  @override
  void initState() {
    super.initState();
    _isMergedView = widget.initialMergedView;
    // Initialize with provided paragraphs if available
    _sourceParagraphs = widget.initialSourceParagraphs ?? <String>[];
    _targetParagraphs = widget.initialTargetParagraphs ?? <String>[];

    // Initialize pagination controller for segments
    _initSegmentsPagination();

    // If no initial paragraphs, try to load from backend
    if (_sourceParagraphs.isEmpty && _targetParagraphs.isEmpty) {
      _loadTranslationContent();
    } else {
      _isLoading = false;
    }

    // Load task status to check for attachments
    _loadTaskStatus();

    // Load source preview segments if available
    _startSourcePreviewPolling();

    // Start polling translation status to detect completion
    _startTranslationStatusPolling();

    // No scroll synchronization needed - single scroll controller handles both sides
  }

  void _setSelectedExclusionFilters(Set<String> filters) {
    // Keep both in sync (legacy code reads _selectedExclusionFilters)
    _selectedExclusionFilters = filters;
    _selectedExclusionFiltersNotifier.value = filters;
  }

  /// Load task status to get attachments (e.g., glossary) and token usage
  /// Token usage is only loaded when translation is completed (called once when status changes to completed)
  Future<void> _loadTaskStatus() async {
    if (!mounted) return;
    final String taskId = _apiTaskId();
    if (taskId == 'pending') return;

    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> status = await svc.getStatus(taskId);
      if (!mounted) return;

      final String currentStatus =
          (status['status'] ?? '').toString().toLowerCase();

      // Detect convert-only / copy-source-only mode from backend task state
      final bool isConvertOnly = status['convert_only'] == true ||
          status['copy_source_only'] == true;
      if (isConvertOnly != _isConvertOnly && mounted) {
        setState(() {
          _isConvertOnly = isConvertOnly;
        });
      }

      final Map<String, dynamic>? attachments =
          status['attachments'] as Map<String, dynamic>?;
      if (attachments != null) {
        // Attachments are available but not used in this widget
      }

      // Set default formats (image) for tables and equations if present
      // No dialog popup - use defaults directly for review phase
      final bool isPdfFile =
          widget.fileName?.toLowerCase().endsWith('.pdf') ?? false;
      final bool hasTables = status['has_tables'] as bool? ?? false;
      final bool hasInterlineEquations =
          status['has_interline_equations'] as bool? ?? false;
      if (isPdfFile &&
          (hasTables || hasInterlineEquations) &&
          !_formatDialogShown &&
          mounted) {
        // Set default formats to backend defaults (html for table, text for equation)
        // without showing dialog
        final formatNotifier = ref.read(
          formatSettingsProviderFamily(taskId).notifier,
        );
        if (hasTables) {
          formatNotifier.setTableFormat('html'); // Backend default
        }
        if (hasInterlineEquations) {
          formatNotifier.setEquationFormat('text'); // Backend default
        }
        setState(() {
          _formatDialogShown = true;
        });
      }

      // Only extract token usage when translation is completed
      if (currentStatus == 'completed') {
        final tokenUsageData = status['token_usage'];

        if (tokenUsageData != null && tokenUsageData is Map) {
          final totalTokens = tokenUsageData['total_tokens'] is int
              ? tokenUsageData['total_tokens']
              : 0;

          // Update token usage even if totalTokens is 0 (to show statistics)
          if (totalTokens >= 0 && mounted) {
            setState(() {
              _tokenUsage = <String, int>{
                'input_tokens': tokenUsageData['input_tokens'] is int
                    ? tokenUsageData['input_tokens']
                    : 0,
                'cached_tokens': tokenUsageData['cached_tokens'] is int
                    ? tokenUsageData['cached_tokens']
                    : 0,
                'output_tokens': tokenUsageData['output_tokens'] is int
                    ? tokenUsageData['output_tokens']
                    : 0,
                'reasoning_tokens': tokenUsageData['reasoning_tokens'] is int
                    ? tokenUsageData['reasoning_tokens']
                    : 0,
                'total_tokens': totalTokens,
              };
            });
          }
        }
      }
    } catch (e) {
      // Attachment loading is optional, fail silently
    }
  }

  // ===== Source Preview =====
  List<String> _sourcePreviewSegments = <String>[];
  bool _sourcePreviewReady = false;
  bool _loadingSourcePreview = false;

  void _startSourcePreviewPolling() {
    _sourcePreviewTimer?.cancel();
    _sourcePreviewPolls = 0;
    // Starting source preview polling (logging removed)
    _sourcePreviewTimer =
        Timer.periodic(const Duration(milliseconds: 800), (Timer t) async {
      _sourcePreviewPolls++;
      await _loadSourcePreview();
      if (!mounted) {
        // Widget not mounted, stopping polling (logging removed)
        t.cancel();
        return;
      }
      // Only stop polling if:
      // 1. Preview is ready AND we have segments, OR
      // 2. We have segments (even if not ready), OR
      // 3. We've polled too many times (50 instead of 20 to allow more time for conversion)
      final bool shouldStop =
          (_sourcePreviewReady && _sourcePreviewSegments.isNotEmpty) ||
              _sourcePreviewSegments.isNotEmpty ||
              _sourcePreviewPolls >= 50;

      if (shouldStop) {
        // Stopping source preview polling (logging removed)
        t.cancel();
      }
    });
  }

  Future<void> _loadSourcePreview() async {
    if (_loadingSourcePreview ||
        _apiTaskId().isEmpty ||
        _apiTaskId() == 'pending') {
      return;
    }
    setState(() {
      _loadingSourcePreview = true;
    });
    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> res =
          await svc.getSourcePreview(_apiTaskId(), limit: 50);
      // Try both 'segments' and 'items' keys for compatibility
      final List<dynamic>? segmentsList =
          res['segments'] as List? ?? res['items'] as List?;
      // Convert segments to strings - handle both string and Map cases
      // IMPORTANT: For source preview, we should always use the original text, not translated text
      // If the segment is a Map, it might have both 'source_text' and 'target_text'
      // We should ONLY use 'source_text' for source preview, and never use 'target_text'
      final List<String> segments = segmentsList?.map((e) {
            if (e is String) {
              return e;
            } else if (e is Map) {
              // If it's a Map, extract text (API returns 'text' field for source preview)
              // Fallback to 'source_text' for backward compatibility
              // NEVER use target_text for source preview - it should always be the original text
              final String? sourceText =
                  (e['text'] as String?) ?? (e['source_text'] as String?);
              if (sourceText != null && sourceText.isNotEmpty) {
                return sourceText;
              }
              // Fallback: if text/source_text is not available, use the string representation
              // Warning: segment Map missing text/source_text, using toString() (logging removed)
              return e.toString();
            } else {
              return e.toString();
            }
          }).toList() ??
          <String>[];
      final bool ready = res['ready'] == true;

      // Debug logging
      // _translationResultLog(
      //     '[SourcePreview] Poll #$_sourcePreviewPolls: ready=$ready, segments count=${segments.length}, total_segments=${res['total_segments']}');

      final Map<String, Map<String, String>> parsedImageMap =
          _parseImageDataMap(res['image_data_map']);
      setState(() {
        _sourcePreviewSegments = segments;
        _sourcePreviewReady = ready;
        if (parsedImageMap.isNotEmpty) {
          _imageDataMap = parsedImageMap;
        }
        // Do NOT seed segments from source preview before translation completes
        // This prevents showing 50 segments in the UI before translation results are available
        // The _loadSegmentsFromApi method will correctly populate source and target from the segments API
        // Only use source preview for metadata (image_data_map), not for displaying segments
      });
    } catch (e) {
      _translationResultLog('[SourcePreview] Error loading preview: $e');
      // ignore
    } finally {
      if (mounted) {
        setState(() {
          _loadingSourcePreview = false;
        });
      }
    }
  }

  @override
  void didUpdateWidget(TranslationResultPreview oldWidget) {
    super.didUpdateWidget(oldWidget);

    // If taskId changed (e.g., from 'pending' to real taskId, or new translation task),
    // reload the content
    if (oldWidget.taskId != widget.taskId) {
      // Reset status tracking
      _lastKnownStatus = null;

      if (widget.taskId != 'pending') {
        // Clear existing content
        setState(() {
          _sourceParagraphs = <String>[];
          _targetParagraphs = <String>[];
          _isLoading = true;
          _loadingError = null;
          // Clear segment-related state
          _segmentPlatforms.clear();
          _failedSegments.clear();
          _failureReasons.clear();
          _markedRetrySegments.clear();
          _excludedSegments.clear();
          _usedPlatformsForSegment.clear();
          _imageSegments.clear();
          _modifiedSegments.clear();
          _editingSegments.clear();
          _retranslatingSegments.clear();
        });

        // Reload content for new taskId
        _loadTranslationContent();
        _loadTaskStatus();
        _startSourcePreviewPolling();
        _startTranslationStatusPolling();
      } else {
        // TaskId changed to 'pending', stop polling
        _translationStatusTimer?.cancel();
      }
    }
  }

  /// Poll translation status to detect completion and reload content
  void _startTranslationStatusPolling() {
    _translationStatusTimer?.cancel();
    if (_apiTaskId() == 'pending') return;

    _translationStatusTimer =
        Timer.periodic(const Duration(seconds: 2), (Timer t) async {
      if (!mounted || _apiTaskId() == 'pending') {
        t.cancel();
        return;
      }

      try {
        final String pollTaskId = _apiTaskId();
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> status = await svc.getStatus(pollTaskId);
        if (!mounted) {
          t.cancel();
          return;
        }

        final String currentStatus =
            (status['status'] ?? '').toString().toLowerCase();

        // Detect convert-only / copy-source-only mode from backend task state
        final bool isConvertOnly = status['convert_only'] == true ||
            status['copy_source_only'] == true;
        if (isConvertOnly != _isConvertOnly && mounted) {
          setState(() {
            _isConvertOnly = isConvertOnly;
          });
        }

        // If status changed to completed or failed, reload translation content
        if (_lastKnownStatus != null &&
            _lastKnownStatus != currentStatus &&
            (currentStatus == 'completed' || currentStatus == 'failed')) {
          // Translation just completed, reload content and status (to get token usage)
          if (mounted) {
            _loadTranslationContent();
            // Load token usage only after translation is completed
            if (currentStatus == 'completed') {
              _loadTaskStatus(); // Reload status to get token usage (only once when completed)
            }
          }
          t.cancel(); // Stop polling after completion
          return;
        }

        // If status is already completed but we haven't loaded token usage yet, try to load it
        if (currentStatus == 'completed' &&
            _tokenUsage == null &&
            mounted) {
          _loadTaskStatus();
        }

        _lastKnownStatus = currentStatus;

        // Stop polling if already completed or failed
        if (currentStatus == 'completed' ||
            currentStatus == 'failed' ||
            currentStatus == 'cancelled') {
          t.cancel();
        }
      } catch (e) {
        // Ignore errors, continue polling
        _translationResultLog(
          '[TranslationResultPreview] Status polling error: $e',
        );
      }
    });
  }

  @override
  void dispose() {
    _selectedExclusionFiltersNotifier.dispose();
    _highlightedIndexNotifier.dispose();
    _scrollManager?.dispose();
    _comparisonScrollController.dispose();
    if (_segmentsPaginationController != null) {
      _segmentsPaginationController!.removeListener(_onPaginationChanged);
      _segmentsPaginationController!.dispose();
    }
    _fullscreenOverlayEntry?.remove();
    _fullscreenOverlayEntry = null;
    _sourcePreviewTimer?.cancel();
    _translationStatusTimer?.cancel();
    super.dispose();
  }

  /// Initialize pagination controller for translation segments
  void _initSegmentsPagination() {
    _segmentsPaginationController = PagedListController<SegmentPair>(
      initialPageSize: 1000, // Default page size for Translate stage
      fetcher: (int offset, int limit) async =>
          _fetchSegmentsPage(offset, limit),
      itemConverter: (Object? item) {
        // Convert Map to SegmentPair
        if (item is Map) {
          final int index = item['index'] as int? ?? 0;
          final String sourceText = item['source_text'] as String? ?? '';
          final Map<String, dynamic> metadata =
              _allSegmentsMetadata[index] ?? <String, dynamic>{};
          // CRITICAL: Always use target_text from _allSegmentsMetadata if available
          // This ensures that cleared segments and other updates are immediately reflected
          // Do NOT fallback to sourceText - empty target means translation failed
          final String? metadataTargetText = metadata['target_text'] as String?;
          final String? metadataModifiedText =
              metadata['modified_text'] as String?;
          final String? itemTargetText = item['target_text'] as String?;
          final String targetText = metadataTargetText ??
              metadataModifiedText ??
              itemTargetText ??
              ''; // Use empty string if no translation (not source text)

          // When a segment is excluded, it should be rendered using the excluded
          // style instead of failed style. Even if backend metadata still marks
          // it as failed, UI should treat excluded segments as non-failed.
          final bool isExcluded =
              metadata['is_excluded'] as bool? ?? false;
          final bool rawIsFailed =
              metadata['is_failed'] as bool? ?? false;
          final bool effectiveIsFailed = isExcluded ? false : rawIsFailed;

          return SegmentPair(
            index: index,
            sourceText: sourceText,
            targetText: targetText,
            platformUsed: metadata['platform_used'] as String?,
            isImage: metadata['is_image'] as bool? ?? false,
            isFailed: effectiveIsFailed,
            failureReason: metadata['failure_reason'] as String?,
            needsRetry: metadata['needs_retry'] as bool? ?? false,
            isExcluded: isExcluded,
            exclusionReason: metadata['exclusion_reason'] as String?,
            usedPlatforms: (metadata['used_platforms'] as List<dynamic>?)
                    ?.map((e) => e.toString())
                    .toList() ??
                <String>[],
          );
        }
        throw ArgumentError('Invalid item type');
      },
    );

    // Add listener to save and restore scroll position during pagination
    _segmentsPaginationController!.addListener(_onPaginationChanged);
  }

  void _onPaginationChanged() {
    if (!mounted || _segmentsPaginationController == null) return;

    // Update segment pair keys for current page
    _updateSegmentPairKeys();

    // Save current scroll position before pagination changes
    _scrollManager?.saveScrollPosition();

    // Restore scroll position after layout
    _scrollManager?.restoreScrollPosition();
  }

  /// Update segment pair keys for current pagination page
  void _updateSegmentPairKeys() {
    if (_segmentsPaginationController == null) return;

    final List<SegmentPair> items = _segmentsPaginationController!.items;
    final int offset = _segmentsPaginationController!.offset;

    // Update keys for current page items
    for (int i = 0; i < items.length; i++) {
      final int globalIndex = offset + i;
      if (!segmentPairKeys.containsKey(globalIndex)) {
        segmentPairKeys[globalIndex] = GlobalKey();
      }
    }
  }

  /// Get filtered segment indices based on selected filters (for rebuild mode)
  List<int> _getFilteredSegmentIndices() {
    // If no filters are selected, return all indices
    if (_selectedExclusionFilters.isEmpty) {
      // Clear cache when filters are cleared
      _cachedFilteredIndices = null;
      _cachedFilteredIndicesFilters = null;
      _cachedFilteredIndicesTotalCount = null;
      return List.generate(_totalSegmentsCount, (i) => i);
    }

    final bool cacheValid = _cachedFilteredIndices != null &&
        _cachedFilteredIndicesFilters != null &&
        _cachedFilteredIndicesTotalCount != null &&
        _cachedFilteredIndicesTotalCount == _totalSegmentsCount &&
        _cachedFilteredIndicesFilters!.length ==
            _selectedExclusionFilters.length &&
        _cachedFilteredIndicesFilters!.containsAll(_selectedExclusionFilters) &&
        _selectedExclusionFilters.containsAll(_cachedFilteredIndicesFilters!);

    if (cacheValid) {
      return _cachedFilteredIndices!;
    }

    // Cache miss或无效，重新计算
    // failed 过滤：直接使用 _failedSegments
    if (_selectedExclusionFilters.contains('failed')) {
      final List<int> filteredIndices = _failedSegments.keys.toList()..sort();
      // Update cache
      _cachedFilteredIndices = filteredIndices;
      _cachedFilteredIndicesFilters =
          Set<String>.from(_selectedExclusionFilters);
      _cachedFilteredIndicesTotalCount = _totalSegmentsCount;
      return filteredIndices;
    }

    // included 过滤：生成全部索引后去掉已排除的
    if (_selectedExclusionFilters.contains('included')) {
      final Set<int> excludedSet = _excludedSegments.keys.toSet();
      final List<int> filteredIndices = List.generate(
        _totalSegmentsCount,
        (index) => index,
        growable: false,
      ).where((index) => !excludedSet.contains(index)).toList();
      // Update cache
      _cachedFilteredIndices = filteredIndices;
      _cachedFilteredIndicesFilters =
          Set<String>.from(_selectedExclusionFilters);
      _cachedFilteredIndicesTotalCount = _totalSegmentsCount;
      return filteredIndices;
    }

    // all_excluded 过滤：直接使用 _excludedSegments
    if (_selectedExclusionFilters.contains('all_excluded')) {
      final List<int> filteredIndices = _excludedSegments.keys.toList()..sort();
      // Update cache
      _cachedFilteredIndices = filteredIndices;
      _cachedFilteredIndicesFilters =
          Set<String>.from(_selectedExclusionFilters);
      _cachedFilteredIndicesTotalCount = _totalSegmentsCount;
      return filteredIndices;
    }

    // Normal filter: show segments matching selected categories (detected type).
    // CRITICAL: Do NOT require segment to be excluded; Translate phase needs
    // filters to work for default-not-excluded categories too.
    final List<int> filteredIndices = <int>[];
    for (int index = 0; index < _totalSegmentsCount; index++) {
      final Map<String, dynamic> metadata =
          _allSegmentsMetadata[index] ?? <String, dynamic>{};
      final String? filterKey = segmentFilterKeyFromMetadata(metadata);
      if (filterKey != null && _selectedExclusionFilters.contains(filterKey)) {
        filteredIndices.add(index);
      }
    }

    // Update cache
    _cachedFilteredIndices = filteredIndices;
    _cachedFilteredIndicesFilters = Set<String>.from(_selectedExclusionFilters);
    _cachedFilteredIndicesTotalCount = _totalSegmentsCount;

    return filteredIndices;
  }

  /// Clear cached filtered indices (call when filters, segments count, or metadata changes)
  void _clearFilteredIndicesCache() {
    _cachedFilteredIndices = null;
    _cachedFilteredIndicesFilters = null;
    _cachedFilteredIndicesTotalCount = null;
  }

  /// Clear cached exclusion counts (call when metadata or excluded segments change)
  void _clearExclusionCountsCache() {
    _cachedExclusionCounts = null;
    _cachedExclusionCountsTotalSegments = null;
    _cachedExclusionCountsMetadataSize = null;
  }

  /// Fetch a page of segments (combines source preview and translation segments)
  Future<Map<String, dynamic>> _fetchSegmentsPage(int offset, int limit) async {
    // Fetch translation segments metadata if not loaded yet
    if (_allSegmentsMetadata.isEmpty && _totalSegmentsCount == 0) {
      await _loadAllSegmentsMetadata();
    }

    // rebuild 模式下并且有过滤时，先按过滤结果分页
    if (_filterMode == 'rebuild' && _selectedExclusionFilters.isNotEmpty) {
      // Get filtered segment indices based on selected filters
      final List<int> filteredIndices = _getFilteredSegmentIndices();

      // Apply pagination to filtered indices
      final int start = offset;
      final int end = (offset + limit).clamp(0, filteredIndices.length);
      final List<int> pageIndices = filteredIndices.sublist(start, end);

      if (pageIndices.isEmpty) {
        return <String, dynamic>{
          'items': <Map<String, dynamic>>[],
          'total': filteredIndices.length,
          'offset': offset,
          'limit': limit,
        };
      }

      // PERFORMANCE: If we already have full _sourceParagraphs in memory,
      // avoid hitting /source-preview API again for filter changes.
      final bool hasFullLocalSource = _sourceParagraphs.isNotEmpty &&
          _sourceParagraphs.length == _totalSegmentsCount;

      if (hasFullLocalSource) {
        final List<Map<String, dynamic>> segmentPairs =
            <Map<String, dynamic>>[];
        for (final int globalIndex in pageIndices) {
          final String sourceText = globalIndex < _sourceParagraphs.length
              ? _sourceParagraphs[globalIndex]
              : '';
          final Map<String, dynamic> metadata =
              _allSegmentsMetadata[globalIndex] ?? <String, dynamic>{};
          final String? metadataTargetText = metadata['target_text'] as String?;
          final String? metadataModifiedText =
              metadata['modified_text'] as String?;
          final String targetText = metadataTargetText ??
              metadataModifiedText ??
              (_targetParagraphs.length > globalIndex
                  ? _targetParagraphs[globalIndex]
                  : '');

          segmentPairs.add(<String, dynamic>{
            'index': globalIndex,
            'source_text': sourceText,
            'target_text': targetText,
            'metadata': metadata,
          });
        }

        return <String, dynamic>{
          'items': segmentPairs,
          'total': filteredIndices.length,
          'offset': offset,
          'limit': limit,
        };
      }

      // Fallback: Fetch source segments for filtered indices from backend.
      // Note: API doesn't support fetching by specific indices, so we fetch a range
      // that covers all needed indices, then filter to only the ones we need.
      final TranslationService svc = TranslationService();
      final int minIndex = pageIndices.reduce((a, b) => a < b ? a : b);
      final int maxIndex = pageIndices.reduce((a, b) => a > b ? a : b);
      final int fetchOffset = minIndex;
      final int fetchLimit = maxIndex - minIndex + 1;

      final Map<String, dynamic> sourcePreview = await svc.getSourcePreview(
        _apiTaskId(),
        offset: fetchOffset,
        limit: fetchLimit,
      );

      final List<dynamic> sourceItems =
          sourcePreview['items'] as List<dynamic>? ??
              sourcePreview['segments'] as List<dynamic>? ??
              <dynamic>[];

      // Build a map of index to source text for quick lookup
      final Map<int, String> indexToSourceText = <int, String>{};
      final Set<int> neededIndices = pageIndices.toSet();

      for (var i = 0; i < sourceItems.length; i++) {
        final dynamic item = sourceItems[i];
        final int segmentIndex = fetchOffset + i;

        // Only process indices we actually need
        if (!neededIndices.contains(segmentIndex)) {
          continue;
        }

        String sourceText;
        if (item is String) {
          sourceText = item;
        } else if (item is Map) {
          // Try to get segment_index from response if available
          final int? providedIndex = item['segment_index'] as int?;
          final int actualIndex = providedIndex ?? segmentIndex;
          sourceText = (item['source_text'] as String?) ??
              (item['text'] as String?) ??
              item.toString();
          indexToSourceText[actualIndex] = sourceText;
        } else {
          sourceText = item.toString();
          indexToSourceText[segmentIndex] = sourceText;
        }
      }

      // Build segment pairs for filtered indices
      final List<Map<String, dynamic>> segmentPairs = <Map<String, dynamic>>[];
      for (final int globalIndex in pageIndices) {
        final Map<String, dynamic> metadata =
            _allSegmentsMetadata[globalIndex] ?? <String, dynamic>{};
        final String sourceText = indexToSourceText[globalIndex] ?? '';
        final String? metadataTargetText = metadata['target_text'] as String?;
        final String? metadataModifiedText =
            metadata['modified_text'] as String?;
        final String targetText = metadataTargetText ??
            metadataModifiedText ??
            (_targetParagraphs.length > globalIndex
                ? _targetParagraphs[globalIndex]
                : '');

        segmentPairs.add(<String, dynamic>{
          'index': globalIndex,
          'source_text': sourceText,
          'target_text': targetText,
          'metadata': metadata,
        });
      }

      return <String, dynamic>{
        'items': segmentPairs,
        'total': filteredIndices.length,
        'offset': offset,
        'limit': limit,
      };
    }

    // For page mode or no filters: use original pagination logic
    final TranslationService svc = TranslationService();

    // Fetch source segments from source-preview API (paginated)
    final Map<String, dynamic> sourcePreview = await svc.getSourcePreview(
      _apiTaskId(),
      offset: offset,
      limit: limit,
    );

    final int totalSegments = sourcePreview['total_segments'] as int? ??
        sourcePreview['total'] as int? ??
        0;

    final List<dynamic> sourceItems =
        sourcePreview['items'] as List<dynamic>? ??
            sourcePreview['segments'] as List<dynamic>? ??
            <dynamic>[];

    // Convert source items to strings and extract segment indices
    final List<String> sourceTexts = <String>[];
    final List<int> segmentIndices = <int>[];
    int itemsWithoutIndex = 0;

    for (var i = 0; i < sourceItems.length; i++) {
      final dynamic item = sourceItems[i];
      String sourceText;
      int segmentIndex;

      if (item is String) {
        sourceText = item;
        // Fallback: use offset + i if no index available
        segmentIndex = offset + i;
        itemsWithoutIndex++;
      } else if (item is Map) {
        sourceText = (item['source_text'] as String?) ??
            (item['text'] as String?) ??
            item.toString();
        // CRITICAL: Use segment_index from response if available, otherwise fallback to offset + i
        final int? providedIndex = item['segment_index'] as int?;
        if (providedIndex != null) {
          segmentIndex = providedIndex;
        } else {
          segmentIndex = offset + i;
          itemsWithoutIndex++;
        }
      } else {
        sourceText = item.toString();
        segmentIndex = offset + i;
        itemsWithoutIndex++;
      }

      sourceTexts.add(sourceText);
      segmentIndices.add(segmentIndex);
    }

    // Log warning if many items are missing segment_index
    if (itemsWithoutIndex > 0) {
      _translationResultLog(
        '[PAGINATION] WARNING: $itemsWithoutIndex items missing segment_index in page (offset=$offset, limit=$limit)',
        level: LogLevel.warn,
      );
    }

    // Build segment pairs for this page using actual segment indices from response
    final List<Map<String, dynamic>> segmentPairs = <Map<String, dynamic>>[];
    int unmatchedCount = 0;

    for (var i = 0; i < sourceTexts.length; i++) {
      final int globalIndex =
          segmentIndices[i]; // Use actual segment_index from response
      final String sourceText = sourceTexts[i];
      final Map<String, dynamic> metadata =
          _allSegmentsMetadata[globalIndex] ?? <String, dynamic>{};
      final bool hasMetadata = metadata.isNotEmpty;

      if (!hasMetadata) {
        unmatchedCount++;
      }

      // Do NOT fallback to sourceText - empty target means translation failed
      final String? metadataTargetText = metadata['target_text'] as String?;
      final String? metadataModifiedText = metadata['modified_text'] as String?;
      final String targetText = metadataTargetText ??
          metadataModifiedText ??
          ''; // Use empty string if no translation (not source text)

      segmentPairs.add(<String, dynamic>{
        'index': globalIndex,
        'source_text': sourceText,
        'target_text': targetText,
      });
    }

    // Log warning if many segments are unmatched
    if (unmatchedCount > 0) {
      _translationResultLog(
        '[PAGINATION] WARNING: $unmatchedCount segments have no metadata in page (offset=$offset, limit=$limit)',
        level: LogLevel.warn,
      );
    }

    return <String, dynamic>{
      'items': segmentPairs,
      'total': _totalSegmentsCount > 0 ? _totalSegmentsCount : totalSegments,
      'offset': offset,
      'limit': limit,
    };
  }

  /// Load all segments metadata from translation-segments API (one-time load)
  Future<void> _loadAllSegmentsMetadata() async {
    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> segmentsData =
          await svc.getTranslationSegments(_apiTaskId());
      final List<dynamic>? segments =
          segmentsData['segments'] as List<dynamic>?;

      if (segments != null) {
        for (final segment in segments) {
          final int index = segment['segment_index'] as int? ?? 0;
          final String targetText = segment['modified_text'] as String? ??
              segment['target_text'] as String? ??
              '';
          final String? detectedExclusionReason =
              segment['detected_exclusion_reason'] as String?;
          final Map<String, dynamic>? exclusionMetadata =
              segment['exclusion_metadata'] is Map
                  ? Map<String, dynamic>.from(
                      segment['exclusion_metadata'] as Map<dynamic, dynamic>,
                    )
                  : null;

          _allSegmentsMetadata[index] = <String, dynamic>{
            'target_text': targetText,
            'platform_used': segment['platform_used'] as String?,
            'is_image': segment['is_image'] as bool? ?? false,
            'is_failed': segment['is_failed'] as bool? ?? false,
            'failure_reason': segment['failure_reason'] as String?,
            'needs_retry': segment['needs_retry'] as bool? ?? false,
            'is_excluded': segment['is_excluded'] as bool? ?? false,
            'exclusion_reason':
                segment['exclusion_reason'] as String?, // keep backend reason
            'status': segment['status']
                as String?, // Include status (e.g., "cleared")
            'used_platforms':
                segment['used_platforms'] as List<dynamic>? ?? <dynamic>[],
            // Exclusion detection metadata for Translate phase filters
            'detected_exclusion_reason': detectedExclusionReason,
            if (exclusionMetadata != null)
              'exclusion_metadata': exclusionMetadata,
          };
        }

        // Determine total count from metadata
        if (_allSegmentsMetadata.isNotEmpty) {
          final int maxIndex =
              _allSegmentsMetadata.keys.reduce((int a, int b) => a > b ? a : b);
          _totalSegmentsCount = maxIndex + 1;
        } else {
          _translationResultLog(
            '[PAGINATION] No metadata loaded: segments list was empty or invalid',
            level: LogLevel.warn,
          );
        }

        // PERFORMANCE: Clear filtered indices cache when metadata is reloaded
        _clearFilteredIndicesCache();
        // Also clear exclusion counts cache so that Segment Type Filters will
        // be recalculated using the latest metadata and global detected counts.
        _cachedExclusionCounts = null;
        _cachedExclusionCountsTotalSegments = null;
        _cachedExclusionCountsMetadataSize = null;
      } else {
        _translationResultLog(
          '[PAGINATION] No segments in response: segments is null',
          level: LogLevel.warn,
        );
      }

      // Read global detected exclusion reason counts from metadata (if present).
      _readGlobalDetectedReasonCounts(segmentsData);
    } catch (e, stackTrace) {
      _translationResultLog(
        '[PAGINATION] Failed to load segments metadata: $e\nStack trace: $stackTrace',
        level: LogLevel.error,
      );
    }
  }

  /// Parse global detected exclusion reason counts from a translation-segments
  /// response and update _globalDetectedReasonCounts for Segment Type Filters.
  void _readGlobalDetectedReasonCounts(
    Map<String, dynamic> segmentsData,
  ) {
    // This is computed in Extract phase and exposed by the translation-segments API
    // to ensure Segment Type Filters enumerate all detected categories, not only
    // those visible in Translate segments.
    final dynamic rawMetadata = segmentsData['metadata'];
    if (rawMetadata is Map) {
      final Map<String, dynamic> metadata = rawMetadata.cast<String, dynamic>();
      _translationResultLog(
        '[EXCLUSION_FILTERS] Raw metadata keys from translation-segments: ${metadata.keys.toList()}',
      );

      final dynamic rawDetected = metadata['detected_exclusion_reason_counts'];
      if (rawDetected is Map) {
        final Map<String, dynamic> detectedCountsDynamic =
            rawDetected.cast<String, dynamic>();
        if (detectedCountsDynamic.isNotEmpty) {
          _globalDetectedReasonCounts = detectedCountsDynamic.map(
            (String key, value) =>
                MapEntry<String, int>(key, (value as num).toInt()),
          );
          final String summary = _globalDetectedReasonCounts!.entries
              .map((MapEntry<String, int> e) => '${e.key}(${e.value})')
              .join(', ');
          _translationResultLog(
            '[EXCLUSION_FILTERS] Parsed detected_exclusion_reason_counts from metadata: $summary',
          );
        } else {
          _translationResultLog(
            '[EXCLUSION_FILTERS] detected_exclusion_reason_counts present but empty in metadata',
          );
          _globalDetectedReasonCounts = null;
        }
      } else if (rawDetected == null) {
        _translationResultLog(
          '[EXCLUSION_FILTERS] metadata has no detected_exclusion_reason_counts field',
        );
        _globalDetectedReasonCounts = null;
      } else {
        _translationResultLog(
          '[EXCLUSION_FILTERS] detected_exclusion_reason_counts has unexpected type: ${rawDetected.runtimeType}',
          level: LogLevel.warn,
        );
        _globalDetectedReasonCounts = null;
      }
    } else {
      _translationResultLog(
        '[EXCLUSION_FILTERS] No metadata map found in translation-segments response (metadata is ${rawMetadata.runtimeType})',
        level: LogLevel.warn,
      );
      _globalDetectedReasonCounts = null;
    }
  }

  /// Update only specific segments without reloading all content
  /// This preserves scroll position and only updates the changed segments
  Future<void> _updateSegmentsOnly(List<int> segmentIndices) async {
    if (segmentIndices.isEmpty) return;

    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> segmentsData =
          await svc.getTranslationSegments(_apiTaskId());
      final List<dynamic>? segments =
          segmentsData['segments'] as List<dynamic>?;

      if (segments == null || segments.isEmpty) return;

      // Create a map of segment_index -> segment for quick lookup
      final Map<int, Map<String, dynamic>> segmentMap =
          <int, Map<String, dynamic>>{};
      for (final segment in segments) {
        final int? index = segment['segment_index'] as int?;
        if (index != null) {
          segmentMap[index] = segment;
        }
      }

      // Update only the specified segments
      if (mounted) {
        setState(() {
          for (final int index in segmentIndices) {
            final Map<String, dynamic>? segment = segmentMap[index];
            if (segment == null) continue;

            // Update target text (even if empty - failed segments should show empty)
            final String targetText = segment['modified_text'] as String? ??
                segment['target_text'] as String? ??
                '';
            // Ensure list is large enough
            while (index >= _targetParagraphs.length) {
              _targetParagraphs.add('');
            }
            // Always update target text (even if empty for failed segments)
            _targetParagraphs[index] = targetText;

            // Update metadata
            final String? platformUsed = segment['platform_used'] as String?;
            final bool isImage = segment['is_image'] as bool? ?? false;
            final bool isFailed = segment['is_failed'] as bool? ?? false;
            final String? failureReason = segment['failure_reason'] as String?;
            final bool needsRetry = segment['needs_retry'] as bool? ?? false;
            final bool isExcluded = segment['is_excluded'] as bool? ?? false;
            final String? exclusionReason =
                segment['exclusion_reason'] as String?;
            final String? detectedExclusionReason =
                segment['detected_exclusion_reason'] as String?;
            final Map<String, dynamic>? exclusionMetadata =
                segment['exclusion_metadata'] is Map
                    ? Map<String, dynamic>.from(
                        segment['exclusion_metadata'] as Map<dynamic, dynamic>,
                      )
                    : null;
            final List<String> usedPlatforms =
                (segment['used_platforms'] as List<dynamic>?)
                        ?.map((e) => e.toString())
                        .toList() ??
                    <String>[];

            // Update segment metadata maps
            if (platformUsed != null && !isImage) {
              _segmentPlatforms[index] = platformUsed;
            }
            if (isFailed && !isImage) {
              _failedSegments[index] = true;
              if (failureReason != null) {
                _failureReasons[index] = failureReason;
              }
            } else {
              _failedSegments.remove(index);
              _failureReasons.remove(index);
            }
            if (needsRetry && !isImage) {
              _markedRetrySegments[index] = true;
            } else {
              _markedRetrySegments.remove(index);
            }
            if (isExcluded) {
              _excludedSegments[index] = true;
            } else {
              _excludedSegments.remove(index);
            }
            if (usedPlatforms.isNotEmpty && !isImage) {
              _usedPlatformsForSegment[index] = usedPlatforms;
            }
            if (isImage) {
              _imageSegments[index] = true;
            } else {
              _imageSegments.remove(index);
            }

            // Update metadata cache for pagination
            _allSegmentsMetadata[index] = <String, dynamic>{
              'target_text': targetText,
              'platform_used': platformUsed,
              'is_image': isImage,
              'is_failed': isFailed,
              'failure_reason': failureReason,
              'needs_retry': needsRetry,
              'is_excluded': isExcluded,
              'exclusion_reason': exclusionReason,
              'used_platforms': usedPlatforms,
              // Exclusion detection metadata for Translate phase filters
              'detected_exclusion_reason': detectedExclusionReason,
              if (exclusionMetadata != null)
                'exclusion_metadata': exclusionMetadata,
            };
          }
        });
      }

      // Also refresh global detected reason counts when we refetch segments,
      // so Segment Type Filters stay in sync with latest backend metadata.
      _readGlobalDetectedReasonCounts(segmentsData);

      _translationResultLog(
        '[UPDATE_SEGMENTS] Updated ${segmentIndices.length} segments: $segmentIndices',
      );
    } catch (e) {
      _translationResultLog(
        '[UPDATE_SEGMENTS] Failed to update segments: $e',
        level: LogLevel.error,
      );
    }
  }

  Future<void> _loadTranslationContent({bool forceRefreshSegments = false}) async {
    // Skip if taskId is 'pending' (not yet submitted)
    if (_apiTaskId() == 'pending') {
      setState(() {
        _isLoading = false;
        _loadingError = null;
      });
      return;
    }

    // No height logging needed - unified panel handles heights naturally

    setState(() {
      _isLoading = true;
      _loadingError = null;
    });

    try {
      final TranslationService svc = TranslationService();

      // First, try to get structured segments from API
      // This works for all workflow types including TS files
      try {
        final Map<String, dynamic> segmentsData = await svc.getTranslationSegments(
          _apiTaskId(),
          forceRefresh: forceRefreshSegments,
        );
        final List<dynamic>? segments =
            segmentsData['segments'] as List<dynamic>?;
        final imageDataMapRaw = segmentsData['image_data_map'];
        final Map<String, Map<String, String>> parsedImageMap =
            _parseImageDataMap(imageDataMapRaw);

        if (segments != null && segments.isNotEmpty) {
          // Log segments data for debugging
          final String first5Segments = segments.take(5).map((s) {
            final int? idx = s['segment_index'] as int?;
            final String target = (s['modified_text'] as String?) ??
                (s['target_text'] as String?) ??
                '';
            final String source = s['source_text'] as String? ?? '';
            final bool isExcluded = s['is_excluded'] as bool? ?? false;
            final bool isImage = s['is_image'] as bool? ?? false;
            return 'idx=$idx, target_len=${target.length}, source_len=${source.length}, excluded=$isExcluded, image=$isImage';
          }).join('; ');
          _translationResultLog(
            '[TRANSLATION_SEGMENTS] Loaded ${segments.length} segments from API. '
            'First 5 segments preview: $first5Segments',
          );

          // Also read global detected exclusion reason counts from metadata so
          // that Segment Type Filters can enumerate all detected categories.
          _readGlobalDetectedReasonCounts(segmentsData);

          // CRITICAL: Source text MUST come from Source Preview API (source_chunks_cache)
          // NO FALLBACK: If Source Preview API is unavailable, we cannot safely display source text
          // Load original text from Source Preview API first (with pagination if needed, max limit is 1000)
          List<String> originalSourceSegments;
          try {
            // First, get total count and first page
            final Map<String, dynamic> firstPageRes =
                await svc.getSourcePreview(
              _apiTaskId(),
              limit: defaultSegmentPreviewLimit,
            );
            final int totalSegments = firstPageRes['total_segments'] as int? ??
                firstPageRes['total'] as int? ??
                0;
            final List<dynamic>? firstPageList =
                firstPageRes['segments'] as List? ??
                    firstPageRes['items'] as List?;

            if (firstPageList == null || firstPageList.isEmpty) {
              throw Exception(
                'Source Preview API returned empty segments list. Task may not be ready yet.',
              );
            }

            originalSourceSegments = firstPageList.map((e) {
              if (e is String) return e;
              if (e is Map) {
                // Extract chunk_id for merged paragraph preview
                final segIndex = e['segment_index'] as int?;
                final chunkId = e['chunk_id'] as int?;
                if (segIndex != null && chunkId != null && chunkId >= 0) {
                  _segmentChunkIds[segIndex] = chunkId;
                }
                // CRITICAL: For MD files, check both 'text' and 'source_text' fields
                // 'text' field contains the actual segment text (including image placeholders)
                // 'source_text' is a fallback
                return (e['text'] as String?) ??
                    (e['source_text'] as String?) ??
                    e.toString();
              }
              return e.toString();
            }).toList();

            // If there are more segments, fetch them in batches (max 1000 per request)
            if (totalSegments > originalSourceSegments.length) {
              var offset = originalSourceSegments.length;
              while (offset < totalSegments) {
                final Map<String, dynamic> nextPageRes =
                    await svc.getSourcePreview(
                  _apiTaskId(),
                  offset: offset,
                  limit: defaultSegmentPreviewLimit,
                );
                final List<dynamic>? nextPageList =
                    nextPageRes['segments'] as List? ??
                        nextPageRes['items'] as List?;
                if (nextPageList == null || nextPageList.isEmpty) {
                  throw Exception(
                    'Source Preview API returned empty page at offset $offset. Expected $totalSegments total segments.',
                  );
                }
                final List<String> nextPageSegments = nextPageList.map((e) {
                  if (e is String) return e;
                  if (e is Map) {
                    // Extract chunk_id for merged paragraph preview
                    final segIndex = e['segment_index'] as int?;
                    final chunkId = e['chunk_id'] as int?;
                    if (segIndex != null && chunkId != null && chunkId >= 0) {
                      _segmentChunkIds[segIndex] = chunkId;
                    }
                    // CRITICAL: For MD files, check both 'text' and 'source_text' fields
                    // 'text' field contains the actual segment text (including image placeholders)
                    // 'source_text' is a fallback
                    return (e['text'] as String?) ??
                        (e['source_text'] as String?) ??
                        e.toString();
                  }
                  return e.toString();
                }).toList();
                originalSourceSegments.addAll(nextPageSegments);
                offset += nextPageSegments.length;
              }
            }

            if (originalSourceSegments.isEmpty) {
              throw Exception(
                'Source Preview API returned no segments. Task may not be ready yet.',
              );
            }

            // Loaded ${originalSourceSegments.length} original segments from Source Preview API (logging removed)
          } catch (e) {
            _translationResultLog(
              '[LOAD_SEGMENTS] ERROR: Source Preview API is required but unavailable: $e. Cannot load translation content without original text.',
              level: LogLevel.error,
            );
            if (mounted) {
              setState(() {
                _loadingError =
                    'Source Preview API unavailable. Cannot load translation content. Please ensure the file has been extracted.';
                _isLoading = false;
              });
            }
            return; // Stop processing - no fallback
          }

          // Initialize source and target lists
          final List<String> sourceList = <String>[];
          final List<String> targetList = <String>[];

          // First pass: Extract all source texts and initialize target with source as fallback
          // Use segment_index to ensure correct ordering
          final int maxIndexFromSegments =
              segments.fold<int>(0, (int max, seg) {
            final int idx = seg['segment_index'] as int? ?? 0;
            return idx > max ? idx : max;
          });

          // Determine the maximum index we need to support
          // Use the larger of: maxIndexFromSegments or originalSourceSegments.length
          final int maxIndex =
              math.max(maxIndexFromSegments, originalSourceSegments.length - 1);

          // Initialize lists with empty strings up to maxIndex
          for (var i = 0; i <= maxIndex; i++) {
            sourceList.add('');
            targetList.add('');
          }

          // Pre-fill sourceList from Source Preview API
          // This ensures all segments from Source Preview API are included, even if not in segments API
          // NOTE: Do NOT pre-fill targetList with source text here - let segments API populate it
          for (var i = 0; i < originalSourceSegments.length; i++) {
            if (i < sourceList.length) {
              sourceList[i] = originalSourceSegments[i];
              // Do NOT initialize target with source here - segments API will provide target_text
              // Only initialize if targetList is too short
              while (targetList.length <= i) {
                targetList
                    .add(''); // Initialize with empty string, not source text
              }
            }
          }

          // Clear existing state maps to ensure clean refresh
          final Map<int, String?> newSegmentPlatforms = <int, String?>{};
          final Map<int, bool> newFailedSegments = <int, bool>{};
          final Map<int, String?> newFailureReasons = <int, String?>{};
          final Map<int, bool> newMarkedRetrySegments = <int, bool>{};
          final Map<int, bool> newExcludedSegments = <int, bool>{};
          final Map<int, List<String>> newUsedPlatformsForSegment =
              <int, List<String>>{};
          final Map<int, bool> newImageSegments = <int, bool>{};

          // Track which segment indices we've seen to detect missing segments
          final Set<int> seenIndices = <int>{};

          // Single pass: Process all segments and fill in source and target
          var processedCount = 0;
          for (final segment in segments) {
            // Extract target_text from segments API (this is the translated text)
            final String targetText = segment['modified_text'] as String? ??
                segment['target_text'] as String? ??
                '';

            // Use segment_index if available, otherwise use current list length
            final int segmentIndex =
                segment['segment_index'] as int? ?? sourceList.length;

            // Log first 10 segments with detailed info
            if (processedCount < 10) {
              final String targetPreview = targetText.length > 100
                  ? '${targetText.substring(0, 100)}...'
                  : targetText;
              _translationResultLog(
                '[TRANSLATION_SEGMENTS] Processing segment $processedCount: '
                'index=$segmentIndex, target_len=${targetText.length}, '
                'target_preview=$targetPreview',
              );
            }
            processedCount++;

            // Extract platform and failure info (same for all workflow types including TS)
            final String? platformUsed = segment['platform_used'] as String?;
            final bool isImage = segment['is_image'] as bool? ??
                false; // Check if this is an image segment

            // CRITICAL: For image segments, use source_text from translation_segments API (contains placeholder)
            // For non-image segments, use Source Preview API (original text with deep split)
            var finalSourceText = '';

            // Extract excluded status early
            final bool isExcluded = segment['is_excluded'] as bool? ?? false;
            final String? exclusionReason =
                segment['exclusion_reason'] as String?;

            if (isImage) {
              // For image segments, use source_text from translation_segments API
              // This contains the placeholder (e.g., <ph-mobi7/Images/image00044.jpeg>)
              finalSourceText = segment['source_text'] as String? ?? '';
              if (processedCount <= 10) {
                _translationResultLog(
                  '[TRANSLATION_SEGMENTS] Image segment $segmentIndex: '
                  'source_text=$finalSourceText, target_text=$targetText',
                );
              }
            } else if (segmentIndex >= 0 &&
                segmentIndex < originalSourceSegments.length) {
              // Use Source Preview API (original text with deep split) for non-image segments
              finalSourceText = originalSourceSegments[segmentIndex];

              // Log first 10 segments with source and target comparison
              if (processedCount <= 10) {
                final String sourcePreview = finalSourceText.length > 100
                    ? '${finalSourceText.substring(0, 100)}...'
                    : finalSourceText;
                _translationResultLog(
                  '[TRANSLATION_SEGMENTS] Segment $segmentIndex: '
                  'source_len=${finalSourceText.length}, target_len=${targetText.length}, '
                  'source_preview=$sourcePreview',
                );
              }
            } else {
              // Segment index out of bounds - this is a data inconsistency error
              _translationResultLog(
                '[LOAD_SEGMENTS] ERROR: Segment $segmentIndex is out of bounds for Source Preview API (length: ${originalSourceSegments.length}). This indicates a data inconsistency between Source Preview API and segments API.',
                level: LogLevel.error,
              );
              // Use empty string - this will show as missing source text
              finalSourceText = '';
            }
            final bool isFailed = segment['is_failed'] as bool? ?? false;
            final String? failureReason = segment['failure_reason'] as String?;
            final bool needsRetry = segment['needs_retry'] as bool? ?? false;

            // Excluded segments are tracked in the summary log at the end
            final List<String> usedPlatforms =
                (segment['used_platforms'] as List<dynamic>?)
                        ?.map((e) => e.toString())
                        .toList() ??
                    <String>[];

            // Always add segment to lists, even if finalSourceText is empty
            // This ensures all segments from segments API are represented
            seenIndices.add(segmentIndex);

            // Ensure index is within bounds
            while (sourceList.length <= segmentIndex) {
              sourceList.add('');
              targetList.add('');
            }

            // CRITICAL: Always use finalSourceText (from Source Preview API or validated segments API) for source list
            // This ensures source is always the original text with deep split when available
            sourceList[segmentIndex] = finalSourceText;

            // CRITICAL: Always update target text from API response, even if empty
            // Empty target_text means translation failed, not that we should use source text
            // Ensure targetList is long enough
            while (targetList.length <= segmentIndex) {
              targetList.add('');
            }
            // Always set target text from API (empty string if translation failed)
            targetList[segmentIndex] = targetText;

            // Log if target is empty (translation failed)
            if (targetText.isEmpty && finalSourceText.isNotEmpty) {
              final String sourcePreview =
                  sanitizeForLog(finalSourceText, maxLength: 30);
              _translationResultLog(
                '[LOAD_SEGMENTS] Segment $segmentIndex has empty target_text. Translation failed. User can retranslate via "Translate Failed". source_text="$sourcePreview"',
              );
            }

            // Store platform and failure info by index (same for TS and DOCX)
            // Image segments should not be marked as failed or retry
            if (platformUsed != null && !isImage) {
              newSegmentPlatforms[segmentIndex] = platformUsed;
            }
            // Image segments should never be marked as failed
            if (isFailed && !isImage) {
              newFailedSegments[segmentIndex] = true;
              if (failureReason != null) {
                newFailureReasons[segmentIndex] = failureReason;
              }
            }
            // Note: We don't clear failure state here - let it be overwritten by new data
            // Image segments should never be marked for retry
            if (needsRetry && !isImage) {
              newMarkedRetrySegments[segmentIndex] = true;
            }
            // Store excluded segments (including image segments that were excluded in Extract page)
            if (isExcluded) {
              newExcludedSegments[segmentIndex] = true;
            }
            if (usedPlatforms.isNotEmpty && !isImage) {
              newUsedPlatformsForSegment[segmentIndex] = usedPlatforms;
            }

            // Store image segment info
            if (isImage) {
              newImageSegments[segmentIndex] = true;
            }

            // Store metadata for pagination
            _allSegmentsMetadata[segmentIndex] = <String, dynamic>{
              'target_text': targetText,
              'platform_used': platformUsed,
              'is_image': isImage,
              'is_failed': isFailed,
              'failure_reason': failureReason,
              'needs_retry': needsRetry,
              'is_excluded': isExcluded,
              'exclusion_reason': exclusionReason,
              'used_platforms': usedPlatforms,
            };
          }

          // Log summary after processing all segments
          final int totalWithTarget = segments.where((s) {
            final String target = (s['modified_text'] as String?) ??
                (s['target_text'] as String?) ??
                '';
            return target.isNotEmpty;
          }).length;
          final int totalExcluded =
              segments.where((s) => s['is_excluded'] as bool? ?? false).length;
          final int totalImages =
              segments.where((s) => s['is_image'] as bool? ?? false).length;
          final int totalFailed =
              segments.where((s) => s['is_failed'] as bool? ?? false).length;

          _translationResultLog(
            '[TRANSLATION_SEGMENTS] Summary: total=${segments.length}, '
            'with_target=$totalWithTarget, excluded=$totalExcluded, '
            'images=$totalImages, failed=$totalFailed',
            level: LogLevel.info,
          );

          // Update total segments count
          final int oldTotalCount = _totalSegmentsCount;
          if (_allSegmentsMetadata.isNotEmpty) {
            _totalSegmentsCount = _allSegmentsMetadata.keys
                    .reduce((int a, int b) => a > b ? a : b) +
                1;
          } else {
            // Fallback to sourceList length if no metadata
            _totalSegmentsCount = sourceList.length;
          }

          // PERFORMANCE: Clear filtered indices cache when total count changes
          if (oldTotalCount != _totalSegmentsCount) {
            _clearFilteredIndicesCache();
          }

          // Fill in missing segments from Source Preview API
          // If Source Preview API has segments that are not in segments API, fill them in
          final List<int> missingFromSegmentsApi = <int>[];
          for (var i = 0; i < originalSourceSegments.length; i++) {
            if (!seenIndices.contains(i)) {
              // This segment exists in Source Preview API but not in segments API
              missingFromSegmentsApi.add(i);

              // Ensure lists are large enough
              while (sourceList.length <= i) {
                sourceList.add('');
                targetList.add('');
              }

              // Fill in source text from Source Preview API
              sourceList[i] = originalSourceSegments[i];

              // Do NOT use source text as target text - keep target empty if no translation
              // Empty target will be marked as failed, user can retranslate
              while (targetList.length <= i) {
                targetList.add(''); // Initialize with empty string
              }
              // Do NOT fill target with source - let it remain empty if no translation
            }
          }
          if (missingFromSegmentsApi.isNotEmpty) {
            _translationResultLog(
              '[LOAD_SEGMENTS] Found ${missingFromSegmentsApi.length} segments in Source Preview API but not in segments API (indices: $missingFromSegmentsApi). Filled in from Source Preview API.',
              level: LogLevel.info,
            );
          }

          // Check for missing segments (segments in source but not in translation results)
          if (sourceList.length > seenIndices.length) {
            final List<int> missingIndices = <int>[];
            for (var i = 0; i < sourceList.length; i++) {
              if (!seenIndices.contains(i)) {
                missingIndices.add(i);
                // Ensure targetList is long enough, but do NOT fill with source text
                // Missing segments from API should have empty target (will be marked as failed)
                while (targetList.length <= i) {
                  targetList
                      .add(''); // Initialize with empty string, not source
                }
                // Do NOT fill target with source - keep empty if segment missing from API
              }
            }
            if (missingIndices.isNotEmpty) {
              _translationResultLog(
                '[LOAD_SEGMENTS] Warning: ${missingIndices.length} segments missing from translation results (indices: $missingIndices). Using source text as fallback.',
                level: LogLevel.warn,
              );
            }
          }

          // CRITICAL: Always overwrite _sourceParagraphs and _targetParagraphs with data from segments API
          // This ensures we use the correct source_text from backend, not potentially corrupted data from source preview
          // Ensure both lists have the same length to prevent missing segments
          final int maxLength = math.max(sourceList.length, targetList.length);
          while (sourceList.length < maxLength) {
            sourceList.add('');
          }
          while (targetList.length < maxLength) {
            targetList.add('');
          }

          // Metadata is already stored during segment processing above
          // Just ensure total count is set
          if (_totalSegmentsCount == 0) {
            _totalSegmentsCount = sourceList.length;
            // PERFORMANCE: Clear filtered indices cache when total count is set
            _clearFilteredIndicesCache();
          }

          if (mounted) {
            setState(() {
              _sourceParagraphs = sourceList;
              _targetParagraphs = targetList;
              // Update all segment metadata (same for TS and DOCX)
              _segmentPlatforms.clear();
              _segmentPlatforms.addAll(newSegmentPlatforms);
              _failedSegments.clear();
              _failedSegments.addAll(newFailedSegments);
              _failureReasons.clear();
              _failureReasons.addAll(newFailureReasons);
              _markedRetrySegments.clear();
              _markedRetrySegments.addAll(newMarkedRetrySegments);
              _excludedSegments.clear();
              _excludedSegments.addAll(newExcludedSegments);
              // PERFORMANCE: Clear exclusion counts cache when excluded segments change
              _clearExclusionCountsCache();
              if (newExcludedSegments.isNotEmpty) {
                _translationResultLog(
                  '[EXCLUDED_SEGMENTS] Loaded ${newExcludedSegments.length} excluded segments: ${newExcludedSegments.keys.toList()}',
                  level: LogLevel.info,
                );
              } else {
                _translationResultLog(
                  '[EXCLUDED_SEGMENTS] No excluded segments found in loaded data',
                );
              }
              _usedPlatformsForSegment.clear();
              _usedPlatformsForSegment.addAll(newUsedPlatformsForSegment);
              _imageSegments.clear();
              _imageSegments.addAll(newImageSegments);
              if (parsedImageMap.isNotEmpty) {
                _imageDataMap = parsedImageMap;
              }
              _isLoading = false;
            });
          }

          // Compute merged paragraphs for merged preview mode
          _computeMergedParagraphs();

          // Initialize height cache and scroll manager after segments are loaded
          if (_heightCache == null && _totalSegmentsCount > 0) {
            _heightCache = SegmentHeightCache(
              estimatedHeight:
                  118, // Estimated height for segment pairs (source + target)
              // Further reduced from 130 to 118 due to additional padding compression:
              // - Segment padding: 4px → 2px (saves 4px per segment, 8px per pair)
              // - Segment margin: 2px → 1px (saves 1px per segment, 2px per pair)
              // - Separator height: 2px → 1px (saves 1px per pair)
              // Total additional savings: ~11px per segment pair
            );

            // Use segmentPairKeys for scrolling (most reliable for unified height)
            final Map<int, GlobalKey<State<StatefulWidget>>> itemKeys =
                <int, GlobalKey>{};
            for (int i = 0; i < _totalSegmentsCount; i++) {
              if (!segmentPairKeys.containsKey(i)) {
                segmentPairKeys[i] = GlobalKey();
              }
              itemKeys[i] = segmentPairKeys[i]!;
            }

            _scrollManager = PaginatedScrollManager(
              scrollController: _comparisonScrollController,
              paginationController: _segmentsPaginationController!,
              heightCache: _heightCache!,
              itemKeys: itemKeys,
              totalItems: _totalSegmentsCount,
            );
          }

          // Load first page of paginated data after setState
          if (_segmentsPaginationController != null &&
              _totalSegmentsCount > 0) {
            await _segmentsPaginationController!.loadFirstPage();
            if (mounted) setState(() {});
          }

          // No height alignment needed - unified panel handles this naturally

          // Initialize undo/redo history for all segments
          _initializeUndoRedoHistory();

          // Verify we have matching segments
          if (_sourceParagraphs.length == _targetParagraphs.length &&
              _sourceParagraphs.isNotEmpty) {
            // Loaded ${_sourceParagraphs.length} segments from API (logging removed)
            return; // Success!
          } else if (_sourceParagraphs.length != _targetParagraphs.length) {
            // Mismatch - log warning but continue with fallback
            // Segment count mismatch (logging removed)
            // Still try to show what we have
            if (_targetParagraphs.isNotEmpty) {
              return; // At least show translated content
            }
          }
        } else {
          // No segments found in API response, trying fallback (logging removed)
        }
      } catch (e) {
        // API call failed (404 for old tasks, or other errors)
        // Failed to load segments from API, trying fallback (logging removed)
        if (e.toString().contains('404')) {
          // 404 error - segments API not available (logging removed)
          // Check task status to provide better error message
          try {
            final TranslationService svc = TranslationService();
            final Map<String, dynamic> status =
                await svc.getStatus(_apiTaskId());
            final String taskStatus = status['status'] as String? ?? 'unknown';
            final String taskMessage = status['message'] as String? ?? '';
            final String taskError = status['error'] as String? ?? '';
            // Task status checked (logging removed)
            if (taskStatus == 'failed') {
              if (mounted) {
                // Prefer a localized, user-friendly hint for common SSL EOF issues
                final combined = '$taskMessage $taskError';
                final bool isSslEofError = combined.contains('UNEXPECTED_EOF_WHILE_READING') ||
                    combined.contains('EOF occurred in violation of protocol');

                setState(() {
                  if (isSslEofError) {
                    _loadingError =
                        'Format conversion failed: SSL connection error detected. Please check your network and try disabling VPN/proxy, then retry.';
                  } else {
                    _loadingError = taskMessage.isNotEmpty
                        ? taskMessage
                        : (taskError.isNotEmpty
                            ? taskError
                            : 'Translation task failed. Please check backend logs for details.');
                  }
                });
              }
              return; // Don't try fallback if task failed
            } else if (taskStatus == 'processing' || taskStatus == 'pending') {
              // Task is still processing (logging removed)
              // Continue with fallback, but don't show error
            }
          } catch (statusError) {
            // Failed to check task status (logging removed)
          }
        }
      }

      // Fallback: Try to download Markdown file (for backward compatibility with old tasks)
      // Note: TS files should also use segments API, so this fallback is mainly for old tasks
      String? markdownContent;
      if (widget.downloads != null && widget.downloads!.containsKey('md')) {
        try {
          final List<int> bytes =
              await svc.downloadFile(widget.downloads!['md']!);
          markdownContent = utf8.decode(bytes);
        } catch (e) {
          // Continue with other formats
        }
      }

      // If no markdown, try HTML (for backward compatibility)
      if (markdownContent == null &&
          widget.downloads != null &&
          widget.downloads!.containsKey('html')) {
        try {
          final List<int> bytes =
              await svc.downloadFile(widget.downloads!['html']!);
          final String htmlContent = utf8.decode(bytes);
          markdownContent = extractTextFromHtml(htmlContent);
        } catch (e) {
          // Continue with empty content
        }
      }

      if (markdownContent != null && markdownContent.isNotEmpty) {
        // Parse translated content (fallback for old tasks without segments API)
        // This should rarely be used for TS files as they should use segments API
        final Map<String, List<String>> parsed =
            TranslationContentParser.parseTranslationContent(markdownContent);

        if (mounted) {
          setState(() {
            _targetParagraphs = parsed['target'] ?? <String>[];
            _sourceParagraphs =
                <String>[]; // Source not available from file alone (fallback mode)
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _loadingError =
                'Translation content not available. Please wait for translation to complete.';
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loadingError = 'Failed to load translation content: $e';
          _isLoading = false;
        });
      }

      // No height alignment needed - unified panel handles this naturally
    }
  }

  Map<String, Map<String, String>> _parseImageDataMap(raw) {
    if (raw is Map) {
      final parsed = <String, Map<String, String>>{};
      raw.forEach((key, value) {
        if (value is Map) {
          parsed[key.toString()] = value.map(
            (innerKey, innerValue) =>
                MapEntry(innerKey.toString(), innerValue?.toString() ?? ''),
          );
        }
      });
      return parsed;
    }
    return <String, Map<String, String>>{};
  }

  void _ensureItemKeysExist(int count) {
    while (sourceItemKeys.length < count) {
      final int index = sourceItemKeys.length;
      sourceItemKeys[index] = GlobalKey();
    }
    while (targetItemKeys.length < count) {
      final int index = targetItemKeys.length;
      targetItemKeys[index] = GlobalKey();
    }
  }

  /// Handle editing started - highlight and scroll to corresponding source segment
  /// Fix: Wait for height measurement after edit mode switch before scrolling
  void _onEditingStarted(int targetIndex) {
    AppLogger.log(
      'TranslationResultPreview',
      '_onEditingStarted CALLED: targetIndex=$targetIndex, _sourceParagraphs.length=${_sourceParagraphs.length}',
      level: LogLevel.info,
    );

    if (targetIndex < 0 || targetIndex >= _sourceParagraphs.length) {
      AppLogger.log(
        'TranslationResultPreview',
        '_onEditingStarted: Early return - invalid targetIndex=$targetIndex',
        level: LogLevel.warn,
      );
      return;
    }

    // Mark this segment as being edited
    if (mounted) {
      setState(() {
        _editingSegments.add(targetIndex);
      });
    }

    // Highlight the corresponding source segment
    highlightedIndex = targetIndex;
    _highlightedIndexNotifier.value = targetIndex;

    // Check if segment is already visible before scrolling
    // Only scroll if segment is not visible or partially visible
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;

      // Check if segment is already visible using GlobalKey
      final GlobalKey<State<StatefulWidget>>? targetKey =
          targetItemKeys[targetIndex];
      if (targetKey != null && _comparisonScrollController.hasClients) {
        final BuildContext? context = targetKey.currentContext;
        if (context != null) {
          try {
            final renderBox = context.findRenderObject() as RenderBox?;
            if (renderBox != null && renderBox.hasSize) {
              final scrollable = Scrollable.of(context);
              final scrollableRenderBox =
                  scrollable.context.findRenderObject() as RenderBox?;
              if (scrollableRenderBox != null) {
                final itemGlobalTop = renderBox.localToGlobal(Offset.zero);
                final itemGlobalBottom =
                    itemGlobalTop + Offset(0, renderBox.size.height);
                final scrollableGlobalTop =
                    scrollableRenderBox.localToGlobal(Offset.zero);
                final scrollableGlobalBottom = scrollableGlobalTop +
                    Offset(
                      0,
                      _comparisonScrollController.position.viewportDimension,
                    );

                // Check if item is fully visible (with some margin)
                const margin = 20; // Small margin for safety
                final isFullyVisible = itemGlobalTop.dy >=
                        (scrollableGlobalTop.dy - margin) &&
                    itemGlobalBottom.dy <= (scrollableGlobalBottom.dy + margin);

                if (isFullyVisible) {
                  // Segment is already visible, no need to scroll
                  return;
                }
              }
            }
          } catch (e) {
            // If visibility check fails, proceed with scrolling
          }
        }
      }

      // Wait for height measurement after edit mode switch (edit mode may have different height)
      // ItemWithHeightMeasurement measures in addPostFrameCallback, so wait 2 frames
      Future.delayed(const Duration(milliseconds: 150), () {
        if (!mounted) return;

        try {
          // Use PaginatedScrollManager.scrollToIndex for accurate scrolling with height cache
          // This accounts for height changes when switching to edit mode
          // Use smaller alignment (0.05) to keep segment near top but not scroll too much
          if (_scrollManager != null &&
              _comparisonScrollController.hasClients) {
            _scrollManager!.scrollToIndex(
              targetIndex,
              alignment: 0.05, // Smaller alignment to minimize scrolling
              animate: true,
            );
          } else {
            // Fallback to Scrollable.ensureVisible if scroll manager not available
            final GlobalKey<State<StatefulWidget>>? targetKey =
                targetItemKeys[targetIndex];
            if (targetKey != null && _comparisonScrollController.hasClients) {
              final BuildContext? context = targetKey.currentContext;
              if (context != null) {
                Scrollable.ensureVisible(
                  context,
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeInOut,
                  alignment: 0.05, // Smaller alignment to minimize scrolling
                );
              }
            }
          }
        } catch (e) {
          // Controller may have been disposed
        }
      });
    });
  }

  /// Update segment metadata with new target text
  /// This ensures pagination controller uses the updated data
  void _updateSegmentMetadata(int index, {required String targetText}) {
    if (_allSegmentsMetadata.containsKey(index)) {
      _allSegmentsMetadata[index] = <String, dynamic>{
        ..._allSegmentsMetadata[index]!,
        'target_text': targetText,
        'modified_text': targetText,
      };
    } else {
      _allSegmentsMetadata[index] = <String, dynamic>{
        'target_text': targetText,
        'modified_text': targetText,
      };
    }
  }

  /// Handle segment text editing
  Future<void> _handleSegmentEdit(int index, String newText) async {
    try {
      // Record old text before saving
      final String oldText = _targetParagraphs[index];

      final TranslationService svc = TranslationService();
      await svc.updateTranslationSegment(
        _apiTaskId(),
        index,
        targetText: newText,
        modifiedBy: 'user', // TODO: Get actual user ID
      );

      // CRITICAL: Update _allSegmentsMetadata so pagination controller uses updated data
      // Without this, the pagination controller will reload old text from metadata
      _updateSegmentMetadata(index, targetText: newText);

      if (mounted) {
        setState(() {
          _targetParagraphs[index] = newText;
          _modifiedSegments[index] = newText;
          _editingSegments.remove(index);
        });

        // CRITICAL: Force refresh pagination controller to ensure it uses updated metadata
        // This ensures the UI immediately reflects the saved changes
        if (_segmentsPaginationController != null) {
          await _segmentsPaginationController!.refresh();
        }
      }

      // Record revision in undo/redo history
      final TranslationSegmentsUndoRedoNotifier undoRedoNotifier =
          ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()).notifier);
      undoRedoNotifier.pushRevision(index, newText, oldText: oldText);
      _notifyTranslationWorkspaceMutation();
    } catch (e) {
      AppLogger.log(
        'TranslationResultPreview',
        '_handleSegmentEdit: Error saving index=$index: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(context, 'Failed to save: $e');
      }
      rethrow;
    }
  }

  /// Initialize undo/redo history for all loaded segments
  void _initializeUndoRedoHistory() {
    final TranslationSegmentsUndoRedoNotifier undoRedoNotifier =
        ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()).notifier);
    for (var i = 0; i < _targetParagraphs.length; i++) {
      undoRedoNotifier.initializeSegment(i, _targetParagraphs[i]);
    }
  }

  /// Handle global undo (cross-segment, time-ordered)
  Future<void> _handleGlobalUndo() async {
    try {
      final TranslationSegmentsUndoRedoNotifier undoRedoNotifier =
          ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()).notifier);
      final GlobalRevisionOperation? operation = undoRedoNotifier.globalUndo();

      if (operation == null) {
        if (mounted) {
          MessageService.showWarning(context, 'Nothing to undo');
        }
        return;
      }

      // Save the undo result to backend
      final TranslationService svc = TranslationService();
      await svc.updateTranslationSegment(
        _apiTaskId(),
        operation.segmentIndex,
        targetText: operation.oldText,
        modifiedBy: 'user',
      );

      // CRITICAL: Update _allSegmentsMetadata so pagination controller uses updated data
      if (_allSegmentsMetadata.containsKey(operation.segmentIndex)) {
        _allSegmentsMetadata[operation.segmentIndex] = <String, dynamic>{
          ..._allSegmentsMetadata[operation.segmentIndex]!,
          'target_text': operation.oldText,
          'modified_text': operation.oldText,
        };
      } else {
        _allSegmentsMetadata[operation.segmentIndex] = <String, dynamic>{
          'target_text': operation.oldText,
          'modified_text': operation.oldText,
        };
      }

      // Update UI
      if (mounted) {
        setState(() {
          _targetParagraphs[operation.segmentIndex] = operation.oldText;
          _modifiedSegments[operation.segmentIndex] = operation.oldText;
        });
      }

      // CRITICAL: Force refresh the pagination controller to reload current page
      if (_segmentsPaginationController != null && mounted) {
        await _segmentsPaginationController!.refresh();
      }

      // Scroll to the affected segment
      _highlightParagraph(operation.segmentIndex);

      if (mounted) {
        MessageService.showSuccess(
          context,
          'Undo: Segment ${operation.segmentIndex + 1}',
        );
      }
      _notifyTranslationWorkspaceMutation();
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to undo: $e');
      }
    }
  }

  /// Handle global redo (cross-segment, time-ordered)
  Future<void> _handleGlobalRedo() async {
    try {
      final TranslationSegmentsUndoRedoNotifier undoRedoNotifier =
          ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()).notifier);
      final GlobalRevisionOperation? operation = undoRedoNotifier.globalRedo();

      if (operation == null) {
        if (mounted) {
          MessageService.showWarning(context, 'Nothing to redo');
        }
        return;
      }

      // Save the redo result to backend
      final TranslationService svc = TranslationService();
      await svc.updateTranslationSegment(
        _apiTaskId(),
        operation.segmentIndex,
        targetText: operation.newText,
        modifiedBy: 'user',
      );

      // CRITICAL: Update _allSegmentsMetadata so pagination controller uses updated data
      if (_allSegmentsMetadata.containsKey(operation.segmentIndex)) {
        _allSegmentsMetadata[operation.segmentIndex] = <String, dynamic>{
          ..._allSegmentsMetadata[operation.segmentIndex]!,
          'target_text': operation.newText,
          'modified_text': operation.newText,
        };
      } else {
        _allSegmentsMetadata[operation.segmentIndex] = <String, dynamic>{
          'target_text': operation.newText,
          'modified_text': operation.newText,
        };
      }

      // Update UI
      if (mounted) {
        setState(() {
          _targetParagraphs[operation.segmentIndex] = operation.newText;
          _modifiedSegments[operation.segmentIndex] = operation.newText;
        });
      }

      // CRITICAL: Force refresh the pagination controller to reload current page
      if (_segmentsPaginationController != null && mounted) {
        await _segmentsPaginationController!.refresh();
      }

      // Scroll to the affected segment
      _highlightParagraph(operation.segmentIndex);

      if (mounted) {
        MessageService.showSuccess(
          context,
          'Redo: Segment ${operation.segmentIndex + 1}',
        );
      }
      _notifyTranslationWorkspaceMutation();
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to redo: $e');
      }
    }
  }

  /// Handle local undo (per-segment)
  Future<void> _handleUndo(int segmentIndex) async {
    try {
      final TranslationSegmentsUndoRedoNotifier undoRedoNotifier =
          ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()).notifier);
      final String? previousText = undoRedoNotifier.undo(segmentIndex);

      if (previousText == null) {
        if (mounted) {
          MessageService.showWarning(context, 'Nothing to undo');
        }
        return;
      }

      // Save the undo result to backend
      final TranslationService svc = TranslationService();
      await svc.updateTranslationSegment(
        _apiTaskId(),
        segmentIndex,
        targetText: previousText,
        modifiedBy: 'user',
      );

      // CRITICAL: Update _allSegmentsMetadata so pagination controller uses updated data
      if (_allSegmentsMetadata.containsKey(segmentIndex)) {
        _allSegmentsMetadata[segmentIndex] = <String, dynamic>{
          ..._allSegmentsMetadata[segmentIndex]!,
          'target_text': previousText,
          'modified_text': previousText,
        };
      } else {
        _allSegmentsMetadata[segmentIndex] = <String, dynamic>{
          'target_text': previousText,
          'modified_text': previousText,
        };
      }

      // Update UI
      if (mounted) {
        setState(() {
          _targetParagraphs[segmentIndex] = previousText;
          _modifiedSegments[segmentIndex] = previousText;
        });
      }

      // CRITICAL: Force refresh the pagination controller to reload current page
      if (_segmentsPaginationController != null && mounted) {
        await _segmentsPaginationController!.refresh();
      }

      if (mounted) {
        MessageService.showSuccess(
          context,
          'Undo: Segment ${segmentIndex + 1}',
        );
      }
      _notifyTranslationWorkspaceMutation();
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to undo: $e');
      }
    }
  }

  /// Handle local redo (per-segment)
  Future<void> _handleRedo(int segmentIndex) async {
    try {
      final TranslationSegmentsUndoRedoNotifier undoRedoNotifier =
          ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()).notifier);
      final String? nextText = undoRedoNotifier.redo(segmentIndex);

      if (nextText == null) {
        if (mounted) {
          MessageService.showWarning(context, 'Nothing to redo');
        }
        return;
      }

      // Save the redo result to backend
      final TranslationService svc = TranslationService();
      await svc.updateTranslationSegment(
        _apiTaskId(),
        segmentIndex,
        targetText: nextText,
        modifiedBy: 'user',
      );

      // CRITICAL: Update _allSegmentsMetadata so pagination controller uses updated data
      if (_allSegmentsMetadata.containsKey(segmentIndex)) {
        _allSegmentsMetadata[segmentIndex] = <String, dynamic>{
          ..._allSegmentsMetadata[segmentIndex]!,
          'target_text': nextText,
          'modified_text': nextText,
        };
      } else {
        _allSegmentsMetadata[segmentIndex] = <String, dynamic>{
          'target_text': nextText,
          'modified_text': nextText,
        };
      }

      // Update UI
      if (mounted) {
        setState(() {
          _targetParagraphs[segmentIndex] = nextText;
          _modifiedSegments[segmentIndex] = nextText;
        });
      }

      // CRITICAL: Force refresh the pagination controller to reload current page
      if (_segmentsPaginationController != null && mounted) {
        await _segmentsPaginationController!.refresh();
      }

      if (mounted) {
        MessageService.showSuccess(
          context,
          'Redo: Segment ${segmentIndex + 1}',
        );
      }
      _notifyTranslationWorkspaceMutation();
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to redo: $e');
      }
    }
  }

  /// Handle marking a segment for retry
  Future<void> _handleMarkForRetry(int index) async {
    try {
      // Update state immediately (UI already updated by child widget's local state)
      _markedRetrySegments[index] = true;

      // CRITICAL: Update metadata cache to ensure statistics are updated
      if (_allSegmentsMetadata.containsKey(index)) {
        _allSegmentsMetadata[index] = <String, dynamic>{
          ..._allSegmentsMetadata[index]!,
          'needs_retry': true,
        };
      } else {
        // If metadata doesn't exist, create it with retry status
        _allSegmentsMetadata[index] = <String, dynamic>{
          'needs_retry': true,
        };
      }

      final TranslationService svc = TranslationService();
      await svc.markSegmentForRetry(_apiTaskId(), index);

      // Only call setState if widget is still mounted and state needs sync
      // (Child widget already updated its local state, so this is just for consistency)
      if (mounted) {
        setState(() {
          // State already updated above, this just triggers a rebuild for consistency
          // but child widget's local state will prevent visual changes
        });
        MessageService.showWarning(context, 'Segment marked for retry');
      }
    } catch (e) {
      // On error, revert the state change
      _markedRetrySegments.remove(index);
      if (mounted) {
        setState(() {
          // Revert state on error
        });
        MessageService.showError(
          context,
          'Failed to mark segment for retry: $e',
        );
      }
    }
  }

  /// Handle unmarking a segment for retry (clear retry flag)
  Future<void> _handleUnmarkForRetry(int index) async {
    try {
      // Update state immediately (UI already updated by child widget's local state)
      _markedRetrySegments.remove(index);

      // Also update metadata cache to ensure pair.needsRetry is updated
      if (_allSegmentsMetadata.containsKey(index)) {
        _allSegmentsMetadata[index] = <String, dynamic>{
          ..._allSegmentsMetadata[index]!,
          'needs_retry': false,
        };
      }

      final TranslationService svc = TranslationService();
      await svc.unmarkSegmentForRetry(_apiTaskId(), index);

      // Only call setState if widget is still mounted and state needs sync
      // (Child widget already updated its local state, so this is just for consistency)
      if (mounted) {
        setState(() {
          // State already updated above, this just triggers a rebuild for consistency
          // but child widget's local state will prevent visual changes
        });
        MessageService.showInfo(context, 'Retry flag cleared');
      }
    } catch (e) {
      // Check if error is 404 (retry flag doesn't exist on backend)
      // This can happen for failed segments that were manually marked for retry
      // but the backend doesn't have the retry flag set
      final bool is404Error = e.toString().contains('404') ||
          e.toString().contains('status code of 404');

      if (is404Error) {
        // 404 means retry flag doesn't exist on backend, which is fine
        // Frontend state is already updated, so we can just log and continue
        _translationResultLog(
          '_handleUnmarkForRetry: Retry flag not found on backend (404), but frontend state already updated. index=$index',
        );
        // Don't revert state or show error - frontend state is already correct
        if (mounted) {
          setState(() {
            // State already updated, just trigger rebuild
          });
          MessageService.showInfo(context, 'Retry flag cleared');
        }
      } else {
        // For other errors, revert the state change
        _markedRetrySegments[index] = true;
        if (_allSegmentsMetadata.containsKey(index)) {
          _allSegmentsMetadata[index] = <String, dynamic>{
            ..._allSegmentsMetadata[index]!,
            'needs_retry': true,
          };
        }
        if (mounted) {
          setState(() {
            // Revert state on error
          });
          MessageService.showError(context, 'Failed to clear retry flag: $e');
        }
      }
    }
  }

  /// Handle exclude segment: restore target_text to source_text
  /// Also excludes all segments with the same source text as the current segment
  Future<void> _handleExcludeSegment(int index) async {
    try {
      // Get current segment's source text (not target text)
      if (index >= _sourceParagraphs.length) {
        MessageService.showError(context, 'Invalid segment index');
        return;
      }
      final String currentSourceText = _sourceParagraphs[index];

      // Find all segments with the same source text as the current segment
      final List<int> matchingIndices = <int>[];
      for (int i = 0; i < _sourceParagraphs.length; i++) {
        // Compare source text, not target text
        if (_sourceParagraphs[i] == currentSourceText) {
          matchingIndices.add(i);
        }
      }

      // Update state immediately for all matching segments (optimistic update)
      for (final int idx in matchingIndices) {
        _excludedSegments[idx] = true;
        // Clear retry flags since we're excluding
        _markedRetrySegments.remove(idx);
        _failedSegments.remove(idx);
        _failureReasons.remove(idx);
        // Clear platform info for excluded segment
        _segmentPlatforms.remove(idx);
        _usedPlatformsForSegment.remove(idx);
        // Keep metadata consistent: excluded segments should not be marked as failed
        if (_allSegmentsMetadata.containsKey(idx)) {
          _allSegmentsMetadata[idx] = <String, dynamic>{
            ..._allSegmentsMetadata[idx]!,
            'is_failed': false,
            'failure_reason': null,
          };
        }
      }

      // PERFORMANCE: Clear filtered indices cache when exclusion state changes
      _clearFilteredIndicesCache();

      // Batch call API for all matching segments
      final TranslationService svc = TranslationService();
      final List<Future<Map<String, dynamic>>> excludeFutures = matchingIndices
          .map((idx) => svc.excludeSegment(_apiTaskId(), idx))
          .toList();
      final List<Map<String, dynamic>> results =
          await Future.wait(excludeFutures);

      // Update target text and metadata for all segments (from backend response)
      for (int i = 0; i < matchingIndices.length && i < results.length; i++) {
        final int idx = matchingIndices[i];
        final Map<String, dynamic>? segment =
            results[i]['segment'] as Map<String, dynamic>?;
        if (segment != null) {
          // Update target text
          if (idx < _targetParagraphs.length) {
            final String targetText = segment['target_text'] as String? ?? '';
            _targetParagraphs[idx] = targetText;
          }
          // CRITICAL: Update metadata from backend response to ensure consistency
          final String? exclusionReason =
              segment['exclusion_reason'] as String?;
          final bool isExcluded = segment['is_excluded'] as bool? ?? false;
          if (_allSegmentsMetadata.containsKey(idx)) {
            _allSegmentsMetadata[idx] = <String, dynamic>{
              ..._allSegmentsMetadata[idx]!,
              'is_excluded': isExcluded,
              'exclusion_reason': exclusionReason,
            };
          } else {
            _allSegmentsMetadata[idx] = <String, dynamic>{
              'is_excluded': isExcluded,
              'exclusion_reason': exclusionReason,
            };
          }
        }
      }

      // CRITICAL: Refresh pagination to update SegmentPair list with new exclusion_reason
      if (_segmentsPaginationController != null) {
        await _segmentsPaginationController!.refresh();
      }

      // Only call setState if widget is still mounted and state needs sync
      if (mounted) {
        setState(() {
          // State already updated above, this just triggers a rebuild
        });
        // Show single message for all excluded segments
        if (matchingIndices.length == 1) {
          MessageService.showInfo(context, 'Segment excluded from translation');
        } else {
          MessageService.showInfo(
            context,
            '${matchingIndices.length} segments excluded from translation',
          );
        }
      }
    } catch (e) {
      // On error, revert the state changes for all matching segments
      // Get current segment's source text to find matching indices
      if (index < _sourceParagraphs.length) {
        final String currentSourceText = _sourceParagraphs[index];
        for (int i = 0; i < _sourceParagraphs.length; i++) {
          if (_sourceParagraphs[i] == currentSourceText) {
            _excludedSegments.remove(i);
          }
        }
      }
      if (mounted) {
        setState(() {
          // Revert state on error
        });
        MessageService.showError(context, 'Failed to exclude segment: $e');
      }
    }
  }

  /// Handle clear segment: clear translation text
  Future<void> _handleClearSegment(int index) async {
    try {
      // Update state immediately
      final String oldText = _targetParagraphs[index];
      _targetParagraphs[index] = '';

      // CRITICAL: Also update _allSegmentsMetadata so pagination controller uses updated data
      // This ensures itemConverter will use the cleared target_text
      if (_allSegmentsMetadata.containsKey(index)) {
        _allSegmentsMetadata[index] = <String, dynamic>{
          ..._allSegmentsMetadata[index]!,
          'target_text': '',
          'modified_text': '', // Also clear modified_text
          'status': 'cleared', // Mark as cleared to prevent retranslation
          'needs_retry': false, // Clear retry flag
          'is_failed': false, // Clear failed flag
        };
      } else {
        // If metadata doesn't exist, create it with empty target_text
        _allSegmentsMetadata[index] = <String, dynamic>{
          'target_text': '',
          'modified_text': '',
          'status': 'cleared', // Mark as cleared to prevent retranslation
          'needs_retry': false, // Clear retry flag
          'is_failed': false, // Clear failed flag
        };
      }

      final TranslationService svc = TranslationService();
      await svc.clearSegment(_apiTaskId(), index);

      // Record revision in undo/redo history
      final TranslationSegmentsUndoRedoNotifier undoRedoNotifier =
          ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()).notifier);
      undoRedoNotifier.pushRevision(index, '', oldText: oldText);

      // Update modified segments map
      _modifiedSegments[index] = '';

      // Update the specific segment from backend to ensure consistency
      await _updateSegmentsOnly(<int>[index]);

      // CRITICAL: Force refresh the pagination controller to reload current page
      // This ensures that itemConverter is called again with updated _allSegmentsMetadata
      if (_segmentsPaginationController != null && mounted) {
        await _segmentsPaginationController!.refresh();
      }

      // Force rebuild to reflect the change
      if (mounted) {
        setState(() {
          // Trigger rebuild so itemConverter uses updated _allSegmentsMetadata
        });
        MessageService.showInfo(context, 'Segment translation cleared');
      }
    } catch (e) {
      // On error, revert the state change
      if (index < _targetParagraphs.length) {
        // Restore from backend
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> segmentsData =
            await svc.getTranslationSegments(_apiTaskId());
        final List<dynamic>? segments =
            segmentsData['segments'] as List<dynamic>?;
        if (segments != null) {
          for (final segment in segments) {
            final int? segIndex = segment['segment_index'] as int?;
            if (segIndex == index) {
              final String targetText = segment['modified_text'] as String? ??
                  segment['target_text'] as String? ??
                  '';
              if (index < _targetParagraphs.length) {
                _targetParagraphs[index] = targetText;
              }
              break;
            }
          }
        }
      }
      if (mounted) {
        setState(() {
          // Revert state on error
        });
        MessageService.showError(context, 'Failed to clear segment: $e');
      }
    }
  }

  /// Handle unclear segment: restore cleared translation text
  Future<void> _handleUnclearSegment(int index) async {
    try {
      // Try to get the old text from undo/redo history
      String? restoredText;
      final TranslationSegmentsUndoRedoNotifier undoRedoNotifier =
          ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()).notifier);
      final TranslationSegmentsUndoRedoState undoRedoState =
          ref.read(translationSegmentsUndoRedoProvider(_apiTaskId()));

      // Look for the most recent clear operation in globalPast
      // Find the last operation for this segment where newText is empty
      for (int i = undoRedoState.globalPast.length - 1; i >= 0; i--) {
        final GlobalRevisionOperation op = undoRedoState.globalPast[i];
        if (op.segmentIndex == index &&
            op.newText.isEmpty &&
            op.oldText.isNotEmpty) {
          restoredText = op.oldText;
          break;
        }
      }

      // If not found in globalPast, try to get from backend
      // Wrap in try-catch to handle cases where task is released (404 error)
      if (restoredText == null || restoredText.isEmpty) {
        try {
          final TranslationService svc = TranslationService();
          final Map<String, dynamic> segmentsData =
              await svc.getTranslationSegments(_apiTaskId());
          final List<dynamic>? segments =
              segmentsData['segments'] as List<dynamic>?;
          if (segments != null) {
            for (final segment in segments) {
              final int? segIndex = segment['segment_index'] as int?;
              if (segIndex == index) {
                // Try to get from original target_text or modified_text
                restoredText = segment['original_target_text'] as String? ??
                    segment['target_text'] as String? ??
                    '';
                break;
              }
            }
          }
        } catch (e) {
          // If backend API fails (e.g., task released, 404), log but continue
          // We'll use empty string or rely on undo/redo history
          debugPrint(
            '[UNCLEAR] Failed to get segments from backend (task may be released): $e',
          );
        }
      }

      // If still no text found, use empty string (will be empty segment)
      restoredText ??= '';

      // Update state immediately
      if (index < _targetParagraphs.length) {
        _targetParagraphs[index] = restoredText;
      }

      // Update metadata
      if (_allSegmentsMetadata.containsKey(index)) {
        _allSegmentsMetadata[index] = <String, dynamic>{
          ..._allSegmentsMetadata[index]!,
          'target_text': restoredText,
          'modified_text': restoredText,
          'status': restoredText.isNotEmpty
              ? 'translated'
              : null, // Clear status if text is restored
        };
      } else {
        _allSegmentsMetadata[index] = <String, dynamic>{
          'target_text': restoredText,
          'modified_text': restoredText,
          'status': restoredText.isNotEmpty ? 'translated' : null,
        };
      }

      // Update segment via API
      final TranslationSegmentsService segmentsService =
          TranslationSegmentsService(_apiTaskId(), ref);
      await segmentsService.updateSegment(
        index,
        restoredText,
        oldText: '',
        onUpdate: (int idx, String text) {
          if (idx < _targetParagraphs.length) {
            _targetParagraphs[idx] = text;
          }
        },
      );

      // Record revision in undo/redo history
      undoRedoNotifier.pushRevision(index, restoredText, oldText: '');

      // Update modified segments map
      if (restoredText.isNotEmpty) {
        _modifiedSegments[index] = restoredText;
      } else {
        _modifiedSegments.remove(index);
      }

      // Update the specific segment from backend to ensure consistency
      // Wrap in try-catch to handle cases where task is released (404 error)
      try {
        await segmentsService.updateSegmentsOnly(<int>[index]);
      } catch (e) {
        // If updateSegmentsOnly fails (e.g., task released, 404), log but continue
        // The segment has already been updated via updateSegment API, so this is just for metadata sync
        _translationResultLog(
          '[UNCLEAR] Failed to update segments metadata (task may be released): $e',
          level: LogLevel.warn,
        );
      }

      // Force refresh the pagination controller
      if (_segmentsPaginationController != null && mounted) {
        await _segmentsPaginationController!.refresh();
      }

      // Force rebuild to reflect the change
      if (mounted) {
        setState(() {
          // Trigger rebuild so itemConverter uses updated _allSegmentsMetadata
        });
        MessageService.showInfo(context, 'Segment translation restored');
        _notifyTranslationWorkspaceMutation();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          // Revert state on error
        });
        MessageService.showError(context, 'Failed to restore segment: $e');
      }
    }
  }

  /// Handle unexclude segment: clear exclusion flag
  /// Also unexcludes all segments with the same source text as the current segment
  Future<void> _handleUnexcludeSegment(int index) async {
    try {
      // Get current segment's source text (not target text)
      if (index >= _sourceParagraphs.length) {
        MessageService.showError(context, 'Invalid segment index');
        return;
      }
      final String currentSourceText = _sourceParagraphs[index];

      // Find all segments with the same source text as the current segment
      final List<int> matchingIndices = <int>[];
      for (int i = 0; i < _sourceParagraphs.length; i++) {
        // Compare source text, not target text
        if (_sourceParagraphs[i] == currentSourceText) {
          matchingIndices.add(i);
        }
      }

      // Batch call API for all matching segments
      final TranslationService svc = TranslationService();
      final List<Future<Map<String, dynamic>>> unexcludeFutures =
          matchingIndices
              .map((idx) => svc.unexcludeSegment(_apiTaskId(), idx))
              .toList();
      final List<Map<String, dynamic>> results =
          await Future.wait(unexcludeFutures);

      // Update state and metadata for all matching segments
      for (int i = 0; i < matchingIndices.length && i < results.length; i++) {
        final int idx = matchingIndices[i];
        final Map<String, dynamic>? segment =
            results[i]['segment'] as Map<String, dynamic>?;

        if (segment != null) {
          // CRITICAL: Update metadata from backend response to ensure consistency
          final String? exclusionReason =
              segment['exclusion_reason'] as String?;
          final bool isExcluded = segment['is_excluded'] as bool? ?? false;
          if (_allSegmentsMetadata.containsKey(idx)) {
            _allSegmentsMetadata[idx] = <String, dynamic>{
              ..._allSegmentsMetadata[idx]!,
              'is_excluded': isExcluded,
              'exclusion_reason': exclusionReason,
            };
          } else {
            _allSegmentsMetadata[idx] = <String, dynamic>{
              'is_excluded': isExcluded,
              'exclusion_reason': exclusionReason,
            };
          }

          // Update target text if backend returned updated segment data
          if (idx < _targetParagraphs.length) {
            final String targetText = segment['modified_text'] as String? ??
                segment['target_text'] as String? ??
                '';
            if (targetText.isNotEmpty) {
              _targetParagraphs[idx] = targetText;
            }
          }
        } else {
          // Fallback: Update metadata cache if backend didn't return segment
          if (_allSegmentsMetadata.containsKey(idx)) {
            _allSegmentsMetadata[idx] = <String, dynamic>{
              ..._allSegmentsMetadata[idx]!,
              'is_excluded': false,
              'exclusion_reason': null,
            };
          }
        }
      }

      // PERFORMANCE: Clear filtered indices cache when exclusion state changes
      _clearFilteredIndicesCache();

      // CRITICAL: Refresh pagination to update SegmentPair list with new exclusion_reason
      if (_segmentsPaginationController != null) {
        await _segmentsPaginationController!.refresh();
      }

      if (mounted) {
        setState(() {
          // Remove excluded status for all matching segments
          for (final int idx in matchingIndices) {
            _excludedSegments.remove(idx);
          }
        });
        // Show single message for all unexcluded segments
        if (matchingIndices.length == 1) {
          MessageService.showInfo(
            context,
            'Segment unexcluded from translation',
          );
        } else {
          MessageService.showInfo(
            context,
            '${matchingIndices.length} segments unexcluded from translation',
          );
        }
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to unexclude segment: $e');
      }
    }
  }

  /// Handle exclusion reason update from Change Exclusion Reason dialog
  /// This is called when user changes exclusion reason via the dialog
  /// Note: The actual segment data is already updated in translation_segment_item.dart
  /// from the updateExclusionReason API response. This method just refreshes the UI.
  Future<void> _handleExclusionUpdated(int index) async {
    // Refresh pagination to reflect changes
    // The metadata will be updated from the API response in translation_segment_item.dart
    if (_segmentsPaginationController != null) {
      await _segmentsPaginationController!.refresh();
    }
  }

  /// Cancel translation task
  Future<void> _cancelTranslation(translationNotifier) async {
    if (translationNotifier == null) return;

    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text('Cancel Translation'),
        content: const Text('Are you sure you want to cancel the translation?'),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('No'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Yes'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      // Get real taskId from state if _apiTaskId() is 'pending'
      String? taskIdToCancel = _apiTaskId();
      if (taskIdToCancel == 'pending' && widget.flowId != null) {
        final TranslationStateFamily translationState =
            ref.read(translationStateProviderFamily(widget.flowId!));
        taskIdToCancel = translationState.taskId;
      }

      // If we still don't have a valid taskId, just update state
      if (taskIdToCancel == null ||
          taskIdToCancel.isEmpty ||
          taskIdToCancel == 'pending') {
        // No task to cancel yet, just update state
        translationNotifier.setTranslating(false);
        translationNotifier.setStatusText('cancelled');
        translationNotifier.setCurrentOperation(TranslationOperation.none);
        if (mounted) {
          MessageService.showInfo(context, 'Translation cancelled');
        }
        return;
      }

      final TranslationService svc = TranslationService();
      await svc.cancelTask(taskIdToCancel);

      if (!mounted) return;

      // Update translation state
      translationNotifier.setTranslating(false);
      translationNotifier.setStatusText('cancelled');
      translationNotifier.setCurrentOperation(TranslationOperation.none);

      if (mounted) {
        MessageService.showInfo(context, 'Translation cancelled');
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to cancel: $e');
      }
    }
  }

  /// Handle retrying translation of a segment with platform rotation
  Future<void> _handleRetrySegment(int index) async {
    if (_retranslatingSegments.contains(index)) {
      return; // Already retranslating
    }

    try {
      // Update state immediately (UI already updated by child widget's local state)
      _retranslatingSegments.add(index);

      // Get available platforms in order
      final AIPlatformSettings aiPlatformSettings =
          ref.read(aiPlatformSettingsProvider);
      final List<AIPlatformInfo> availablePlatforms =
          aiPlatformSettings.getAvailablePlatformsInOrder();

      if (availablePlatforms.isEmpty) {
        throw Exception('No available AI platforms');
      }

      // Get used platforms for this segment
      final List<String> usedPlatforms =
          _usedPlatformsForSegment[index] ?? <String>[];
      final String? currentPlatform = _segmentPlatforms[index];

      // Add current platform to used list if not already there
      if (currentPlatform != null && !usedPlatforms.contains(currentPlatform)) {
        usedPlatforms.add(currentPlatform);
      }

      // Select next available platform (rotation algorithm)
      String? selectedPlatform;
      for (final AIPlatformInfo platform in availablePlatforms) {
        if (!usedPlatforms.contains(platform.key)) {
          selectedPlatform = platform.key;
          break;
        }
      }

      // If all platforms have been used, start from the beginning (excluding the first one)
      if (selectedPlatform == null && availablePlatforms.length > 1) {
        // Skip the first platform (which was likely the original one)
        selectedPlatform = availablePlatforms[1].key;
      } else {
        selectedPlatform ??= availablePlatforms[0].key;
      }

      // Update used platforms list
      final List<String> updatedUsedPlatforms =
          List<String>.from(usedPlatforms);
      if (!updatedUsedPlatforms.contains(selectedPlatform)) {
        updatedUsedPlatforms.add(selectedPlatform);
      }

      // Call retranslation API
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> response = await svc.retranslateSegment(
        _apiTaskId(),
        index,
        platformKey: selectedPlatform,
      );

      // Check if retranslation succeeded
      final bool success = response['success'] as bool? ?? false;
      final Map<String, dynamic>? segment =
          response['segment'] as Map<String, dynamic>?;
      final bool isFailed = segment?['is_failed'] as bool? ?? false;
      final String? failureReason = segment?['failure_reason'] as String?;

      // Update state - only clear failure flags if retranslation succeeded
      _retranslatingSegments.remove(index);
      _usedPlatformsForSegment[index] = updatedUsedPlatforms;
      _segmentPlatforms[index] = selectedPlatform;

      // Only clear failure flags if retranslation succeeded
      if (success && !isFailed) {
        _failedSegments.remove(index);
        _failureReasons.remove(index);
        _markedRetrySegments.remove(index);
      } else {
        // Retranslation failed - update failure state from API response
        if (isFailed) {
          _failedSegments[index] = true;
          if (failureReason != null) {
            _failureReasons[index] = failureReason;
          }
        }
      }

      // Only call setState if widget is still mounted
      // (Child widget's local state already updated, so this is just for consistency)
      if (mounted) {
        setState(() {
          // State already updated above, this just triggers a rebuild for consistency
          // but child widget's local state will prevent visual changes
        });
      }

      // Trigger partial update for immediate UI refresh (more efficient than full reload)
      // This will fetch latest segment data from API and update UI
      ref.read(translationSegmentsUpdateProvider.notifier).state = <int>[index];

      // Also trigger full reload to ensure all metadata is updated
      // This ensures UI is refreshed even if partial update fails
      await _loadTranslationContent();

      if (mounted) {
        if (success && !isFailed) {
          MessageService.showSuccess(
            context,
            'Segment retranslated using $selectedPlatform',
          );
        } else {
          final String reason = failureReason ?? 'Unknown error';
          MessageService.showError(context, 'Retranslation failed: $reason');
        }
      }
    } catch (e) {
      // On error, revert the state change
      _retranslatingSegments.remove(index);
      if (mounted) {
        setState(() {
          // Revert state on error
        });
        MessageService.showError(context, 'Failed to retranslate segment: $e');
      }
    }
  }

  /// Navigate to the next or previous failed segment
  void _navigateToFailedSegment({required int direction}) {
    // Get all failed segment indices, sorted
    final List<int> failedIndices = _failedSegments.keys
        .where((int idx) => _failedSegments[idx] ?? false)
        .toList()
      ..sort();

    if (failedIndices.isEmpty) {
      if (mounted) {
        MessageService.showInfo(context, 'No retry segments found');
      }
      return;
    }

    // Find the target index based on current highlighted index
    int targetIndex;

    if (highlightedIndex == null) {
      // No current selection, go to first or last
      targetIndex = direction > 0 ? failedIndices.first : failedIndices.last;
    } else {
      // Find next/previous failed segment relative to current
      if (direction > 0) {
        // Next: find first failed segment after current
        final List<int> nextFailed =
            failedIndices.where((int idx) => idx > highlightedIndex!).toList();
        if (nextFailed.isNotEmpty) {
          targetIndex = nextFailed.first;
        } else {
          // Wrap around to first
          targetIndex = failedIndices.first;
        }
      } else {
        // Previous: find last failed segment before current
        final List<int> previousFailed =
            failedIndices.where((int idx) => idx < highlightedIndex!).toList();
        if (previousFailed.isNotEmpty) {
          targetIndex = previousFailed.last;
        } else {
          // Wrap around to last
          targetIndex = failedIndices.last;
        }
      }
    }

    // Highlight and scroll to the target segment using scroll manager
    _highlightParagraph(targetIndex);

    // Removed message notification - user can see the highlighted segment directly
  }

  /// Highlight a paragraph and scroll to it
  /// With unified panel, both source and target are in the same row, so we only need one scroll
  void _highlightParagraph(int index) {
    // Ensure index is valid
    if (index < 0 ||
        index >= _sourceParagraphs.length ||
        index >= _targetParagraphs.length) {
      return;
    }

    // Always update the visual highlight immediately — even if a scroll is in progress.
    // This ensures the user sees instant feedback when clicking a segment.
    highlightedIndex = index;
    _highlightedIndexNotifier.value = index;

    // Prevent recursive scrolling (guard is AFTER the visual update so clicks always show feedback)
    if (_isScrolling) return;

    // Wait for any pending height measurements to complete before scrolling
    // This is especially important after exiting edit mode, as height may have changed
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;

      // Force height measurement for the target index and nearby indices
      // This ensures height cache is up-to-date before scrolling
      if (_scrollManager != null && _heightCache != null) {
        // Measure the target index and a few nearby indices to ensure accurate scrolling
        final startIndex = (index - 2).clamp(0, _totalSegmentsCount - 1);
        final endIndex = (index + 2).clamp(0, _totalSegmentsCount - 1);
        _scrollManager!.measureRange(startIndex, endIndex);
      }

      // Wait for height cache to be updated (e.g., after edit mode exit)
      // This ensures scroll position calculation uses the correct height
      // Use longer delay and multiple frames to ensure height measurement completes
      Future.delayed(const Duration(milliseconds: 200), () {
        if (!mounted) return;

        // Wait for another frame to ensure height cache is fully updated
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;

          // Ensure keys exist for the target index
          _ensureItemKeysExist(index + 1);

          // Use scroll manager for precise scrolling (supports cross-page navigation)
          _isScrolling = true;
          _scrollManager
              ?.scrollToIndex(
            index,
            animate: true,
          )
              .whenComplete(() {
            // Use whenComplete instead of then to ensure _isScrolling is always reset,
            // even if scrollToIndex throws an exception (which would otherwise
            // permanently block future segment clicks).
            if (mounted) {
              _isScrolling = false;
            }
          });
        });
      });
    });
  }

  void _toggleFullscreen() {
    if (_isFullscreen) {
      _exitFullscreen();
    } else {
      _enterFullscreen();
    }
  }

  void _enterFullscreen() {
    if (_isFullscreen || !mounted) return;
    final OverlayState overlay = Overlay.of(context, rootOverlay: true);
    _fullscreenOverlayEntry = OverlayEntry(
      builder: (BuildContext overlayContext) {
        // Use RepaintBoundary to isolate fullscreen content rendering
        return RepaintBoundary(
          child: Material(
            color: Colors.black.withOpacity(0.78),
            child: SafeArea(
              child: Theme(
                data: Theme.of(context),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.surface,
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: const <BoxShadow>[
                        BoxShadow(
                          blurRadius: 20,
                          color: Colors.black26,
                        ),
                      ],
                    ),
                    child: _buildInteractiveShell(isFullscreenView: true),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
    overlay.insert(_fullscreenOverlayEntry!);
    if (mounted) {
      setState(() {
        _isFullscreen = true;
      });
    }
  }

  void _exitFullscreen() {
    if (!_isFullscreen) return;
    _fullscreenOverlayEntry?.remove();
    _fullscreenOverlayEntry = null;
    if (mounted) {
      setState(() {
        _isFullscreen = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch refresh trigger and reload content when it changes
    // This allows external components (like batch retranslation) to trigger refresh
    final int refreshTrigger = ref.watch(translationRefreshProvider);
    final List<int>? segmentsUpdateTrigger =
        ref.watch(translationSegmentsUpdateProvider);

    // Handle full refresh trigger
    if (_lastRefreshTrigger != null && _lastRefreshTrigger != refreshTrigger) {
      // Refresh trigger changed, reload content to get updated translations
      // Use WidgetsBinding to ensure this happens after build
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _loadTranslationContent(forceRefreshSegments: true);
        }
      });
    }
    _lastRefreshTrigger = refreshTrigger;

    // Handle partial update trigger (only update specific segments)
    if (segmentsUpdateTrigger != null && segmentsUpdateTrigger.isNotEmpty) {
      // Segments update trigger changed, update only the specified segments
      // Use WidgetsBinding to ensure this happens after build
      final List<int> segmentsToUpdate = List<int>.from(segmentsUpdateTrigger);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _updateSegmentsOnly(segmentsToUpdate);
          // Clear the trigger after processing
          ref.read(translationSegmentsUpdateProvider.notifier).state = null;
        }
      });
    }

    if (_isFullscreen) {
      return const SizedBox.shrink();
    }
    return _buildInteractiveShell();
  }

  Widget _buildInteractiveShell({bool isFullscreenView = false}) {
    final Map<ShortcutActivator, Intent> shortcutsMap =
        <ShortcutActivator, Intent>{
      const SingleActivator(LogicalKeyboardKey.keyZ, control: true):
          const _GlobalUndoIntent(),
      const SingleActivator(LogicalKeyboardKey.keyZ, meta: true):
          const _GlobalUndoIntent(),
      const SingleActivator(LogicalKeyboardKey.keyY, control: true):
          const _GlobalRedoIntent(),
      const SingleActivator(
        LogicalKeyboardKey.keyZ,
        control: true,
        shift: true,
      ): const _GlobalRedoIntent(),
      const SingleActivator(LogicalKeyboardKey.keyZ, meta: true, shift: true):
          const _GlobalRedoIntent(),
    };
    if (isFullscreenView) {
      shortcutsMap[const SingleActivator(LogicalKeyboardKey.escape)] =
          const _ExitFullscreenIntent();
    }

    final Map<Type, Action<Intent>> actionMap = <Type, Action<Intent>>{
      _GlobalUndoIntent: CallbackAction<_GlobalUndoIntent>(
        onInvoke: (_) {
          _handleGlobalUndo();
          return null;
        },
      ),
      _GlobalRedoIntent: CallbackAction<_GlobalRedoIntent>(
        onInvoke: (_) {
          _handleGlobalRedo();
          return null;
        },
      ),
    };
    if (isFullscreenView) {
      actionMap[_ExitFullscreenIntent] = CallbackAction<_ExitFullscreenIntent>(
        onInvoke: (_) {
          _exitFullscreen();
          return null;
        },
      );
    }

    return Shortcuts(
      shortcuts: shortcutsMap,
      child: Actions(
        actions: actionMap,
        child: Focus(
          autofocus: isFullscreenView ? true : !_isFullscreen,
          child: _buildContent(isFullscreenView: isFullscreenView),
        ),
      ),
    );
  }

  Widget _buildContent({bool isFullscreenView = false}) {
    // Get translation state if flowId is available
    final dynamic translationState = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!))
        : null;
    final dynamic translationNotifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : null;

    // Prefer state.downloads so we reflect on-demand links after refresh; fallback to widget.downloads.
    final Map<String, String>? stateDownloads = translationState?.downloads;
    final bool stateDownloadsNonEmpty =
        stateDownloads != null && stateDownloads.isNotEmpty;
    final Map<String, String>? effectiveDownloads =
        stateDownloadsNonEmpty ? stateDownloads : widget.downloads;

    // When completed/failed with empty downloads (e.g. restored flow), fetch status once to get on-demand links.
    if (_apiTaskId() != 'pending' &&
        widget.flowId != null &&
        translationNotifier != null &&
        (effectiveDownloads == null || effectiveDownloads.isEmpty) &&
        _lastTaskIdForOnDemandDownloadsFetch != _apiTaskId()) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || _lastTaskIdForOnDemandDownloadsFetch == _apiTaskId()) {
          return;
        }
        _lastTaskIdForOnDemandDownloadsFetch = _apiTaskId();
        TranslationService()
            .getStatus(_apiTaskId())
            .then((Map<String, dynamic> status) {
          final dynamic dv = status['downloads'];
          if (dv != null && dv is Map && dv.isNotEmpty && mounted) {
            final Map<String, String> map =
                dv.map((k, v) => MapEntry(k.toString(), v.toString()));
            translationNotifier.setDownloads(map);
          }
        }).catchError((Object e) {
          if (mounted) _lastTaskIdForOnDemandDownloadsFetch = null;
        });
      });
    }

    // Use cached token usage from status API, fallback to translationState
    final tokenUsage = _tokenUsage ?? translationState?.tokenUsage;

    return Stack(
      children: <Widget>[
        Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            // Toolbar with progress and status
            ValueListenableBuilder<Set<String>>(
              valueListenable: _selectedExclusionFiltersNotifier,
              builder: (context, selectedFilters, _) =>
                  TranslationResultToolbar(
                taskId: _apiTaskId(),
                flowId: widget.flowId,
                translationState: translationState,
                tokenUsage: tokenUsage,
                failedSegmentsCount: _failedSegments.length,
                loadingHtmlPreview: _loadingHtmlPreview,
                isFullscreen: _isFullscreen,
                isFullscreenView: isFullscreenView,
                fileName: widget.fileName,
                downloads: effectiveDownloads,
                segmentsPaginationController: _segmentsPaginationController,
                onCancelTranslation: () =>
                    _cancelTranslation(translationNotifier),
                onGlobalUndo: _handleGlobalUndo,
                onGlobalRedo: _handleGlobalRedo,
                onNavigateToFailedSegment: (direction) =>
                    _navigateToFailedSegment(direction: direction),
                onViewPreview: _viewTranslationPreview,
                onShowSettings: _showPreviewSettingsDialog,
                onShowDownload: _showDownloadDialog,
                onViewPdfPreview: _viewPdfPreview,
                onToggleFullscreen: _toggleFullscreen,
                excludedCount: _calculateExcludedCount(),
                isExclusionPanelExpanded: _isExclusionPanelExpanded,
                onToggleExclusionPanel: () {
                  setState(() {
                    _isExclusionPanelExpanded = !_isExclusionPanelExpanded;
                  });
                },
                // Only show formula check button for PDF source files (PDF workflow)
                onCheckPdfFormulas: (widget.fileName != null &&
                        widget.fileName!.toLowerCase().endsWith('.pdf'))
                    ? () => _checkPdfFormulas(context)
                    : null,
                onRepairDocxMath: (widget.workflowType == 'markdown_based')
                    ? () => _repairDocxMathFragments(context)
                    : null,
                // Filter buttons state (for toolbar filter buttons)
                selectedFilters: selectedFilters,
                onFiltersChanged: (Set<String> filters) async {
                  // PERFORMANCE: Prevent duplicate refresh calls
                  if (_isRefreshingForFilter) {
                    return;
                  }

                  final start = DateTime.now();

                  _setSelectedExclusionFilters(filters);
                  _clearFilteredIndicesCache();

                  _isRefreshingForFilter = true;
                  try {
                    // Load from first page so filter change shows correct dataset (All vs Excluded vs Included).
                    await _segmentsPaginationController?.loadFirstPage();
                    if (mounted) setState(() {});
                  } catch (e) {
                    if (kDebugMode) {
                      final end = DateTime.now();
                      _translationResultLog(
                        '[FILTER_PERF] Refresh ERROR: filters=$filters, error=$e, duration=${end.difference(start).inMilliseconds}ms',
                        level: LogLevel.error,
                      );
                    }
                  } finally {
                    if (mounted) {
                      _isRefreshingForFilter = false;
                    }
                  }
                },
                totalSegments: _totalSegmentsCount,
                failedCount: _calculateFailedCount(),
                // Search functionality
                isSearchBoxVisible: _isSearchBoxVisible,
                searchQuery: _searchQuery,
                searchMatchCount: _searchMatchIndices.length,
                currentSearchMatchIndex: _currentSearchMatchIndex,
                onToggleSearch: () {
                  setState(() {
                    _isSearchBoxVisible = !_isSearchBoxVisible;
                    if (!_isSearchBoxVisible) {
                      _searchQuery = '';
                      _searchMatchIndices.clear();
                      _currentSearchMatchIndex = 0;
                    }
                  });
                },
                onSearch: _handleSearch,
                onNextSearchMatch: _searchMatchIndices.isNotEmpty
                    ? () {
                        setState(() {
                          _currentSearchMatchIndex =
                              (_currentSearchMatchIndex + 1) %
                                  _searchMatchIndices.length;
                          _scrollToSearchMatch();
                        });
                      }
                    : null,
                onPreviousSearchMatch: _searchMatchIndices.isNotEmpty
                    ? () {
                        setState(() {
                          _currentSearchMatchIndex = (_currentSearchMatchIndex -
                                  1 +
                                  _searchMatchIndices.length) %
                              _searchMatchIndices.length;
                          _scrollToSearchMatch();
                        });
                      }
                    : null,
                // Merged paragraph view toggle
                isMergedView: _isMergedView,
                onToggleMergedView: () {
                  setState(() {
                    _isMergedView = !_isMergedView;
                  });
                },
              ),
            ),
            // Exclusion panel (if expanded)
            // CRITICAL: Recalculate statistics on every build to ensure real-time updates
            if (_isExclusionPanelExpanded)
              ValueListenableBuilder<Set<String>>(
                valueListenable: _selectedExclusionFiltersNotifier,
                builder: (context, selectedFilters, _) => ExclusionPanelWidget(
                  exclusionCounts: _calculateExclusionCounts(),
                  totalSegments: _totalSegmentsCount,
                  excludedCount: _calculateExcludedCount(),
                  failedCount: _calculateFailedCount(),
                  selectedFilters: selectedFilters,
                  onFiltersChanged: (Set<String> filters) async {
                    if (_isRefreshingForFilter) return;
                    _setSelectedExclusionFilters(filters);
                    _clearFilteredIndicesCache();
                    _isRefreshingForFilter = true;
                    try {
                      await _segmentsPaginationController?.loadFirstPage();
                      if (mounted) setState(() {});
                    } finally {
                      if (mounted) {
                        _isRefreshingForFilter = false;
                      }
                    }
                  },
                  filterMode: _filterMode,
                  onFilterModeChanged: (String mode) {
                    setState(() {
                      _filterMode = mode;
                    });
                    _segmentsPaginationController?.refresh();
                  },
                  // Callback when panel is collapsed from inside (Translate phase)
                  onPanelCollapsed: () {
                    setState(() {
                      _isExclusionPanelExpanded = false;
                    });
                  },
                ),
              ),
            // Comparison view - unified panel with single scroll controller
            Expanded(
              child: _buildComparisonPanel(),
            ),
          ],
        ),
        // Floating search box (similar to Cursor Terminal search)
        if (_isSearchBoxVisible)
          Positioned(
            top: 48, // Position below toolbar (36px) + some spacing
            right: 12,
            child: SegmentSearchBox(
              initialQuery: _searchQuery,
              matchCount: _searchMatchIndices.length,
              currentMatchIndex: _currentSearchMatchIndex,
              onSearch: _handleSearch,
              onClose: () {
                setState(() {
                  _isSearchBoxVisible = false;
                  _searchQuery = '';
                  _searchMatchIndices.clear();
                  _currentSearchMatchIndex = 0;
                  // Clear highlight when search box is closed
                  highlightedIndex = null;
                  _highlightedIndexNotifier.value = null;
                });
              },
              onNextMatch: _searchMatchIndices.isNotEmpty
                  ? () {
                      setState(() {
                        _currentSearchMatchIndex =
                            (_currentSearchMatchIndex + 1) %
                                _searchMatchIndices.length;
                        // Clear previous highlight before scrolling to new match
                        highlightedIndex = null;
                        _highlightedIndexNotifier.value = null;
                        _scrollToSearchMatch();
                      });
                    }
                  : null,
              onPreviousMatch: _searchMatchIndices.isNotEmpty
                  ? () {
                      setState(() {
                        _currentSearchMatchIndex = (_currentSearchMatchIndex -
                                1 +
                                _searchMatchIndices.length) %
                            _searchMatchIndices.length;
                        // Clear previous highlight before scrolling to new match
                        highlightedIndex = null;
                        _highlightedIndexNotifier.value = null;
                        _scrollToSearchMatch();
                      });
                    }
                  : null,
            ),
          ),
      ],
    );
  }

  /// Handle search query changes
  void _handleSearch(String query) {
    setState(() {
      _searchQuery = query;
      if (query.isEmpty) {
        _searchMatchIndices.clear();
        _currentSearchMatchIndex = 0;
        // Clear highlight when search is cleared
        highlightedIndex = null;
        _highlightedIndexNotifier.value = null;
      } else {
        // Search in both source and target paragraphs
        _searchMatchIndices.clear();
        final queryLower = query.toLowerCase();
        for (int i = 0; i < _sourceParagraphs.length; i++) {
          if (_sourceParagraphs[i].toLowerCase().contains(queryLower) ||
              (i < _targetParagraphs.length &&
                  _targetParagraphs[i].toLowerCase().contains(queryLower))) {
            _searchMatchIndices.add(i);
          }
        }
        if (_searchMatchIndices.isNotEmpty) {
          _currentSearchMatchIndex = 0;
          // Clear previous highlight before scrolling to new match
          highlightedIndex = null;
          _highlightedIndexNotifier.value = null;
          _scrollToSearchMatch();
        } else {
          _currentSearchMatchIndex = 0;
          // Clear highlight when no matches found
          highlightedIndex = null;
          _highlightedIndexNotifier.value = null;
        }
      }
    });
  }

  /// Scroll to current search match
  void _scrollToSearchMatch() {
    if (_searchMatchIndices.isEmpty) return;
    final targetIndex = _searchMatchIndices[_currentSearchMatchIndex];

    // Set highlightedIndex to show the segment as selected
    setState(() {
      highlightedIndex = targetIndex;
      _highlightedIndexNotifier.value = targetIndex;
    });

    // Try to scroll to the segment
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;

      // Check if the segment is in the current page
      if (_segmentsPaginationController != null) {
        final currentPageItems = _segmentsPaginationController!.items;
        final currentPageStart = _segmentsPaginationController!.startIndex;

        if (targetIndex >= currentPageStart &&
            targetIndex < currentPageStart + currentPageItems.length) {
          // Segment is in current page, scroll to it
          final localIndex = targetIndex - currentPageStart;
          if (_scrollManager != null) {
            _scrollManager!.scrollToIndex(localIndex);
          }
        } else {
          // Segment is not in current page, load the page containing it
          final pageSize = _segmentsPaginationController!.pageSize;
          final targetPage = (targetIndex / pageSize).floor();
          _segmentsPaginationController!.jumpToPage(targetPage).then((_) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (!mounted) return;
              final localIndex = targetIndex % pageSize;
              // Ensure highlight is set after page loads
              setState(() {
                highlightedIndex = targetIndex;
                _highlightedIndexNotifier.value = targetIndex;
              });
              if (_scrollManager != null) {
                _scrollManager!.scrollToIndex(localIndex);
              }
            });
          });
        }
      }
    });
  }

  /// Calculate excluded segments count
  int _calculateExcludedCount() {
    // PERFORMANCE: Use cached Map instead of iterating metadata
    // _excludedSegments Map is already maintained and synchronized with metadata
    return _excludedSegments.length;
  }

  /// Calculate failed segments count
  int _calculateFailedCount() {
    // PERFORMANCE: Use cached Map instead of iterating metadata
    // _failedSegments Map is already maintained and synchronized with metadata
    return _failedSegments.length;
  }

  /// Calculate exclusion counts by type
  Map<String, int> _calculateExclusionCounts() {
    // PERFORMANCE: Check cache validity
    final bool cacheValid = _cachedExclusionCounts != null &&
        _cachedExclusionCountsTotalSegments != null &&
        _cachedExclusionCountsMetadataSize != null &&
        _cachedExclusionCountsTotalSegments == _totalSegmentsCount &&
        _cachedExclusionCountsMetadataSize == _allSegmentsMetadata.length;

    if (cacheValid) {
      return _cachedExclusionCounts!;
    }

    // Cache miss or invalid - recalculate.
    //
    // CRITICAL: Translate phase filters should be usable even for NOT-excluded
    // categories (e.g. table, structural, language_match). Therefore, counts are
    // built from ALL segments metadata (detected type), not only excluded ones.
    final Map<String, int> counts = buildSegmentTypeCounts(
      allSegmentsMetadata: _allSegmentsMetadata,
      totalSegmentsCount: _totalSegmentsCount,
    );

    // Debug logging to understand how Segment Type Filters are computed.
    if (_allSegmentsMetadata.isNotEmpty) {
      final String baseCountsSummary = counts.entries
          .where((MapEntry<String, int> e) => e.value > 0)
          .map((MapEntry<String, int> e) => '${e.key}(${e.value})')
          .join(', ');
      _translationResultLog(
        '[EXCLUSION_FILTERS] Base counts before global merge: $baseCountsSummary',
      );

      if (_globalDetectedReasonCounts != null &&
          _globalDetectedReasonCounts!.isNotEmpty) {
        final String globalCountsSummary = _globalDetectedReasonCounts!.entries
            .where((MapEntry<String, int> e) => e.value > 0)
            .map((MapEntry<String, int> e) => '${e.key}(${e.value})')
            .join(', ');
        _translationResultLog(
          '[EXCLUSION_FILTERS] Global detected reason counts from metadata: $globalCountsSummary',
        );
      } else {
        _translationResultLog(
          '[EXCLUSION_FILTERS] Global detected reason counts from metadata: <none>',
        );
      }
    }

    // If backend provided global detected exclusion reason counts (from Extract
    // phase), use them only to ensure that all detected categories are known,
    // but do NOT increase counts beyond what actually exists in Translate
    // segments. This guarantees that the number shown on each filter matches
    // the number of segments visible when the filter is applied.
    if (_globalDetectedReasonCounts != null &&
        _globalDetectedReasonCounts!.isNotEmpty) {
      _globalDetectedReasonCounts!.forEach((String reason, int globalCount) {
        // Ensure the reason key exists in the map so that downstream code knows
        // about all detected categories, but keep the count equal to the actual
        // number of matching segments in _allSegmentsMetadata.
        counts.putIfAbsent(reason, () => 0);
      });
    }

    final String finalCountsSummary = counts.entries
        .where((MapEntry<String, int> e) => e.value > 0)
        .map((MapEntry<String, int> e) => '${e.key}(${e.value})')
        .join(', ');
    _translationResultLog(
      '[EXCLUSION_FILTERS] Final merged counts used for filters: $finalCountsSummary',
    );

    // Update cache
    _cachedExclusionCounts = counts;
    _cachedExclusionCountsTotalSegments = _totalSegmentsCount;
    _cachedExclusionCountsMetadataSize = _allSegmentsMetadata.length;

    return counts;
  }

  /// Compute clean-mode paragraphs — each segment is its own paragraph,
  /// same structure as labeled mode, just without segment tags/actions.
  /// All segments shown (excluded included) for a complete reading experience.
  void _computeMergedParagraphs() {
    _mergedSourceParagraphs = <String>[];
    _mergedTargetParagraphs = <String>[];

    if (_sourceParagraphs.isEmpty && _targetParagraphs.isEmpty) return;

    for (int i = 0; i < _sourceParagraphs.length; i++) {
      _mergedSourceParagraphs.add(_sourceParagraphs[i]);
      _mergedTargetParagraphs.add(_targetParagraphs[i]);
    }
  }

  /// Build unified comparison panel with source and target side by side
  /// This replaces the previous separate _buildSourcePanel and _buildTargetPanel
  Widget _buildComparisonPanel() {
    // Get translation state if flowId is available
    final dynamic translationState = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!))
        : null;
    // Use cached token usage from status API, fallback to translationState
    final tokenUsage = _tokenUsage ?? translationState?.tokenUsage;

    // Resolve current workflow type to decide if Clear/Unclear should be enabled.
    final String resolvedWorkflowType = widget.workflowType ??
        (widget.flowId != null
            ? ref
                .read(translationQuickSettingsProviderFamily(widget.flowId!))
                .workflowType
            : ref.read(translationQuickSettingsProvider).workflowType);
    final bool isDocxWorkflow = resolvedWorkflowType == 'docx';

    // Merged paragraph preview mode (no segment labels, merged deep-split paragraphs)
    if (_isMergedView) {
      return TranslationMergedPreviewPanel(
        sourceParagraphs: _mergedSourceParagraphs,
        targetParagraphs: _mergedTargetParagraphs,
        scrollController: _comparisonScrollController,
        previewFontSize:
            ref.watch(globalSettingsProvider).previewFontSize,
      );
    }

    return TranslationComparisonPanel(
      taskId: _apiTaskId(),
      isLoading: _isLoading,
      loadingError: _loadingError,
      isConvertOnly: _isConvertOnly,
      sourceParagraphs: _sourceParagraphs,
      targetParagraphs: _targetParagraphs,
      highlightedIndexNotifier: _highlightedIndexNotifier,
      scrollController: _comparisonScrollController,
      segmentsPaginationController: _segmentsPaginationController,
      totalSegmentsCount: _totalSegmentsCount,
      segmentPairKeys: segmentPairKeys,
      sourceItemKeys: sourceItemKeys,
      targetItemKeys: targetItemKeys,
      modifiedSegments: _modifiedSegments,
      imageDataMap: _imageDataMap,
      segmentMetadata: _allSegmentsMetadata,
      retranslatingSegments: _retranslatingSegments,
      heightCache: _heightCache,
      onHighlightParagraph: _highlightParagraph,
      onSegmentEdit: _handleSegmentEdit,
      onEditingStarted: _onEditingStarted,
      onRetrySegment: _handleRetrySegment,
      onMarkForRetry: _handleMarkForRetry,
      onUnmarkForRetry: _handleUnmarkForRetry,
      onExcludeSegment: _handleExcludeSegment,
      onUnexcludeSegment: _handleUnexcludeSegment,
      // Disable Clear/Unclear for DOCX workflow to avoid inconsistent export behavior.
      onClearSegment: isDocxWorkflow ? null : _handleClearSegment,
      onUnclearSegment: isDocxWorkflow ? null : _handleUnclearSegment,
      onUndo: _handleUndo,
      onRedo: _handleRedo,
      onExclusionUpdated: _handleExclusionUpdated,
      translationState: translationState,
      tokenUsage: tokenUsage,
      selectedExclusionFilters: _selectedExclusionFilters,
      onFormulaFix: _handleFormulaFixForSegment,
    );
  }

  /// Handle LLM-based LaTeX/formula repair for a single segment.
  Future<void> _handleFormulaFixForSegment(int index) async {
    final String currentText =
        _allSegmentsMetadata[index]?['target_text'] as String? ??
            _targetParagraphs.elementAt(index);
    if (currentText.isEmpty) {
      MessageService.showInfo(context, '当前片段没有译文可供修复');
      return;
    }
    try {
      // Read user prompt from QuickSettings (same as retry/retranslate)
      final qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final String? userPrompt =
          (qs.taskNote != null && qs.taskNote!.trim().isNotEmpty)
              ? qs.taskNote!.trim()
              : null;

      final TranslationService svc = TranslationService();
      final Map<String, dynamic> resp =
          await svc.repairLatexForSegment(
            _apiTaskId(),
            index,
            currentText,
            userPrompt: userPrompt,
          );
      final String fixed =
          (resp['fixed_text'] as String? ?? '').trimRight();
      final String original =
          (resp['original_text'] as String? ?? '').trimRight();
      if (fixed.isEmpty || fixed == original) {
        MessageService.showInfo(context, 'LLM 未给出更好的修复建议');
        return;
      }

      final bool? confirmed = await showDialog<bool>(
        context: context,
        builder: (BuildContext ctx) => AlertDialog(
            title: const Text('修复公式片段'),
            content: SizedBox(
              width: 600,
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    const Text(
                      '原片段（译文）：',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    SelectableText(original),
                    const SizedBox(height: 12),
                    const Text(
                      '修复后的片段：',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    SelectableText(fixed),
                  ],
                ),
              ),
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: const Text('取消'),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(true),
                child: const Text('应用修复'),
              ),
            ],
          ),
      );

      if (confirmed != true) {
        return;
      }

      // Apply fix by updating the segment on backend, then refresh segments.
      await TranslationService()
          .updateTranslationSegment(_apiTaskId(), index, targetText: fixed);

      // Invalidate local metadata cache for this segment
      _allSegmentsMetadata[index] ??= <String, dynamic>{};
      _allSegmentsMetadata[index]!['target_text'] = fixed;

      if (mounted) {
        setState(() {
          if (index < _targetParagraphs.length) {
            _targetParagraphs[index] = fixed;
          }
        });
      }

      // Trigger partial update + reload for consistency
      ref.read(translationSegmentsUpdateProvider.notifier).state = <int>[index];
      await _loadTranslationContent();

      if (mounted) {
        MessageService.showSuccess(context, '已应用 LLM 修复后的公式片段');
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, '公式修复失败: $e');
      }
    }
  }

  /// View PDF preview
  Future<void> _viewPdfPreview() async {
    final bool isPdfFile =
        widget.fileName?.toLowerCase().endsWith('.pdf') ?? false;
    final bool hasPdfDownload = widget.downloads?.containsKey('pdf') ?? false;

    if (!isPdfFile || !hasPdfDownload) {
      MessageService.showWarning(context, 'PDF preview not available');
      return;
    }

    // Show dialog to select table format and PDF type (translated/original)
    final Map<String, String>? exportOptions = await _showPdfExportDialog();
    if (exportOptions == null) {
      // User cancelled, don't open preview
      return;
    }

    final String tableFormat = exportOptions['tableFormat'] ?? 'html';
    final String pdfType = exportOptions['pdfType'] ?? 'translated';

    if (mounted) {
      setState(() {
        _loadingHtmlPreview = true;
      });
    }

    try {
      // Add PDF preview tab
      final PreviewTabsNotifier tabsNotifier = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
          : ref.read(previewTabsProvider.notifier);

      final PreviewTab pdfTab = PreviewTab(
        id: 'pdf_preview_${_apiTaskId()}_${DateTime.now().millisecondsSinceEpoch}',
        type: PreviewTabType.translationResult,
        title: pdfType == 'original' ? 'Original PDF (Debug)' : 'PDF Viewer',
        icon: pdfType == 'original' ? Icons.bug_report : Icons.picture_as_pdf,
        content: _buildPdfPreview(
          tableFormat: tableFormat,
          pdfType: pdfType,
        ),
        dataRef: <String, dynamic>{
          'taskId': _apiTaskId(),
          'flowId': widget.flowId,
          'downloads': widget.downloads,
        },
      );

      tabsNotifier.addTab(pdfTab);

      // Find the index of the newly added tab and switch to it
      final List<PreviewTab> currentTabs = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!)).tabs
          : ref.read(previewTabsProvider).tabs;
      final int tabIndex =
          currentTabs.indexWhere((PreviewTab t) => t.id == pdfTab.id);
      if (tabIndex >= 0) {
        tabsNotifier.switchToTab(tabIndex);
      }

      if (mounted) {
        MessageService.showSuccess(context, 'PDF preview opened');
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to open PDF preview: $e');
      }
    } finally {
      if (mounted) {
        setState(() {
          _loadingHtmlPreview = false;
        });
      }
    }
  }

  /// Build PDF preview widget
  Widget _buildPdfPreview({String? tableFormat, String? pdfType}) {
    String? relativeUrl;

    // If original PDF is selected (debug mode only), build debug URL
    if (pdfType == 'original' && kDebugMode) {
      final TranslationService svc = TranslationService();
      // Build debug URL for original PDF
      final String debugUrl = svc.buildDebugUrl(_apiTaskId(), 'original-pdf');
      relativeUrl = debugUrl;
    } else {
      // Translated PDF (default)
      relativeUrl = widget.downloads?['pdf'];
    }

    if (relativeUrl == null) {
      return const Center(
        child: Text('PDF download not available'),
      );
    }

    // Add table_body_format query parameter if provided
    var finalUrl = relativeUrl;
    if (tableFormat != null) {
      final Uri uri = Uri.parse(relativeUrl);
      final Uri updatedUri = uri.replace(
        queryParameters: <String, dynamic>{
          ...uri.queryParameters,
          'table_body_format': tableFormat,
        },
      );
      finalUrl = updatedUri.toString();
    }

    final String viewerUrl = finalUrl.startsWith('http')
        ? finalUrl
        : '${AppConfig.baseUrl}$finalUrl';

    return PdfPreview(
      downloadUrl: finalUrl,
      viewerUrl: viewerUrl,
      onDownload: widget.onDownload,
    );
  }

  /// View Translation Preview (HTML format using unified_preview.dart)
  Future<void> _viewTranslationPreview() async {
    _translationResultLog(
      '[Preview] _viewTranslationPreview called, taskId=${_apiTaskId()}, flowId=${widget.flowId}',
      level: LogLevel.info,
    );

    // Get downloads from widget first, then from translation state if needed
    var downloads = widget.downloads;
    _translationResultLog(
      '[Preview] Initial downloads from widget: ${downloads?.keys.toList()}',
    );

    if ((downloads == null || downloads.isEmpty) && widget.flowId != null) {
      // Try to get downloads from translation state
      try {
        final TranslationStateFamily translationState =
            ref.read(translationStateProviderFamily(widget.flowId!));
        final Map<String, String> stateDownloads = translationState.downloads;
        _translationResultLog(
          '[Preview] Downloads from translation state: ${stateDownloads.keys.toList()}',
        );
        if (stateDownloads.isNotEmpty) {
          downloads = stateDownloads.map(
            (String k, String v) => MapEntry(k.toString(), v.toString()),
          );
        }
      } catch (e) {
        _translationResultLog(
          '[Preview] Failed to get downloads from translation state: $e',
          level: LogLevel.warn,
        );
        // Fallback to widget.downloads
      }
    }

    _translationResultLog(
      '[Preview] Final downloads: ${downloads?.keys.toList()}, hasHtml=${downloads?.containsKey('html')}, hasMd=${downloads?.containsKey('md')}',
      level: LogLevel.info,
    );

    // If no HTML or MD in downloads, try to get from status API or build URL directly
    if (downloads == null ||
        (!downloads.containsKey('html') && !downloads.containsKey('md'))) {
      _translationResultLog(
        '[Preview] No HTML or MD in downloads, trying to get from status API...',
        level: LogLevel.info,
      );

      try {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> status = await svc.getStatus(_apiTaskId());
        final Map<String, dynamic>? statusDownloads =
            status['downloads'] as Map<String, dynamic>?;

        if (statusDownloads != null && statusDownloads.isNotEmpty) {
          final Map<String, String> statusDownloadsMap = statusDownloads
              .map((String k, v) => MapEntry(k.toString(), v.toString()));

          _translationResultLog(
            '[Preview] Status API downloads: ${statusDownloadsMap.keys.toList()}',
            level: LogLevel.info,
          );

          // Merge status downloads with existing downloads
          downloads ??= <String, String>{};
          downloads.addAll(statusDownloadsMap);
        }

        // If still no HTML/MD, try to build URL directly (backend may have it even if not in downloads)
        if (downloads != null &&
            !downloads.containsKey('html') &&
            !downloads.containsKey('md')) {
          // Building download URL directly...

          // Try MD first, then HTML
          final String mdUrl = svc.buildDownloadUrl(_apiTaskId(), 'md');
          final String htmlUrl = svc.buildDownloadUrl(_apiTaskId(), 'html');

          // Add to downloads map (will be validated when actually downloading)
          downloads['md'] = mdUrl;
          downloads['html'] = htmlUrl;

          // Built download URLs
        }
      } catch (e) {
        _translationResultLog(
          '[Preview] Failed to get downloads from status or build URL: $e',
          level: LogLevel.warn,
        );
      }
    }

    // Final check: if still no HTML/MD, show warning
    if (downloads == null ||
        (!downloads.containsKey('html') && !downloads.containsKey('md'))) {
      _translationResultLog(
        '[Preview] No HTML or MD download available after all attempts, showing warning',
        level: LogLevel.warn,
      );
      MessageService.showWarning(
        context,
        'Translation preview not available. Please wait for translation to complete.',
      );
      return;
    }

    if (mounted) {
      setState(() {
        _loadingHtmlPreview = true;
      });
    }

    try {
      // Creating Translation Preview tab

      // Add Translation Preview tab
      final PreviewTabsNotifier tabsNotifier = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
          : ref.read(previewTabsProvider.notifier);

      // TabsNotifier obtained

      // Use TranslationPreviewTabWidget (with toolbar) like the original implementation
      final TranslationPreviewTabWidget previewContent =
          TranslationPreviewTabWidget(
        taskId: _apiTaskId(),
        flowId: widget.flowId,
        downloads: downloads,
        onDownload: widget.onDownload,
      );

      // Use fixed ID for Preview tab (like the original implementation)
      final PreviewTab previewTab = PreviewTab(
        id: 'translation_preview_tab',
        type: PreviewTabType.translationResult,
        title: 'Translation Preview',
        icon: Icons.preview,
        content: previewContent,
        dataRef: <String, dynamic>{
          'taskId': _apiTaskId(),
          'downloads': downloads,
          'flowId': widget.flowId,
        },
      );

      // PreviewTab created

      // Use updateOrAddTab like the original implementation
      tabsNotifier.updateOrAddTab(previewTab);
      // Tab added to tabsNotifier

      // Find the index of the newly added tab and switch to it
      final List<PreviewTab> currentTabs = widget.flowId != null
          ? ref.read(previewTabsProviderFamily(widget.flowId!)).tabs
          : ref.read(previewTabsProvider).tabs;
      // Current tabs count: ${currentTabs.length}

      final int tabIndex = currentTabs
          .indexWhere((PreviewTab t) => t.id == 'translation_preview_tab');
      // Tab index found: $tabIndex

      if (tabIndex >= 0) {
        tabsNotifier.switchToTab(tabIndex);
        // Switched to tab at index $tabIndex
      } else {
        _translationResultLog(
          '[Preview] WARNING: Tab index not found after adding tab',
          level: LogLevel.warn,
        );
      }

      if (mounted) {
        MessageService.showSuccess(context, 'Translation preview opened');
        // Success message shown
      }
    } catch (e, stackTrace) {
      _translationResultLog(
        '[Preview] ERROR: Failed to open translation preview: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to open translation preview: $e',
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _loadingHtmlPreview = false;
        });
        // Loading state reset
      }
    }
  }

  /// Show preview settings dialog (similar to Convert)
  Future<void> _showPreviewSettingsDialog() async {
    try {
      // Get status to check for tables and equations
      final TranslationService svc = TranslationService();
      Map<String, dynamic> status;
      try {
        status = await svc.getStatus(_apiTaskId());
      } catch (e) {
        // Gracefully handle 404 when task has been released
        final errorString = e.toString();
        if (errorString.contains('404') || errorString.contains('Not Found')) {
          if (mounted) {
            MessageService.showInfo(
              context,
              'Preview settings are not available because the task has been released.',
            );
          }
          return;
        }
        rethrow;
      }
      final bool hasTables = status['has_tables'] == true;
      final bool hasInterlineEquations =
          status['has_interline_equations'] == true;

      // Check if there are any images (tables or equations as images)
      final bool hasImages = _imageDataMap.isNotEmpty ||
          (status['image_data_map'] != null &&
              (status['image_data_map'] as Map).isNotEmpty);

      if (!hasTables && !hasInterlineEquations && !hasImages) {
        MessageService.showInfo(
          context,
          'No image elements found. No settings needed.',
        );
        return;
      }

      if (!hasTables && !hasInterlineEquations) {
        MessageService.showInfo(context, 'No tables or equations to configure');
        return;
      }

      // Get current format settings from provider
      final formatSettings = ref.read(
        formatSettingsProviderFamily(_apiTaskId()),
      );
      // Create state variables for dialog with current settings or defaults
      var tableFormat = formatSettings.getTableFormat();
      var equationFormat = formatSettings.getEquationFormat();

      await DialogHelper.showGeneralDialog(
        context: context,
        barrierColor: Colors.black54,
        barrierLabel: 'Preview Settings',
        useRootNavigator: true,
        pageBuilder: (
          dialogContext,
          animation,
          secondaryAnimation,
        ) =>
            StatefulBuilder(
          builder: (BuildContext context, setDialogState) => Material(
            type: MaterialType.transparency,
            child: AlertDialog(
              title: const Text('Preview Settings'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    if (hasTables) ...<Widget>[
                      const Text(
                        'Table Format:',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      RadioListTile<String>(
                        title: const Text('Image'),
                        subtitle: const Text('Display tables as images'),
                        value: 'image',
                        groupValue: tableFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              tableFormat = value;
                            });
                          }
                        },
                      ),
                      RadioListTile<String>(
                        title: const Text('HTML'),
                        subtitle: const Text('Convert HTML tables to markdown'),
                        value: 'html',
                        groupValue: tableFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              tableFormat = value;
                            });
                          }
                        },
                      ),
                      const SizedBox(height: 16),
                    ],
                    if (hasInterlineEquations) ...<Widget>[
                      const Text(
                        'Equation Format:',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      RadioListTile<String>(
                        title: const Text('Image'),
                        subtitle: const Text('Display equations as images'),
                        value: 'image',
                        groupValue: equationFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              equationFormat = value;
                            });
                          }
                        },
                      ),
                      RadioListTile<String>(
                        title: const Text('LaTeX'),
                        subtitle:
                            const Text('Display equations as LaTeX formulas'),
                        value: 'text',
                        groupValue: equationFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              equationFormat = value;
                            });
                          }
                        },
                      ),
                    ],
                  ],
                ),
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () {
                    Navigator.of(context, rootNavigator: true).pop();
                  },
                  child: const Text('Cancel'),
                ),
                TextButton.icon(
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: const Text('Save as Default'),
                  onPressed: () async {
                    // Apply settings to provider first
                    final formatNotifier = ref.read(
                      formatSettingsProviderFamily(_apiTaskId()).notifier,
                    );
                    if (hasTables) {
                      formatNotifier.setTableFormat(tableFormat);
                    }
                    if (hasInterlineEquations) {
                      formatNotifier.setEquationFormat(equationFormat);
                    }
                    // Save as user defaults
                    await formatNotifier.saveAsUserDefaults();
                    // Use dialogContext instead of context to show message in dialog
                    MessageService.showSuccess(
                      dialogContext,
                      'Default format settings saved',
                    );
                  },
                ),
                ElevatedButton(
                  onPressed: () {
                    Navigator.of(context, rootNavigator: true).pop();
                    // Apply settings to provider
                    final formatNotifier = ref.read(
                      formatSettingsProviderFamily(_apiTaskId()).notifier,
                    );
                    if (hasTables) {
                      formatNotifier.setTableFormat(tableFormat);
                    }
                    if (hasInterlineEquations) {
                      formatNotifier.setEquationFormat(equationFormat);
                    }
                    MessageService.showSuccess(context, 'Settings applied');
                    // Note: Translation Preview uses UnifiedPreviewWidget which will
                    // automatically reload when format settings change via watch
                  },
                  child: const Text('Apply'),
                ),
              ],
            ),
          ),
        ),
        transitionBuilder: (
          BuildContext context,
          Animation<double> animation,
          Animation<double> secondaryAnimation,
          Widget child,
        ) =>
            FadeTransition(
          opacity: animation,
          child: child,
        ),
      );
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to show settings: $e');
      }
    }
  }

  /// Show download dialog. Export formats are fixed per workflow type;
  /// documents are generated on-demand when user picks a format, so we do not
  /// depend on status downloads.
  Future<void> _showDownloadDialog() async {
    final String resolvedWorkflowType = widget.workflowType ??
        (widget.flowId != null
            ? ref
                .read(translationQuickSettingsProviderFamily(widget.flowId!))
                .workflowType
            : ref.read(translationQuickSettingsProvider).workflowType);

    final String fileNameLower = widget.fileName?.toLowerCase() ?? '';
    final bool isPdfFile = fileNameLower.endsWith('.pdf');
    final bool isArbFile = fileNameLower.endsWith('.arb');

    // Get status to check for tables and equations (for PDF workflow format options)
    Map<String, dynamic>? status;
    try {
      final TranslationService svc = TranslationService();
      status = await svc.getStatus(_apiTaskId());
    } catch (e) {
      // If status fetch fails, continue without format options
      status = null;
    }
    final bool isDocWorkflow = fileNameLower.endsWith('.docx') ||
        fileNameLower.endsWith('.doc') ||
        resolvedWorkflowType == 'docx';
    final bool isPptxWorkflow = fileNameLower.endsWith('.pptx') ||
        fileNameLower.endsWith('.ppt') ||
        resolvedWorkflowType == 'pptx';
    final bool isXlsxWorkflow = fileNameLower.endsWith('.xlsx') ||
        fileNameLower.endsWith('.xls') ||
        fileNameLower.endsWith('.csv') ||
        resolvedWorkflowType == 'xlsx';
    final bool isMobiWorkflow = fileNameLower.endsWith('.mobi') ||
        fileNameLower.endsWith('.azw') ||
        resolvedWorkflowType == 'mobi';
    final bool isEpubWorkflow =
        fileNameLower.endsWith('.epub') || resolvedWorkflowType == 'epub';
    final bool isJsonWorkflow =
        fileNameLower.endsWith('.json') || resolvedWorkflowType == 'json';
    final bool isQtTsWorkflow =
        fileNameLower.endsWith('.ts') || resolvedWorkflowType == 'ts';

    // Fixed export formats per workflow; no dependency on status downloads
    final List<String> availableFormats;
    final bool shouldHidePdf = widget.isTextMode ||
        resolvedWorkflowType == 'txt' ||
        (resolvedWorkflowType == 'markdown_based' && !isPdfFile);

    if (isQtTsWorkflow) {
      availableFormats = <String>['ts'];
    } else if (isPptxWorkflow) {
      availableFormats = <String>['pptx', 'html', 'md'];
    } else if (isXlsxWorkflow) {
      availableFormats = <String>['xlsx', 'html', 'md'];
    } else if (isMobiWorkflow) {
      availableFormats = <String>['mobi', 'epub', 'html', 'md', 'docx'];
    } else if (isEpubWorkflow) {
      availableFormats = <String>['epub', 'html', 'md', 'docx'];
    } else if (isJsonWorkflow) {
      if (isArbFile) {
        availableFormats = <String>['html', 'json', 'arb'];
      } else {
        availableFormats = <String>['html', 'json'];
      }
    } else if (resolvedWorkflowType == 'html') {
      // HTML workflow: docx, md, html (PDF not supported)
      availableFormats = <String>['docx', 'md', 'html'];
    } else {
      // PDF / markdown_based / txt: docx, md, html; add pdf when not hidden (e.g. PDF source)
      availableFormats = <String>['docx', 'md', 'html'];
      if (!shouldHidePdf) {
        availableFormats.add('pdf');
      }
      if (isDocWorkflow) {
        availableFormats.remove('pdf');
      }
    }

    if (availableFormats.isEmpty) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showWarning(context, l10n.translationExportNoFormats);
      return;
    }

    // Build download options (for MD, always offer embedded and with-images variants)
    final List<Map<String, dynamic>> downloadOptions = <Map<String, dynamic>>[];
    for (final String format in availableFormats) {
      if (format == 'md') {
        downloadOptions.add(<String, dynamic>{
          'type': 'md',
          'label': 'MD (Embedded Images)',
          'embedImages': true,
        });
        downloadOptions.add(<String, dynamic>{
          'type': 'md',
          'label': 'MD (With Images Folder)',
          'embedImages': false,
        });
      } else if (format == 'epub' || format == 'mobi') {
        // For EPUB/MOBI, always use the unified ebook engine path on the backend.
        // Do not expose engine names (Pandoc/Calibre) in the UI.
        downloadOptions.add(<String, dynamic>{
          'type': format,
          'label': format.toUpperCase(),
          'embedImages': null,
          'ebookEngine': 'pandoc',
        });
      } else {
        downloadOptions.add(<String, dynamic>{
          'type': format,
          'label': format.toUpperCase(),
          'embedImages': null,
        });
      }
    }

    // Check if this is a PDF workflow (markdown_based) to show format options
    final bool isPdfWorkflow =
        resolvedWorkflowType == 'markdown_based' || isPdfFile;
    final bool hasTables = status?['has_tables'] as bool? ?? false;
    final bool hasInterlineEquations =
        status?['has_interline_equations'] as bool? ?? false;
    final bool showFormatOptions =
        isPdfWorkflow && (hasTables || hasInterlineEquations);

    final l10n = AppLocalizations.of(context)!;

    DialogHelper.showGeneralDialog(
      context: context,
      barrierColor: Colors.black54,
      barrierLabel: l10n.translationExportDialogTitle,
      useRootNavigator: true,
      pageBuilder: (
        dialogContext,
        animation,
        secondaryAnimation,
      ) =>
          Consumer(
        builder: (BuildContext context, WidgetRef ref, Widget? child) {
          // Get current format settings from provider (watch for changes)
          final formatSettings = ref.watch(
            formatSettingsProviderFamily(_apiTaskId()),
          );
          String tableFormat = formatSettings.getTableFormat();
          String equationFormat = formatSettings.getEquationFormat();

          return StatefulBuilder(
            builder: (BuildContext context, setDialogState) => Material(
              type: MaterialType.transparency,
              child: AlertDialog(
                title: Text(l10n.translationExportDialogTitle),
                content: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      // Format options for PDF workflow (moved to top)
                      if (showFormatOptions) ...<Widget>[
                        Text(
                          l10n.translationExportFormatOptionsTitle,
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 12),
                        if (hasTables) ...<Widget>[
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              SizedBox(
                                width: 120, // Fixed width for label alignment
                                child: Text(
                                  l10n.translationExportTableFormatLabel,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Row(
                                  children: <Widget>[
                                    Radio<String>(
                                      value: 'image',
                                      groupValue: tableFormat,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            tableFormat = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setTableFormat(value);
                                        }
                                      },
                                    ),
                                    Text(
                                      l10n.translationExportTableFormatImage,
                                    ),
                                    const SizedBox(width: 16),
                                    Radio<String>(
                                      value: 'html',
                                      groupValue: tableFormat,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            tableFormat = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setTableFormat(value);
                                        }
                                      },
                                    ),
                                    Text(
                                      l10n.translationExportTableFormatHtml,
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                        ],
                        if (hasInterlineEquations) ...<Widget>[
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              SizedBox(
                                width:
                                    120, // Fixed width for label alignment (same as Table Format)
                                child: Text(
                                  l10n.translationExportEquationFormatLabel,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Row(
                                  children: <Widget>[
                                    Radio<String>(
                                      value: 'image',
                                      groupValue: equationFormat,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            equationFormat = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setEquationFormat(value);
                                        }
                                      },
                                    ),
                                    Text(
                                      l10n.translationExportEquationFormatImage,
                                    ),
                                    const SizedBox(width: 16),
                                    Radio<String>(
                                      value: 'text',
                                      groupValue: equationFormat,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            equationFormat = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setEquationFormat(value);
                                        }
                                      },
                                    ),
                                    Text(
                                      l10n.translationExportEquationFormatLatex,
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ],
                        const Divider(height: 24),
                      ],

                      // Download format options (moved to bottom)
                      ...downloadOptions.map((option) {
                        final fileType = option['type'] as String;
                        final label = option['label'] as String;
                        final embedImages = option['embedImages'] as bool?;
                        final ebookEngine = option['ebookEngine'] as String?;
                        final downloadKey = embedImages != null
                            ? '${fileType}_${embedImages ? 'embedded' : 'with_images'}'
                            : (ebookEngine != null ? '${fileType}_$ebookEngine' : fileType);
                        final isFormatDownloading =
                            _downloading[downloadKey] ?? false;
                        return ListTile(
                          enabled: !isFormatDownloading,
                          leading: isFormatDownloading
                              ? const SizedBox(
                                  width: 24,
                                  height: 24,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2),
                                )
                              : Icon(
                                  _getFormatIcon(fileType),
                                  color: Theme.of(context).colorScheme.primary,
                                ),
                          title: Text(
                            label,
                            style: TextStyle(
                              fontWeight: FontWeight.w500,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                          ),
                          trailing: Icon(
                            Icons.download,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          onTap: isFormatDownloading
                              ? null
                              : () {
                                  // Capture current format values from dialog state before closing
                                  final currentTableFormat = tableFormat;
                                  final currentEquationFormat = equationFormat;
                                  final ebookEngine = option['ebookEngine'] as String?;
                                  Navigator.of(context, rootNavigator: true)
                                      .pop();
                                  _handlePreviewFormatDownload(
                                    fileType,
                                    embedImages: embedImages,
                                    tableFormat: currentTableFormat,
                                    equationFormat: currentEquationFormat,
                                    ebookEngine: ebookEngine,
                                  );
                                },
                        );
                      }),
                    ],
                  ),
                ),
                actions: <Widget>[
                  TextButton(
                    onPressed: () {
                      Navigator.of(context, rootNavigator: true).pop();
                    },
                    child: const Text('Cancel'),
                  ),
                ],
              ),
            ),
          );
        },
      ),
      transitionBuilder: (
        BuildContext context,
        Animation<double> animation,
        Animation<double> secondaryAnimation,
        Widget child,
      ) =>
          FadeTransition(
        opacity: animation,
        child: child,
      ),
    );
  }

  /// Handle format download with format parameters (for Preview Settings)
  Future<void> _handlePreviewFormatDownload(
    String fileType, {
    bool? embedImages,
    String? tableFormat,
    String? equationFormat,
    String? ebookEngine,
  }) async {
    if (widget.onDownload == null) {
      MessageService.showError(context, 'Download not available');
      return;
    }

    try {
      final TranslationService svc = TranslationService();
      var downloadUrl = svc.buildDownloadUrl(_apiTaskId(), fileType);
      final Uri uri = Uri.parse(downloadUrl);
      final Map<String, String> queryParams =
          Map<String, String>.from(uri.queryParameters);

      // Add format parameters for MD, HTML, DOCX, PDF
      if (fileType == 'md' ||
          fileType == 'html' ||
          fileType == 'docx' ||
          fileType == 'pdf') {
        final formatSettings = ref.read(
          formatSettingsProviderFamily(_apiTaskId()),
        );
        queryParams['table_body_format'] =
            tableFormat ?? formatSettings.getTableFormat();
        queryParams['equation_format'] =
            equationFormat ?? formatSettings.getEquationFormat();
        if (fileType == 'md' && embedImages != null) {
          queryParams['embed_images'] = embedImages.toString();
        }
      }

      // For EPUB/MOBI, add ebook_engine when user chose Pandoc or Calibre
      if ((fileType == 'epub' || fileType == 'mobi') && ebookEngine != null) {
        queryParams['ebook_engine'] = ebookEngine;
      }

      downloadUrl = uri.replace(queryParameters: queryParams).toString();
      widget.onDownload!(fileType, downloadUrl);
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to download $fileType: $e');
      }
    }
  }

  /// Get icon for file format
  IconData _getFormatIcon(String format) {
    switch (format.toLowerCase()) {
      case 'md':
        return Icons.description;
      case 'html':
        return Icons.code;
      case 'docx':
        return Icons.description;
      case 'pdf':
        return Icons.picture_as_pdf;
      default:
        return Icons.file_download;
    }
  }

  /// Show PDF export dialog with table format and PDF type (translated/original) options
  /// Returns a Map with 'tableFormat' and 'pdfType' keys, or null if cancelled
  Future<Map<String, String>?> _showPdfExportDialog() async =>
      DialogHelper.showDialog<Map<String, String>>(
        context: context,
        builder: (BuildContext context) {
          String selectedFormat = 'html'; // Default value
          String selectedPdfType = 'translated'; // Default: translated PDF

          return AlertDialog(
            title: const Text('PDF Preview Options'),
            content: StatefulBuilder(
              builder: (BuildContext context, setState) => Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  // Development notice banner
                  Container(
                    padding: const EdgeInsets.all(12),
                    margin: const EdgeInsets.only(bottom: 12),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.orange.shade300),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Icon(
                          Icons.construction,
                          color: Colors.orange.shade700,
                          size: 20,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'PDF export is still under development. The generated PDF may have imperfections such as layout shifts or missing fonts. We are continuously improving this feature.',
                            style: TextStyle(
                              fontSize: 13,
                              color: Colors.orange.shade900,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  // PDF type selection (only in debug mode)
                  if (kDebugMode) ...<Widget>[
                    const Text(
                      'Select PDF type:',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    RadioListTile<String>(
                      title: const Text('Translated PDF'),
                      subtitle: const Text('Translated version (default)'),
                      value: 'translated',
                      groupValue: selectedPdfType,
                      onChanged: (value) {
                        if (value != null) {
                          setState(() {
                            selectedPdfType = value;
                          });
                        }
                      },
                    ),
                    RadioListTile<String>(
                      title: const Text('Original PDF'),
                      subtitle: const Text('Original version (debug only)'),
                      value: 'original',
                      groupValue: selectedPdfType,
                      onChanged: (value) {
                        if (value != null) {
                          setState(() {
                            selectedPdfType = value;
                          });
                        }
                      },
                    ),
                    const Divider(),
                    const SizedBox(height: 8),
                  ],
                  // Table format selection
                  const Text(
                    'Choose how tables should be rendered in the PDF:',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  RadioListTile<String>(
                    title: const Text('HTML'),
                    subtitle: const Text(
                      'Tables rendered as HTML text (translatable)',
                    ),
                    value: 'html',
                    groupValue: selectedFormat,
                    onChanged: (value) {
                      if (value != null) {
                        setState(() {
                          selectedFormat = value;
                        });
                      }
                    },
                  ),
                  RadioListTile<String>(
                    title: const Text('Image'),
                    subtitle: const Text(
                      'Tables rendered as images (not translatable)',
                    ),
                    value: 'image',
                    groupValue: selectedFormat,
                    onChanged: (value) {
                      if (value != null) {
                        setState(() {
                          selectedFormat = value;
                        });
                      }
                    },
                  ),
                ],
              ),
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(context).pop(), // Cancel
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () => Navigator.of(context).pop(<String, String>{
                  'tableFormat': selectedFormat,
                  'pdfType': selectedPdfType,
                }), // Confirm
                child: const Text('OK'),
              ),
            ],
          );
        },
      );
}
