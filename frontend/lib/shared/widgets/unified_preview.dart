// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../utils/html_stub.dart' if (dart.library.html) 'dart:html' as html;
import '../utils/ui_web_stub.dart' if (dart.library.html) 'dart:ui_web'
    as ui_web;
import 'package:webview_flutter/webview_flutter.dart';
import 'dart:convert';
import 'markdown_text_with_images.dart';
import '../providers/settings_provider.dart';
import '../utils/app_logger.dart';
import '../../core/constants/app_constants.dart';

void _unifiedPreviewLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('UnifiedPreview', message, level: level);
}

/// Unified preview widget that handles both original and translated content
/// Supports MD and HTML formats with images, formulas, and tables
class UnifiedPreview extends ConsumerStatefulWidget {
  const UnifiedPreview({
    required this.content,
    required this.contentType,
    required this.taskId,
    super.key,
    this.imageDataMap,
    this.enableSelection = true,
    this.fontSize,
    this.onDisablePointerEvents,
    this.onEnablePointerEvents,
  });

  /// Content to display (MD or HTML)
  final String content;

  /// Content type: 'md' or 'html'
  final String contentType;

  /// Image data map: {placeholder_id: {"data": "data:image/...", "alt": "title"}}
  final Map<String, Map<String, String>>? imageDataMap;

  /// Task ID for generating unique view IDs
  final String taskId;

  /// Enable text selection
  final bool enableSelection;

  /// Custom font size (if null, uses global settings)
  final double? fontSize;

  /// Callback to disable iframe pointer-events (for dialog display)
  final VoidCallback? onDisablePointerEvents;

  /// Callback to enable iframe pointer-events (after dialog closes)
  final VoidCallback? onEnablePointerEvents;

  @override
  ConsumerState<UnifiedPreview> createState() => _UnifiedPreviewState();
}

class _UnifiedPreviewState extends ConsumerState<UnifiedPreview> {
  String? _viewId;
  bool _iframeRegistered = false;

  @override
  Widget build(BuildContext context) {
    if (widget.content.isEmpty) {
      return const SizedBox.shrink();
    }

    // Check if content contains LaTeX formulas
    // Support multiple formats: $$...$$, $...$, \[...\], \(...\)
    final RegExp latexBlockPattern =
        RegExp(r'\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]');
    final RegExp latexInlinePattern =
        RegExp(r'\$(?!\$)[^\$]*?\$|\\\([^\\]*?\\\)');
    final bool hasLaTeX = latexBlockPattern.hasMatch(widget.content) ||
        latexInlinePattern.hasMatch(widget.content);

    // For HTML preview or MD with LaTeX, use HTML rendering with KaTeX
    if (widget.contentType == 'html' || hasLaTeX) {
      // Prepare HTML content
      String htmlContent;
      if (widget.contentType == 'html') {
        htmlContent = _wrapHtmlWithKaTeX(widget.content);
      } else {
        htmlContent = _wrapMarkdownInHtml(widget.content);
      }

      // Use iframe for web, fallback for desktop
      if (kIsWeb) {
        return _buildWebIframe(htmlContent);
      } else {
        // Desktop: show HTML source or use WebView if available
        return _buildDesktopHtmlPreview(htmlContent);
      }
    } else {
      // For MD without LaTeX, use MarkdownTextWithImages (better performance)
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);
      return SingleChildScrollView(
        child: Container(
          padding: const EdgeInsets.all(16),
          child: MarkdownTextWithImages(
            text: widget.content,
            imageDataMap: widget.imageDataMap,
            enableSelection: widget.enableSelection,
            style: TextStyle(
              fontSize: widget.fontSize ?? globalSettings.previewFontSize,
            ),
          ),
        ),
      );
    }
  }

  /// Build iframe for web platform
  Widget _buildWebIframe(String htmlContent) {
    if (!kIsWeb || htmlContent.isEmpty) {
      return const SizedBox.shrink();
    }

    try {
      // Create a unique view ID for the iframe
      _viewId ??=
          'unified_preview_${widget.taskId}_${DateTime.now().millisecondsSinceEpoch}';

      // Always use blob URL to avoid CSP issues
      final html.Blob blob = html.Blob(<dynamic>[htmlContent], 'text/html');
      final String iframeSrc = html.Url.createObjectUrlFromBlob(blob);

      // Create iframe element
      final html.IFrameElement iframe = html.IFrameElement()
        ..src = iframeSrc
        ..style.border = 'none'
        ..style.width = '100%'
        ..style.height = '100%'
        ..allowFullscreen = true
        ..id =
            'unified_preview_iframe_${widget.taskId}'; // Add ID for easy access

      // Add attribute for easy selection (for dialog pointer-events control)
      iframe.setAttribute('data-preview-iframe', 'true');

      // Set explicit z-index and position to ensure iframe stays below dialogs
      // This works together with the CSS in index.html
      iframe.style.zIndex = '1';
      iframe.style.position = 'relative';

      // Register the iframe with Flutter (only register once per viewId)
      if (!_iframeRegistered) {
        try {
          // ignore: undefined_prefixed_name
          ui_web.platformViewRegistry.registerViewFactory(
            _viewId!,
            (int viewId) => iframe,
          );
          _iframeRegistered = true;
        } catch (e) {
          _unifiedPreviewLog(
            'Error registering iframe: $e',
            level: LogLevel.error,
          );
          // If registration fails, try with a new viewId
          _viewId =
              'unified_preview_${widget.taskId}_${DateTime.now().millisecondsSinceEpoch}';
          try {
            // ignore: undefined_prefixed_name
            ui_web.platformViewRegistry.registerViewFactory(
              _viewId!,
              (int viewId) => iframe,
            );
            _iframeRegistered = true;
          } catch (e2) {
            _unifiedPreviewLog(
              'Failed to register iframe with new viewId: $e2',
              level: LogLevel.error,
            );
          }
        }
      }

      // Return HtmlElementView to display the iframe
      return HtmlElementView(
        viewType: _viewId!,
        onPlatformViewCreated: (id) {
          _unifiedPreviewLog('HtmlElementView created with id: $id');
        },
      );
    } catch (e, stackTrace) {
      _unifiedPreviewLog(
        'Error creating iframe: $e\n$stackTrace',
        level: LogLevel.error,
      );
      return _buildFallbackPreview();
    }
  }

  /// Build desktop HTML preview using WebView
  Widget _buildDesktopHtmlPreview(String htmlContent) {
    // Use WebView to render HTML content properly
    // This ensures HTML tables and other elements are rendered, not shown as source code
    try {
      final WebViewController controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setBackgroundColor(Colors.transparent)
        ..setNavigationDelegate(
          NavigationDelegate(
            onPageFinished: (url) {
              _unifiedPreviewLog('WebView page finished loading: $url');
            },
          ),
        )
        ..loadRequest(
          Uri.dataFromString(
            htmlContent,
            mimeType: 'text/html',
            encoding: Encoding.getByName('utf-8'),
          ),
        );

      return WebViewWidget(controller: controller);
    } catch (e) {
      _unifiedPreviewLog('Error creating WebView: $e', level: LogLevel.error);
      // Fallback to showing HTML source if WebView fails
      return SingleChildScrollView(
        child: Container(
          padding: const EdgeInsets.all(16),
          child: SelectableText.rich(
            TextSpan(
              text: htmlContent,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
              ),
            ),
          ),
        ),
      );
    }
  }

  /// Build fallback preview widget
  Widget _buildFallbackPreview() {
    if (widget.contentType == 'md') {
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);
      return SingleChildScrollView(
        child: Container(
          padding: const EdgeInsets.all(16),
          child: MarkdownTextWithImages(
            text: widget.content,
            imageDataMap: widget.imageDataMap,
            enableSelection: widget.enableSelection,
            style: TextStyle(
              fontSize: widget.fontSize ?? globalSettings.previewFontSize,
            ),
          ),
        ),
      );
    } else {
      return SingleChildScrollView(
        child: Container(
          padding: const EdgeInsets.all(16),
          child: SelectableText.rich(
            TextSpan(
              text: widget.content,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          ),
        ),
      );
    }
  }

  /// Wrap markdown content in HTML with KaTeX support for formula rendering
  String _wrapMarkdownInHtml(String markdown) {
    // Extract LaTeX blocks to protect them from HTML escaping
    final List<String> latexBlocks = <String>[];
    final List<String> latexPlaceholders = <String>[];

    // Extract block math: $$...$$ and \[...\]
    var processedMarkdown = markdown;

    // First extract \[...\] format (LaTeX block math)
    final RegExp latexBracketBlockPattern = RegExp(r'\\\[[\s\S]*?\\\]');
    var bracketBlockIndex = 0;
    processedMarkdown = processedMarkdown
        .replaceAllMapped(latexBracketBlockPattern, (Match match) {
      final String placeholder =
          '___LATEX_BRACKET_BLOCK_${bracketBlockIndex}___';
      // Keep original \[...\] format (KaTeX supports this format)
      // Only clean up whitespace inside the LaTeX block
      final String content = match.group(0)!;
      // Extract content between \[ and \]
      final RegExpMatch? contentMatch =
          RegExp(r'\\\[([\s\S]*?)\\\]').firstMatch(content);
      if (contentMatch != null) {
        final String mathContent = contentMatch.group(1)!.trim();
        // Store as \[...\] format (KaTeX supports this, no need to convert to $$...$$)
        latexBlocks.add('\\[$mathContent\\]');
      } else {
        latexBlocks.add(content);
      }
      latexPlaceholders.add(placeholder);
      bracketBlockIndex++;
      return placeholder;
    });

    // Extract block math: $$...$$
    final RegExp blockMathPattern = RegExp(r'\$\$[\s\S]*?\$\$');
    var blockIndex = 0;
    processedMarkdown =
        processedMarkdown.replaceAllMapped(blockMathPattern, (Match match) {
      final String placeholder = '___LATEX_BLOCK_${blockIndex}___';
      // Clean up whitespace inside $$...$$ blocks (remove leading/trailing newlines)
      final String content = match.group(0)!;
      final RegExpMatch? contentMatch =
          RegExp(r'\$\$([\s\S]*?)\$\$').firstMatch(content);
      if (contentMatch != null) {
        final String mathContent = contentMatch.group(1)!.trim();
        // Store cleaned version (single line, no extra newlines)
        latexBlocks.add('\$\$$mathContent\$\$');
      } else {
        latexBlocks.add(content);
      }
      latexPlaceholders.add(placeholder);
      blockIndex++;
      return placeholder;
    });

    // Extract inline math: $...$ and \(...\)
    // First extract \(...\) format (LaTeX inline math)
    final RegExp latexBracketInlinePattern = RegExp(r'\\\([^\\]*?\\\)');
    var bracketInlineIndex = 0;
    processedMarkdown = processedMarkdown
        .replaceAllMapped(latexBracketInlinePattern, (Match match) {
      final String placeholder =
          '___LATEX_BRACKET_INLINE_${bracketInlineIndex}___';
      // Keep original \(...\) format (KaTeX supports this format)
      final String content = match.group(0)!;
      final RegExpMatch? contentMatch =
          RegExp(r'\\\(([^\\]*?)\\\)').firstMatch(content);
      if (contentMatch != null) {
        final String mathContent = contentMatch.group(1)!.trim();
        // Store as \(...\) format (KaTeX supports this, no need to convert to $...$)
        latexBlocks.add('\\($mathContent\\)');
      } else {
        latexBlocks.add(content);
      }
      latexPlaceholders.add(placeholder);
      bracketInlineIndex++;
      return placeholder;
    });

    // Extract inline math: $...$ (but not $$...$$)
    final RegExp inlineMathPattern =
        RegExp(r'(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)');
    var inlineIndex = 0;
    processedMarkdown =
        processedMarkdown.replaceAllMapped(inlineMathPattern, (Match match) {
      final String placeholder = '___LATEX_INLINE_${inlineIndex}___';
      latexBlocks.add(match.group(0)!);
      latexPlaceholders.add(placeholder);
      inlineIndex++;
      return placeholder;
    });

    // Replace image placeholders with actual images FIRST (before HTML escaping)
    // This ensures images are replaced before HTML conversion and link conversion happens
    // Extract image references to protect them from HTML escaping
    final List<String> imagePlaceholders = <String>[];
    final List<String> imageDataUris = <String>[];
    if (widget.imageDataMap != null) {
      processedMarkdown = _replaceImagePlaceholdersInMarkdown(
        processedMarkdown,
        widget.imageDataMap!,
      );

      // Extract data:image URIs to protect them from HTML escaping
      final RegExp imagePattern =
          RegExp(r'!\[([^\]]*)\]\((data:image/[^\)]+)\)');
      var imageIndex = 0;
      processedMarkdown =
          processedMarkdown.replaceAllMapped(imagePattern, (Match match) {
        final String placeholder = '___IMAGE_PLACEHOLDER_${imageIndex}___';
        imagePlaceholders.add(placeholder);
        imageDataUris
            .add(match.group(0)!); // Store the full markdown image syntax
        imageIndex++;
        return placeholder;
      });
    }

    // CRITICAL: Protect HTML tables from escaping BEFORE escaping HTML
    // HTML tables in markdown should be preserved as-is, not escaped
    final RegExp htmlTablePattern =
        RegExp(r'<table>[\s\S]*?</table>', dotAll: true);
    final List<String> htmlTableProtections = <String>[];
    var htmlTableIndex = 0;
    var processedWithProtectedTables = processedMarkdown;
    processedWithProtectedTables = processedWithProtectedTables
        .replaceAllMapped(htmlTablePattern, (Match match) {
      final String placeholder = '___HTML_TABLE_PROTECT_${htmlTableIndex}___';
      htmlTableProtections.add(match.group(0)!); // Store original HTML table
      htmlTableIndex++;
      return placeholder;
    });

    // Escape HTML special characters in the remaining markdown (without LaTeX blocks, images, and HTML tables)
    // But protect image placeholders from escaping
    var escapedMarkdown = processedWithProtectedTables;
    // Temporarily replace image placeholders with safe text before escaping
    final List<String> safeImagePlaceholders = <String>[];
    for (var i = 0; i < imagePlaceholders.length; i++) {
      final String safePlaceholder = '___SAFE_IMAGE_${i}___';
      safeImagePlaceholders.add(safePlaceholder);
      escapedMarkdown =
          escapedMarkdown.replaceAll(imagePlaceholders[i], safePlaceholder);
    }

    // Now escape HTML (HTML tables are already protected as placeholders)
    escapedMarkdown = escapedMarkdown
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');

    // Restore image references (they contain data:image URIs which should not be escaped)
    for (var i = 0; i < safeImagePlaceholders.length; i++) {
      escapedMarkdown = escapedMarkdown.replaceAll(
        safeImagePlaceholders[i],
        imageDataUris[i],
      );
    }

    // Restore HTML tables (they should remain as HTML, not escaped)
    for (var i = 0; i < htmlTableProtections.length; i++) {
      escapedMarkdown = escapedMarkdown.replaceAll(
        '___HTML_TABLE_PROTECT_${i}___',
        htmlTableProtections[i],
      );
    }

    // Convert markdown to HTML (simple conversion for basic markdown)
    // IMPORTANT: Process tables BEFORE line break conversion to preserve table structure
    var html = escapedMarkdown;

    // Convert markdown tables to HTML tables FIRST (before line break processing)
    // Pattern: | col1 | col2 | ... followed by | --- | --- | ... (header separator) then data rows
    final RegExp tablePattern = RegExp(
      r'(\|(?:\s*[^|\n]+\s*\|)+\s*\n)' // Header row: | col1 | col2 |
      r'(\|\s*[-:]+(?:\s*[-:]+)*\s*\|\s*\n)?' // Separator row: | --- | --- | (optional)
      r'((?:\|(?:\s*[^|\n]+\s*\|)+\s*\n?)+)', // Data rows: | val1 | val2 | ...
      multiLine: true,
    );

    html = html.replaceAllMapped(tablePattern, (Match match) {
      final String headerRow = match.group(1) ?? '';
      // separatorRow is used to detect if table has header separator (optional)
      final String dataRows = match.group(3) ?? '';

      // Parse header row
      final List<String> headerCells = headerRow
          .split('|')
          .map((String cell) => cell.trim())
          .where((String cell) => cell.isNotEmpty)
          .toList();

      if (headerCells.isEmpty) {
        return match.group(0)!; // Return original if parsing fails
      }

      // Parse data rows
      final List<List<String>> allRows = <List<String>>[];
      allRows.add(headerCells); // Add header as first row

      final List<String> rowLines = dataRows.split('\n');
      for (final String rowLine in rowLines) {
        if (rowLine.trim().isEmpty) continue;
        final List<String> cells = rowLine
            .split('|')
            .map((String cell) => cell.trim())
            .where((String cell) => cell.isNotEmpty)
            .toList();
        if (cells.isNotEmpty) {
          allRows.add(cells);
        }
      }

      // Build HTML table
      final StringBuffer tableHtml = StringBuffer();
      tableHtml.write('<table>');

      // Header row
      if (allRows.isNotEmpty) {
        tableHtml.write('<thead><tr>');
        for (final String cell in allRows[0]) {
          // Escape HTML in cell content
          final String escapedCell = cell
              .replaceAll('&', '&amp;')
              .replaceAll('<', '&lt;')
              .replaceAll('>', '&gt;');
          tableHtml.write('<th>$escapedCell</th>');
        }
        tableHtml.write('</tr></thead>');
      }

      // Data rows
      if (allRows.length > 1) {
        tableHtml.write('<tbody>');
        for (var i = 1; i < allRows.length; i++) {
          tableHtml.write('<tr>');
          for (final String cell in allRows[i]) {
            // Escape HTML in cell content
            final String escapedCell = cell
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;');
            tableHtml.write('<td>$escapedCell</td>');
          }
          tableHtml.write('</tr>');
        }
        tableHtml.write('</tbody>');
      }

      tableHtml.write('</table>');
      return tableHtml.toString();
    });

    // Now process other markdown elements
    html = html
        // Headers
        .replaceAllMapped(
          RegExp(r'^### (.*)$', multiLine: true),
          (Match match) => '<h3>${match.group(1)}</h3>',
        )
        .replaceAllMapped(
          RegExp(r'^## (.*)$', multiLine: true),
          (Match match) => '<h2>${match.group(1)}</h2>',
        )
        .replaceAllMapped(
          RegExp(r'^# (.*)$', multiLine: true),
          (Match match) => '<h1>${match.group(1)}</h1>',
        )
        // Bold
        .replaceAllMapped(
          RegExp(r'\*\*(.*?)\*\*'),
          (Match match) => '<strong>${match.group(1)}</strong>',
        )
        // Italic
        .replaceAllMapped(
          RegExp(r'\*(.*?)\*'),
          (Match match) => '<em>${match.group(1)}</em>',
        )
        // Code blocks
        .replaceAllMapped(
          RegExp(r'```([\s\S]*?)```'),
          (Match match) => '<pre><code>${match.group(1)}</code></pre>',
        )
        // Inline code
        .replaceAllMapped(
          RegExp('`([^`]+)`'),
          (Match match) => '<code>${match.group(1)}</code>',
        )
        // Links (exclude image references that start with ! and data:image URIs)
        .replaceAllMapped(RegExp(r'(?<!\!)\[([^\]]+)\]\(([^\)]+)\)'),
            (Match match) {
      final String url = match.group(2) ?? '';
      // Skip if it's a data:image URI (already converted to img tag)
      if (url.startsWith('data:image/')) {
        return match.group(0)!;
      }
      return '<a href="$url">${match.group(1)}</a>';
    })
        // Convert markdown image syntax with data:image URIs to img tags
        // Note: data:image URIs may contain commas and other characters, so we need to match carefully
        .replaceAllMapped(RegExp(r'!\[([^\]]*)\]\((data:image/[^\)]+)\)'),
            (Match match) {
      final String altText = match.group(1) ?? '';
      final String dataUri = match.group(2) ?? '';
      final String style = _getImageStyle(altText);
      return '<img src="$dataUri" alt="${altText.replaceAll('"', '&quot;')}" style="$style" />';
    });

    // IMPORTANT: Process line breaks BEFORE restoring LaTeX blocks
    // This prevents LaTeX formulas from being split by paragraph conversion
    // Strategy: Keep LaTeX blocks as placeholders during line break processing, then restore them

    // First, protect tables (they're already HTML, so protect them now)
    final RegExp tableProtectionPattern = RegExp(r'<table>[\s\S]*?</table>');
    final List<String> tableProtections = <String>[];
    var tableProtectionIndex = 0;
    html = html.replaceAllMapped(tableProtectionPattern, (Match match) {
      final String placeholder = '___TABLE_PROTECT_${tableProtectionIndex}___';
      tableProtections.add(match.group(0)!);
      tableProtectionIndex++;
      return placeholder;
    });

    // Now process line breaks (LaTeX blocks are still placeholders, so they won't be affected)
    html =
        html.replaceAll(RegExp(r'\n\n+'), '</p><p>').replaceAll('\n', '<br>');

    // Restore tables first
    for (var i = 0; i < tableProtections.length; i++) {
      html = html.replaceAll('___TABLE_PROTECT_${i}___', tableProtections[i]);
    }

    // IMPORTANT: Restore LaTeX blocks AFTER line break processing
    // This ensures LaTeX formulas are not split by paragraph conversion
    // Also normalize LaTeX blocks to ensure they don't contain problematic newlines
    for (var i = 0; i < latexBlocks.length; i++) {
      // Replace placeholder with normalized LaTeX block
      html = html.replaceAll(latexPlaceholders[i], latexBlocks[i]);
    }

    // Wrap in paragraph tags
    html = '<p>$html</p>';

    // Build complete HTML document with KaTeX
    return _buildCompleteHtmlDocument(html);
  }

  /// Replace image placeholders in Markdown with actual images (before HTML conversion)
  /// This handles markdown format: ![alt](filename.jpg) or ![alt](<ph-xxx>)
  String _replaceImagePlaceholdersInMarkdown(
    String markdown,
    Map<String, Map<String, String>> imageDataMap,
  ) {
    // Build reverse map: filename -> image data (for equation images using filenames)
    final Map<String, Map<String, String>> filenameToImageData =
        <String, Map<String, String>>{};

    _unifiedPreviewLog(
      'Replacing image placeholders in markdown: imageDataMap has ${imageDataMap.length} entries',
    );

    var processedMarkdown = markdown;

    imageDataMap.forEach((String placeholderId, Map<String, String> imageData) {
      final String? base64Data = imageData['data'];
      final String altText = imageData['alt'] ?? '';
      if (base64Data != null && base64Data.startsWith('data:image/')) {
        // Replace <ph-xxx> placeholders with markdown image syntax using base64 data URI
        processedMarkdown = processedMarkdown.replaceAll(
          '<ph-$placeholderId>',
          '![$altText]($base64Data)',
        );
        // Handle markdown image syntax with placeholders: ![alt](<ph-xxx>)
        processedMarkdown = processedMarkdown.replaceAllMapped(
          RegExp(r'!\[([^\]]*)\]\(<ph-$placeholderId>\)'),
          (Match match) => '![${match.group(1) ?? altText}]($base64Data)',
        );
        // Handle markdown image syntax with direct placeholder ID: ![alt](placeholder_id)
        final String escapedPlaceholderId = RegExp.escape(placeholderId);
        processedMarkdown = processedMarkdown.replaceAllMapped(
          RegExp('!\\[([^\\]]*)\\]\\($escapedPlaceholderId\\)'),
          (Match match) => '![${match.group(1) ?? altText}]($base64Data)',
        );

        // Build filename reverse map for equation images
        if (altText.isNotEmpty) {
          final String extractedFilename =
              altText.split('/').last.split(r'\').last;
          if (extractedFilename.isNotEmpty && extractedFilename.contains('.')) {
            filenameToImageData[extractedFilename] = imageData;
            _unifiedPreviewLog(
              'Added filename mapping: $extractedFilename -> placeholder $placeholderId',
            );
          }
          // Also add full altText as key (might be full path)
          filenameToImageData[altText] = imageData;
          // Add placeholder ID as key for backward compatibility
          filenameToImageData[placeholderId] = imageData;
        }
      }
    });

    _unifiedPreviewLog(
      'Filename map built with ${filenameToImageData.length} entries',
    );

    // Handle filename-based image references (e.g., ![Equation](filename.jpg))
    final RegExp filenameImagePattern =
        RegExp(r'!\[([^\]]*)\]\(([^\)]+\.(jpg|jpeg|png|gif|webp))\)');
    final Iterable<RegExpMatch> filenameMatches =
        filenameImagePattern.allMatches(processedMarkdown);
    _unifiedPreviewLog(
      'Found ${filenameMatches.length} filename image references in markdown',
    );

    if (filenameMatches.isNotEmpty) {
      // Process in reverse order to maintain string indices
      final List<RegExpMatch> sortedMatches = filenameMatches.toList()
        ..sort((RegExpMatch a, RegExpMatch b) => b.start.compareTo(a.start));

      for (final RegExpMatch match in sortedMatches) {
        final String altText = match.group(1) ?? '';
        final String filename = match.group(2) ?? '';

        // Normalize filename (remove ./ prefix and path)
        final String normalizedFilename = filename
            .replaceFirst(RegExp(r'^\./'), '') // Remove leading ./
            .split('/')
            .last
            .split(r'\')
            .last;

        _unifiedPreviewLog(
          'Processing markdown image reference: alt="$altText", filename="$filename", normalized="$normalizedFilename"',
        );

        // Try to find in filenameToImageData
        Map<String, String>? imageData;
        if (filenameToImageData.containsKey(normalizedFilename)) {
          imageData = filenameToImageData[normalizedFilename];
          _unifiedPreviewLog(
            'Found image data by normalized filename: $normalizedFilename',
          );
        } else if (filenameToImageData.containsKey(filename)) {
          imageData = filenameToImageData[filename];
          _unifiedPreviewLog(
            'Found image data by original filename: $filename',
          );
        } else {
          // Try to find in imageDataMap by searching all entries
          for (final MapEntry<String, Map<String, String>> entry
              in imageDataMap.entries) {
            final String entryAltText = entry.value['alt'] ?? '';
            final String extractedFilename =
                entryAltText.split('/').last.split(r'\').last;
            if (extractedFilename == normalizedFilename ||
                extractedFilename == filename ||
                entryAltText == filename ||
                entryAltText.endsWith(normalizedFilename) ||
                entryAltText.endsWith(filename)) {
              imageData = entry.value;
              _unifiedPreviewLog(
                'Found image data by searching: placeholder=${entry.key}, alt=$entryAltText',
              );
              break;
            }
          }
        }

        if (imageData != null) {
          final String? base64Data = imageData['data'];
          if (base64Data != null && base64Data.startsWith('data:image/')) {
            // Replace markdown image syntax with base64 data URI
            processedMarkdown = processedMarkdown.replaceRange(
              match.start,
              match.end,
              '![$altText]($base64Data)',
            );
            _unifiedPreviewLog(
              'Replaced markdown image reference with base64 data: $filename',
            );
          } else {
            _unifiedPreviewLog(
              'Image data found but base64Data is invalid: length=${base64Data?.length ?? 0}',
              level: LogLevel.warn,
            );
          }
        } else {
          _unifiedPreviewLog(
            'WARNING: No image data found for filename: $filename (normalized: $normalizedFilename)',
            level: LogLevel.warn,
          );
          _unifiedPreviewLog(
            'Available keys in filenameToImageData: ${filenameToImageData.keys.toList()}',
            level: LogLevel.warn,
          );
          _unifiedPreviewLog(
            'Available keys in imageDataMap: ${imageDataMap.keys.toList()}',
            level: LogLevel.warn,
          );
        }
      }
    }

    return processedMarkdown;
  }

  /// Generate image style string based on alt text
  /// Formula and table images use smaller max-width to match text size
  String _getImageStyle(String altText) {
    final bool isFormulaOrTable = altText.toLowerCase().contains('equation') ||
        altText.toLowerCase().contains('table');
    final String maxWidth = isFormulaOrTable ? '70%' : '90%';
    return 'max-width: $maxWidth; height: auto; object-fit: contain; display: block; margin: 1em auto;';
  }

  /// Replace image placeholders in HTML with actual images
  String _replaceImagePlaceholders(
    String html,
    Map<String, Map<String, String>> imageDataMap,
  ) {
    // Build reverse map: filename -> image data (for equation images using filenames)
    final Map<String, Map<String, String>> filenameToImageData =
        <String, Map<String, String>>{};

    _unifiedPreviewLog(
      'Replacing image placeholders: imageDataMap has ${imageDataMap.length} entries',
    );

    // Debug: Check what image reference formats exist in HTML
    final RegExp phPattern = RegExp('<ph-([a-zA-Z0-9]+)>');
    final Iterable<RegExpMatch> phMatches = phPattern.allMatches(html);
    _unifiedPreviewLog(
      'Found ${phMatches.length} <ph-xxx> placeholders in HTML',
    );
    if (phMatches.isNotEmpty) {
      for (final RegExpMatch match in phMatches.take(5)) {
        _unifiedPreviewLog(
          'Placeholder found: ${match.group(0)}, id=${match.group(1)}',
        );
      }
    }

    final RegExp markdownPhPattern =
        RegExp(r'!\[([^\]]*)\]\(<ph-([a-zA-Z0-9]+)>\)');
    final Iterable<RegExpMatch> markdownPhMatches =
        markdownPhPattern.allMatches(html);
    _unifiedPreviewLog(
      'Found ${markdownPhMatches.length} ![alt](<ph-xxx>) references in HTML',
    );

    final RegExp markdownIdPattern = RegExp(r'!\[([^\]]*)\]\(([a-zA-Z0-9]+)\)');
    final Iterable<RegExpMatch> markdownIdMatches =
        markdownIdPattern.allMatches(html);
    _unifiedPreviewLog(
      'Found ${markdownIdMatches.length} ![alt](id) references in HTML',
    );
    if (markdownIdMatches.isNotEmpty) {
      for (final RegExpMatch match in markdownIdMatches.take(5)) {
        _unifiedPreviewLog(
          'Markdown ID reference: alt=${match.group(1)}, id=${match.group(2)}',
        );
      }
    }

    imageDataMap.forEach((String placeholderId, Map<String, String> imageData) {
      final String? base64Data = imageData['data'];
      final String altText = imageData['alt'] ?? '';
      if (base64Data != null && base64Data.startsWith('data:image/')) {
        // Check if placeholder exists before replacement
        final RegExp placeholderPattern =
            RegExp(RegExp.escape('<ph-$placeholderId>'));
        final int placeholderCount = placeholderPattern.allMatches(html).length;
        if (placeholderCount > 0) {
          _unifiedPreviewLog(
            'Replacing $placeholderCount occurrences of <ph-$placeholderId> with image (alt: $altText, data length: ${base64Data.length})',
          );
        }

        // Replace <ph-xxx> placeholders
        final String style = _getImageStyle(altText);
        html = html.replaceAll(
          '<ph-$placeholderId>',
          '<img src="$base64Data" alt="${altText.replaceAll('"', '&quot;')}" style="$style" />',
        );

        // Verify replacement
        final int remainingCount = placeholderPattern.allMatches(html).length;
        if (placeholderCount > 0 && remainingCount == 0) {
          _unifiedPreviewLog(
            'Successfully replaced all <ph-$placeholderId> placeholders',
          );
        } else if (placeholderCount > 0 && remainingCount > 0) {
          _unifiedPreviewLog(
            'WARNING: Still found $remainingCount occurrences of <ph-$placeholderId> after replacement',
            level: LogLevel.warn,
          );
        }

        // Handle markdown image syntax with placeholders: ![alt](<ph-xxx>)
        html = html.replaceAllMapped(
            RegExp(r'!\[([^\]]*)\]\(<ph-$placeholderId>\)'), (Match match) {
          final String matchAltText =
              match.group(1)?.replaceAll('"', '&quot;') ??
                  altText.replaceAll('"', '&quot;');
          final String matchStyle = _getImageStyle(matchAltText);
          return '<img src="$base64Data" alt="$matchAltText" style="$matchStyle" />';
        });
        // Handle markdown image syntax with direct placeholder ID: ![alt](placeholder_id)
        final String escapedPlaceholderId = RegExp.escape(placeholderId);
        html = html.replaceAllMapped(
            RegExp('!\\[([^\\]]*)\\]\\($escapedPlaceholderId\\)'),
            (Match match) {
          final String matchAltText =
              match.group(1)?.replaceAll('"', '&quot;') ??
                  altText.replaceAll('"', '&quot;');
          final String matchStyle = _getImageStyle(matchAltText);
          return '<img src="$base64Data" alt="$matchAltText" style="$matchStyle" />';
        });

        // Build filename reverse map for equation images
        if (altText.isNotEmpty) {
          final String extractedFilename =
              altText.split('/').last.split(r'\').last;
          if (extractedFilename.isNotEmpty && extractedFilename.contains('.')) {
            filenameToImageData[extractedFilename] = imageData;
            _unifiedPreviewLog(
              'Added filename mapping: $extractedFilename -> placeholder $placeholderId',
            );
          }
          // Also add full altText as key (might be full path)
          filenameToImageData[altText] = imageData;
          // Add placeholder ID as key for backward compatibility
          filenameToImageData[placeholderId] = imageData;
        }
      }
    });

    _unifiedPreviewLog(
      'Filename map built with ${filenameToImageData.length} entries',
    );

    // Handle placeholder ID references first (e.g., ![Table](layoutimg0))
    // These are not filenames but placeholder IDs that should be replaced
    final RegExp placeholderIdPattern =
        RegExp(r'!\[([^\]]*)\]\(([a-zA-Z0-9]+)\)');
    final Iterable<RegExpMatch> placeholderIdMatches =
        placeholderIdPattern.allMatches(html);
    _unifiedPreviewLog(
      'Found ${placeholderIdMatches.length} potential placeholder ID references in HTML',
    );

    // Process placeholder ID references in reverse order to maintain string indices
    if (placeholderIdMatches.isNotEmpty) {
      final List<RegExpMatch> sortedMatches = placeholderIdMatches.toList()
        ..sort((RegExpMatch a, RegExpMatch b) => b.start.compareTo(a.start));

      for (final RegExpMatch match in sortedMatches) {
        final String altText = match.group(1) ?? '';
        final String placeholderId = match.group(2) ?? '';

        // Skip if it looks like a filename (contains dot and extension)
        if (placeholderId.contains('.') &&
            RegExp(r'\.(jpg|jpeg|png|gif|webp)$', caseSensitive: false)
                .hasMatch(placeholderId)) {
          continue; // Will be handled by filename pattern below
        }

        // Check if this placeholder ID exists in imageDataMap
        if (imageDataMap.containsKey(placeholderId)) {
          final Map<String, String> imageData = imageDataMap[placeholderId]!;
          final String? base64Data = imageData['data'];
          if (base64Data != null && base64Data.startsWith('data:image/')) {
            final String style = _getImageStyle(altText);
            html = html.replaceRange(
              match.start,
              match.end,
              '<img src="$base64Data" alt="${altText.replaceAll('"', '&quot;')}" style="$style" />',
            );
            _unifiedPreviewLog(
              'Replaced placeholder ID reference: ![$altText]($placeholderId)',
            );
          } else {
            _unifiedPreviewLog(
              'Placeholder ID found but base64Data is invalid: $placeholderId, length=${base64Data?.length ?? 0}',
              level: LogLevel.warn,
            );
          }
        }
      }
    }

    // Handle HTML img tags with placeholder ID src (e.g., <img src="layoutimg3" alt="Table">)
    // This handles cases where markdown.markdown() converted ![Table](placeholder_id) to <img src="placeholder_id">
    // Match img tags with src that doesn't contain a file extension (likely a placeholder ID)
    final RegExp imgTagPlaceholderPattern = RegExp(
      r'<img\s+([^>]*?)src=["' ']([^"' ']+?)["' ']([^>]*?)>',
      caseSensitive: false,
    );
    final Iterable<RegExpMatch> imgTagPlaceholderMatches =
        imgTagPlaceholderPattern.allMatches(html);
    var placeholderImgCount = 0;
    if (imgTagPlaceholderMatches.isNotEmpty) {
      // Process in reverse order to maintain string indices
      final List<RegExpMatch> sortedMatches = imgTagPlaceholderMatches.toList()
        ..sort((RegExpMatch a, RegExpMatch b) => b.start.compareTo(a.start));

      for (final RegExpMatch match in sortedMatches) {
        final String srcValue = match.group(2) ?? '';

        // Skip if it looks like a filename (contains dot and extension)
        if (srcValue.contains('.') &&
            RegExp(r'\.(jpg|jpeg|png|gif|webp|webm|svg)$', caseSensitive: false)
                .hasMatch(srcValue)) {
          continue; // Will be handled by filename pattern below
        }

        // Skip if it's already a data URI
        if (srcValue.startsWith('data:image/')) {
          continue;
        }

        // Check if this is a placeholder ID in imageDataMap
        if (imageDataMap.containsKey(srcValue)) {
          final Map<String, String> imageData = imageDataMap[srcValue]!;
          final String? base64Data = imageData['data'];
          if (base64Data != null && base64Data.startsWith('data:image/')) {
            final String altText = imageData['alt'] ?? '';
            final String style = _getImageStyle(altText);
            html = html.replaceRange(
              match.start,
              match.end,
              '<img src="$base64Data" alt="${altText.replaceAll('"', '&quot;')}" style="$style" />',
            );
            placeholderImgCount++;
          }
        }
      }
    }
    if (placeholderImgCount > 0) {
      _unifiedPreviewLog(
        'Replaced $placeholderImgCount <img> tags with placeholder ID src in HTML',
      );
    }

    // Handle HTML img tags with filename src (e.g., <img src="filename.jpg" alt="Equation">)
    // This handles cases where markdown was converted to HTML by backend
    // Match both lowercase and uppercase img tags
    final RegExp imgTagPattern = RegExp(
      r'<img\s+([^>]*?)src=["'
      ']([^"'
      ']+.(jpg|jpeg|png|gif|webp))["'
      ']([^>]*?)>',
      caseSensitive: false,
    );
    final Iterable<RegExpMatch> imgTagMatches = imgTagPattern.allMatches(html);

    if (imgTagMatches.isNotEmpty) {
      // Process in reverse order to maintain string indices
      final List<RegExpMatch> sortedMatches = imgTagMatches.toList()
        ..sort((RegExpMatch a, RegExpMatch b) => b.start.compareTo(a.start));

      for (final RegExpMatch match in sortedMatches) {
        final String filename = match.group(2) ?? '';

        // Normalize filename (remove ./ prefix and path)
        final String normalizedFilename = filename
            .replaceFirst(RegExp(r'^\./'), '') // Remove leading ./
            .split('/')
            .last
            .split(r'\')
            .last;

        // Try to find in filenameToImageData
        Map<String, String>? imageData;
        if (filenameToImageData.containsKey(normalizedFilename)) {
          imageData = filenameToImageData[normalizedFilename];
        } else if (filenameToImageData.containsKey(filename)) {
          imageData = filenameToImageData[filename];
        } else {
          // Try to find in imageDataMap by searching all entries
          // This handles cases where filename is a hash (e.g., from MinerU)
          for (final MapEntry<String, Map<String, String>> entry
              in imageDataMap.entries) {
            final String entryKey = entry.key;
            final String entryAltText = entry.value['alt'] ?? '';
            final String extractedFilename =
                entryAltText.split('/').last.split(r'\').last;
            // Try multiple matching strategies:
            // 1. Direct key match (filename as key)
            if (entryKey == normalizedFilename || entryKey == filename) {
              imageData = entry.value;
              _unifiedPreviewLog(
                'Found image data by direct key match: $entryKey',
              );
              break;
            }
            // 2. Alt text filename match
            if (extractedFilename == normalizedFilename ||
                extractedFilename == filename ||
                entryAltText == filename ||
                entryAltText.endsWith(normalizedFilename) ||
                entryAltText.endsWith(filename)) {
              imageData = entry.value;
              _unifiedPreviewLog(
                'Found image data by alt text match: $entryAltText (extracted: $extractedFilename)',
              );
              break;
            }
            // 3. Partial match (filename contains hash or vice versa)
            if (normalizedFilename.length > 20 && entryKey.length > 20) {
              // Both look like hashes, try substring match
              if (normalizedFilename.contains(entryKey.substring(0, 8)) ||
                  entryKey.contains(normalizedFilename.substring(0, 8))) {
                imageData = entry.value;
                _unifiedPreviewLog(
                  'Found image data by hash substring match: $entryKey <-> $normalizedFilename',
                );
                break;
              }
            }
          }
        }

        if (imageData != null) {
          final String? base64Data = imageData['data'];
          if (base64Data != null && base64Data.startsWith('data:image/')) {
            // Replace the entire img tag, preserving other attributes
            final String altText = imageData['alt'] ?? '';
            final String style = _getImageStyle(altText);
            html = html.replaceRange(
              match.start,
              match.end,
              '<img src="$base64Data" alt="${altText.replaceAll('"', '&quot;')}" style="$style" />',
            );
          } else {
            _unifiedPreviewLog(
              'Image data found but base64Data is invalid: length=${base64Data?.length ?? 0}',
              level: LogLevel.warn,
            );
          }
        } else {
          _unifiedPreviewLog(
            'WARNING: No image data found for <img> tag filename: $filename (normalized: $normalizedFilename)',
            level: LogLevel.warn,
          );
          _unifiedPreviewLog(
            'Available keys in filenameToImageData: ${filenameToImageData.keys.toList()}',
            level: LogLevel.warn,
          );
          _unifiedPreviewLog(
            'Available keys in imageDataMap: ${imageDataMap.keys.toList()}',
            level: LogLevel.warn,
          );
          // Also log all alt texts to help debug equation image matching
          final List<String> allAltTexts = imageDataMap.values
              .map((Map<String, String> e) => e['alt'] ?? '')
              .toList();
          _unifiedPreviewLog(
            'All alt texts in imageDataMap: ${allAltTexts.take(10).toList()}',
            level: LogLevel.warn,
          );
        }
      }
    }

    // Handle unmatched image references (e.g., ![Equation](filename.jpg))
    final RegExp remainingImagePattern =
        RegExp(r'!\[([^\]]*)\]\(([^\)]+\.(jpg|jpeg|png|gif|webp))\)');
    final Iterable<RegExpMatch> remainingMatches =
        remainingImagePattern.allMatches(html);

    if (remainingMatches.isNotEmpty) {
      for (final RegExpMatch match in remainingMatches) {
        final String altText = match.group(1) ?? '';
        final String filename = match.group(2) ?? '';

        // Normalize filename (remove ./ prefix and path)
        final String normalizedFilename = filename
            .replaceFirst(RegExp(r'^\./'), '') // Remove leading ./
            .split('/')
            .last
            .split(r'\')
            .last;

        // Try to find in filenameToImageData
        Map<String, String>? imageData;
        if (filenameToImageData.containsKey(normalizedFilename)) {
          imageData = filenameToImageData[normalizedFilename];
        } else if (filenameToImageData.containsKey(filename)) {
          imageData = filenameToImageData[filename];
        } else {
          // Try to find in imageDataMap by searching all entries
          for (final MapEntry<String, Map<String, String>> entry
              in imageDataMap.entries) {
            final String entryAltText = entry.value['alt'] ?? '';
            final String extractedFilename =
                entryAltText.split('/').last.split(r'\').last;
            if (extractedFilename == normalizedFilename ||
                extractedFilename == filename ||
                entryAltText == filename ||
                entryAltText.endsWith(normalizedFilename) ||
                entryAltText.endsWith(filename)) {
              imageData = entry.value;
              _unifiedPreviewLog(
                'Found image data by searching: placeholder=${entry.key}, alt=$entryAltText',
              );
              break;
            }
          }
        }

        if (imageData != null) {
          final String? base64Data = imageData['data'];
          if (base64Data != null && base64Data.startsWith('data:image/')) {
            final String style = _getImageStyle(altText);
            html = html.replaceAll(
              match.group(0)!,
              '<img src="$base64Data" alt="${altText.replaceAll('"', '&quot;')}" style="$style" />',
            );
          } else {
            _unifiedPreviewLog(
              'Image data found but base64Data is invalid: length=${base64Data?.length ?? 0}',
              level: LogLevel.warn,
            );
          }
        } else {
          _unifiedPreviewLog(
            'WARNING: No image data found for filename: $filename (normalized: $normalizedFilename)',
            level: LogLevel.warn,
          );
          _unifiedPreviewLog(
            'Available keys in filenameToImageData: ${filenameToImageData.keys.toList()}',
            level: LogLevel.warn,
          );
          _unifiedPreviewLog(
            'Available keys in imageDataMap: ${imageDataMap.keys.toList()}',
            level: LogLevel.warn,
          );
          // Also log all alt texts to help debug equation image matching
          final List<String> allAltTexts = imageDataMap.values
              .map((Map<String, String> e) => e['alt'] ?? '')
              .toList();
          _unifiedPreviewLog(
            'All alt texts in imageDataMap: ${allAltTexts.take(10).toList()}',
            level: LogLevel.warn,
          );
        }
      }
    }

    return html;
  }

  /// Wrap HTML content with KaTeX support
  String _wrapHtmlWithKaTeX(String html) {
    // Replace image placeholders with actual images before wrapping
    if (widget.imageDataMap != null) {
      // Check for placeholders before replacement
      final RegExp phPattern = RegExp('<ph-([a-zA-Z0-9]+)>');
      final Iterable<RegExpMatch> phMatchesBefore = phPattern.allMatches(html);
      _unifiedPreviewLog(
        'Before replacement: Found ${phMatchesBefore.length} <ph-xxx> placeholders in HTML',
      );

      html = _replaceImagePlaceholders(html, widget.imageDataMap!);

      // Check for remaining placeholders after replacement
      final Iterable<RegExpMatch> phMatchesAfter = phPattern.allMatches(html);
      if (phMatchesAfter.isNotEmpty) {
        _unifiedPreviewLog(
          'WARNING: After replacement, still found ${phMatchesAfter.length} <ph-xxx> placeholders',
          level: LogLevel.warn,
        );
        for (final RegExpMatch match in phMatchesAfter.take(5)) {
          _unifiedPreviewLog(
            'Remaining placeholder: ${match.group(0)}, id=${match.group(1)}',
            level: LogLevel.warn,
          );
        }
      } else if (phMatchesBefore.isNotEmpty) {
        _unifiedPreviewLog(
          'Successfully replaced all ${phMatchesBefore.length} <ph-xxx> placeholders',
        );
      }
    }

    // Build complete HTML document with KaTeX
    return _buildCompleteHtmlDocument(html);
  }

  /// Build complete HTML document with KaTeX support
  String _buildCompleteHtmlDocument(String bodyHtml) {
    final String baseUrl = AppConstants.baseUrl;
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="script-src 'self' $baseUrl 'unsafe-inline' 'unsafe-eval'; style-src 'self' $baseUrl 'unsafe-inline'; font-src 'self' $baseUrl data:; img-src 'self' $baseUrl data: blob:;">
    <title>Preview</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        img {
            max-width: 90%;
            height: auto;
            object-fit: contain;
            display: block;
            margin: 1em auto;
        }
        /* For formula and table images, use smaller max-width to match text size */
        img[alt*="Equation"],
        img[alt*="Table"] {
            max-width: 70%;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }
        table th, table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        table th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        pre {
            background-color: #f4f4f4;
            padding: 12px;
            border-radius: 4px;
            overflow-x: auto;
        }
        code {
            background-color: #f4f4f4;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        /* Hide original LaTeX text after KaTeX renders it */
        /* KaTeX auto-render should replace the original text, but hide any remaining LaTeX delimiters */
        .katex-display {
            margin: 1em 0;
        }
        /* Hide any raw LaTeX text that might appear alongside rendered formulas */
        /* This ensures only the rendered formula is visible, not the original LaTeX source */
        script[type="math/tex"],
        script[type="math/tex; mode=display"],
        script[type="math/tex; mode=inline"] {
            display: none !important;
        }
        /* Hide raw LaTeX text that might not be replaced by KaTeX auto-render */
        /* This targets LaTeX delimiters that might appear as plain text */
        /* Note: KaTeX auto-render should replace these, but this is a fallback */
        body:not(.katex-rendered) {
            /* Only apply if KaTeX hasn't rendered yet - but we'll use a more specific approach */
        }
        /* After KaTeX renders, hide any remaining LaTeX delimiters that appear as plain text */
        /* This is a fallback in case auto-render misses some LaTeX text */
        /* We'll use JavaScript to hide these after rendering */
    </style>
</head>
<body>
    $bodyHtml
    <script>
        (function() {
            function loadScript(src) {
                return new Promise(function(resolve, reject) {
                    var script = document.createElement('script');
                    script.src = src;
                    script.onload = resolve;
                    script.onerror = reject;
                    document.head.appendChild(script);
                });
            }
            
            function renderMath() {
                if (typeof renderMathInElement !== 'undefined') {
                    try {
                        renderMathInElement(document.body, {
                            delimiters: [
                                {left: String.fromCharCode(36, 36), right: String.fromCharCode(36, 36), display: true},
                                {left: String.fromCharCode(36), right: String.fromCharCode(36), display: false},
                                {left: '\\\\[', right: '\\\\]', display: true},
                                {left: '\\\\(', right: '\\\\)', display: false}
                            ],
                            strict: false
                        });
                        console.log('KaTeX auto-render: renderMathInElement called successfully');
                        
                        // Check after rendering to see if formulas were rendered
                        setTimeout(function() {
                            var katexElements = document.querySelectorAll('.katex, .katex-display');
                            console.log('KaTeX: Found ' + katexElements.length + ' rendered formula elements');
                            
                            // Only clean up duplicate raw LaTeX text if KaTeX has successfully rendered formulas
                            // This ensures we don't interfere with KaTeX's rendering process
                            if (katexElements.length > 0) {
                                // KaTeX has rendered formulas, now check for any remaining raw LaTeX text
                                // that appears alongside rendered formulas (duplicates)
                                setTimeout(function() {
                                    var walker = document.createTreeWalker(
                                        document.body,
                                        NodeFilter.SHOW_TEXT,
                                        null,
                                        false
                                    );
                                    var textNode;
                                    var nodesToClean = [];
                                    while (textNode = walker.nextNode()) {
                                        var text = textNode.textContent;
                                        // Check if this text node contains LaTeX delimiters
                                        if (text && text.trim() && (
                                            (text.indexOf(String.fromCharCode(92, 91)) >= 0 && text.indexOf(String.fromCharCode(92, 93)) >= 0) ||
                                            (text.indexOf(String.fromCharCode(92, 40)) >= 0 && text.indexOf(String.fromCharCode(92, 41)) >= 0) ||
                                            (text.indexOf(String.fromCharCode(36, 36)) >= 0 && text.lastIndexOf(String.fromCharCode(36, 36)) > text.indexOf(String.fromCharCode(36, 36)))
                                        )) {
                                            // Check if there's a KaTeX element in the same parent or nearby
                                            var parent = textNode.parentElement;
                                            var hasKatexNearby = false;
                                            while (parent && parent !== document.body) {
                                                if (parent.querySelector('.katex, .katex-display')) {
                                                    hasKatexNearby = true;
                                                    break;
                                                }
                                                parent = parent.parentElement;
                                            }
                                            // Only hide if there's a KaTeX element nearby (meaning it's a duplicate)
                                            if (hasKatexNearby && !textNode.parentElement.querySelector('.katex, .katex-display')) {
                                                nodesToClean.push(textNode);
                                            }
                                        }
                                    }
                                    // Clean up duplicate nodes
                                    if (nodesToClean.length > 0) {
                                        nodesToClean.forEach(function(node) {
                                            node.textContent = '';
                                        });
                                        console.log('KaTeX: Cleaned up ' + nodesToClean.length + ' duplicate LaTeX text nodes');
                                    }
                                }, 500);
                            } else {
                                console.log('KaTeX: No rendered elements found - check if LaTeX text format is correct');
                            }
                        }, 500);
                    } catch (e) {
                        console.error("KaTeX auto-render error:", e);
                    }
                } else {
                    console.error("renderMathInElement not available after script loading");
                }
            }
            
            var baseUrl = '$baseUrl';
            var katexJsUrl = baseUrl + '/static/katex/katex.js';
            var autoRenderUrl = baseUrl + '/static/katex/contrib/auto-render.min.js';
            
            loadScript(katexJsUrl).then(function() {
                console.log("KaTeX loader: Successfully loaded katex.js");
                return loadScript(autoRenderUrl);
            }).then(function() {
                console.log("KaTeX loader: Successfully loaded auto-render.min.js");
                setTimeout(renderMath, 100);
            }).catch(function(error) {
                console.error("KaTeX loader error:", error);
            });
        })();
    </script>
</body>
</html>
    ''';
  }
}
