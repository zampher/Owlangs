// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

/// How a compare-reading pane renders its content.
enum ComparePaneKind {
  pdf,
  image,
  scrollable,
}

/// Loaded document ready for side-by-side compare reading.
class CompareDocumentModel {
  const CompareDocumentModel({
    required this.fileName,
    required this.kind,
    required this.contentType,
    this.pdfBytes,
    this.imageBytes,
    this.textContent,
  });

  final String fileName;
  final ComparePaneKind kind;

  /// UnifiedPreview content type: `md`, `html`, or `plain`.
  final String contentType;

  final Uint8List? pdfBytes;
  final Uint8List? imageBytes;
  final String? textContent;

  bool get isReady {
    switch (kind) {
      case ComparePaneKind.pdf:
        return pdfBytes != null && pdfBytes!.isNotEmpty;
      case ComparePaneKind.image:
        return imageBytes != null && imageBytes!.isNotEmpty;
      case ComparePaneKind.scrollable:
        return textContent != null;
    }
  }
}
