// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../shared/utils/message_service.dart';
import '../../../../shared/utils/app_logger.dart';
import '../../../../shared/widgets/markdown_text_with_images.dart';
import '../../models/exclusion_reason.dart';
import '../../../../shared/services/translation_service.dart';
import '../common/exclusion_reason_editor.dart';

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
  final Function(int index)?
      onExclusionUpdated; // Callback when exclusion reason is updated
  final Function(int index)? onFormulaFix; // Callback to trigger LLM formula repair

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
  bool _localIsCleared = false;

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
    if (oldWidget.isCleared != widget.isCleared) {
      _localIsCleared = widget.isCleared;
    }
  }

  @override
  void dispose() {
    _textController.removeListener(_onTextChanged);
    _textController.dispose();
    _editFocusNode.dispose();
    super.dispose();
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
        MessageService.showError(context, 'Failed to save: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) => GestureDetector(
        key: widget.itemKey,
        behavior: HitTestBehavior.opaque, // Ensure entire area is clickable
        onTap: _isEditing ? null : widget.onTap, // Click anywhere to select
        onDoubleTap: widget.isSource || widget.onEdit == null
            ? null
            : () {
                AppLogger.log(
                  'TranslationSegmentItem',
                  'OUTER GestureDetector.onDoubleTap: index=${widget.index}, isSource=${widget.isSource}, onEdit=${widget.onEdit != null}, _isEditing=$_isEditing',
                  level: LogLevel.info,
                );
                _startEditing();
              },
        child: Container(
          // Use ValueKey to force ItemWithHeightMeasurement to remeasure when edit mode changes
          // This ensures height cache is updated when switching between edit and preview modes
          key: ValueKey('segment_${widget.index}_editing_$_isEditing'),
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
          child: _isEditing ? _buildEditMode() : _buildViewMode(),
        ),
      );

  Widget _buildViewMode() {
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
                    if (!_isSelectingText && !_isEditing) {
                      // Small delay to check if text selection occurred
                      Future.delayed(const Duration(milliseconds: 100), () {
                        if (mounted && !_isSelectingText && !_isEditing) {
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
                      // Use GestureDetector to avoid focusing inputs during pointer down on Web.
                      if (!widget.isSource &&
                          widget.onEdit != null &&
                          !_isEditing) {
                        AppLogger.log(
                          'TranslationSegmentItem',
                          'GestureDetector.onDoubleTap: Starting edit for index=${widget.index}',
                          level: LogLevel.info,
                        );
                        _startEditing();
                      }
                    },
                    onTap: () {
                      // Only trigger if not selecting text and not editing
                      if (!_isSelectingText && !_isEditing) {
                        widget.onTap();
                      }
                    },
                    child: MarkdownTextWithImages(
                      text: widget.text,
                      imageDataMap: widget.imageDataMap.isEmpty
                          ? null
                          : widget.imageDataMap,
                      style: TextStyle(
                        fontSize: widget.previewFontSize ?? 14.0,
                        color: Theme.of(context).colorScheme.onSurface,
                        decoration:
                            widget.isModified ? TextDecoration.none : null,
                      ),
                      imageMaxWidth: double.infinity,
                      imageMaxHeight: 400,
                    ),
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
                      (widget.onExclude != null && !_localIsExcluded) ||
                      (widget.onClear != null &&
                          widget.text.isNotEmpty &&
                          !_localIsCleared)))
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Row(
                    children: <Widget>[
                      // Platform badge
                      if (widget.platformUsed != null)
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
                      // Mark for retry button (if not already marked for retry and not excluded)
                      // Can be shown even if failed (failed segments can also be marked for retry)
                      if (!_localNeedsRetry &&
                          !_localIsExcluded &&
                          widget.onMarkForRetry != null)
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
                                      'Retry',
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
                      // Unmark retry button (icon + text button to unmark for retry)
                      // Only show if needsRetry is true (not for failed segments)
                      if (_localNeedsRetry)
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
                                      'Marked Retry',
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
                      // Excluded badge (clickable to edit, with quick unexclude x button)
                      if (_localIsExcluded)
                        Padding(
                          padding: const EdgeInsets.only(left: 4),
                          child: _buildExclusionBadge(context),
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
                                      'Exclude',
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
                                      'Cleared',
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
                                      'Clear',
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
                      if (!_localIsCleared &&
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
                                      'Fix formula',
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

  /// Build exclusion badge with reason-specific styling
  /// New design: Badge body for quick unexclude, edit button for editing, x button for quick unexclude
  Widget _buildExclusionBadge(BuildContext context) {
    final reason = ExclusionReason.fromString(widget.exclusionReason);
    final bool isDark = Theme.of(context).brightness == Brightness.dark;
    final bool canUnexclude = reason.canUnexclude && widget.onUnexclude != null;
    final bool canEdit = widget.taskId != null;

    // Build display text with EX prefix
    final String displayText = 'EX: ${reason.displayName}';

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
                    });
                    // Then call the callback (which will update backend)
                    widget.onUnexclude!(widget.index);
                  }
                : null,
            borderRadius: BorderRadius.circular(4),
            child: Tooltip(
              message: canUnexclude
                  ? 'Click to remove exclusion'
                  : 'This segment is automatically excluded and cannot be unexcluded',
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
            message: 'Click to edit exclusion reason',
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
            message: 'Click to remove exclusion',
            child: GestureDetector(
              behavior: HitTestBehavior
                  .opaque, // Prevent event propagation to parent InkWell
              onTap: () {
                // Update local state immediately for instant UI feedback
                setState(() {
                  _localIsExcluded = false;
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
    final String? newReason = await showDialog<String?>(
      context: context,
      builder: (context) => ExclusionReasonEditor(
        currentReason: widget.exclusionReason,
      ),
    );

    if (newReason != widget.exclusionReason && widget.taskId != null) {
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
        });

        // Refresh parent widget to get updated data
        // Pass updated exclusion info so parent can update metadata immediately
        if (widget.onExclusionUpdated != null) {
          widget.onExclusionUpdated!(widget.index);
        }

        if (mounted) {
          MessageService.showInfo(
            context,
            newReason == null
                ? 'Exclusion removed'
                : 'Exclusion reason updated',
          );
        }
      } catch (e) {
        // Show error message
        if (mounted) {
          MessageService.showError(
            context,
            'Failed to update exclusion reason: $e',
          );
        }
      }
    }
  }

  Widget _buildEditMode() => Column(
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
                  tooltip: 'Undo (Edit)',
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
                  tooltip: 'Redo (Edit)',
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
                  tooltip: 'Undo (Save)',
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
                  tooltip: 'Redo (Save)',
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
                child: const Text('Cancel'),
              ),
              const SizedBox(width: 8),
              ElevatedButton.icon(
                onPressed: _saveEditing,
                icon: const Icon(Icons.save, size: 16),
                label: const Text('Save'),
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
              'Press Ctrl+Enter to save, Esc to cancel',
              style: TextStyle(
                fontSize: 11,
                color: Colors.grey.shade600,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),
        ],
      );

  Widget _buildAdaptiveEditorField() {
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
                  hintText: 'Enter translation...',
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
