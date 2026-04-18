// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

/// Service to parse translation content from Markdown or other formats
class TranslationContentParser {
  /// Parse Markdown content into paragraphs
  /// Returns a list of paragraphs (non-empty lines or paragraphs separated by blank lines)
  static List<String> parseMarkdownToParagraphs(String markdownContent) {
    final List<String> paragraphs = <String>[];

    // Split by double newlines (paragraphs)
    final List<String> parts = markdownContent.split(RegExp(r'\n\s*\n'));

    for (final String part in parts) {
      final List<String> lines = part.split('\n');
      final List<String> textLines = <String>[];

      for (final String line in lines) {
        final String trimmed = line.trim();
        // Skip empty lines, headings (starting with #), code blocks, and horizontal rules
        if (trimmed.isEmpty) continue;
        if (trimmed.startsWith('#') &&
            trimmed.length > 1 &&
            trimmed[1] == ' ') {
          continue;
        }
        if (trimmed.startsWith('```') || trimmed.startsWith('~~~')) continue;
        if (RegExp(r'^[-*_]{3,}$').hasMatch(trimmed)) continue;
        // Skip list markers at start of line
        if (RegExp(r'^[-*+]\s+').hasMatch(trimmed)) {
          // Extract text after marker
          final String text =
              trimmed.replaceFirst(RegExp(r'^[-*+]\s+'), '').trim();
          if (text.isNotEmpty) {
            textLines.add(text);
          }
          continue;
        }
        // Skip blockquote markers
        if (trimmed.startsWith('> ')) {
          final String text = trimmed.substring(2).trim();
          if (text.isNotEmpty) {
            textLines.add(text);
          }
          continue;
        }
        // Regular paragraph line
        if (trimmed.isNotEmpty) {
          textLines.add(trimmed);
        }
      }

      // Combine consecutive lines into paragraphs
      if (textLines.isNotEmpty) {
        paragraphs.add(textLines.join(' '));
      }
    }

    // If no paragraphs found, split by single newlines as fallback
    if (paragraphs.isEmpty) {
      final List<String> lines = markdownContent.split('\n');
      for (final String line in lines) {
        final String trimmed = line.trim();
        if (trimmed.isNotEmpty &&
            !trimmed.startsWith('#') &&
            !trimmed.startsWith('```') &&
            !trimmed.startsWith('~~~')) {
          paragraphs.add(trimmed);
        }
      }
    }

    return paragraphs;
  }

  /// Extract source and target paragraphs from a translated markdown file
  /// Note: This assumes the markdown contains only translated content
  /// For source content, we'd need a separate source file or backend API
  static Map<String, List<String>> parseTranslationContent(
    String markdownContent,
  ) {
    // For now, we only have translated content
    // In a full implementation, we'd need source content from elsewhere
    final List<String> translatedParagraphs =
        parseMarkdownToParagraphs(markdownContent);

    return <String, List<String>>{
      'source': <String>[], // Will be filled from source document if available
      'target': translatedParagraphs,
    };
  }
}
