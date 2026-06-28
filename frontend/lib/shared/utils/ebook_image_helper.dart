// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

// Helpers for MOBI/EPUB image placeholders and image_data_map lookup.

/// HtmlExtractor emits standalone image blocks as "[Image: {src}]"
final RegExp htmlExtractorImageSegmentRe = RegExp(
  r'^\[Image:\s*(.+?)\]\s*$',
  caseSensitive: false,
);

/// Placeholder syntax: <ph-mobi7/Images/image00044.jpeg>
final RegExp ebookPlaceholderRe = RegExp(r'<ph-([a-zA-Z0-9_./-]+)>');

String? parseHtmlExtractorImageSegment(String text) {
  if (text.isEmpty) {
    return null;
  }
  final match = htmlExtractorImageSegmentRe.firstMatch(text.trim());
  if (match == null) {
    return null;
  }
  final path = match.group(1)?.trim();
  return (path == null || path.isEmpty) ? null : path;
}

bool imagePathsMatch(String pathA, String pathB) {
  if (pathA.isEmpty || pathB.isEmpty) {
    return false;
  }
  var a = pathA.replaceAll('\\', '/').replaceFirst(RegExp(r'^\.?/'), '');
  var b = pathB.replaceAll('\\', '/').replaceFirst(RegExp(r'^\.?/'), '');
  if (a == b || a.contains(b) || b.contains(a)) {
    return true;
  }
  final baseA = a.split('/').last.split(r'\').last;
  final baseB = b.split('/').last.split(r'\').last;
  return baseA.isNotEmpty && baseA == baseB;
}

/// Resolve image_data_map entry by exact key or fuzzy path match.
Map<String, String>? lookupImageData(
  Map<String, Map<String, String>>? imageDataMap,
  String key,
) {
  if (imageDataMap == null || imageDataMap.isEmpty || key.isEmpty) {
    return null;
  }
  final direct = imageDataMap[key];
  if (direct != null && (direct['data'] ?? '').isNotEmpty) {
    return direct;
  }
  for (final entry in imageDataMap.entries) {
    if ((entry.value['data'] ?? '').isEmpty) {
      continue;
    }
    if (imagePathsMatch(key, entry.key)) {
      return entry.value;
    }
  }
  return null;
}
