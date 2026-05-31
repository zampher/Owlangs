// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/utils/app_logger.dart';
import '../../models/exclusion_reason.dart';

void _translationResultLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('TranslationResultPreview', message, level: level);
}

/// Filter section in exclusion panel
/// Displays FilterChips for each exclusion reason type
class ExclusionFilterSection extends StatelessWidget {
  const ExclusionFilterSection({
    required this.selectedFilters,
    required this.onFiltersChanged,
    required this.exclusionCounts,
    required this.totalSegments,
    required this.excludedCount,
    required this.failedCount,
    required this.filterMode,
    required this.onFilterModeChanged,
    this.isTranslatePhase =
        false, // True for Translate phase, false for Extract phase
    this.onCollapse, // Optional collapse callback (only in Translate phase)
    super.key,
  });

  final Set<String> selectedFilters;
  final Function(Set<String>) onFiltersChanged;
  final Map<String, int> exclusionCounts;
  final int totalSegments;
  final int excludedCount;
  final int failedCount; // Number of failed segments
  final String filterMode; // 'rebuild' or 'page'
  final Function(String) onFilterModeChanged;
  final bool isTranslatePhase; // Whether this is in Translate phase
  final VoidCallback? onCollapse; // Collapse button callback

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    // Only show exclusion types that have at least one segment (count > 0)
    final availableFilters = exclusionCounts.entries
        .where((e) => e.value > 0)
        .map((e) => e.key)
        .toList();

    // For Translate phase, log which exclusion filters will be rendered
    if (isTranslatePhase && availableFilters.isNotEmpty) {
      final buffer = StringBuffer('[EXCLUSION_FILTERS] Available filters: ');
      for (final key in availableFilters) {
        final count = exclusionCounts[key] ?? 0;
        buffer.write('$key($count), ');
      }
      _translationResultLog(buffer.toString());
    }

    if (availableFilters.isEmpty) {
      return const SizedBox.shrink();
    }

    // For Translate phase: compact layout with Filter Display Mode and Filter on same line
    if (isTranslatePhase) {
      return Row(
        children: <Widget>[
          Expanded(
            child: Wrap(
              spacing: 8,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: <Widget>[
                // Filter Display Mode
                Text(
                  l10n.exclusionPanelFilterDisplayMode,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
                SegmentedButton<String>(
                  segments: <ButtonSegment<String>>[
                    ButtonSegment(
                      value: 'rebuild',
                      label: Text(
                        l10n.exclusionPanelRebuild,
                        style: const TextStyle(fontSize: 10),
                      ),
                      tooltip: l10n.exclusionPanelRebuildTooltip,
                    ),
                    ButtonSegment(
                      value: 'page',
                      label: Text(
                        l10n.exclusionPanelPage,
                        style: const TextStyle(fontSize: 10),
                      ),
                      tooltip: l10n.exclusionPanelPageTooltip,
                    ),
                  ],
                  selected: <String>{filterMode},
                  onSelectionChanged: (Set<String> newSelection) {
                    if (newSelection.isNotEmpty) {
                      onFilterModeChanged(newSelection.first);
                    }
                  },
                  style: SegmentedButton.styleFrom(
                    textStyle: const TextStyle(fontSize: 10),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ), // Compact padding
                  ),
                ),
                // Filter label and chips (Segment type based)
                Text(
                  l10n.exclusionPanelSegmentTypeFilters,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                ),
                // Filter chips
                ..._buildFilterChips(context),
              ],
            ),
          ),
          // Collapse button on the right
          if (onCollapse != null)
            IconButton(
              icon: const Icon(Icons.keyboard_arrow_up),
              iconSize: 16,
              color: Colors.grey.shade600,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(
                minWidth: 28,
                minHeight: 28,
              ),
              tooltip: l10n.exclusionPanelCollapsePanelTooltip,
              onPressed: onCollapse,
            ),
        ],
      );
    }

    // For Extract phase: original layout (unchanged)
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        // Filter Display Mode Selector
        Text(
          l10n.exclusionPanelFilterDisplayMode,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: Theme.of(context).colorScheme.onSurface,
          ),
        ),
        const SizedBox(height: 6),
        SegmentedButton<String>(
          segments: <ButtonSegment<String>>[
            ButtonSegment(
              value: 'rebuild',
              label: Text(l10n.exclusionPanelRebuild),
              tooltip: l10n.exclusionPanelRebuildTooltip,
            ),
            ButtonSegment(
              value: 'page',
              label: Text(l10n.exclusionPanelPage),
              tooltip: l10n.exclusionPanelPageTooltip,
            ),
          ],
          selected: <String>{filterMode},
          onSelectionChanged: (Set<String> newSelection) {
            if (newSelection.isNotEmpty) {
              onFilterModeChanged(newSelection.first);
            }
          },
        ),
        const SizedBox(height: 12),
        const Divider(height: 16),
        // Filter section (Segment type based)
        Text(
          l10n.exclusionPanelSegmentTypeFilters,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: Theme.of(context).colorScheme.onSurface,
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: _buildFilterChips(context),
        ),
      ],
    );
  }

  /// Resolve display label and ExclusionReason for a filter key.
  /// Keeps filter chip labels consistent with segment tags (e.g. "EX: Structural").
  static ExclusionReason _reasonForFilterKey(String reasonKey) {
    if (reasonKey == 'structural_header' || reasonKey == 'structural_footer') {
      return ExclusionReason.structural;
    }
    return ExclusionReason.fromString(reasonKey);
  }

  static String _displayLabelForFilterKey(BuildContext context, String reasonKey) {
    final l10n = AppLocalizations.of(context)!;
    if (reasonKey == 'structural_header') return l10n.exclusionPanelStructuralHeader;
    if (reasonKey == 'structural_footer') return l10n.exclusionPanelStructuralFooter;
    return _reasonForFilterKey(reasonKey).displayNameLocalized(l10n);
  }

  /// Build filter chips list (used by both Translate and Extract phases)
  List<Widget> _buildFilterChips(BuildContext context) {
    // Only show exclusion types that have count > 0
    final availableFilters = exclusionCounts.entries
        .where((e) => e.value > 0)
        .map((e) => e.key)
        .toList();

    return <Widget>[
      // Note: "All", "Failed", "Included", and "All Excluded" buttons are now in the toolbar
      // Only show exclusion reason type FilterChips here - Sorted by count (descending)
      ...() {
        final sortedFilters = availableFilters
            .map((reason) => MapEntry(reason, exclusionCounts[reason] ?? 0))
            .toList()
          ..sort(
            (a, b) => b.value.compareTo(a.value),
          ); // Sort by count descending
        return sortedFilters.map((entry) {
          final reason = entry.key;
          final exclusionReason = _reasonForFilterKey(reason);
          final displayLabel = _displayLabelForFilterKey(context, reason);
          final count = entry.value;
          return FilterChip(
            label: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(
                  exclusionReason.icon,
                  size: isTranslatePhase ? 12 : 14,
                  color: selectedFilters.contains(reason)
                      ? exclusionReason.color
                      : Colors.grey.shade600,
                ),
                const SizedBox(width: 4),
                Text(
                  '$displayLabel ($count)',
                  style: TextStyle(fontSize: isTranslatePhase ? 10 : 10),
                ),
              ],
            ),
            selected: selectedFilters.contains(reason),
            onSelected: (selected) {
              final newFilters = Set<String>.from(selectedFilters);
              // Remove state-based filter keys when selecting an exclusion reason (type) filter
              for (final k in <String>[
                'included',
                'all_excluded',
                'failed',
                'translated',
                'pending',
                'excluded',
                'retry',
                'cleared',
                'images',
              ]) {
                newFilters.remove(k);
              }
              if (selected) {
                newFilters.add(reason);
              } else {
                newFilters.remove(reason);
              }
              onFiltersChanged(newFilters);
            },
            selectedColor: exclusionReason.color.withOpacity(0.2),
            checkmarkColor: exclusionReason.color,
            padding: isTranslatePhase
                ? const EdgeInsets.symmetric(horizontal: 6)
                : null, // Compact padding for Translate phase
            visualDensity: isTranslatePhase
                ? VisualDensity.compact
                : null, // Compact density for Translate phase
          );
        });
      }(),
    ];
  }
}
