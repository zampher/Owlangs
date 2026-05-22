// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../../shared/widgets/markdown_text_with_images.dart';

/// Clean-mode preview panel showing source/target text side by side
/// without segment labels/numbers or action buttons.
class TranslationMergedPreviewPanel extends StatelessWidget {
  const TranslationMergedPreviewPanel({
    required this.sourceParagraphs,
    required this.targetParagraphs,
    required this.scrollController,
    this.previewFontSize = 14.0,
    super.key,
  });

  final List<String> sourceParagraphs;
  final List<String> targetParagraphs;
  final ScrollController scrollController;
  final double previewFontSize;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    final int itemCount = sourceParagraphs.length;

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
      controller: scrollController,
      thickness: 8,
      radius: const Radius.circular(4),
      thumbVisibility: true,
      child: ListView.builder(
        controller: scrollController,
        padding: const EdgeInsets.all(12),
        itemCount: itemCount,
        itemBuilder: (BuildContext context, int index) {
          final hasSource = index < sourceParagraphs.length;
          final hasTarget = index < targetParagraphs.length;
          final sourceText = hasSource ? sourceParagraphs[index] : '';
          final targetText = hasTarget ? targetParagraphs[index] : '';
          final textStyle = TextStyle(fontSize: previewFontSize);

          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                // Source paragraph (left panel)
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: theme.dividerColor.withOpacity(0.3),
                      ),
                    ),
                    child: MarkdownTextWithImages(
                      text: sourceText,
                      style: textStyle,
                    ),
                  ),
                ),
                // Thin divider
                SizedBox(
                  width: 16,
                  child: Center(
                    child: Container(
                      width: 1,
                      height: 40,
                      color: theme.dividerColor.withOpacity(0.3),
                    ),
                  ),
                ),
                // Target paragraph (right panel)
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: theme.dividerColor.withOpacity(0.3),
                      ),
                    ),
                    child: MarkdownTextWithImages(
                      text: targetText,
                      style: textStyle,
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
