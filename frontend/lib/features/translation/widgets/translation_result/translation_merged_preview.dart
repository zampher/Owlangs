// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../../shared/widgets/markdown_text_with_images.dart';

/// Clean-mode preview panel showing source/target text side by side
/// without segment labels/numbers or action buttons.
class TranslationMergedPreviewPanel extends StatefulWidget {
  const TranslationMergedPreviewPanel({
    required this.sourceParagraphs,
    required this.targetParagraphs,
    required this.scrollController,
    required this.highlightedIndexNotifier,
    required this.onHighlightParagraph,
    this.previewFontSize = 14.0,
    super.key,
  });

  final List<String> sourceParagraphs;
  final List<String> targetParagraphs;
  final ScrollController scrollController;
  final double previewFontSize;
  final ValueNotifier<int?> highlightedIndexNotifier;
  final void Function(int) onHighlightParagraph;

  @override
  State<TranslationMergedPreviewPanel> createState() =>
      _TranslationMergedPreviewPanelState();
}

class _TranslationMergedPreviewPanelState
    extends State<TranslationMergedPreviewPanel> {
  final Map<int, GlobalKey> _itemKeys = <int, GlobalKey>{};

  @override
  void initState() {
    super.initState();
    widget.highlightedIndexNotifier.addListener(_onHighlightChanged);
    // If a segment is already highlighted when this widget mounts
    // (e.g. after mode toggle), schedule a scroll to it.
    if (widget.highlightedIndexNotifier.value != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _scrollToHighlighted(widget.highlightedIndexNotifier.value!);
        }
      });
    }
  }

  @override
  void dispose() {
    widget.highlightedIndexNotifier.removeListener(_onHighlightChanged);
    super.dispose();
  }

  void _onHighlightChanged() {
    if (!mounted) return;
    setState(() {});
    final int? index = widget.highlightedIndexNotifier.value;
    if (index == null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _scrollToHighlighted(index);
    });
  }

  void _scrollToHighlighted(int index) {
    final GlobalKey? key = _itemKeys[index];
    if (key == null) return;
    final BuildContext? itemContext = key.currentContext;
    if (itemContext == null) return;
    try {
      Scrollable.ensureVisible(
        itemContext,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
        alignment: 0.1,
      );
    } catch (_) {
      // Scrollable not available yet — silently ignore.
    }
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final ColorScheme scheme = theme.colorScheme;

    final int itemCount = widget.sourceParagraphs.length;

    if (itemCount == 0) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(
            'No content available.',
            textAlign: TextAlign.center,
            style: TextStyle(color: scheme.onSurfaceVariant),
          ),
        ),
      );
    }

    return Scrollbar(
      controller: widget.scrollController,
      thickness: 8,
      radius: const Radius.circular(4),
      thumbVisibility: true,
      child: ListView.builder(
        controller: widget.scrollController,
        padding: const EdgeInsets.all(12),
        itemCount: itemCount,
        addAutomaticKeepAlives: true,
        itemBuilder: (BuildContext context, int index) {
          final GlobalKey itemKey =
              _itemKeys.putIfAbsent(index, () => GlobalKey());
          final bool hasSource = index < widget.sourceParagraphs.length;
          final bool hasTarget = index < widget.targetParagraphs.length;
          final String sourceText =
              hasSource ? widget.sourceParagraphs[index] : '';
          final String targetText =
              hasTarget ? widget.targetParagraphs[index] : '';
          final TextStyle textStyle =
              TextStyle(fontSize: widget.previewFontSize);
          final bool isHighlighted =
              widget.highlightedIndexNotifier.value == index;

          final Color highlightBg = theme.brightness == Brightness.dark
              ? Colors.amber.shade900.withOpacity(0.15)
              : Colors.amber.shade50.withOpacity(0.4);
          final Color defaultBg = scheme.surfaceContainerLow;

          return Padding(
            key: itemKey,
            padding: const EdgeInsets.only(bottom: 1),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                // Source paragraph (left panel)
                Expanded(
                  child: Listener(
                    onPointerDown: (_) => widget.onHighlightParagraph(index),
                    // translucent + Listener bypasses the gesture arena so taps
                    // work even over SelectableText (which would otherwise win
                    // the arena and block GestureDetector.onTap).
                    behavior: HitTestBehavior.translucent,
                    child: Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: isHighlighted ? highlightBg : defaultBg,
                        border: Border(
                          left: BorderSide(
                            color: isHighlighted
                                ? Colors.amber.shade400
                                : Colors.transparent,
                            width: 3,
                          ),
                          bottom: BorderSide(
                            color: theme.dividerColor.withOpacity(0.3),
                          ),
                        ),
                      ),
                      child: MarkdownTextWithImages(
                        text: sourceText,
                        style: textStyle,
                      ),
                    ),
                  ),
                ),
                // Segment ID in the gap between source and target
                SizedBox(
                  width: 24,
                  child: GestureDetector(
                    onTap: () => widget.onHighlightParagraph(index),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Container(
                          width: 1,
                          height: 12,
                          color: theme.dividerColor.withOpacity(0.2),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${index + 1}',
                          style: TextStyle(
                            fontSize: 10,
                            color: isHighlighted
                                ? Colors.amber.shade600
                                : scheme.onSurfaceVariant.withOpacity(0.5),
                            fontWeight:
                                isHighlighted ? FontWeight.w600 : FontWeight.w400,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Container(
                          width: 1,
                          height: 12,
                          color: theme.dividerColor.withOpacity(0.2),
                        ),
                      ],
                    ),
                  ),
                ),
                // Target paragraph (right panel)
                Expanded(
                  child: Listener(
                    onPointerDown: (_) => widget.onHighlightParagraph(index),
                    behavior: HitTestBehavior.translucent,
                    child: Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: isHighlighted ? highlightBg : defaultBg,
                        border: Border(
                          left: BorderSide(
                            color: isHighlighted
                                ? Colors.amber.shade400
                                : Colors.transparent,
                            width: 3,
                          ),
                          bottom: BorderSide(
                            color: theme.dividerColor.withOpacity(0.3),
                          ),
                        ),
                      ),
                      child: MarkdownTextWithImages(
                        text: targetText,
                        style: textStyle,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
