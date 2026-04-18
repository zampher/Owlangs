// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:math';
import '../models/entity_group.dart';

/// Helper class for grouping entities and detecting missing placeholders
class EntityGroupHelper {
  /// Group entities by text + type
  static List<EntityGroup> groupEntities(List<dynamic> entities) {
    final Map<String, EntityGroup> groups = <String, EntityGroup>{};

    for (var i = 0; i < entities.length; i++) {
      final Map<String, dynamic> entity =
          entities[i] as Map<String, dynamic>? ?? <String, dynamic>{};
      final String text = entity['text']?.toString() ?? '';
      final String type = entity['type']?.toString() ?? 'UNKNOWN';
      final String placeholder = entity['placeholder']?.toString() ?? '';
      final int? segmentIndex = entity['segmentIndex'] as int?;
      final int start = entity['start'] as int? ?? 0;
      final int end = entity['end'] as int? ?? start;

      final String groupKey = '${text}_$type';

      final EntityOccurrence occurrence = EntityOccurrence(
        index: i,
        entity: entity,
        placeholder: placeholder,
        segmentIndex: segmentIndex,
        start: start,
        end: end,
      );

      if (groups.containsKey(groupKey)) {
        groups[groupKey]!.occurrences.add(occurrence);
      } else {
        groups[groupKey] = EntityGroup(
          text: text,
          type: type,
          primaryPlaceholder: placeholder.isNotEmpty ? placeholder : null,
          occurrences: <EntityOccurrence>[occurrence],
        );
      }
    }

    // Update primary placeholder for each group (use most common)
    for (final EntityGroup group in groups.values) {
      if (group.occurrences.isNotEmpty) {
        final Map<String, int> placeholderCounts = <String, int>{};
        for (final EntityOccurrence occurrence in group.occurrences) {
          placeholderCounts[occurrence.placeholder] =
              (placeholderCounts[occurrence.placeholder] ?? 0) + 1;
        }
        if (placeholderCounts.isNotEmpty) {
          final String mostCommonPlaceholder = placeholderCounts.entries
              .reduce(
                (MapEntry<String, int> a, MapEntry<String, int> b) =>
                    a.value > b.value ? a : b,
              )
              .key;
          group.primaryPlaceholder = mostCommonPlaceholder;
        }
      }
    }

    // Sort groups by text, then by type
    final List<EntityGroup> sortedGroups = groups.values.toList()
      ..sort((EntityGroup a, EntityGroup b) {
        final int textCompare = a.text.compareTo(b.text);
        if (textCompare != 0) return textCompare;
        return a.type.compareTo(b.type);
      });

    // Sort occurrences within each group by segment index, then by start position
    for (final EntityGroup group in sortedGroups) {
      group.occurrences.sort((EntityOccurrence a, EntityOccurrence b) {
        if (a.segmentIndex != null && b.segmentIndex != null) {
          final int segmentCompare = a.segmentIndex!.compareTo(b.segmentIndex!);
          if (segmentCompare != 0) return segmentCompare;
        } else if (a.segmentIndex != null) {
          return -1;
        } else if (b.segmentIndex != null) {
          return 1;
        }
        return a.start.compareTo(b.start);
      });
    }

    return sortedGroups;
  }

  /// Scan for missing placeholders in anonymized text
  static Set<String> scanMissingPlaceholders(
    String anonymizedText,
    List<dynamic> entities,
  ) {
    // Extract all placeholders from anonymized text
    final RegExp placeholderPattern = RegExp(r'\[(\w+)_(\d+)\]');
    final Set<String> foundPlaceholders = <String>{};
    final Iterable<RegExpMatch> matches =
        placeholderPattern.allMatches(anonymizedText);
    for (final RegExpMatch match in matches) {
      foundPlaceholders.add(match.group(0)!); // [TYPE_N]
    }

    // Collect all placeholders from existing entities
    final Set<String> existingPlaceholders = <String>{};
    for (final entity in entities) {
      final Map<String, dynamic> entityMap =
          entity as Map<String, dynamic>? ?? <String, dynamic>{};
      final String placeholder = entityMap['placeholder']?.toString() ?? '';
      if (placeholder.isNotEmpty) {
        existingPlaceholders.add(placeholder);
      }
    }

    // Find missing placeholders
    return foundPlaceholders.difference(existingPlaceholders);
  }

  /// Scan for missing entities based on entitiesExpanded (backend-driven)
  /// Returns a list of missing entity seeds (text + type) that should be added
  static List<Map<String, String>> scanMissingEntitiesFromExpanded(
    List<dynamic> currentEntities,
    List<dynamic>? entitiesExpanded,
  ) {
    if (entitiesExpanded == null || entitiesExpanded.isEmpty) {
      return <Map<String, String>>[];
    }

    // Build a set of current entity keys (text + type)
    final Set<String> currentKeys = <String>{};
    for (final entity in currentEntities) {
      final Map<String, dynamic> entityMap =
          entity as Map<String, dynamic>? ?? <String, dynamic>{};
      final String text = entityMap['text']?.toString() ?? '';
      final String type = entityMap['type']?.toString() ?? 'UNKNOWN';
      if (text.isNotEmpty) {
        currentKeys.add('$text::$type');
      }
    }

    // Build a set of expanded entity keys
    final Set<String> expandedKeys = <String>{};
    final Map<String, Map<String, String>> expandedSeeds =
        <String, Map<String, String>>{};
    for (final entity in entitiesExpanded) {
      final Map<String, dynamic> entityMap =
          entity as Map<String, dynamic>? ?? <String, dynamic>{};
      final String text = entityMap['text']?.toString() ?? '';
      final String type = entityMap['type']?.toString() ?? 'UNKNOWN';
      if (text.isNotEmpty) {
        final String key = '$text::$type';
        if (expandedKeys.add(key)) {
          // First occurrence of this text+type, store as seed
          expandedSeeds[key] = <String, String>{'text': text, 'type': type};
        }
      }
    }

    // Find missing seeds
    final List<Map<String, String>> missingSeeds = <Map<String, String>>[];
    for (final String key in expandedKeys) {
      if (!currentKeys.contains(key)) {
        final Map<String, String>? seed = expandedSeeds[key];
        if (seed != null) {
          missingSeeds.add(seed);
        }
      }
    }

    return missingSeeds;
  }

  /// Extract entity type from placeholder
  /// Example: [PERSON_2] -> PERSON
  static String? extractTypeFromPlaceholder(String placeholder) {
    final RegExpMatch? match = RegExp(r'\[(\w+)_\d+\]').firstMatch(placeholder);
    return match?.group(1);
  }

  /// Find all positions of a placeholder in text
  static List<PlaceholderPosition> findPlaceholderPositions(
    String text,
    String placeholder,
  ) {
    final List<PlaceholderPosition> positions = <PlaceholderPosition>[];
    var searchStart = 0;

    while (true) {
      final int index = text.indexOf(placeholder, searchStart);
      if (index == -1) break;

      // Extract context around the placeholder
      final int contextStart = max(0, index - 30);
      final int contextEnd = min(text.length, index + placeholder.length + 30);
      final String context = text.substring(contextStart, contextEnd);

      positions.add(
        PlaceholderPosition(
          index: index,
          placeholder: placeholder,
          context: context,
          contextStart: contextStart,
        ),
      );

      searchStart = index + 1;
    }

    return positions;
  }

  /// Check if edit requires regrouping
  static bool needsRegroup(
    Map<String, dynamic> oldEntity,
    Map<String, dynamic> newEntity,
  ) {
    final String oldText = oldEntity['text']?.toString() ?? '';
    final String oldType = oldEntity['type']?.toString() ?? 'UNKNOWN';
    final String newText = newEntity['text']?.toString() ?? '';
    final String newType = newEntity['type']?.toString() ?? 'UNKNOWN';

    final String oldKey = '${oldText}_$oldType';
    final String newKey = '${newText}_$newType';

    return oldKey != newKey;
  }

  /// Find occurrence indices for a group
  static List<int> findOccurrenceIndices(
    List<dynamic> entities,
    String groupKey,
  ) {
    final List<int> indices = <int>[];
    for (var i = 0; i < entities.length; i++) {
      final Map<String, dynamic> entity =
          entities[i] as Map<String, dynamic>? ?? <String, dynamic>{};
      final String text = entity['text']?.toString() ?? '';
      final String type = entity['type']?.toString() ?? 'UNKNOWN';
      if ('${text}_$type' == groupKey) {
        indices.add(i);
      }
    }
    return indices;
  }
}

/// Model for placeholder position in text
class PlaceholderPosition {
  // Start position of context

  PlaceholderPosition({
    required this.index,
    required this.placeholder,
    required this.context,
    required this.contextStart,
  });
  final int index; // Position in text
  final String placeholder; // Placeholder text
  final String context; // Context around placeholder
  final int contextStart;
}
