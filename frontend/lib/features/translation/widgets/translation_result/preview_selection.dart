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
}

extension TranslationPreviewModeX on TranslationPreviewMode {
  String? get rendererType {
    switch (this) {
      case TranslationPreviewMode.pdfPreserve:
        return 'typst_overlay';
      case TranslationPreviewMode.pdfReflow:
        return 'pandoc';
      case TranslationPreviewMode.html:
        return null;
    }
  }

  bool get usesHtmlPreview => this == TranslationPreviewMode.html;

  bool get usesPdfPreview =>
      this == TranslationPreviewMode.pdfPreserve ||
      this == TranslationPreviewMode.pdfReflow;

  /// Inline bilingual export (source+target in one document).
  /// Not supported for preserve-layout PDF.
  bool get supportsBilingualExportOptions =>
      this == TranslationPreviewMode.html ||
      this == TranslationPreviewMode.pdfReflow;

  /// Default full-document compare for this preview mode (preserve PDF only).
  bool get defaultFullDocumentCompare =>
      this == TranslationPreviewMode.pdfPreserve;

  /// Default linked-scroll for full-document compare (preserve PDF only).
  bool get defaultFullCompareSyncScroll =>
      this == TranslationPreviewMode.pdfPreserve;
}

/// Default preview mode for the settings dialog.
TranslationPreviewMode defaultPreviewModeForDialog({
  required bool isPdfFile,
  required bool hasPdfDownload,
  required String resolvedWorkflowType,
}) {
  final bool isPdfWorkflow =
      resolvedWorkflowType == 'markdown_based' || isPdfFile;
  if (isPdfWorkflow && isPdfFile && hasPdfDownload) {
    return TranslationPreviewMode.pdfPreserve;
  }
  return TranslationPreviewMode.html;
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
