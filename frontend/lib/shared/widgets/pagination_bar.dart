/// Pagination bar widget for navigating between pages.
library;

import 'package:flutter/material.dart';

/// Pagination bar widget.
///
/// Displays page navigation controls including:
/// - Previous/Next buttons
/// - Current page indicator
/// - Total pages
/// - Optional page jump input
class PaginationBar extends StatelessWidget {
  const PaginationBar({
    required this.currentPage,
    required this.totalPages,
    super.key,
    this.onPrevPage,
    this.onNextPage,
    this.onJumpToPage,
    this.hasPrev = true,
    this.hasNext = true,
    this.showPageJump = true,
    this.backgroundColor,
    this.textColor,
    this.height,
  });

  /// Current page (1-based)
  final int currentPage;

  /// Total number of pages
  final int totalPages;

  /// Callback when previous page is requested
  final VoidCallback? onPrevPage;

  /// Callback when next page is requested
  final VoidCallback? onNextPage;

  /// Callback when a specific page is requested
  final ValueChanged<int>? onJumpToPage;

  /// Whether previous button should be enabled
  final bool hasPrev;

  /// Whether next button should be enabled
  final bool hasNext;

  /// Whether to show page jump input
  final bool showPageJump;

  /// Custom styling
  final Color? backgroundColor;
  final Color? textColor;
  final double? height;

  @override
  Widget build(BuildContext context) {
    if (totalPages <= 1) {
      return const SizedBox.shrink();
    }

    final ThemeData theme = Theme.of(context);
    final Color bgColor = backgroundColor ?? theme.colorScheme.surface;
    final Color txtColor = textColor ?? theme.colorScheme.onSurface;

    return Container(
      height: height ?? 28, // Reduced from 36 to 28 for more compact display
      padding:
          const EdgeInsets.symmetric(horizontal: 2), // Further reduced padding
      decoration: BoxDecoration(
        color: bgColor,
        border: Border(
          top: BorderSide(color: theme.dividerColor),
        ),
      ),
      child: Row(
        mainAxisSize:
            MainAxisSize.min, // Allow shrink-wrapping when in unbounded width
        mainAxisAlignment: MainAxisAlignment.center,
        children: <Widget>[
          // Previous button
          IconButton(
            icon: const Icon(Icons.chevron_left),
            onPressed: hasPrev && onPrevPage != null ? onPrevPage : null,
            tooltip: 'Previous page',
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(
              minWidth: 24,
              minHeight: 24,
            ), // Further reduced from 28 to 24
            iconSize: 16, // Reduced icon size from 18 to 16
          ),

          // Page info
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: 2,
            ), // Further reduced from 4 to 2
            child: Row(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: <Widget>[
                Text(
                  'Page $currentPage of $totalPages',
                  style: TextStyle(
                    color: txtColor,
                    fontSize: 11,
                  ), // Reduced font size from 12 to 11
                ),
                if (showPageJump &&
                    onJumpToPage != null &&
                    totalPages > 5) ...<Widget>[
                  const SizedBox(width: 4), // Further reduced from 6 to 4
                  _PageJumpInput(
                    currentPage: currentPage,
                    totalPages: totalPages,
                    onJump: onJumpToPage!,
                  ),
                ],
              ],
            ),
          ),

          // Next button
          IconButton(
            icon: const Icon(Icons.chevron_right),
            onPressed: hasNext && onNextPage != null ? onNextPage : null,
            tooltip: 'Next page',
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(
              minWidth: 24,
              minHeight: 24,
            ), // Further reduced from 28 to 24
            iconSize: 16, // Reduced icon size from 18 to 16
          ),
        ],
      ),
    );
  }
}

/// Page jump input widget
class _PageJumpInput extends StatefulWidget {
  const _PageJumpInput({
    required this.currentPage,
    required this.totalPages,
    required this.onJump,
  });
  final int currentPage;
  final int totalPages;
  final ValueChanged<int> onJump;

  @override
  State<_PageJumpInput> createState() => _PageJumpInputState();
}

class _PageJumpInputState extends State<_PageJumpInput> {
  late TextEditingController _controller;
  final FocusNode _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.currentPage.toString());
  }

  @override
  void didUpdateWidget(_PageJumpInput oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.currentPage != widget.currentPage) {
      _controller.text = widget.currentPage.toString();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _handleJump() {
    final String text = _controller.text.trim();
    if (text.isEmpty) return;

    final int? page = int.tryParse(text);
    if (page == null) {
      _controller.text = widget.currentPage.toString();
      return;
    }

    if (page < 1 || page > widget.totalPages) {
      _controller.text = widget.currentPage.toString();
      return;
    }

    widget.onJump(page);
    _focusNode.unfocus();
  }

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 70, // Reduced from 80 to 70
        height: 28, // Add height constraint to make it more compact
        child: TextField(
          controller: _controller,
          focusNode: _focusNode,
          textAlign: TextAlign.center,
          keyboardType: TextInputType.number,
          style: const TextStyle(fontSize: 12), // Keep font size unchanged
          decoration: InputDecoration(
            isDense: true,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 6,
              vertical: 2,
            ), // Reduced padding
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(4),
            ),
            hintText: 'Page',
          ),
          onSubmitted: (_) => _handleJump(),
        ),
      );
}
