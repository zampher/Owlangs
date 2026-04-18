// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart'
    show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter/widgets.dart' show HardwareKeyboard;

/// Floating search box widget similar to Cursor Terminal search box
///
/// This widget displays a floating search box that can be positioned
/// over content panels. It supports keyboard shortcuts (Ctrl+F / Cmd+F)
/// and provides search functionality with next/previous navigation.
class SegmentSearchBox extends StatefulWidget {
  const SegmentSearchBox({
    required this.onSearch,
    required this.onClose,
    this.initialQuery = '',
    this.matchCount = 0,
    this.currentMatchIndex = 0,
    this.onNextMatch,
    this.onPreviousMatch,
    super.key,
  });

  /// Callback when search query changes
  final void Function(String query) onSearch;

  /// Callback when search box is closed
  final VoidCallback onClose;

  /// Initial search query
  final String initialQuery;

  /// Total number of matches found
  final int matchCount;

  /// Current match index (0-based)
  final int currentMatchIndex;

  /// Callback for navigating to next match
  final VoidCallback? onNextMatch;

  /// Callback for navigating to previous match
  final VoidCallback? onPreviousMatch;

  @override
  State<SegmentSearchBox> createState() => _SegmentSearchBoxState();
}

class _SegmentSearchBoxState extends State<SegmentSearchBox> {
  late final TextEditingController _controller;
  late final FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialQuery);
    _focusNode = FocusNode();

    // Focus the text field when widget is created
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _focusNode.requestFocus();
      // Select all text if there's initial query
      if (widget.initialQuery.isNotEmpty) {
        _controller.selection = TextSelection(
          baseOffset: 0,
          extentOffset: widget.initialQuery.length,
        );
      }
    });
  }

  @override
  void didUpdateWidget(SegmentSearchBox oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Update controller if initialQuery changes externally
    if (widget.initialQuery != oldWidget.initialQuery &&
        widget.initialQuery != _controller.text) {
      _controller.text = widget.initialQuery;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _handleSearch(String query) {
    widget.onSearch(query);
  }

  void _handleKeyEvent(KeyEvent event) {
    // Handle Escape key to close search box
    if (event is KeyDownEvent &&
        event.logicalKey == LogicalKeyboardKey.escape) {
      widget.onClose();
      return;
    }

    // Handle Enter key for next match
    if (event is KeyDownEvent && event.logicalKey == LogicalKeyboardKey.enter) {
      if (HardwareKeyboard.instance.isShiftPressed &&
          widget.onPreviousMatch != null) {
        widget.onPreviousMatch?.call();
      } else if (widget.onNextMatch != null) {
        widget.onNextMatch?.call();
      }
      return;
    }

    // Handle F3 for next match (Windows/Linux)
    if (event is KeyDownEvent && event.logicalKey == LogicalKeyboardKey.f3) {
      if (HardwareKeyboard.instance.isShiftPressed &&
          widget.onPreviousMatch != null) {
        widget.onPreviousMatch?.call();
      } else if (widget.onNextMatch != null) {
        widget.onNextMatch?.call();
      }
      return;
    }
  }

  @override
  Widget build(BuildContext context) {
    final bool isMac = !kIsWeb && defaultTargetPlatform == TargetPlatform.macOS;
    final String nextShortcut = isMac ? 'Enter' : 'Enter / F3';
    final String prevShortcut =
        isMac ? 'Shift+Enter' : 'Shift+Enter / Shift+F3';

    return KeyboardListener(
      focusNode: FocusNode(),
      onKeyEvent: _handleKeyEvent,
      child: Material(
        elevation: 8,
        borderRadius: BorderRadius.circular(4),
        color: Theme.of(context).colorScheme.surface,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          constraints: const BoxConstraints(
            minWidth: 300,
            maxWidth: 400,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              // Search icon
              Icon(
                Icons.search,
                size: 16,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 8),
              // Search input field
              Expanded(
                child: TextField(
                  controller: _controller,
                  focusNode: _focusNode,
                  autofocus: true,
                  style: TextStyle(
                    fontSize: 13,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                  decoration: InputDecoration(
                    hintText: 'Search...',
                    hintStyle: TextStyle(
                      fontSize: 13,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                    border: InputBorder.none,
                    isDense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                  onChanged: _handleSearch,
                  textInputAction: TextInputAction.search,
                ),
              ),
              const SizedBox(width: 8),
              // Match count and navigation
              if (widget.matchCount > 0) ...<Widget>[
                Text(
                  '${widget.currentMatchIndex + 1}/${widget.matchCount}',
                  style: TextStyle(
                    fontSize: 11,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(width: 8),
                // Previous match button
                if (widget.onPreviousMatch != null)
                  Tooltip(
                    message: 'Previous ($prevShortcut)',
                    child: IconButton(
                      icon: const Icon(Icons.arrow_upward, size: 16),
                      onPressed: widget.onPreviousMatch,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 24,
                        minHeight: 24,
                      ),
                      tooltip: 'Previous',
                    ),
                  ),
                // Next match button
                if (widget.onNextMatch != null)
                  Tooltip(
                    message: 'Next ($nextShortcut)',
                    child: IconButton(
                      icon: const Icon(Icons.arrow_downward, size: 16),
                      onPressed: widget.onNextMatch,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 24,
                        minHeight: 24,
                      ),
                      tooltip: 'Next',
                    ),
                  ),
              ] else if (_controller.text.isNotEmpty) ...<Widget>[
                Text(
                  'No matches',
                  style: TextStyle(
                    fontSize: 11,
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
                const SizedBox(width: 8),
              ],
              // Close button
              Tooltip(
                message: 'Close (Esc)',
                child: IconButton(
                  icon: const Icon(Icons.close, size: 16),
                  onPressed: widget.onClose,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 24,
                    minHeight: 24,
                  ),
                  tooltip: 'Close',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
