// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../models/entity_group.dart';

/// Widget for displaying a single entity occurrence (second level)
class EntityOccurrenceItem extends StatelessWidget {
  const EntityOccurrenceItem({
    required this.occurrence,
    required this.isSelected,
    required this.onTap,
    super.key,
    this.isChecked = false,
    this.onCheckboxChanged,
    this.onEdit,
    this.onDelete,
  });
  final EntityOccurrence occurrence;
  final bool isSelected;
  final bool isChecked;
  final VoidCallback onTap;
  final void Function(bool)? onCheckboxChanged;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Use displaySegmentIndexString for consistent 1-based display (matches preview)
    final segmentDisplay = occurrence.displaySegmentIndexString;
    final placeholder = occurrence.placeholder;

    return Card(
      margin: const EdgeInsets.only(left: 16, right: 8, bottom: 4),
      elevation: isSelected ? 2 : 0,
      color: isSelected
          ? theme.colorScheme.primaryContainer.withOpacity(0.2)
          : theme.colorScheme.surface,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: <Widget>[
              // Checkbox
              if (onCheckboxChanged != null)
                Checkbox(
                  value: isChecked,
                  onChanged: (checked) =>
                      onCheckboxChanged?.call(checked ?? false),
                ),
              // Segment and position info
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primaryContainer.withOpacity(0.3),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  segmentDisplay,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Text
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      occurrence.text,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight:
                            isSelected ? FontWeight.bold : FontWeight.normal,
                        color: theme.colorScheme.onSurface,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (placeholder.isNotEmpty) ...<Widget>[
                      const SizedBox(height: 2),
                      Text(
                        placeholder,
                        style: TextStyle(
                          fontSize: 11,
                          color: theme.colorScheme.onSurfaceVariant,
                          fontFamily: 'monospace',
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              // Actions
              if (onEdit != null || onDelete != null) ...<Widget>[
                if (onEdit != null)
                  IconButton(
                    icon: const Icon(Icons.edit, size: 16),
                    onPressed: onEdit,
                    tooltip: 'Edit',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                  ),
                if (onDelete != null)
                  IconButton(
                    icon: const Icon(Icons.delete, size: 16),
                    onPressed: onDelete,
                    tooltip: 'Delete',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    color: theme.colorScheme.error,
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
