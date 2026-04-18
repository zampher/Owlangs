// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

/// Model for grouping entities by text and type
class EntityGroup {
  // Whether this is a missing placeholder (only placeholder, no original text)

  EntityGroup({
    required this.text,
    required this.type,
    required this.occurrences,
    this.primaryPlaceholder,
    this.isMissing = false,
  });
  final String text; // Sensitive word text
  final String type; // Entity type
  String? primaryPlaceholder; // Primary placeholder used (first or most common)
  final List<EntityOccurrence> occurrences; // All occurrence positions
  final bool isMissing;

  /// Get group key for identification
  String get groupKey => '${text}_$type';

  /// Get display name
  String get displayName => text.isEmpty ? '(Empty)' : text;

  /// Get occurrence count
  int get occurrenceCount => occurrences.length;
}

/// Model for a single entity occurrence
class EntityOccurrence {
  // End position

  EntityOccurrence({
    required this.index,
    required this.entity,
    required this.placeholder,
    required this.start,
    required this.end,
    this.segmentIndex,
  });
  final int index; // Index in the original entities list
  final Map<String, dynamic> entity; // Original entity data
  final String placeholder; // Placeholder used for this occurrence
  final int? segmentIndex; // Segment index
  final int start; // Start position
  final int end;

  /// Get entity text
  String get text => entity['text']?.toString() ?? '';

  /// Get entity type
  String get type => entity['type']?.toString() ?? 'UNKNOWN';

  /// Get 1-based segment index for display (consistent with preview)
  /// Returns null if segmentIndex is null, otherwise returns segmentIndex + 1
  int? get displaySegmentIndex =>
      segmentIndex != null ? segmentIndex! + 1 : null;

  /// Get formatted segment index string for display (e.g., "#1", "#2")
  /// Returns "N/A" if segmentIndex is null
  String get displaySegmentIndexString =>
      segmentIndex != null ? '#${segmentIndex! + 1}' : 'N/A';
}
