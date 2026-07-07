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

  if (blockType == 'header') {
    return 'structural_header';
  }

  if (blockType == 'footer') {
    return 'structural_footer';
  }

  if (blockType == 'table_body' || isTableBody) {
    return ExclusionReason.table.value;
  }

  if (blockType == 'chart_body') {
    return ExclusionReason.chart.value;
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

/// Classification fields copied from a translation-segments API item.
Map<String, dynamic> segmentClassificationFieldsFromApi(
  Map<dynamic, dynamic> segment,
) {
  final dynamic segInfoRaw = segment['segment_info'];
  final Map<String, dynamic>? segInfo = segInfoRaw is Map
      ? Map<String, dynamic>.from(segInfoRaw)
      : null;

  String? blockType = segment['block_type'] as String?;
  blockType ??= segInfo?['block_type'] as String?;

  final bool isTableBody = segment['is_table_body'] as bool? ??
      segInfo?['is_table_body'] as bool? ??
      false;
  final String? chunkType = segment['chunk_type'] as String? ??
      segInfo?['chunk_type'] as String?;

  final dynamic latexFlagsRaw =
      segment['latex_flags'] ?? segInfo?['latex_flags'];

  return <String, dynamic>{
    if (blockType != null && blockType.isNotEmpty) 'block_type': blockType,
    if (isTableBody) 'is_table_body': true,
    if (chunkType != null && chunkType.isNotEmpty) 'chunk_type': chunkType,
    if (latexFlagsRaw is Map)
      'latex_flags': Map<String, dynamic>.from(latexFlagsRaw),
  };
}

/// Default PDF table grid stroke width (pt).
const double kPdfDefaultTableStrokePt = 0.5;

/// Preset table grid stroke widths (pt) in PDF revision UI.
const List<double> kPdfTableStrokeOptionsPt = <double>[0, 0.5, 1.0, 1.5];

/// Default minimum bbox height/width ratio for auto sideways text rotation.
const double kDefaultAutoRotationAspectRatio = 20.0;

/// Default rotation angle (degrees) for auto sideways text rotation.
const int kDefaultAutoRotationDegrees = 270;

/// Selectable PDF overlay rotation angles (degrees, clockwise).
const List<int> kPdfRotationOptionsDegrees = <int>[0, 90, 180, 270];

/// Whether [text] looks like a markdown pipe table (header + at least one row).
bool isMarkdownTableText(String? text) {
  if (text == null || text.trim().isEmpty) {
    return false;
  }
  final List<String> lines = text
      .split('\n')
      .map((String line) => line.trim())
      .where((String line) => line.isNotEmpty)
      .toList();
  if (lines.length < 2) {
    return false;
  }
  int tableLineCount = 0;
  for (final String line in lines) {
    if (line.startsWith('|') && line.endsWith('|')) {
      tableLineCount++;
    }
  }
  return tableLineCount >= 2;
}

/// Whether [metadata] describes a PDF table segment (table body overlay).
bool isPdfTableSegment(Map<String, dynamic> metadata) {
  final String? blockType = metadata['block_type'] as String?;
  final bool isTableBody = metadata['is_table_body'] as bool? ?? false;
  if (isTableBody ||
      blockType == 'table' ||
      blockType == 'table_body') {
    return true;
  }

  final String? chunkType = metadata['chunk_type'] as String?;
  if (chunkType == 'table_body') {
    return true;
  }

  final String? detectedReason =
      metadata['detected_exclusion_reason'] as String?;
  final String? exclusionReason = metadata['exclusion_reason'] as String?;
  if (detectedReason == ExclusionReason.table.value ||
      exclusionReason == ExclusionReason.table.value) {
    return true;
  }

  final String targetText = metadata['target_text'] as String? ?? '';
  final String sourceText = metadata['source_text'] as String? ?? '';
  return isMarkdownTableText(targetText) || isMarkdownTableText(sourceText);
}

double readPdfTableStrokePt(Map<String, dynamic> metadata) {
  if (!metadata.containsKey('table_stroke_pt')) {
    return kPdfDefaultTableStrokePt;
  }
  final dynamic raw = metadata['table_stroke_pt'];
  if (raw is num) {
    return raw.toDouble();
  }
  if (raw is String) {
    return double.tryParse(raw) ?? kPdfDefaultTableStrokePt;
  }
  return kPdfDefaultTableStrokePt;
}

/// Normalize stroke width to one decimal place for option matching.
double normalizePdfTableStrokePt(double strokePt) {
  return (strokePt * 10).roundToDouble() / 10.0;
}

/// Whether [strokePt] matches a selectable table stroke option.
bool isPdfTableStrokeOptionSelected(double current, double option) {
  return normalizePdfTableStrokePt(current) == option;
}

/// Format stroke width for chip/menu labels.
String formatPdfTableStrokePtLabel(double strokePt) {
  final double normalized = normalizePdfTableStrokePt(strokePt);
  if (normalized <= 0) {
    return '0';
  }
  return normalized.truncateToDouble() == normalized
      ? normalized.toStringAsFixed(0)
      : normalized.toStringAsFixed(1);
}

/// Whether [metadata] matches any selected type filter in [selectedFilters].
///
/// Classifies by detected segment type (see [segmentFilterKeyFromMetadata]),
/// not by whether the segment is currently excluded.
bool matchesSegmentTypeFilter(
  Map<String, dynamic> metadata,
  Set<String> selectedFilters,
) {
  if (selectedFilters.isEmpty) {
    return true;
  }
  final String? filterKey = segmentFilterKeyFromMetadata(metadata);
  return filterKey != null && selectedFilters.contains(filterKey);
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
