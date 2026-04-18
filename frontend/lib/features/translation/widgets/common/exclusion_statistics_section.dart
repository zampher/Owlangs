// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../../l10n/app_localizations.dart';
import '../../models/exclusion_reason.dart';

/// Statistics section in exclusion panel
/// Displays total segments, excluded count, and breakdown by type
/// Supports checkbox controls for categories (Reference, Structural, Language Match)
class ExclusionStatisticsSection extends StatelessWidget {
  const ExclusionStatisticsSection({
    required this.exclusionCounts,
    required this.totalSegments,
    required this.excludedCount,
    this.categoryExclusionStates,
    this.onCategoryExclusionChanged,
    super.key,
  });

  final Map<String, int> exclusionCounts;
  final int totalSegments;
  final int excludedCount;
  final Map<String, bool>? categoryExclusionStates;
  final Function(String category, bool exclude)? onCategoryExclusionChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            l10n.exclusionPanelExclusionByType,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 8),
          // Use Wrap layout, 2-3 types per row
          // Show checkboxes for controllable categories (Reference, Structural, Language Match)
          // For Structural, show header and footer separately
          // Sort by count (descending) before displaying
          Builder(
            builder: (BuildContext context) {
              final List<MapEntry<String, int>> filteredEntries =
                  exclusionCounts.entries.where((MapEntry<String, int> entry) {
                // Filter out structural_header and structural_footer (handled separately below)
                // Filter out unknown (merged into user_selected)
                // Only show types with count > 0
                return entry.key != 'structural_header' &&
                    entry.key != 'structural_footer' &&
                    entry.key != ExclusionReason.unknown.value &&
                    entry.value > 0;
              }).toList()
                    ..sort(
                      (MapEntry<String, int> a, MapEntry<String, int> b) =>
                          b.value.compareTo(a.value),
                    ); // Sort by count descending

              return Wrap(
                spacing: 16,
                runSpacing: 8,
                children: <Widget>[
                  ...filteredEntries.map((MapEntry<String, int> entry) {
                    final ExclusionReason reason =
                        ExclusionReason.fromString(entry.key);
                    // Check if this category can be controlled
                    final category = _getCategoryForReason(reason);
                    final isExcluded =
                        category != null && categoryExclusionStates != null
                            ? categoryExclusionStates![category]
                            : null;
                    // Only show checkbox when count > 0 and category is controllable
                    final showCheckbox = entry.value > 0 &&
                        category != null &&
                        onCategoryExclusionChanged != null;

                    return _buildTypeStat(
                      context,
                      reason,
                      entry.value,
                      showCheckbox: showCheckbox,
                      isExcluded: isExcluded ?? false,
                      onChanged: showCheckbox
                          ? (bool? value) {
                              if (value != null) {
                                // category is guaranteed to be non-null when showCheckbox is true
                                onCategoryExclusionChanged!(category, value);
                              }
                            }
                          : null,
                    );
                  }),
                  // Add structural_header and structural_footer if they exist
                  if (exclusionCounts.containsKey('structural_header') &&
                      exclusionCounts['structural_header']! > 0)
                    _buildTypeStat(
                      context,
                      ExclusionReason.structural,
                      exclusionCounts['structural_header']!,
                      label: l10n.exclusionPanelStructuralHeader,
                      showCheckbox: categoryExclusionStates != null &&
                          onCategoryExclusionChanged != null &&
                          categoryExclusionStates!.containsKey('structural'),
                      isExcluded:
                          categoryExclusionStates?['structural'] ?? false,
                      onChanged: (categoryExclusionStates != null &&
                              onCategoryExclusionChanged != null)
                          ? (bool? value) {
                              if (value != null) {
                                onCategoryExclusionChanged!(
                                    'structural', value,);
                              }
                            }
                          : null,
                    ),
                  if (exclusionCounts.containsKey('structural_footer') &&
                      exclusionCounts['structural_footer']! > 0)
                    _buildTypeStat(
                      context,
                      ExclusionReason.structural,
                      exclusionCounts['structural_footer']!,
                      label: l10n.exclusionPanelStructuralFooter,
                      showCheckbox: categoryExclusionStates != null &&
                          onCategoryExclusionChanged != null &&
                          categoryExclusionStates!.containsKey('structural'),
                      isExcluded:
                          categoryExclusionStates?['structural'] ?? false,
                      onChanged: (categoryExclusionStates != null &&
                              onCategoryExclusionChanged != null)
                          ? (bool? value) {
                              if (value != null) {
                                onCategoryExclusionChanged!(
                                    'structural', value,);
                              }
                            }
                          : null,
                    ),
                ],
              );
            },
          ),
        ],
      );
  }

  Widget _buildTypeStat(
    BuildContext context,
    ExclusionReason reason,
    int count, {
    bool showCheckbox = false,
    bool isExcluded = false,
    Function(bool?)? onChanged,
    String? label,
  }) {
    final l10n = AppLocalizations.of(context)!;
    final String displayLabel = label ?? reason.displayNameLocalized(l10n);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        if (showCheckbox) ...<Widget>[
          SizedBox(
            width: 18,
            height: 18,
            child: Checkbox(
              value: isExcluded,
              onChanged: onChanged,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
          ),
          const SizedBox(width: 4),
        ],
        Icon(reason.icon, size: 14, color: reason.color),
        const SizedBox(width: 4),
        Text(
          '$displayLabel: $count',
          style: const TextStyle(fontSize: 10),
        ),
      ],
    );
  }

  /// Get category name for a given ExclusionReason (if controllable)
  String? _getCategoryForReason(ExclusionReason reason) {
    switch (reason) {
      case ExclusionReason.formula:
        return 'formula';
      case ExclusionReason.reference:
        return 'reference';
      case ExclusionReason.structural:
        return 'structural';
      case ExclusionReason.languageMatch:
        return 'language_match';
      case ExclusionReason.identifier:
        return 'identifier';
      case ExclusionReason.table:
        return 'table';
      case ExclusionReason.userSelected:
        return 'user_selected';
      case ExclusionReason.unknown:
        // Merge unknown into user_selected
        return 'user_selected';
      default:
        return null;
    }
  }
}
