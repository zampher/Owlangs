// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'dart:convert';
import '../../shared/utils/app_logger.dart';
import '../../shared/utils/ebook_image_helper.dart';
import '../../shared/utils/latex_text_segments.dart';

/// Widget that displays markdown text with image placeholders replaced by actual images
/// Supports both selectable and non-selectable text
class MarkdownTextWithImages extends StatelessWidget {
  const MarkdownTextWithImages({
    required this.text,
    super.key,
    this.imageDataMap,
    this.enableSelection = true,
    this.style,
    this.imageMaxWidth,
    this.imageMaxHeight,
  });
  final String text;
  final Map<String, Map<String, String>>?
      imageDataMap; // {placeholder_id: {"data": "data:image/...", "alt": "title"}}
  final bool enableSelection;
  final TextStyle? style;
  final double? imageMaxWidth;
  final double? imageMaxHeight;

  // Static flag to ensure null imageDataMap log is only output once
  static bool _hasLoggedNullImageDataMap = false;

  @override
  Widget build(BuildContext context) {
    // Log imageDataMap info for debugging
    if (imageDataMap != null) {
      // AppLogger.log('MarkdownTextWithImages',
      //     'Building widget: imageDataMap has ${imageDataMap!.length} entries, text length=${text.length}');
      if (imageDataMap!.isNotEmpty) {
        // final sampleKey = imageDataMap!.keys.first;
        // final sampleValue = imageDataMap![sampleKey];
        // AppLogger.log('MarkdownTextWithImages',
        //     'Sample entry: key=$sampleKey, data length=${sampleValue?['data']?.length ?? 0}, alt=${sampleValue?['alt']}');
      }
    } else {
      // Only log once to avoid repetitive output
      if (!_hasLoggedNullImageDataMap) {
        AppLogger.log(
          'MarkdownTextWithImages',
          'Building widget: imageDataMap is null',
        );
        _hasLoggedNullImageDataMap = true;
      }
    }

    // Check if text contains LaTeX formulas ($$...$$, $...$, \[...\], \(...\))
    final bool hasLaTeX = textContainsLatexMath(text);

    // Check if text contains image placeholders
    // Support path characters (/, ., -, _) in placeholder IDs for MOBI/EPUB images
    // Example: <ph-mobi7/Images/image00044.jpeg>
    final hasPlaceholders = ebookPlaceholderRe.hasMatch(text);
    final htmlExtractorPath = parseHtmlExtractorImageSegment(text.trim());
    final hasHtmlExtractorImage = htmlExtractorPath != null;
    // Placeholder detection (logging removed to reduce noise)

    // Check if text contains base64 image data (data:image/...;base64,...)
    final base64ImagePattern = RegExp(r'data:image/[^;]+;base64,[^\s)]+');
    final hasBase64Images = base64ImagePattern.hasMatch(text);

    // Check if text contains markdown image syntax with filenames: ![alt](filename.jpg)
    final filenameImagePattern =
        RegExp(r'!\[([^\]]*)\]\(([^)]+\.(jpg|jpeg|png|gif|webp))\)');
    final hasFilenameImages = filenameImagePattern.hasMatch(text);
    // Filename image detection (logging removed to reduce noise)

    // If text contains LaTeX formulas, render with LaTeX support
    if (hasLaTeX) {
      return _buildWithLaTeX(text);
    }

    // Standalone HtmlExtractor image line: [Image: path]
    if (hasHtmlExtractorImage &&
        imageDataMap != null &&
        imageDataMap!.isNotEmpty) {
      final imageData = lookupImageData(imageDataMap, htmlExtractorPath);
      if (imageData != null) {
        return _buildImageWidget(imageData);
      }
    }

    // Standalone <ph-...> placeholder (single image segment)
    if (hasPlaceholders &&
        imageDataMap != null &&
        imageDataMap!.isNotEmpty) {
      final phMatch = ebookPlaceholderRe.firstMatch(text.trim());
      if (phMatch != null &&
          phMatch.group(0) == text.trim() &&
          phMatch.group(1) != null) {
        final imageData = lookupImageData(imageDataMap, phMatch.group(1)!);
        if (imageData != null) {
          return _buildImageWidget(imageData);
        }
      }
    }

    if ((!hasPlaceholders || imageDataMap == null || imageDataMap!.isEmpty) &&
        !hasHtmlExtractorImage &&
        !hasBase64Images &&
        (!hasFilenameImages || imageDataMap == null || imageDataMap!.isEmpty)) {
      // No placeholders, no image data map, and no base64 images, render as plain text
      return enableSelection
          ? SelectableText(
              text,
              style: style,
            )
          : Text(
              text,
              style: style,
            );
    }

    // If text contains base64 images but no placeholders and no filename images, handle base64 images directly
    if (hasBase64Images &&
        (!hasPlaceholders || imageDataMap == null || imageDataMap!.isEmpty) &&
        (!hasFilenameImages || imageDataMap == null || imageDataMap!.isEmpty)) {
      return _buildWithBase64Images(text);
    }

    // If text contains filename images but no placeholders, handle filename images directly
    if (hasFilenameImages &&
        imageDataMap != null &&
        imageDataMap!.isNotEmpty &&
        (!hasPlaceholders || imageDataMap == null || imageDataMap!.isEmpty)) {
      return _buildWithFilenameImages(text);
    }

    // If text contains both placeholders and filename images, use combined processing
    if (hasPlaceholders &&
        hasFilenameImages &&
        imageDataMap != null &&
        imageDataMap!.isNotEmpty) {
      return _buildWithPlaceholdersAndFilenameImages(text);
    }

    // Parse text and replace placeholders with images
    final parts = <Widget>[];
    final textParts = text.split(ebookPlaceholderRe);
    final matches = ebookPlaceholderRe.allMatches(text);
    int matchIndex = 0;

    for (int i = 0; i < textParts.length; i++) {
      // Add text part
      if (textParts[i].isNotEmpty) {
        parts.add(
          enableSelection
              ? SelectableText.rich(
                  TextSpan(
                    text: textParts[i],
                    style: style,
                  ),
                )
              : Text.rich(
                  TextSpan(
                    text: textParts[i],
                    style: style,
                  ),
                ),
        );
      }

      // Add image if placeholder found
      if (i < textParts.length - 1 && matchIndex < matches.length) {
        final match = matches.elementAt(matchIndex);
        final placeholderId = match.group(1);
        matchIndex++;

        if (placeholderId != null) {
          final imageData = lookupImageData(imageDataMap, placeholderId);
          if (imageData != null) {
            parts.add(_buildImageWidget(imageData));
            continue;
          }
          // Placeholder ID not found in map, show placeholder text
          AppLogger.log(
            'MarkdownTextWithImages',
            'Placeholder ID not found in imageDataMap: $placeholderId',
            level: LogLevel.warn,
          );
          AppLogger.log(
            'MarkdownTextWithImages',
            'Available placeholder IDs: ${imageDataMap?.keys.toList() ?? <String>[]}',
          );
          parts.add(
            Text(
              '<ph-$placeholderId>',
              style: TextStyle(
                fontSize: style?.fontSize ?? 14,
                color: Colors.grey.shade600,
                fontStyle: FontStyle.italic,
              ),
            ),
          );
        }
      }
    }

    // If only one part and it's text, return as SelectableText/Text
    if (parts.length == 1) {
      return parts[0];
    }

    // Multiple parts (text + images), wrap in Column
    // Use RepaintBoundary to prevent unnecessary repaints
    return RepaintBoundary(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: parts,
      ),
    );
  }

  /// Build widget with filename-based image references (e.g., ![alt](filename.jpg))
  Widget _buildWithFilenameImages(String text) {
    // Build reverse map: filename -> image data
    final filenameToImageData = <String, Map<String, String>>{};

    if (imageDataMap != null) {
      AppLogger.log(
        'MarkdownTextWithImages',
        'Building filename map from imageDataMap with ${imageDataMap!.length} entries',
      );
      imageDataMap!.forEach((placeholderId, imageData) {
        final altText = imageData['alt'] ?? '';
        if (altText.isNotEmpty) {
          // Extract filename from alt text (could be full path or just filename)
          final extractedFilename = altText.split('/').last.split(r'\').last;
          if (extractedFilename.isNotEmpty && extractedFilename.contains('.')) {
            filenameToImageData[extractedFilename] = imageData;
            AppLogger.log(
              'MarkdownTextWithImages',
              'Added filename mapping: $extractedFilename -> placeholder $placeholderId',
            );
          }
          // Also add full altText as key (might be full path)
          filenameToImageData[altText] = imageData;
          // Add placeholder ID as key for backward compatibility
          filenameToImageData[placeholderId] = imageData;
        }
      });
      AppLogger.log(
        'MarkdownTextWithImages',
        'Filename map built with ${filenameToImageData.length} entries',
      );
    }

    final filenameImagePattern =
        RegExp(r'!\[([^\]]*)\]\(([^)]+\.(jpg|jpeg|png|gif|webp))\)');
    final matches = filenameImagePattern.allMatches(text);
    AppLogger.log(
      'MarkdownTextWithImages',
      'Found ${matches.length} filename image references in text',
    );

    final parts = <Widget>[];
    final textParts = text.split(filenameImagePattern);
    int matchIndex = 0;

    for (int i = 0; i < textParts.length; i++) {
      // Add text part
      if (textParts[i].isNotEmpty) {
        parts.add(
          enableSelection
              ? SelectableText.rich(
                  TextSpan(
                    text: textParts[i],
                    style: style,
                  ),
                )
              : Text.rich(
                  TextSpan(
                    text: textParts[i],
                    style: style,
                  ),
                ),
        );
      }

      // Add image if filename reference found
      if (i < textParts.length - 1 && matchIndex < matches.length) {
        final match = matches.elementAt(matchIndex);
        final altText = match.group(1) ?? '';
        final filename = match.group(2) ?? '';
        matchIndex++;

        // Extract just the filename from path (handle ./images/xxx.jpg, images/xxx.jpg, xxx.jpg)
        final normalizedFilename = filename
            .replaceFirst(RegExp(r'^\./'), '') // Remove leading ./
            .split('/')
            .last
            .split(r'\')
            .last;

        AppLogger.log(
          'MarkdownTextWithImages',
          'Processing image reference: alt="$altText", filename="$filename", normalized="$normalizedFilename"',
        );

        // Try to find image data by filename
        Map<String, String>? imageData;

        // Try exact match first
        if (filenameToImageData.containsKey(normalizedFilename)) {
          imageData = filenameToImageData[normalizedFilename];
          AppLogger.log(
            'MarkdownTextWithImages',
            'Found image data by normalized filename: $normalizedFilename',
          );
        } else if (filenameToImageData.containsKey(filename)) {
          imageData = filenameToImageData[filename];
          AppLogger.log(
            'MarkdownTextWithImages',
            'Found image data by original filename: $filename',
          );
        } else {
          // Try to find by searching in imageDataMap
          if (imageDataMap != null) {
            for (final entry in imageDataMap!.entries) {
              final entryAltText = entry.value['alt'] ?? '';
              final extractedFilename =
                  entryAltText.split('/').last.split(r'\').last;
              // Try multiple matching strategies
              if (extractedFilename == normalizedFilename ||
                  extractedFilename == filename ||
                  entryAltText == filename ||
                  entryAltText.endsWith(normalizedFilename) ||
                  entryAltText.endsWith(filename)) {
                imageData = entry.value;
                AppLogger.log(
                  'MarkdownTextWithImages',
                  'Found image data by searching: placeholder=${entry.key}, alt=$entryAltText',
                );
                break;
              }
            }
          }

          if (imageData == null) {
            AppLogger.log(
              'MarkdownTextWithImages',
              'No image data found for filename: $filename (normalized: $normalizedFilename)',
              level: LogLevel.warn,
            );
            AppLogger.log(
              'MarkdownTextWithImages',
              'Available keys in filenameToImageData: ${filenameToImageData.keys.toList()}',
            );
          }
        }

        if (imageData != null) {
          final base64Data = imageData['data'];
          AppLogger.log(
            'MarkdownTextWithImages',
            'Image data found: base64Data length=${base64Data?.length ?? 0}, startsWith data:image=${base64Data?.startsWith('data:image/') ?? false}',
          );

          if (base64Data != null && base64Data.startsWith('data:image/')) {
            try {
              // Extract base64 string (remove "data:image/type;base64," prefix)
              final base64String = base64Data.split(',')[1];
              AppLogger.log(
                'MarkdownTextWithImages',
                'Decoding image: base64String length=${base64String.length}',
              );

              final imageBytes = base64Decode(base64String);
              AppLogger.log(
                'MarkdownTextWithImages',
                'Image decoded successfully: bytes length=${imageBytes.length}',
              );

              parts.add(
                RepaintBoundary(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Align(
                          alignment: Alignment.centerLeft,
                          child: ConstrainedBox(
                            constraints: BoxConstraints(
                              maxWidth: imageMaxWidth ?? double.infinity,
                              maxHeight: imageMaxHeight ?? double.infinity,
                            ),
                            child: Image.memory(
                              imageBytes,
                              fit: BoxFit.scaleDown,
                              gaplessPlayback: true,
                              frameBuilder: (
                                context,
                                child,
                                frame,
                                wasSynchronouslyLoaded,
                              ) =>
                                  child,
                              errorBuilder: (
                                context,
                                error,
                                stackTrace,
                              ) {
                                AppLogger.log(
                                  'MarkdownTextWithImages',
                                  'Image.memory error: $error\n$stackTrace',
                                  level: LogLevel.error,
                                );
                                return Container(
                                  constraints: BoxConstraints(
                                    maxWidth: imageMaxWidth ?? double.infinity,
                                    maxHeight: imageMaxHeight ?? 400,
                                  ),
                                  padding: const EdgeInsets.all(8),
                                  color: Colors.grey.shade200,
                                  child: Center(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: <Widget>[
                                        Icon(
                                          Icons.broken_image,
                                          color: Colors.grey.shade600,
                                          size: 32,
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          altText.isNotEmpty
                                              ? altText
                                              : 'Image',
                                          style: TextStyle(
                                            fontSize:
                                                (style?.fontSize ?? 14) * 0.9,
                                            color: Colors.grey.shade600,
                                          ),
                                        ),
                                        Text(
                                          'Error: ${error.toString()}',
                                          style: TextStyle(
                                            fontSize:
                                                (style?.fontSize ?? 14) * 0.7,
                                            color: Colors.red.shade600,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                        ),
                        if (altText.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              altText,
                              style: TextStyle(
                                fontSize: (style?.fontSize ?? 14) * 0.85,
                                color: Colors.grey.shade600,
                                fontStyle: FontStyle.italic,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              );
            } catch (e, stackTrace) {
              // If image decode fails, show placeholder text
              AppLogger.log(
                'MarkdownTextWithImages',
                'Failed to decode image: $e\n$stackTrace',
                level: LogLevel.error,
              );
              parts.add(
                Container(
                  padding: const EdgeInsets.all(8),
                  color: Colors.orange.shade50,
                  child: Row(
                    children: <Widget>[
                      Icon(
                        Icons.error_outline,
                        color: Colors.orange.shade700,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '![$altText]($filename)',
                          style: TextStyle(
                            fontSize: style?.fontSize ?? 14,
                            color: Colors.orange.shade900,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }
          } else {
            // No valid image data, show placeholder text
            parts.add(
              Text(
                '![$altText]($filename)',
                style: TextStyle(
                  fontSize: style?.fontSize ?? 14,
                  color: Colors.grey.shade600,
                  fontStyle: FontStyle.italic,
                ),
              ),
            );
          }
        } else {
          // Image data not found, show placeholder text
          parts.add(
            Text(
              '![$altText]($filename)',
              style: TextStyle(
                fontSize: style?.fontSize ?? 14,
                color: Colors.grey.shade600,
                fontStyle: FontStyle.italic,
              ),
            ),
          );
        }
      }
    }

    // If only one part and it's text, return as SelectableText/Text
    if (parts.length == 1) {
      return parts[0];
    }

    // Multiple parts (text + images), wrap in Column
    return RepaintBoundary(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: parts,
      ),
    );
  }

  /// Build widget with both placeholders and filename-based image references
  Widget _buildWithPlaceholdersAndFilenameImages(String text) {
    // First, replace placeholders with filename-based image references
    String processedText = text;

    if (imageDataMap != null) {
      processedText = processedText.replaceAllMapped(ebookPlaceholderRe, (match) {
        final placeholderId = match.group(1);
        if (placeholderId != null) {
          final imageData = lookupImageData(imageDataMap, placeholderId);
          if (imageData != null) {
            final base64Data = imageData['data'];
            final altText = imageData['alt'] ?? '';
            if (base64Data != null && base64Data.startsWith('data:image/')) {
              final filename = altText.split('/').last.split(r'\').last;
              if (filename.isNotEmpty && filename.contains('.')) {
                return '![$altText]($filename)';
              }
            }
          }
        }
        return match.group(0)!;
      });
    }

    // Then process filename images
    return _buildWithFilenameImages(processedText);
  }

  /// Build widget with base64 images embedded directly in text
  Widget _buildWithBase64Images(String text) {
    final base64ImagePattern = RegExp(r'(data:image/[^;]+;base64,[^\s)]+)');
    final parts = <Widget>[];
    final textParts = text.split(base64ImagePattern);
    final matches = base64ImagePattern.allMatches(text);
    int matchIndex = 0;

    for (int i = 0; i < textParts.length; i++) {
      // Add text part
      if (textParts[i].isNotEmpty) {
        parts.add(
          enableSelection
              ? SelectableText.rich(
                  TextSpan(
                    text: textParts[i],
                    style: style,
                  ),
                )
              : Text.rich(
                  TextSpan(
                    text: textParts[i],
                    style: style,
                  ),
                ),
        );
      }

      // Add image if base64 data found
      if (i < textParts.length - 1 && matchIndex < matches.length) {
        final match = matches.elementAt(matchIndex);
        final base64Data = match.group(1);
        matchIndex++;

        if (base64Data != null && base64Data.startsWith('data:image/')) {
          try {
            // Extract base64 string (remove "data:image/type;base64," prefix)
            final base64String = base64Data.split(',')[1];
            final imageBytes = base64Decode(base64String);

            parts.add(
              RepaintBoundary(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: imageMaxWidth ?? double.infinity,
                      maxHeight: imageMaxHeight ?? double.infinity,
                    ),
                    child: Image.memory(
                      imageBytes,
                      fit: BoxFit.scaleDown,
                      gaplessPlayback: true,
                      errorBuilder: (
                        context,
                        error,
                        stackTrace,
                      ) =>
                          Container(
                        constraints: BoxConstraints(
                          maxWidth: imageMaxWidth ?? double.infinity,
                          maxHeight: imageMaxHeight ?? 400,
                        ),
                        padding: const EdgeInsets.all(8),
                        color: Colors.grey.shade200,
                        child: Center(
                          child: Text(
                            'Image',
                            style: TextStyle(
                              fontSize: (style?.fontSize ?? 14) * 0.9,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            );
          } catch (e) {
            // If image decode fails, show placeholder text
            parts.add(
              Text(
                '[Image decode error]',
                style: TextStyle(
                  fontSize: style?.fontSize ?? 14,
                  color: Colors.grey.shade600,
                  fontStyle: FontStyle.italic,
                ),
              ),
            );
          }
        }
      }
    }

    // If only one part and it's text, return as SelectableText/Text
    if (parts.length == 1) {
      return parts[0];
    }

    // Multiple parts (text + images), wrap in Column
    return RepaintBoundary(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: parts,
      ),
    );
  }

  /// Render a single image from image_data_map entry.
  Widget _buildImageWidget(Map<String, String> imageData) {
    final base64Data = imageData['data'];
    final altText = imageData['alt'] ?? '';

    if (base64Data == null || !base64Data.startsWith('data:image/')) {
      return Text(
        altText.isNotEmpty ? altText : 'Image',
        style: TextStyle(
          fontSize: style?.fontSize ?? 14,
          color: Colors.grey.shade600,
          fontStyle: FontStyle.italic,
        ),
      );
    }

    try {
      final base64String = base64Data.split(',')[1];
      final imageBytes = base64Decode(base64String);
      return RepaintBoundary(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Align(
                alignment: Alignment.centerLeft,
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxWidth: imageMaxWidth ?? double.infinity,
                    maxHeight: imageMaxHeight ?? double.infinity,
                  ),
                  child: Image.memory(
                    imageBytes,
                    fit: BoxFit.scaleDown,
                    gaplessPlayback: true,
                    frameBuilder: (
                      context,
                      child,
                      frame,
                      wasSynchronouslyLoaded,
                    ) =>
                        child,
                    errorBuilder: (
                      context,
                      error,
                      stackTrace,
                    ) {
                      return Container(
                        constraints: BoxConstraints(
                          maxWidth: imageMaxWidth ?? double.infinity,
                          maxHeight: imageMaxHeight ?? 400,
                        ),
                        padding: const EdgeInsets.all(8),
                        color: Colors.grey.shade200,
                        child: Center(
                          child: Text(
                            altText.isNotEmpty ? altText : 'Image',
                            style: TextStyle(
                              fontSize: (style?.fontSize ?? 14) * 0.9,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
              if (altText.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    altText,
                    style: TextStyle(
                      fontSize: (style?.fontSize ?? 14) * 0.85,
                      color: Colors.grey.shade600,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
    } catch (e) {
      return Text(
        altText.isNotEmpty ? altText : 'Image',
        style: TextStyle(
          fontSize: style?.fontSize ?? 14,
          color: Colors.grey.shade600,
          fontStyle: FontStyle.italic,
        ),
      );
    }
  }

  /// Build widget with inline and display LaTeX delimiters.
  Widget _buildWithLaTeX(String text) {
    final List<LatexTextSegment> segments = splitLatexTextSegments(text);
    final bool hasDisplay = segments.any(
      (LatexTextSegment segment) => segment.kind == LatexSegmentKind.display,
    );

    if (!hasDisplay) {
      return _buildInlineLaTeXFlow(segments);
    }

    final List<Widget> parts = <Widget>[];
    final StringBuffer plainBuffer = StringBuffer();

    void flushPlainBuffer() {
      if (plainBuffer.isEmpty) {
        return;
      }
      final String plainText = plainBuffer.toString();
      plainBuffer.clear();
      parts.add(_buildPlainOrRecursiveTextPart(plainText));
    }

    for (final LatexTextSegment segment in segments) {
      switch (segment.kind) {
        case LatexSegmentKind.plain:
          plainBuffer.write(segment.text);
        case LatexSegmentKind.inline:
          flushPlainBuffer();
          parts.add(_buildInlineLaTeXFlow(<LatexTextSegment>[segment]));
        case LatexSegmentKind.display:
          flushPlainBuffer();
          parts.add(_buildLaTeXWidget(segment.text, displayMode: true));
      }
    }
    flushPlainBuffer();

    if (parts.length == 1) {
      return parts.first;
    }

    return RepaintBoundary(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: parts,
      ),
    );
  }

  Widget _buildPlainOrRecursiveTextPart(String plainText) {
    if (plainText.isEmpty) {
      return const SizedBox.shrink();
    }

    final RegExp base64ImagePattern =
        RegExp(r'data:image/[^;]+;base64,[^\s)]+');
    final bool hasPlaceholders = ebookPlaceholderRe.hasMatch(plainText);
    final bool hasHtmlExtractorPart =
        parseHtmlExtractorImageSegment(plainText.trim()) != null;
    final bool hasBase64Images = base64ImagePattern.hasMatch(plainText);

    if (hasPlaceholders || hasBase64Images || hasHtmlExtractorPart) {
      return MarkdownTextWithImages(
        text: plainText,
        imageDataMap: imageDataMap,
        enableSelection: enableSelection,
        style: style,
        imageMaxWidth: imageMaxWidth,
        imageMaxHeight: imageMaxHeight,
      );
    }

    if (textContainsLatexMath(plainText)) {
      return _buildWithLaTeX(plainText);
    }

    return enableSelection
        ? SelectableText.rich(
            TextSpan(
              text: plainText,
              style: style,
            ),
          )
        : Text.rich(
            TextSpan(
              text: plainText,
              style: style,
            ),
          );
  }

  Widget _buildInlineLaTeXFlow(List<LatexTextSegment> segments) {
    final List<InlineSpan> spans = <InlineSpan>[];
    for (final LatexTextSegment segment in segments) {
      if (segment.kind == LatexSegmentKind.plain) {
        if (segment.text.isEmpty) {
          continue;
        }
        spans.add(TextSpan(text: segment.text));
        continue;
      }
      spans.add(
        WidgetSpan(
          alignment: PlaceholderAlignment.baseline,
          baseline: TextBaseline.alphabetic,
          child: _buildInlineLaTeXChip(segment.text),
        ),
      );
    }

    if (spans.isEmpty) {
      return const SizedBox.shrink();
    }

    if (spans.length == 1 && spans.first is TextSpan) {
      final TextSpan onlySpan = spans.first as TextSpan;
      return enableSelection
          ? SelectableText.rich(
              TextSpan(
                text: onlySpan.text,
                style: style,
              ),
            )
          : Text.rich(
              TextSpan(
                text: onlySpan.text,
                style: style,
              ),
            );
    }

    return enableSelection
        ? SelectableText.rich(
            TextSpan(style: style, children: spans),
          )
        : Text.rich(
            TextSpan(style: style, children: spans),
          );
  }

  Widget _buildInlineLaTeXChip(String latex) {
    final TextStyle chipStyle = style?.copyWith(
          fontFamily: 'monospace',
          fontSize: (style?.fontSize ?? 14) * 0.92,
          color: Colors.blue.shade800,
          height: 1.2,
        ) ??
        TextStyle(
          fontFamily: 'monospace',
          fontSize: 12,
          color: Colors.blue.shade800,
          height: 1.2,
        );

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 1),
      child: Text(latex, style: chipStyle),
    );
  }

  /// Build a widget for rendering LaTeX formula
  /// Note: Due to limitations with HtmlElementView in Flutter Web,
  /// we display LaTeX code as formatted text on all platforms.
  /// Users can copy the LaTeX code and render it in external tools if needed.
  Widget _buildLaTeXWidget(String latex, {bool displayMode = false}) {
    // Display LaTeX code as formatted text on all platforms
    // This avoids HtmlElementView issues in Flutter Web
    return Padding(
      padding: EdgeInsets.symmetric(vertical: displayMode ? 8.0 : 4.0),
      child: Container(
        padding: EdgeInsets.all(displayMode ? 12.0 : 8.0),
        decoration: BoxDecoration(
          color: Colors.blue.shade50.withOpacity(0.5),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: Colors.blue.shade300,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            // LaTeX indicator icon
            Padding(
              padding: const EdgeInsets.only(right: 8, top: 2),
              child: Icon(
                Icons.functions,
                size: 16,
                color: Colors.blue.shade700,
              ),
            ),
            // LaTeX code
            Expanded(
              child: SelectableText(
                '\$$latex\$',
                style: style?.copyWith(
                      fontFamily: 'monospace',
                      color: Colors.blue.shade900,
                      fontSize: (style?.fontSize ?? 14) * 0.95,
                    ) ??
                    TextStyle(
                      fontFamily: 'monospace',
                      color: Colors.blue.shade900,
                      fontSize: 12,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
