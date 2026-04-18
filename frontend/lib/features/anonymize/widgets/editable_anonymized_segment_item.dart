// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../shared/utils/message_service.dart';

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

/// Editable anonymized segment item widget with inline editing support
class EditableAnonymizedSegmentItem extends StatefulWidget {
  const EditableAnonymizedSegmentItem({
    required this.text,
    required this.index,
    required this.isHighlighted,
    required this.onTap,
    required this.onEdit,
    super.key,
    this.highlightText,
    this.itemKey,
    this.badgeColor,
    this.badgeTextColor,
    this.fontSize,
  });
  final String text;
  final int index;
  final bool isHighlighted;
  final String? highlightText; // Text to highlight within the segment
  final VoidCallback onTap;
  final Function(String newText) onEdit; // Callback when text is edited
  final GlobalKey? itemKey;
  final Color? badgeColor;
  final Color? badgeTextColor;
  final double? fontSize;

  @override
  State<EditableAnonymizedSegmentItem> createState() =>
      _EditableAnonymizedSegmentItemState();
}

class _EditableAnonymizedSegmentItemState
    extends State<EditableAnonymizedSegmentItem> {
  bool _isEditing = false;
  bool _isHovered = false;
  bool _isSelectingText = false; // Track if user is selecting text
  late TextEditingController _textController;
  String _originalText = '';

  // Edit history stack for undo/redo during editing (like Office)
  final List<String> _editHistory = <String>[]; // Past states (oldest first)
  String? _currentEditText; // Current editing text
  final List<String> _editFuture = <String>[]; // Redo stack (newest first)

  // Track last text to detect changes
  String _lastText = '';

  // Flag to prevent recording history during undo/redo operations
  bool _isUndoRedoOperation = false;

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController(text: widget.text);
    _originalText = widget.text;
    _lastText = widget.text;

    // Listen to text changes to build edit history
    _textController.addListener(_onTextChanged);
  }

  void _onTextChanged() {
    if (!_isEditing || _isUndoRedoOperation) return;

    final String currentText = _textController.text;
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
  void didUpdateWidget(EditableAnonymizedSegmentItem oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.text != widget.text) {
      // If not editing, always update
      if (!_isEditing) {
        _textController.text = widget.text;
        _originalText = widget.text;
      } else {
        // In editing mode, this is an external update
        _textController.text = widget.text;
        _originalText = widget.text;
      }
    }
  }

  @override
  void dispose() {
    _textController.removeListener(_onTextChanged);
    _textController.dispose();
    super.dispose();
  }

  void _startEditing() {
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
    final String previousText = _editHistory.removeLast();
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
    final String nextText = _editFuture.removeAt(0);
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
  }

  Future<void> _saveEditing() async {
    final String newText = _textController.text.trim();
    if (newText == _originalText) {
      _cancelEditing();
      return;
    }

    if (newText.isEmpty) {
      // Don't allow empty text
      return;
    }

    try {
      await widget.onEdit(newText);
      if (mounted) {
        setState(() {
          _isEditing = false;
          _originalText = newText;
          _lastText = newText;
          // Clear edit history when saving
          _editHistory.clear();
          _editFuture.clear();
          _currentEditText = null;
        });
      }
    } catch (e) {
      // Show error message
      if (mounted) {
        MessageService.showError(context, 'Failed to save: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final int displayIndex = widget.index + 1; // 1-based display
    final ThemeData theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;
    final Color badgeColor = widget.badgeColor ??
        (isDark ? theme.colorScheme.primaryContainer : Colors.orange.shade50);
    final Color badgeTextColor = widget.badgeTextColor ??
        (isDark
            ? theme.colorScheme.onPrimaryContainer
            : Colors.orange.shade700);
    final Color highlightColor = widget.isHighlighted
        ? (isDark
            ? theme.colorScheme.primaryContainer.withOpacity(0.5)
            : Colors.orange.shade100)
        : (_isHovered
            ? theme.colorScheme.onSurfaceVariant.withOpacity(0.06)
            : Colors.transparent);

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        key: widget.itemKey,
        behavior: HitTestBehavior.opaque,
        onTap: _isEditing ? null : widget.onTap,
        onDoubleTap: _startEditing,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          decoration: BoxDecoration(
            color: highlightColor,
            borderRadius: BorderRadius.circular(4),
            border: widget.isHighlighted
                ? Border.all(color: theme.colorScheme.primary, width: 2)
                : null,
          ),
          child: _isEditing
              ? _buildEditMode(badgeColor, badgeTextColor, displayIndex)
              : _buildViewMode(badgeColor, badgeTextColor, displayIndex),
        ),
      ),
    );
  }

  Widget _buildViewMode(
    Color badgeColor,
    Color badgeTextColor,
    int displayIndex,
  ) =>
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          // Segment number badge
          GestureDetector(
            onTap: widget.onTap,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
          ),
          const SizedBox(width: 12),
          // Segment text with highlighting support
          Expanded(
            child:
                widget.highlightText != null && widget.highlightText!.isNotEmpty
                    ? _buildHighlightedText()
                    : _buildSelectableTextWithTap(),
          ),
        ],
      );

  Widget _buildHighlightedText() {
    final String text = widget.text;
    final String highlightText = widget.highlightText!;
    final double fontSize = widget.fontSize ?? 14;

    // Find all occurrences of the highlight text (case-insensitive)
    final String highlightLower = highlightText.toLowerCase();
    final String textLower = text.toLowerCase();

    if (!textLower.contains(highlightLower)) {
      // No match found, return plain text
      return SelectableText(
        text,
        style: TextStyle(fontSize: fontSize),
      );
    }

    // Build TextSpan with highlights
    final List<TextSpan> spans = <TextSpan>[];
    var lastIndex = 0;

    while (true) {
      final int index = textLower.indexOf(highlightLower, lastIndex);
      if (index == -1) break;

      // Add text before highlight
      if (index > lastIndex) {
        spans.add(
          TextSpan(
            text: text.substring(lastIndex, index),
            style: TextStyle(fontSize: fontSize),
          ),
        );
      }

      // Add highlighted text
      final int highlightEnd = index + highlightText.length;
      spans.add(
        TextSpan(
          text: text.substring(index, highlightEnd),
          style: TextStyle(
            fontSize: fontSize,
            backgroundColor: Colors.yellow.withOpacity(0.5),
            fontWeight: FontWeight.bold,
          ),
        ),
      );

      lastIndex = highlightEnd;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      spans.add(
        TextSpan(
          text: text.substring(lastIndex),
          style: TextStyle(fontSize: fontSize),
        ),
      );
    }

    return SelectableText.rich(
      TextSpan(children: spans),
    );
  }

  /// Build SelectableText with tap handling for segment selection
  Widget _buildSelectableTextWithTap() => Listener(
        onPointerDown: (_) {
          // Reset text selection flag when pointer down
          _isSelectingText = false;
        },
        onPointerMove: (_) {
          // User is dragging, likely selecting text
          _isSelectingText = true;
        },
        onPointerUp: (_) {
          // If user wasn't selecting text, trigger segment selection
          if (!_isSelectingText) {
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
          onTap: () {
            // Only trigger if not selecting text and not editing
            if (!_isSelectingText && !_isEditing) {
              widget.onTap();
            }
          },
          behavior: HitTestBehavior.translucent,
          child: SelectableText(
            widget.text,
            style: TextStyle(
              fontSize: widget.fontSize ?? 14,
            ),
          ),
        ),
      );

  Widget _buildEditMode(
    Color badgeColor,
    Color badgeTextColor,
    int displayIndex,
  ) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          // Segment number badge (non-editable in edit mode)
          Row(
            children: <Widget>[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
            ],
          ),
          const SizedBox(height: 8),
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
                child: TextField(
                  controller: _textController,
                  maxLines: null,
                  minLines: 3,
                  decoration: InputDecoration(
                    hintText: 'Enter anonymized text...',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(4),
                    ),
                    contentPadding: const EdgeInsets.all(12),
                  ),
                  style: TextStyle(fontSize: widget.fontSize ?? 16.0),
                  autofocus: true,
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          // Action buttons
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: <Widget>[
              // Local Undo/Redo buttons
              IconButton(
                icon: const Icon(Icons.undo, size: 18),
                tooltip: 'Undo (Edit)',
                onPressed: _canUndoEditing ? _undoEditing : null,
                color: _canUndoEditing
                    ? Colors.blue.shade700
                    : Colors.grey.shade400,
                padding: const EdgeInsets.all(8),
                constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              ),
              IconButton(
                icon: const Icon(Icons.redo, size: 18),
                tooltip: 'Redo (Edit)',
                onPressed: _canRedoEditing ? _redoEditing : null,
                color: _canRedoEditing
                    ? Colors.blue.shade700
                    : Colors.grey.shade400,
                padding: const EdgeInsets.all(8),
                constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              ),
              const SizedBox(width: 8),
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
}
