// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/utils/message_service.dart';
import '../../../../shared/utils/app_logger.dart';
import '../../../../shared/widgets/markdown_text_with_images.dart';
import '../../models/exclusion_reason.dart';
import '../../../../shared/services/translation_service.dart';
import '../common/exclusion_reason_editor.dart';
import 'segment_pdf_typography_dialog.dart';
import '../../utils/segment_type_utils.dart';
import '../../utils/layout_bbox_text_split.dart';

// Intent classes for keyboard shortcuts
class _CancelEditingIntent extends Intent {
  const _CancelEditingIntent();
}

class _SaveEditingIntent extends Intent {
  const _SaveEditingIntent();
}

class _UndoEditingIntent extends Intent {
  const _UndoEditingIntent();
}

class _RedoEditingIntent extends Intent {
  const _RedoEditingIntent();
}

/// Single translation segment item widget with inline editing support.
///
/// Displays a single segment (source or target) with support for:
/// - Highlighting when selected
/// - Inline editing (double-click to edit)
/// - Exclusion badges with reason display
/// - Retry/failure status indicators
/// - Image placeholder rendering
/// - Undo/redo functionality
class TranslationSegmentItem extends StatefulWidget {
  const TranslationSegmentItem({
    required this.text,
    required this.index,
    required this.isSource,
    required this.isHighlighted,
    required this.onTap,
    super.key,
    this.sourceText,
    this.isModified = false,
    this.platformUsed,
    this.isFailed = false,
    this.failureReason,
    this.needsRetry = false,
    this.onRetry,
    this.onMarkForRetry,
    this.onUnmarkForRetry,
    this.isExcluded = false,
    this.exclusionReason,
    this.detectedExclusionReason,
    this.suggestedExclusionReason,
    this.showExclusionTypeSwitcher = false,
    this.onExclude,
    this.onUnexclude,
    this.isCleared = false,
    this.onClear,
    this.onUnclear,
    this.onEdit,
    this.onEditingStarted,
    this.onUndo,
    this.onRedo,
    this.canUndo = false,
    this.canRedo = false,
    this.itemKey,
    this.previewFontSize,
    this.editFontSize,
    this.imageDataMap = const <String, Map<String, String>>{},
    this.taskId,
    this.onExclusionUpdated,
    this.onFormulaFix,
    this.showPdfFontSize = false,
    this.fontSizePt,
    this.computedFontSizePt,
    this.overlayRenderFontSizePt,
    this.fontSizeSource,
    this.fontWeight,
    this.computedFontWeight,
    this.fontWeightSource,
    this.fontStyle,
    this.computedFontStyle,
    this.fontStyleSource,
    this.leadingEm,
    this.computedLeadingEm,
    this.leadingEmSource,
    this.onFontSizeChanged,
    this.pdfRevisionMode = false,
    this.rotation = 0,
    this.onRotationChanged,
    this.tableStrokePt = 0,
    this.onTableStrokeChanged,
    this.tableBorderStyle = kPdfDefaultTableBorderStyle,
    this.onTableBorderStyleChanged,
    this.showTableStroke = false,
    this.layoutBlockBboxes,
    this.layoutBlockIndices,
    this.layoutGroupTextParts,
    this.onLayoutGroupPartsEdit,
  });
  final String text;
  final String?
      sourceText; // For displaying source text in edit mode (not used anymore)
  final int index;
  final bool isSource;
  final bool isHighlighted;
  final bool isModified; // Whether this segment has been modified
  final String? platformUsed; // AI platform key used for translation
  final bool isFailed; // Whether translation failed
  final String? failureReason; // Failure reason if failed
  final bool needsRetry; // Whether user manually marked for retry
  final Function(int index)?
      onRetry; // Callback to retry translation (deprecated, use onUnmarkForRetry instead)
  final Function(int index)? onMarkForRetry; // Callback to mark for retry
  final Function(int index)?
      onUnmarkForRetry; // Callback to unmark for retry (clear retry flag)
  final bool isExcluded; // Whether this segment is excluded from translation
  final String?
      exclusionReason; // Exclusion reason (e.g., 'image', 'formula', 'reference')
  /// Detected type even when the segment is not currently excluded.
  final String? detectedExclusionReason;
  /// Preferred reason for the type switcher (formula/table/chart/image).
  final String? suggestedExclusionReason;
  /// Show exclusion-type picker before the segment is excluded (image-switchable).
  final bool showExclusionTypeSwitcher;
  final Function(int index)? onExclude; // Callback to exclude segment
  final Function(int index)? onUnexclude; // Callback to unexclude segment
  final bool isCleared; // Whether this segment translation is cleared
  final Function(int index)? onClear; // Callback to clear segment translation
  final Function(int index)?
      onUnclear; // Callback to unclear segment (restore translation)
  final VoidCallback onTap;
  final Function(String newText)? onEdit; // Callback when text is edited
  final Function(int index)?
      onEditingStarted; // Callback when editing starts (to highlight source)
  final Function(int index)? onUndo; // Callback for local undo
  final Function(int index)? onRedo; // Callback for local redo
  final bool canUndo; // Whether local undo is available
  final bool canRedo; // Whether local redo is available
  final GlobalKey? itemKey;
  final double? previewFontSize; // Font size for preview text
  final double? editFontSize; // Font size for editing
  final Map<String, Map<String, String>> imageDataMap;
  final String? taskId; // Task ID for API calls
  final FutureOr<void> Function(
    int index, {
    String? exclusionReason,
    bool? isExcluded,
  })? onExclusionUpdated; // Callback when exclusion reason is updated
  final Function(int index)? onFormulaFix; // Callback to trigger LLM formula repair
  final bool showPdfFontSize;
  final double? fontSizePt;
  final double? computedFontSizePt;
  final double? overlayRenderFontSizePt;
  final String? fontSizeSource;
  final String? fontWeight;
  final String? computedFontWeight;
  final String? fontWeightSource;
  final String? fontStyle;
  final String? computedFontStyle;
  final String? fontStyleSource;
  final double? leadingEm;
  final double? computedLeadingEm;
  final String? leadingEmSource;
  final void Function(
    int index, {
    double? fontSizePt,
    String? fontWeight,
    String? fontStyle,
    double? leadingEm,
    bool reset,
    SegmentPdfTypographyDialogMode scope,
  })? onFontSizeChanged;
  final bool pdfRevisionMode;
  final int rotation; // Current rotation value: 0, 90, 180, or 270
  final void Function(int index, int rotation)? onRotationChanged;
  final double tableStrokePt; // Table grid stroke width in pt (0 = hidden)
  final void Function(int index, double tableStrokePt)? onTableStrokeChanged;
  final String tableBorderStyle;
  final void Function(int index, String tableBorderStyle)? onTableBorderStyleChanged;
  final bool showTableStroke;
  /// Layout group bboxes (image pixel coords) for area-proportional text split.
  final List<List<double>>? layoutBlockBboxes;
  /// Layout block indices aligned with [layoutBlockBboxes].
  final List<int>? layoutBlockIndices;
  /// Stored per-block texts when user has edited layout group parts.
  final Map<String, dynamic>? layoutGroupTextParts;
  final Future<void> Function(int index, Map<int, String> parts)?
      onLayoutGroupPartsEdit;

  @override
  State<TranslationSegmentItem> createState() => _TranslationSegmentItemState();
}

class _TranslationSegmentItemState extends State<TranslationSegmentItem> {
  bool _isEditing = false;
  late TextEditingController _textController;
  late final FocusNode _editFocusNode;
  String _originalText = '';

  // Edit history stack for undo/redo during editing (like Office)
  final List<String> _editHistory = <String>[]; // Past states (oldest first)
  String? _currentEditText; // Current editing text
  final List<String> _editFuture = <String>[]; // Redo stack (newest first)

  // Track last text to detect changes
  String _lastText = '';

  // Flag to prevent recording history during undo/redo operations
  bool _isUndoRedoOperation = false;

  // Flag to track if user is selecting text (dragging)
  bool _isSelectingText = false;

  // Local state for immediate UI updates without triggering parent rebuild
  bool _localNeedsRetry = false;
  bool _localIsExcluded = false;
  String? _localExclusionReason;
  bool _localIsCleared = false;

  final Map<int, TextEditingController> _layoutPartControllers =
      <int, TextEditingController>{};
  List<int>? _layoutPartControllerIndices;
  String _layoutPartsSnapshot = '';
  bool _isLayoutGroupEditing = false;
  bool _layoutPartsSaving = false;

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController(text: widget.text);
    _editFocusNode = FocusNode(debugLabel: 'segment_edit_${widget.index}');
    _originalText = widget.text;
    _lastText = widget.text;

    // Initialize local state from widget props
    _localNeedsRetry = widget.needsRetry;
    _localIsExcluded = widget.isExcluded;
    _localIsCleared = widget.isCleared;
    _localExclusionReason = widget.exclusionReason;

    // Listen to text changes to build edit history
    _textController.addListener(_onTextChanged);
  }

  void _onTextChanged() {
    if (!_isEditing || _isUndoRedoOperation) return;

    final currentText = _textController.text;
    if (currentText == _lastText) return; // No actual change

    // Push previous text to history
    if (_currentEditText != null && _currentEditText != currentText) {
      _editHistory.add(_currentEditText!);
      // Limit edit history depth (e.g., 50 for editing operations)
      if (_editHistory.length > 50) {
        _editHistory.removeAt(0);
      }
      // Clear redo stack when new edit is made
      _editFuture.clear();
    }

    _currentEditText = currentText;
    _lastText = currentText;
  }

  @override
  void didUpdateWidget(TranslationSegmentItem oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.text != widget.text) {
      // If not in editing mode, always sync text from parent.
      //
      // If we ARE in editing mode, we must be careful:
      // - Background refreshes (polling, list reload, etc.) may rebuild the widget with
      //   the old text from the server while the user is still typing.
      // - If we blindly overwrite the controller/original text here, the user's in‑progress
      //   edits are lost, and Save will think "nothing changed" (newText == _originalText),
      //   which matches the symptom "saving still shows old value".
      //
      // Therefore, when editing, only accept the external update if the user has NOT
      // modified the text since the last frame (controller still equals oldWidget.text).
      if (!_isEditing) {
        _textController.text = widget.text;
        _originalText = widget.text;
        _lastText = widget.text;
      } else if (_textController.text == oldWidget.text) {
        // Safe to apply external update (e.g. undo/redo from parent) because
        // user hasn't typed since oldWidget.
        _textController.text = widget.text;
        _originalText = widget.text;
        _lastText = widget.text;
      } else {
        // Ignore external update while user is actively editing.
        AppLogger.log(
          'TranslationSegmentItem',
          'didUpdateWidget: Ignoring external text update while editing '
              'for index=${widget.index} to preserve in-progress edits',
          level: LogLevel.warn,
        );
      }
    }
    // Only update local state if widget props changed from external source
    // (not from our own local updates)
    if (oldWidget.needsRetry != widget.needsRetry) {
      _localNeedsRetry = widget.needsRetry;
    }
    if (oldWidget.isExcluded != widget.isExcluded) {
      _localIsExcluded = widget.isExcluded;
    }
    if (oldWidget.exclusionReason != widget.exclusionReason) {
      _localExclusionReason = widget.exclusionReason;
    }
    if (oldWidget.isCleared != widget.isCleared) {
      _localIsCleared = widget.isCleared;
    }
    if (!_layoutPartsSaving &&
        _isLayoutGroupEditing &&
        (oldWidget.layoutBlockIndices != widget.layoutBlockIndices ||
            oldWidget.layoutBlockBboxes != widget.layoutBlockBboxes ||
            oldWidget.layoutGroupTextParts != widget.layoutGroupTextParts ||
            (oldWidget.text != widget.text && !_isEditing))) {
      _syncLayoutPartControllers();
    }
  }

  @override
  void dispose() {
    _disposeLayoutPartControllers();
    _textController.removeListener(_onTextChanged);
    _textController.dispose();
    _editFocusNode.dispose();
    super.dispose();
  }

  void _handleDoubleTapEdit() {
    if (widget.isSource) {
      return;
    }
    if (_canEditLayoutGroupParts()) {
      _startLayoutGroupEditing();
      return;
    }
    if (widget.onEdit != null) {
      _startEditing();
    }
  }

  void _startLayoutGroupEditing() {
    if (!_canEditLayoutGroupParts() || _isLayoutGroupEditing || _isEditing) {
      return;
    }
    widget.onEditingStarted?.call(widget.index);
    _syncLayoutPartControllers(force: true);
    setState(() => _isLayoutGroupEditing = true);
  }

  void _cancelLayoutGroupEditing() {
    if (!_isLayoutGroupEditing) {
      return;
    }
    setState(() {
      _isLayoutGroupEditing = false;
      _layoutPartsSaving = false;
    });
    _disposeLayoutPartControllers();
  }

  void _startEditing() {
    AppLogger.log(
      'TranslationSegmentItem',
      '_startEditing CALLED: index=${widget.index}, isSource=${widget.isSource}, onEdit=${widget.onEdit != null}, _isEditing=$_isEditing',
      level: LogLevel.info,
    );

    if (widget.isSource || widget.onEdit == null) {
      AppLogger.log(
        'TranslationSegmentItem',
        '_startEditing: Early return - isSource=${widget.isSource}, onEdit=${widget.onEdit != null}',
        level: LogLevel.warn,
      );
      return;
    }

    // Safety check: if already editing, reset first (shouldn't happen, but safeguard)
    if (_isEditing) {
      AppLogger.log(
        'TranslationSegmentItem',
        '_startEditing: Already editing, resetting first for index=${widget.index}',
        level: LogLevel.warn,
      );
      setState(() {
        _isEditing = false;
      });
    }

    // Notify parent to highlight and scroll to corresponding source segment
    if (widget.onEditingStarted != null) {
      AppLogger.log(
        'TranslationSegmentItem',
        '_startEditing: Calling onEditingStarted(${widget.index})',
        level: LogLevel.info,
      );
      widget.onEditingStarted!(widget.index);
    } else {
      AppLogger.log(
        'TranslationSegmentItem',
        '_startEditing: onEditingStarted is null',
        level: LogLevel.warn,
      );
    }

    AppLogger.log(
      'TranslationSegmentItem',
      '_startEditing: Setting _isEditing=true, text length=${widget.text.length}',
      level: LogLevel.info,
    );
    setState(() {
      _isEditing = true;
      _originalText = widget.text;
      _textController.text = widget.text;
      _currentEditText = widget.text;
      _lastText = widget.text;
      // Initialize edit history with starting text
      _editHistory.clear();
      _editFuture.clear();
    });

    AppLogger.log(
      'TranslationSegmentItem',
      '_startEditing: setState completed, _isEditing=$_isEditing',
      level: LogLevel.info,
    );

    // CRITICAL (Web): Do NOT rely on TextField.autofocus during pointer events.
    // Request focus after the next frame to avoid Flutter Web engine assertion:
    // "The targeted input element must be the active input element"
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_isEditing) return;
      AppLogger.log(
        'TranslationSegmentItem',
        '_startEditing: Requesting focus after frame for index=${widget.index}',
        level: LogLevel.info,
      );
      _editFocusNode.requestFocus();
      final String t = _textController.text;
      _textController.selection = TextSelection.collapsed(offset: t.length);
    });

    // Force height remeasurement after entering edit mode
    // Edit mode may have different height (different font size, etc.)
    // Wait for layout to complete, then trigger remeasurement
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        // Wait for edit mode layout to complete
        Future.delayed(const Duration(milliseconds: 50), () {
          if (mounted) {
            // Trigger rebuild to force ItemWithHeightMeasurement to remeasure
            // The child widget has changed (edit mode), so didUpdateWidget will reset _lastMeasuredHeight
            setState(() {
              // Empty setState to trigger rebuild and height remeasurement
            });
          }
        });
      }
    });
  }

  /// Undo during editing (Office-like undo for text changes)
  void _undoEditing() {
    if (_editHistory.isEmpty) return;

    _isUndoRedoOperation = true;

    // Move current text to future (for redo)
    if (_currentEditText != null) {
      _editFuture.insert(0, _currentEditText!);
    }

    // Get previous text from history
    final previousText = _editHistory.removeLast();
    _currentEditText = previousText;
    _lastText = previousText;

    // Update controller
    _textController.value = TextEditingValue(
      text: previousText,
      selection: TextSelection.collapsed(offset: previousText.length),
    );

    _isUndoRedoOperation = false;
  }

  /// Redo during editing (Office-like redo for text changes)
  void _redoEditing() {
    if (_editFuture.isEmpty) return;

    _isUndoRedoOperation = true;

    // Move current text to history
    if (_currentEditText != null) {
      _editHistory.add(_currentEditText!);
    }

    // Get next text from future
    final nextText = _editFuture.removeAt(0);
    _currentEditText = nextText;
    _lastText = nextText;

    // Update controller
    _textController.value = TextEditingValue(
      text: nextText,
      selection: TextSelection.collapsed(offset: nextText.length),
    );

    _isUndoRedoOperation = false;
  }

  bool get _canUndoEditing => _editHistory.isNotEmpty;
  bool get _canRedoEditing => _editFuture.isNotEmpty;

  void _cancelEditing() {
    setState(() {
      _isEditing = false;
      _textController.text = _originalText;
      _lastText = _originalText;
      // Clear edit history when canceling
      _editHistory.clear();
      _editFuture.clear();
      _currentEditText = null;
    });

    // Force height remeasurement after exiting edit mode
    // Edit mode height may differ from preview mode height
    // Wait for layout to complete, then trigger remeasurement
    // Use multiple frames to ensure height is measured accurately
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        // Wait for preview mode layout to complete
        Future.delayed(const Duration(milliseconds: 100), () {
          if (mounted) {
            // Trigger rebuild to force ItemWithHeightMeasurement to remeasure
            // The child widget has changed (preview mode), so didUpdateWidget will reset _lastMeasuredHeight
            setState(() {
              // Empty setState to trigger rebuild and height remeasurement
            });
            // Also trigger another measurement after another frame
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) {
                setState(() {
                  // Second rebuild to ensure height is measured
                });
              }
            });
          }
        });
      }
    });
  }

  Future<void> _saveEditing() async {
    final newText = _textController.text.trim();
    if (newText == _originalText) {
      _cancelEditing();
      return;
    }

    if (newText.isEmpty) {
      // Don't allow empty text
      return;
    }

    AppLogger.log(
      'TranslationSegmentItem',
      '_saveEditing: Starting save for index=${widget.index}, newText length=${newText.length}, originalText length=${_originalText.length}',
      level: LogLevel.info,
    );

    try {
      await widget.onEdit!(newText);

      AppLogger.log(
        'TranslationSegmentItem',
        '_saveEditing: Save successful for index=${widget.index}, updating local state',
        level: LogLevel.info,
      );

      if (mounted) {
        setState(() {
          _isEditing = false;
          _originalText = newText;
          _lastText = newText;
          // Update controller text immediately to ensure view mode shows new text
          // even if parent's widget.text update is delayed
          _textController.text = newText;
          // Clear edit history when saving (edit history is only for editing session)
          _editHistory.clear();
          _editFuture.clear();
          _currentEditText = null;
        });

        // Force height remeasurement after exiting edit mode
        // Edit mode height may differ from preview mode height
        // Wait for layout to complete, then trigger remeasurement
        // Use multiple frames to ensure height is measured accurately
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            // Wait for preview mode layout to complete
            Future.delayed(const Duration(milliseconds: 100), () {
              if (mounted) {
                // Trigger rebuild to force ItemWithHeightMeasurement to remeasure
                // The child widget has changed (preview mode), so didUpdateWidget will reset _lastMeasuredHeight
                setState(() {
                  // Empty setState to trigger rebuild and height remeasurement
                });
                // Also trigger another measurement after another frame
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (mounted) {
                    setState(() {
                      // Second rebuild to ensure height is measured
                    });
                  }
                });
              }
            });
          }
        });
      }
    } catch (e) {
      // CRITICAL: Always reset editing state on error to allow re-editing
      // Otherwise, _isEditing remains true and double-tap won't work
      AppLogger.log(
        'TranslationSegmentItem',
        '_saveEditing: Error occurred for index=${widget.index}, resetting _isEditing to false: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        setState(() {
          _isEditing = false;
          // Reset controller to original text on error
          _textController.text = _originalText;
          _lastText = _originalText;
          // Keep original text on error (don't update _originalText)
        });
        MessageService.showError(
          context,
          AppLocalizations.of(context)!.segmentItemSaveFailed('$e'),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => GestureDetector(
        key: widget.itemKey,
        behavior: HitTestBehavior.opaque, // Ensure entire area is clickable
        onTap: (_isEditing || _isLayoutGroupEditing) ? null : widget.onTap,
        onDoubleTap: widget.isSource ||
                (widget.onEdit == null && !_canEditLayoutGroupParts())
            ? null
            : _handleDoubleTapEdit,
        child: Container(
          key: ValueKey(
            'segment_${widget.index}_editing_${_isEditing}_'
            'layoutGroup_$_isLayoutGroupEditing',
          ),
          margin: const EdgeInsets.only(
            bottom: 1,
          ), // Further reduced from 2 to 1 for more compact display
          padding: const EdgeInsets.all(
            2,
          ), // Further reduced from 4 to 2 for more compact display
          decoration: BoxDecoration(
            color: widget.isHighlighted
                ? (Theme.of(context).brightness == Brightness.dark
                    ? Colors.amber.shade200.withOpacity(
                        0.22,
                      ) // Unified highlight color for both Source and Translated Text in dark mode
                    : Colors.amber.shade50)
                : Theme.of(context).colorScheme.surface,
            // Always use 2px border to prevent layout overflow when state changes
            // Use background color for normal state border (invisible but maintains layout)
            // Use colored border for highlighted/modified/failed/retry states
            // Priority: Failed (red) > Retry (orange) > Modified (green) > Highlighted (amber) > Default
            border: Border.all(
              color: widget.isFailed
                  ? Colors.red.shade600
                  : (widget.needsRetry
                      ? Colors.orange.shade600
                      : (widget.isModified
                          ? Colors.green.shade600
                          : (widget.isHighlighted
                              ? (Theme.of(context).brightness == Brightness.dark
                                  ? Colors.amber
                                      .shade300 // Unified border color for both Source and Translated Text in dark mode
                                  : Colors.amber.shade400)
                              : Theme.of(context)
                                  .colorScheme
                                  .surface))), // Same as background for normal state
              width: 2, // Always 2px to maintain consistent layout
            ),
            borderRadius: BorderRadius.circular(8),
          ),
          child: _isEditing
              ? _buildEditMode()
              : (_isLayoutGroupEditing
                  ? _buildLayoutGroupEditMode()
                  : _buildViewMode()),
        ),
      );

  String _pdfFontSizeLabel(AppLocalizations l10n) {
    final bool isUserOverride = _hasPdfTypographyOverride();
    final double sizePt = _effectiveFontSizePt();
    final String sizeLabel = isUserOverride && widget.fontSizePt != null
        ? l10n.segmentPdfFontSizeManual(sizePt.toStringAsFixed(1))
        : (widget.computedFontSizePt != null
            ? l10n.segmentPdfFontSizeAuto(sizePt.toStringAsFixed(1))
            : l10n.segmentPdfFontSizeAutoUnknown);
    final List<String> styleParts = <String>[sizeLabel];
    final String weight = _effectiveFontWeight();
    final String style = _effectiveFontStyle();
    if (weight == 'bold') {
      styleParts.add('B');
    }
    if (style == 'italic') {
      styleParts.add('I');
    }
    if (kPdfLeadingTypographyUiEnabled) {
      styleParts.add('↕${_effectiveLeadingEm().toStringAsFixed(2)}');
    }
    return styleParts.join(' · ');
  }

  /// PDF revision panel: always show effective (computed or user) typography values.
  String _pdfRevisionFontLabel(AppLocalizations l10n) {
    final List<String> styleParts = <String>[];
    final double? sizePt = _effectiveFontSizePtOrNull();
    if (sizePt != null) {
      styleParts.add(l10n.segmentPdfFontSizeManual(sizePt.toStringAsFixed(1)));
    } else {
      styleParts.add(l10n.segmentPdfFontSizeAutoUnknown);
    }
    final String weight = _effectiveFontWeight();
    final String style = _effectiveFontStyle();
    if (weight == 'bold') {
      styleParts.add('B');
    }
    if (style == 'italic') {
      styleParts.add('I');
    }
    if (kPdfLeadingTypographyUiEnabled) {
      final double? leadingEm = _effectiveLeadingEmOrNull();
      if (leadingEm != null) {
        styleParts.add('↕${leadingEm.toStringAsFixed(2)}');
      }
    }
    return styleParts.join(' · ');
  }

  double? _effectiveFontSizePtOrNull() {
    return effectivePdfSegmentFontSizePtOrNull(
      fontSizeSource: widget.fontSizeSource,
      fontSizePt: widget.fontSizePt,
      computedFontSizePt: widget.computedFontSizePt,
      overlayRenderFontSizePt: widget.overlayRenderFontSizePt,
    );
  }

  double _effectiveFontSizePt() {
    return effectivePdfSegmentFontSizePt(
      fontSizeSource: widget.fontSizeSource,
      fontSizePt: widget.fontSizePt,
      computedFontSizePt: widget.computedFontSizePt,
      overlayRenderFontSizePt: widget.overlayRenderFontSizePt,
    );
  }

  double? _effectiveLeadingEmOrNull() {
    if (widget.leadingEmSource == 'user' && widget.leadingEm != null) {
      return widget.leadingEm;
    }
    return widget.computedLeadingEm ?? widget.leadingEm;
  }

  bool _hasPdfTypographyOverride() {
    return (widget.fontSizeSource == 'user' && widget.fontSizePt != null) ||
        widget.fontWeightSource == 'user' ||
        widget.fontStyleSource == 'user' ||
        (kPdfLeadingTypographyUiEnabled && widget.leadingEmSource == 'user');
  }

  String _effectiveFontWeight() {
    if (widget.fontWeightSource == 'user' && widget.fontWeight != null) {
      return widget.fontWeight!;
    }
    return widget.computedFontWeight ?? widget.fontWeight ?? 'regular';
  }

  String _effectiveFontStyle() {
    if (widget.fontStyleSource == 'user' && widget.fontStyle != null) {
      return widget.fontStyle!;
    }
    return widget.computedFontStyle ?? widget.fontStyle ?? 'normal';
  }

  double _effectiveLeadingEm() {
    if (widget.leadingEmSource == 'user' && widget.leadingEm != null) {
      return widget.leadingEm!;
    }
    return widget.computedLeadingEm ??
        widget.leadingEm ??
        kPdfLeadingEmDefault;
  }

  bool _canUseLayoutGroupSplit() {
    return widget.pdfRevisionMode &&
        !widget.isSource &&
        widget.layoutBlockBboxes != null &&
        widget.layoutBlockBboxes!.length > 1 &&
        widget.layoutBlockIndices != null &&
        widget.layoutBlockIndices!.length > 1 &&
        widget.text.trim().isNotEmpty;
  }

  bool _canEditLayoutGroupParts() {
    return _canUseLayoutGroupSplit() &&
        widget.onLayoutGroupPartsEdit != null;
  }

  void _disposeLayoutPartControllers() {
    for (final TextEditingController controller
        in _layoutPartControllers.values) {
      controller.dispose();
    }
    _layoutPartControllers.clear();
    _layoutPartControllerIndices = null;
    _layoutPartsSnapshot = '';
  }

  void _syncLayoutPartControllers({bool force = false}) {
    final List<int>? indices = widget.layoutBlockIndices;
    final List<List<double>>? bboxes = widget.layoutBlockBboxes;
    if (indices == null || bboxes == null || indices.length < 2) {
      _disposeLayoutPartControllers();
      return;
    }
    final Map<int, String>? stored =
        parseLayoutGroupTextParts(widget.layoutGroupTextParts);
    final List<String> texts = resolveLayoutGroupDisplayTexts(
      text: widget.text,
      bboxes: bboxes,
      indices: indices,
      storedParts: stored,
    );
    final String snapshot = texts.join('\u0001');
    if (!force &&
        _layoutPartControllerIndices != null &&
        listEquals(_layoutPartControllerIndices!, indices) &&
        _layoutPartsSnapshot == snapshot &&
        _layoutPartControllers.isNotEmpty) {
      return;
    }
    _disposeLayoutPartControllers();
    for (int i = 0; i < indices.length; i++) {
      final int blockIndex = indices[i];
      final String initial = i < texts.length ? texts[i] : '';
      _layoutPartControllers[blockIndex] =
          TextEditingController(text: initial);
    }
    _layoutPartControllerIndices = List<int>.from(indices);
    _layoutPartsSnapshot = snapshot;
  }

  Map<int, String> _collectLayoutGroupParts() {
    final Map<int, String> parts = <int, String>{};
    _layoutPartControllers.forEach((int idx, TextEditingController controller) {
      parts[idx] = controller.text.trim();
    });
    return parts;
  }

  String _layoutPartsControllersSignature() {
    final List<int>? indices = _layoutPartControllerIndices;
    if (indices == null) {
      return '';
    }
    return indices
        .map((int idx) => (_layoutPartControllers[idx]?.text ?? '').trim())
        .join('\u0001');
  }

  bool _layoutPartsDirty() {
    return _layoutPartsControllersSignature() != _layoutPartsSnapshot;
  }

  Future<void> _saveLayoutGroupParts() async {
    if (!mounted || widget.onLayoutGroupPartsEdit == null) {
      return;
    }
    if (!_layoutPartsDirty()) {
      _cancelLayoutGroupEditing();
      return;
    }
    final List<int>? indices = widget.layoutBlockIndices;
    if (indices == null || indices.length < 2) {
      return;
    }
    final Map<int, String> parts = _collectLayoutGroupParts();
    setState(() => _layoutPartsSaving = true);
    try {
      await widget.onLayoutGroupPartsEdit!(widget.index, parts);
      if (!mounted) {
        return;
      }
      setState(() {
        _isLayoutGroupEditing = false;
        _layoutPartsSaving = false;
      });
      _disposeLayoutPartControllers();
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLayoutGroupEditing = false;
          _layoutPartsSaving = false;
        });
        _disposeLayoutPartControllers();
        MessageService.showError(
          context,
          AppLocalizations.of(context)!.segmentItemSaveFailed('$e'),
        );
      }
    }
  }

  TextStyle _segmentPreviewTextStyle(BuildContext context) {
    return TextStyle(
      fontSize: widget.previewFontSize ?? 14.0,
      color: Theme.of(context).colorScheme.onSurface,
      decoration: widget.isModified ? TextDecoration.none : null,
    );
  }

  Widget _buildSegmentPreviewText(BuildContext context) {
    if (_canUseLayoutGroupSplit()) {
      return _buildLayoutGroupSplitPreview(context);
    }
    return MarkdownTextWithImages(
      text: widget.text,
      imageDataMap:
          widget.imageDataMap.isEmpty ? null : widget.imageDataMap,
      style: _segmentPreviewTextStyle(context),
      imageMaxWidth: double.infinity,
      imageMaxHeight: 400,
    );
  }

  Widget _buildLayoutGroupSplitEditor(BuildContext context) {
    final List<List<double>> bboxes = widget.layoutBlockBboxes!;
    final List<int> indices = widget.layoutBlockIndices!;
    final Map<int, String>? stored =
        parseLayoutGroupTextParts(widget.layoutGroupTextParts);
    final bool usesStoredParts = stored != null &&
        layoutGroupTextPartsCoverIndices(stored, indices);
    final double totalArea = bboxes.fold<double>(
      0,
      (double sum, List<double> bbox) => sum + layoutBboxArea(bbox),
    );
    final ColorScheme colors = Theme.of(context).colorScheme;
    final Color accent = colors.error.withValues(alpha: 0.75);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: List<Widget>.generate(indices.length, (int i) {
        final int blockIndex = indices[i];
        final TextEditingController? controller =
            _layoutPartControllers[blockIndex];
        final double area = i < bboxes.length ? layoutBboxArea(bboxes[i]) : 0;
        final double sharePct =
            totalArea > 0 ? area / totalArea * 100 : 100 / indices.length;
        final String labelSuffix = usesStoredParts
            ? 'edited'
            : '${sharePct.toStringAsFixed(0)}%';
        return Padding(
          padding: EdgeInsets.only(bottom: i < indices.length - 1 ? 8 : 0),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: widget.isHighlighted
                  ? colors.errorContainer.withValues(alpha: 0.25)
                  : colors.surfaceContainerHighest.withValues(alpha: 0.35),
              border: Border(
                left: BorderSide(color: accent, width: 3),
              ),
              borderRadius: const BorderRadius.only(
                topRight: Radius.circular(4),
                bottomRight: Radius.circular(4),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(8, 4, 4, 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Text(
                        'Block $blockIndex ($labelSuffix)',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: colors.error,
                        ),
                      ),
                      if (_layoutPartsSaving) ...<Widget>[
                        const SizedBox(width: 6),
                        SizedBox(
                          width: 10,
                          height: 10,
                          child: CircularProgressIndicator(
                            strokeWidth: 1.5,
                            color: colors.error.withValues(alpha: 0.7),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 4),
                  TextField(
                    controller: controller,
                    maxLines: null,
                    style: _segmentPreviewTextStyle(context).copyWith(
                      fontSize: widget.editFontSize ?? 13,
                    ),
                    decoration: const InputDecoration(
                      isDense: true,
                      border: OutlineInputBorder(),
                      contentPadding: EdgeInsets.all(8),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      }),
    );
  }

  Widget _buildLayoutGroupEditMode() {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Shortcuts(
          shortcuts: const <ShortcutActivator, Intent>{
            SingleActivator(LogicalKeyboardKey.escape):
                _CancelEditingIntent(),
            SingleActivator(LogicalKeyboardKey.enter, control: true):
                _SaveEditingIntent(),
            SingleActivator(LogicalKeyboardKey.enter, meta: true):
                _SaveEditingIntent(),
          },
          child: Actions(
            actions: <Type, Action<Intent>>{
              _CancelEditingIntent: CallbackAction<_CancelEditingIntent>(
                onInvoke: (_) {
                  _cancelLayoutGroupEditing();
                  return null;
                },
              ),
              _SaveEditingIntent: CallbackAction<_SaveEditingIntent>(
                onInvoke: (_) {
                  unawaited(_saveLayoutGroupParts());
                  return null;
                },
              ),
            },
            child: _buildLayoutGroupSplitEditor(context),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: <Widget>[
            TextButton(
              onPressed: _layoutPartsSaving ? null : _cancelLayoutGroupEditing,
              child: Text(l10n.segmentItemCancel),
            ),
            const SizedBox(width: 8),
            ElevatedButton.icon(
              onPressed:
                  _layoutPartsSaving ? null : () => unawaited(_saveLayoutGroupParts()),
              icon: _layoutPartsSaving
                  ? SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Theme.of(context).colorScheme.onPrimary,
                      ),
                    )
                  : const Icon(Icons.save, size: 18),
              label: Text(l10n.segmentItemSave),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildLayoutGroupSplitPreview(BuildContext context) {
    final List<List<double>> bboxes = widget.layoutBlockBboxes!;
    final List<int> indices = widget.layoutBlockIndices!;
    final Map<int, String>? stored =
        parseLayoutGroupTextParts(widget.layoutGroupTextParts);
    final List<String> parts = resolveLayoutGroupDisplayTexts(
      text: widget.text,
      bboxes: bboxes,
      indices: indices,
      storedParts: stored,
    );
    final bool usesStoredParts = stored != null &&
        layoutGroupTextPartsCoverIndices(stored, indices);
    final double totalArea = bboxes.fold<double>(
      0,
      (double sum, List<double> bbox) => sum + layoutBboxArea(bbox),
    );
    final ColorScheme colors = Theme.of(context).colorScheme;
    final Color accent = colors.error.withValues(alpha: 0.75);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: List<Widget>.generate(indices.length, (int i) {
        final double area = i < bboxes.length ? layoutBboxArea(bboxes[i]) : 0;
        final double sharePct =
            totalArea > 0 ? area / totalArea * 100 : 100 / indices.length;
        final int blockLabel = indices[i];
        final String partText = i < parts.length ? parts[i] : '';
        final String labelSuffix = usesStoredParts
            ? 'edited'
            : '${sharePct.toStringAsFixed(0)}%';
        return Padding(
          padding: EdgeInsets.only(bottom: i < indices.length - 1 ? 8 : 0),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: widget.isHighlighted
                  ? colors.errorContainer.withValues(alpha: 0.25)
                  : colors.surfaceContainerHighest.withValues(alpha: 0.35),
              border: Border(
                left: BorderSide(color: accent, width: 3),
              ),
              borderRadius: const BorderRadius.only(
                topRight: Radius.circular(4),
                bottomRight: Radius.circular(4),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(8, 4, 4, 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Block $blockLabel ($labelSuffix)',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: colors.error,
                    ),
                  ),
                  const SizedBox(height: 2),
                  MarkdownTextWithImages(
                    text: partText.isEmpty ? '—' : partText,
                    imageDataMap: widget.imageDataMap.isEmpty
                        ? null
                        : widget.imageDataMap,
                    style: _segmentPreviewTextStyle(context),
                    imageMaxWidth: double.infinity,
                    imageMaxHeight: 400,
                  ),
                ],
              ),
            ),
          ),
        );
      }),
    );
  }

  Future<void> _openFontSizeDialog() async {
    if (widget.onFontSizeChanged == null) {
      return;
    }
    final bool isUserOverride = _hasPdfTypographyOverride();
    final double initialSize = snapPdfFontSize(_effectiveFontSizePt());

    final SegmentPdfTypographyResult? result =
        await showSegmentPdfTypographyDialog(
      context: context,
      previewText: widget.text,
      hasUserOverride: isUserOverride,
      initialFontSizePt: initialSize,
      initialFontWeight: _effectiveFontWeight(),
      initialFontStyle: _effectiveFontStyle(),
      initialLeadingEm: _effectiveLeadingEm(),
    );

    if (!mounted || result == null) {
      return;
    }
    if (result.reset) {
      widget.onFontSizeChanged!(
        widget.index,
        reset: true,
        scope: result.mode,
      );
      return;
    }
    widget.onFontSizeChanged!(
      widget.index,
      fontSizePt: result.fontSizePt,
      fontWeight: result.fontWeight,
      fontStyle: result.fontStyle,
      leadingEm: result.leadingEm,
      scope: result.mode,
    );
  }

  Widget _buildPdfFontSizeChip() {
    final l10n = AppLocalizations.of(context)!;
    final bool isUserOverride = _hasPdfTypographyOverride();
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _openFontSizeDialog,
          borderRadius: BorderRadius.circular(4),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: isUserOverride
                  ? colors.secondaryContainer
                  : colors.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(4),
              border: Border.all(
                color: isUserOverride
                    ? colors.secondary
                    : colors.outlineVariant,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(
                  Icons.format_size,
                  size: 12,
                  color: isUserOverride
                      ? colors.onSecondaryContainer
                      : colors.onSurfaceVariant,
                ),
                const SizedBox(width: 4),
                Text(
                  widget.pdfRevisionMode
                      ? _pdfRevisionFontLabel(l10n)
                      : _pdfFontSizeLabel(l10n),
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                    color: isUserOverride
                        ? colors.onSecondaryContainer
                        : colors.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildRotationChip(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final bool hasRotation = widget.rotation != 0;
    final ColorScheme colors = Theme.of(context).colorScheme;
    final String label = hasRotation
        ? l10n.segmentRotationLabel(widget.rotation)
        : l10n.segmentRotationOff;
    final bool canEdit = widget.onRotationChanged != null;

    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: MenuAnchor(
        style: MenuStyle(
          visualDensity: VisualDensity.compact,
          minimumSize: const WidgetStatePropertyAll<Size>(Size(148, 0)),
        ),
        menuChildren: <Widget>[
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: Text(
              l10n.segmentRotationMenuTitle,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: colors.onSurfaceVariant,
              ),
            ),
          ),
          ...kPdfRotationOptionsDegrees.map((int degrees) {
            final bool selected = widget.rotation == degrees;
            final String optionLabel = degrees == 0
                ? l10n.segmentRotationNone
                : l10n.segmentRotationLabel(degrees);
            return MenuItemButton(
              onPressed: canEdit
                  ? () => widget.onRotationChanged!(widget.index, degrees)
                  : null,
              child: _buildRotationMenuRow(
                context,
                degrees: degrees,
                label: optionLabel,
                checked: selected,
              ),
            );
          }),
        ],
        builder: (
          BuildContext context,
          MenuController controller,
          Widget? child,
        ) {
          return Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: canEdit
                  ? () {
                      if (controller.isOpen) {
                        controller.close();
                      } else {
                        controller.open();
                      }
                    }
                  : null,
              borderRadius: BorderRadius.circular(4),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: hasRotation
                      ? colors.secondaryContainer
                      : colors.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: hasRotation
                        ? colors.secondary
                        : colors.outlineVariant,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Icon(
                      Icons.rotate_right,
                      size: 12,
                      color: hasRotation
                          ? colors.onSecondaryContainer
                          : colors.onSurfaceVariant,
                    ),
                    const SizedBox(width: 2),
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: hasRotation
                            ? colors.onSecondaryContainer
                            : colors.onSurfaceVariant,
                      ),
                    ),
                    if (canEdit) ...<Widget>[
                      Icon(
                        Icons.arrow_drop_down,
                        size: 14,
                        color: hasRotation
                            ? colors.onSecondaryContainer
                            : colors.onSurfaceVariant,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildRotationMenuRow(
    BuildContext context, {
    required int degrees,
    required String label,
    required bool checked,
  }) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Row(
      children: <Widget>[
        SizedBox(
          width: 18,
          child: checked
              ? Icon(Icons.check, size: 14, color: colors.primary)
              : const SizedBox.shrink(),
        ),
        _RotationPreviewIcon(
          degrees: degrees,
          color: colors.onSurface,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 12),
          ),
        ),
      ],
    );
  }

  Widget _buildTableStrokeChip(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final bool hasStroke = widget.tableStrokePt > 0;
    final bool isNoneStyle = widget.tableBorderStyle == 'none';
    final ColorScheme colors = Theme.of(context).colorScheme;
    final String styleLabel = pdfTableBorderStyleLabel(
      l10n,
      widget.tableBorderStyle,
    );
    final String label = isNoneStyle
        ? styleLabel
        : hasStroke
            ? '$styleLabel · ${formatPdfTableStrokePtLabel(widget.tableStrokePt)}pt'
            : styleLabel;
    final bool canEdit = widget.onTableStrokeChanged != null ||
        widget.onTableBorderStyleChanged != null;
    final bool showWeightMenu =
        widget.tableBorderStyle != 'none' && widget.onTableStrokeChanged != null;

    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: MenuAnchor(
        style: MenuStyle(
          visualDensity: VisualDensity.compact,
          minimumSize: const WidgetStatePropertyAll<Size>(Size(168, 0)),
        ),
        menuChildren: <Widget>[
          if (widget.onTableBorderStyleChanged != null) ...<Widget>[
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
              child: Text(
                l10n.segmentTableBorderMenuTitle,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: colors.onSurfaceVariant,
                ),
              ),
            ),
            ...kPdfTableBorderStyleOptions.map((String optionStyle) {
              final bool selected = isPdfTableBorderStyleSelected(
                widget.tableBorderStyle,
                optionStyle,
              );
              return MenuItemButton(
                onPressed: canEdit
                    ? () => widget.onTableBorderStyleChanged!(
                          widget.index,
                          optionStyle,
                        )
                    : null,
                child: _buildTableBorderStyleMenuRow(
                  context,
                  style: optionStyle,
                  label: pdfTableBorderStyleLabel(l10n, optionStyle),
                  checked: selected,
                ),
              );
            }),
          ],
          if (showWeightMenu) ...<Widget>[
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
              child: Text(
                l10n.segmentTableStrokeMenuTitle,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: colors.onSurfaceVariant,
                ),
              ),
            ),
            ...kPdfTableStrokeOptionsPt.map((double optionPt) {
              final bool selected = isPdfTableStrokeOptionSelected(
                widget.tableStrokePt,
                optionPt,
              );
              final String optionLabel = optionPt <= 0
                  ? l10n.segmentTableStrokeNone
                  : l10n.segmentTableStrokeLabel(
                      formatPdfTableStrokePtLabel(optionPt),
                    );
              return MenuItemButton(
                onPressed: canEdit
                    ? () => widget.onTableStrokeChanged!(
                          widget.index,
                          optionPt,
                        )
                    : null,
                child: _buildTableStrokeMenuRow(
                  context,
                  strokePt: optionPt,
                  label: optionLabel,
                  checked: selected,
                ),
              );
            }),
          ],
        ],
        builder: (
          BuildContext context,
          MenuController controller,
          Widget? child,
        ) {
          return Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: canEdit
                  ? () {
                      if (controller.isOpen) {
                        controller.close();
                      } else {
                        controller.open();
                      }
                    }
                  : null,
              borderRadius: BorderRadius.circular(4),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: (!isNoneStyle && hasStroke)
                      ? colors.secondaryContainer
                      : colors.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: (!isNoneStyle && hasStroke)
                        ? colors.secondary
                        : colors.outlineVariant,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Icon(
                      _tableBorderStyleIcon(widget.tableBorderStyle),
                      size: 12,
                      color: (!isNoneStyle && hasStroke)
                          ? colors.onSecondaryContainer
                          : colors.onSurfaceVariant,
                    ),
                    const SizedBox(width: 2),
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: (!isNoneStyle && hasStroke)
                            ? colors.onSecondaryContainer
                            : colors.onSurfaceVariant,
                      ),
                    ),
                    if (canEdit) ...<Widget>[
                      Icon(
                        Icons.arrow_drop_down,
                        size: 14,
                        color: (!isNoneStyle && hasStroke)
                            ? colors.onSecondaryContainer
                            : colors.onSurfaceVariant,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildTableBorderStyleMenuRow(
    BuildContext context, {
    required String style,
    required String label,
    required bool checked,
  }) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Row(
      children: <Widget>[
        SizedBox(
          width: 18,
          child: checked
              ? Icon(Icons.check, size: 14, color: colors.primary)
              : const SizedBox.shrink(),
        ),
        _TableBorderStylePreviewIcon(
          style: style,
          color: colors.onSurface,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 12),
          ),
        ),
      ],
    );
  }

  Widget _buildTableStrokeMenuRow(
    BuildContext context, {
    required double strokePt,
    required String label,
    required bool checked,
  }) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Row(
      children: <Widget>[
        SizedBox(
          width: 18,
          child: checked
              ? Icon(Icons.check, size: 14, color: colors.primary)
              : const SizedBox.shrink(),
        ),
        _TableGridPreviewIcon(
          strokePt: strokePt,
          color: colors.onSurface,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 12),
          ),
        ),
      ],
    );
  }

  Widget _buildViewMode() {
    final l10n = AppLocalizations.of(context)!;
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final displayIndex = widget.index + 1; // 1-based display
    // Use green badge color like Extract page, but adjust for highlight/modified/failed/retry states
    // Priority: Highlighted (amber) > Modified (green) > Failed (red) > Retry (orange) > Default (green)
    final badgeColor = widget.isHighlighted
        ? Colors.amber.shade50
        : (widget.isModified
            ? Colors.green.shade50
            : (widget.isFailed
                ? Colors.red.shade50
                : (widget.needsRetry
                    ? Colors.orange.shade50
                    : (isDark
                        ? theme.colorScheme.primaryContainer
                        : Colors.green.shade50))));
    final badgeTextColor = widget.isHighlighted
        ? Colors.amber.shade700
        : (widget.isModified
            ? Colors.green.shade700
            : (widget.isFailed
                ? Colors.red.shade700
                : (widget.needsRetry
                    ? Colors.orange.shade700
                    : (isDark
                        ? theme.colorScheme.onPrimaryContainer
                        : Colors.green.shade700))));

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        // Segment number badge (same style as Extract page)
        Stack(
          clipBehavior: Clip.none,
          children: <Widget>[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
              decoration: BoxDecoration(
                color: badgeColor,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: badgeColor.withOpacity(0.3)),
              ),
              child: Text(
                '#$displayIndex',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: badgeTextColor,
                ),
              ),
            ),
            // Modified indicator (small badge on top-right)
            if (widget.isModified)
              Positioned(
                right: -4,
                top: -4,
                child: Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: Colors.green.shade600,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white),
                  ),
                  child: const Icon(
                    Icons.check,
                    size: 8,
                    color: Colors.white,
                  ),
                ),
              ),
            // Failed indicator (small badge on top-right)
            if (widget.isFailed)
              Positioned(
                right: -4,
                top: -4,
                child: Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: Colors.red.shade600,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white),
                  ),
                  child: const Icon(
                    Icons.warning,
                    size: 8,
                    color: Colors.white,
                  ),
                ),
              ),
            // Retry indicator (small badge on top-right)
            if (widget.needsRetry && !widget.isFailed)
              Positioned(
                right: -4,
                top: -4,
                child: Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: Colors.orange.shade600,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white),
                  ),
                  child: const Icon(
                    Icons.flag,
                    size: 8,
                    color: Colors.white,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(width: 4),
        // Text content (clickable via outer GestureDetector)
        // Use Listener to detect text selection vs segment selection
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min, // Allow column to shrink if needed
            children: <Widget>[
              // Use Flexible to allow text to take available space but shrink if needed
              // This prevents overflow when content exceeds the aligned height
              // The outer ClipRect in translation_result_preview.dart will clip any overflow
              Flexible(
                child: Listener(
                  onPointerDown: (PointerDownEvent event) {
                    // Reset text selection flag when pointer down
                    _isSelectingText = false;
                  },
                  onPointerMove: (_) {
                    // User is dragging, likely selecting text
                    _isSelectingText = true;
                  },
                  onPointerUp: (_) {
                    // If user wasn't selecting text, trigger segment selection
                    if (!_isSelectingText &&
                        !_isEditing &&
                        !_isLayoutGroupEditing) {
                      // Small delay to check if text selection occurred
                      Future.delayed(const Duration(milliseconds: 100), () {
                        if (mounted &&
                            !_isSelectingText &&
                            !_isEditing &&
                            !_isLayoutGroupEditing) {
                          widget.onTap();
                        }
                      });
                    }
                    _isSelectingText = false;
                  },
                  child: GestureDetector(
                    // Use translucent behavior to allow clicks to pass through to text selection
                    // but also trigger the onTap callback when clicking on text
                    behavior: HitTestBehavior.translucent,
                    onDoubleTap: () {
                      if (!widget.isSource &&
                          !_isEditing &&
                          !_isLayoutGroupEditing &&
                          (widget.onEdit != null ||
                              _canEditLayoutGroupParts())) {
                        _handleDoubleTapEdit();
                      }
                    },
                    onTap: () {
                      if (!_isSelectingText &&
                          !_isEditing &&
                          !_isLayoutGroupEditing) {
                        widget.onTap();
                      }
                    },
                    child: _buildSegmentPreviewText(context),
                  ),
                ),
              ),
              // Platform badge, retry button, exclude button, and clear button row
              if (!widget.isSource &&
                  (widget.platformUsed != null ||
                      widget.isFailed ||
                      widget.needsRetry ||
                      _localNeedsRetry ||
                      widget.isExcluded ||
                      _localIsExcluded ||
                      _localIsCleared ||
                      _shouldShowExclusionTypeSwitcher ||
                      (widget.showPdfFontSize && widget.onFontSizeChanged != null) ||
                      (widget.onRotationChanged != null) ||
                      (widget.onTableStrokeChanged != null &&
                          widget.showTableStroke) ||
                      (widget.onTableBorderStyleChanged != null &&
                          widget.showTableStroke) ||
                      (widget.onExclude != null && !_localIsExcluded) ||
                      (widget.onClear != null &&
                          widget.text.isNotEmpty &&
                          !_localIsCleared) ||
                      (widget.onEdit != null && !_isEditing)))
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Wrap(
                    spacing: 4,
                    runSpacing: 4,
                    children: <Widget>[
                      if (widget.showPdfFontSize && widget.onFontSizeChanged != null)
                        _buildPdfFontSizeChip(),
                      if (widget.onRotationChanged != null && !widget.isSource)
                        _buildRotationChip(context),
                      if ((widget.onTableStrokeChanged != null ||
                              widget.onTableBorderStyleChanged != null) &&
                          !widget.isSource &&
                          widget.showTableStroke)
                        _buildTableStrokeChip(context),
                      // Platform badge
                      if (!widget.pdfRevisionMode && widget.platformUsed != null)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: widget.isFailed
                                ? (Theme.of(context).brightness ==
                                        Brightness.dark
                                    ? Colors.red.shade900.withOpacity(0.3)
                                    : Colors.red.shade100)
                                : (widget.needsRetry
                                    ? (Theme.of(context).brightness ==
                                            Brightness.dark
                                        ? Colors.orange.shade900
                                            .withOpacity(0.3)
                                        : Colors.orange.shade100)
                                    : (Theme.of(context).brightness ==
                                            Brightness.dark
                                        ? Colors.green.shade900.withOpacity(0.3)
                                        : Colors.green.shade100)),
                            borderRadius: BorderRadius.circular(4),
                            border: Border.all(
                              color: widget.isFailed
                                  ? (Theme.of(context).brightness ==
                                          Brightness.dark
                                      ? Colors.red.shade700
                                      : Colors.red.shade300)
                                  : (widget.needsRetry
                                      ? (Theme.of(context).brightness ==
                                              Brightness.dark
                                          ? Colors.orange.shade700
                                          : Colors.orange.shade300)
                                      : (Theme.of(context).brightness ==
                                              Brightness.dark
                                          ? Colors.green.shade700
                                          : Colors.green.shade300)),
                            ),
                          ),
                          child: Text(
                            widget.platformUsed!,
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w500,
                              color: widget.isFailed
                                  ? (Theme.of(context).brightness ==
                                          Brightness.dark
                                      ? Colors.red.shade300
                                      : Colors.red.shade700)
                                  : (widget.needsRetry
                                      ? (Theme.of(context).brightness ==
                                              Brightness.dark
                                          ? Colors.orange.shade300
                                          : Colors.orange.shade700)
                                      : (Theme.of(context).brightness ==
                                              Brightness.dark
                                          ? Colors.green.shade300
                                          : Colors.green.shade700)),
                            ),
                          ),
                        ),
                      // Edit button (trigger inline editing)
                      if (!widget.isSource && widget.onEdit != null && !_isEditing)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: _startEditing,
                              borderRadius: BorderRadius.circular(4),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.blue.shade50,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.blue.shade300,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: <Widget>[
                                    Icon(
                                      Icons.edit,
                                      size: 12,
                                      color: Colors.blue.shade700,
                                    ),
                                    const SizedBox(width: 2),
                                    Text(
                                      widget.pdfRevisionMode
                                          ? l10n.segmentPdfRevisionEditLabel
                                          : l10n.segmentItemEdit,
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w500,
                                        color: Colors.blue.shade700,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      // Retry chips are mutually exclusive to avoid duplicate
                      // "重试" / "已标记重试" labels (esp. in PDF revision mode).
                      // - Run-retry (revision): failed or marked → single "重试"
                      // - Mark-retry: only when run-retry chip is not shown
                      // - Marked badge: only when run-retry chip is not shown
                      if (!_localNeedsRetry &&
                          !_localIsExcluded &&
                          widget.onMarkForRetry != null &&
                          !(widget.pdfRevisionMode &&
                              widget.onRetry != null &&
                              widget.isFailed))
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: () {
                                // Update local state immediately for instant UI feedback
                                setState(() {
                                  _localNeedsRetry = true;
                                });
                                // Then call the callback (which will update backend)
                                widget.onMarkForRetry!(widget.index);
                              },
                              borderRadius: BorderRadius.circular(4),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.orange.shade50,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.orange.shade300,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: <Widget>[
                                    Icon(
                                      Icons.flag,
                                      size: 12,
                                      color: Colors.orange.shade700,
                                    ),
                                    const SizedBox(width: 2),
                                    Text(
                                      l10n.segmentItemRetry,
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w500,
                                        color: Colors.orange.shade700,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      // Unmark retry badge — hidden when PDF revision run-retry chip
                      // already covers the same status.
                      if (_localNeedsRetry &&
                          !(widget.pdfRevisionMode && widget.onRetry != null))
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: widget.onUnmarkForRetry != null
                                  ? () {
                                      // Update local state immediately for instant UI feedback
                                      setState(() {
                                        _localNeedsRetry = false;
                                      });
                                      // Then call the callback (which will update backend)
                                      widget.onUnmarkForRetry!(widget.index);
                                    }
                                  : null,
                              borderRadius: BorderRadius.circular(4),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.grey.shade100,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.grey.shade300,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: <Widget>[
                                    Icon(
                                      Icons.close,
                                      size: 12,
                                      color: Colors.grey.shade700,
                                    ),
                                    const SizedBox(width: 2),
                                    Text(
                                      l10n.segmentItemMarkedRetry,
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w500,
                                        color: Colors.grey.shade700,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      // Run retry immediately (PDF revision mode only).
                      // For manually marked segments, include a close control to unmark
                      // without a second "已标记重试" chip.
                      if (widget.pdfRevisionMode &&
                          !widget.isSource &&
                          (widget.isFailed || _localNeedsRetry) &&
                          widget.onRetry != null)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Tooltip(
                            message: l10n.translationToolbarRetryTooltip,
                            child: Material(
                              color: Colors.transparent,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.orange.shade50,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.orange.shade400,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: <Widget>[
                                    InkWell(
                                      onTap: () =>
                                          widget.onRetry!(widget.index),
                                      borderRadius: BorderRadius.circular(4),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: <Widget>[
                                          Icon(
                                            Icons.refresh,
                                            size: 12,
                                            color: Colors.orange.shade800,
                                          ),
                                          const SizedBox(width: 2),
                                          Text(
                                            l10n.segmentItemRetry,
                                            style: TextStyle(
                                              fontSize: 10,
                                              fontWeight: FontWeight.w500,
                                              color: Colors.orange.shade800,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    if (_localNeedsRetry &&
                                        widget.onUnmarkForRetry != null) ...<
                                        Widget>[
                                      const SizedBox(width: 4),
                                      InkWell(
                                        onTap: () {
                                          setState(() {
                                            _localNeedsRetry = false;
                                          });
                                          widget.onUnmarkForRetry!(
                                            widget.index,
                                          );
                                        },
                                        borderRadius: BorderRadius.circular(4),
                                        child: Icon(
                                          Icons.close,
                                          size: 12,
                                          color: Colors.orange.shade800,
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      // Excluded badge (clickable to edit, with quick unexclude x button)
                      if (_localIsExcluded)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: _buildExclusionBadge(context),
                        ),
                      // Type switcher for formula/table/chart/image — shown even
                      // before the segment is excluded so users can pick Image directly.
                      if (!_localIsExcluded && _shouldShowExclusionTypeSwitcher)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: _buildExclusionTypeSwitcher(context),
                        ),
                      // Exclude button (if not excluded and not source)
                      if (!_localIsExcluded &&
                          !widget.isSource &&
                          widget.onExclude != null)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: () {
                                // Update local state immediately for instant UI feedback
                                setState(() {
                                  _localIsExcluded = true;
                                  _localNeedsRetry =
                                      false; // Clear retry when excluding
                                });
                                // Then call the callback (which will update backend)
                                widget.onExclude!(widget.index);
                              },
                              borderRadius: BorderRadius.circular(4),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.orange.shade50,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.orange.shade300,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: <Widget>[
                                    Icon(
                                      Icons.block_outlined,
                                      size: 12,
                                      color: Colors.orange.shade700,
                                    ),
                                    const SizedBox(width: 2),
                                    Text(
                                      l10n.segmentItemExclude,
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w500,
                                        color: Colors.orange.shade700,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      // Cleared badge (clickable to unclear)
                      if (_localIsCleared)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: widget.onUnclear != null
                                  ? () {
                                      // Update local state immediately for instant UI feedback
                                      setState(() {
                                        _localIsCleared = false;
                                      });
                                      // Then call the callback (which will update backend)
                                      widget.onUnclear!(widget.index);
                                    }
                                  : null,
                              borderRadius: BorderRadius.circular(4),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.purple.shade50,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.purple.shade300,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: <Widget>[
                                    Icon(
                                      Icons.clear,
                                      size: 12,
                                      color: Colors.purple.shade700,
                                    ),
                                    const SizedBox(width: 2),
                                    Text(
                                      l10n.segmentItemCleared,
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w500,
                                        color: Colors.purple.shade700,
                                      ),
                                    ),
                                    if (widget.onUnclear != null) ...<Widget>[
                                      const SizedBox(width: 4),
                                      Icon(
                                        Icons.close,
                                        size: 10,
                                        color: Theme.of(context).brightness ==
                                                Brightness.dark
                                            ? Colors.purple.shade400
                                            : Colors.purple.shade600,
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      // Clear button (if not cleared and text is not empty and not source)
                      if (!_localIsCleared &&
                          !widget.isSource &&
                          widget.text.isNotEmpty &&
                          widget.onClear != null)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: () {
                                // Update local state immediately for instant UI feedback
                                setState(() {
                                  _localIsCleared = true;
                                });
                                // Then call the callback (which will update backend)
                                widget.onClear!(widget.index);
                              },
                              borderRadius: BorderRadius.circular(4),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.purple.shade50,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.purple.shade300,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: <Widget>[
                                    Icon(
                                      Icons.clear,
                                      size: 12,
                                      color: Colors.purple.shade700,
                                    ),
                                    const SizedBox(width: 2),
                                    Text(
                                      widget.pdfRevisionMode
                                          ? l10n.segmentPdfRevisionClearLabel
                                          : l10n.segmentItemClear,
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w500,
                                        color: Colors.purple.shade700,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      // Formula fix button (LLM repair for this segment)
                      if (!widget.pdfRevisionMode &&
                          !_localIsCleared &&
                          !widget.isSource &&
                          widget.text.isNotEmpty &&
                          widget.onFormulaFix != null)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              onTap: () {
                                // Delegate to parent via onEdit callback after LLM repair in parent.
                                if (widget.onFormulaFix != null) {
                                  widget.onFormulaFix!(widget.index);
                                }
                              },
                              borderRadius: BorderRadius.circular(4),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.blue.shade50,
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.blue.shade300,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: <Widget>[
                                    Icon(
                                      Icons.functions,
                                      size: 12,
                                      color: Colors.blue.shade700,
                                    ),
                                    const SizedBox(width: 2),
                                    Text(
                                      l10n.segmentItemFix,
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w500,
                                        color: Colors.blue.shade700,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      // Failure reason tooltip (question mark icon) - placed after Clear / Fix buttons
                      if (widget.isFailed && widget.failureReason != null)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: Tooltip(
                            message: widget.failureReason,
                            child: Icon(
                              Icons.help_outline,
                              size: 14,
                              color: Colors.orange.shade700,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  bool get _shouldShowExclusionTypeSwitcher =>
      !widget.isSource &&
      widget.taskId != null &&
      widget.showExclusionTypeSwitcher;

  String? get _effectiveExclusionTypeHint =>
      _localExclusionReason ??
      widget.exclusionReason ??
      widget.suggestedExclusionReason ??
      widget.detectedExclusionReason;

  /// Type picker shown for formula/table/chart/image before exclusion.
  Widget _buildExclusionTypeSwitcher(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final ExclusionReason reason =
        ExclusionReason.fromString(_effectiveExclusionTypeHint);
    final bool isDark = Theme.of(context).brightness == Brightness.dark;

    return Tooltip(
      message: l10n.segmentItemExclusionEditTooltip,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => _showEditExclusionDialog(context),
          borderRadius: BorderRadius.circular(4),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: isDark
                  ? reason.color.withOpacity(0.18)
                  : reason.color.withOpacity(0.10),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(
                color: isDark
                    ? reason.color.withOpacity(0.55)
                    : reason.color.withOpacity(0.40),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(reason.icon, size: 12, color: reason.color),
                const SizedBox(width: 2),
                Text(
                  reason.displayNameLocalized(l10n),
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                    color: isDark
                        ? reason.color.withOpacity(0.95)
                        : reason.color.withOpacity(0.90),
                  ),
                ),
                const SizedBox(width: 2),
                Icon(
                  Icons.edit,
                  size: 10,
                  color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Build exclusion badge with reason-specific styling
  /// New design: Badge body for quick unexclude, edit button for editing, x button for quick unexclude
  Widget _buildExclusionBadge(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final reason = ExclusionReason.fromString(_effectiveExclusionTypeHint);
    final bool isDark = Theme.of(context).brightness == Brightness.dark;
    final bool canUnexclude = reason.canUnexclude && widget.onUnexclude != null;
    final bool canEdit = widget.taskId != null;

    final String displayText = l10n.segmentItemExclusionBadge(
      reason.displayNameLocalized(l10n),
    );

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        // Badge body: Click to quick unexclude (if canUnexclude) or show info
        Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: canUnexclude
                ? () {
                    // Quick unexclude: one-click to remove exclusion
                    // Update local state immediately for instant UI feedback
                    setState(() {
                      _localIsExcluded = false;
                      _localExclusionReason = null;
                    });
                    // Then call the callback (which will update backend)
                    widget.onUnexclude!(widget.index);
                  }
                : null,
            borderRadius: BorderRadius.circular(4),
            child: Tooltip(
              message: canUnexclude
                  ? l10n.segmentItemExclusionRemoveTooltip
                  : l10n.segmentItemExclusionLockedTooltip,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 6,
                  vertical: 2,
                ),
                decoration: BoxDecoration(
                  // Use grey background to clearly indicate excluded state
                  color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    // Border color varies by reason type
                    color: isDark
                        ? reason.color.withOpacity(0.6)
                        : reason.color.withOpacity(0.4),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    // Block icon (indicates exclusion)
                    Icon(
                      Icons.block,
                      size: 12,
                      color:
                          isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                    ),
                    const SizedBox(width: 2),
                    // Display text: EX prefix + reason name
                    Text(
                      displayText,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w600, // Bold for emphasis
                        color: isDark
                            ? Colors.grey.shade300
                            : Colors.grey.shade800,
                      ),
                    ),
                    // Reason type icon (for quick identification)
                    const SizedBox(width: 2),
                    Icon(
                      reason.icon,
                      size: 10,
                      color: isDark
                          ? reason.color.withOpacity(0.7)
                          : reason.color.withOpacity(0.8),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        // Edit button (if can edit) - for editing/switching exclusion reason
        if (canEdit) ...<Widget>[
          const SizedBox(width: 4),
          Tooltip(
            message: l10n.segmentItemExclusionEditTooltip,
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () {
                _showEditExclusionDialog(context);
              },
              child: MouseRegion(
                cursor: SystemMouseCursors.click,
                child: Container(
                  padding: const EdgeInsets.all(2),
                  decoration: BoxDecoration(
                    color: isDark ? Colors.grey.shade700 : Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Icon(
                    Icons.edit,
                    size: 10,
                    color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                  ),
                ),
              ),
            ),
          ),
        ],
        // Close button (only if can be unexcluded) - alternative quick unexclude action
        if (canUnexclude) ...<Widget>[
          const SizedBox(width: 4),
          Tooltip(
            message: l10n.segmentItemExclusionRemoveTooltip,
            child: GestureDetector(
              behavior: HitTestBehavior
                  .opaque, // Prevent event propagation to parent InkWell
              onTap: () {
                // Update local state immediately for instant UI feedback
                setState(() {
                  _localIsExcluded = false;
                  _localExclusionReason = null;
                });
                // Then call the callback (which will update backend)
                widget.onUnexclude!(widget.index);
              },
              child: MouseRegion(
                cursor: SystemMouseCursors.click,
                child: Container(
                  padding: const EdgeInsets.all(2),
                  decoration: BoxDecoration(
                    color: isDark ? Colors.grey.shade700 : Colors.grey.shade200,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.close,
                    size: 10,
                    color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                  ),
                ),
              ),
            ),
          ),
        ],
        // Info icon (if cannot be unexcluded and cannot edit)
        if (!canUnexclude && !canEdit) ...<Widget>[
          const SizedBox(width: 4),
          Icon(
            Icons.info_outline,
            size: 10,
            color: isDark ? Colors.grey.shade500 : Colors.grey.shade500,
          ),
        ],
      ],
    );
  }

  /// Show dialog to edit exclusion reason
  Future<void> _showEditExclusionDialog(BuildContext context) async {
    final String? priorReason = _localIsExcluded
        ? (_localExclusionReason ?? widget.exclusionReason)
        : _effectiveExclusionTypeHint;
    final String? newReason = await showDialog<String?>(
      context: context,
      builder: (context) => ExclusionReasonEditor(
        currentReason: priorReason,
      ),
    );

    // Applying a type while not excluded (null -> formula/image) must call API.
    final bool reasonChanged = newReason != widget.exclusionReason ||
        (!_localIsExcluded && newReason != null);
    if (reasonChanged && widget.taskId != null) {
      // Call API to update exclusion reason
      try {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> response = await svc.updateExclusionReason(
          widget.taskId!,
          widget.index,
          newReason,
        );

        // Extract updated exclusion info from API response
        final Map<String, dynamic>? segment =
            response['segment'] as Map<String, dynamic>?;
        final bool updatedIsExcluded =
            segment?['is_excluded'] as bool? ?? (newReason != null);

        // Update local state
        setState(() {
          _localIsExcluded = updatedIsExcluded;
          _localExclusionReason = newReason;
        });

        // Refresh parent widget to get updated data
        // Pass updated exclusion info so parent can update metadata immediately
        if (widget.onExclusionUpdated != null) {
          await widget.onExclusionUpdated!(
            widget.index,
            exclusionReason: newReason,
            isExcluded: updatedIsExcluded,
          );
        }

        if (mounted) {
          final l10n = AppLocalizations.of(context)!;
          MessageService.showInfo(
            context,
            newReason == null
                ? l10n.segmentItemExclusionRemoved
                : l10n.segmentItemExclusionReasonUpdated,
          );
        }
      } catch (e) {
        // Show error message
        if (mounted) {
          MessageService.showError(
            context,
            AppLocalizations.of(context)!.segmentItemExclusionUpdateFailed('$e'),
          );
        }
      }
    }
  }

  Widget _buildEditMode() {
    final l10n = AppLocalizations.of(context)!;
    return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          // Editable text field with keyboard shortcuts
          Shortcuts(
            shortcuts: const <ShortcutActivator, Intent>{
              SingleActivator(LogicalKeyboardKey.escape):
                  _CancelEditingIntent(),
              SingleActivator(LogicalKeyboardKey.enter, control: true):
                  _SaveEditingIntent(),
              SingleActivator(LogicalKeyboardKey.enter, meta: true):
                  _SaveEditingIntent(),
              // Editing undo/redo shortcuts (when in editing mode)
              SingleActivator(LogicalKeyboardKey.keyZ, control: true):
                  _UndoEditingIntent(),
              SingleActivator(LogicalKeyboardKey.keyZ, meta: true):
                  _UndoEditingIntent(),
              SingleActivator(
                LogicalKeyboardKey.keyZ,
                control: true,
                shift: true,
              ): _RedoEditingIntent(),
              SingleActivator(
                LogicalKeyboardKey.keyZ,
                meta: true,
                shift: true,
              ): _RedoEditingIntent(),
              SingleActivator(LogicalKeyboardKey.keyY, control: true):
                  _RedoEditingIntent(),
            },
            child: Actions(
              actions: <Type, Action<Intent>>{
                _CancelEditingIntent: CallbackAction<_CancelEditingIntent>(
                  onInvoke: (_) => _cancelEditing(),
                ),
                _SaveEditingIntent: CallbackAction<_SaveEditingIntent>(
                  onInvoke: (_) => _saveEditing(),
                ),
                _UndoEditingIntent: CallbackAction<_UndoEditingIntent>(
                  onInvoke: (_) {
                    if (_isEditing && _canUndoEditing) {
                      _undoEditing();
                    }
                    return null;
                  },
                ),
                _RedoEditingIntent: CallbackAction<_RedoEditingIntent>(
                  onInvoke: (_) {
                    if (_isEditing && _canRedoEditing) {
                      _redoEditing();
                    }
                    return null;
                  },
                ),
              },
              child: Focus(
                child: _buildAdaptiveEditorField(),
              ),
            ),
          ),
          const SizedBox(height: 8),
          // Action buttons
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: <Widget>[
              // Local Undo/Redo buttons
              // In editing mode: operate on edit history (Office-like)
              // Not in editing mode: operate on segment revision history (Save operations)
              if (_isEditing) ...<Widget>[
                // Editing mode: use edit history undo/redo
                IconButton(
                  icon: const Icon(Icons.undo, size: 18),
                  tooltip: l10n.segmentItemUndoEditTooltip,
                  onPressed: _canUndoEditing ? _undoEditing : null,
                  color: _canUndoEditing
                      ? Colors.blue.shade700
                      : Colors.grey.shade400,
                  padding: const EdgeInsets.all(8),
                  constraints:
                      const BoxConstraints(minWidth: 32, minHeight: 32),
                ),
                IconButton(
                  icon: const Icon(Icons.redo, size: 18),
                  tooltip: l10n.segmentItemRedoEditTooltip,
                  onPressed: _canRedoEditing ? _redoEditing : null,
                  color: _canRedoEditing
                      ? Colors.blue.shade700
                      : Colors.grey.shade400,
                  padding: const EdgeInsets.all(8),
                  constraints:
                      const BoxConstraints(minWidth: 32, minHeight: 32),
                ),
                const SizedBox(width: 8),
              ] else if (widget.onUndo != null ||
                  widget.onRedo != null) ...<Widget>[
                // Not editing: use segment revision undo/redo (Save operations)
                IconButton(
                  icon: const Icon(Icons.undo, size: 18),
                  tooltip: l10n.segmentItemUndoSaveTooltip,
                  onPressed: widget.canUndo && widget.onUndo != null
                      ? () => widget.onUndo!(widget.index)
                      : null,
                  color: widget.canUndo
                      ? Colors.blue.shade700
                      : Colors.grey.shade400,
                  padding: const EdgeInsets.all(8),
                  constraints:
                      const BoxConstraints(minWidth: 32, minHeight: 32),
                ),
                IconButton(
                  icon: const Icon(Icons.redo, size: 18),
                  tooltip: l10n.segmentItemRedoSaveTooltip,
                  onPressed: widget.canRedo && widget.onRedo != null
                      ? () => widget.onRedo!(widget.index)
                      : null,
                  color: widget.canRedo
                      ? Colors.blue.shade700
                      : Colors.grey.shade400,
                  padding: const EdgeInsets.all(8),
                  constraints:
                      const BoxConstraints(minWidth: 32, minHeight: 32),
                ),
                const SizedBox(width: 8),
              ],
              TextButton(
                onPressed: _cancelEditing,
                child: Text(l10n.segmentItemCancel),
              ),
              const SizedBox(width: 8),
              ElevatedButton.icon(
                onPressed: _saveEditing,
                icon: const Icon(Icons.save, size: 16),
                label: Text(l10n.segmentItemSave),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green.shade700,
                  foregroundColor: Colors.white,
                ),
              ),
            ],
          ),
          // Keyboard shortcut hint
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              l10n.segmentItemEditShortcutHint,
              style: TextStyle(
                fontSize: 11,
                color: Colors.grey.shade600,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),
        ],
      );
  }

  Widget _buildAdaptiveEditorField() {
    final l10n = AppLocalizations.of(context)!;
    final textStyle = TextStyle(fontSize: widget.editFontSize ?? 16.0);
    return ValueListenableBuilder<TextEditingValue>(
      valueListenable: _textController,
      builder: (context, value, _) => LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          final double mediaWidth = MediaQuery.of(context).size.width;
          var availableWidth =
              constraints.maxWidth.isFinite ? constraints.maxWidth : mediaWidth;
          availableWidth = math.max(120, availableWidth - 24);

          final TextPainter painter = TextPainter(
            text: TextSpan(
              text: value.text.isEmpty ? ' ' : value.text,
              style: textStyle,
            ),
            textDirection: Directionality.of(context),
            textAlign: TextAlign.left,
          )..layout(maxWidth: availableWidth);

          final double lineHeight = painter.preferredLineHeight == 0
              ? (textStyle.fontSize ?? 16) * 1.2
              : painter.preferredLineHeight;
          const double minLines = 3;
          const double maxLines = 12;
          final minHeight = lineHeight * minLines + 24;
          final maxHeight = lineHeight * maxLines + 24;
          final contentHeight = painter.size.height + 24;
          final editorHeight = contentHeight.clamp(minHeight, maxHeight);

          return ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: minHeight,
              maxHeight: maxHeight,
            ),
            child: SizedBox(
              height: editorHeight,
              child: TextField(
                controller: _textController,
                focusNode: _editFocusNode,
                expands: true,
                maxLines: null,
                textAlignVertical: TextAlignVertical.top,
                decoration: InputDecoration(
                  hintText: l10n.segmentItemTranslationHint,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(4),
                  ),
                  contentPadding: const EdgeInsets.all(12),
                ),
                style: textStyle,
              ),
            ),
          );
        },
      ),
    );
  }
}

/// Mini rotation preview for the angle picker menu.
class _RotationPreviewIcon extends StatelessWidget {
  const _RotationPreviewIcon({
    required this.degrees,
    required this.color,
  });

  final int degrees;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 22,
      height: 16,
      child: Center(
        child: Transform.rotate(
          angle: degrees * math.pi / 180.0,
          child: Icon(
            Icons.text_rotation_none,
            size: 14,
            color: degrees == 0 ? color.withValues(alpha: 0.45) : color,
          ),
        ),
      ),
    );
  }
}

/// Mini table border style preview icon for PDF revision menu.
class _TableBorderStylePreviewIcon extends StatelessWidget {
  const _TableBorderStylePreviewIcon({
    required this.style,
    required this.color,
  });

  final String style;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 22,
      height: 16,
      child: CustomPaint(
        painter: _TableBorderStylePreviewPainter(
          style: style,
          color: color,
        ),
      ),
    );
  }
}

class _TableBorderStylePreviewPainter extends CustomPainter {
  _TableBorderStylePreviewPainter({
    required this.style,
    required this.color,
  });

  final String style;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final Rect bounds = Rect.fromLTWH(1, 1, size.width - 2, size.height - 2);
    final Paint linePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    switch (style) {
      case 'booktabs':
      case 'booktabs_2':
      case 'booktabs_3':
        canvas.drawLine(
          Offset(bounds.left, bounds.top),
          Offset(bounds.right, bounds.top),
          linePaint,
        );
        final int headerRows = style == 'booktabs_3'
            ? 3
            : style == 'booktabs_2'
                ? 2
                : 1;
        final double headerBand = bounds.height * 0.28 / headerRows;
        for (int row = 1; row <= headerRows; row++) {
          final double y = bounds.top + headerBand * row;
          canvas.drawLine(
            Offset(bounds.left, y),
            Offset(bounds.right, y),
            linePaint,
          );
        }
        canvas.drawLine(
          Offset(bounds.left, bounds.bottom),
          Offset(bounds.right, bounds.bottom),
          linePaint,
        );
        break;
      case 'horizontal':
        for (final double y in <double>[0.0, 0.28, 0.56, 0.84, 1.0]) {
          final double py = bounds.top + bounds.height * y;
          canvas.drawLine(
            Offset(bounds.left, py),
            Offset(bounds.right, py),
            linePaint,
          );
        }
        break;
      case 'outer':
        canvas.drawRect(bounds, linePaint);
        break;
      case 'none':
        final Paint dashed = Paint()
          ..color = color.withValues(alpha: 0.35)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1;
        canvas.drawRect(bounds, dashed);
        break;
      case 'grid':
      default:
        canvas.drawRect(bounds, linePaint);
        canvas.drawLine(
          Offset(bounds.left, bounds.center.dy),
          Offset(bounds.right, bounds.center.dy),
          linePaint,
        );
        canvas.drawLine(
          Offset(bounds.center.dx, bounds.top),
          Offset(bounds.center.dx, bounds.bottom),
          linePaint,
        );
    }
  }

  @override
  bool shouldRepaint(covariant _TableBorderStylePreviewPainter oldDelegate) {
    return oldDelegate.style != style || oldDelegate.color != color;
  }
}

IconData _tableBorderStyleIcon(String style) {
  switch (style) {
    case 'booktabs':
    case 'booktabs_2':
    case 'booktabs_3':
      return Icons.table_rows_outlined;
    case 'horizontal':
      return Icons.horizontal_rule;
    case 'outer':
      return Icons.crop_square_outlined;
    case 'none':
      return Icons.border_clear_outlined;
    case 'grid':
    default:
      return Icons.grid_on_outlined;
  }
}

/// Mini 2x2 grid preview for table border weight (Word/Excel-style menu icon).
class _TableGridPreviewIcon extends StatelessWidget {
  const _TableGridPreviewIcon({
    required this.strokePt,
    required this.color,
  });

  final double strokePt;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 22,
      height: 16,
      child: CustomPaint(
        painter: _TableGridPreviewPainter(
          strokePt: strokePt,
          color: color,
        ),
      ),
    );
  }
}

class _TableGridPreviewPainter extends CustomPainter {
  _TableGridPreviewPainter({
    required this.strokePt,
    required this.color,
  });

  final double strokePt;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final Rect bounds = Rect.fromLTWH(1, 1, size.width - 2, size.height - 2);
    if (strokePt <= 0) {
      final Paint dashed = Paint()
        ..color = color.withValues(alpha: 0.35)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1;
      canvas.drawRect(bounds, dashed);
      return;
    }

    final double previewStroke = switch (strokePt) {
      <= 0.5 => 0.8,
      <= 1.0 => 1.1,
      _ => 1.4,
    };
    final Paint linePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = previewStroke;

    canvas.drawRect(bounds, linePaint);
    canvas.drawLine(
      Offset(bounds.left, bounds.center.dy),
      Offset(bounds.right, bounds.center.dy),
      linePaint,
    );
    canvas.drawLine(
      Offset(bounds.center.dx, bounds.top),
      Offset(bounds.center.dx, bounds.bottom),
      linePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _TableGridPreviewPainter oldDelegate) {
    return oldDelegate.strokePt != strokePt || oldDelegate.color != color;
  }
}
