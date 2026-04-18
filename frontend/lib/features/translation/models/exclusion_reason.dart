// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../l10n/app_localizations.dart';

/// Exclusion reason enum for translation segments
/// Maps backend exclusion_reason values to frontend display properties
enum ExclusionReason {
  image('image', 'Image', Icons.image, Colors.blue),
  formula('formula', 'Formula', Icons.functions, Colors.purple),
  table('table', 'Table', Icons.table_chart, Colors.teal),
  reference('reference', 'Reference', Icons.format_quote, Colors.orange),
  identifier('identifier', 'Identifier', Icons.tag, Colors.grey),
  structural('structural', 'Structural', Icons.view_headline, Colors.brown),
  languageMatch(
      'language_match', 'Language Match', Icons.language, Colors.green,),
  userSelected('user_selected', 'User Excluded', Icons.block, Colors.red),
  unknown('unknown', 'Excluded', Icons.block, Colors.grey);

  final String value;
  final String displayName;
  final IconData icon;
  final Color color;

  const ExclusionReason(
    this.value,
    this.displayName,
    this.icon,
    this.color,
  );

  /// Localized display name for UI (use instead of [displayName] when l10n is available).
  String displayNameLocalized(AppLocalizations l10n) {
    switch (this) {
      case ExclusionReason.image:
        return l10n.settingsExclusionImageTitle;
      case ExclusionReason.formula:
        return l10n.settingsExclusionFormulaTitle;
      case ExclusionReason.table:
        return l10n.settingsExclusionTableTitle;
      case ExclusionReason.reference:
        return l10n.settingsExclusionReferenceTitle;
      case ExclusionReason.identifier:
        return l10n.settingsExclusionIdentifierTitle;
      case ExclusionReason.structural:
        return l10n.settingsExclusionStructuralTitle;
      case ExclusionReason.languageMatch:
        return l10n.settingsExclusionLanguageMatchTitle;
      case ExclusionReason.userSelected:
        return l10n.exclusionPanelUserExcluded;
      case ExclusionReason.unknown:
        return l10n.exclusionPanelExcluded;
    }
  }

  /// Convert string value to ExclusionReason enum
  /// Returns unknown if value is null or not found
  static ExclusionReason fromString(String? value) {
    if (value == null) return unknown;
    return ExclusionReason.values.firstWhere(
      (e) => e.value == value,
      orElse: () => unknown,
    );
  }

  /// Check if this exclusion reason is content-based (cannot be unexcluded)
  /// Content-based exclusions: image, formula, identifier, reference, structural
  /// Note: table is NOT content-based - it's optional (user can choose to exclude)
  bool get isContentBased =>
      this == image ||
      this == formula ||
      this == identifier ||
      this == reference ||
      this == structural;

  /// Check if this exclusion reason is language-based
  bool get isLanguageBased => this == languageMatch;

  /// Check if this exclusion reason is user-based (can be unexcluded)
  bool get isUserBased => this == userSelected;

  /// Check if this exclusion can be unexcluded by user
  /// user_selected, language_match, identifier, table, and formula can be unexcluded
  /// formula, identifier and table can be modified by user (e.g., if they were incorrectly detected)
  bool get canUnexclude =>
      isUserBased ||
      isLanguageBased ||
      this == identifier ||
      this == table ||
      this == formula;
}
