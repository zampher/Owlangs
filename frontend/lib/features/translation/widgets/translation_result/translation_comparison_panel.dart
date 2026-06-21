// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/widgets/paginated_sliver_list.dart';
import '../../../../shared/widgets/page_size_selector.dart';
import '../../../../shared/utils/pagination.dart';
import '../../../../shared/providers/settings_provider.dart';
import '../../providers/segment_undo_redo_provider.dart';
import '../../models/segment_pair.dart';
import '../../utils/segment_height_cache.dart';
import '../../utils/segment_type_utils.dart';
import 'translation_segment_item.dart';
import 'segment_pdf_typography_dialog.dart';

/// State-based filter keys (mutually exclusive - single select)
const Set<String> _stateFilterKeys = <String>{
  'translated',
  'pending',
  'failed',
  'excluded',
  'retry',
  'cleared',
  'images',
};

/// Comparison panel for displaying source and target segments side by side
class TranslationComparisonPanel extends ConsumerWidget {
  const TranslationComparisonPanel({
    required this.taskId,
    required this.isLoading,
    required this.sourceParagraphs,
    required this.targetParagraphs,
    required this.highlightedIndexNotifier,
    required this.scrollController,
    required this.segmentPairKeys,
    required this.sourceItemKeys,
    required this.targetItemKeys,
    required this.modifiedSegments,
    required this.imageDataMap,
    required this.segmentMetadata,
    required this.retranslatingSegments,
    required this.onHighlightParagraph,
    required this.onSegmentEdit,
    required this.onEditingStarted,
    required this.onRetrySegment,
    required this.onMarkForRetry,
    required this.onUnmarkForRetry,
    required this.onExcludeSegment,
    required this.onUnexcludeSegment,
    required this.onUndo, required this.onRedo, this.onClearSegment,
    this.onUnclearSegment,
    super.key,
    this.loadingError,
    this.segmentsPaginationController,
    this.totalSegmentsCount = 0,
    this.heightCache,
    this.translationState,
    this.tokenUsage,
    this.selectedExclusionFilters,
    this.onFiltersChanged,
    this.onExclusionUpdated,
    this.onFormulaFix,
    this.isConvertOnly = false,
    this.showPdfFontSize = false,
    this.onFontSizeChanged,
    this.onRotationChanged,
    this.batchSelectionEnabled = false,
    this.selectedSegmentIndices = const <int>{},
    this.selectedSegmentIndicesListenable,
    this.onSegmentSelectionToggle,
    this.onBulkSelectAll,
    this.onBulkInvertSelection,
    this.onBatchFontApply,
    this.onBatchFontSizeStep,
    this.getFilteredSelectableSegmentIndices,
    this.exclusionFiltersListenable,
    this.pdfRevisionMode = false,
    this.pdfPageFilterListenable,
    this.onPdfPageFilterChanged,
    this.showSegmentScrollbar = true,
  });

  final String taskId;
  final bool isLoading;
  final String? loadingError;
  final List<String> sourceParagraphs;
  final List<String> targetParagraphs;
  final ValueNotifier<int?> highlightedIndexNotifier;
  final ScrollController scrollController;
  final PagedListController<SegmentPair>? segmentsPaginationController;
  final int totalSegmentsCount;
  final Map<int, GlobalKey> segmentPairKeys;
  final Map<int, GlobalKey> sourceItemKeys;
  final Map<int, GlobalKey> targetItemKeys;
  final Map<int, String> modifiedSegments;
  final Map<String, Map<String, String>> imageDataMap;
  final Map<int, Map<String, dynamic>> segmentMetadata;
  final Set<int> retranslatingSegments;
  final SegmentHeightCache? heightCache;
  final void Function(int) onHighlightParagraph;
  final void Function(int, String) onSegmentEdit;
  final void Function(int) onEditingStarted;
  final void Function(int) onRetrySegment;
  final void Function(int) onMarkForRetry;
  final void Function(int) onUnmarkForRetry;
  final void Function(int) onExcludeSegment;
  final void Function(int) onUnexcludeSegment;
  final void Function(int)? onClearSegment;
  final void Function(int)? onUnclearSegment;
  final void Function(int) onUndo;
  final void Function(int) onRedo;
  final void Function(int)? onExclusionUpdated;
  final dynamic translationState;
  final Map<String, int>? tokenUsage;
  final Set<String>? selectedExclusionFilters;
  final void Function(Set<String>)? onFiltersChanged;
  final void Function(int)? onFormulaFix;
  final bool isConvertOnly;
  final bool showPdfFontSize;
  final void Function(
    int index, {
    double? fontSizePt,
    String? fontWeight,
    String? fontStyle,
    double? leadingEm,
    bool reset,
    SegmentPdfTypographyDialogMode scope,
  })? onFontSizeChanged;
  final void Function(int index, int rotation)? onRotationChanged;
  final bool batchSelectionEnabled;
  final Set<int> selectedSegmentIndices;
  final ValueListenable<Set<int>>? selectedSegmentIndicesListenable;
  final void Function(int index, bool selected)? onSegmentSelectionToggle;
  final void Function(Set<int> indices)? onBulkSelectAll;
  final void Function(Set<int> indices)? onBulkInvertSelection;
  final Future<void> Function()? onBatchFontApply;
  final Future<void> Function(double delta)? onBatchFontSizeStep;
  final Set<int> Function()? getFilteredSelectableSegmentIndices;
  final ValueListenable<Set<String>>? exclusionFiltersListenable;
  final bool pdfRevisionMode;
  final ValueListenable<Set<int>>? pdfPageFilterListenable;
  final void Function(Set<int> pages, {int? jumpToPage})? onPdfPageFilterChanged;
  final bool showSegmentScrollbar;

  /// Check if a segment is cleared based on metadata
  bool _isSegmentCleared(Map<String, dynamic> metadata) {
    final status = metadata['status'] as String?;
    final targetText = metadata['target_text'] as String?;
    return status == 'cleared' || (targetText ?? '').isEmpty;
  }

  double? _readFontSizePt(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['font_size_pt'];
    if (raw is num) {
      return raw.toDouble();
    }
    if (raw is String) {
      return double.tryParse(raw);
    }
    return null;
  }

  double? _readOverlayRenderFontSizePt(Map<String, dynamic> metadata) {
    return _readOptionalDouble(metadata['overlay_render_font_size_pt']);
  }

  String? _readFontWeight(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['font_weight'];
    return raw is String ? raw : null;
  }

  String? _readComputedFontWeight(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['computed_font_weight'];
    return raw is String ? raw : null;
  }

  String? _readFontStyle(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['font_style'];
    return raw is String ? raw : null;
  }

  String? _readComputedFontStyle(Map<String, dynamic> metadata) {
    final dynamic raw = metadata['computed_font_style'];
    return raw is String ? raw : null;
  }

  double? _readLeadingEm(Map<String, dynamic> metadata) {
    return _readOptionalDouble(metadata['leading_em']);
  }

  double? _readComputedLeadingEm(Map<String, dynamic> metadata) {
    return _readOptionalDouble(metadata['computed_leading_em']);
  }

  double? _readOptionalDouble(dynamic raw) {
    if (raw is num) {
      return raw.toDouble();
    }
    if (raw is String) {
      return double.tryParse(raw);
    }
    return null;
  }

  /// Calculate counts for state-based filter chips
  Map<String, int> _calculateFilterCounts(
    Map<int, Map<String, dynamic>> segmentMetadata,
  ) {
    var total = 0;
    var translated = 0;
    var pending = 0;
    var excluded = 0;
    var retry = 0;
    var failed = 0;
    var cleared = 0;
    var images = 0;

    for (final MapEntry<int, Map<String, dynamic>> entry
        in segmentMetadata.entries) {
      final metadata = entry.value;
      final isImage = metadata['is_image'] as bool? ?? false;
      final isExcluded = metadata['is_excluded'] as bool? ?? false;
      final targetText = metadata['target_text'] as String?;
      final status = metadata['status'] as String?;
      final needsRetry = metadata['needs_retry'] as bool? ?? false;
      final isFailed = metadata['is_failed'] as bool? ?? false;
      final isCleared = status == 'cleared';

      total++;

      if (isImage) {
        images++;
      } else if (isExcluded && !isFailed) {
        excluded++;
      } else if (isCleared) {
        cleared++;
      } else if (isFailed) {
        // counted in failed below
      } else {
        if (targetText != null && targetText.isNotEmpty) {
          translated++;
        } else {
          pending++;
        }
      }

      if (!isCleared && !isImage) {
        if (isFailed) failed++;
        if (needsRetry && !isFailed && !(isExcluded && !isFailed)) retry++;
      }
    }

    return <String, int>{
      '': total,
      'translated': translated,
      'pending': pending,
      'failed': failed,
      'excluded': excluded,
      'retry': retry + failed, // "Retry" shows failed + manual retry
      'cleared': cleared,
      'images': images,
    };
  }

  /// Build filter chips bar (replaces the old statistics widget)
  Widget _buildFilterChipsBar(BuildContext context, Set<String> selected) {
    final l10n = AppLocalizations.of(context)!;
    final counts = _calculateFilterCounts(segmentMetadata);

    // Define filter chip configs: key, label, color
    final filters = <_FilterChipConfig>[
      _FilterChipConfig('', l10n.translationToolbarFilterAll, Colors.blue),
      _FilterChipConfig('translated', l10n.translationStatsTranslatedLabel, Colors.green),
      _FilterChipConfig('pending', l10n.translationStatsPendingLabel, Colors.orange),
      _FilterChipConfig('failed', l10n.translationToolbarFilterFailed, Colors.red),
      _FilterChipConfig('excluded', l10n.translationToolbarFilterExcluded, Colors.grey),
      if (!pdfRevisionMode)
        _FilterChipConfig('retry', l10n.translationToolbarRetry, Colors.orange),
      _FilterChipConfig('cleared', l10n.translationStatsClearedLabel, Colors.purple),
      if (!pdfRevisionMode)
        _FilterChipConfig(
          'images',
          l10n.translationStatsImagesLabel,
          Colors.blue,
        ),
    ];

    final chipWidgets = filters.map((cfg) {
        final count = counts[cfg.key] ?? 0;
        // Hide chips with 0 count (except "All")
        if (count == 0 && cfg.key.isNotEmpty) {
          return const SizedBox.shrink();
        }
        final isSelected = cfg.key.isEmpty
            ? selected.isEmpty
            : selected.contains(cfg.key);
        const EdgeInsets chipPadding =
            EdgeInsets.symmetric(horizontal: 2, vertical: 0);
        final VisualDensity chipDensity = pdfRevisionMode
            ? const VisualDensity(horizontal: -2, vertical: -3)
            : const VisualDensity(horizontal: -4, vertical: -4);
        return Tooltip(
          message: '${cfg.label} ($count)',
          child: ActionChip(
            label: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                if (isSelected)
                  Icon(Icons.check, size: 10, color: cfg.color.shade700),
                if (isSelected) SizedBox(width: 2),
                Text(
                  '${cfg.label} ($count)',
                  style: TextStyle(
                    fontSize: 9,
                    color: isSelected ? cfg.color.shade700 : Colors.grey.shade700,
                  ),
                ),
              ],
            ),
            onPressed: onFiltersChanged != null
                ? () {
                    if (cfg.key.isEmpty) {
                      // "All" clears all state filters
                      onFiltersChanged!(<String>{});
                    } else {
                      // Toggle: if already selected, clear; else set this filter
                      if (isSelected) {
                        onFiltersChanged!(<String>{});
                      } else {
                        onFiltersChanged!(<String>{cfg.key});
                      }
                    }
                  }
                : null,
            backgroundColor: isSelected ? cfg.color.shade100 : Colors.grey.shade200,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(pdfRevisionMode ? 5 : 6),
            ),
            padding: chipPadding,
            labelPadding: pdfRevisionMode
                ? const EdgeInsets.symmetric(horizontal: 3)
                : const EdgeInsets.symmetric(horizontal: 4),
            visualDensity: chipDensity,
            materialTapTargetSize: pdfRevisionMode
                ? MaterialTapTargetSize.shrinkWrap
                : MaterialTapTargetSize.padded,
            side: BorderSide(
              color: isSelected ? cfg.color.shade300 : Colors.grey.shade400,
            ),
          ),
        );
      }).toList();

    final Widget filterLabel = Padding(
      padding: const EdgeInsets.only(right: 3),
      child: Text(
        pdfRevisionMode
            ? '${l10n.settingsGlossaryFilterLabel}:'
            : '${l10n.settingsGlossaryFilterLabel} ',
        style: TextStyle(
          fontSize: 9,
          fontWeight: FontWeight.w600,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );

    // PDF revision: use full-width Wrap so chips flow horizontally (max ~2 rows)
    // instead of stacking one chip per row when the panel is narrow.
    if (pdfRevisionMode) {
      return Wrap(
        spacing: 3,
        runSpacing: 3,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: <Widget>[
          filterLabel,
          ...chipWidgets,
        ],
      );
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        filterLabel,
        Flexible(
          child: Wrap(
            spacing: 2,
            runSpacing: 1,
            children: chipWidgets,
          ),
        ),
      ],
    );
  }

  Widget _buildFilterChipsBarListenable(BuildContext context) {
    if (exclusionFiltersListenable != null) {
      return ValueListenableBuilder<Set<String>>(
        valueListenable: exclusionFiltersListenable!,
        builder: (BuildContext context, Set<String> selected, Widget? _) {
          return _buildFilterChipsBar(context, selected);
        },
      );
    }
    return _buildFilterChipsBar(context, selectedExclusionFilters ?? <String>{});
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

  List<int> _availablePdfPageNumbers() {
    final Set<int> pages = <int>{};
    for (final Map<String, dynamic> metadata in segmentMetadata.values) {
      final int? page = _readPdfPageNumber(metadata);
      if (page != null) {
        pages.add(page);
      }
    }
    final List<int> sorted = pages.toList()..sort();
    return sorted;
  }

  Map<int, int> _calculatePdfPageCounts() {
    final Map<int, int> counts = <int, int>{};
    for (final Map<String, dynamic> metadata in segmentMetadata.values) {
      final int? page = _readPdfPageNumber(metadata);
      if (page != null) {
        counts[page] = (counts[page] ?? 0) + 1;
      }
    }
    return counts;
  }

  bool _isAllPdfPagesSelected(Set<int> selected, List<int> availablePages) {
    if (selected.isEmpty) {
      return true;
    }
    return availablePages.isNotEmpty &&
        availablePages.every(selected.contains);
  }

  String _pdfPageFilterSummaryLabel(
    Set<int> selected,
    List<int> availablePages,
    AppLocalizations l10n,
  ) {
    if (_isAllPdfPagesSelected(selected, availablePages)) {
      return l10n.translationPreviewPdfRevisionPageFilterAll;
    }
    final List<int> sorted = selected.toList()..sort();
    if (sorted.length == 1) {
      return 'P${sorted.first}';
    }
    if (sorted.length <= 3) {
      return sorted.map((int page) => 'P$page').join(', ');
    }
    return 'P${sorted.first}, +${sorted.length - 1}';
  }

  Widget _pdfPageMenuRow({required String label, required bool checked}) {
    return Row(
      children: <Widget>[
        SizedBox(
          width: 18,
          child: checked
              ? const Icon(Icons.check, size: 14)
              : const SizedBox.shrink(),
        ),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 12),
          ),
        ),
      ],
    );
  }

  void _togglePdfPageSelection({
    required Set<int> selected,
    required List<int> availablePages,
    required int page,
  }) {
    if (onPdfPageFilterChanged == null) {
      return;
    }
    final bool allSelected = _isAllPdfPagesSelected(selected, availablePages);
    final Set<int> next = Set<int>.from(selected);
    if (allSelected) {
      next
        ..clear()
        ..add(page);
    } else if (next.contains(page)) {
      next.remove(page);
    } else {
      next.add(page);
    }
    final bool pageRemoved =
        !allSelected && selected.contains(page) && !next.contains(page);
    onPdfPageFilterChanged!(
      next,
      jumpToPage: pageRemoved ? null : page,
    );
  }

  Widget _buildPdfPageFilterDropdown(BuildContext context, Set<int> selected) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final List<int> availablePages = _availablePdfPageNumbers();
    if (availablePages.isEmpty) {
      return const SizedBox.shrink();
    }

    final Map<int, int> counts = _calculatePdfPageCounts();
    final bool allSelected = _isAllPdfPagesSelected(selected, availablePages);
    final ColorScheme scheme = Theme.of(context).colorScheme;

    return MenuAnchor(
      style: MenuStyle(
        visualDensity: VisualDensity.compact,
        minimumSize: const WidgetStatePropertyAll<Size>(Size(160, 0)),
      ),
      builder: (
        BuildContext context,
        MenuController controller,
        Widget? child,
      ) {
        return InkWell(
          onTap: () {
            if (controller.isOpen) {
              controller.close();
            } else {
              controller.open();
            }
          },
          borderRadius: BorderRadius.circular(6),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              border: Border.all(color: scheme.outlineVariant),
              borderRadius: BorderRadius.circular(6),
              color: scheme.surface,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  '${l10n.translationPreviewPdfRevisionPageFilterLabel}: ',
                  style: TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w600,
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                Text(
                  _pdfPageFilterSummaryLabel(selected, availablePages, l10n),
                  style: TextStyle(
                    fontSize: 9,
                    color: scheme.onSurface,
                  ),
                ),
                Icon(
                  Icons.arrow_drop_down,
                  size: 16,
                  color: scheme.onSurfaceVariant,
                ),
              ],
            ),
          ),
        );
      },
      menuChildren: <Widget>[
        MenuItemButton(
          closeOnActivate: false,
          onPressed: onPdfPageFilterChanged == null
              ? null
              : () => onPdfPageFilterChanged!(<int>{}),
          child: _pdfPageMenuRow(
            label: l10n.translationPreviewPdfRevisionPageFilterAll,
            checked: allSelected,
          ),
        ),
        MenuItemButton(
          closeOnActivate: false,
          onPressed: onPdfPageFilterChanged == null
              ? null
              : () => onPdfPageFilterChanged!(
                    Set<int>.from(availablePages),
                    jumpToPage: availablePages.first,
                  ),
          child: _pdfPageMenuRow(
            label: l10n.translationPreviewPdfRevisionPageFilterSelectAll,
            checked: !allSelected &&
                selected.length == availablePages.length &&
                selected.isNotEmpty,
          ),
        ),
        ...availablePages.map((int page) {
          final bool pageChecked = !allSelected && selected.contains(page);
          return MenuItemButton(
            closeOnActivate: false,
            onPressed: onPdfPageFilterChanged == null
                ? null
                : () => _togglePdfPageSelection(
                      selected: selected,
                      availablePages: availablePages,
                      page: page,
                    ),
            child: _pdfPageMenuRow(
              label: 'P$page (${counts[page] ?? 0})',
              checked: pageChecked,
            ),
          );
        }),
      ],
    );
  }

  Widget _buildPdfPageFilterDropdownListenable(BuildContext context) {
    if (pdfPageFilterListenable != null) {
      return ValueListenableBuilder<Set<int>>(
        valueListenable: pdfPageFilterListenable!,
        builder: (BuildContext context, Set<int> selected, Widget? _) {
          return _buildPdfPageFilterDropdown(context, selected);
        },
      );
    }
    return const SizedBox.shrink();
  }

  Widget _buildFilterSection(BuildContext context) {
    final Widget filterBar = _buildFilterChipsBarListenable(context);
    if (pdfRevisionMode) {
      return filterBar;
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: <Widget>[
        Flexible(
          fit: FlexFit.loose,
          child: filterBar,
        ),
      ],
    );
  }

  Widget _buildPageSizeSelector() {
    if (segmentsPaginationController == null) {
      return const SizedBox.shrink();
    }
    return ListenableBuilder(
      listenable: segmentsPaginationController!,
      builder: (context, _) => PageSizeSelector(
        currentPageSize: segmentsPaginationController!.pageSize,
        onPageSizeChanged: (size) {
          segmentsPaginationController!.setPageSize(size);
        },
        preferenceKey: 'translation_result_segments_page_size',
        pageSizeOptions: const <int>[50, 100, 200, 500, 1000, 2000],
        showLabel: false,
      ),
    );
  }

  Widget _buildPdfRevisionPanelHeader(BuildContext context) {
    final bool showFilters = segmentMetadata.isNotEmpty &&
        exclusionFiltersListenable != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        if (showFilters) ...<Widget>[
          _buildFilterSection(context),
          const SizedBox(height: 4),
        ],
        Row(
          children: <Widget>[
            if (batchSelectionEnabled) ...<Widget>[
              _buildPdfRevisionSelectionActions(context),
            ],
            const Spacer(),
            if (pdfPageFilterListenable != null) ...<Widget>[
              _buildPdfPageFilterDropdownListenable(context),
              const SizedBox(width: 6),
            ],
            _buildPageSizeSelector(),
          ],
        ),
      ],
    );
  }

  Set<int> _currentVisibleSelectableIndices() {
    if (getFilteredSelectableSegmentIndices != null) {
      return getFilteredSelectableSegmentIndices!();
    }
    if (segmentsPaginationController == null) {
      return <int>{};
    }
    final Set<int> indices = <int>{};
    for (final SegmentPair pair in segmentsPaginationController!.items) {
      if (!pair.isImage) {
        indices.add(pair.index);
      }
    }
    return indices;
  }

  Widget _buildPdfRevisionSelectionActions(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final ButtonStyle compactStyle = TextButton.styleFrom(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      minimumSize: Size.zero,
      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      visualDensity: VisualDensity.compact,
      textStyle: const TextStyle(fontSize: 10),
    );
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        TextButton(
          style: compactStyle,
          onPressed: onBulkSelectAll == null
              ? null
              : () {
                  onBulkSelectAll!(_currentVisibleSelectableIndices());
                },
          child: Text(l10n.translationPreviewPdfRevisionSelectAll),
        ),
        TextButton(
          style: compactStyle,
          onPressed: onBulkInvertSelection == null
              ? null
              : () {
                  onBulkInvertSelection!(_currentVisibleSelectableIndices());
                },
          child: Text(l10n.translationPreviewPdfRevisionInvertSelection),
        ),
        if (onBatchFontApply != null)
          _buildBatchFontButton(context, compactStyle, l10n),
        if (onBatchFontSizeStep != null)
          _buildBatchFontSizeStepButtons(context, l10n),
      ],
    );
  }

  Widget _buildBatchFontSizeStepButtons(
    BuildContext context,
    AppLocalizations l10n,
  ) {
    Widget buildButtons(Set<int> selected) {
      final bool enabled = selected.isNotEmpty;
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          IconButton(
            icon: const Icon(Icons.text_decrease, size: 16),
            tooltip: l10n.translationPreviewBatchFontSizeDecreaseTooltip,
            onPressed: enabled
                ? () {
                    unawaited(onBatchFontSizeStep!(-kPdfFontSizeStep));
                  }
                : null,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(
              minWidth: 28,
              minHeight: 28,
            ),
            visualDensity: VisualDensity.compact,
          ),
          IconButton(
            icon: const Icon(Icons.text_increase, size: 16),
            tooltip: l10n.translationPreviewBatchFontSizeIncreaseTooltip,
            onPressed: enabled
                ? () {
                    unawaited(onBatchFontSizeStep!(kPdfFontSizeStep));
                  }
                : null,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(
              minWidth: 28,
              minHeight: 28,
            ),
            visualDensity: VisualDensity.compact,
          ),
        ],
      );
    }

    final ValueListenable<Set<int>>? listenable =
        selectedSegmentIndicesListenable;
    if (listenable != null) {
      return ValueListenableBuilder<Set<int>>(
        valueListenable: listenable,
        builder: (BuildContext context, Set<int> selected, Widget? _) {
          return buildButtons(selected);
        },
      );
    }
    return buildButtons(selectedSegmentIndices);
  }

  Widget _buildBatchFontButton(
    BuildContext context,
    ButtonStyle compactStyle,
    AppLocalizations l10n,
  ) {
    Widget buildButton(Set<int> selected) {
      return Tooltip(
        message: l10n.translationPreviewBatchFontTooltip,
        child: TextButton(
          style: compactStyle,
          onPressed: selected.isEmpty
              ? null
              : () {
                  unawaited(onBatchFontApply!());
                },
          child: Text(l10n.translationPreviewBatchFont),
        ),
      );
    }

    final ValueListenable<Set<int>>? listenable =
        selectedSegmentIndicesListenable;
    if (listenable != null) {
      return ValueListenableBuilder<Set<int>>(
        valueListenable: listenable,
        builder: (BuildContext context, Set<int> selected, Widget? _) {
          return buildButton(selected);
        },
      );
    }
    return buildButton(selectedSegmentIndices);
  }

  Widget _wrapSegmentScrollView(Widget child) {
    if (!showSegmentScrollbar) {
      return child;
    }
    return Scrollbar(
      controller: scrollController,
      thickness: 8,
      radius: const Radius.circular(4),
      thumbVisibility: true,
      child: child,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final effectiveTotal = segmentsPaginationController != null &&
            segmentsPaginationController!.total > 0
        ? segmentsPaginationController!.total
        : totalSegmentsCount;

    return RepaintBoundary(
      child: ColoredBox(
        color: scheme.surface,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            // Header with both labels and pagination bar
            Container(
              padding: EdgeInsets.symmetric(
                horizontal: pdfRevisionMode ? 7 : 8,
                vertical: 4,
              ),
              decoration: BoxDecoration(
                color: scheme.surfaceContainerHighest,
                border: Border(
                  bottom: BorderSide(color: theme.dividerColor),
                ),
              ),
              child: pdfRevisionMode
                  ? _buildPdfRevisionPanelHeader(context)
                  : Row(
                children: <Widget>[
                  if (pdfRevisionMode && batchSelectionEnabled) ...<Widget>[
                    _buildPdfRevisionSelectionActions(context),
                    const SizedBox(width: 8),
                  ],
                  // Filter chips bar (left-aligned, after bulk selection in PDF revision)
                  if (segmentMetadata.isNotEmpty &&
                      (!pdfRevisionMode || exclusionFiltersListenable != null))
                    Expanded(
                      child: _buildFilterSection(context),
                    ),
                  if (segmentMetadata.isNotEmpty &&
                      (!pdfRevisionMode || exclusionFiltersListenable != null) &&
                      !pdfRevisionMode)
                    const SizedBox(width: 8),
                  // Segment info and stats (right-aligned; PDF revision keeps only pagination)
                  if (!pdfRevisionMode)
                    Expanded(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: <Widget>[
                          ValueListenableBuilder<int?>(
                            valueListenable: highlightedIndexNotifier,
                            builder: (context, highlightedIndex, _) {
                              if (highlightedIndex != null && effectiveTotal > 0) {
                                return Padding(
                                  padding: const EdgeInsets.only(
                                    right: 4,
                                  ),
                                  child: Text(
                                    AppLocalizations.of(context)!
                                        .translationStatsSegment(
                                      (highlightedIndex + 1).toString(),
                                      effectiveTotal.toString(),
                                    ),
                                    style: TextStyle(
                                      fontSize: 10,
                                      color: scheme.onSurfaceVariant,
                                      fontWeight: FontWeight.w500,
                                    ),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                );
                              }
                              return const SizedBox.shrink();
                            },
                          ),
                          const SizedBox(width: 6),
                          Text(
                            AppLocalizations.of(context)!
                                .translationStatsDoubleClickToEdit,
                            style: TextStyle(
                              fontSize: 10,
                              color: scheme.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(width: 4),
                          if (translationState != null)
                            _buildTranslationStats(context, scheme),
                          if (segmentsPaginationController != null) ...<Widget>[
                            const SizedBox(width: 6),
                            _buildPageSizeSelector(),
                          ],
                        ],
                      ),
                    ),
                  if (pdfRevisionMode && segmentsPaginationController != null)
                    _buildPageSizeSelector(),
                ],
              ),
            ),
            // Content area with unified ListView
            Expanded(
              child: isLoading
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: <Widget>[
                          const CircularProgressIndicator(),
                          const SizedBox(height: 16),
                          Text(
                            loadingError ??
                                AppLocalizations.of(context)!
                                    .translationStatsLoadingContent,
                            style: TextStyle(color: scheme.onSurfaceVariant),
                          ),
                        ],
                      ),
                    )
                  : sourceParagraphs.isEmpty && targetParagraphs.isEmpty
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Text(
                              loadingError ??
                                  AppLocalizations.of(context)!
                                      .translationStatsNoContentAvailable,
                              textAlign: TextAlign.center,
                              style: TextStyle(color: scheme.onSurfaceVariant),
                            ),
                          ),
                        )
                      : Consumer(
                          builder: (context, ref, _) {
                            // Watch globalSettings at outer level to avoid rebuilding all items
                            // when settings change (e.g., font size)
                            final GlobalSettings globalSettings =
                                ref.watch(globalSettingsProvider);

                            // Use pagination if available and total > 0, otherwise fallback to full list
                            if (segmentsPaginationController != null &&
                                totalSegmentsCount > 0) {
                              return ListenableBuilder(
                                listenable: segmentsPaginationController!,
                                builder: (context, _) {
                                  final items =
                                      segmentsPaginationController!.items;
                                  return Column(
                                    children: <Widget>[
                                      Expanded(
                                        child: items.isEmpty
                                            ? Center(
                                                child: segmentsPaginationController!
                                                        .isLoading
                                                    ? const CircularProgressIndicator()
                                                    : Text(
                                                        AppLocalizations.of(
                                                          context,
                                                        )!
                                                            .translationStatsNoSegmentsAvailable,
                                                        style: TextStyle(
                                                          color: scheme
                                                              .onSurfaceVariant,
                                                        ),
                                                      ),
                                              )
                                            : _wrapSegmentScrollView(
                                                heightCache != null &&
                                                        segmentsPaginationController !=
                                                            null
                                                    ? PaginatedSliverList<
                                                        SegmentPair>(
                                                        key: ValueKey(
                                                          'comparison_sliver_${taskId}_$effectiveTotal',
                                                        ),
                                                        paginationController:
                                                            segmentsPaginationController!,
                                                        heightCache:
                                                            heightCache!,
                                                        scrollController:
                                                            scrollController,
                                                        totalItems:
                                                            effectiveTotal,
                                                        itemKeys:
                                                            segmentPairKeys,
                                                        itemBuilder: (
                                                          context,
                                                          index,
                                                          pair,
                                                          itemKey,
                                                        ) {
                                                          // itemKey is provided but _buildComparisonRowFromPair
                                                          // already uses segmentPairKeys[pair.index] internally
                                                          // Pass globalSettings to avoid ref.watch in itemBuilder
                                                          return _buildComparisonRowFromPair(
                                                            context,
                                                            ref,
                                                            pair,
                                                            scheme,
                                                            theme,
                                                            globalSettings,
                                                          );
                                                        },
                                                        padding:
                                                            const EdgeInsets
                                                                .all(8),
                                                      )
                                                    : ListView.builder(
                                                        controller:
                                                            scrollController,
                                                        padding:
                                                            const EdgeInsets
                                                                .all(8),
                                                        itemCount: items.length,
                                                        cacheExtent: 500,
                                                        itemBuilder: (
                                                          context,
                                                          index,
                                                        ) {
                                                          final pair =
                                                              items[index];
                                                          return _buildComparisonRowFromPair(
                                                            context,
                                                            ref,
                                                            pair,
                                                            scheme,
                                                            theme,
                                                            globalSettings,
                                                          );
                                                        },
                                                      ),
                                              ),
                                      ),
                                    ],
                                  );
                                },
                              );
                            } else {
                              // Fallback to full list (for backward compatibility)
                              final int itemCount = math.max(
                                sourceParagraphs.length,
                                targetParagraphs.length,
                              );
                              return _wrapSegmentScrollView(
                                ListView.builder(
                                  controller: scrollController,
                                  padding: const EdgeInsets.all(8),
                                  itemCount: itemCount,
                                  cacheExtent: 500,
                                  itemBuilder: (context, index) =>
                                      _buildComparisonRow(
                                    context,
                                    ref,
                                    index,
                                    scheme,
                                    theme,
                                    globalSettings,
                                  ),
                                ),
                              );
                            }
                          },
                        ),
            ),
          ],
        ),
      ),
    );
  }

  /// Build a single row from a SegmentPair (for paginated view)
  /// Performance optimization:
  /// - globalSettings passed as parameter (read at outer level)
  /// - Use ref.read for undoRedoState to avoid unnecessary rebuilds
  Widget _buildComparisonRowFromPair(
    BuildContext context,
    WidgetRef ref,
    SegmentPair pair,
    ColorScheme scheme,
    ThemeData theme,
    GlobalSettings globalSettings,
  ) =>
      ValueListenableBuilder<int?>(
        valueListenable: highlightedIndexNotifier,
        builder: (context, highlightedIdx, child) {
          final isHighlighted = highlightedIdx == pair.index;
          // Use ref.read for undoRedoState (changes less frequently than settings)
          // globalSettings is passed as parameter to avoid ref.watch in itemBuilder
          final undoRedoState =
              ref.read(translationSegmentsUndoRedoProvider(taskId));

          final canUndo = undoRedoState.canUndo(pair.index);
          final canRedo = undoRedoState.canRedo(pair.index);

          final Map<String, dynamic> metadata =
              segmentMetadata[pair.index] ?? <String, dynamic>{};
          final isExcluded = metadata['is_excluded'] as bool? ?? false;
          final exclusionReason = metadata['exclusion_reason'] as String?;

          // Apply filter: if filters are selected, only show matching segments
          if (selectedExclusionFilters != null &&
              selectedExclusionFilters!.isNotEmpty) {
            // Check if a state-based filter is active (mutually exclusive)
            final String stateFilter = selectedExclusionFilters!.firstWhere(
              (k) => _stateFilterKeys.contains(k),
              orElse: () => '',
            );

            if (stateFilter.isNotEmpty) {
              // State-based filtering
              final isImage = metadata['is_image'] as bool? ?? false;
              final isFailed = metadata['is_failed'] as bool? ?? false;
              final targetText = metadata['target_text'] as String?;
              final status = metadata['status'] as String?;
              final needsRetry = metadata['needs_retry'] as bool? ?? false;
              final isCleared = status == 'cleared';

              bool show = false;
              switch (stateFilter) {
                case 'translated':
                  show = !isImage &&
                      !isExcluded &&
                      !isFailed &&
                      !isCleared &&
                      targetText != null &&
                      targetText.isNotEmpty;
                case 'pending':
                  show = !isImage &&
                      !isExcluded &&
                      !isFailed &&
                      !isCleared &&
                      (targetText == null || targetText.isEmpty);
                case 'failed':
                  show = isFailed;
                case 'excluded':
                  show = isExcluded && !isFailed;
                case 'retry':
                  show = needsRetry || isFailed;
                case 'cleared':
                  show = isCleared;
                case 'images':
                  show = isImage;
              }

              if (!show) {
                return const SizedBox.shrink();
              }
            } else {
              // Type-based filtering (detected segment type, not excluded state)
              if (!matchesSegmentTypeFilter(
                metadata,
                selectedExclusionFilters!,
              )) {
                return const SizedBox.shrink();
              }
            }
          }

          // Build target segment widget (reused for both single-column and dual-column modes)
          final String segmentKeyPrefix =
              pdfRevisionMode ? 'pdf_revision_' : '';
          final Widget targetSegment = RepaintBoundary(
            key: ValueKey('${segmentKeyPrefix}target_${pair.index}'),
            child: TranslationSegmentItem(
              itemKey: targetItemKeys[pair.index],
              text: pair.targetText,
              sourceText: pair.sourceText,
              index: pair.index,
              isSource: false,
              isHighlighted: isHighlighted,
              isModified: modifiedSegments.containsKey(pair.index),
              platformUsed: pair.isImage
                  ? null
                  : (metadata['platform_used'] as String?),
              isFailed: pair.isImage
                  ? false
                  : (metadata['is_failed'] as bool? ?? false),
              failureReason: pair.isImage
                  ? null
                  : (metadata['failure_reason'] as String?),
              needsRetry: pair.isImage
                  ? false
                  : (metadata['needs_retry'] as bool? ?? false),
              isExcluded: pair.isExcluded,
              exclusionReason: pair.exclusionReason,
              isCleared:
                  pair.isImage ? false : _isSegmentCleared(metadata),
              onRetry: retranslatingSegments.contains(pair.index)
                  ? null
                  : onRetrySegment,
              onMarkForRetry: onMarkForRetry,
              onUnmarkForRetry: onUnmarkForRetry,
              onExclude: onExcludeSegment,
              onUnexclude: onUnexcludeSegment,
              onClear: onClearSegment,
              onUnclear: onUnclearSegment,
              onTap: () => onHighlightParagraph(pair.index),
              onEdit: (newText) => onSegmentEdit(pair.index, newText),
              onEditingStarted: onEditingStarted,
              onUndo: onUndo,
              onRedo: onRedo,
              canUndo: canUndo,
              canRedo: canRedo,
              previewFontSize: globalSettings.previewFontSize,
              editFontSize: globalSettings.editFontSize,
              imageDataMap: imageDataMap,
              taskId: taskId,
              onExclusionUpdated: onExclusionUpdated ??
                  (int index) {
                    // Fallback: Refresh segments to get updated exclusion reason
                    segmentsPaginationController?.refresh();
                  },
              onFormulaFix: onFormulaFix,
              showPdfFontSize: showPdfFontSize && !pair.isImage,
              fontSizePt: _readFontSizePt(metadata),
              computedFontSizePt:
                  _readOptionalDouble(metadata['computed_font_size_pt']),
              overlayRenderFontSizePt: _readOverlayRenderFontSizePt(metadata),
              fontSizeSource: metadata['font_size_source'] as String?,
              fontWeight: _readFontWeight(metadata),
              computedFontWeight: _readComputedFontWeight(metadata),
              fontWeightSource: metadata['font_weight_source'] as String?,
              fontStyle: _readFontStyle(metadata),
              computedFontStyle: _readComputedFontStyle(metadata),
              fontStyleSource: metadata['font_style_source'] as String?,
              leadingEm: _readLeadingEm(metadata),
              computedLeadingEm: _readComputedLeadingEm(metadata),
              leadingEmSource: metadata['leading_em_source'] as String?,
              rotation: metadata['rotation'] as int? ?? 0,
              onRotationChanged: onRotationChanged,
              onFontSizeChanged: onFontSizeChanged,
              pdfRevisionMode: pdfRevisionMode,
            ),
          );

          final Widget segmentRow = isConvertOnly
              ? targetSegment
              : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      // Source segment (left)
                      Expanded(
                        child: RepaintBoundary(
                          key: ValueKey('${segmentKeyPrefix}source_${pair.index}'),
                          child: TranslationSegmentItem(
                            itemKey: sourceItemKeys[pair.index],
                            text: pair.sourceText,
                            index: pair.index,
                            isSource: true,
                            isHighlighted: isHighlighted,
                            onTap: () => onHighlightParagraph(pair.index),
                            previewFontSize: globalSettings.previewFontSize,
                            editFontSize: globalSettings.editFontSize,
                            imageDataMap: imageDataMap,
                          ),
                        ),
                      ),
                      // Divider
                      Container(
                        width: 1,
                        color: theme.dividerColor.withOpacity(0.6),
                        margin: const EdgeInsets.symmetric(horizontal: 2),
                      ),
                      // Target segment (right)
                      Expanded(child: targetSegment),
                    ],
                  );

          final Widget rowContent = batchSelectionEnabled &&
                  onSegmentSelectionToggle != null &&
                  !pair.isImage
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Checkbox(
                        value: selectedSegmentIndices.contains(pair.index),
                        onChanged: (bool? value) {
                          onSegmentSelectionToggle!(
                            pair.index,
                            value ?? false,
                          );
                        },
                        visualDensity: VisualDensity.compact,
                      ),
                    ),
                    Expanded(child: segmentRow),
                  ],
                )
              : segmentRow;

          return Container(
            key: segmentPairKeys[pair.index],
            margin: const EdgeInsets.only(bottom: 1),
            child: rowContent,
          );
        },
      );

  /// Build a single row containing both source and target segments side by side
  /// Performance optimization: globalSettings passed as parameter
  Widget _buildComparisonRow(
    BuildContext context,
    WidgetRef ref,
    int index,
    ColorScheme scheme,
    ThemeData theme,
    GlobalSettings globalSettings,
  ) {
    // Ensure index is valid
    final hasSource = index < sourceParagraphs.length;
    final hasTarget = index < targetParagraphs.length;

    if (!hasSource && !hasTarget) {
      return const SizedBox.shrink();
    }

    return ValueListenableBuilder<int?>(
      valueListenable: highlightedIndexNotifier,
      builder: (context, highlightedIdx, child) {
        final isHighlighted = highlightedIdx == index;
        // Use ref.read for undoRedoState (changes less frequently)
        // globalSettings is passed as parameter to avoid ref.watch in itemBuilder
        final undoRedoState =
            ref.read(translationSegmentsUndoRedoProvider(taskId));

        // Get target segment metadata
        final metadata = segmentMetadata[index] ?? <String, dynamic>{};
        final platformUsed = metadata['platform_used'] as String?;
        final isImage = metadata['is_image'] as bool? ?? false;
        final isFailed = metadata['is_failed'] as bool? ?? false;
        final failureReason = metadata['failure_reason'] as String?;
        final needsRetry = metadata['needs_retry'] as bool? ?? false;
        final isRetranslating = retranslatingSegments.contains(index);
        final canUndo = undoRedoState.canUndo(index);
        final canRedo = undoRedoState.canRedo(index);
        final isExcluded = metadata['is_excluded'] as bool? ?? false;
        final exclusionReason = metadata['exclusion_reason'] as String?;
        final isCleared = isImage ? false : _isSegmentCleared(metadata);

        // Apply filter: if filters are selected, only show matching segments
        if (selectedExclusionFilters != null &&
            selectedExclusionFilters!.isNotEmpty) {
          final String stateFilter = selectedExclusionFilters!.firstWhere(
            (k) => _stateFilterKeys.contains(k),
            orElse: () => '',
          );

          if (stateFilter.isNotEmpty) {
            bool show = false;
            switch (stateFilter) {
              case 'translated':
                show = !isImage &&
                    !isExcluded &&
                    !isFailed &&
                    !isCleared &&
                    metadata['target_text'] != null &&
                    (metadata['target_text'] as String).isNotEmpty;
              case 'pending':
                show = !isImage &&
                    !isExcluded &&
                    !isFailed &&
                    !isCleared &&
                    (metadata['target_text'] == null ||
                        (metadata['target_text'] as String).isEmpty);
              case 'failed':
                show = isFailed;
              case 'excluded':
                show = isExcluded && !isFailed;
              case 'retry':
                show = needsRetry || isFailed;
              case 'cleared':
                show = isCleared;
              case 'images':
                show = isImage;
            }
            if (!show) {
              return const SizedBox.shrink();
            }
          } else {
            if (!matchesSegmentTypeFilter(
              metadata,
              selectedExclusionFilters!,
            )) {
              return const SizedBox.shrink();
            }
          }
        }

        // Build target segment widget (reused for both modes)
        final Widget targetSegmentWidget = hasTarget
            ? RepaintBoundary(
                key: ValueKey('target_$index'),
                child: TranslationSegmentItem(
                  itemKey: targetItemKeys[index],
                  text: targetParagraphs[index],
                  sourceText:
                      hasSource ? sourceParagraphs[index] : null,
                  index: index,
                  isSource: false,
                  isHighlighted: isHighlighted,
                  isModified: modifiedSegments.containsKey(index),
                  platformUsed: isImage ? null : platformUsed,
                  isFailed: isImage ? false : isFailed,
                  failureReason: isImage ? null : failureReason,
                  needsRetry: isImage ? false : needsRetry,
                  isExcluded: isExcluded,
                  exclusionReason: exclusionReason,
                  isCleared: isCleared,
                  onRetry: isRetranslating ? null : onRetrySegment,
                  onMarkForRetry: onMarkForRetry,
                  onExclude: onExcludeSegment,
                  onUnexclude: onUnexcludeSegment,
                  onClear: onClearSegment,
                  onUnclear: onUnclearSegment,
                  onTap: () => onHighlightParagraph(index),
                  onEdit: (newText) => onSegmentEdit(index, newText),
                  onEditingStarted: onEditingStarted,
                  onUndo: onUndo,
                  onRedo: onRedo,
                  canUndo: canUndo,
                  canRedo: canRedo,
                  previewFontSize: globalSettings.previewFontSize,
                  editFontSize: globalSettings.editFontSize,
                  imageDataMap: imageDataMap,
                  taskId: taskId,
                  onExclusionUpdated: onExclusionUpdated ??
                      (int index) {
                        // Fallback: Refresh segments to get updated exclusion reason
                        segmentsPaginationController?.refresh();
                      },
                  showPdfFontSize: showPdfFontSize && !isImage,
                  fontSizePt: _readFontSizePt(metadata),
                  computedFontSizePt:
                      _readOptionalDouble(metadata['computed_font_size_pt']),
                  overlayRenderFontSizePt: _readOverlayRenderFontSizePt(metadata),
                  fontSizeSource: metadata['font_size_source'] as String?,
                  fontWeight: _readFontWeight(metadata),
                  computedFontWeight: _readComputedFontWeight(metadata),
                  fontWeightSource: metadata['font_weight_source'] as String?,
                  fontStyle: _readFontStyle(metadata),
                  computedFontStyle: _readComputedFontStyle(metadata),
                  fontStyleSource: metadata['font_style_source'] as String?,
                  leadingEm: _readLeadingEm(metadata),
                  computedLeadingEm: _readComputedLeadingEm(metadata),
                  leadingEmSource: metadata['leading_em_source'] as String?,
                  rotation: metadata['rotation'] as int? ?? 0,
                  onRotationChanged: onRotationChanged,
                  onFontSizeChanged: onFontSizeChanged,
                ),
              )
            : Container(
                // Placeholder if target is missing
                height: 50,
                color: scheme.surfaceContainerHighest,
              );

        return Container(
          key: segmentPairKeys[index],
          margin: const EdgeInsets.only(
            bottom: 1,
          ), // Further reduced from 2 to 1 for more compact display
          child: isConvertOnly
              ? targetSegmentWidget
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    // Source segment (left)
                    Expanded(
                      child: hasSource
                          ? RepaintBoundary(
                              key: ValueKey('source_$index'),
                              child: TranslationSegmentItem(
                                itemKey: sourceItemKeys[index],
                                text: sourceParagraphs[index],
                                index: index,
                                isSource: true,
                                isHighlighted: isHighlighted,
                                onTap: () => onHighlightParagraph(index),
                                previewFontSize: globalSettings.previewFontSize,
                                editFontSize: globalSettings.editFontSize,
                                imageDataMap: imageDataMap,
                              ),
                            )
                          : Container(
                              // Placeholder if source is missing
                              height: 50,
                              color: scheme.surfaceContainerHighest,
                            ),
                    ),
                    // Divider
                    Container(
                      width: 1,
                      color: theme.dividerColor.withOpacity(0.6),
                      margin: const EdgeInsets.symmetric(horizontal: 2),
                    ),
                    // Target segment (right)
                    Expanded(child: targetSegmentWidget),
                  ],
                ),
        );
      },
    );
  }

  /// Build translation completion statistics widget
  Widget _buildTranslationStats(BuildContext context, ColorScheme scheme) {
    final statusText = translationState?.statusText?.toString() ?? '';
    final isCompleted = statusText.toLowerCase() == 'completed' ||
        statusText.toLowerCase() == 'failed';

    if (!isCompleted) {
      return const SizedBox.shrink();
    }

    final successCount = translationState?.successCount;
    final failCount = translationState?.failCount;
    final totalSegments = translationState?.totalSegments;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        // Success/Fail counts
        if (totalSegments != null && totalSegments > 0) ...<Widget>[
          const Icon(
            Icons.check_circle,
            size: 11,
            color: Colors.green,
          ),
          const SizedBox(width: 2),
          Text(
            '${successCount ?? 0}',
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.green,
            ),
          ),
          const SizedBox(width: 4),
          const Icon(Icons.error, size: 10, color: Colors.red),
          const SizedBox(width: 2),
          Text(
            '${failCount ?? 0}',
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.red,
            ),
          ),
          const SizedBox(width: 2),
          Text(
            '/ $totalSegments',
            style: TextStyle(
              fontSize: 10,
              color: scheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(width: 6),
        ],
        // Translation duration
        if (translationState?.totalDuration != null) ...<Widget>[
          Icon(
            Icons.timer,
            size: 11,
            color: Colors.orange.shade700,
          ),
          const SizedBox(width: 2),
          Text(
            _formatDuration(translationState!.totalDuration!),
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.orange.shade700,
            ),
          ),
          const SizedBox(width: 6),
        ],
        // Token usage statistics
        if (tokenUsage != null &&
            tokenUsage!['total_tokens'] != null &&
            tokenUsage!['total_tokens']! > 0) ...<Widget>[
          Icon(
            Icons.memory,
            size: 10,
            color: Colors.blue.shade700,
          ),
          const SizedBox(width: 2),
          Text(
            AppLocalizations.of(context)!.translationStatsTokenIn(
              _formatTokenCount(tokenUsage!['input_tokens'] ?? 0),
            ),
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.blue.shade700,
            ),
          ),
          const SizedBox(width: 3),
          Text(
            AppLocalizations.of(context)!.translationStatsTokenOut(
              _formatTokenCount(tokenUsage!['output_tokens'] ?? 0),
            ),
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: Colors.green.shade700,
            ),
          ),
          const SizedBox(width: 2),
          Text(
            AppLocalizations.of(context)!.translationStatsTokenTotal(
              _formatTokenCount(tokenUsage!['total_tokens']!),
            ),
            style: TextStyle(
              fontSize: 10,
              color: scheme.onSurfaceVariant,
            ),
          ),
        ],
      ],
    );
  }

  /// Format token count for display
  String _formatTokenCount(int count) {
    if (count < 1000) {
      return '$count';
    } else if (count < 1000000) {
      return '${(count / 1000).toStringAsFixed(1)}K';
    } else {
      return '${(count / 1000000).toStringAsFixed(1)}M';
    }
  }

  /// Format duration for display
  String _formatDuration(Duration duration) {
    final hours = duration.inHours;
    final minutes = duration.inMinutes.remainder(60);
    final seconds = duration.inSeconds.remainder(60);

    if (hours > 0) {
      return '${hours.toString().padLeft(2, '0')}:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    } else {
      return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    }
  }
}

/// Configuration for a filter chip in the filter bar.
class _FilterChipConfig {
  const _FilterChipConfig(this.key, this.label, this.color);
  final String key;
  final String label;
  final MaterialColor color;
}
