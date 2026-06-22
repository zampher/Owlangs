// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

/// Data structure for a segment pair (source + target + metadata)
class SegmentPair {
  SegmentPair({
    required this.index,
    required this.sourceText,
    required this.targetText,
    this.platformUsed,
    this.isImage = false,
    this.isFailed = false,
    this.failureReason,
    this.needsRetry = false,
    this.isExcluded = false,
    this.exclusionReason,
    this.usedPlatforms = const <String>[],
    this.rotation = 0,
    this.layoutBlockBboxOverride,
  });

  final int index;
  final String sourceText;
  final String targetText;
  final String? platformUsed;
  final bool isImage;
  final bool isFailed;
  final String? failureReason;
  final bool needsRetry;
  final bool isExcluded;
  final String?
      exclusionReason; // Exclusion reason (e.g., 'image', 'formula', 'reference')
  final List<String> usedPlatforms;
  final int rotation; // Manual rotation override: 0, 90, 180, or 270

  /// Bbox override in PDF points: [x0, y0, x1, y1], or null for default.
  final List<double>? layoutBlockBboxOverride;
}
