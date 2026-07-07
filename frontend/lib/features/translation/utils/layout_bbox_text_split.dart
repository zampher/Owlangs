// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

/// Area-proportional text split for multi-bbox layout groups (mirrors backend).
library;

/// Parse `layout_block_bbox` from an API segment dict into
/// `List<List<double>>` (each entry is [x0, y0, x1, y1] in image pixels).
List<List<double>>? parseLayoutBlockBboxes(dynamic raw) {
  if (raw is! List || raw.isEmpty) {
    return null;
  }
  // Single bbox flat list: [x0, y0, x1, y1]
  if (raw.length >= 4 && raw[0] is num) {
    return <List<double>>[
      <double>[
        (raw[0] as num).toDouble(),
        (raw[1] as num).toDouble(),
        (raw[2] as num).toDouble(),
        (raw[3] as num).toDouble(),
      ],
    ];
  }
  final List<List<double>> result = <List<double>>[];
  for (final dynamic entry in raw) {
    if (entry is List && entry.length >= 4) {
      result.add(<double>[
        (entry[0] as num).toDouble(),
        (entry[1] as num).toDouble(),
        (entry[2] as num).toDouble(),
        (entry[3] as num).toDouble(),
      ]);
    }
  }
  return result.isNotEmpty ? result : null;
}

List<int>? parseLayoutBlockIndices(dynamic raw) {
  if (raw is! List || raw.isEmpty) {
    return null;
  }
  final List<int> result = <int>[];
  for (final dynamic entry in raw) {
    if (entry is int) {
      result.add(entry);
    } else if (entry is num) {
      result.add(entry.toInt());
    } else if (entry is String) {
      final int? value = int.tryParse(entry);
      if (value != null) {
        result.add(value);
      }
    }
  }
  return result.isNotEmpty ? result : null;
}

/// Parse 1-based PDF page numbers aligned with [layout_block_indices].
List<int>? parseLayoutBlockPageNumbers(dynamic raw) {
  if (raw is! List || raw.isEmpty) {
    return null;
  }
  final List<int> result = <int>[];
  for (final dynamic entry in raw) {
    if (entry is int) {
      result.add(entry);
    } else if (entry is num) {
      result.add(entry.toInt());
    } else if (entry is String) {
      final int? value = int.tryParse(entry);
      if (value != null) {
        result.add(value);
      }
    }
  }
  return result.isNotEmpty ? result : null;
}

/// Keep only bboxes whose layout block lies on [pdfPageNumber] (1-based).
List<List<double>>? filterLayoutBlockBboxesForPdfPage({
  required List<List<double>> bboxes,
  required List<int> pageNumbers,
  required int pdfPageNumber,
}) {
  if (bboxes.isEmpty || pageNumbers.isEmpty || pdfPageNumber < 1) {
    return bboxes;
  }
  if (bboxes.length != pageNumbers.length) {
    return bboxes;
  }
  final List<List<double>> filtered = <List<double>>[];
  for (int i = 0; i < bboxes.length; i++) {
    if (pageNumbers[i] == pdfPageNumber) {
      filtered.add(bboxes[i]);
    }
  }
  return filtered.isEmpty ? null : filtered;
}

List<double>? _parseSingleBboxList(dynamic raw) {
  if (raw is! List || raw.length < 4) {
    return null;
  }
  try {
    return <double>[
      (raw[0] as num).toDouble(),
      (raw[1] as num).toDouble(),
      (raw[2] as num).toDouble(),
      (raw[3] as num).toDouble(),
    ];
  } catch (_) {
    return null;
  }
}

/// Read all layout block bboxes for a segment metadata dict.
/// Applies per-block overrides and legacy primary [layout_block_bbox_override].
List<List<double>>? readSegmentLayoutBlockBboxes(Map<String, dynamic>? metadata) {
  if (metadata == null) {
    return null;
  }
  final List<List<double>>? parsed =
      parseLayoutBlockBboxes(metadata['layout_block_bbox']);
  if (parsed == null || parsed.isEmpty) {
    return null;
  }
  final List<int>? blockIndices =
      parseLayoutBlockIndices(metadata['layout_block_indices']);
  final Map<String, dynamic>? overridesRaw =
      metadata['layout_block_bbox_overrides'] is Map
          ? Map<String, dynamic>.from(
              metadata['layout_block_bbox_overrides'] as Map,
            )
          : null;
  final List<double>? primaryOverride =
      _parseSingleBboxList(metadata['layout_block_bbox_override']);
  final List<List<double>> result = <List<double>>[];
  for (int i = 0; i < parsed.length; i++) {
    List<double>? override;
    if (blockIndices != null && i < blockIndices.length) {
      if (overridesRaw != null) {
        final int blockKey = blockIndices[i];
        override = _parseSingleBboxList(
          overridesRaw['$blockKey'] ?? overridesRaw[blockKey.toString()],
        );
      }
      if (override == null &&
          i == 0 &&
          primaryOverride != null &&
          blockIndices.isNotEmpty) {
        override = primaryOverride;
      }
    } else if (i == 0 && primaryOverride != null) {
      override = primaryOverride;
    }
    if (override != null) {
      result.add(override);
    } else {
      final List<double> bbox = parsed[i];
      result.add(<double>[bbox[0], bbox[1], bbox[2], bbox[3]]);
    }
  }
  return result;
}

double layoutBboxArea(List<double> bbox) {
  if (bbox.length < 4) {
    return 0;
  }
  final double width = (bbox[2] - bbox[0]).abs();
  final double height = (bbox[3] - bbox[1]).abs();
  return width * height;
}

int _nearestWhitespaceBoundary(String text, int target) {
  if (target >= text.length) {
    return text.length;
  }
  if (target <= 0) {
    return 0;
  }
  if (text[target].trim().isEmpty) {
    return target;
  }
  const int window = 20;
  int? forward;
  for (int offset = 1; offset < window; offset++) {
    final int pos = target + offset;
    if (pos >= text.length) {
      break;
    }
    if (text[pos].trim().isEmpty) {
      forward = pos;
      break;
    }
  }
  int? backward;
  for (int offset = 1; offset < window; offset++) {
    final int pos = target - offset;
    if (pos <= 0) {
      break;
    }
    if (text[pos].trim().isEmpty) {
      backward = pos;
      break;
    }
  }
  final List<int> candidates = <int>[
    if (backward != null) backward,
    if (forward != null) forward,
  ];
  if (candidates.isEmpty) {
    return target;
  }
  candidates.sort(
    (int a, int b) => (a - target).abs().compareTo((b - target).abs()),
  );
  return candidates.first;
}

/// Split [text] across [bboxes] by bbox area; returns one string per bbox.
List<String> splitTextByLayoutBboxAreas(
  String text,
  List<List<double>> bboxes,
) {
  if (bboxes.isEmpty) {
    return <String>[];
  }
  final String normalized = text.trim();
  if (normalized.isEmpty) {
    return List<String>.filled(bboxes.length, '');
  }
  if (bboxes.length == 1) {
    return <String>[normalized];
  }

  final List<double> weights = bboxes
      .map((List<double> bbox) => layoutBboxArea(bbox).clamp(1.0, double.infinity))
      .toList(growable: false);
  final double totalWeight =
      weights.fold<double>(0, (double sum, double w) => sum + w);
  final int textLen = normalized.length;
  final List<String> result = <String>[];
  int cursor = 0;

  for (int idx = 0; idx < bboxes.length; idx++) {
    if (idx == bboxes.length - 1) {
      result.add(normalized.substring(cursor).trim());
      break;
    }
    final double share = weights[idx] / totalWeight;
    int tentativeEnd = (cursor + (textLen * share).round()).clamp(cursor + 1, textLen);
    final int boundary = _nearestWhitespaceBoundary(normalized, tentativeEnd);
    final int endPos = boundary <= cursor ? (cursor + 1).clamp(0, textLen) : boundary;
    result.add(normalized.substring(cursor, endPos).trim());
    cursor = endPos;
  }

  while (result.length < bboxes.length) {
    result.add('');
  }
  if (result.length > bboxes.length) {
    final String extra = result
        .sublist(bboxes.length - 1)
        .where((String part) => part.isNotEmpty)
        .join(' ');
    result.removeRange(bboxes.length, result.length);
    final String merged = <String>[result.last, extra]
        .where((String part) => part.isNotEmpty)
        .join(' ');
    result[bboxes.length - 1] = merged;
  }
  return result;
}

/// Parse `layout_group_text_parts` from segment metadata.
Map<int, String>? parseLayoutGroupTextParts(dynamic raw) {
  if (raw == null) {
    return null;
  }
  final Map<int, String> result = <int, String>{};
  if (raw is Map) {
    raw.forEach((dynamic key, dynamic value) {
      if (value is! String) {
        return;
      }
      final int? idx = int.tryParse(key.toString());
      if (idx != null) {
        result[idx] = value;
      }
    });
  } else if (raw is List) {
    for (final dynamic entry in raw) {
      if (entry is! Map) {
        continue;
      }
      final dynamic idxRaw =
          entry['layout_block_index'] ?? entry['index'];
      final dynamic text = entry['text'];
      if (text is! String) {
        continue;
      }
      final int? idx = idxRaw is int
          ? idxRaw
          : int.tryParse(idxRaw?.toString() ?? '');
      if (idx != null) {
        result[idx] = text;
      }
    }
  }
  return result.isEmpty ? null : result;
}

bool layoutGroupTextPartsCoverIndices(
  Map<int, String> parts,
  List<int> indices,
) {
  if (indices.length < 2) {
    return false;
  }
  for (final int idx in indices) {
    if (!parts.containsKey(idx)) {
      return false;
    }
  }
  return true;
}

String mergeLayoutGroupTextParts(
  Map<int, String> parts,
  List<int> indices,
) {
  final List<String> pieces = <String>[];
  for (final int idx in indices) {
    final String text = (parts[idx] ?? '').trim();
    if (text.isNotEmpty) {
      pieces.add(text);
    }
  }
  return pieces.join(' ');
}

/// Resolve per-block display texts: stored parts when complete, else area split.
List<String> resolveLayoutGroupDisplayTexts({
  required String text,
  required List<List<double>> bboxes,
  required List<int> indices,
  Map<int, String>? storedParts,
}) {
  if (storedParts != null &&
      layoutGroupTextPartsCoverIndices(storedParts, indices)) {
    return indices
        .map((int idx) => (storedParts[idx] ?? '').trim())
        .toList(growable: false);
  }
  return splitTextByLayoutBboxAreas(text, bboxes);
}

Map<String, String> serializeLayoutGroupTextParts(Map<int, String> parts) {
  final Map<String, String> serialized = <String, String>{};
  final List<int> sortedKeys = parts.keys.toList()..sort();
  for (final int key in sortedKeys) {
    serialized[key.toString()] = parts[key]!;
  }
  return serialized;
}
