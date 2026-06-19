// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart';
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
import '../providers/translation_state_provider.dart';
import '../providers/format_settings_provider.dart';
import '../models/preview_tab.dart';
import '../models/segment_pair.dart';
import '../widgets/pdf_preview.dart';
import '../../../shared/config/pagination_config.dart';
import '../widgets/translation_quick_settings.dart';
import '../widgets/translation_result/preview_selection.dart';
import '../widgets/translation_result/pdf_compare_layout_mode.dart';
import '../widgets/translation_result/translation_preview_dialog.dart';
import '../widgets/translation_result/translation_full_compare_preview_tab.dart';
import 'translation_result/segment_pdf_typography_dialog.dart';
import '../widgets/translation_result/preview_url_utils.dart';
import '../widgets/translation_result/image_format_utils.dart';
import '../widgets/translation_result/image_overlay_preview.dart';
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

const String _kTranslationPreviewTabId = 'translation_preview_tab';

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
  // Dedicated scroll controller for PDF revision side panel (avoids duplicate attachment)
  final ScrollController _pdfRevisionScrollController = ScrollController();

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

  // Keys dedicated to PDF revision panel (must not overlap with main comparison panel)
  final Map<int, GlobalKey> _pdfRevisionSegmentPairKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};
  final Map<int, GlobalKey> _pdfRevisionSourceItemKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};
  final Map<int, GlobalKey> _pdfRevisionTargetItemKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};

  /// Last preview mode chosen in the unified preview dialog (null = use workflow default).
  TranslationPreviewMode? _lastPreviewMode;

  /// Whether full-document compare was enabled in the last preview dialog.
  bool? _lastFullDocumentCompare;

  /// Whether linked scroll was enabled for full-document compare preview.
  bool? _lastSyncScroll;

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

  bool _isPdfSourceFile() {
    final fileNameLower = widget.fileName?.toLowerCase() ?? '';
    return fileNameLower.endsWith('.pdf');
  }

  bool _isImageSourceFile() {
    return isMineruLayoutImageFileName(widget.fileName);
  }

  bool get _shouldRefreshOverlayPreviewRevision =>
      _isPdfSourceFile() || _isImageSourceFile();

  String? _originalImageDownloadKey() {
    return originalImageDownloadExtension(widget.fileName);
  }

  bool _hasImageDownload(Map<String, String>? downloads) {
    final String? key = _originalImageDownloadKey();
    if (key == null) {
      return false;
    }
    if (downloads == null) {
      return false;
    }
    if (downloads.containsKey(key)) {
      return true;
    }
    if (key == 'jpg' || key == 'jpeg') {
      return downloads.containsKey('jpg') || downloads.containsKey('jpeg');
    }
    return false;
  }

  bool _translationLooksComplete(dynamic translationState) {
    if (translationState == null) {
      return false;
    }
    final String status =
        (translationState.statusText ?? '').toString().toLowerCase();
    final int progress = translationState.progress is int
        ? translationState.progress as int
        : int.tryParse('${translationState.progress}') ?? 0;
    final bool isTranslating = translationState.isTranslating == true;
    if (status == 'completed' || status == 'failed') {
      return true;
    }
    if (status == 'processing' && progress >= 100) {
      return true;
    }
    if (!isTranslating && progress >= 100) {
      return true;
    }
    final dynamic downloads = translationState.downloads;
    return downloads is Map && downloads.isNotEmpty && !isTranslating;
  }

  Map<String, String>? _mergeDownloadMaps(
    Map<String, String>? widgetDownloads,
    Map<String, String>? stateDownloads,
  ) {
    if ((widgetDownloads == null || widgetDownloads.isEmpty) &&
        (stateDownloads == null || stateDownloads.isEmpty)) {
      return null;
    }
    final Map<String, String> merged = <String, String>{};
    if (widgetDownloads != null) {
      merged.addAll(widgetDownloads);
    }
    if (stateDownloads != null) {
      merged.addAll(stateDownloads);
    }
    return merged;
  }

  Map<String, String>? _resolveEffectiveDownloads(dynamic translationState) {
    Map<String, String>? stateDownloads;
    if (translationState?.downloads is Map) {
      final Map raw = translationState.downloads as Map;
      if (raw.isNotEmpty) {
        stateDownloads = raw.map(
          (dynamic k, dynamic v) => MapEntry(k.toString(), v.toString()),
        );
      }
    }

    Map<String, String>? merged =
        _mergeDownloadMaps(widget.downloads, stateDownloads);

    if (_isPdfSourceFile() &&
        _apiTaskId() != 'pending' &&
        _translationLooksComplete(translationState) &&
        merged?.containsKey('pdf') != true) {
      merged ??= <String, String>{};
      merged['pdf'] = TranslationService().buildDownloadUrl(_apiTaskId(), 'pdf');
    }

    final String? imageKey = _originalImageDownloadKey();
    if (imageKey != null &&
        _apiTaskId() != 'pending' &&
        _translationLooksComplete(translationState) &&
        !_hasImageDownload(merged)) {
      merged ??= <String, String>{};
      merged[imageKey] =
          TranslationService().buildDownloadUrl(_apiTaskId(), imageKey);
    }

    return merged;
  }

  bool _shouldFetchOnDemandDownloads(
    Map<String, String>? effectiveDownloads,
    dynamic translationState,
  ) {
    if (_apiTaskId() == 'pending' || widget.flowId == null) {
      return false;
    }
    if (_lastTaskIdForOnDemandDownloadsFetch == _apiTaskId()) {
      return false;
    }
    if (effectiveDownloads == null || effectiveDownloads.isEmpty) {
      return true;
    }
    if (_isPdfSourceFile() &&
        !effectiveDownloads.containsKey('pdf') &&
        _translationLooksComplete(translationState)) {
      return true;
    }
    final String? imageKey = _originalImageDownloadKey();
    if (imageKey != null &&
        !_hasImageDownload(effectiveDownloads) &&
        _translationLooksComplete(translationState)) {
      return true;
    }
    return false;
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
  int _pdfPreviewRevision = 0;
  final ValueNotifier<int> _pdfPreviewRevisionNotifier = ValueNotifier<int>(0);
  final ValueNotifier<Set<int>> _pdfPreviewDirtySegmentsNotifier =
      ValueNotifier<Set<int>>(<int>{});
  Timer? _pdfPreviewRevisionDebounceTimer;
  static const Duration _pdfPreviewRevisionDebounce =
      Duration(milliseconds: 500);
  final Set<int> _pendingDirtySegmentIndices = <int>{};
  // Coalesce PDF preview refresh during batch typography updates.
  int _pdfTypographyBatchDepth = 0;
  final ValueNotifier<int> _segmentUiRevisionNotifier = ValueNotifier<int>(0);

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
  Set<int>? _cachedFilteredIndicesPdfPages;

  // PDF revision page filter (empty = all pages)
  Set<int> _selectedPdfPageNumbers = <int>{};
  late final ValueNotifier<Set<int>> _selectedPdfPageNumbersNotifier =
      ValueNotifier<Set<int>>(<int>{});
  late final ValueNotifier<int?> _pdfPreviewJumpPageNotifier =
      ValueNotifier<int?>(null);
  late final ValueNotifier<int> _pdfPreviewJumpPageTriggerNotifier =
      ValueNotifier<int>(0);
  int _pdfPreviewJumpPageTrigger = 0;
  late final ValueNotifier<int?> _pdfHighlightBboxPageNotifier =
      ValueNotifier<int?>(null);
  late final ValueNotifier<List<double>?> _pdfHighlightBboxNotifier =
      ValueNotifier<List<double>?>(null);
  late final ValueNotifier<bool> _autoFollowSegmentPdfPageNotifier =
      ValueNotifier<bool>(true);
  late final ValueNotifier<bool> _showSelectedSegmentMarkerNotifier =
      ValueNotifier<bool>(true);
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

  /// Handle filter change from status bar filter chips
  Future<void> _handleFiltersChanged(Set<String> filters) async {
    if (_isRefreshingForFilter) return;

    _setSelectedExclusionFilters(filters);
    _clearFilteredIndicesCache();

    _isRefreshingForFilter = true;
    try {
      await _segmentsPaginationController?.loadFirstPage();
      if (mounted) {
        _segmentUiRevisionNotifier.value++;
        setState(() {});
      }
    } finally {
      if (mounted) {
        _isRefreshingForFilter = false;
      }
    }
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

      // PDF layout: display defaults come from FormatSettings getters (table=image, equation=latex).
      // Do not auto-persist legacy html/text values into task state.
      final bool isPdfFile =
          widget.fileName?.toLowerCase().endsWith('.pdf') ?? false;
      final bool hasTables = status['has_tables'] as bool? ?? false;
      final bool hasInterlineEquations =
          status['has_interline_equations'] as bool? ?? false;
      if (isPdfFile &&
          (hasTables || hasInterlineEquations) &&
          !_formatDialogShown &&
          mounted) {
        final formatNotifier = ref.read(
          formatSettingsProviderFamily(taskId).notifier,
        );
        final FormatSettings current = ref.read(
          formatSettingsProviderFamily(taskId),
        );
        // Clear legacy auto-persisted table default from older builds (html).
        if (hasTables && current.tableFormat == 'html') {
          formatNotifier.clearTableFormat();
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
      _closeTranslationPreviewTabSilently();
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
    _closeTranslationPreviewTabSilently();
    _selectedExclusionFiltersNotifier.dispose();
    _selectedPdfPageNumbersNotifier.dispose();
    _pdfPreviewJumpPageNotifier.dispose();
    _pdfPreviewJumpPageTriggerNotifier.dispose();
    _pdfHighlightBboxPageNotifier.dispose();
    _pdfHighlightBboxNotifier.dispose();
    _autoFollowSegmentPdfPageNotifier.dispose();
    _showSelectedSegmentMarkerNotifier.dispose();
    _highlightedIndexNotifier.dispose();
    _pdfPreviewRevisionNotifier.dispose();
    _pdfPreviewDirtySegmentsNotifier.dispose();
    _pdfPreviewRevisionDebounceTimer?.cancel();
    _segmentUiRevisionNotifier.dispose();
    _scrollManager?.dispose();
    _comparisonScrollController.dispose();
    _pdfRevisionScrollController.dispose();
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
    final bool cacheValid = _cachedFilteredIndices != null &&
        _cachedFilteredIndicesFilters != null &&
        _cachedFilteredIndicesPdfPages != null &&
        _cachedFilteredIndicesTotalCount != null &&
        _cachedFilteredIndicesTotalCount == _totalSegmentsCount &&
        _cachedFilteredIndicesFilters!.length ==
            _selectedExclusionFilters.length &&
        _cachedFilteredIndicesFilters!.containsAll(_selectedExclusionFilters) &&
        _selectedExclusionFilters.containsAll(_cachedFilteredIndicesFilters!) &&
        _cachedFilteredIndicesPdfPages!.length ==
            _selectedPdfPageNumbers.length &&
        _cachedFilteredIndicesPdfPages!.containsAll(_selectedPdfPageNumbers) &&
        _selectedPdfPageNumbers.containsAll(_cachedFilteredIndicesPdfPages!);

    if (cacheValid) {
      return _cachedFilteredIndices!;
    }

    return _finalizeFilteredSegmentIndices(_getStateFilteredSegmentIndices());
  }

  List<int> _getStateFilteredSegmentIndices() {
    if (_selectedExclusionFilters.isEmpty) {
      return List.generate(_totalSegmentsCount, (int i) => i);
    }

    if (_selectedExclusionFilters.contains('failed')) {
      return _failedSegments.keys.toList()..sort();
    }

    if (_selectedExclusionFilters.contains('included')) {
      final Set<int> excludedSet = _excludedSegments.keys.toSet();
      return List.generate(
        _totalSegmentsCount,
        (int index) => index,
        growable: false,
      ).where((int index) => !excludedSet.contains(index)).toList();
    }

    if (_selectedExclusionFilters.contains('all_excluded')) {
      return _excludedSegments.keys.toList()..sort();
    }

    const Set<String> stateKeys = <String>{
      'translated', 'pending', 'excluded', 'retry', 'cleared', 'images',
    };
    if (_selectedExclusionFilters.length == 1 &&
        stateKeys.contains(_selectedExclusionFilters.first)) {
      final String stateFilter = _selectedExclusionFilters.first;
      final List<int> filteredIndices = <int>[];
      for (int index = 0; index < _totalSegmentsCount; index++) {
        final Map<String, dynamic> metadata =
            _allSegmentsMetadata[index] ?? <String, dynamic>{};
        final bool isImage = metadata['is_image'] as bool? ?? false;
        final bool isFailed = metadata['is_failed'] as bool? ?? false;
        final bool isExcluded = metadata['is_excluded'] as bool? ?? false;
        final String? targetText = metadata['target_text'] as String?;
        final String? status = metadata['status'] as String?;
        final bool needsRetry = metadata['needs_retry'] as bool? ?? false;
        final bool isCleared = status == 'cleared';

        bool match = false;
        switch (stateFilter) {
          case 'translated':
            match = !isImage && !isExcluded && !isFailed && !isCleared &&
                targetText != null && targetText.isNotEmpty;
          case 'pending':
            match = !isImage && !isExcluded && !isFailed && !isCleared &&
                (targetText == null || targetText.isEmpty);
          case 'excluded':
            match = isExcluded && !isFailed;
          case 'retry':
            match = needsRetry || isFailed;
          case 'cleared':
            match = isCleared;
          case 'images':
            match = isImage;
        }
        if (match) filteredIndices.add(index);
      }
      return filteredIndices;
    }

    final List<int> filteredIndices = <int>[];
    for (int index = 0; index < _totalSegmentsCount; index++) {
      final Map<String, dynamic> metadata =
          _allSegmentsMetadata[index] ?? <String, dynamic>{};
      final String? filterKey = segmentFilterKeyFromMetadata(metadata);
      if (filterKey != null && _selectedExclusionFilters.contains(filterKey)) {
        filteredIndices.add(index);
      }
    }
    return filteredIndices;
  }

  Set<int> _availablePdfPageNumbers() {
    final Set<int> pages = <int>{};
    for (final Map<String, dynamic> metadata in _allSegmentsMetadata.values) {
      final int? page = _readPdfPageNumber(metadata);
      if (page != null) {
        pages.add(page);
      }
    }
    return pages;
  }

  int? _readPdfPageNumber(Map<String, dynamic>? metadata) {
    final dynamic raw = metadata?['pdf_page_number'];
    if (raw is int) {
      return raw;
    }
    if (raw is num) {
      return raw.toInt();
    }
    if (raw is String) {
      return int.tryParse(raw);
    }
    return null;
  }

  /// Parse `layout_block_bbox` from an API segment dict into
  /// `List<List<double>>` (list of [x0, y0, x1, y1] entries in PDF points).
  static List<List<double>>? _parseLayoutBlockBbox(dynamic raw) {
    if (raw is! List || raw.isEmpty) {
      return null;
    }
    // Single bbox flat list: [x0, y0, x1, y1]
    if (raw.length >= 4 && raw[0] is num) {
      return <List<double>>[
        <double>[
          (raw[0] as num).toDouble(),
          (raw[1] as num).toDouble(),
          (raw[2] as num).toDouble(),
          (raw[3] as num).toDouble(),
        ],
      ];
    }
    final List<List<double>> result = <List<double>>[];
    for (final dynamic entry in raw) {
      if (entry is List && entry.length >= 4) {
        result.add(<double>[
          (entry[0] as num).toDouble(),
          (entry[1] as num).toDouble(),
          (entry[2] as num).toDouble(),
          (entry[3] as num).toDouble(),
        ]);
      }
    }
    return result.isNotEmpty ? result : null;
  }

  /// Read the primary (first) layout block bbox for a segment, in image pixel coords.
  /// Returns `[x0, y0, x1, y1]` or null.
  List<double>? _readSegmentBbox(int index) {
    final Map<String, dynamic>? metadata = _allSegmentsMetadata[index];
    final dynamic raw = metadata?['layout_block_bbox'];
    final List<List<double>>? parsed = _parseLayoutBlockBbox(raw);
    if (parsed == null || parsed.isEmpty || parsed.first.length < 4) {
      return null;
    }
    final List<double> first = parsed.first;
    return <double>[first[0], first[1], first[2], first[3]];
  }

  static bool _isMineruTextImageLikeSegmentText(String? text) {
    if (text == null || text.trim().isEmpty) {
      return false;
    }
    final String normalized = text;
    final RegExp detailsRe = RegExp(r'<details\b', caseSensitive: false);
    final RegExp summaryRe = RegExp(
      r'<summary\b[^>]*>\s*(text_image|natural_image)\s*</summary>',
      caseSensitive: false,
    );
    final RegExp closingRe = RegExp(r'</details>', caseSensitive: false);
    if (detailsRe.hasMatch(normalized) && summaryRe.hasMatch(normalized)) {
      return true;
    }
    // Split markdown closing half, e.g. "DAYONE\n</details>"
    return closingRe.hasMatch(normalized) && !detailsRe.hasMatch(normalized);
  }

  bool _isAllPdfPagesSelected() {
    if (_selectedPdfPageNumbers.isEmpty) {
      return true;
    }
    final Set<int> available = _availablePdfPageNumbers();
    return available.isNotEmpty &&
        available.every(_selectedPdfPageNumbers.contains);
  }

  List<int> _applyPdfPageNumberFilter(List<int> indices) {
    if (_selectedPdfPageNumbers.isEmpty || _isAllPdfPagesSelected()) {
      return indices;
    }
    return indices
        .where((int index) {
          final int? page = _readPdfPageNumber(_allSegmentsMetadata[index]);
          return page != null && _selectedPdfPageNumbers.contains(page);
        })
        .toList();
  }

  List<int> _finalizeFilteredSegmentIndices(List<int> stateFiltered) {
    final List<int> result = _applyPdfPageNumberFilter(stateFiltered);
    _cachedFilteredIndices = result;
    _cachedFilteredIndicesFilters =
        Set<String>.from(_selectedExclusionFilters);
    _cachedFilteredIndicesPdfPages =
        Set<int>.from(_selectedPdfPageNumbers);
    _cachedFilteredIndicesTotalCount = _totalSegmentsCount;
    return result;
  }

  void _setSelectedPdfPageNumbers(Set<int> pages) {
    _selectedPdfPageNumbers = Set<int>.from(pages);
    _selectedPdfPageNumbersNotifier.value =
        Set<int>.from(_selectedPdfPageNumbers);
  }

  void _requestPdfPreviewJump(int pageNumber) {
    if (pageNumber < 1) {
      return;
    }
    _pdfPreviewJumpPageNotifier.value = pageNumber;
    _pdfPreviewJumpPageTriggerNotifier.value = ++_pdfPreviewJumpPageTrigger;
  }

  void _requestPdfBboxHighlight(int index) {
    if (!_showSelectedSegmentMarkerNotifier.value) {
      _clearPdfBboxHighlight();
      return;
    }
    final Map<String, dynamic>? meta = _allSegmentsMetadata[index];
    final int? page = _readPdfPageNumber(meta);
    final List<double>? bbox = _readSegmentBbox(index);
    final dynamic indicesRaw = meta?['layout_block_indices'];
    final dynamic bboxRaw = meta?['layout_block_bbox'];
    final dynamic resolution = meta?['layout_block_indices_resolution'];
    final String? sourceParagraph = index >= 0 && index < _sourceParagraphs.length
        ? _sourceParagraphs[index]
        : null;
    final bool mineruTextImage =
        _isMineruTextImageLikeSegmentText(sourceParagraph);
    _translationResultLog(
      '[BBOX-HIGHLIGHT] segment=$index page=$page '
      'indices=$indicesRaw resolution=$resolution '
      'mineru_text_image=$mineruTextImage '
      'metadata_bbox=$bboxRaw resolved_bbox=${bbox?.toString() ?? "null"}',
      level: bbox != null ? LogLevel.debug : LogLevel.warn,
    );
    if (bbox != null) {
      final int? resolvedPage =
          page ?? (_isImageSourceFile() ? 1 : null);
      _pdfHighlightBboxPageNotifier.value = resolvedPage;
      _pdfHighlightBboxNotifier.value = bbox;
    } else {
      _clearPdfBboxHighlight();
    }
  }

  void _clearPdfBboxHighlight() {
    _pdfHighlightBboxPageNotifier.value = null;
    _pdfHighlightBboxNotifier.value = null;
  }

  void _followSegmentPdfPage(int index) {
    final int? page = _readPdfPageNumber(_allSegmentsMetadata[index]);
    if (page != null && page >= 1) {
      _requestPdfPreviewJump(page);
    }
    _requestPdfBboxHighlight(index);
  }

  void _setAutoFollowSegmentPdfPage(bool enabled) {
    if (_autoFollowSegmentPdfPageNotifier.value == enabled) {
      return;
    }
    _autoFollowSegmentPdfPageNotifier.value = enabled;
    if (enabled && highlightedIndex != null) {
      _followSegmentPdfPage(highlightedIndex!);
    }
  }

  void _setShowSelectedSegmentMarker(bool enabled) {
    if (_showSelectedSegmentMarkerNotifier.value == enabled) {
      return;
    }
    _showSelectedSegmentMarkerNotifier.value = enabled;
    if (!enabled) {
      _clearPdfBboxHighlight();
      return;
    }
    if (highlightedIndex != null) {
      _requestPdfBboxHighlight(highlightedIndex!);
    }
  }

  Future<void> _handlePdfPageFilterChanged(
    Set<int> pages, {
    int? jumpToPage,
  }) async {
    if (_isRefreshingForFilter) {
      return;
    }
    _setSelectedPdfPageNumbers(pages);
    _clearFilteredIndicesCache();
    if (jumpToPage != null) {
      _requestPdfPreviewJump(jumpToPage);
    }
    _isRefreshingForFilter = true;
    try {
      await _segmentsPaginationController?.loadFirstPage();
      if (mounted) {
        _segmentUiRevisionNotifier.value++;
        setState(() {});
      }
    } finally {
      if (mounted) {
        _isRefreshingForFilter = false;
      }
    }
  }

  Set<int> _getFilteredSelectableSegmentIndices() {
    return _getFilteredSegmentIndices()
        .where(
          (int index) => _allSegmentsMetadata[index]?['is_image'] != true,
        )
        .toSet();
  }

  /// Clear cached filtered indices (call when filters, segments count, or metadata changes)
  void _clearFilteredIndicesCache() {
    _cachedFilteredIndices = null;
    _cachedFilteredIndicesFilters = null;
    _cachedFilteredIndicesTotalCount = null;
    _cachedFilteredIndicesPdfPages = null;
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

    // rebuild mode with active filters: paginate filtered indices
    final bool hasActivePdfPageFilter = _selectedPdfPageNumbers.isNotEmpty &&
        !_isAllPdfPagesSelected();
    if (_filterMode == 'rebuild' &&
        (_selectedExclusionFilters.isNotEmpty || hasActivePdfPageFilter)) {
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
            ..._layoutBlockMetadataFieldsFromApi(segment),
            ...segmentClassificationFieldsFromApi(segment),
            ..._pdfFontSizeMetadataFields(segment),
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
              ...segmentClassificationFieldsFromApi(segment),
              ..._layoutBlockMetadataFieldsFromApi(segment),
              ..._pdfFontSizeMetadataFields(segment),
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
          int layoutIndicesCount = 0;
          int layoutBboxCount = 0;
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
            final Map<String, dynamic> layoutFields =
                _layoutBlockMetadataFieldsFromApi(segment);
            if (layoutFields.containsKey('layout_block_indices')) {
              layoutIndicesCount++;
            }
            if (layoutFields.containsKey('layout_block_bbox')) {
              layoutBboxCount++;
            }
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
              ...layoutFields,
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
          _translationResultLog(
            '[LAYOUT-BBOX] Metadata from API: with_indices=$layoutIndicesCount '
            'with_bbox=$layoutBboxCount / ${segments.length}',
            level: layoutBboxCount < layoutIndicesCount
                ? LogLevel.warn
                : LogLevel.info,
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

    // In merged/clean view, scrolling is handled by TranslationMergedPreviewPanel
    // via its own Scrollable.ensureVisible — skip the PaginatedScrollManager path.
    if (_isMergedView) return;

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

  double? _parseOptionalDouble(dynamic raw) {
    if (raw is num) {
      return raw.toDouble();
    }
    if (raw is String) {
      return double.tryParse(raw);
    }
    return null;
  }

  /// Layout block indices/bbox/page from translation-segments API (PDF/image revision).
  Map<String, dynamic> _layoutBlockMetadataFieldsFromApi(
    Map<dynamic, dynamic> segment,
  ) {
    final List<List<double>>? layoutBlockBbox =
        _parseLayoutBlockBbox(segment['layout_block_bbox']);
    List<int>? layoutBlockIndices;
    final dynamic indicesRaw = segment['layout_block_indices'];
    if (indicesRaw is List) {
      final List<int> parsed = <int>[];
      for (final dynamic entry in indicesRaw) {
        if (entry is int) {
          parsed.add(entry);
        } else if (entry is num) {
          parsed.add(entry.toInt());
        } else if (entry is String) {
          final int? value = int.tryParse(entry);
          if (value != null) {
            parsed.add(value);
          }
        }
      }
      if (parsed.isNotEmpty) {
        layoutBlockIndices = parsed;
      }
    }
    final int? segmentIndex = segment['segment_index'] is int
        ? segment['segment_index'] as int
        : int.tryParse('${segment['segment_index']}');
    if (layoutBlockIndices != null && layoutBlockBbox == null) {
      _translationResultLog(
        '[LAYOUT-BBOX] segment=$segmentIndex indices=$layoutBlockIndices '
        'api_layout_block_bbox=${segment['layout_block_bbox']} '
        'parse_failed_or_empty',
        level: LogLevel.warn,
      );
    }
    return <String, dynamic>{
      if (layoutBlockIndices != null)
        'layout_block_indices': layoutBlockIndices,
      if (layoutBlockBbox != null) 'layout_block_bbox': layoutBlockBbox,
      if (segment.containsKey('layout_block_indices_resolution'))
        'layout_block_indices_resolution':
            segment['layout_block_indices_resolution'],
      if (segment.containsKey('pdf_page_number'))
        'pdf_page_number': _parseOptionalInt(segment['pdf_page_number']),
    };
  }

  Map<String, dynamic> _pdfFontSizeMetadataFields(Map<String, dynamic> segment) {
    return <String, dynamic>{
      if (segment.containsKey('font_size_pt'))
        'font_size_pt': _parseOptionalDouble(segment['font_size_pt']),
      if (segment.containsKey('computed_font_size_pt'))
        'computed_font_size_pt':
            _parseOptionalDouble(segment['computed_font_size_pt']),
      if (segment.containsKey('overlay_render_font_size_pt'))
        'overlay_render_font_size_pt':
            _parseOptionalDouble(segment['overlay_render_font_size_pt']),
      if (segment.containsKey('overlay_estimated_font_size_pt'))
        'overlay_estimated_font_size_pt':
            _parseOptionalDouble(segment['overlay_estimated_font_size_pt']),
      if (segment.containsKey('font_size_source'))
        'font_size_source': segment['font_size_source'],
      if (segment.containsKey('font_weight'))
        'font_weight': segment['font_weight'],
      if (segment.containsKey('computed_font_weight'))
        'computed_font_weight': segment['computed_font_weight'],
      if (segment.containsKey('font_weight_source'))
        'font_weight_source': segment['font_weight_source'],
      if (segment.containsKey('font_style'))
        'font_style': segment['font_style'],
      if (segment.containsKey('computed_font_style'))
        'computed_font_style': segment['computed_font_style'],
      if (segment.containsKey('font_style_source'))
        'font_style_source': segment['font_style_source'],
      if (segment.containsKey('leading_em'))
        'leading_em': _parseOptionalDouble(segment['leading_em']),
      if (segment.containsKey('computed_leading_em'))
        'computed_leading_em':
            _parseOptionalDouble(segment['computed_leading_em']),
      if (segment.containsKey('leading_em_source'))
        'leading_em_source': segment['leading_em_source'],
    };
  }

  int? _parseOptionalInt(dynamic raw) {
    if (raw is int) {
      return raw;
    }
    if (raw is num) {
      return raw.toInt();
    }
    if (raw is String) {
      return int.tryParse(raw);
    }
    return null;
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
          // Keep merged paragraphs in sync so clean mode reflects the edit.
          if (index < _mergedTargetParagraphs.length) {
            _mergedTargetParagraphs[index] = newText;
          }
        });

        // CRITICAL: Force refresh pagination controller to ensure it uses updated metadata
        // This ensures the UI immediately reflects the saved changes
        if (_segmentsPaginationController != null) {
          await _segmentsPaginationController!.refresh();
        }
        if (_shouldRefreshOverlayPreviewRevision) {
          _schedulePdfPreviewRevisionChanged(dirtySegmentIndex: index);
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
          // Keep merged paragraphs in sync so clean mode reflects the undo.
          if (operation.segmentIndex < _mergedTargetParagraphs.length) {
            _mergedTargetParagraphs[operation.segmentIndex] = operation.oldText;
          }
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
          // Keep merged paragraphs in sync so clean mode reflects the redo.
          if (operation.segmentIndex < _mergedTargetParagraphs.length) {
            _mergedTargetParagraphs[operation.segmentIndex] = operation.newText;
          }
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
          // Keep merged paragraphs in sync so clean mode reflects the undo.
          if (segmentIndex < _mergedTargetParagraphs.length) {
            _mergedTargetParagraphs[segmentIndex] = previousText;
          }
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
          // Keep merged paragraphs in sync so clean mode reflects the redo.
          if (segmentIndex < _mergedTargetParagraphs.length) {
            _mergedTargetParagraphs[segmentIndex] = nextText;
          }
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
      final Map<String, dynamic> batchResult =
          await svc.excludeSegmentsBatch(_apiTaskId(), matchingIndices);
      final List<dynamic> segmentsRaw =
          batchResult['segments'] as List<dynamic>? ?? <dynamic>[];

      // Update target text and metadata for all segments (from backend response)
      for (final dynamic segRaw in segmentsRaw) {
        if (segRaw is! Map) continue;
        final Map<String, dynamic> segment = segRaw.cast<String, dynamic>();
        final int idx = segment['segment_index'] as int? ?? -1;
        if (idx < 0) continue;
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
        if (_shouldRefreshOverlayPreviewRevision) {
          _schedulePdfPreviewRevisionChanged(dirtySegmentIndex: index);
        }
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
      final Map<String, dynamic> batchResult =
          await svc.unexcludeSegmentsBatch(_apiTaskId(), matchingIndices);
      final List<dynamic> segmentsRaw =
          batchResult['segments'] as List<dynamic>? ?? <dynamic>[];
      final Set<int> updatedIndices = <int>{};

      // Update state and metadata for all segments returned by backend
      for (final dynamic segRaw in segmentsRaw) {
        if (segRaw is! Map) continue;
        final Map<String, dynamic> segment = segRaw.cast<String, dynamic>();
        final int idx = segment['segment_index'] as int? ?? -1;
        if (idx < 0) continue;
        updatedIndices.add(idx);

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
      }

      // Fallback for indices not returned in batch response
      for (final int idx in matchingIndices) {
        if (updatedIndices.contains(idx)) continue;
        if (_allSegmentsMetadata.containsKey(idx)) {
          _allSegmentsMetadata[idx] = <String, dynamic>{
            ..._allSegmentsMetadata[idx]!,
            'is_excluded': false,
            'exclusion_reason': null,
          };
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

    // In merged/clean view, scrolling is handled by TranslationMergedPreviewPanel
    // via GlobalKey + Scrollable.ensureVisible — skip PaginatedScrollManager logic.
    if (_isMergedView) return;

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

  String _pdfRevisionLaunchScopeKey() =>
      widget.flowId ?? _apiTaskId();

  Widget _buildContent({bool isFullscreenView = false}) {
    ref.listen<int>(
      pdfRevisionLaunchProvider(_pdfRevisionLaunchScopeKey()),
      (int? previous, int next) {
        if (next > 0 && previous != next && mounted) {
          if (_isImageSourceFile()) {
            unawaited(_onEnterImageRevisionMode());
          } else {
            unawaited(_onEnterPdfRevisionMode());
          }
        }
      },
    );

    // Get translation state if flowId is available
    final dynamic translationState = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!))
        : null;
    final dynamic translationNotifier = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!).notifier)
        : null;

    // Merge widget + state downloads; synthesize PDF on-demand URL when needed.
    final Map<String, String>? effectiveDownloads =
        _resolveEffectiveDownloads(translationState);

    // Refresh status when downloads are missing or PDF link absent after completion.
    if (translationNotifier != null &&
        _shouldFetchOnDemandDownloads(effectiveDownloads, translationState)) {
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
                onViewPreview: _onViewPreview,
                onEnterPdfRevisionMode: (_isPdfSourceFile() ||
                        _isImageSourceFile()) &&
                    _translationLooksComplete(translationState)
                    ? () {
                        if (_isImageSourceFile()) {
                          unawaited(_onEnterImageRevisionMode());
                        } else {
                          unawaited(_onEnterPdfRevisionMode());
                        }
                      }
                    : null,
                onShowDownload: _showDownloadDialog,
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
                  final int? savedIndex = highlightedIndex;
                  setState(() {
                    _isMergedView = !_isMergedView;
                  });
                  if (savedIndex != null) {
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (!mounted) return;
                      _highlightParagraph(savedIndex);
                    });
                  }
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

  void _flushPdfPreviewRevisionChanged({bool refreshSegmentPanel = true}) {
    _pdfPreviewRevisionDebounceTimer?.cancel();
    final Set<int> dirtySegments =
        Set<int>.from(_pendingDirtySegmentIndices);
    _pendingDirtySegmentIndices.clear();
    // Update dirty segments before revision so preview tab reads both together.
    _pdfPreviewDirtySegmentsNotifier.value = dirtySegments;
    _pdfPreviewRevision++;
    _pdfPreviewRevisionNotifier.value = _pdfPreviewRevision;
    if (refreshSegmentPanel) {
      _segmentUiRevisionNotifier.value++;
    }
  }

  void _schedulePdfPreviewRevisionChanged({
    int? dirtySegmentIndex,
    Iterable<int>? dirtySegmentIndices,
    bool refreshSegmentPanel = true,
  }) {
    if (dirtySegmentIndex != null) {
      _pendingDirtySegmentIndices.add(dirtySegmentIndex);
    }
    if (dirtySegmentIndices != null) {
      _pendingDirtySegmentIndices.addAll(dirtySegmentIndices);
    }
    _pdfPreviewRevisionDebounceTimer?.cancel();
    _pdfPreviewRevisionDebounceTimer = Timer(_pdfPreviewRevisionDebounce, () {
      if (!mounted) {
        return;
      }
      _flushPdfPreviewRevisionChanged(refreshSegmentPanel: refreshSegmentPanel);
    });
  }

  /// Bump PDF preview cache revision and optionally refresh segment panel UI.
  void _notifyPdfPreviewRevisionChanged({
    bool refreshSegmentPanel = true,
    bool immediate = true,
    int? dirtySegmentIndex,
    Iterable<int>? dirtySegmentIndices,
  }) {
    if (dirtySegmentIndex != null) {
      _pendingDirtySegmentIndices.add(dirtySegmentIndex);
    }
    if (dirtySegmentIndices != null) {
      _pendingDirtySegmentIndices.addAll(dirtySegmentIndices);
    }
    if (immediate) {
      _flushPdfPreviewRevisionChanged(refreshSegmentPanel: refreshSegmentPanel);
      return;
    }
    _schedulePdfPreviewRevisionChanged(refreshSegmentPanel: refreshSegmentPanel);
  }

  /// Refresh segment panel and PDF preview once after a batch typography update.
  Future<void> _finalizePdfTypographyBatchRefresh(
    int segmentCount, {
    Iterable<int>? dirtySegmentIndices,
  }) async {
    if (!mounted) {
      return;
    }
    _notifyPdfPreviewRevisionChanged(
      dirtySegmentIndices: dirtySegmentIndices,
    );
    _translationResultLog(
      '[PDF_REVISION] Batch typography applied to $segmentCount segment(s); '
      'coalesced PDF preview refresh (rev=$_pdfPreviewRevision)',
    );
    setState(() {});
    await _segmentsPaginationController?.refresh();
  }

  /// Reload computed PDF typography from backend overlay/Typst dry-run enrichment.
  Future<void> _refreshPdfTypographyMetadata({bool forceRefresh = false}) async {
    final bool imageLayoutTask = _isImageSourceFile();
    if (!forceRefresh &&
        !imageLayoutTask &&
        _allSegmentsMetadata.isNotEmpty) {
      final bool allResolved = _allSegmentsMetadata.values.every(
        (Map<String, dynamic> metadata) =>
            metadata['overlay_render_font_size_pt'] != null ||
            metadata['computed_font_size_pt'] != null ||
            (metadata['font_size_source'] == 'user' &&
                metadata['font_size_pt'] != null),
      );
      if (allResolved) {
        _translationResultLog(
          '[PDF_REVISION] Skipping typography refresh; all segments resolved',
        );
        return;
      }
    }

    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> segmentsData =
          await svc.getTranslationSegments(
        _apiTaskId(),
        forceRefresh: forceRefresh,
      );
      final List<dynamic>? segments =
          segmentsData['segments'] as List<dynamic>?;
      if (segments == null) {
        return;
      }

      int withIndices = 0;
      int withBbox = 0;
      for (final dynamic raw in segments) {
        if (raw is! Map) {
          continue;
        }
        final Map<String, dynamic> segment =
            Map<String, dynamic>.from(raw);
        final int index = segment['segment_index'] as int? ?? 0;
        final Map<String, dynamic> fontFields =
            _pdfFontSizeMetadataFields(segment);
        final Map<String, dynamic> layoutFields =
            _layoutBlockMetadataFieldsFromApi(segment);
        if (layoutFields.containsKey('layout_block_indices')) {
          withIndices++;
        }
        if (layoutFields.containsKey('layout_block_bbox')) {
          withBbox++;
        }
        if (_allSegmentsMetadata.containsKey(index)) {
          _allSegmentsMetadata[index] = <String, dynamic>{
            ..._allSegmentsMetadata[index]!,
            ...layoutFields,
            ...fontFields,
          };
        } else {
          _allSegmentsMetadata[index] = <String, dynamic>{
            ...layoutFields,
            ...fontFields,
          };
        }
      }

      _translationResultLog(
        '[LAYOUT-BBOX] Typography refresh merged: with_indices=$withIndices '
        'with_bbox=$withBbox / ${segments.length} (forceRefresh=$forceRefresh)',
        level: withBbox < withIndices ? LogLevel.warn : LogLevel.info,
      );

      _clearFilteredIndicesCache();
      if (mounted) {
        _segmentUiRevisionNotifier.value++;
        setState(() {});
        unawaited(_segmentsPaginationController?.refresh());
      }
    } catch (e) {
      _translationResultLog(
        '[PDF_REVISION] Failed to refresh computed typography: $e',
        level: LogLevel.warn,
      );
    }
  }

  void _ensurePdfRevisionKeys(int count) {
    while (_pdfRevisionSourceItemKeys.length < count) {
      final int index = _pdfRevisionSourceItemKeys.length;
      _pdfRevisionSourceItemKeys[index] = GlobalKey();
    }
    while (_pdfRevisionTargetItemKeys.length < count) {
      final int index = _pdfRevisionTargetItemKeys.length;
      _pdfRevisionTargetItemKeys[index] = GlobalKey();
    }
    for (int i = 0; i < count; i++) {
      _pdfRevisionSegmentPairKeys.putIfAbsent(i, GlobalKey.new);
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
        highlightedIndexNotifier: _highlightedIndexNotifier,
        onHighlightParagraph: _highlightParagraph,
        onEdit: _handleSegmentEdit,
        onEditingStarted: _onEditingStarted,
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
      onFiltersChanged: _handleFiltersChanged,
      onFormulaFix: _handleFormulaFixForSegment,
      showPdfFontSize: false,
      onFontSizeChanged: null,
    );
  }

  Widget _buildPdfRevisionSegmentPanel({
    required Set<int> selectedSegmentIndices,
    ValueListenable<Set<int>>? selectedSegmentIndicesListenable,
    required void Function(int index, bool selected) onSegmentSelectionToggle,
    Set<int> Function()? getFilteredSelectableSegmentIndices,
    required void Function(Set<int> indices) onBulkSelectAll,
    required void Function(Set<int> indices) onBulkInvertSelection,
    Future<void> Function()? onBatchFontApply,
    Future<void> Function(double delta)? onBatchFontSizeStep,
    ScrollController? segmentScrollController,
    bool showSegmentScrollbar = true,
    bool enablePdfPageFilter = true,
  }) {
    // PDF revision always uses the segment list panel, even when the main tab
    // is in merged/clean reading view (queue "阅读编辑模式" / view_mode=clean).

    final dynamic translationState = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!))
        : null;
    final Map<String, int>? tokenUsage =
        _tokenUsage ?? translationState?.tokenUsage;
    final String resolvedWorkflowType = widget.workflowType ??
        (widget.flowId != null
            ? ref
                .read(translationQuickSettingsProviderFamily(widget.flowId!))
                .workflowType
            : ref.read(translationQuickSettingsProvider).workflowType);
    final bool isDocxWorkflow = resolvedWorkflowType == 'docx';
    _ensurePdfRevisionKeys(_totalSegmentsCount);

    return TranslationComparisonPanel(
      key: const ValueKey('pdf_revision_segment_panel'),
      taskId: _apiTaskId(),
      isLoading: _isLoading,
      loadingError: _loadingError,
      isConvertOnly: true,
      pdfRevisionMode: true,
      batchSelectionEnabled: true,
      selectedSegmentIndices: selectedSegmentIndices,
      selectedSegmentIndicesListenable: selectedSegmentIndicesListenable,
      onSegmentSelectionToggle: (int index, bool selected) {
        onSegmentSelectionToggle(index, selected);
        if (selected && _autoFollowSegmentPdfPageNotifier.value) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) {
              return;
            }
            _followSegmentPdfPage(index);
          });
        }
      },
      onBulkSelectAll: onBulkSelectAll,
      onBulkInvertSelection: onBulkInvertSelection,
      onBatchFontApply: onBatchFontApply,
      onBatchFontSizeStep: onBatchFontSizeStep,
      getFilteredSelectableSegmentIndices: getFilteredSelectableSegmentIndices,
      exclusionFiltersListenable: _selectedExclusionFiltersNotifier,
      pdfPageFilterListenable:
          enablePdfPageFilter ? _selectedPdfPageNumbersNotifier : null,
      onPdfPageFilterChanged:
          enablePdfPageFilter ? _handlePdfPageFilterChanged : null,
      sourceParagraphs: _sourceParagraphs,
      targetParagraphs: _targetParagraphs,
      highlightedIndexNotifier: _highlightedIndexNotifier,
      scrollController:
          segmentScrollController ?? _pdfRevisionScrollController,
      segmentsPaginationController: _segmentsPaginationController,
      totalSegmentsCount: _totalSegmentsCount,
      segmentPairKeys: _pdfRevisionSegmentPairKeys,
      sourceItemKeys: _pdfRevisionSourceItemKeys,
      targetItemKeys: _pdfRevisionTargetItemKeys,
      modifiedSegments: _modifiedSegments,
      imageDataMap: _imageDataMap,
      segmentMetadata: _allSegmentsMetadata,
      retranslatingSegments: _retranslatingSegments,
      heightCache: null,
      onHighlightParagraph: (int index) {
        _highlightParagraph(index);
        _requestPdfBboxHighlight(index);
        if (_autoFollowSegmentPdfPageNotifier.value) {
          _followSegmentPdfPage(index);
        }
      },
      onSegmentEdit: _handleSegmentEdit,
      onEditingStarted: _onEditingStarted,
      onRetrySegment: _handleRetrySegment,
      onMarkForRetry: _handleMarkForRetry,
      onUnmarkForRetry: _handleUnmarkForRetry,
      onExcludeSegment: _handleExcludeSegment,
      onUnexcludeSegment: _handleUnexcludeSegment,
      onClearSegment: isDocxWorkflow ? null : _handleClearSegment,
      onUnclearSegment: isDocxWorkflow ? null : _handleUnclearSegment,
      onUndo: _handleUndo,
      onRedo: _handleRedo,
      onExclusionUpdated: _handleExclusionUpdated,
      translationState: translationState,
      tokenUsage: tokenUsage,
      selectedExclusionFilters: _selectedExclusionFilters,
      onFiltersChanged: _handleFiltersChanged,
      onFormulaFix: _handleFormulaFixForSegment,
      showPdfFontSize: true,
      onFontSizeChanged: _handleFontSizeChanged,
      showSegmentScrollbar: showSegmentScrollbar,
    );
  }

  double _effectiveSegmentFontSizePt(Map<String, dynamic> metadata) {
    return effectivePdfSegmentFontSizePtFromMetadata(metadata);
  }

  Future<void> _handleBatchFontSizeStep(
    Set<int> indices,
    double delta,
  ) async {
    if (indices.isEmpty || delta == 0) {
      return;
    }
    final List<int> sorted = indices.toList()..sort();
    final List<int> changedIndices = <int>[];
    _pdfTypographyBatchDepth++;
    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> response =
          await svc.batchUpdateTranslationSegmentTypography(
        _apiTaskId(),
        sorted,
        fontSizeDeltaPt: delta,
      );
      final List<dynamic>? changedRaw =
          response['changed_indices'] as List<dynamic>?;
      if (changedRaw != null) {
        changedIndices.addAll(
          changedRaw.map((dynamic v) => (v as num).toInt()),
        );
      }

      final List<dynamic>? segments =
          response['segments'] as List<dynamic>?;
      if (segments != null) {
        for (final dynamic raw in segments) {
          if (raw is! Map) {
            continue;
          }
          final Map<String, dynamic> segment = Map<String, dynamic>.from(raw);
          final int? index = segment['segment_index'] as int?;
          if (index == null || !changedIndices.contains(index)) {
            continue;
          }
          final Map<String, dynamic> computedFields =
              _pdfFontSizeMetadataFields(segment);
          final double appliedPt = computedFields['font_size_pt'] is num
              ? (computedFields['font_size_pt'] as num).toDouble()
              : _effectiveSegmentFontSizePt(
                  _allSegmentsMetadata[index] ?? <String, dynamic>{},
                );
          _applyLocalPdfTypographyMetadata(
            index,
            fontSizePt: appliedPt,
            scope: SegmentPdfTypographyDialogMode.fontOnly,
          );
          if (_allSegmentsMetadata.containsKey(index)) {
            _allSegmentsMetadata[index] = <String, dynamic>{
              ..._allSegmentsMetadata[index]!,
              ...computedFields,
              'font_size_pt': appliedPt,
              'font_size_source': 'user',
            };
          } else {
            _allSegmentsMetadata[index] = <String, dynamic>{
              ...computedFields,
              'font_size_pt': appliedPt,
              'font_size_source': 'user',
            };
          }
        }
      }

      final List<dynamic>? failedRaw =
          response['failed_indices'] as List<dynamic>?;
      if (failedRaw != null && failedRaw.isNotEmpty && mounted) {
        MessageService.showError(
          context,
          'Some segments failed to update font size: $failedRaw',
        );
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to update segment font size: $e',
        );
      }
    } finally {
      _pdfTypographyBatchDepth--;
      if (_pdfTypographyBatchDepth <= 0) {
        _pdfTypographyBatchDepth = 0;
        if (changedIndices.isNotEmpty) {
          await _finalizePdfTypographyBatchRefresh(
            changedIndices.length,
            dirtySegmentIndices: changedIndices,
          );
        }
      }
    }
  }

  Future<void> _handleBatchPdfTypography(
    Set<int> indices,
    SegmentPdfTypographyDialogMode mode,
  ) async {
    if (indices.isEmpty) {
      return;
    }
    final List<int> sorted = indices.toList()..sort();
    final int firstIndex = sorted.first;
    final Map<String, dynamic> metadata =
        _allSegmentsMetadata[firstIndex] ?? <String, dynamic>{};
    final String previewText = metadata['target_text'] as String? ??
        (firstIndex < _targetParagraphs.length
            ? _targetParagraphs[firstIndex]
            : '');

    bool hasUserOverride;
    switch (mode) {
      case SegmentPdfTypographyDialogMode.fontOnly:
        hasUserOverride =
            (metadata['font_size_source'] == 'user' &&
                    metadata['font_size_pt'] != null) ||
                metadata['font_weight_source'] == 'user' ||
                metadata['font_style_source'] == 'user';
      case SegmentPdfTypographyDialogMode.leadingOnly:
        hasUserOverride = metadata['leading_em_source'] == 'user';
      case SegmentPdfTypographyDialogMode.all:
        hasUserOverride =
            (metadata['font_size_source'] == 'user' &&
                    metadata['font_size_pt'] != null) ||
                metadata['font_weight_source'] == 'user' ||
                metadata['font_style_source'] == 'user' ||
                metadata['leading_em_source'] == 'user';
    }

    double readDouble(dynamic raw, double fallback) {
      if (raw is num) {
        return raw.toDouble();
      }
      if (raw is String) {
        return double.tryParse(raw) ?? fallback;
      }
      return fallback;
    }

    String readString(dynamic raw, String fallback) {
      return raw is String ? raw : fallback;
    }

    final double initialSize =
        effectivePdfSegmentFontSizePtFromMetadata(metadata);
    final String initialWeight = metadata['font_weight_source'] == 'user' &&
            metadata['font_weight'] != null
        ? readString(metadata['font_weight'], 'regular')
        : readString(metadata['computed_font_weight'],
            readString(metadata['font_weight'], 'regular'));
    final String initialStyle = metadata['font_style_source'] == 'user' &&
            metadata['font_style'] != null
        ? readString(metadata['font_style'], 'normal')
        : readString(metadata['computed_font_style'],
            readString(metadata['font_style'], 'normal'));
    final double initialLeading = metadata['leading_em_source'] == 'user' &&
            metadata['leading_em'] != null
        ? readDouble(metadata['leading_em'], kPdfLeadingEmDefault)
        : readDouble(metadata['computed_leading_em'],
            readDouble(metadata['leading_em'], kPdfLeadingEmDefault));

    final SegmentPdfTypographyResult? result =
        await showSegmentPdfTypographyDialog(
      context: context,
      previewText: previewText,
      hasUserOverride: hasUserOverride,
      initialFontSizePt: initialSize,
      initialFontWeight: initialWeight,
      initialFontStyle: initialStyle,
      initialLeadingEm: snapPdfLeadingEm(initialLeading),
      mode: mode,
    );
    if (!mounted || result == null) {
      return;
    }

    _pdfTypographyBatchDepth++;
    try {
      final bool resetAll =
          result.reset && result.mode == SegmentPdfTypographyDialogMode.all;
      final bool resetFont = result.reset &&
          (result.mode == SegmentPdfTypographyDialogMode.fontOnly ||
              result.mode == SegmentPdfTypographyDialogMode.all);
      final bool resetLeading = result.reset &&
          (result.mode == SegmentPdfTypographyDialogMode.leadingOnly ||
              result.mode == SegmentPdfTypographyDialogMode.all);
      final bool applyFont =
          result.mode != SegmentPdfTypographyDialogMode.leadingOnly &&
              !result.reset;
      final bool applyLeading =
          result.mode != SegmentPdfTypographyDialogMode.fontOnly && !result.reset;

      final TranslationService svc = TranslationService();
      await svc.batchUpdateTranslationSegmentTypography(
        _apiTaskId(),
        sorted,
        fontSizePt: applyFont ? result.fontSizePt : null,
        fontSizeReset: resetFont && !resetAll,
        fontWeight: applyFont ? result.fontWeight : null,
        fontWeightReset: resetFont && !resetAll,
        fontStyle: applyFont ? result.fontStyle : null,
        fontStyleReset: resetFont && !resetAll,
        leadingEm: applyLeading ? result.leadingEm : null,
        leadingEmReset: resetLeading && !resetAll,
        pdfFontReset: resetAll,
      );

      for (final int index in sorted) {
        _applyLocalPdfTypographyMetadata(
          index,
          fontSizePt: applyFont ? result.fontSizePt : null,
          fontWeight: applyFont ? result.fontWeight : null,
          fontStyle: applyFont ? result.fontStyle : null,
          leadingEm: applyLeading ? result.leadingEm : null,
          reset: result.reset,
          scope: result.mode,
        );
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to update PDF typography: $e');
      }
    } finally {
      _pdfTypographyBatchDepth--;
      if (_pdfTypographyBatchDepth <= 0) {
        _pdfTypographyBatchDepth = 0;
        await _finalizePdfTypographyBatchRefresh(
          sorted.length,
          dirtySegmentIndices: sorted,
        );
      }
    }
  }

  void _applyLocalPdfTypographyMetadata(
    int index, {
    double? fontSizePt,
    String? fontWeight,
    String? fontStyle,
    double? leadingEm,
    bool reset = false,
    SegmentPdfTypographyDialogMode scope = SegmentPdfTypographyDialogMode.all,
  }) {
    final bool resetAll =
        reset && scope == SegmentPdfTypographyDialogMode.all;
    final bool resetFont = reset &&
        (scope == SegmentPdfTypographyDialogMode.fontOnly ||
            scope == SegmentPdfTypographyDialogMode.all);
    final bool resetLeading = reset &&
        (scope == SegmentPdfTypographyDialogMode.leadingOnly ||
            scope == SegmentPdfTypographyDialogMode.all);
    final bool applyFont =
        scope != SegmentPdfTypographyDialogMode.leadingOnly && !reset;
    final bool applyLeading =
        scope != SegmentPdfTypographyDialogMode.fontOnly && !reset;

    final Map<String, dynamic> typographyPatch = resetAll
        ? <String, dynamic>{
            'font_size_pt': null,
            'font_size_source': 'auto',
            'font_weight': null,
            'font_weight_source': 'auto',
            'font_style': null,
            'font_style_source': 'auto',
            'leading_em': null,
            'leading_em_source': 'auto',
          }
        : resetFont
            ? <String, dynamic>{
                'font_size_pt': null,
                'font_size_source': 'auto',
                'font_weight': null,
                'font_weight_source': 'auto',
                'font_style': null,
                'font_style_source': 'auto',
              }
            : resetLeading
                ? <String, dynamic>{
                    'leading_em': null,
                    'leading_em_source': 'auto',
                  }
                : <String, dynamic>{
                    if (applyFont && fontSizePt != null) 'font_size_pt': fontSizePt,
                    if (applyFont && fontSizePt != null)
                      'font_size_source': 'user',
                    if (applyFont && fontWeight != null) 'font_weight': fontWeight,
                    if (applyFont && fontWeight != null)
                      'font_weight_source': 'user',
                    if (applyFont && fontStyle != null) 'font_style': fontStyle,
                    if (applyFont && fontStyle != null)
                      'font_style_source': 'user',
                    if (applyLeading && leadingEm != null) 'leading_em': leadingEm,
                    if (applyLeading && leadingEm != null)
                      'leading_em_source': 'user',
                  };

    if (_allSegmentsMetadata.containsKey(index)) {
      _allSegmentsMetadata[index] = <String, dynamic>{
        ..._allSegmentsMetadata[index]!,
        ...typographyPatch,
      };
    } else {
      _allSegmentsMetadata[index] = typographyPatch;
    }
  }

  Future<void> _handleFontSizeChanged(
    int index, {
    double? fontSizePt,
    String? fontWeight,
    String? fontStyle,
    double? leadingEm,
    bool reset = false,
    SegmentPdfTypographyDialogMode scope = SegmentPdfTypographyDialogMode.all,
  }) async {
    final bool resetAll =
        reset && scope == SegmentPdfTypographyDialogMode.all;
    final bool resetFont = reset &&
        (scope == SegmentPdfTypographyDialogMode.fontOnly ||
            scope == SegmentPdfTypographyDialogMode.all);
    final bool resetLeading = reset &&
        (scope == SegmentPdfTypographyDialogMode.leadingOnly ||
            scope == SegmentPdfTypographyDialogMode.all);
    final bool applyFont =
        scope != SegmentPdfTypographyDialogMode.leadingOnly && !reset;
    final bool applyLeading =
        scope != SegmentPdfTypographyDialogMode.fontOnly && !reset;

    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> response =
          await svc.updateTranslationSegment(
        _apiTaskId(),
        index,
        fontSizePt: applyFont ? fontSizePt : null,
        fontSizeReset: resetFont && !resetAll,
        fontWeight: applyFont ? fontWeight : null,
        fontWeightReset: resetFont && !resetAll,
        fontStyle: applyFont ? fontStyle : null,
        fontStyleReset: resetFont && !resetAll,
        leadingEm: applyLeading ? leadingEm : null,
        leadingEmReset: resetLeading && !resetAll,
        pdfFontReset: resetAll,
      );
      final Map<String, dynamic>? updatedSegment =
          response['segment'] is Map
              ? Map<String, dynamic>.from(
                  response['segment'] as Map<dynamic, dynamic>,
                )
              : null;
      final Map<String, dynamic> computedFields = updatedSegment != null
          ? _pdfFontSizeMetadataFields(updatedSegment)
          : <String, dynamic>{};

      _applyLocalPdfTypographyMetadata(
        index,
        fontSizePt: applyFont ? fontSizePt : null,
        fontWeight: applyFont ? fontWeight : null,
        fontStyle: applyFont ? fontStyle : null,
        leadingEm: applyLeading ? leadingEm : null,
        reset: reset,
        scope: scope,
      );
      if (_allSegmentsMetadata.containsKey(index)) {
        _allSegmentsMetadata[index] = <String, dynamic>{
          ..._allSegmentsMetadata[index]!,
          ...computedFields,
        };
      } else if (computedFields.isNotEmpty) {
        _allSegmentsMetadata[index] = computedFields;
      }

      if (mounted && _pdfTypographyBatchDepth == 0 &&
          _shouldRefreshOverlayPreviewRevision) {
        _schedulePdfPreviewRevisionChanged(dirtySegmentIndex: index);
        setState(() {});
        await _segmentsPaginationController?.refresh();
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to update PDF typography: $e');
      }
    }
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

  String _resolvedWorkflowType() {
    return widget.workflowType ??
        (widget.flowId != null
            ? ref
                .read(translationQuickSettingsProviderFamily(widget.flowId!))
                .workflowType
            : ref.read(translationQuickSettingsProvider).workflowType);
  }

  PreviewTabsNotifier _previewTabsNotifier() {
    return widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);
  }

  void _closeTranslationPreviewTabSilently() {
    try {
      _previewTabsNotifier().closeTabByIdSilently(_kTranslationPreviewTabId);
    } catch (e) {
      _translationResultLog(
        '[REVISION_PREVIEW] Failed to close stale translation preview tab: $e',
        level: LogLevel.warn,
      );
    }
  }

  void _switchToPreviewTab(String tabId) {
    final PreviewTabsNotifier tabsNotifier = _previewTabsNotifier();
    final List<PreviewTab> currentTabs = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!)).tabs
        : ref.read(previewTabsProvider).tabs;
    final int tabIndex =
        currentTabs.indexWhere((PreviewTab t) => t.id == tabId);
    if (tabIndex >= 0) {
      tabsNotifier.switchToTab(tabIndex);
    }
  }

  /// Unified preview entry: dialog → launch selected mode.
  Future<void> _onViewPreview() async {
    final PreviewSelection? selection = await _showPreviewDialogInternal();
    if (selection != null) {
      await _launchPreview(selection);
    }
  }

  /// Open full-compare preview directly in revision mode (PDF or image overlay).
  Future<void> _onEnterRevisionPreviewMode({
    required TranslationPreviewMode baseMode,
  }) async {
    _lastPreviewMode = baseMode;
    _lastFullDocumentCompare = true;
    _lastSyncScroll = baseMode.defaultFullCompareSyncScroll;

    if (mounted) {
      setState(() {
        _loadingHtmlPreview = true;
      });
    }

    try {
      if (_totalSegmentsCount == 0 && !_isLoading) {
        await _loadTranslationContent(forceRefreshSegments: true);
      }
      if (_segmentsPaginationController != null &&
          _totalSegmentsCount > 0 &&
          _segmentsPaginationController!.items.isEmpty) {
        await _segmentsPaginationController!.loadFirstPage();
        if (mounted) {
          _segmentUiRevisionNotifier.value++;
          setState(() {});
        }
      }
      await _openFullDocumentCompareTab(
        baseMode: baseMode,
        initialLayoutMode: PdfCompareLayoutMode.compareRevision,
      );
      if (mounted && highlightedIndex != null) {
        _requestPdfBboxHighlight(highlightedIndex!);
      }
    } catch (e, stackTrace) {
      _translationResultLog(
        '[REVISION_PREVIEW] Failed to open revision mode ($baseMode): $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(context, 'Failed to open revision preview: $e');
      }
    } finally {
      if (mounted) {
        setState(() {
          _loadingHtmlPreview = false;
        });
      }
    }
  }

  Future<void> _onRevisionModeEntered(TranslationPreviewMode baseMode) async {
    if (baseMode == TranslationPreviewMode.imageOriginalLayout) {
      await _warmImageOverlayTypographyCache();
    }
    await _refreshPdfTypographyMetadata(forceRefresh: true);
  }

  Future<void> _warmImageOverlayTypographyCache() async {
    try {
      final dynamic translationState = widget.flowId != null
          ? ref.read(translationStateProviderFamily(widget.flowId!))
          : ref.read(translationStateProvider);
      final Map<String, String>? effectiveDownloads =
          _resolveEffectiveDownloads(translationState);
      if (!_hasImageDownload(effectiveDownloads)) {
        return;
      }
      final String url = _buildImageOverlayPreviewUrl(effectiveDownloads);
      final TranslationService svc = TranslationService();
      await svc.downloadFile(url);
    } catch (e) {
      _translationResultLog(
        '[PDF_REVISION] Image overlay warm-up for typography failed: $e',
        level: LogLevel.warn,
      );
    }
  }

  Future<void> _onEnterPdfRevisionMode() => _onEnterRevisionPreviewMode(
        baseMode: TranslationPreviewMode.pdfPreserve,
      );

  Future<void> _onEnterImageRevisionMode() => _onEnterRevisionPreviewMode(
        baseMode: TranslationPreviewMode.imageOriginalLayout,
      );

  bool _supportsRevisionForMode(TranslationPreviewMode baseMode) {
    if (baseMode == TranslationPreviewMode.pdfPreserve) {
      return _isPdfSourceFile();
    }
    if (baseMode == TranslationPreviewMode.imageOriginalLayout) {
      return _isImageSourceFile();
    }
    return false;
  }

  Future<PreviewSelection?> _showPreviewDialogInternal({
    TranslationPreviewMode? initialMode,
  }) async {
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : null;
    final Map<String, String>? effectiveDownloads =
        _resolveEffectiveDownloads(translationState);

    final TranslationPreviewMode resolvedMode = initialMode ??
        _lastPreviewMode ??
        defaultPreviewModeForDialog(
          isPdfFile: _isPdfSourceFile(),
          hasPdfDownload: effectiveDownloads?.containsKey('pdf') ?? false,
          resolvedWorkflowType: _resolvedWorkflowType(),
          isImageFile: _isImageSourceFile(),
          hasImageDownload: _hasImageDownload(effectiveDownloads),
        );
    final bool resolvedFullCompare = _lastFullDocumentCompare ??
        resolvedMode.defaultFullDocumentCompare;
    final bool resolvedSyncScroll = _lastSyncScroll ??
        (resolvedFullCompare ? resolvedMode.defaultFullCompareSyncScroll : false);

    return showTranslationPreviewDialog(
      context: context,
      ref: ref,
      taskId: _apiTaskId(),
      isPdfFile: _isPdfSourceFile(),
      hasPdfDownload: effectiveDownloads?.containsKey('pdf') ?? false,
      isImageFile: _isImageSourceFile(),
      hasImageDownload: _hasImageDownload(effectiveDownloads),
      resolvedWorkflowType: _resolvedWorkflowType(),
      initialMode: resolvedMode,
      initialFullDocumentCompare: resolvedFullCompare,
      initialSyncScroll: resolvedSyncScroll,
    );
  }

  Future<PreviewSelection?> _handlePreviewSettingsRequest() async {
    final PreviewSelection? selection = await _showPreviewDialogInternal(
      initialMode: _lastPreviewMode,
    );
    if (selection != null) {
      await _launchPreview(selection);
    }
    return selection;
  }

  Future<Map<String, String>?> _resolvePreviewDownloads() async {
    var downloads = widget.downloads;

    if ((downloads == null || downloads.isEmpty) && widget.flowId != null) {
      try {
        final TranslationStateFamily translationState =
            ref.read(translationStateProviderFamily(widget.flowId!));
        final Map<String, String> stateDownloads = translationState.downloads;
        if (stateDownloads.isNotEmpty) {
          downloads = stateDownloads.map(
            (String k, String v) => MapEntry(k.toString(), v.toString()),
          );
        }
      } catch (_) {}
    }

    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : null;
    downloads = _resolveEffectiveDownloads(translationState) ?? downloads;

    if (downloads == null ||
        (!downloads.containsKey('html') && !downloads.containsKey('md'))) {
      try {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> status = await svc.getStatus(_apiTaskId());
        final Map<String, dynamic>? statusDownloads =
            status['downloads'] as Map<String, dynamic>?;

        if (statusDownloads != null && statusDownloads.isNotEmpty) {
          downloads ??= <String, String>{};
          downloads.addAll(
            statusDownloads.map(
              (String k, dynamic v) => MapEntry(k.toString(), v.toString()),
            ),
          );
        }

        if (downloads != null &&
            !downloads.containsKey('html') &&
            !downloads.containsKey('md')) {
          downloads['md'] = svc.buildDownloadUrl(_apiTaskId(), 'md');
          downloads['html'] = svc.buildDownloadUrl(_apiTaskId(), 'html');
        }
      } catch (_) {}
    }

    return downloads;
  }

  Future<void> _launchPreview(PreviewSelection selection) async {
    _lastPreviewMode = selection.mode;
    _lastFullDocumentCompare = selection.fullDocumentCompare;
    _lastSyncScroll = selection.syncScroll;

    if (mounted) {
      setState(() {
        _loadingHtmlPreview = true;
      });
    }

    try {
      if (selection.fullDocumentCompare) {
        await _openFullDocumentCompareTab(baseMode: selection.mode);
        return;
      }
      switch (selection.mode) {
        case TranslationPreviewMode.html:
          await _openHtmlPreviewTab();
        case TranslationPreviewMode.pdfPreserve:
          await _openPdfPreviewTab(rendererType: 'typst_overlay');
        case TranslationPreviewMode.pdfReflow:
          await _openPdfPreviewTab(rendererType: 'pandoc');
        case TranslationPreviewMode.imageOriginalLayout:
          await _openImageOriginalLayoutPreviewTab();
      }
    } catch (e, stackTrace) {
      _translationResultLog(
        '[Preview] Failed to launch preview (${selection.mode}): $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(context, 'Failed to open preview: $e');
      }
    } finally {
      if (mounted) {
        setState(() {
          _loadingHtmlPreview = false;
        });
      }
    }
  }

  Future<void> _openHtmlPreviewTab() async {
    final Map<String, String>? downloads = await _resolvePreviewDownloads();
    if (downloads == null ||
        (!downloads.containsKey('html') && !downloads.containsKey('md'))) {
      MessageService.showWarning(
        context,
        'HTML preview not available. Try full document comparison instead.',
      );
      return;
    }

    final TranslationPreviewTabWidget previewContent =
        TranslationPreviewTabWidget(
      taskId: _apiTaskId(),
      flowId: widget.flowId,
      downloads: downloads,
      onDownload: widget.onDownload,
      onRequestPreviewSettings: _handlePreviewSettingsRequest,
    );

    final AppLocalizations l10n = AppLocalizations.of(context)!;
    const String tabId = _kTranslationPreviewTabId;
    _previewTabsNotifier().updateOrAddTab(
      PreviewTab(
        id: tabId,
        type: PreviewTabType.translationResult,
        title: l10n.translationPreviewModeHtml,
        icon: Icons.preview,
        content: previewContent,
        dataRef: <String, dynamic>{
          'taskId': _apiTaskId(),
          'downloads': downloads,
          'flowId': widget.flowId,
        },
      ),
    );
    _switchToPreviewTab(tabId);
  }

  String? _imageOverlayDownloadUrl(Map<String, String>? downloads) {
    final String? key = _originalImageDownloadKey();
    if (key == null || downloads == null) {
      return null;
    }
    return downloads[key] ?? downloads['jpeg'] ?? downloads['jpg'];
  }

  String _buildImageOverlayPreviewUrl(Map<String, String>? downloads) {
    final TranslationService svc = TranslationService();
    final String taskId = _apiTaskId();
    final String key = _originalImageDownloadKey() ?? 'png';
    String relative = _imageOverlayDownloadUrl(downloads) ??
        svc.buildDownloadUrl(taskId, key);
    final formatSettings = ref.read(formatSettingsProviderFamily(taskId));
    final Map<String, String> queryParams = buildPreviewExportQueryParams(
      formatSettings,
      isPdfWorkflow: true,
      isImageWorkflow: true,
    );
    return mergePreviewUrl(relative, queryParams);
  }

  Future<void> _openImageOriginalLayoutPreviewTab() async {
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : null;
    final Map<String, String>? effectiveDownloads =
        _resolveEffectiveDownloads(translationState);
    if (!_isImageSourceFile() || !_hasImageDownload(effectiveDownloads)) {
      MessageService.showWarning(
        context,
        'Original layout image preview not available.',
      );
      return;
    }

    final String imageUrl = _buildImageOverlayPreviewUrl(effectiveDownloads);
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    const String tabId = _kTranslationPreviewTabId;
    _previewTabsNotifier().updateOrAddTab(
      PreviewTab(
        id: tabId,
        type: PreviewTabType.translationResult,
        title: l10n.translationExportImageOriginalLayout,
        icon: Icons.image_outlined,
        content: ImageOverlayPreviewView(imageUrl: imageUrl),
        dataRef: <String, dynamic>{
          'taskId': _apiTaskId(),
          'flowId': widget.flowId,
          'downloads': effectiveDownloads,
        },
      ),
    );
    _switchToPreviewTab(tabId);
  }

  Future<void> _openFullDocumentCompareTab({
    required TranslationPreviewMode baseMode,
    PdfCompareLayoutMode initialLayoutMode =
        PdfCompareLayoutMode.comparePreview,
  }) async {
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : null;
    final Map<String, String>? effectiveDownloads =
        _resolveEffectiveDownloads(translationState);
    Map<String, String>? downloads = effectiveDownloads;
    if (baseMode == TranslationPreviewMode.html) {
      downloads = await _resolvePreviewDownloads();
    }

    if (baseMode.usesPdfPreview &&
        (!_isPdfSourceFile() || effectiveDownloads?.containsKey('pdf') != true)) {
      MessageService.showWarning(context, 'PDF comparison preview not available');
      return;
    }

    if (baseMode == TranslationPreviewMode.imageOriginalLayout &&
        (!_isImageSourceFile() ||
            !_hasImageDownload(effectiveDownloads))) {
      MessageService.showWarning(
        context,
        'Image comparison preview not available',
      );
      return;
    }

    String? translatedImageUrl;
    if (baseMode == TranslationPreviewMode.imageOriginalLayout) {
      translatedImageUrl = _buildImageOverlayPreviewUrl(effectiveDownloads);
    }

    String? translatedHtmlUrl = downloads?['html'];
    translatedHtmlUrl ??= downloads?['md'];
    if (baseMode == TranslationPreviewMode.html && translatedHtmlUrl == null) {
      MessageService.showWarning(context, 'HTML comparison preview not available');
      return;
    }

    final AppLocalizations l10n = AppLocalizations.of(context)!;
    const String tabId = _kTranslationPreviewTabId;
    _previewTabsNotifier().updateOrAddTab(
      PreviewTab(
        id: tabId,
        type: PreviewTabType.translationResult,
        title: initialLayoutMode.showsRevisionControls
            ? l10n.translationPreviewPdfRevision
            : l10n.translationPreviewFullDocumentCompare,
        icon: initialLayoutMode.showsRevisionControls
            ? Icons.edit_note
            : Icons.compare_arrows,
        content: TranslationFullComparePreviewTab(
          key: ValueKey<String>('full_compare_${_apiTaskId()}'),
          taskId: _apiTaskId(),
          baseMode: baseMode,
          isPdfSource: _isPdfSourceFile(),
          isImageSource: _isImageSourceFile(),
          isPdfWorkflow: _resolvedWorkflowType() == 'markdown_based' ||
              _isPdfSourceFile(),
          translatedPdfUrl: effectiveDownloads?['pdf'],
          translatedImageUrl: translatedImageUrl,
          pdfRenderRevision: _pdfPreviewRevision,
          pdfRenderRevisionListenable: _pdfPreviewRevisionNotifier,
          pdfPreviewDirtySegmentsListenable: _pdfPreviewDirtySegmentsNotifier,
          segmentUiRevisionListenable: _segmentUiRevisionNotifier,
          translatedHtmlUrl: translatedHtmlUrl,
          initialSyncScroll:
              _lastSyncScroll ?? baseMode.defaultFullCompareSyncScroll,
          initialLayoutMode: initialLayoutMode,
          onSyncScrollChanged: (bool enabled) {
            _lastSyncScroll = enabled;
          },
          onRequestPreviewSettings: _handlePreviewSettingsRequest,
          onDownload: widget.onDownload,
          onShowDownload: _showDownloadDialog,
          segmentScrollController: _supportsRevisionForMode(baseMode)
              ? _pdfRevisionScrollController
              : null,
          pdfRevisionSegmentPanelBuilder: _supportsRevisionForMode(baseMode)
              ? ({
                  required Set<int> selectedSegmentIndices,
                  ValueListenable<Set<int>>? selectedSegmentIndicesListenable,
                  required void Function(int index, bool selected)
                      onSegmentSelectionToggle,
                  Set<int> Function()? getFilteredSelectableSegmentIndices,
                  required void Function(Set<int> indices) onBulkSelectAll,
                  required void Function(Set<int> indices) onBulkInvertSelection,
                  Future<void> Function()? onBatchFontApply,
                  Future<void> Function(double delta)? onBatchFontSizeStep,
                  ScrollController? segmentScrollController,
                  bool showSegmentScrollbar = true,
                }) =>
                  _buildPdfRevisionSegmentPanel(
                    selectedSegmentIndices: selectedSegmentIndices,
                    selectedSegmentIndicesListenable:
                        selectedSegmentIndicesListenable,
                    onSegmentSelectionToggle: onSegmentSelectionToggle,
                    getFilteredSelectableSegmentIndices:
                        getFilteredSelectableSegmentIndices,
                    onBulkSelectAll: onBulkSelectAll,
                    onBulkInvertSelection: onBulkInvertSelection,
                    onBatchFontApply: onBatchFontApply,
                    onBatchFontSizeStep: onBatchFontSizeStep,
                    segmentScrollController: segmentScrollController,
                    showSegmentScrollbar: showSegmentScrollbar,
                    enablePdfPageFilter: baseMode ==
                        TranslationPreviewMode.pdfPreserve,
                  )
              : null,
          onBatchFontApply: _supportsRevisionForMode(baseMode)
              ? (Set<int> indices) => _handleBatchPdfTypography(
                    indices,
                    SegmentPdfTypographyDialogMode.fontOnly,
                  )
              : null,
          onBatchFontSizeStep: _supportsRevisionForMode(baseMode)
              ? _handleBatchFontSizeStep
              : null,
          onBatchLeadingApply: kPdfLeadingTypographyUiEnabled &&
                  _supportsRevisionForMode(baseMode) &&
                  baseMode == TranslationPreviewMode.pdfPreserve
              ? (Set<int> indices) => _handleBatchPdfTypography(
                    indices,
                    SegmentPdfTypographyDialogMode.leadingOnly,
                  )
              : null,
          onPdfRevisionModeEntered: _supportsRevisionForMode(baseMode)
              ? () => _onRevisionModeEntered(baseMode)
              : null,
          pdfPreviewJumpPageListenable: _supportsRevisionForMode(baseMode) &&
                  baseMode == TranslationPreviewMode.pdfPreserve
              ? _pdfPreviewJumpPageNotifier
              : null,
          pdfPreviewJumpPageTriggerListenable:
              _supportsRevisionForMode(baseMode) &&
                      baseMode == TranslationPreviewMode.pdfPreserve
                  ? _pdfPreviewJumpPageTriggerNotifier
                  : null,
          autoFollowSegmentPdfPageListenable:
              _supportsRevisionForMode(baseMode) &&
                      baseMode == TranslationPreviewMode.pdfPreserve
                  ? _autoFollowSegmentPdfPageNotifier
                  : null,
          pdfHighlightBboxPageListenable:
              _supportsRevisionForMode(baseMode)
                  ? _pdfHighlightBboxPageNotifier
                  : null,
          pdfHighlightBboxListenable:
              _supportsRevisionForMode(baseMode)
                  ? _pdfHighlightBboxNotifier
                  : null,
          showSelectedSegmentMarkerListenable:
              _supportsRevisionForMode(baseMode)
                  ? _showSelectedSegmentMarkerNotifier
                  : null,
          onShowSelectedSegmentMarkerChanged:
              _supportsRevisionForMode(baseMode)
                  ? _setShowSelectedSegmentMarker
                  : null,
          onAutoFollowSegmentPdfPageChanged:
              _supportsRevisionForMode(baseMode) &&
                      baseMode == TranslationPreviewMode.pdfPreserve
                  ? _setAutoFollowSegmentPdfPage
                  : null,
          getFilteredSelectableSegmentIndices:
              _supportsRevisionForMode(baseMode)
                  ? _getFilteredSelectableSegmentIndices
                  : null,
        ),
        dataRef: <String, dynamic>{
          'taskId': _apiTaskId(),
          'flowId': widget.flowId,
          'downloads': effectiveDownloads,
        },
      ),
    );
    _switchToPreviewTab(tabId);
  }

  Future<void> _openPdfPreviewTab({required String rendererType}) async {
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : null;
    final Map<String, String>? effectiveDownloads =
        _resolveEffectiveDownloads(translationState);

    if (!_isPdfSourceFile() || effectiveDownloads?.containsKey('pdf') != true) {
      MessageService.showWarning(context, 'PDF preview not available');
      return;
    }

    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final String title = rendererType == 'typst_overlay'
        ? l10n.translationExportPdfPreserveLayout
        : l10n.translationExportPdfReflow;

    const String tabId = _kTranslationPreviewTabId;
    _previewTabsNotifier().updateOrAddTab(
      PreviewTab(
        id: tabId,
        type: PreviewTabType.translationResult,
        title: title,
        icon: Icons.picture_as_pdf,
        content: _buildPdfPreview(rendererType: rendererType),
        dataRef: <String, dynamic>{
          'taskId': _apiTaskId(),
          'flowId': widget.flowId,
          'downloads': effectiveDownloads,
        },
      ),
    );
    _switchToPreviewTab(tabId);
  }

  /// Build PDF preview widget (Typst overlay or Pandoc reflow).
  Widget _buildPdfPreview({required String rendererType}) {
    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : null;
    final String? relativeUrl =
        _resolveEffectiveDownloads(translationState)?['pdf'];

    if (relativeUrl == null) {
      return const Center(child: Text('PDF download not available'));
    }

    final FormatSettings formatSettings = ref.read(
      formatSettingsProviderFamily(_apiTaskId()),
    );
    const bool isPdfWorkflow = true;
    final Map<String, String> queryParams = {
      ...buildPreviewExportQueryParams(
        formatSettings,
        isPdfWorkflow: isPdfWorkflow,
        rendererType: rendererType,
      ),
      ...previewCacheBustParams(_pdfPreviewRevision),
    };
    final String finalUrl = mergePreviewUrl(relativeUrl, queryParams);
    final String viewerUrl = finalUrl.startsWith('http')
        ? finalUrl
        : '${AppConfig.baseUrl}$finalUrl';

    return PdfPreview(
      downloadUrl: finalUrl,
      viewerUrl: viewerUrl,
      rendererType: rendererType,
      onDownload: widget.onDownload,
      onRequestPreviewSettings: _handlePreviewSettingsRequest,
    );
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
    final bool isImageFile = isMineruLayoutImageFileName(widget.fileName);
    final String? imageExt = originalImageDownloadExtension(widget.fileName);
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
      availableFormats = <String>['docx', 'md', 'html', 'pdf'];
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

    if (isImageFile && imageExt != null) {
      availableFormats.remove(imageExt);
      availableFormats.insert(0, imageExt);
    }

    if (availableFormats.isEmpty) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showWarning(context, l10n.translationExportNoFormats);
      return;
    }

    final l10n = AppLocalizations.of(context)!;

    // Build download options (for MD, always offer embedded and with-images variants)
    final List<Map<String, dynamic>> downloadOptions = <Map<String, dynamic>>[];
    for (final String format in availableFormats) {
      if (format == 'md') {
        downloadOptions.add(<String, dynamic>{
          'type': 'md',
          'label': l10n.translationExportMdEmbeddedImages,
          'embedImages': true,
        });
        downloadOptions.add(<String, dynamic>{
          'type': 'md',
          'label': l10n.translationExportMdWithImagesFolder,
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
      } else if (format == 'pdf') {
        if (resolvedWorkflowType == 'html') {
          downloadOptions.add(<String, dynamic>{
            'type': 'pdf',
            'label': 'PDF',
            'embedImages': null,
            'rendererType': 'html',
          });
        } else {
          downloadOptions.add(<String, dynamic>{
            'type': 'pdf',
            'label': l10n.translationExportPdfPreserveLayout,
            'description': l10n.translationExportPdfPreserveLayoutDesc,
            'embedImages': null,
            'rendererType': 'typst_overlay',
          });
          downloadOptions.add(<String, dynamic>{
            'type': 'pdf',
            'label': l10n.translationExportPdfReflow,
            'description': l10n.translationExportPdfReflowDesc,
            'embedImages': null,
            'rendererType': 'pandoc',
          });
        }
      } else if (isOriginalImageDownloadFormat(format)) {
        downloadOptions.add(<String, dynamic>{
          'type': format,
          'label': l10n.translationExportImageOriginalLayout,
          'description': l10n.translationExportImageOriginalLayoutDesc,
          'embedImages': null,
        });
      } else {
        downloadOptions.add(<String, dynamic>{
          'type': format,
          'label': format.toUpperCase(),
          'embedImages': null,
        });
      }
    }

    // Check if this is a PDF or image layout workflow to show format options
    final bool isPdfWorkflow =
        resolvedWorkflowType == 'markdown_based' || isPdfFile;
    final bool isImageLayoutWorkflow =
        isImageFile && resolvedWorkflowType == 'markdown_based';
    final bool hasTables = status?['has_tables'] as bool? ?? false;
    final bool hasInterlineEquations =
        status?['has_interline_equations'] as bool? ?? false;
    final bool hasCharts = status?['has_charts'] as bool? ?? false;
    final bool showFormatOptions =
        (isPdfWorkflow || isImageLayoutWorkflow) &&
        (hasTables || hasInterlineEquations || hasCharts);
    final bool showImageOverlayOptions = isImageLayoutWorkflow;

    // Determine whether bilingual export option should be shown
    final bool supportsBilingual = <String>{
      'markdown_based',
      'txt',
      'html',
      'srt',
      'epub',
      'mobi',
      'docx',
      'pptx',
      'xlsx',
    }.contains(resolvedWorkflowType);

    final List<Map<String, dynamic>> _colorOptions = [
      {'value': '', 'color': Colors.transparent, 'label': l10n.translationExportColorDefault},
      {'value': 'gray', 'color': Colors.grey, 'label': l10n.translationExportColorGray},
      {'value': 'blue', 'color': Colors.blue, 'label': l10n.translationExportColorBlue},
      {'value': 'red', 'color': Colors.red, 'label': l10n.translationExportColorRed},
      {'value': 'green', 'color': Colors.green, 'label': l10n.translationExportColorGreen},
      {'value': 'orange', 'color': Colors.orange, 'label': l10n.translationExportColorOrange},
      {'value': 'black', 'color': Colors.black, 'label': l10n.translationExportColorBlack},
    ];

    int selectedDownloadIndex = 0;

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
          String tableFormat =
              formatSettings.getTableFormat(isPdfWorkflow: isPdfWorkflow);
          String equationFormat =
              formatSettings.getEquationFormat(isPdfWorkflow: isPdfWorkflow);
          String chartFormat =
              formatSettings.getChartFormat(isPdfWorkflow: isPdfWorkflow);
          String coverColorMode = formatSettings.getCoverColorMode();
          String bilingualOrder =
              formatSettings.bilingualOrder ?? 'target_after_source';
          bool sourceTextItalic = formatSettings.sourceTextItalic ?? false;
          String sourceTextColor =
              formatSettings.sourceTextColor ?? ''; // empty means default color
          bool targetTextItalic = formatSettings.targetTextItalic ?? true;
          String targetTextColor =
              formatSettings.targetTextColor ?? 'gray';

          return StatefulBuilder(
            builder: (BuildContext context, setDialogState) {
              final Map<String, dynamic> selectedDownloadOption =
                  downloadOptions[selectedDownloadIndex];
              final String? selectedRendererType =
                  selectedDownloadOption['rendererType'] as String?;
              final bool isPreserveLayoutPdf =
                  selectedDownloadOption['type'] == 'pdf' &&
                  selectedRendererType == 'typst_overlay';
              final bool bilingualAvailable =
                  supportsBilingual && !isPreserveLayoutPdf;
              final bool bilingualExport =
                  bilingualAvailable &&
                  (formatSettings.bilingualExport ?? false);

              return Material(
              type: MaterialType.transparency,
              child: AlertDialog(
                title: Text(l10n.translationExportDialogTitle),
                content: SizedBox(
                  width: 720,
                  height: 380,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      // LEFT: Parameter options
                      Expanded(
                        flex: 3,
                        child: SingleChildScrollView(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              // Format options for PDF workflow
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
                        if (hasCharts) ...<Widget>[
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              SizedBox(
                                width: 120, // Fixed width for label alignment
                                child: Text(
                                  l10n.translationExportChartFormatLabel,
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
                                      groupValue: chartFormat,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            chartFormat = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setChartFormat(value);
                                        }
                                      },
                                    ),
                                    Text(
                                      l10n.translationExportChartFormatImage,
                                    ),
                                    const SizedBox(width: 16),
                                    Radio<String>(
                                      value: 'html',
                                      groupValue: chartFormat,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            chartFormat = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setChartFormat(value);
                                        }
                                      },
                                    ),
                                    Text(
                                      l10n.translationExportChartFormatHtml,
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ],
                        const Divider(height: 24),
                      ],
                      if (showImageOverlayOptions) ...<Widget>[
                        Text(
                          l10n.translationExportFormatOptionsTitle,
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            SizedBox(
                              width: 120,
                              child: Text(
                                l10n.translationImageCoverColorModeLabel,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  RadioListTile<String>(
                                    value: 'max',
                                    groupValue: coverColorMode,
                                    onChanged: (String? value) {
                                      if (value == null) {
                                        return;
                                      }
                                      setDialogState(() {
                                        coverColorMode = value;
                                      });
                                      ref
                                          .read(
                                            formatSettingsProviderFamily(
                                              _apiTaskId(),
                                            ).notifier,
                                          )
                                          .setCoverColorMode(value);
                                    },
                                    title: Text(
                                      l10n.translationImageCoverColorModeMax,
                                    ),
                                    dense: true,
                                    contentPadding: EdgeInsets.zero,
                                  ),
                                  RadioListTile<String>(
                                    value: 'min',
                                    groupValue: coverColorMode,
                                    onChanged: (String? value) {
                                      if (value == null) {
                                        return;
                                      }
                                      setDialogState(() {
                                        coverColorMode = value;
                                      });
                                      ref
                                          .read(
                                            formatSettingsProviderFamily(
                                              _apiTaskId(),
                                            ).notifier,
                                          )
                                          .setCoverColorMode(value);
                                    },
                                    title: Text(
                                      l10n.translationImageCoverColorModeMin,
                                    ),
                                    dense: true,
                                    contentPadding: EdgeInsets.zero,
                                  ),
                                  RadioListTile<String>(
                                    value: 'avg',
                                    groupValue: coverColorMode,
                                    onChanged: (String? value) {
                                      if (value == null) {
                                        return;
                                      }
                                      setDialogState(() {
                                        coverColorMode = value;
                                      });
                                      ref
                                          .read(
                                            formatSettingsProviderFamily(
                                              _apiTaskId(),
                                            ).notifier,
                                          )
                                          .setCoverColorMode(value);
                                    },
                                    title: Text(
                                      l10n.translationImageCoverColorModeAvg,
                                    ),
                                    dense: true,
                                    contentPadding: EdgeInsets.zero,
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const Divider(height: 24),
                      ],
                      // Bilingual export options
                      if (supportsBilingual) ...<Widget>[
                        Opacity(
                          opacity: bilingualAvailable ? 1.0 : 0.4,
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.center,
                            children: <Widget>[
                              Checkbox(
                                value: bilingualExport,
                                onChanged: bilingualAvailable
                                    ? (bool? value) {
                                        if (value == null) {
                                          return;
                                        }
                                        ref
                                            .read(
                                              formatSettingsProviderFamily(
                                                      _apiTaskId(),)
                                                  .notifier,
                                            )
                                            .setBilingualExport(value);
                                      }
                                    : null,
                              ),
                              Expanded(
                                child: Text(
                                  l10n.translationExportBilingualExport,
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w600),
                                ),
                              ),
                            ],
                          ),
                        ),
                        // Always show options, but disable when bilingual is off
                        Opacity(
                          opacity: bilingualAvailable && bilingualExport
                              ? 1.0
                              : 0.4,
                          child: AbsorbPointer(
                            absorbing:
                                !bilingualAvailable || !bilingualExport,
                            child: Padding(
                              padding: const EdgeInsets.only(left: 32.0),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                // Order: inline radios
                                Row(
                                  children: <Widget>[
                                    Radio<String>(
                                      value: 'target_after_source',
                                      groupValue: bilingualOrder,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            bilingualOrder = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setBilingualOrder(value);
                                        }
                                      },
                                    ),
                                    Text(l10n.translationExportBilingualOrderTargetAfter),
                                    const SizedBox(width: 16),
                                    Radio<String>(
                                      value: 'target_before_source',
                                      groupValue: bilingualOrder,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            bilingualOrder = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setBilingualOrder(value);
                                        }
                                      },
                                    ),
                                    Text(l10n.translationExportBilingualOrderTargetBefore),
                                  ],
                                ),
                                const Divider(height: 20),
                                // Italic: source and target side by side
                                Row(
                                  children: <Widget>[
                                    Checkbox(
                                      value: sourceTextItalic,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            sourceTextItalic = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setSourceTextItalic(value);
                                        }
                                      },
                                    ),
                                    Text(l10n.translationExportSourceTextItalic),
                                    const SizedBox(width: 24),
                                    Checkbox(
                                      value: targetTextItalic,
                                      onChanged: (value) {
                                        if (value != null) {
                                          setDialogState(() {
                                            targetTextItalic = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setTargetTextItalic(value);
                                        }
                                      },
                                    ),
                                    Text(l10n.translationExportTargetTextItalic),
                                  ],
                                ),
                                const Divider(height: 20),
                                // Colors: source color row
                                Row(
                                  children: <Widget>[
                                    Text(l10n.translationExportSourceTextColor),
                                    const SizedBox(width: 8),
                                    ..._colorOptions.map((option) {
                                      final value = option['value'] as String;
                                      final color = option['color'] as Color;
                                      final label = option['label'] as String?;
                                      final isSelected =
                                          sourceTextColor == value;
                                      final Widget circle = GestureDetector(
                                        onTap: () {
                                          setDialogState(() {
                                            sourceTextColor = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setSourceTextColor(value);
                                        },
                                        child: Container(
                                          margin: const EdgeInsets.symmetric(
                                              horizontal: 4),
                                          width: 24,
                                          height: 24,
                                          decoration: BoxDecoration(
                                            color: color,
                                            shape: BoxShape.circle,
                                            border: Border.all(
                                              color: isSelected
                                                  ? Theme.of(context)
                                                      .colorScheme
                                                      .primary
                                                  : (color == Colors.transparent
                                                      ? Colors.grey.shade300
                                                      : Colors.transparent),
                                              width: 2,
                                            ),
                                          ),
                                        ),
                                      );
                                      return label != null
                                          ? Tooltip(
                                              message: label,
                                              child: circle,
                                            )
                                          : circle;
                                    }).toList(),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                // Target color row
                                Row(
                                  children: <Widget>[
                                    Text(l10n.translationExportTargetTextColor),
                                    const SizedBox(width: 8),
                                    ..._colorOptions.map((option) {
                                      final value = option['value'] as String;
                                      final color = option['color'] as Color;
                                      final label = option['label'] as String?;
                                      final isSelected = targetTextColor == value;
                                      final Widget circle = GestureDetector(
                                        onTap: () {
                                          setDialogState(() {
                                            targetTextColor = value;
                                          });
                                          ref
                                              .read(
                                                formatSettingsProviderFamily(
                                                        _apiTaskId(),)
                                                    .notifier,
                                              )
                                              .setTargetTextColor(value);
                                        },
                                        child: Container(
                                          margin: const EdgeInsets.symmetric(
                                              horizontal: 4),
                                          width: 24,
                                          height: 24,
                                          decoration: BoxDecoration(
                                            color: color,
                                            shape: BoxShape.circle,
                                            border: Border.all(
                                              color: isSelected
                                                  ? Theme.of(context)
                                                      .colorScheme
                                                      .primary
                                                  : (color == Colors.transparent
                                                      ? Colors.grey.shade300
                                                      : Colors.transparent),
                                              width: 2,
                                            ),
                                          ),
                                        ),
                                      );
                                      return label != null
                                          ? Tooltip(
                                              message: label,
                                              child: circle,
                                            )
                                          : circle;
                                    }).toList(),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                        ),
                        const Divider(height: 24),
                      ],
                            ],
                          ),
                        ),
                      ),
                      const VerticalDivider(width: 1),
                      // RIGHT: Download buttons
                      Expanded(
                        flex: 2,
                        child: SingleChildScrollView(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Padding(
                                padding: const EdgeInsets.all(16.0),
                                child: Text(
                                  l10n.translationExportDocumentType,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 16,
                                  ),
                                ),
                              ),
                            ...downloadOptions.asMap().entries.map((entry) {
                              final int index = entry.key;
                              final Map<String, dynamic> option = entry.value;
                              final String label = option['label'] as String;
                              final String? description =
                                  option['description'] as String?;
                              return RadioListTile<int>(
                                value: index,
                                groupValue: selectedDownloadIndex,
                                title: Text(label),
                                subtitle: description != null &&
                                        description.isNotEmpty
                                    ? Text(
                                        description,
                                        style: Theme.of(context)
                                            .textTheme
                                            .labelSmall
                                            ?.copyWith(
                                          color: Theme.of(context)
                                              .colorScheme
                                              .onSurfaceVariant,
                                        ),
                                      )
                                    : null,
                                dense: true,
                                onChanged: (int? value) {
                                  if (value == null) {
                                    return;
                                  }
                                  final Map<String, dynamic> newOption =
                                      downloadOptions[value];
                                  final String? newRendererType =
                                      newOption['rendererType'] as String?;
                                  final bool preserveLayoutPdf =
                                      newOption['type'] == 'pdf' &&
                                      newRendererType == 'typst_overlay';
                                  if (preserveLayoutPdf) {
                                    ref
                                        .read(
                                          formatSettingsProviderFamily(
                                                  _apiTaskId(),)
                                              .notifier,
                                        )
                                        .setBilingualExport(false);
                                  }
                                  setDialogState(() {
                                    selectedDownloadIndex = value;
                                  });
                                },
                              );
                            }),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                actions: <Widget>[
                  TextButton(
                    onPressed: () {
                      Navigator.of(context, rootNavigator: true).pop();
                    },
                    child: Text(l10n.translationToolbarCancelButton),
                  ),
                  TextButton(
                    onPressed: () {
                      final selectedOption =
                          downloadOptions[selectedDownloadIndex];
                      final fileType = selectedOption['type'] as String;
                      final embedImages =
                          selectedOption['embedImages'] as bool?;
                      final ebookEngine =
                          selectedOption['ebookEngine'] as String?;
                      final rendererType =
                          selectedOption['rendererType'] as String?;
                      final currentTableFormat = tableFormat;
                      final currentEquationFormat = equationFormat;
                      final currentChartFormat = chartFormat;
                      Navigator.of(context, rootNavigator: true).pop();
                      _handlePreviewFormatDownload(
                        fileType,
                        embedImages: embedImages,
                        tableFormat: currentTableFormat,
                        equationFormat: currentEquationFormat,
                        chartFormat: currentChartFormat,
                        ebookEngine: ebookEngine,
                        rendererType: rendererType,
                      );
                    },
                    child: Text(l10n.translationExportDownloadButton),
                  ),
                ],
              ),
            );
            },
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
    String? chartFormat,
    String? ebookEngine,
    String? rendererType,
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
      // Only send when user has explicitly set values (provider has non-null);
      // otherwise let backend decide based on PDF/non-PDF flow.
      if (fileType == 'md' ||
          fileType == 'html' ||
          fileType == 'docx' ||
          fileType == 'pdf') {
        final formatSettings = ref.read(
          formatSettingsProviderFamily(_apiTaskId()),
        );
        final bool isPdfFile =
            widget.fileName?.toLowerCase().endsWith('.pdf') ?? false;
        final bool isPdfWorkflow =
            widget.workflowType == 'markdown_based' || isPdfFile;
        queryParams['table_body_format'] = tableFormat ??
            formatSettings.getTableFormat(isPdfWorkflow: isPdfWorkflow);
        queryParams['equation_format'] = equationFormat ??
            formatSettings.getEquationFormat(isPdfWorkflow: isPdfWorkflow);
        queryParams['chart_body_format'] = chartFormat ??
            formatSettings.getChartFormat(isPdfWorkflow: isPdfWorkflow);
        if (fileType == 'md' && embedImages != null) {
          queryParams['embed_images'] = embedImages.toString();
        }
      }

      // For EPUB/MOBI, add ebook_engine when user chose Pandoc or Calibre
      if ((fileType == 'epub' || fileType == 'mobi') && ebookEngine != null) {
        queryParams['ebook_engine'] = ebookEngine;
      }

      // Add renderer_type for PDF export (typst_overlay | pandoc)
      if (rendererType != null && rendererType.isNotEmpty) {
        queryParams['renderer_type'] = rendererType;
      }

      if (isOriginalImageDownloadFormat(fileType)) {
        final formatSettings = ref.read(
          formatSettingsProviderFamily(_apiTaskId()),
        );
        queryParams['cover_color_mode'] = formatSettings.getCoverColorMode();
      }

      // Add bilingual parameters if enabled (not supported for preserve-layout PDF)
      final formatSettings = ref.read(
        formatSettingsProviderFamily(_apiTaskId()),
      );
      if (formatSettings.bilingualExport == true &&
          rendererType != 'typst_overlay') {
        queryParams['bilingual_export'] = 'true';
        queryParams['bilingual_order'] =
            formatSettings.bilingualOrder ?? 'target_after_source';
        if (formatSettings.sourceTextItalic != null) {
          queryParams['source_text_italic'] =
              formatSettings.sourceTextItalic.toString();
        }
        if (formatSettings.sourceTextColor != null) {
          queryParams['source_text_color'] = formatSettings.sourceTextColor!;
        }
        if (formatSettings.targetTextItalic != null) {
          queryParams['target_text_italic'] =
              formatSettings.targetTextItalic.toString();
        }
        if (formatSettings.targetTextColor != null &&
            formatSettings.targetTextColor!.isNotEmpty) {
          queryParams['target_text_color'] = formatSettings.targetTextColor!;
        }
      }

      downloadUrl = uri.replace(queryParameters: queryParams).toString();
      widget.onDownload!(fileType, downloadUrl);
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to download $fileType: $e');
      }
    }
  }
}
