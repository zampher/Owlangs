// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

/// Translation output format for preview.
enum TranslationPreviewMode {
  /// Rendered HTML / Markdown (UnifiedPreviewWidget).
  html,

  /// High-fidelity PDF (Typst overlay).
  pdfPreserve,

  /// Reflow PDF (Pandoc).
  pdfReflow,

  /// Original raster layout (erase OCR + write translation on source image).
  imageOriginalLayout,
}

extension TranslationPreviewModeX on TranslationPreviewMode {
  String? get rendererType {
    switch (this) {
      case TranslationPreviewMode.pdfPreserve:
        return 'typst_overlay';
      case TranslationPreviewMode.pdfReflow:
        return 'pandoc';
      case TranslationPreviewMode.html:
      case TranslationPreviewMode.imageOriginalLayout:
        return null;
    }
  }

  bool get usesHtmlPreview => this == TranslationPreviewMode.html;

  bool get usesImagePreview => this == TranslationPreviewMode.imageOriginalLayout;

  bool get usesPdfPreview =>
      this == TranslationPreviewMode.pdfPreserve ||
      this == TranslationPreviewMode.pdfReflow;

  /// Inline bilingual export (source+target in one document).
  /// Not supported for preserve-layout PDF.
  bool get supportsBilingualExportOptions =>
      this == TranslationPreviewMode.html ||
      this == TranslationPreviewMode.pdfReflow;

  /// Default full-document compare for this preview mode (preserve PDF / image).
  bool get defaultFullDocumentCompare =>
      this == TranslationPreviewMode.pdfPreserve ||
      this == TranslationPreviewMode.imageOriginalLayout;

  /// Default linked-scroll for full-document compare (preserve PDF / image).
  bool get defaultFullCompareSyncScroll =>
      this == TranslationPreviewMode.pdfPreserve ||
      this == TranslationPreviewMode.imageOriginalLayout;
}

/// Default preview mode for the settings dialog.
TranslationPreviewMode defaultPreviewModeForDialog({
  required bool isPdfFile,
  required bool hasPdfDownload,
  required String resolvedWorkflowType,
  bool isImageFile = false,
  bool hasImageDownload = false,
}) {
  if (isImageFile && hasImageDownload) {
    return TranslationPreviewMode.imageOriginalLayout;
  }
  final bool isPdfWorkflow =
      resolvedWorkflowType == 'markdown_based' || isPdfFile;
  if (isPdfWorkflow && isPdfFile && hasPdfDownload) {
    return TranslationPreviewMode.pdfPreserve;
  }
  return TranslationPreviewMode.html;
}

/// Default export option index for the download dialog.
/// PDF source tasks prefer preserve-layout PDF (typst_overlay).
int defaultExportDownloadOptionIndex(
  List<Map<String, dynamic>> downloadOptions, {
  required bool isPdfFile,
  required String resolvedWorkflowType,
}) {
  if (isPdfFile && resolvedWorkflowType != 'html') {
    final int preserveLayoutIndex = downloadOptions.indexWhere(
      (Map<String, dynamic> option) =>
          option['type'] == 'pdf' &&
          option['rendererType'] == 'typst_overlay',
    );
    if (preserveLayoutIndex >= 0) {
      return preserveLayoutIndex;
    }
  }
  return 0;
}

/// Result of the preview settings dialog.
class PreviewSelection {
  const PreviewSelection({
    required this.mode,
    this.fullDocumentCompare = false,
    this.syncScroll = false,
  });

  final TranslationPreviewMode mode;
  final bool fullDocumentCompare;

  /// When [fullDocumentCompare] is true, use a single linked scrollbar.
  final bool syncScroll;
}
