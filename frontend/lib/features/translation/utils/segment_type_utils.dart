// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import '../models/exclusion_reason.dart';

/// Utilities for classifying segments into exclusion/filter categories.
///
/// Note:
/// - This is used by the Translate phase filter and counts.
/// - It intentionally classifies by detected type, not by excluded state.
String? segmentFilterKeyFromMetadata(Map<String, dynamic> metadata) {
  final String? blockType = metadata['block_type'] as String?;
  final bool isTableBody = metadata['is_table_body'] as bool? ?? false;
  final bool isImage = metadata['is_image'] as bool? ?? false;

  if (isImage) {
    return ExclusionReason.image.value;
  }

  if (blockType == 'ref_text') {
    return ExclusionReason.reference.value;
  }

  if (blockType == 'header' || blockType == 'page_header') {
    return 'structural_header';
  }

  if (blockType == 'footer' || blockType == 'page_footer') {
    return 'structural_footer';
  }

  if (blockType == 'table_body' || isTableBody) {
    return ExclusionReason.table.value;
  }

  if (blockType == 'interline_equation') {
    return ExclusionReason.formula.value;
  }

  final String? detectedReason =
      metadata['detected_exclusion_reason'] as String?;
  final String? exclusionReason = metadata['exclusion_reason'] as String?;
  final String? reasonToUse = detectedReason ?? exclusionReason;

  if (reasonToUse == null) {
    return null;
  }

  // Merge unknown into user_selected for UI consistency.
  if (reasonToUse == ExclusionReason.unknown.value) {
    return ExclusionReason.userSelected.value;
  }

  return reasonToUse;
}

/// Build counts by type for ALL segments (not just excluded ones).
///
/// This ensures Translate phase FilterChips remain usable even for
/// default-not-excluded categories (e.g. table, structural, language_match).
Map<String, int> buildSegmentTypeCounts({
  required Map<int, Map<String, dynamic>> allSegmentsMetadata,
  required int totalSegmentsCount,
}) {
  final Map<String, int> counts = <String, int>{};

  for (int i = 0; i < totalSegmentsCount; i++) {
    final Map<String, dynamic>? metadata = allSegmentsMetadata[i];
    if (metadata == null) continue;
    final String? key = segmentFilterKeyFromMetadata(metadata);
    if (key == null) continue;
    counts[key] = (counts[key] ?? 0) + 1;
  }

  // Ensure all exclusion reason types are present with 0 count.
  for (final reason in ExclusionReason.values) {
    if (reason == ExclusionReason.unknown) {
      continue; // Unknown is merged into user_selected.
    }
    counts.putIfAbsent(reason.value, () => 0);
  }

  // Structural headers/footers are represented with specialized keys.
  counts.putIfAbsent('structural_header', () => 0);
  counts.putIfAbsent('structural_footer', () => 0);

  return counts;
}
