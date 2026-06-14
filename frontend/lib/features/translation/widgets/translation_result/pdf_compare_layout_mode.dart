// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

import '../../../../l10n/app_localizations.dart';

/// Layout modes for PDF full-compare / revision preview tab.
enum PdfCompareLayoutMode {
  /// Source preview + translation preview (translation on the right).
  comparePreview,

  /// Translation preview + segment list (segment list on the right).
  translationRevision,

  /// Source preview + translation preview + segment list (left to right).
  compareRevision,
}

extension PdfCompareLayoutModeUi on PdfCompareLayoutMode {
  String label(AppLocalizations l10n) {
    switch (this) {
      case PdfCompareLayoutMode.comparePreview:
        return l10n.translationPreviewLayoutComparePreview;
      case PdfCompareLayoutMode.translationRevision:
        return l10n.translationPreviewLayoutTranslationRevision;
      case PdfCompareLayoutMode.compareRevision:
        return l10n.translationPreviewLayoutCompareRevision;
    }
  }

  IconData get icon {
    switch (this) {
      case PdfCompareLayoutMode.comparePreview:
        return Icons.compare_arrows;
      case PdfCompareLayoutMode.translationRevision:
        return Icons.edit_note;
      case PdfCompareLayoutMode.compareRevision:
        return Icons.view_column_outlined;
    }
  }

  bool get showsRevisionControls =>
      this == PdfCompareLayoutMode.translationRevision ||
      this == PdfCompareLayoutMode.compareRevision;
}
