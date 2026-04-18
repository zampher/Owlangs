// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show debugPrint;

/// Dialog for editing entity text and placeholder
/// Shows the segment containing the entity and allows user to select/edit text
class EntityEditDialog extends StatefulWidget {
  const EntityEditDialog({
    required this.entity,
    required this.segmentText,
    required this.segmentIndex,
    required this.segmentStartInFullText,
    required this.entityStartInSegment,
    required this.entityEndInSegment,
    super.key,
  });
  final Map<String, dynamic> entity;
  final String segmentText;
  final int segmentIndex;
  final int segmentStartInFullText;
  final int entityStartInSegment;
  final int entityEndInSegment;

  @override
  State<EntityEditDialog> createState() => _EntityEditDialogState();
}

class _EntityEditDialogState extends State<EntityEditDialog> {
  late TextEditingController _segmentTextController;
  late TextEditingController _placeholderController;

  @override
  void initState() {
    super.initState();
    _segmentTextController = TextEditingController(text: widget.segmentText);
    _placeholderController = TextEditingController(
      text: widget.entity['placeholder']?.toString() ?? '',
    );

    // Set initial selection to current entity text
    if (widget.entityStartInSegment >= 0 &&
        widget.entityEndInSegment <= widget.segmentText.length &&
        widget.entityStartInSegment < widget.entityEndInSegment) {
      _segmentTextController.selection = TextSelection(
        baseOffset: widget.entityStartInSegment,
        extentOffset: widget.entityEndInSegment,
      );
    }
  }

  @override
  void dispose() {
    _segmentTextController.dispose();
    _placeholderController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Row(
          children: <Widget>[
            Icon(Icons.edit_outlined, size: 24),
            SizedBox(width: 8),
            Text('Edit Entity'),
          ],
        ),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(
                'Segment ${widget.segmentIndex + 1}:',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: Theme.of(context).dividerColor,
                  ),
                ),
                child: SelectableText.rich(
                  TextSpan(
                    text: widget.segmentText,
                    style: TextStyle(
                      fontSize: 13,
                      fontFamily: 'monospace',
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  selectionColor:
                      Theme.of(context).colorScheme.primary.withOpacity(0.3),
                  onSelectionChanged:
                      (TextSelection selection, SelectionChangedCause? cause) {
                    if (selection.isValid &&
                        selection.start >= 0 &&
                        selection.end <= widget.segmentText.length) {
                      final String selectedText = widget.segmentText.substring(
                        selection.start,
                        selection.end,
                      );
                      _segmentTextController.text = selectedText;
                      _segmentTextController.selection = TextSelection(
                        baseOffset: 0,
                        extentOffset: selectedText.length,
                      );
                      setState(() {});
                    }
                  },
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Selected Text (editable):',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: Theme.of(context).dividerColor,
                  ),
                ),
                child: TextField(
                  controller: _segmentTextController,
                  decoration: const InputDecoration(
                    hintText:
                        'Select text in segment above, or edit directly here',
                    border: InputBorder.none,
                    isDense: true,
                  ),
                  style: TextStyle(
                    fontSize: 13,
                    fontFamily: 'monospace',
                    color: Theme.of(context).colorScheme.onSurface,
                  ),
                  maxLines: 3,
                  onChanged: (String value) {
                    setState(() {});
                  },
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Tip: Select text in the segment above (it will appear in the text field), or edit directly in the text field',
                style: TextStyle(
                  fontSize: 11,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  fontStyle: FontStyle.italic,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Placeholder:',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _placeholderController,
                decoration: InputDecoration(
                  hintText: 'Enter placeholder text',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(4),
                  ),
                  isDense: true,
                ),
                style: TextStyle(
                  fontSize: 13,
                  fontFamily: 'monospace',
                  color: Colors.orange.shade700,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => _handleSave(context),
            child: const Text('Save'),
          ),
        ],
      );

  void _handleSave(BuildContext context) {
    final selectedText = _segmentTextController.text.trim();

    if (selectedText.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Please select or enter text'),
            duration: Duration(seconds: 2),
          ),
        );
      }
      return;
    }

    final newPlaceholder = _placeholderController.text.trim();
    if (newPlaceholder.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Placeholder cannot be empty'),
            duration: Duration(seconds: 2),
          ),
        );
      }
      return;
    }

    // Find the selected text in the segment
    // First, try to find exact match
    int newEntityStartInSegment = widget.segmentText.indexOf(selectedText);
    int newEntityEndInSegment = newEntityStartInSegment + selectedText.length;

    // If not found, try to find the text in the segment (case-insensitive)
    if (newEntityStartInSegment == -1) {
      final lowerSelectedText = selectedText.toLowerCase();
      final lowerSegmentText = widget.segmentText.toLowerCase();
      final index = lowerSegmentText.indexOf(lowerSelectedText);
      if (index != -1) {
        newEntityStartInSegment = index;
        newEntityEndInSegment = index + selectedText.length;
      } else {
        // Text not found in segment, use current entity position as fallback
        if (widget.entityStartInSegment >= 0 &&
            widget.entityEndInSegment <= widget.segmentText.length) {
          newEntityStartInSegment = widget.entityStartInSegment;
          newEntityEndInSegment = widget.entityEndInSegment;
        } else {
          // No valid position, show error
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  'Text "$selectedText" not found in segment. Please select text from the segment above.',
                ),
                duration: const Duration(seconds: 3),
              ),
            );
          }
          return;
        }
      }
    }

    // Calculate new entity positions in full text
    final newEntityStart =
        widget.segmentStartInFullText + newEntityStartInSegment;
    final newEntityEnd = widget.segmentStartInFullText + newEntityEndInSegment;

    // Return result to caller
    Navigator.of(context).pop(<String, Object>{
      'text': selectedText,
      'placeholder': newPlaceholder,
      'start': newEntityStart,
      'end': newEntityEnd,
    });
  }
}

/// Helper class for updating anonymized text based on entities
class AnonymizedTextUpdater {
  /// Update anonymized text based on current entities
  /// Handles multiple entities in the same segment correctly by sorting and replacing from end to start
  static String updateAnonymizedText({
    required String originalText,
    required List<dynamic> entities,
  }) {
    // Build a map of entity text -> placeholder for text-based matching (查漏)
    // Ensures all occurrences of sensitive words are replaced, even if not explicitly listed as entities
    final entityTextToPlaceholder = <String, String>{};
    for (final entity in entities) {
      final entityMap = entity as Map<String, dynamic>? ?? <String, dynamic>{};
      final text = entityMap['text']?.toString() ?? '';
      final placeholder = entityMap['placeholder']?.toString() ?? '';
      if (text.isNotEmpty && placeholder.isNotEmpty) {
        // First placeholder wins for a given text to maintain consistency
        entityTextToPlaceholder.putIfAbsent(text, () => placeholder);
      }
    }

    // Debug: log the mapping
    debugPrint('[updateAnonymizedText] Entity text to placeholder mapping:');
    for (final entry in entityTextToPlaceholder.entries) {
      debugPrint('[updateAnonymizedText]   "${entry.key}" -> "${entry.value}"');
    }

    // Collect all replacements by scanning the full original text
    final replacements = <Map<String, dynamic>>[];
    for (final entry in entityTextToPlaceholder.entries) {
      final text = entry.key;
      final placeholder = entry.value;
      int searchStart = 0;
      int count = 0;
      while (true) {
        final idx = originalText.indexOf(text, searchStart);
        if (idx == -1) break;
        count++;
        replacements.add(<String, dynamic>{
          'start': idx,
          'end': idx + text.length,
          'length': text.length,
          'text': text,
          'placeholder': placeholder,
        });
        searchStart = idx + 1;
      }
      debugPrint(
        '[updateAnonymizedText] Found $count occurrence(s) of "$text" -> "$placeholder"',
      );
    }

    debugPrint(
      '[updateAnonymizedText] Total replacements to apply: ${replacements.length}',
    );

    // Sort: longer first, then by position descending, to avoid substring collisions and index shifts
    replacements.sort((a, b) {
      final lenA = (a['length'] as int?) ?? 0;
      final lenB = (b['length'] as int?) ?? 0;
      if (lenA != lenB) return lenB.compareTo(lenA);
      final startA = (a['start'] as int?) ?? 0;
      final startB = (b['start'] as int?) ?? 0;
      return startB.compareTo(startA);
    });

    // Apply replacements from end to start
    String result = originalText;
    int successfulReplacements = 0;
    int skippedReplacements = 0;
    for (final r in replacements) {
      final start = (r['start'] as int?) ?? 0;
      final end = (r['end'] as int?) ?? result.length;
      final text = r['text']?.toString() ?? '';
      final placeholder = r['placeholder']?.toString() ?? '';

      if (start < 0 ||
          end > result.length ||
          start >= end ||
          placeholder.isEmpty) {
        skippedReplacements++;
        debugPrint(
          '[updateAnonymizedText] ⚠ Skipped replacement: invalid bounds (start=$start, end=$end, resultLength=${result.length})',
        );
        continue;
      }

      // Verify content matches before replacing
      final currentText = result.substring(start, end);
      if (currentText == text) {
        result =
            result.substring(0, start) + placeholder + result.substring(end);
        successfulReplacements++;
      } else {
        skippedReplacements++;
        debugPrint(
          '[updateAnonymizedText] ⚠ Skipped replacement: text mismatch at position $start-$end',
        );
        debugPrint('[updateAnonymizedText]   Expected: "$text"');
        debugPrint('[updateAnonymizedText]   Found: "$currentText"');
      }
    }

    debugPrint(
      '[updateAnonymizedText] Replacement summary: $successfulReplacements successful, $skippedReplacements skipped',
    );
    debugPrint(
      '[updateAnonymizedText] Result length: ${result.length} (original: ${originalText.length})',
    );

    return result;
  }

  /// Update anonymized segments based on current entities
  /// Only replaces positions that are explicitly recorded in entities list
  /// Handles multiple entities in the same segment correctly
  static List<String> updateAnonymizedSegments({
    required List<String> originalSegments,
    required List<dynamic> entities,
    required List<int> segmentBoundaries,
  }) {
    if (originalSegments.isEmpty) return <String>[];

    // Filter and validate entities first
    final validEntities = <Map<String, dynamic>>[];
    for (final entity in entities) {
      final entityMap = entity as Map<String, dynamic>? ?? <String, dynamic>{};
      final start = (entityMap['start'] as int?) ?? 0;
      final end = (entityMap['end'] as int?) ?? 0;
      final placeholder = entityMap['placeholder']?.toString() ?? '';
      final segmentIndex = entityMap['segmentIndex'] as int?;

      // Validate entity
      if (start >= 0 &&
          end > start &&
          placeholder.isNotEmpty &&
          segmentIndex != null &&
          segmentIndex >= 0 &&
          segmentIndex < originalSegments.length) {
        validEntities.add(entityMap);
      }
    }

    // Group entities by segment index
    final entitiesBySegment = <int, List<Map<String, dynamic>>>{};
    for (final entity in validEntities) {
      final segmentIndex = (entity['segmentIndex'] as int?) ?? -1;
      if (segmentIndex >= 0 && segmentIndex < originalSegments.length) {
        entitiesBySegment
            .putIfAbsent(segmentIndex, () => <Map<String, dynamic>>[])
            .add(entity);
      }
    }

    // Generate anonymized segments by replacing entities in each segment
    final anonymizedSegments = <String>[];
    for (int i = 0; i < originalSegments.length; i++) {
      final segmentText = originalSegments[i];

      // Get entities for this segment
      final segmentEntities = entitiesBySegment[i] ?? <Map<String, dynamic>>[];

      if (segmentEntities.isEmpty) {
        // No entities in this segment, keep original
        anonymizedSegments.add(segmentText);
        continue;
      }

      // Calculate segment start position in full text
      int segmentStartInFullText = 0;
      if (i < segmentBoundaries.length) {
        segmentStartInFullText = segmentBoundaries[i];
      }

      // Convert entity positions from full text to segment-relative positions
      final segmentReplacements = <Map<String, dynamic>>[];
      for (final entity in segmentEntities) {
        final startInFullText = (entity['start'] as int?) ?? 0;
        final endInFullText = (entity['end'] as int?) ?? 0;
        final placeholder = entity['placeholder']?.toString() ?? '';

        // Convert to segment-relative positions
        final startInSegment = startInFullText - segmentStartInFullText;
        final endInSegment = endInFullText - segmentStartInFullText;
        final length = endInSegment - startInSegment;

        // Validate positions are within segment bounds
        if (startInSegment >= 0 &&
            endInSegment <= segmentText.length &&
            startInSegment < endInSegment &&
            placeholder.isNotEmpty) {
          segmentReplacements.add(<String, dynamic>{
            'start': startInSegment,
            'end': endInSegment,
            'placeholder': placeholder,
            'length': length,
          });
        }
      }

      // Sort replacements by length (descending) first, then by position (descending)
      // This ensures longer entities are replaced first, avoiding substring replacement issues
      segmentReplacements.sort((a, b) {
        final lengthA = (a['length'] as int?) ?? 0;
        final lengthB = (b['length'] as int?) ?? 0;
        if (lengthA != lengthB) {
          return lengthB.compareTo(lengthA); // Longer first
        }
        // If same length, sort by position (descending) to replace from end to start
        final startA = (a['start'] as int?) ?? 0;
        final startB = (b['start'] as int?) ?? 0;
        return startB.compareTo(startA);
      });

      // Apply replacements from end to start
      String anonymizedSegment = segmentText;
      for (final replacement in segmentReplacements) {
        final start = (replacement['start'] as int?) ?? 0;
        final end = (replacement['end'] as int?) ?? anonymizedSegment.length;
        final placeholder = replacement['placeholder']?.toString() ?? '';

        if (start >= 0 &&
            end > start &&
            end <= anonymizedSegment.length &&
            placeholder.isNotEmpty) {
          anonymizedSegment = anonymizedSegment.substring(0, start) +
              placeholder +
              anonymizedSegment.substring(end);
        }
      }

      anonymizedSegments.add(anonymizedSegment);
    }

    return anonymizedSegments;
  }
}
