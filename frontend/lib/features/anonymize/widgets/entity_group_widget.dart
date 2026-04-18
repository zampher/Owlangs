// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../models/entity_group.dart';
import 'entity_occurrence_item.dart';

/// Widget for displaying an entity group (first level)
class EntityGroupWidget extends StatelessWidget {
  const EntityGroupWidget({
    required this.group,
    required this.isExpanded,
    required this.hasSelectedOccurrence,
    required this.onToggle,
    required this.onGroupCheckboxChanged,
    required this.onOccurrenceTap,
    super.key,
    this.highlightedEntityIndex,
    this.isGroupSelected = false,
    this.selectedOccurrenceIndices = const <int>{},
    this.onOccurrenceEdit,
    this.onOccurrenceDelete,
    this.onOccurrenceCheckboxChanged,
    this.onAdd,
    this.onDeleteAll,
  });
  final EntityGroup group;
  final bool isExpanded;
  final bool hasSelectedOccurrence;
  final int? highlightedEntityIndex;
  final bool isGroupSelected;
  final Set<int> selectedOccurrenceIndices;
  final VoidCallback onToggle;
  final void Function(bool) onGroupCheckboxChanged;
  final void Function(int occurrenceIndex) onOccurrenceTap;
  final void Function(int occurrenceIndex)? onOccurrenceEdit;
  final void Function(int occurrenceIndex)? onOccurrenceDelete;
  final void Function(int occurrenceIndex)? onOccurrenceCheckboxChanged;
  final VoidCallback? onAdd;
  final VoidCallback? onDeleteAll;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: hasSelectedOccurrence ? 3 : 1,
      color: hasSelectedOccurrence
          ? theme.colorScheme.primaryContainer.withOpacity(0.2)
          : theme.colorScheme.surface,
      child: ExpansionTile(
        initiallyExpanded: isExpanded,
        onExpansionChanged: (_) => onToggle(),
        leading: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Checkbox(
              value: isGroupSelected,
              onChanged: (checked) => onGroupCheckboxChanged(checked ?? false),
            ),
            Icon(
              isExpanded ? Icons.expand_more : Icons.chevron_right,
              size: 20,
            ),
          ],
        ),
        title: Row(
          children: <Widget>[
            // Text
            Flexible(
              child: Text(
                group.displayName,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: theme.colorScheme.onSurface,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (group.primaryPlaceholder != null) ...<Widget>[
              const SizedBox(width: 8),
              // Placeholder
              Text(
                group.primaryPlaceholder!,
                style: TextStyle(
                  fontSize: 11,
                  color: theme.colorScheme.onSurfaceVariant,
                  fontFamily: 'monospace',
                ),
              ),
            ],
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Row(
            children: <Widget>[
              // Count badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '${group.occurrenceCount} ${group.occurrenceCount == 1 ? 'occurrence' : 'occurrences'}',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
              const Spacer(),
              // Action buttons
              if (onAdd != null)
                IconButton(
                  icon: const Icon(Icons.add, size: 18),
                  onPressed: onAdd,
                  tooltip: 'Add occurrence',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              if (onDeleteAll != null && group.occurrenceCount > 0)
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 18),
                  onPressed: onDeleteAll,
                  tooltip: 'Delete all',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  color: theme.colorScheme.error,
                ),
            ],
          ),
        ),
        children: group.occurrences.map((occurrence) {
          // Check if this specific occurrence is selected
          final isSelected = highlightedEntityIndex != null &&
              occurrence.index == highlightedEntityIndex;
          final isOccurrenceChecked =
              selectedOccurrenceIndices.contains(occurrence.index);

          return EntityOccurrenceItem(
            occurrence: occurrence,
            isSelected: isSelected,
            isChecked: isOccurrenceChecked,
            onTap: () => onOccurrenceTap(occurrence.index),
            onCheckboxChanged: onOccurrenceCheckboxChanged != null
                ? (checked) => onOccurrenceCheckboxChanged!(occurrence.index)
                : null,
            onEdit: onOccurrenceEdit != null
                ? () => onOccurrenceEdit!(occurrence.index)
                : null,
            onDelete: onOccurrenceDelete != null
                ? () => onOccurrenceDelete!(occurrence.index)
                : null,
          );
        }).toList(),
      ),
    );
  }
}
