// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../utils/entity_group_helper.dart';

/// Widget for displaying missing placeholders
class MissingPlaceholdersWidget extends StatelessWidget {
  const MissingPlaceholdersWidget({
    required this.missingPlaceholders,
    required this.anonymizedText,
    required this.isExpanded,
    required this.onToggle,
    required this.onAddAll,
    super.key,
  });
  final Set<String> missingPlaceholders;
  final String anonymizedText;
  final bool isExpanded;
  final VoidCallback onToggle;
  final void Function(String placeholder) onAddAll;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    if (missingPlaceholders.isEmpty) {
      return const SizedBox.shrink();
    }

    // Count occurrences for each placeholder
    final Map<String, int> placeholderCounts = <String, int>{};
    for (final String placeholder in missingPlaceholders) {
      final List<PlaceholderPosition> positions =
          EntityGroupHelper.findPlaceholderPositions(
        anonymizedText,
        placeholder,
      );
      placeholderCounts[placeholder] = positions.length;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 1,
      color: theme.colorScheme.errorContainer.withOpacity(0.2),
      child: ExpansionTile(
        initiallyExpanded: isExpanded,
        onExpansionChanged: (_) => onToggle(),
        leading: Icon(
          Icons.warning_amber_rounded,
          size: 20,
          color: theme.colorScheme.error,
        ),
        title: Row(
          children: <Widget>[
            Text(
              'Missing Placeholders',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: theme.colorScheme.onSurface,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: theme.colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                '${missingPlaceholders.length}',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: theme.colorScheme.onErrorContainer,
                ),
              ),
            ),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            'Placeholders found in anonymized text but not in entities',
            style: TextStyle(
              fontSize: 11,
              color: theme.colorScheme.onSurfaceVariant,
              fontStyle: FontStyle.italic,
            ),
          ),
        ),
        children: missingPlaceholders.map((String placeholder) {
          final int count = placeholderCounts[placeholder] ?? 0;
          final String? type =
              EntityGroupHelper.extractTypeFromPlaceholder(placeholder);

          return Card(
            margin: const EdgeInsets.only(left: 16, right: 8, bottom: 4),
            elevation: 0,
            color: theme.colorScheme.surface,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: <Widget>[
                  // Placeholder
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          placeholder,
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: theme.colorScheme.onSurface,
                            fontFamily: 'monospace',
                          ),
                        ),
                        if (type != null) ...<Widget>[
                          const SizedBox(height: 2),
                          Text(
                            'Type: $type',
                            style: TextStyle(
                              fontSize: 11,
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Count
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color:
                          theme.colorScheme.primaryContainer.withOpacity(0.3),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '$count ${count == 1 ? 'occurrence' : 'occurrences'}',
                      style: TextStyle(
                        fontSize: 11,
                        color: theme.colorScheme.onPrimaryContainer,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Add All button
                  ElevatedButton.icon(
                    onPressed: () => onAddAll(placeholder),
                    icon: const Icon(Icons.add, size: 16),
                    label: const Text('Add All'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
