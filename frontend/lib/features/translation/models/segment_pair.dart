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
}
