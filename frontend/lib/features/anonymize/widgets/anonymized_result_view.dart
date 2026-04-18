// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show debugPrint, kDebugMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/utils/pagination.dart';
import '../../../shared/widgets/pagination_bar.dart';
import '../../../shared/widgets/page_size_selector.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/utils/text_scroll_helper.dart';
import '../../../shared/utils/segment_scroll_helper.dart';
import '../../tasks/models/flow.dart';
import 'entity_edit_dialog.dart';
import 'entity_add_dialog.dart';
import 'entity_batch_add_dialog.dart';
import 'entity_details_dialog.dart';
import 'entity_list_widget.dart';
import '../utils/entity_group_helper.dart';
import '../models/entity_group.dart';
import 'anonymized_download_helper.dart';
import 'text_highlighter.dart';
import 'segment_loader.dart';
import '../../../shared/services/anonymize_service.dart';
import 'dart:convert';
import '../../translation/mixins/synchronized_scroll_mixin.dart';
import 'highlightable_segment_item.dart';
import 'editable_anonymized_segment_item.dart';
import '../../tasks/providers/flow_provider.dart';
import '../../tasks/providers/tasks_provider.dart';
import '../../tasks/models/task.dart';
import '../widgets/anonymization_quick_settings.dart';
import '../../translation/providers/translation_state_provider.dart';
import '../../translation/providers/translation_state_provider_family.dart';

/// Widget to display anonymized result with highlighting support
class AnonymizedResultView extends ConsumerStatefulWidget {
  const AnonymizedResultView({
    required this.originalText,
    required this.anonymizedText,
    required this.entities,
    super.key,
    this.statistics,
    this.report,
    this.flowId,
  });
  final String originalText;
  final String anonymizedText;
  final List<dynamic> entities;
  final Map<String, dynamic>? statistics;
  final Map<String, dynamic>? report;
  final String? flowId;

  @override
  ConsumerState<AnonymizedResultView> createState() =>
      _AnonymizedResultViewState();
}

class _ExitAnonymizedFullscreenIntent extends Intent {
  const _ExitAnonymizedFullscreenIntent();
}

class _AnonymizedResultViewState extends ConsumerState<AnonymizedResultView>
    with SynchronizedScrollMixin {
  int? _highlightedEntityIndex;
  final ScrollController _originalTextScrollController = ScrollController();
  final ScrollController _anonymizedTextScrollController = ScrollController();

  // GlobalKeys for highlighted text spans (same approach as translation panel)
  final Map<int, GlobalKey> _originalTextKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};
  final Map<int, GlobalKey> _anonymizedTextKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};

  // Local copy of entities for deletion
  late List<dynamic> _entities;

  // Local copy of anonymized text (updated when entities are deleted)
  late String _anonymizedText;

  // Current navigation index for "Next" button
  int _currentNavigationIndex = -1;

  // Display mode: 'text' or 'segment'
  String _displayMode = 'segment';

  // View mode notifier for EntityListWidget (true = grouped, false = flat)
  final ValueNotifier<bool> _viewModeNotifier = ValueNotifier<bool>(true);

  // Segment mode data
  List<String> _originalSegments = <String>[];
  List<String> _anonymizedSegments = <String>[];
  int? _highlightedSegmentIndex; // Primary highlighted segment (for scrolling)
  Set<int> _highlightedSegmentIndices =
      <int>{}; // All segments containing the same entity text/placeholder
  bool _loadingSegments = false;
  final Map<int, GlobalKey> _originalSegmentKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};
  final Map<int, GlobalKey> _anonymizedSegmentKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};

  // Segment boundaries for debugging (cumulative positions in full text)
  List<int> _segmentBoundaries = <int>[];

  // For highlighting text within segments
  String?
      _highlightedTextInSegment; // The text to highlight in the current segment
  String?
      _highlightedPlaceholderInSegment; // The placeholder to highlight in the anonymized segment

  // Segment heights for alignment (calculated once, stored per index)
  final Map<String, double> _segmentHeightCache = <String, double>{};

  // Pagination controllers
  PagedListController<String>? _segmentPaginationController;
  PagedListController<String>? _textPaginationController;

  // Text mode pagination: current page text ranges
  String _currentPageOriginalText = '';
  String _currentPageAnonymizedText = '';
  bool _isFullscreen = false;
  OverlayEntry? _fullscreenOverlayEntry;

  @override
  void initState() {
    super.initState();
    // Debug: Log the received data
    debugPrint(
      '[AnonymizedResultView] initState: originalText.len=${widget.originalText.length}, anonymizedText.len=${widget.anonymizedText.length}, entities.len=${widget.entities.length}',
    );

    _entities = List<dynamic>.from(widget.entities);
    _anonymizedText = widget.anonymizedText;

    // Initialize text pagination variables with full text as fallback
    _currentPageOriginalText = widget.originalText;
    _currentPageAnonymizedText = _anonymizedText;

    // Initialize synchronized scrolling for segment mode
    initSynchronizedScroll(
      controller1: _originalTextScrollController,
      controller2: _anonymizedTextScrollController,
    );

    // Load segments if in segment mode (default)
    if (_displayMode == 'segment') {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _originalSegments.isEmpty && !_loadingSegments) {
          _loadSegments();
        }
      });
    }
  }

  @override
  void dispose() {
    _originalTextScrollController.dispose();
    _anonymizedTextScrollController.dispose();
    _segmentPaginationController?.dispose();
    _textPaginationController?.dispose();
    _fullscreenOverlayEntry?.remove();
    _fullscreenOverlayEntry = null;
    super.dispose(); // SynchronizedScrollMixin.dispose() will be called
  }

  Future<void> _loadSegments() async {
    if (widget.flowId == null) {
      setState(() {
        _loadingSegments = false;
        _originalSegments = <String>[];
        _anonymizedSegments = <String>[];
      });
      return;
    }

    setState(() {
      _loadingSegments = true;
    });

    try {
      // Try to restore segments from FlowContext cache first
      final flow = ref.read(flowProviderFamily(widget.flowId!));
      final artifacts = flow.context.anonymize;

      if (artifacts.originalSegments != null &&
          artifacts.originalSegments!.isNotEmpty &&
          artifacts.anonymizedSegments != null &&
          artifacts.anonymizedSegments!.isNotEmpty) {
        // Use cached segments
        _originalSegments = List<String>.from(artifacts.originalSegments!);
        _anonymizedSegments = List<String>.from(artifacts.anonymizedSegments!);

        // Calculate segment boundaries from segments
        _segmentBoundaries = <int>[0];
        int currentPos = 0;
        for (int i = 0; i < _originalSegments.length; i++) {
          currentPos += _originalSegments[i].length;
          _segmentBoundaries.add(currentPos);
        }

        if (kDebugMode) {
          debugPrint(
            '[AnonymizedResultView] _loadSegments: Restored ${_originalSegments.length} segments from FlowContext cache, flowId=${widget.flowId}',
          );
        }
      } else {
        // No cached segments, load from backend
        // Get taskId from translation state
        final dynamic translationState = widget.flowId != null
            ? ref.read(translationStateProviderFamily(widget.flowId!))
            : ref.read(translationStateProvider);

        final taskId = translationState.taskId;

        SegmentLoadResult result;
        if (taskId == null || (taskId as String).isEmpty) {
          // No taskId available, split text manually
          result = SegmentLoader.splitTextIntoSegments(
            originalText: widget.originalText,
            entities: _entities,
          );
        } else {
          // Load segments from translation service
          result = await SegmentLoader.loadSegments(
            flowId: widget.flowId,
            taskId: taskId,
            entities: _entities,
            ref: ref,
          );
        }

        _originalSegments = result.originalSegments;
        _anonymizedSegments = result.anonymizedSegments;
        _segmentBoundaries = result.segmentBoundaries;

        // Cache segments to FlowContext for later use (e.g., export)
        if (widget.flowId != null &&
            _originalSegments.isNotEmpty &&
            _anonymizedSegments.isNotEmpty) {
          try {
            final flowNotifier =
                ref.read(flowProviderFamily(widget.flowId!).notifier);
            final currentArtifacts =
                ref.read(flowProviderFamily(widget.flowId!)).context.anonymize;
            // Update artifacts with segments cache, preserving existing data
            flowNotifier.setAnonymizeArtifacts(
              currentArtifacts.copyWith(
                originalSegments: _originalSegments,
                anonymizedSegments: _anonymizedSegments,
              ),
            );
            if (kDebugMode) {
              debugPrint(
                '[AnonymizedResultView] _loadSegments: Cached ${_originalSegments.length} segments to FlowContext, flowId=${widget.flowId}',
              );
            }
          } catch (e) {
            if (kDebugMode) {
              debugPrint(
                '[AnonymizedResultView] _loadSegments: Failed to cache segments to FlowContext: $e',
              );
            }
          }
        }
      }

      // Calculate and update segmentIndex for entities that don't have it
      _calculateSegmentIndicesForEntities();

      // Initialize keys for all segments
      _originalSegmentKeys.clear();
      _anonymizedSegmentKeys.clear();

      // Calculate segment heights for alignment
      _calculateSegmentHeights();
      for (int i = 0; i < _originalSegments.length; i++) {
        _originalSegmentKeys[i] = GlobalKey();
        _anonymizedSegmentKeys[i] = GlobalKey();
      }

      // Initialize segment pagination controller
      _initializeSegmentPagination();

      setState(() {
        _loadingSegments = false;
      });
    } catch (e) {
      // Fallback: split text manually
      final result = SegmentLoader.splitTextIntoSegments(
        originalText: widget.originalText,
        entities: _entities,
      );
      _originalSegments = result.originalSegments;
      _anonymizedSegments = result.anonymizedSegments;
      _segmentBoundaries = result.segmentBoundaries;

      // Calculate and update segmentIndex for entities that don't have it
      _calculateSegmentIndicesForEntities();

      // Initialize keys
      _originalSegmentKeys.clear();
      _anonymizedSegmentKeys.clear();

      // Calculate segment heights for alignment
      _calculateSegmentHeights();
      for (int i = 0; i < _originalSegments.length; i++) {
        _originalSegmentKeys[i] = GlobalKey();
        _anonymizedSegmentKeys[i] = GlobalKey();
      }

      // Initialize segment pagination controller
      _initializeSegmentPagination();

      // Initialize text pagination if in text mode
      // Note: Don't initialize pagination if we're already displaying text
      // This prevents the loading indicator from appearing
      if (_displayMode == 'text' && _textPaginationController == null) {
        // Only initialize if not already initialized
        _initializeTextPagination();
      }

      setState(() {
        _loadingSegments = false;
      });
    }
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
    final overlay = Overlay.of(context, rootOverlay: true);
    _fullscreenOverlayEntry = OverlayEntry(
      builder: (overlayContext) => RepaintBoundary(
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
                  child: _buildMainContent(isFullscreenView: true),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    overlay.insert(_fullscreenOverlayEntry!);
    setState(() {
      _isFullscreen = true;
    });
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

  /// Calculate segmentIndex for entities based on start position and actual segment boundaries
  /// This ensures segmentIndex is always calculated from the actual segments, not from plain text
  void _calculateSegmentIndicesForEntities() {
    if (_segmentBoundaries.isEmpty || _originalSegments.isEmpty) return;

    for (int i = 0; i < _entities.length; i++) {
      final entity =
          _entities[i] as Map<String, dynamic>? ?? <String, dynamic>{};
      final start = entity['start'] as int?;

      if (start == null) continue;

      // Always recalculate segmentIndex based on actual segment boundaries
      // This ensures we use the correct segments, not plain text boundaries
      int? calculatedSegmentIndex;
      for (int segIdx = 0; segIdx < _segmentBoundaries.length - 1; segIdx++) {
        if (start >= _segmentBoundaries[segIdx] &&
            start < _segmentBoundaries[segIdx + 1]) {
          calculatedSegmentIndex = segIdx;
          break;
        }
      }

      // If position is at or after last boundary, use last segment
      if (calculatedSegmentIndex == null && _segmentBoundaries.isNotEmpty) {
        if (start >= _segmentBoundaries[_segmentBoundaries.length - 1]) {
          calculatedSegmentIndex = _segmentBoundaries.length - 2;
          if (calculatedSegmentIndex < 0) calculatedSegmentIndex = 0;
        }
      }

      // Update the entity with calculated segmentIndex
      if (calculatedSegmentIndex != null &&
          calculatedSegmentIndex < _originalSegments.length) {
        final updatedEntity = Map<String, dynamic>.from(entity);
        updatedEntity['segmentIndex'] = calculatedSegmentIndex;
        _entities[i] = updatedEntity;
      }
    }
  }

  void _initializeSegmentPagination() {
    if (_originalSegments.isEmpty) return;

    _segmentPaginationController?.dispose();
    _segmentPaginationController = PagedListController<String>(
      fetcher: (offset, limit) async {
        // Return paginated segments
        final total = _originalSegments.length;
        final end = (offset + limit).clamp(0, total);
        final items = _originalSegments.sublist(offset.clamp(0, total), end);
        return <String, dynamic>{
          'items': items,
          'total': total,
          'offset': offset,
          'limit': limit,
        };
      },
      // itemConverter not needed - items are already String type
    );

    _segmentPaginationController!.addListener(() {
      if (mounted) {
        setState(_updateSegmentKeysForPagination);
      }
    });

    // Load first page
    _segmentPaginationController!.loadFirstPage();
  }

  void _updateSegmentKeysForPagination() {
    if (_segmentPaginationController == null) return;

    final items = _segmentPaginationController!.items;
    final offset = _segmentPaginationController!.offset;

    // Update keys only for current page items
    for (int i = 0; i < items.length; i++) {
      final globalIndex = offset + i;
      if (!_originalSegmentKeys.containsKey(globalIndex)) {
        _originalSegmentKeys[globalIndex] = GlobalKey();
      }
      if (!_anonymizedSegmentKeys.containsKey(globalIndex)) {
        _anonymizedSegmentKeys[globalIndex] = GlobalKey();
      }
    }
  }

  void _initializeTextPagination() {
    if (_originalSegments.isEmpty || _segmentBoundaries.isEmpty) return;

    // Don't reinitialize if already initialized
    if (_textPaginationController != null) return;

    _textPaginationController = PagedListController<String>(
      fetcher: (offset, limit) async {
        // Calculate text range for current page based on segments
        final total = _originalSegments.length;
        final startSegmentIndex = offset.clamp(0, total - 1);
        final endSegmentIndex = (offset + limit).clamp(0, total);

        // Get text boundaries for these segments
        // segmentBoundaries[i] is the start position of segment i
        // segmentBoundaries[i+1] is the end position of segment i
        final startPos = startSegmentIndex < _segmentBoundaries.length
            ? _segmentBoundaries[startSegmentIndex]
            : widget.originalText.length;
        final endPos = endSegmentIndex < _segmentBoundaries.length
            ? _segmentBoundaries[endSegmentIndex]
            : widget.originalText.length;

        // Extract text for this page
        final pageOriginalText =
            widget.originalText.substring(startPos, endPos);

        return <String, dynamic>{
          'items': <String>[
            pageOriginalText,
          ], // Single item representing the page text
          'total': total,
          'offset': offset,
          'limit': limit,
        };
      },
      // itemConverter not needed - items are already String type
    );

    _textPaginationController!.addListener(() {
      if (mounted) {
        setState(_updateTextForPagination);
      }
    });

    // Pre-populate first page text before loading to avoid showing loading indicator
    // This ensures text is displayed immediately even while loadFirstPage() is running
    _updateTextForPagination();

    // Load first page asynchronously (won't show loading indicator since we pre-populated)
    _textPaginationController!.loadFirstPage();
  }

  void _updateTextForPagination() {
    // If pagination controller is not ready or segments are not loaded, use full text
    if (_textPaginationController == null ||
        _originalSegments.isEmpty ||
        _segmentBoundaries.isEmpty) {
      // Keep current text or fallback to full text
      if (_currentPageOriginalText.isEmpty) {
        _currentPageOriginalText = widget.originalText;
      }
      if (_currentPageAnonymizedText.isEmpty) {
        _currentPageAnonymizedText = _anonymizedText;
      }
      return;
    }

    // If controller is loading, don't update text (keep current text)
    if (_textPaginationController!.isLoading) {
      return;
    }

    final offset = _textPaginationController!.offset;
    final pageSize = _textPaginationController!.pageSize;
    final total = _originalSegments.length;

    final startSegmentIndex = offset.clamp(0, total - 1);
    final endSegmentIndex = (offset + pageSize).clamp(0, total);

    // Get text boundaries for these segments
    // segmentBoundaries[i] is the start position of segment i
    // segmentBoundaries[i+1] is the end position of segment i
    final startPos = startSegmentIndex < _segmentBoundaries.length
        ? _segmentBoundaries[startSegmentIndex]
        : widget.originalText.length;
    final endPos = endSegmentIndex < _segmentBoundaries.length
        ? _segmentBoundaries[endSegmentIndex]
        : widget.originalText.length;

    // Extract text for this page
    _currentPageOriginalText = widget.originalText.substring(startPos, endPos);
    _currentPageAnonymizedText = _anonymizedText.substring(startPos, endPos);
  }

  void _calculateSegmentHeights() {
    _segmentHeightCache.clear();
  }

  double _getSegmentHeight(int index, double maxWidth) {
    if (index < 0 ||
        index >= _originalSegments.length ||
        index >= _anonymizedSegments.length) {
      return 80;
    }

    final widthKey =
        maxWidth.isFinite ? maxWidth.toStringAsFixed(1) : 'default';
    final cacheKey = '$widthKey-$index';
    final cached = _segmentHeightCache[cacheKey];
    if (cached != null) return cached;

    // Estimate available width for the text area (remove padding + badge)
    final textWidth = (maxWidth - 90).clamp(120.0, maxWidth);
    const textStyle = TextStyle(
      fontSize: 14,
      height: 1.35,
      fontFamily: 'monospace',
    );
    final textPainter = TextPainter(
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.left,
    );

    textPainter.text = TextSpan(
      text: _originalSegments[index],
      style: textStyle,
    );
    textPainter.layout(maxWidth: textWidth);
    final originalHeight = textPainter.size.height;

    textPainter.text = TextSpan(
      text: _anonymizedSegments[index],
      style: textStyle,
    );
    textPainter.layout(maxWidth: textWidth);
    final anonymizedHeight = textPainter.size.height;

    const padding = 16;
    const badgeHeight = 24;
    final computedHeight = (originalHeight > anonymizedHeight
            ? originalHeight
            : anonymizedHeight) +
        padding +
        badgeHeight;

    final finalHeight = computedHeight < 60.0 ? 60.0 : computedHeight;
    _segmentHeightCache[cacheKey] = finalHeight;
    return finalHeight;
  }

  void _highlightSegment(
    int index, {
    String? highlightText,
    String? highlightPlaceholder,
  }) {
    // Find all segments containing the same text/placeholder (for text highlighting within segments)
    final textHighlightIndices = <int>{};
    if (highlightText != null && highlightText.isNotEmpty) {
      for (int i = 0; i < _originalSegments.length; i++) {
        if (_originalSegments[i].contains(highlightText)) {
          textHighlightIndices.add(i);
        }
      }
    } else if (highlightPlaceholder != null &&
        highlightPlaceholder.isNotEmpty) {
      for (int i = 0; i < _anonymizedSegments.length; i++) {
        if (_anonymizedSegments[i].contains(highlightPlaceholder)) {
          textHighlightIndices.add(i);
        }
      }
    }

    // Find entities in this segment and select the first one
    // Also collect all entity texts/placeholders in this segment for highlighting
    int? entityIndexToSelect;
    final entityTextsInSegment = <String>{};
    final placeholdersInSegment = <String>{};

    if (index >= 0 && index < _originalSegments.length) {
      // Calculate segment boundaries if available
      int segmentStart = 0;
      int segmentEnd = widget.originalText.length;

      if (_segmentBoundaries.isNotEmpty) {
        segmentStart =
            index < _segmentBoundaries.length ? _segmentBoundaries[index] : 0;
        segmentEnd = index + 1 < _segmentBoundaries.length
            ? _segmentBoundaries[index + 1]
            : widget.originalText.length;
      } else {
        // Fallback: calculate segment boundaries from segments
        for (int i = 0; i < index; i++) {
          if (i < _originalSegments.length) {
            segmentStart += _originalSegments[i].length;
          }
        }
        if (index < _originalSegments.length) {
          segmentEnd = segmentStart + _originalSegments[index].length;
        }
      }

      // Find entities that are within this segment
      for (int i = 0; i < _entities.length; i++) {
        final entity =
            _entities[i] as Map<String, dynamic>? ?? <String, dynamic>{};
        final entityStart = entity['start'] as int?;
        final entitySegmentIndex = entity['segmentIndex'] as int?;

        // Check if entity is in this segment by segmentIndex (preferred) or position
        bool isInSegment = false;
        if (entitySegmentIndex != null && entitySegmentIndex == index) {
          // Direct match by segmentIndex (most reliable)
          isInSegment = true;
        } else if (entityStart != null) {
          // Fallback: check by position range
          if (entityStart >= segmentStart && entityStart < segmentEnd) {
            isInSegment = true;
          }
        }

        if (isInSegment) {
          // Collect entity text and placeholder for highlighting
          final entityText = entity['text']?.toString() ?? '';
          final placeholder = entity['placeholder']?.toString() ?? '';
          if (entityText.isNotEmpty) {
            entityTextsInSegment.add(entityText);
          }
          if (placeholder.isNotEmpty) {
            placeholdersInSegment.add(placeholder);
          }

          // Select the first entity found
          entityIndexToSelect ??= i;
        }
      }
    }

    // If no specific highlightText/highlightPlaceholder provided, use all texts/placeholders in segment
    String? finalHighlightText = highlightText;
    String? finalHighlightPlaceholder = highlightPlaceholder;

    if (finalHighlightText == null && entityTextsInSegment.isNotEmpty) {
      // Use the first entity text for highlighting (or could use all)
      finalHighlightText = entityTextsInSegment.first;
    }
    if (finalHighlightPlaceholder == null && placeholdersInSegment.isNotEmpty) {
      // Use the first placeholder for highlighting (or could use all)
      finalHighlightPlaceholder = placeholdersInSegment.first;
    }

    // Update text highlight indices based on final highlight text/placeholder
    if (finalHighlightText != null && finalHighlightText.isNotEmpty) {
      textHighlightIndices.clear();
      for (int i = 0; i < _originalSegments.length; i++) {
        if (_originalSegments[i].contains(finalHighlightText)) {
          textHighlightIndices.add(i);
        }
      }
    } else if (finalHighlightPlaceholder != null &&
        finalHighlightPlaceholder.isNotEmpty) {
      textHighlightIndices.clear();
      for (int i = 0; i < _anonymizedSegments.length; i++) {
        if (_anonymizedSegments[i].contains(finalHighlightPlaceholder)) {
          textHighlightIndices.add(i);
        }
      }
    }

    setState(() {
      _highlightedSegmentIndex =
          index; // Only current entity's segment gets border highlight
      _highlightedSegmentIndices =
          textHighlightIndices; // All segments with same text/placeholder get text highlight
      _highlightedTextInSegment = finalHighlightText;
      _highlightedPlaceholderInSegment = finalHighlightPlaceholder;

      // Select entity in this segment if found
      if (entityIndexToSelect != null) {
        _highlightedEntityIndex = entityIndexToSelect;
        _currentNavigationIndex = entityIndexToSelect;
      } else {
        // Clear entity selection if no entity in this segment
        _highlightedEntityIndex = null;
        _currentNavigationIndex = -1;
      }
    });

    // Scroll to primary segment with retry mechanism using GlobalKey (preferred) or index (fallback)
    // Use post-frame callback to ensure widgets are rendered
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;

      // Scroll original text segment with retry mechanism
      final originalKey = _originalSegmentKeys[index];
      SegmentScrollHelper.scrollToSegment(
        segmentKey: originalKey,
        index: index,
        scrollController: _originalTextScrollController,
      );

      // Scroll anonymized text segment with retry mechanism
      final anonymizedKey = _anonymizedSegmentKeys[index];
      SegmentScrollHelper.scrollToSegment(
        segmentKey: anonymizedKey,
        index: index,
        scrollController: _anonymizedTextScrollController,
      );
    });
  }

  /// Show detailed information dialog for an entity
  void _showEntityDetailsDialog(Map<String, dynamic> entity) {
    showDialog(
      context: context,
      builder: (BuildContext context) => EntityDetailsDialog(
        entity: entity,
        originalSegments: _originalSegments,
        segmentBoundaries: _segmentBoundaries,
        entities: _entities,
      ),
    );
  }

  void _deleteEntity(int index) {
    if (_entities.isEmpty || index < 0 || index >= _entities.length) {
      return;
    }

    final entityToDelete =
        _entities[index] as Map<String, dynamic>? ?? <String, dynamic>{};
    final placeholder = entityToDelete['placeholder']?.toString() ?? '';

    setState(() {
      // Remove entity from list
      _entities = List<dynamic>.from(_entities)..removeAt(index);

      // Clear highlight if deleted entity was highlighted
      if (_highlightedEntityIndex == index) {
        _highlightedEntityIndex = null;
      } else if (_highlightedEntityIndex != null &&
          _highlightedEntityIndex! > index) {
        // Adjust highlight index if entity before it was deleted
        _highlightedEntityIndex = _highlightedEntityIndex! - 1;
      }
    });

    // Rebuild anonymized text/segments so the removed placeholder falls back to original text
    _updateAnonymizedText();

    if (mounted) {
      final message = placeholder.isNotEmpty
          ? 'Placeholder $placeholder restored to original text'
          : 'Entity deleted';
      MessageService.showSuccess(context, message);
    }
  }

  /// Edit entity: show dialog with segment text and allow user to select text range
  void _editEntity(int index) {
    if (_entities.isEmpty || index < 0 || index >= _entities.length) {
      return;
    }

    final entity =
        _entities[index] as Map<String, dynamic>? ?? <String, dynamic>{};
    final segmentIndex = entity['segmentIndex'] as int?;
    final entityStart = entity['start'] as int?;
    final entityEnd = entity['end'] as int?;

    // Get segment text
    String segmentText = '';
    int segmentStartInFullText = 0;
    int actualSegmentIndex = 0;

    if (segmentIndex != null && segmentIndex < _originalSegments.length) {
      segmentText = _originalSegments[segmentIndex];
      actualSegmentIndex = segmentIndex;
      // Calculate segment start position in full text
      if (segmentIndex < _segmentBoundaries.length) {
        segmentStartInFullText = _segmentBoundaries[segmentIndex];
      }
    } else {
      // Fallback: use full text if segment not available
      segmentText = widget.originalText;
      segmentStartInFullText = 0;
      actualSegmentIndex = 0;
    }

    // Calculate entity position within segment
    int entityStartInSegment = 0;
    int entityEndInSegment = 0;
    if (entityStart != null && entityEnd != null) {
      entityStartInSegment = entityStart - segmentStartInFullText;
      entityEndInSegment = entityEnd - segmentStartInFullText;
      // Clamp to segment bounds
      if (entityStartInSegment < 0) entityStartInSegment = 0;
      if (entityEndInSegment > segmentText.length) {
        entityEndInSegment = segmentText.length;
      }
      if (entityStartInSegment > segmentText.length) {
        entityStartInSegment = segmentText.length;
      }
    }

    showDialog(
      context: context,
      builder: (BuildContext context) => EntityEditDialog(
        entity: entity,
        segmentText: segmentText,
        segmentIndex: actualSegmentIndex,
        segmentStartInFullText: segmentStartInFullText,
        entityStartInSegment: entityStartInSegment,
        entityEndInSegment: entityEndInSegment,
      ),
    ).then((result) async {
      if (result != null && result is Map<String, dynamic>) {
        // Backend-driven: expand → rebuild using updated text/type
        final updatedText = result['text']?.toString() ?? '';
        final updatedType = result['type']?.toString() ??
            (entity['type']?.toString() ?? 'UNKNOWN');
        await _expandAndRebuildWithSeeds(
          seeds: <Map<String, String>>[
            <String, String>{'text': updatedText, 'type': updatedType},
          ],
        );
        if (mounted) MessageService.showSuccess(context, 'Entity updated');
      }
    });
  }

  /// Add new entity: show dialog to select text and create new entity
  void _addEntity({String? prefillText, String? prefillType}) {
    // Determine which segment to show (prioritize current highlighted segment)
    String segmentText = '';
    int segmentStartInFullText = 0;
    int actualSegmentIndex = 0;

    if (_displayMode == 'segment' &&
        _highlightedSegmentIndex != null &&
        _highlightedSegmentIndex! < _originalSegments.length) {
      // Use currently highlighted segment
      segmentText = _originalSegments[_highlightedSegmentIndex!];
      actualSegmentIndex = _highlightedSegmentIndex!;
      if (_highlightedSegmentIndex! < _segmentBoundaries.length) {
        segmentStartInFullText = _segmentBoundaries[_highlightedSegmentIndex!];
      }
    } else if (_displayMode == 'segment' && _originalSegments.isNotEmpty) {
      // Use first segment
      segmentText = _originalSegments[0];
      actualSegmentIndex = 0;
      if (_segmentBoundaries.isNotEmpty) {
        segmentStartInFullText = _segmentBoundaries[0];
      }
    } else {
      // Fallback: use full text
      segmentText = widget.originalText;
      segmentStartInFullText = 0;
      actualSegmentIndex = 0;
    }

    // Get anonymize mode and custom placeholder
    final anonymizeQs = widget.flowId != null
        ? ref.read(anonymizationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(anonymizationQuickSettingsProvider);
    final anonymizeMode = anonymizeQs.anonymizeMode;
    final customPlaceholder = anonymizeQs.customPlaceholder;

    showDialog(
      context: context,
      builder: (BuildContext context) => EntityAddDialog(
        segmentText: segmentText,
        segmentIndex: actualSegmentIndex,
        segmentStartInFullText: segmentStartInFullText,
        originalText: widget.originalText,
        anonymizeMode: anonymizeMode,
        customPlaceholder: customPlaceholder,
        existingEntities: _entities,
        prefillText: prefillText,
        prefillType: prefillType,
      ),
    ).then((result) async {
      if (result != null && result is Map<String, dynamic>) {
        final entityText = result['text']?.toString() ?? '';
        final entityType = result['type']?.toString() ?? 'UNKNOWN';
        if (entityText.isEmpty) return;
        await _expandAndRebuildWithSeeds(
          seeds: <Map<String, String>>[
            <String, String>{'text': entityText, 'type': entityType},
          ],
        );
        if (mounted) MessageService.showSuccess(context, 'Entity added');
      }
    });
  }

  /// Add missing placeholder entities
  void _addMissingPlaceholder(String placeholder) {
    // Find all positions of this placeholder
    final positions = EntityGroupHelper.findPlaceholderPositions(
      _anonymizedText,
      placeholder,
    );

    if (positions.isEmpty) {
      if (mounted) {
        MessageService.showError(
          context,
          'No occurrences found for $placeholder',
        );
      }
      return;
    }

    // Get anonymize mode and custom placeholder
    final anonymizeQs = widget.flowId != null
        ? ref.read(anonymizationQuickSettingsProviderFamily(widget.flowId!))
        : ref.read(anonymizationQuickSettingsProvider);
    final anonymizeMode = anonymizeQs.anonymizeMode;
    final customPlaceholder = anonymizeQs.customPlaceholder;

    // Show batch add dialog
    showDialog(
      context: context,
      builder: (BuildContext context) => EntityBatchAddDialog(
        placeholder: placeholder,
        positions: positions,
        anonymizedText: _anonymizedText,
        originalText: widget.originalText,
        segmentBoundaries: _segmentBoundaries,
        originalSegments: _originalSegments,
        anonymizeMode: anonymizeMode,
        customPlaceholder: customPlaceholder,
      ),
    ).then((result) {
      if (result != null && result is List<Map<String, dynamic>>) {
        // Add all new entities
        setState(() {
          for (final entity in result) {
            _entities.add(entity);
          }
        });

        // Update anonymized text
        _updateAnonymizedText();

        // Highlight the first added entity
        if (result.isNotEmpty) {
          final newIndex = _entities.length - result.length;
          setState(() {
            _highlightedEntityIndex = newIndex;
            _currentNavigationIndex = newIndex;
          });

          // If in segment mode, highlight the segment
          final segmentIndex = result[0]['segmentIndex'] as int?;
          if (_displayMode == 'segment' && segmentIndex != null) {
            _highlightSegment(
              segmentIndex,
              highlightText: result[0]['text']?.toString(),
              highlightPlaceholder: placeholder,
            );
          } else {
            _onEntityTap(newIndex);
          }
        }

        if (mounted) {
          MessageService.showSuccess(
            context,
            'Added ${result.length} entity(ies)',
          );
        }
      }
    });
  }

  /// Update anonymized text based on current entities
  /// Handles multiple entities in the same segment correctly by sorting and replacing from end to start
  void _updateAnonymizedText() {
    // If displaying text mode and we have segments and workflow, rebuild full text via backend (keeps consistency with segment view)
    final canRebuildFromSegments = _displayMode == 'text' &&
        _originalSegments.isNotEmpty &&
        _anonymizedSegments.isNotEmpty &&
        widget.flowId != null &&
        (ref
                .read(flowProviderFamily(widget.flowId!))
                .context
                .anonymize
                .workflowId !=
            null);

    if (canRebuildFromSegments) {
      // Build segments data and request backend to rebuild full anonymized document
      final flow = ref.read(flowProviderFamily(widget.flowId!));
      final workflowId = flow.context.anonymize.workflowId!;
      final segmentsData = <Map<String, dynamic>>[];
      final len = _anonymizedSegments.length;
      for (int i = 0; i < len; i++) {
        final originalSeg =
            i < _originalSegments.length ? _originalSegments[i] : '';
        final anonymizedSeg = _anonymizedSegments[i];
        segmentsData.add(<String, dynamic>{
          'segment_index': i,
          'original_text': originalSeg,
          'anonymized_text': anonymizedSeg,
        });
      }

      // Rebuild full text from segments via backend API
      Future<void> rebuildText() async {
        try {
          final anonymizeService = AnonymizeService();
          final bytes = await anonymizeService.rebuildDocumentFromSegments(
            workflowId,
            segmentsData,
          );
          final rebuilt = utf8.decode(bytes);
          if (mounted) {
            setState(() {
              _anonymizedText = rebuilt;
            });
          }
        } catch (e) {
          debugPrint(
            '[updateAnonymizedText] Failed to rebuild from segments: $e',
          );
          // Fallback to local generation on error
          final fallback = AnonymizedTextUpdater.updateAnonymizedText(
            originalText: widget.originalText,
            entities: _entities,
          );
          if (mounted) {
            setState(() {
              _anonymizedText = fallback;
            });
          }
        }
      }

      rebuildText();
    } else {
      final result = AnonymizedTextUpdater.updateAnonymizedText(
        originalText: widget.originalText,
        entities: _entities,
      );
      setState(() {
        _anonymizedText = result;
      });
    }

    // Update anonymized segments to keep segment mode in sync
    if (_originalSegments.isNotEmpty) {
      _anonymizedSegments = AnonymizedTextUpdater.updateAnonymizedSegments(
        originalSegments: _originalSegments,
        entities: _entities,
        segmentBoundaries: _segmentBoundaries,
      );
      // Recalculate segment heights only when segment mode is active
      if (_displayMode == 'segment') {
        _calculateSegmentHeights();
      }
    }

    // Update flow context if available
    if (widget.flowId != null) {
      try {
        final flowNotifier =
            ref.read(flowProviderFamily(widget.flowId!).notifier);
        final currentFlow = ref.read(flowProviderFamily(widget.flowId!));
        final currentArtifacts = currentFlow.context.anonymize;

        // Update mappings
        final updatedMappings = Map<String, dynamic>.from(
          currentArtifacts.mappings ?? <dynamic, dynamic>{},
        );
        final placeholdersToKeep = <String>{};
        for (final entity in _entities) {
          final entityMap =
              entity as Map<String, dynamic>? ?? <String, dynamic>{};
          final placeholder = entityMap['placeholder']?.toString() ?? '';
          final text = entityMap['text']?.toString() ?? '';
          if (placeholder.isNotEmpty && text.isNotEmpty) {
            updatedMappings[placeholder] = text;
            placeholdersToKeep.add(placeholder);
          }
        }
        updatedMappings.removeWhere(
          (key, value) => !placeholdersToKeep.contains(key),
        );

        flowNotifier.setAnonymizeArtifacts(
          currentArtifacts.copyWith(
            anonymizedText: _anonymizedText,
            mappings: updatedMappings,
            entitiesExpanded: List<dynamic>.from(_entities),
          ),
        );
      } catch (e) {
        // Ignore errors
      }
    }
  }

  Future<void> _downloadAnonymized() async {
    if (widget.flowId == null) {
      if (mounted) {
        MessageService.showError(context, 'Flow ID is required for download');
      }
      return;
    }

    final flow = ref.read(flowProviderFamily(widget.flowId!));
    if (flow.context.anonymize.workflowId == null) {
      if (mounted) {
        MessageService.showError(context, 'No anonymized document to download');
      }
      return;
    }

    final originalFileName =
        flow.context.source.fileName ?? 'anonymized_document';

    try {
      if (_displayMode == 'text') {
        await AnonymizedDownloadHelper.downloadTextMode(
          context: context,
          anonymizedText: _anonymizedText,
          originalFileName: originalFileName,
        );
      } else {
        await AnonymizedDownloadHelper.downloadSegmentMode(
          context: context,
          workflowId: flow.context.anonymize.workflowId!,
          originalSegments: _originalSegments,
          anonymizedSegments: _anonymizedSegments,
          originalFileName: originalFileName,
        );
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to download: $e');
      }
    }
  }

  Future<void> _copyAnonymized() async {
    try {
      String textToCopy;

      if (_displayMode == 'text') {
        // Text mode: use the anonymized text directly
        textToCopy = _anonymizedText;
      } else {
        // Segment mode: use the same logic as download (rebuild from segments via API)
        if (widget.flowId == null) {
          if (mounted) {
            MessageService.showError(context, 'Flow ID is required for copy');
          }
          return;
        }

        final flow = ref.read(flowProviderFamily(widget.flowId!));
        if (flow.context.anonymize.workflowId == null) {
          if (mounted) {
            MessageService.showError(context, 'No anonymized document to copy');
          }
          return;
        }

        if (_originalSegments.isEmpty || _anonymizedSegments.isEmpty) {
          if (mounted) {
            MessageService.showError(
              context,
              'Segments not loaded. Please wait for segments to load.',
            );
          }
          return;
        }

        if (_anonymizedSegments.length != _originalSegments.length) {
          if (mounted) {
            MessageService.showError(
              context,
              'Segment count mismatch. Please reload segments.',
            );
          }
          return;
        }

        // Build segments data (same as download)
        final segmentsData = <Map<String, dynamic>>[];
        for (int i = 0; i < _anonymizedSegments.length; i++) {
          final originalSeg =
              i < _originalSegments.length ? _originalSegments[i] : '';
          final anonymizedSeg = _anonymizedSegments[i];

          segmentsData.add(<String, dynamic>{
            'segment_index': i,
            'original_text': originalSeg,
            'anonymized_text': anonymizedSeg,
          });
        }

        // Call API to rebuild document (same as download)
        final anonymizeService = AnonymizeService();
        final bytes = await anonymizeService.rebuildDocumentFromSegments(
          flow.context.anonymize.workflowId!,
          segmentsData,
        );

        // Decode bytes to text
        textToCopy = utf8.decode(bytes);
      }

      // Copy to clipboard
      await Clipboard.setData(ClipboardData(text: textToCopy));
      if (mounted) {
        MessageService.showSuccess(context, 'Copied to clipboard');
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to copy: $e');
      }
    }
  }

  Future<void> _runDeAnonymize() async {
    if (widget.flowId == null) return;

    // Navigate to De-anonymize phase
    final tasksNotifier = ref.read(tasksProvider.notifier);
    tasksNotifier.setPhase(widget.flowId!, PipelinePhase.deAnonymize);
    // The De-anonymize tab will be created in DeAnonymizeScreen and will read data from current tab
  }

  /// Get entity indices in the order they appear in the current view mode
  /// If grouped view: returns indices in group order (group by group, then occurrence by occurrence)
  /// If flat view: returns indices in original order (0, 1, 2, ...)
  List<int> _getOrderedEntityIndices() {
    if (!_viewModeNotifier.value) {
      // Flat view: return original order
      return List.generate(_entities.length, (i) => i);
    }

    // Grouped view: return indices in group order
    final groups = EntityGroupHelper.groupEntities(_entities);
    final orderedIndices = <int>[];

    for (final group in groups) {
      // Add all occurrence indices from this group
      for (final occurrence in group.occurrences) {
        orderedIndices.add(occurrence.index);
      }
    }

    return orderedIndices;
  }

  void _navigateToNextEntity() {
    if (_entities.isEmpty) return;

    // Get ordered entity indices based on current view mode
    final orderedIndices = _getOrderedEntityIndices();
    if (orderedIndices.isEmpty) return;

    // Find current index in ordered list
    int currentOrderedIndex = -1;
    if (_currentNavigationIndex >= 0 &&
        _currentNavigationIndex < _entities.length) {
      currentOrderedIndex = orderedIndices.indexOf(_currentNavigationIndex);
    }

    // Move to next index in ordered list
    final nextOrderedIndex = currentOrderedIndex < 0
        ? 0
        : (currentOrderedIndex + 1) % orderedIndices.length;

    final nextIndex = orderedIndices[nextOrderedIndex];

    setState(() {
      _currentNavigationIndex = nextIndex;
      _highlightedEntityIndex = nextIndex;
    });

    // Note: Group expansion and scrolling is handled in EntityListWidget's didUpdateWidget
    // when highlightedEntityIndex changes, so we don't need to do anything here

    // If in segment mode and entity has segment index, highlight the segment and text
    // (same logic as _onEntityTap)
    if (_displayMode == 'segment') {
      final entity =
          _entities[nextIndex] as Map<String, dynamic>? ?? <String, dynamic>{};
      final segmentIndex = entity['segmentIndex'] as int?;
      if (segmentIndex != null &&
          segmentIndex >= 0 &&
          segmentIndex < _originalSegments.length) {
        final entityText = entity['text']?.toString() ?? '';
        final placeholder = entity['placeholder']?.toString() ?? '';
        _highlightSegment(
          segmentIndex,
          highlightText: entityText,
          highlightPlaceholder: placeholder,
        );
        return; // Segment highlighting handles scrolling
      }
    }

    // Scroll to highlight position (same logic as _onEntityTap)
    final entity =
        _entities[nextIndex] as Map<String, dynamic>? ?? <String, dynamic>{};
    final originalStart = (entity['start'] as int?) ?? 0;
    final anonymizedStart = TextHighlighter.findReplacementPosition(
      originalText: widget.originalText,
      anonymizedText: _anonymizedText,
      originalStart: originalStart,
      originalEnd: (entity['end'] as int?) ?? originalStart,
      entities: _entities,
      highlightedEntityIndex: nextIndex,
    );

    // Use post-frame callback to ensure widgets are rendered (same as translation panel)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // Scroll original text with enhanced retry mechanism
      final originalKey = _originalTextKeys[nextIndex];
      if (originalKey != null) {
        // Use scrollUntilVisible for correction logic (increased maxAttempts for better reliability)
        TextScrollHelper.scrollUntilVisible(
          widgetKey: originalKey,
          scrollController: _originalTextScrollController,
        );
      } else if (originalStart >= 0 &&
          originalStart < widget.originalText.length) {
        // Fallback to TextPainter calculation
        TextScrollHelper.scrollToTextPosition(
          text: widget.originalText,
          charPosition: originalStart,
          scrollController: _originalTextScrollController,
          textStyle: const TextStyle(fontSize: 14),
        );
      }

      // Scroll anonymized text with enhanced retry mechanism
      final anonymizedKey = _anonymizedTextKeys[nextIndex];
      if (anonymizedKey != null) {
        // Use scrollUntilVisible for correction logic (increased maxAttempts for better reliability)
        TextScrollHelper.scrollUntilVisible(
          widgetKey: anonymizedKey,
          scrollController: _anonymizedTextScrollController,
        );
      } else if (anonymizedStart != null &&
          anonymizedStart >= 0 &&
          anonymizedStart < _anonymizedText.length) {
        // Fallback to TextPainter calculation
        TextScrollHelper.scrollToTextPosition(
          text: _anonymizedText,
          charPosition: anonymizedStart,
          scrollController: _anonymizedTextScrollController,
          textStyle: const TextStyle(fontSize: 14),
        );
      }
    });
  }

  void _onEntityTap(int index) {
    // Log placeholder positions for the selected group
    if (index >= 0 && index < _entities.length) {
      final entity =
          _entities[index] as Map<String, dynamic>? ?? <String, dynamic>{};
      final entityText = entity['text']?.toString() ?? '';
      final entityType = entity['type']?.toString() ?? 'UNKNOWN';

      // Group entities to find the group this entity belongs to
      final groups = EntityGroupHelper.groupEntities(_entities);
      EntityGroup? selectedGroup;
      for (final group in groups) {
        if (group.text == entityText && group.type == entityType) {
          selectedGroup = group;
          break;
        }
      }

      if (selectedGroup != null) {
        // Collect all placeholders used by this group
        final groupPlaceholders = <String>{};
        if (selectedGroup.primaryPlaceholder != null) {
          groupPlaceholders.add(selectedGroup.primaryPlaceholder!);
        }
        for (final occurrence in selectedGroup.occurrences) {
          if (occurrence.placeholder.isNotEmpty) {
            groupPlaceholders.add(occurrence.placeholder);
          }
        }

        // Find all positions of all placeholders in anonymized text
        for (final placeholder in groupPlaceholders) {
          final anonymizedPositions = <int>[];
          int searchStart = 0;
          while (true) {
            final pos = _anonymizedText.indexOf(placeholder, searchStart);
            if (pos == -1) break;
            anonymizedPositions.add(pos);
            searchStart = pos + 1;
          }
        }

        // Find all positions of the sensitive word text in original text
        final originalText = widget.originalText;
        final sensitiveWord = selectedGroup.text;
        final originalPositions = <int>[];
        if (sensitiveWord.isNotEmpty) {
          int searchStart = 0;
          while (true) {
            final pos = originalText.indexOf(sensitiveWord, searchStart);
            if (pos == -1) break;
            originalPositions.add(pos);
            searchStart = pos + 1;
          }
        }

        // Summary and missing detection
        // Search for ALL placeholders of this type in anonymized text (not just group's known placeholders)
        // This ensures we find all placeholders, even if they use different counters
        final allPlaceholdersOfType = <String>{};
        final escapedType = RegExp.escape(selectedGroup.type);
        final placeholderPattern = RegExp(r'\[' + escapedType + r'_\d+\]');

        final matches = placeholderPattern.allMatches(_anonymizedText);
        for (final match in matches) {
          final placeholder = match.group(0)!;
          allPlaceholdersOfType.add(placeholder);
        }

        // Collect existing entity positions
        final existingEntityPositions = <int>{};
        for (final occurrence in selectedGroup.occurrences) {
          existingEntityPositions.add(occurrence.start);
        }

        if (sensitiveWord.isNotEmpty) {
          // Detect missing entities by comparing original text positions with existing entities
          final missingOriginalPositions = <int>[];
          for (final pos in originalPositions) {
            if (!existingEntityPositions.contains(pos)) {
              missingOriginalPositions.add(pos);
            }
          }
        }
      }
    }

    setState(() {
      _highlightedEntityIndex = _highlightedEntityIndex == index ? null : index;
      // Update navigation index when manually selecting
      if (_highlightedEntityIndex != null) {
        _currentNavigationIndex = index;
      } else {
        _currentNavigationIndex = -1;
      }
    });

    // If in segment mode and entity has segment index, highlight the segment and text
    if (_displayMode == 'segment') {
      final entity =
          _entities[index] as Map<String, dynamic>? ?? <String, dynamic>{};
      final segmentIndex = entity['segmentIndex'] as int?;
      if (segmentIndex != null &&
          segmentIndex >= 0 &&
          segmentIndex < _originalSegments.length) {
        final entityText = entity['text']?.toString() ?? '';
        final placeholder = entity['placeholder']?.toString() ?? '';
        _highlightSegment(
          segmentIndex,
          highlightText: entityText,
          highlightPlaceholder: placeholder,
        );
        return; // Segment highlighting handles scrolling
      }
    }

    // Scroll to highlight position if entity is selected (same approach as translation panel)
    if (_highlightedEntityIndex == index) {
      final entity =
          _entities[index] as Map<String, dynamic>? ?? <String, dynamic>{};
      final originalStart = (entity['start'] as int?) ?? 0;
      final anonymizedStart = TextHighlighter.findReplacementPosition(
        originalText: widget.originalText,
        anonymizedText: _anonymizedText,
        originalStart: originalStart,
        originalEnd: (entity['end'] as int?) ?? originalStart,
        entities: _entities,
        highlightedEntityIndex: index,
      );

      // Use post-frame callback to ensure widgets are rendered (same as translation panel)
      WidgetsBinding.instance.addPostFrameCallback((_) {
        // Scroll original text with enhanced retry mechanism
        final originalKey = _originalTextKeys[index];
        if (originalKey != null) {
          // Use scrollUntilVisible for correction logic (increased maxAttempts for better reliability)
          TextScrollHelper.scrollUntilVisible(
            widgetKey: originalKey,
            scrollController: _originalTextScrollController,
          );
        } else if (originalStart >= 0 &&
            originalStart < widget.originalText.length) {
          // Fallback to TextPainter calculation
          TextScrollHelper.scrollToTextPosition(
            text: widget.originalText,
            charPosition: originalStart,
            scrollController: _originalTextScrollController,
            textStyle: const TextStyle(fontSize: 14),
          );
        }

        // Scroll anonymized text with enhanced retry mechanism
        final anonymizedKey = _anonymizedTextKeys[index];
        if (anonymizedKey != null) {
          // Use scrollUntilVisible for correction logic (increased maxAttempts for better reliability)
          TextScrollHelper.scrollUntilVisible(
            widgetKey: anonymizedKey,
            scrollController: _anonymizedTextScrollController,
          );
        } else if (anonymizedStart != null &&
            anonymizedStart >= 0 &&
            anonymizedStart < _anonymizedText.length) {
          // Fallback to TextPainter calculation
          TextScrollHelper.scrollToTextPosition(
            text: _anonymizedText,
            charPosition: anonymizedStart,
            scrollController: _anonymizedTextScrollController,
            textStyle: const TextStyle(fontSize: 14),
          );
        }
      });
    }
  }

  /// Expand current entities (plus optional seeds) and rebuild via backend
  Future<void> _expandAndRebuildWithSeeds({
    required List<Map<String, String>> seeds,
  }) async {
    if (widget.flowId == null) return;
    final flow = ref.read(flowProviderFamily(widget.flowId!));
    final workflowId = flow.context.anonymize.workflowId;
    if (workflowId == null || workflowId.isEmpty) {
      if (mounted) MessageService.showError(context, 'No workflow ID');
      return;
    }

    final anonymizeQs = ref.read(
      widget.flowId != null
          ? anonymizationQuickSettingsProviderFamily(widget.flowId!)
          : anonymizationQuickSettingsProvider,
    );
    final mode = anonymizeQs.anonymizeMode;
    final customPlaceholder = anonymizeQs.customPlaceholder;
    final enabledEntities =
        anonymizeQs.selectedEntityTypes; // Get enabled entity types

    // Build unique text+type seeds from current entities + provided seeds
    final seen = <String>{};
    final allSeeds = <Map<String, String>>[];
    for (final e in _entities) {
      final m = e as Map<String, dynamic>? ?? <String, dynamic>{};
      final t = m['text']?.toString() ?? '';
      final ty = m['type']?.toString() ?? 'UNKNOWN';
      if (t.isEmpty) continue;
      final key = '$t::$ty';
      if (seen.add(key)) allSeeds.add(<String, String>{'text': t, 'type': ty});
    }
    for (final s in seeds) {
      final t = s['text'] ?? '';
      final ty = s['type'] ?? 'UNKNOWN';
      if (t.isEmpty) continue;
      final key = '$t::$ty';
      if (seen.add(key)) allSeeds.add(<String, String>{'text': t, 'type': ty});
    }

    try {
      final svc = AnonymizeService();
      final expandRes = await svc.expandEntities(
        workflowId,
        entities: allSeeds,
        enabledEntities: enabledEntities.isNotEmpty ? enabledEntities : null,
      );
      final entitiesExpanded =
          expandRes['entities_expanded'] as List<dynamic>? ?? <dynamic>[];
      final rebuildRes = await svc.rebuildUnified(
        workflowId,
        entitiesExpanded: entitiesExpanded.cast<Map<String, dynamic>>(),
        mode: mode,
        customPlaceholder: customPlaceholder,
      );

      final updatedAnonymizedText =
          rebuildRes['anonymized_text']?.toString() ?? '';
      final updatedSegments =
          (rebuildRes['segments'] as List<dynamic>? ?? <dynamic>[])
              .map((e) => e.toString())
              .toList();

      if (mounted) {
        setState(() {
          _entities = List<dynamic>.from(entitiesExpanded);
          _anonymizedText = updatedAnonymizedText.isNotEmpty
              ? updatedAnonymizedText
              : _anonymizedText;
          if (updatedSegments.isNotEmpty) {
            _anonymizedSegments = updatedSegments;
          }
        });
      }

      // Update flow context mappings, text, and entitiesExpanded
      try {
        final flowNotifier =
            ref.read(flowProviderFamily(widget.flowId!).notifier);
        final currentFlow = ref.read(flowProviderFamily(widget.flowId!));
        final currentArtifacts = currentFlow.context.anonymize;
        final mappings = (rebuildRes['mappings'] as Map<String, dynamic>?)
            ?.map((k, v) => MapEntry(k.toString(), v.toString()));
        flowNotifier.setAnonymizeArtifacts(
          currentArtifacts.copyWith(
            anonymizedText: _anonymizedText,
            mappings: mappings,
            entitiesExpanded: _entities, // Update with expanded entities
          ),
        );
      } catch (_) {}
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Backend update failed: $e');
      }
    }
  }

  /// Fill all missing entities from entitiesExpanded (one-click)
  Future<void> _fillAllMissingEntities() async {
    if (widget.flowId == null) return;

    try {
      final flow = ref.read(flowProviderFamily(widget.flowId!));
      final entitiesExpanded = flow.context.anonymize.entitiesExpanded;

      if (entitiesExpanded == null || entitiesExpanded.isEmpty) {
        if (mounted) {
          MessageService.showInfo(context, 'No expanded entities available');
        }
        return;
      }

      // Get missing seeds
      final missingSeeds = EntityGroupHelper.scanMissingEntitiesFromExpanded(
        _entities,
        entitiesExpanded,
      );

      if (missingSeeds.isEmpty) {
        if (mounted) {
          MessageService.showInfo(context, 'No missing entities found');
        }
        return;
      }

      // Fill all missing entities via backend expand + rebuild
      await _expandAndRebuildWithSeeds(seeds: missingSeeds);

      // Update flow context with new entitiesExpanded
      try {
        final flowNotifier =
            ref.read(flowProviderFamily(widget.flowId!).notifier);
        final currentFlow = ref.read(flowProviderFamily(widget.flowId!));
        final currentArtifacts = currentFlow.context.anonymize;
        flowNotifier.setAnonymizeArtifacts(
          currentArtifacts.copyWith(
            entitiesExpanded: _entities,
          ),
        );
      } catch (_) {}

      if (mounted) {
        MessageService.showSuccess(
          context,
          'Filled ${missingSeeds.length} missing entity(ies)',
        );
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to fill missing entities: $e',
        );
      }
    }
  }

  /// Update anonymized segment after editing
  Future<void> _updateAnonymizedSegment(
    int segmentIndex,
    String newText,
  ) async {
    if (segmentIndex < 0 || segmentIndex >= _anonymizedSegments.length) {
      return;
    }

    // Update local segment
    setState(() {
      _anonymizedSegments[segmentIndex] = newText;
    });

    // Rebuild full anonymized text from segments
    final updatedAnonymizedText = _anonymizedSegments.join();
    setState(() {
      _anonymizedText = updatedAnonymizedText;
    });

    // Update flow context
    if (widget.flowId != null) {
      try {
        final flowNotifier =
            ref.read(flowProviderFamily(widget.flowId!).notifier);
        final currentFlow = ref.read(flowProviderFamily(widget.flowId!));
        final currentArtifacts = currentFlow.context.anonymize;

        flowNotifier.setAnonymizeArtifacts(
          currentArtifacts.copyWith(
            anonymizedText: updatedAnonymizedText,
          ),
        );
      } catch (e) {
        if (mounted) {
          MessageService.showError(
            context,
            'Failed to update flow context: $e',
          );
        }
      }
    }

    // Note: Entity details are not automatically updated when editing segments
    // Users can manually update entities if needed through the entity list
    if (mounted) {
      MessageService.showSuccess(
        context,
        'Segment ${segmentIndex + 1} updated',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isFullscreen) {
      return const SizedBox.shrink();
    }
    return _buildMainContent();
  }

  Widget _buildMainContent({bool isFullscreenView = false}) {
    final highlightedEntity = _highlightedEntityIndex != null &&
            _highlightedEntityIndex! < _entities.length
        ? _entities[_highlightedEntityIndex!] as Map<String, dynamic>?
        : null;

    final originalStart =
        highlightedEntity != null ? (highlightedEntity['start'] as int?) : null;
    final originalEnd =
        highlightedEntity != null ? (highlightedEntity['end'] as int?) : null;

    // Get entity text and placeholder for multi-highlighting
    final entityText = highlightedEntity != null
        ? (highlightedEntity['text']?.toString() ?? '')
        : null;
    final placeholder = highlightedEntity != null
        ? (highlightedEntity['placeholder']?.toString() ?? '')
        : null;

    // For anonymized text, find the replacement position (for scrolling to primary occurrence)
    int? anonymizedStart;
    int? anonymizedEnd;
    if (highlightedEntity != null &&
        originalStart != null &&
        originalEnd != null) {
      anonymizedStart = TextHighlighter.findReplacementPosition(
        originalText: widget.originalText,
        anonymizedText: _anonymizedText,
        originalStart: originalStart,
        originalEnd: originalEnd,
        entities: _entities,
        highlightedEntityIndex: _highlightedEntityIndex ?? -1,
      );

      if (anonymizedStart != null) {
        // Try to get the placeholder length
        if (placeholder != null && placeholder.isNotEmpty) {
          anonymizedEnd = anonymizedStart + placeholder.length;
        } else {
          // Fallback: use a reasonable default length
          anonymizedEnd = anonymizedStart + 10;
        }
      }
    }

    final shortcuts = <ShortcutActivator, Intent>{};
    final actions = <Type, Action<Intent>>{};
    if (isFullscreenView) {
      shortcuts[const SingleActivator(LogicalKeyboardKey.escape)] =
          const _ExitAnonymizedFullscreenIntent();
      actions[_ExitAnonymizedFullscreenIntent] =
          CallbackAction<_ExitAnonymizedFullscreenIntent>(
        onInvoke: (_) {
          _exitFullscreen();
          return null;
        },
      );
    }

    Widget content = Column(
      children: <Widget>[
        // Toolbar
        Container(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).dividerColor,
              ),
            ),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: <Widget>[
              Icon(
                Icons.visibility_off,
                size: 20,
                color: Colors.orange.shade700,
              ),
              const SizedBox(width: 8),
              Text(
                '',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
              const Spacer(),
              // Statistics summary in toolbar
              if (widget.statistics != null &&
                  widget.statistics!.isNotEmpty) ...<Widget>[
                ...widget.statistics!.entries.take(2).map<Widget>(
                      (entry) => Padding(
                        padding: const EdgeInsets.only(left: 16),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            Text(
                              '${entry.key}: ',
                              style: TextStyle(
                                fontSize: 12,
                                color: Theme.of(context)
                                    .colorScheme
                                    .onSurfaceVariant,
                              ),
                            ),
                            Text(
                              entry.value.toString(),
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: Theme.of(context).colorScheme.primary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
              ],
              const SizedBox(width: 8),
              // Display mode toggle
              ToggleButtons(
                isSelected: <bool>[
                  _displayMode == 'text',
                  _displayMode == 'segment',
                ],
                onPressed: (index) {
                  setState(() {
                    _displayMode = index == 0 ? 'text' : 'segment';
                  });
                  if (_displayMode == 'segment') {
                    // Load segments if not already loaded
                    if (_originalSegments.isEmpty && !_loadingSegments) {
                      _loadSegments();
                    }
                  } else if (_displayMode == 'text' &&
                      _originalSegments.isNotEmpty) {
                    // Initialize text pagination when switching to text mode
                    if (_textPaginationController == null) {
                      _initializeTextPagination();
                    }
                  }
                },
                borderRadius: BorderRadius.circular(8),
                constraints: const BoxConstraints(
                  minHeight: 32,
                  minWidth: 80,
                ),
                children: const <Widget>[
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Icon(Icons.text_fields, size: 16),
                        SizedBox(width: 4),
                        Text('Text'),
                      ],
                    ),
                  ),
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Icon(Icons.format_list_numbered, size: 16),
                        SizedBox(width: 4),
                        Text('Segment'),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 8),
              // Download button
              OutlinedButton.icon(
                onPressed: _downloadAnonymized,
                icon: const Icon(Icons.download, size: 16),
                label: const Text('Download'),
                style: OutlinedButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  foregroundColor: Colors.green.shade700,
                ),
              ),
              const SizedBox(width: 8),
              // Copy button
              OutlinedButton.icon(
                onPressed: _copyAnonymized,
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy'),
                style: OutlinedButton.styleFrom(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  foregroundColor: Colors.blue.shade700,
                ),
              ),
              const SizedBox(width: 8),
              // De-anonymize button (only available for placeholder mode)
              Builder(
                builder: (context) {
                  final anonymizeQs = widget.flowId != null
                      ? ref.watch(
                          anonymizationQuickSettingsProviderFamily(
                            widget.flowId!,
                          ),
                        )
                      : ref.watch(anonymizationQuickSettingsProvider);
                  final canDeAnonymize =
                      anonymizeQs.anonymizeMode == 'placeholder';

                  if (!canDeAnonymize) {
                    return const SizedBox.shrink();
                  }

                  return OutlinedButton.icon(
                    onPressed: _runDeAnonymize,
                    icon: const Icon(Icons.visibility, size: 16),
                    label: const Text('De-anonymize'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      foregroundColor: Colors.purple.shade700,
                    ),
                  );
                },
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: Icon(
                  _isFullscreen && isFullscreenView
                      ? Icons.fullscreen_exit
                      : Icons.fullscreen,
                ),
                tooltip: _isFullscreen && isFullscreenView
                    ? 'Exit Fullscreen'
                    : 'Enter Fullscreen',
                onPressed: _toggleFullscreen,
              ),
            ],
          ),
        ),
        // Content area: Text mode or Segment mode
        Expanded(
          child: _displayMode == 'segment'
              ? _buildSegmentMode()
              : _buildTextMode(
                  originalStart,
                  originalEnd,
                  anonymizedStart,
                  anonymizedEnd,
                  entityText,
                  placeholder,
                ),
        ),
      ],
    );

    if (shortcuts.isNotEmpty) {
      content = Shortcuts(
        shortcuts: shortcuts,
        child: Actions(
          actions: actions,
          child: Focus(
            autofocus: true,
            child: content,
          ),
        ),
      );
    }
    return content;
  }

  Widget _buildTextMode(
    int? originalStart,
    int? originalEnd,
    int? anonymizedStart,
    int? anonymizedEnd,
    String? entityText,
    String? placeholder,
  ) {
    // Determine which text to display
    // Only use pagination if controller is ready and not loading
    final usePagination = _textPaginationController != null &&
        !_textPaginationController!.isLoading &&
        _currentPageOriginalText.isNotEmpty &&
        _currentPageAnonymizedText.isNotEmpty;

    final displayOriginalText =
        usePagination ? _currentPageOriginalText : widget.originalText;
    final displayAnonymizedText =
        usePagination ? _currentPageAnonymizedText : _anonymizedText;

    // Debug: Log the text being displayed
    debugPrint(
      '[AnonymizedResultView] _buildTextMode: usePagination=$usePagination, isLoading=${_textPaginationController?.isLoading ?? false}, displayOriginalText.len=${displayOriginalText.length}, displayAnonymizedText.len=${displayAnonymizedText.length}',
    );

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        // Column 1: Original Text
        Expanded(
          child: DecoratedBox(
            decoration: BoxDecoration(
              border: Border(
                right: BorderSide(
                  color: Theme.of(context).dividerColor,
                ),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    border: Border(
                      bottom: BorderSide(
                        color: Theme.of(context).dividerColor,
                      ),
                    ),
                  ),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        Icons.description,
                        size: 18,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Original Text${_textPaginationController != null ? ' (${_textPaginationController!.startIndex}-${_textPaginationController!.endIndex} of ${_originalSegments.length} segments)' : ''}',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                        ),
                      ),
                      if (_textPaginationController != null) ...<Widget>[
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: PaginationBar(
                            currentPage: _textPaginationController!.currentPage,
                            totalPages: _textPaginationController!.totalPages,
                            hasPrev: _textPaginationController!.hasPrev,
                            hasNext: _textPaginationController!.hasMore,
                            onPrevPage: _textPaginationController!.isLoading
                                ? null
                                : _textPaginationController!.loadPrevPage,
                            onNextPage: _textPaginationController!.isLoading
                                ? null
                                : _textPaginationController!.loadNextPage,
                            onJumpToPage: _textPaginationController!.isLoading
                                ? null
                                : _textPaginationController!.jumpToPage,
                            showPageJump: false,
                            height: 40,
                          ),
                        ),
                        PageSizeSelector(
                          currentPageSize: _textPaginationController!.pageSize,
                          onPageSizeChanged: (size) =>
                              _textPaginationController!.setPageSize(size),
                          preferenceKey: 'anonymize_result_text_page_size',
                        ),
                      ],
                    ],
                  ),
                ),
                Expanded(
                  child: SingleChildScrollView(
                    controller: _originalTextScrollController,
                    padding: const EdgeInsets.all(16),
                    child: Builder(
                      builder: (context) {
                        if (displayOriginalText.isEmpty) {
                          return Text(
                            'No original text available',
                            style: TextStyle(
                              fontSize: 14,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                          );
                        }
                        // Debug: Log before building text widget
                        debugPrint(
                          '[AnonymizedResultView] Building original text widget: len=${displayOriginalText.length}',
                        );
                        // Temporarily use simple Text widget for testing
                        // TODO: Re-enable highlighting after confirming text displays
                        return SelectableText(
                          displayOriginalText,
                          style: const TextStyle(fontSize: 14),
                        );
                        // return TextHighlighter.buildHighlightableText(
                        //   text: displayOriginalText,
                        //   highlightStart: originalStart,
                        //   highlightEnd: originalEnd,
                        //   highlightText: entityText?.isNotEmpty == true ? entityText : null,
                        //   highlightKey: _highlightedEntityIndex != null
                        //       ? _originalTextKeys[_highlightedEntityIndex!]
                        //       : null,
                        // );
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        // Column 2: Anonymized Text
        Expanded(
          child: DecoratedBox(
            decoration: BoxDecoration(
              border: Border(
                right: BorderSide(
                  color: Theme.of(context).dividerColor,
                ),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    border: Border(
                      bottom: BorderSide(
                        color: Theme.of(context).dividerColor,
                      ),
                    ),
                  ),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        Icons.visibility_off,
                        size: 18,
                        color: Colors.orange.shade700,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Anonymized Text${_textPaginationController != null ? ' (${_textPaginationController!.startIndex}-${_textPaginationController!.endIndex} of ${_anonymizedSegments.length} segments)' : ''}',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: SingleChildScrollView(
                    controller: _anonymizedTextScrollController,
                    padding: const EdgeInsets.all(16),
                    child: Builder(
                      builder: (context) {
                        if (displayAnonymizedText.isEmpty) {
                          return Text(
                            'No anonymized text available',
                            style: TextStyle(
                              fontSize: 14,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                          );
                        }
                        // Debug: Log before building text widget
                        debugPrint(
                          '[AnonymizedResultView] Building anonymized text widget: len=${displayAnonymizedText.length}',
                        );
                        // Temporarily use simple Text widget for testing
                        // TODO: Re-enable highlighting after confirming text displays
                        return SelectableText(
                          displayAnonymizedText,
                          style: const TextStyle(fontSize: 14),
                        );
                        // return TextHighlighter.buildHighlightableText(
                        //   text: displayAnonymizedText,
                        //   highlightStart: anonymizedStart,
                        //   highlightEnd: anonymizedEnd,
                        //   highlightText: placeholder?.isNotEmpty == true ? placeholder : null,
                        //   highlightKey: _highlightedEntityIndex != null
                        //       ? _anonymizedTextKeys[_highlightedEntityIndex!]
                        //       : null,
                        // );
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        // Column 3: Detected Entities
        Expanded(
          child: Builder(
            builder: (context) {
              // Watch flow context to automatically reload when anonymize artifacts change
              if (widget.flowId != null) {
                try {
                  final flow = ref.watch(flowProviderFamily(widget.flowId!));
                  final anonymizeArtifacts = flow.context.anonymize;

                  // Check if anonymized text or entities have changed in flow context
                  if (anonymizeArtifacts.anonymizedText != null &&
                      anonymizeArtifacts.anonymizedText != _anonymizedText) {
                    // Update local state from flow context
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (mounted) {
                        setState(() {
                          _anonymizedText = anonymizeArtifacts.anonymizedText!;
                          // Update entities if available
                          if (anonymizeArtifacts.entitiesExpanded != null) {
                            _entities = List<dynamic>.from(
                              anonymizeArtifacts.entitiesExpanded!,
                            );
                          }
                          // Update anonymized segments if in segment mode
                          if (_displayMode == 'segment' &&
                              _originalSegments.isNotEmpty) {
                            _anonymizedSegments =
                                AnonymizedTextUpdater.updateAnonymizedSegments(
                              originalSegments: _originalSegments,
                              entities: _entities,
                              segmentBoundaries: _segmentBoundaries,
                            );
                            _calculateSegmentHeights();
                          }
                        });
                      }
                    });
                  }

                  final entitiesExpanded = anonymizeArtifacts.entitiesExpanded;

                  return EntityListWidget(
                    entities: _entities,
                    highlightedEntityIndex: _highlightedEntityIndex,
                    currentNavigationIndex: _currentNavigationIndex,
                    originalSegments: _originalSegments,
                    segmentBoundaries: _segmentBoundaries,
                    anonymizedText: _anonymizedText,
                    onNavigateToNext: _navigateToNextEntity,
                    onEntityTap: _onEntityTap,
                    onEditEntity: _editEntity,
                    onShowEntityDetails: _showEntityDetailsDialog,
                    onDeleteEntity: _deleteEntity,
                    onAddEntity: _addEntity,
                    onAddMissingPlaceholder: _addMissingPlaceholder,
                    onScanMissing: () {
                      // Manual scan trigger (already handled in EntityListWidget)
                    },
                    entitiesExpanded: entitiesExpanded,
                    onFillAllMissing: _fillAllMissingEntities,
                    viewModeNotifier: _viewModeNotifier,
                  );
                } catch (_) {
                  // Fallback if flow context is not available
                  return EntityListWidget(
                    entities: _entities,
                    highlightedEntityIndex: _highlightedEntityIndex,
                    currentNavigationIndex: _currentNavigationIndex,
                    originalSegments: _originalSegments,
                    segmentBoundaries: _segmentBoundaries,
                    anonymizedText: _anonymizedText,
                    onNavigateToNext: _navigateToNextEntity,
                    onEntityTap: _onEntityTap,
                    onEditEntity: _editEntity,
                    onShowEntityDetails: _showEntityDetailsDialog,
                    onDeleteEntity: _deleteEntity,
                    onAddEntity: _addEntity,
                    onAddMissingPlaceholder: _addMissingPlaceholder,
                    onScanMissing: () {
                      // Manual scan trigger (already handled in EntityListWidget)
                    },
                    onFillAllMissing: _fillAllMissingEntities,
                    viewModeNotifier: _viewModeNotifier,
                  );
                }
              } else {
                // No flowId, use local state only
                return EntityListWidget(
                  entities: _entities,
                  highlightedEntityIndex: _highlightedEntityIndex,
                  currentNavigationIndex: _currentNavigationIndex,
                  originalSegments: _originalSegments,
                  segmentBoundaries: _segmentBoundaries,
                  anonymizedText: _anonymizedText,
                  onNavigateToNext: _navigateToNextEntity,
                  onEntityTap: _onEntityTap,
                  onEditEntity: _editEntity,
                  onShowEntityDetails: _showEntityDetailsDialog,
                  onDeleteEntity: _deleteEntity,
                  onAddEntity: _addEntity,
                  onAddMissingPlaceholder: _addMissingPlaceholder,
                  onScanMissing: () {
                    // Manual scan trigger (already handled in EntityListWidget)
                  },
                  onFillAllMissing: _fillAllMissingEntities,
                  viewModeNotifier: _viewModeNotifier,
                );
              }
            },
          ),
        ),
      ],
    );
  }

  Widget _buildSegmentMode() {
    if (_loadingSegments) {
      // While loading segments, show text mode as fallback
      return _buildTextMode(null, null, null, null, null, null);
    }

    if (_originalSegments.isEmpty || _anonymizedSegments.isEmpty) {
      // If segments are not available, fallback to text mode
      debugPrint(
        '[AnonymizedResultView] _buildSegmentMode: Segments not available, falling back to text mode',
      );
      return _buildTextMode(null, null, null, null, null, null);
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        // Column 1: Original Text Segments
        Expanded(
          child: DecoratedBox(
            decoration: BoxDecoration(
              border: Border(
                right: BorderSide(
                  color: Theme.of(context).dividerColor,
                ),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    border: Border(
                      bottom: BorderSide(
                        color: Theme.of(context).dividerColor,
                      ),
                    ),
                  ),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        Icons.description,
                        size: 18,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Original Text (${_segmentPaginationController?.startIndex ?? 1}-${_segmentPaginationController?.endIndex ?? _originalSegments.length} of ${_originalSegments.length} segments)',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                        ),
                      ),
                      if (_segmentPaginationController != null) ...<Widget>[
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: PaginationBar(
                            currentPage:
                                _segmentPaginationController!.currentPage,
                            totalPages:
                                _segmentPaginationController!.totalPages,
                            hasPrev: _segmentPaginationController!.hasPrev,
                            hasNext: _segmentPaginationController!.hasMore,
                            onPrevPage: _segmentPaginationController!.isLoading
                                ? null
                                : _segmentPaginationController!.loadPrevPage,
                            onNextPage: _segmentPaginationController!.isLoading
                                ? null
                                : _segmentPaginationController!.loadNextPage,
                            onJumpToPage:
                                _segmentPaginationController!.isLoading
                                    ? null
                                    : _segmentPaginationController!.jumpToPage,
                            showPageJump: false,
                            height: 40,
                          ),
                        ),
                        PageSizeSelector(
                          currentPageSize:
                              _segmentPaginationController!.pageSize,
                          onPageSizeChanged: (size) =>
                              _segmentPaginationController!.setPageSize(size),
                          preferenceKey: 'anonymize_result_segment_page_size',
                        ),
                      ],
                    ],
                  ),
                ),
                Expanded(
                  child: _segmentPaginationController == null ||
                          _segmentPaginationController!.items.isEmpty
                      ? Center(
                          child: _loadingSegments
                              ? const CircularProgressIndicator(strokeWidth: 2)
                              : Text(
                                  'No segments available',
                                  style: TextStyle(
                                    fontSize: 14,
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                                ),
                        )
                      : ListView.separated(
                          controller: _originalTextScrollController,
                          padding: const EdgeInsets.all(8),
                          itemCount: _segmentPaginationController!.items.length,
                          separatorBuilder: (_, __) => const Divider(height: 8),
                          itemBuilder: (context, i) {
                            final globalIndex =
                                _segmentPaginationController!.offset + i;
                            // Segment border highlight: only current entity's segment
                            final isSegmentHighlighted =
                                _highlightedSegmentIndex == globalIndex;
                            // Text highlight: all segments containing the same text
                            final shouldHighlightText =
                                _highlightedSegmentIndices
                                    .contains(globalIndex);
                            // Get segment text from _originalSegments array, not from pagination controller items
                            final segmentText =
                                globalIndex < _originalSegments.length
                                    ? _originalSegments[globalIndex]
                                    : _segmentPaginationController!.items[i];
                            return LayoutBuilder(
                              builder: (
                                context,
                                constraints,
                              ) {
                                final segmentHeight = _getSegmentHeight(
                                  globalIndex,
                                  constraints.maxWidth,
                                );
                                return SizedBox(
                                  height: segmentHeight,
                                  child: HighlightableSegmentItem(
                                    itemKey: _originalSegmentKeys[globalIndex],
                                    text: segmentText,
                                    index: globalIndex,
                                    isHighlighted: isSegmentHighlighted,
                                    highlightText: shouldHighlightText
                                        ? _highlightedTextInSegment
                                        : null,
                                    onTap: () => _highlightSegment(globalIndex),
                                    onCopy: () {
                                      Clipboard.setData(
                                        ClipboardData(text: segmentText),
                                      );
                                      if (mounted) {
                                        MessageService.showSuccess(
                                          context,
                                          'Segment ${globalIndex + 1} copied',
                                        );
                                      }
                                    },
                                    badgeColor: Colors.blue.shade50,
                                    badgeTextColor: Colors.blue.shade700,
                                  ),
                                );
                              },
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        ),
        // Column 2: Anonymized Text Segments
        Expanded(
          child: DecoratedBox(
            decoration: BoxDecoration(
              border: Border(
                right: BorderSide(
                  color: Theme.of(context).dividerColor,
                ),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    border: Border(
                      bottom: BorderSide(
                        color: Theme.of(context).dividerColor,
                      ),
                    ),
                  ),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        Icons.visibility_off,
                        size: 18,
                        color: Colors.orange.shade700,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Anonymized Text (${_segmentPaginationController?.startIndex ?? 1}-${_segmentPaginationController?.endIndex ?? _anonymizedSegments.length} of ${_anonymizedSegments.length} segments)',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: _segmentPaginationController == null ||
                          _segmentPaginationController!.items.isEmpty
                      ? Center(
                          child: _loadingSegments
                              ? const CircularProgressIndicator(strokeWidth: 2)
                              : Text(
                                  'No segments available',
                                  style: TextStyle(
                                    fontSize: 14,
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                                ),
                        )
                      : ListView.separated(
                          controller: _anonymizedTextScrollController,
                          padding: const EdgeInsets.all(8),
                          itemCount: _segmentPaginationController!.items.length,
                          separatorBuilder: (_, __) => const Divider(height: 8),
                          itemBuilder: (context, i) {
                            final globalIndex =
                                _segmentPaginationController!.offset + i;
                            // Segment border highlight: only current entity's segment
                            final isSegmentHighlighted =
                                _highlightedSegmentIndex == globalIndex;
                            // Text highlight: all segments containing the same placeholder
                            final shouldHighlightText =
                                _highlightedSegmentIndices
                                    .contains(globalIndex);
                            final anonymizedSegment =
                                globalIndex < _anonymizedSegments.length
                                    ? _anonymizedSegments[globalIndex]
                                    : '';
                            return LayoutBuilder(
                              builder: (
                                context,
                                constraints,
                              ) {
                                final segmentHeight = _getSegmentHeight(
                                  globalIndex,
                                  constraints.maxWidth,
                                );
                                return SizedBox(
                                  height: segmentHeight,
                                  child: EditableAnonymizedSegmentItem(
                                    itemKey:
                                        _anonymizedSegmentKeys[globalIndex],
                                    text: anonymizedSegment,
                                    index: globalIndex,
                                    isHighlighted: isSegmentHighlighted,
                                    highlightText: shouldHighlightText
                                        ? _highlightedPlaceholderInSegment
                                        : null,
                                    onTap: () => _highlightSegment(globalIndex),
                                    onEdit: (newText) =>
                                        _updateAnonymizedSegment(
                                      globalIndex,
                                      newText,
                                    ),
                                    badgeColor: Colors.orange.shade50,
                                    badgeTextColor: Colors.orange.shade700,
                                  ),
                                );
                              },
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        ),
        // Column 3: Detected Entities (same as text mode)
        Expanded(
          child: Builder(
            builder: (context) {
              // Get entitiesExpanded from flow context
              List<dynamic>? entitiesExpanded;
              if (widget.flowId != null) {
                try {
                  final flow = ref.read(flowProviderFamily(widget.flowId!));
                  entitiesExpanded = flow.context.anonymize.entitiesExpanded;
                } catch (_) {
                  // Ignore errors
                }
              }

              return EntityListWidget(
                entities: _entities,
                highlightedEntityIndex: _highlightedEntityIndex,
                currentNavigationIndex: _currentNavigationIndex,
                originalSegments: _originalSegments,
                segmentBoundaries: _segmentBoundaries,
                anonymizedText: _anonymizedText,
                onNavigateToNext: _navigateToNextEntity,
                onEntityTap: _onEntityTap,
                onEditEntity: _editEntity,
                onShowEntityDetails: _showEntityDetailsDialog,
                onDeleteEntity: _deleteEntity,
                onAddEntity: _addEntity,
                onAddMissingPlaceholder: _addMissingPlaceholder,
                onScanMissing: () {
                  // Manual scan trigger (already handled in EntityListWidget)
                },
                entitiesExpanded: entitiesExpanded,
                onFillAllMissing: _fillAllMissingEntities,
                viewModeNotifier: _viewModeNotifier,
              );
            },
          ),
        ),
      ],
    );
  }
}
