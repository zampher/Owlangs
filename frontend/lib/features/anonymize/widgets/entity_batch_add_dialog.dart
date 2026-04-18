// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../utils/entity_group_helper.dart';

/// Dialog for batch adding missing placeholders
class EntityBatchAddDialog extends StatefulWidget {
  const EntityBatchAddDialog({
    required this.placeholder,
    required this.positions,
    required this.anonymizedText,
    required this.originalText,
    required this.segmentBoundaries,
    required this.originalSegments,
    required this.anonymizeMode,
    super.key,
    this.customPlaceholder,
  });
  final String placeholder;
  final List<PlaceholderPosition> positions;
  final String anonymizedText;
  final String originalText;
  final List<int> segmentBoundaries;
  final List<String> originalSegments;
  final String anonymizeMode;
  final String? customPlaceholder;

  @override
  State<EntityBatchAddDialog> createState() => _EntityBatchAddDialogState();
}

class _EntityBatchAddDialogState extends State<EntityBatchAddDialog> {
  final Map<int, bool> _selectedPositions = <int, bool>{};
  String _selectedType = 'UNKNOWN';
  final Map<int, String> _manualTexts =
      <int, String>{}; // Position index -> manual text

  @override
  void initState() {
    super.initState();
    // Extract type from placeholder
    final type =
        EntityGroupHelper.extractTypeFromPlaceholder(widget.placeholder);
    if (type != null) {
      _selectedType = type;
    }
    // Select all by default
    for (int i = 0; i < widget.positions.length; i++) {
      _selectedPositions[i] = true;
    }
  }

  int? _findSegmentIndex(int position) {
    if (widget.segmentBoundaries.isEmpty) return null;

    int left = 0;
    int right = widget.segmentBoundaries.length - 2;

    while (left <= right) {
      final mid = (left + right) ~/ 2;
      final segmentStart = widget.segmentBoundaries[mid];
      final segmentEnd = widget.segmentBoundaries[mid + 1];

      if (position >= segmentStart && position < segmentEnd) {
        return mid;
      } else if (position < segmentStart) {
        right = mid - 1;
      } else {
        left = mid + 1;
      }
    }

    // Fallback: if position is at or after the last boundary
    if (widget.segmentBoundaries.length >= 2) {
      final lastBoundary =
          widget.segmentBoundaries[widget.segmentBoundaries.length - 2];
      if (position >= lastBoundary) {
        return widget.segmentBoundaries.length - 2;
      }
    }

    return null;
  }

  String? _extractTextFromContext(int positionIndex) {
    final position = widget.positions[positionIndex];
    final context = position.context;

    // Try to find text before and after placeholder
    final placeholderIndex = context.indexOf(widget.placeholder);
    if (placeholderIndex == -1) return null;

    // Extract surrounding text (simplified - user can edit)
    final before = context.substring(0, placeholderIndex).trim();
    final after =
        context.substring(placeholderIndex + widget.placeholder.length).trim();

    // Try to extract a reasonable text (this is a heuristic)
    if (before.length > 5 && after.length > 5) {
      return '${before.substring(before.length - 5)}...${after.substring(0, 5)}';
    }

    return null;
  }

  @override
  Widget build(BuildContext context) {
    final selectedCount = _selectedPositions.values.where((v) => v).length;
    final entityTypes = <Map<String, String>>[
      <String, String>{'code': 'UNKNOWN', 'name': 'Unknown'},
      <String, String>{'code': 'PERSON', 'name': 'Person'},
      <String, String>{'code': 'EMAIL_ADDRESS', 'name': 'Email Address'},
      <String, String>{'code': 'PHONE_NUMBER', 'name': 'Phone Number'},
      <String, String>{'code': 'LOCATION', 'name': 'Location'},
      <String, String>{'code': 'ORGANIZATION', 'name': 'Organization'},
      <String, String>{'code': 'DATE', 'name': 'Date'},
      <String, String>{'code': 'TIME', 'name': 'Time'},
      <String, String>{'code': 'MONEY', 'name': 'Money'},
      <String, String>{'code': 'PERCENT', 'name': 'Percent'},
      <String, String>{'code': 'URL', 'name': 'URL'},
      <String, String>{'code': 'IP_ADDRESS', 'name': 'IP Address'},
      <String, String>{'code': 'CREDIT_CARD', 'name': 'Credit Card'},
      <String, String>{'code': 'SSN', 'name': 'SSN'},
      <String, String>{'code': 'PASSPORT', 'name': 'Passport'},
      <String, String>{'code': 'DRIVER_LICENSE', 'name': 'Driver License'},
      <String, String>{'code': 'BANK_ACCOUNT', 'name': 'Bank Account'},
    ];

    return Dialog(
      child: Container(
        width: 600,
        height: 600,
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  Icons.add_circle_outline,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Add Missing Placeholders: ${widget.placeholder}',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Entity Type selector
            Row(
              children: <Widget>[
                const Text('Entity Type: '),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _selectedType,
                  items: entityTypes
                      .map(
                        (type) => DropdownMenuItem<String>(
                          value: type['code'],
                          child: Text(type['name']!),
                        ),
                      )
                      .toList(),
                  onChanged: (value) {
                    if (value != null) {
                      setState(() {
                        _selectedType = value;
                      });
                    }
                  },
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              'Found $selectedCount occurrence(s):',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: ListView.builder(
                itemCount: widget.positions.length,
                itemBuilder: (context, index) {
                  final position = widget.positions[index];
                  final isSelected = _selectedPositions[index] ?? false;
                  final segmentIndex = _findSegmentIndex(position.index);
                  final autoText = _extractTextFromContext(index);
                  final manualText = _manualTexts[index] ?? autoText ?? '';

                  return Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: CheckboxListTile(
                      value: isSelected,
                      onChanged: (value) {
                        setState(() {
                          _selectedPositions[index] = value ?? false;
                        });
                      },
                      title: Row(
                        children: <Widget>[
                          if (segmentIndex != null) ...<Widget>[
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.blue.shade50,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                '#${segmentIndex + 1}',
                                style: const TextStyle(fontSize: 10),
                              ),
                            ),
                            const SizedBox(width: 8),
                          ],
                          Expanded(
                            child: Text(
                              'Position: ${position.index}',
                              style: const TextStyle(fontSize: 12),
                            ),
                          ),
                        ],
                      ),
                      subtitle: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          const SizedBox(height: 4),
                          Text(
                            'Context: ...${position.context}...',
                            style: TextStyle(
                              fontSize: 11,
                              fontFamily: 'monospace',
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(height: 8),
                          TextField(
                            decoration: const InputDecoration(
                              labelText: 'Original Text (auto-detected)',
                              isDense: true,
                              border: OutlineInputBorder(),
                            ),
                            controller: TextEditingController(text: manualText)
                              ..selection = TextSelection.collapsed(
                                offset: manualText.length,
                              ),
                            onChanged: (value) {
                              _manualTexts[index] = value;
                            },
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: <Widget>[
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: selectedCount > 0
                      ? () {
                          final result = <Map<String, dynamic>>[];
                          for (int i = 0; i < widget.positions.length; i++) {
                            if (_selectedPositions[i] ?? false) {
                              final position = widget.positions[i];
                              final text = _manualTexts[i]?.trim() ??
                                  _extractTextFromContext(i)?.trim() ??
                                  'UNKNOWN_TEXT';
                              final segmentIndex =
                                  _findSegmentIndex(position.index);

                              // Calculate start/end in original text
                              // This is approximate - we need to find the text in original
                              // For now, we'll use the placeholder position as a guide
                              final start = position.index; // Approximate
                              final end = start + text.length;

                              result.add(<String, dynamic>{
                                'text': text,
                                'type': _selectedType,
                                'placeholder': widget.placeholder,
                                'start': start,
                                'end': end,
                                'segmentIndex': segmentIndex,
                                'confidence': 1.0,
                              });
                            }
                          }
                          Navigator.of(context).pop(result);
                        }
                      : null,
                  child: Text('Add Selected ($selectedCount)'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
