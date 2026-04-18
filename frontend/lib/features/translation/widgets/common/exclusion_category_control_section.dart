// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../../l10n/app_localizations.dart';
import '../../models/exclusion_reason.dart';

/// Category exclusion control section in exclusion panel
/// Displays checkboxes for each exclusion category (Reference, Structural, Language Match, etc.)
class ExclusionCategoryControlSection extends StatelessWidget {
  const ExclusionCategoryControlSection({
    required this.categoryExclusionStates,
    required this.exclusionCounts,
    required this.onCategoryExclusionChanged,
    super.key,
  });

  final Map<String, bool> categoryExclusionStates;
  final Map<String, int> exclusionCounts;
  final Function(String category, bool exclude) onCategoryExclusionChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            l10n.exclusionPanelExclusionControls,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 8),
          // Display checkboxes only for categories that have at least one segment (count > 0)
          ...categoryExclusionStates.entries
              .map((MapEntry<String, bool> entry) {
            final category = entry.key;
            final isExcluded = entry.value;
            final count = _getCategoryCount(category);

            if (count == 0) {
              return const SizedBox.shrink();
            }

            final reason = _getCategoryReason(category);
            if (reason == null) {
              return const SizedBox.shrink();
            }

            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: <Widget>[
                  SizedBox(
                    width: 18,
                    height: 18,
                    child: Checkbox(
                      value: isExcluded,
                      onChanged: (bool? value) {
                        if (value != null) {
                          onCategoryExclusionChanged(category, value);
                        }
                      },
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Icon(
                    reason.icon,
                    size: 14,
                    color: reason.color,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    l10n.exclusionPanelExcludeCategory(
                      count.toString(),
                      reason.displayNameLocalized(l10n),
                    ),
                    style: TextStyle(
                      fontSize: 10,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      );
  }

  /// Get count for a category
  int _getCategoryCount(String category) {
    final String? reasonValue = _categoryToReason[category];
    if (reasonValue == null) return 0;
    return exclusionCounts[reasonValue] ?? 0;
  }

  /// Get ExclusionReason for a category
  ExclusionReason? _getCategoryReason(String category) {
    final String? reasonValue = _categoryToReason[category];
    if (reasonValue == null) return null;
    return ExclusionReason.fromString(reasonValue);
  }

  static const Map<String, String> _categoryToReason = <String, String>{
    'image': 'image',
    'formula': 'formula',
    'reference': 'reference',
    'identifier': 'identifier',
    'structural': 'structural',
    'table': 'table',
    'language_match': 'language_match',
    'user_selected': 'user_selected',
  };
}
