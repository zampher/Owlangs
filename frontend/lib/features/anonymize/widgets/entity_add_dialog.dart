// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// Dialog for adding a new entity
/// Shows the segment or full text and allows user to select text range
class EntityAddDialog extends StatefulWidget {
  // Prefill type (e.g., when adding from a group)

  const EntityAddDialog({
    required this.segmentText,
    required this.segmentIndex,
    required this.segmentStartInFullText,
    required this.originalText,
    required this.anonymizeMode,
    required this.existingEntities,
    super.key,
    this.customPlaceholder,
    this.prefillText,
    this.prefillType,
  });
  final String segmentText;
  final int segmentIndex;
  final int segmentStartInFullText;
  final String originalText; // Full original text for fallback
  final String anonymizeMode; // placeholder/mask/type/custom
  final String? customPlaceholder; // Custom placeholder when mode is custom
  final List<dynamic>
      existingEntities; // For duplicate detection and placeholder reuse
  final String? prefillText; // Prefill text (e.g., when adding from a group)
  final String? prefillType;

  @override
  State<EntityAddDialog> createState() => _EntityAddDialogState();
}

class _EntityAddDialogState extends State<EntityAddDialog> {
  late TextEditingController _segmentTextController;
  late TextEditingController _placeholderController;
  String _selectedEntityType = 'UNKNOWN';

  // Available entity types (from anonymization_quick_settings.dart)
  static const List<Map<String, String>> entityTypes = <Map<String, String>>[
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

  @override
  void initState() {
    super.initState();
    // Prefill text if provided
    _segmentTextController = TextEditingController(
      text: widget.prefillText ?? '',
    );
    _placeholderController = TextEditingController();
    // Prefill type if provided
    if (widget.prefillType != null) {
      _selectedEntityType = widget.prefillType!;
      // Generate placeholder if text is also prefilled
      if (widget.prefillText != null && widget.prefillText!.isNotEmpty) {
        final placeholder =
            _generatePlaceholder(widget.prefillText!, widget.prefillType!);
        _placeholderController.text = placeholder;
      }
    }
  }

  @override
  void dispose() {
    _segmentTextController.dispose();
    _placeholderController.dispose();
    super.dispose();
  }

  /// Generate placeholder based on mode and entity type
  String _generatePlaceholder(String text, String type) {
    switch (widget.anonymizeMode) {
      case 'placeholder':
        // Check if same text already exists, reuse its placeholder
        for (final entity in widget.existingEntities) {
          final entityMap =
              entity as Map<String, dynamic>? ?? <String, dynamic>{};
          final entityText = entityMap['text']?.toString() ?? '';
          if (entityText == text) {
            final existingPlaceholder =
                entityMap['placeholder']?.toString() ?? '';
            if (existingPlaceholder.isNotEmpty) {
              return existingPlaceholder;
            }
          }
        }
        // Find the maximum counter for this type from existing placeholders
        int maxCounter = 0;
        // Escape special regex characters in type
        final escapedType = RegExp.escape(type);
        final placeholderPattern = RegExp(r'\[' + escapedType + r'_(\d+)\]');
        for (final entity in widget.existingEntities) {
          final entityMap =
              entity as Map<String, dynamic>? ?? <String, dynamic>{};
          final entityType = entityMap['type']?.toString() ?? 'UNKNOWN';
          if (entityType == type) {
            final placeholder = entityMap['placeholder']?.toString() ?? '';
            if (placeholder.isNotEmpty) {
              final match = placeholderPattern.firstMatch(placeholder);
              if (match != null) {
                final counter = int.tryParse(match.group(1) ?? '0') ?? 0;
                if (counter > maxCounter) {
                  maxCounter = counter;
                }
              }
            }
          }
        }
        // Return next counter (maxCounter + 1)
        return '[${type}_${maxCounter + 1}]';
      case 'mask':
        return '*' * text.length;
      case 'type':
        return '[$type]';
      case 'custom':
        return widget.customPlaceholder ?? '[REDACTED]';
      default:
        // Fallback to placeholder mode
        // Find the maximum counter for this type from existing placeholders
        int maxCounter = 0;
        // Escape special regex characters in type
        final escapedType = RegExp.escape(type);
        final placeholderPattern = RegExp(r'\[' + escapedType + r'_(\d+)\]');
        for (final entity in widget.existingEntities) {
          final entityMap =
              entity as Map<String, dynamic>? ?? <String, dynamic>{};
          final entityType = entityMap['type']?.toString() ?? 'UNKNOWN';
          if (entityType == type) {
            final placeholder = entityMap['placeholder']?.toString() ?? '';
            if (placeholder.isNotEmpty) {
              final match = placeholderPattern.firstMatch(placeholder);
              if (match != null) {
                final counter = int.tryParse(match.group(1) ?? '0') ?? 0;
                if (counter > maxCounter) {
                  maxCounter = counter;
                }
              }
            }
          }
        }
        // Return next counter (maxCounter + 1)
        return '[${type}_${maxCounter + 1}]';
    }
  }

  /// Check for duplicate entities
  bool _checkDuplicate(String text) {
    for (final entity in widget.existingEntities) {
      final entityMap = entity as Map<String, dynamic>? ?? <String, dynamic>{};
      final entityText = entityMap['text']?.toString() ?? '';
      if (entityText == text) {
        return true;
      }
    }
    return false;
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Row(
          children: <Widget>[
            Icon(Icons.add, size: 24),
            SizedBox(width: 8),
            Text('Add Entity'),
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
                      setState(() {
                        final String selectedText = widget.segmentText
                            .substring(selection.start, selection.end);
                        _segmentTextController.text = selectedText;
                        _segmentTextController.selection = TextSelection(
                          baseOffset: 0,
                          extentOffset: selectedText.length,
                        );

                        // Auto-generate placeholder when text is selected
                        if (selectedText.isNotEmpty) {
                          final String placeholder = _generatePlaceholder(
                            selectedText,
                            _selectedEntityType,
                          );
                          _placeholderController.text = placeholder;
                        }
                      });
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
                    // Auto-generate placeholder when text changes
                    if (value.isNotEmpty) {
                      final String placeholder =
                          _generatePlaceholder(value, _selectedEntityType);
                      _placeholderController.text = placeholder;
                    }
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
                'Entity Type:',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _selectedEntityType,
                decoration: InputDecoration(
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(4),
                  ),
                  isDense: true,
                ),
                items: entityTypes
                    .map(
                      (Map<String, String> type) => DropdownMenuItem<String>(
                        value: type['code'],
                        child: Text(type['name']!),
                      ),
                    )
                    .toList(),
                onChanged: (String? value) {
                  if (value != null) {
                    setState(() {
                      _selectedEntityType = value;
                      // Regenerate placeholder when type changes
                      final String text = _segmentTextController.text.trim();
                      // Always regenerate placeholder when type changes, even if text is empty
                      // Use empty string as text if no text is entered yet
                      final String placeholder = _generatePlaceholder(
                        text.isNotEmpty ? text : '',
                        value,
                      );
                      _placeholderController.text = placeholder;
                    });
                  }
                },
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
            onPressed: () => _handleAdd(context),
            child: const Text('Add'),
          ),
        ],
      );

  void _handleAdd(BuildContext context) {
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

    final placeholder = _placeholderController.text.trim();
    if (placeholder.isEmpty) {
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

    // Check for duplicate
    final isDuplicate = _checkDuplicate(selectedText);
    if (isDuplicate) {
      // Show confirmation dialog
      showDialog(
        context: context,
        builder: (BuildContext dialogContext) => AlertDialog(
          title: const Text('Duplicate Entity'),
          content: Text(
            'An entity with the text "$selectedText" already exists. Do you want to add it anyway?',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
                _doAdd(context, selectedText, placeholder);
              },
              child: const Text('Add Anyway'),
            ),
          ],
        ),
      );
      return;
    }

    _doAdd(context, selectedText, placeholder);
  }

  void _doAdd(BuildContext context, String selectedText, String placeholder) {
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
        // Text not found in segment, try to find in full text
        final fullTextIndex = widget.originalText.indexOf(selectedText);
        if (fullTextIndex != -1) {
          // Calculate position relative to segment
          newEntityStartInSegment =
              fullTextIndex - widget.segmentStartInFullText;
          newEntityEndInSegment = newEntityStartInSegment + selectedText.length;

          // Clamp to segment bounds
          if (newEntityStartInSegment < 0) newEntityStartInSegment = 0;
          if (newEntityEndInSegment > widget.segmentText.length) {
            newEntityEndInSegment = widget.segmentText.length;
          }
        } else {
          // No valid position, show error
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  'Text "$selectedText" not found in segment or original text. Please select text from the segment above.',
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
      'placeholder': placeholder,
      'start': newEntityStart,
      'end': newEntityEnd,
      'type': _selectedEntityType,
      'confidence': 1.0,
    });
  }
}
