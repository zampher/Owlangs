// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Segment item widget with support for highlighting specific text within the segment
class HighlightableSegmentItem extends StatefulWidget {
  const HighlightableSegmentItem({
    required this.text,
    required this.index,
    super.key,
    this.isHighlighted = false,
    this.highlightText,
    this.onTap,
    this.onCopy,
    this.itemKey,
    this.onEdit,
    this.isEditable = false,
    this.badgeColor,
    this.badgeTextColor,
    this.fontSize,
    this.enableSelection = true,
  });
  final String text;
  final int index; // 0-based index
  final bool isHighlighted;
  final String? highlightText; // Text to highlight within the segment
  final VoidCallback? onTap;
  final VoidCallback?
      onCopy; // Deprecated: copy button removed, but kept for backward compatibility
  final GlobalKey? itemKey;
  final Function(String newText)? onEdit; // Callback when text is edited
  final bool isEditable; // Whether this segment can be edited
  final Color? badgeColor;
  final Color? badgeTextColor;
  final double? fontSize;
  final bool enableSelection;

  @override
  State<HighlightableSegmentItem> createState() =>
      _HighlightableSegmentItemState();
}

class _HighlightableSegmentItemState extends State<HighlightableSegmentItem> {
  bool _isHovered = false;
  bool _isSelectingText = false; // Track if user is selecting text

  @override
  Widget build(BuildContext context) {
    final int displayIndex = widget.index + 1; // 1-based display
    final ThemeData theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;
    final Color badgeColor = widget.badgeColor ??
        (isDark ? theme.colorScheme.primaryContainer : Colors.blue.shade50);
    final Color badgeTextColor = widget.badgeTextColor ??
        (isDark ? theme.colorScheme.onPrimaryContainer : Colors.blue.shade700);
    final Color highlightColor = widget.isHighlighted
        ? (isDark
            ? theme.colorScheme.primaryContainer.withOpacity(0.5)
            : Colors.blue.shade100)
        : (_isHovered
            ? theme.colorScheme.onSurfaceVariant.withOpacity(0.06)
            : Colors.transparent);

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        behavior: HitTestBehavior
            .translucent, // Allow taps to pass through to SelectableText when selecting text
        child: Container(
          key: widget.itemKey,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          decoration: BoxDecoration(
            color: highlightColor,
            borderRadius: BorderRadius.circular(4),
            border: widget.isHighlighted
                ? Border.all(color: theme.colorScheme.primary, width: 2)
                : null,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Segment number badge (clickable area for segment selection)
              GestureDetector(
                onTap: widget.onTap,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
                child: widget.highlightText != null &&
                        widget.highlightText!.isNotEmpty
                    ? _buildHighlightedText()
                    : (widget.enableSelection
                        ? _buildSelectableTextWithTap()
                        : GestureDetector(
                            onTap: widget.onTap,
                            child: Text(
                              widget.text,
                              style: TextStyle(
                                fontSize: widget.fontSize ?? 14,
                              ),
                            ),
                          )),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHighlightedText() {
    final String text = widget.text;
    final String highlightText = widget.highlightText!;
    final double fontSize = widget.fontSize ?? 14;

    // Find all occurrences of the highlight text (case-insensitive)
    final String highlightLower = highlightText.toLowerCase();
    final String textLower = text.toLowerCase();

    if (!textLower.contains(highlightLower)) {
      // No match found, return plain text
      return widget.enableSelection
          ? SelectableText(
              text,
              style: TextStyle(fontSize: fontSize),
            )
          : Text(
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

    // Wrap SelectableText.rich with GestureDetector to handle taps
    final Widget textWidget = widget.enableSelection
        ? SelectableText.rich(
            TextSpan(children: spans),
          )
        : RichText(
            text: TextSpan(children: spans),
          );

    // If onTap is provided, wrap with GestureDetector to handle segment selection
    if (widget.onTap != null) {
      return GestureDetector(
        onTap: widget.onTap,
        behavior: HitTestBehavior.translucent,
        child: textWidget,
      );
    }

    return textWidget;
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
          if (!_isSelectingText && widget.onTap != null) {
            // Small delay to check if text selection occurred
            Future.delayed(const Duration(milliseconds: 100), () {
              if (mounted && !_isSelectingText) {
                widget.onTap?.call();
              }
            });
          }
          _isSelectingText = false;
        },
        child: GestureDetector(
          onTap: () {
            // Only trigger if not selecting text
            if (!_isSelectingText && widget.onTap != null) {
              widget.onTap?.call();
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
}
