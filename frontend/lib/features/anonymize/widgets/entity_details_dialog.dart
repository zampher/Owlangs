// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Dialog for showing detailed information about an entity
class EntityDetailsDialog extends StatelessWidget {
  const EntityDetailsDialog({
    required this.entity,
    required this.originalSegments,
    required this.segmentBoundaries,
    required this.entities,
    super.key,
  });
  final Map<String, dynamic> entity;
  final List<String> originalSegments;
  final List<int> segmentBoundaries;
  final List<dynamic> entities;

  @override
  Widget build(BuildContext context) {
    final text = entity['text']?.toString() ?? 'N/A';
    final type = entity['type']?.toString() ?? 'Unknown';
    final placeholder = entity['placeholder']?.toString() ?? 'N/A';
    final start = entity['start'] as int?;
    final end = entity['end'] as int?;
    final confidence = entity['score']?.toString() ?? 'N/A';
    final segmentIndex = entity['segmentIndex'] as int?;

    return AlertDialog(
      title: const Row(
        children: <Widget>[
          Icon(Icons.info_outline, size: 24),
          SizedBox(width: 8),
          Text('Entity Details'),
        ],
      ),
      content: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            _buildDetailRow(context, 'Text', text),
            const SizedBox(height: 12),
            _buildDetailRow(context, 'Type', type),
            const SizedBox(height: 12),
            _buildDetailRow(
              context,
              'Placeholder',
              placeholder,
              isMonospace: true,
              highlightColor: Colors.orange.shade700,
            ),
            const SizedBox(height: 12),
            _buildDetailRow(context, 'Confidence', confidence),
            if (start != null && end != null) ...<Widget>[
              const SizedBox(height: 12),
              _buildDetailRow(
                context,
                'Position in full text',
                '$start-$end (length: ${end - start})',
              ),
            ],
            if (segmentIndex != null) ...<Widget>[
              const SizedBox(height: 12),
              _buildDetailRow(
                context,
                'Segment index',
                'Segment ${segmentIndex + 1} (0-based: $segmentIndex)',
              ),
              if (start != null &&
                  originalSegments.isNotEmpty &&
                  segmentIndex < originalSegments.length) ...<Widget>[
                const SizedBox(height: 8),
                _buildSegmentPositionInfo(context, text, start, segmentIndex),
              ],
              if (start != null && segmentBoundaries.isNotEmpty) ...<Widget>[
                const SizedBox(height: 12),
                _buildSegmentBoundariesDebugInfo(
                  context,
                  start,
                  segmentIndex,
                ),
              ],
            ] else ...<Widget>[
              const SizedBox(height: 12),
              _buildDetailRow(context, 'Segment index', 'Not calculated'),
              if (start != null && segmentBoundaries.isNotEmpty) ...<Widget>[
                const SizedBox(height: 12),
                _buildSegmentBoundariesDebugInfo(context, start, null),
              ],
            ],
          ],
        ),
      ),
      actions: <Widget>[
        TextButton.icon(
          onPressed: () {
            final details = _buildEntityDetailsText();
            Clipboard.setData(ClipboardData(text: details));
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Entity details copied to clipboard'),
                duration: Duration(seconds: 2),
              ),
            );
          },
          icon: const Icon(Icons.copy, size: 18),
          label: const Text('Copy'),
        ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }

  Widget _buildDetailRow(
    BuildContext context,
    String label,
    String value, {
    bool isMonospace = false,
    Color? highlightColor,
  }) =>
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(
            width: 140,
            child: Text(
              '$label:',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 13,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 13,
                fontFamily: isMonospace ? 'monospace' : null,
                color:
                    highlightColor ?? Theme.of(context).colorScheme.onSurface,
                fontWeight: highlightColor != null
                    ? FontWeight.bold
                    : FontWeight.normal,
              ),
            ),
          ),
        ],
      );

  Widget _buildSegmentPositionInfo(
    BuildContext context,
    String text,
    int start,
    int segmentIndex,
  ) {
    String positionInfo = '';
    String preview = '';

    int segmentStartInFullText = 0;
    if (segmentBoundaries.isNotEmpty &&
        segmentIndex < segmentBoundaries.length - 1) {
      segmentStartInFullText = segmentBoundaries[segmentIndex];
    }

    final positionInSegment = start - segmentStartInFullText;
    final endInSegment = positionInSegment + text.length;
    positionInfo = '$positionInSegment-$endInSegment';

    if (segmentIndex < originalSegments.length) {
      final segmentText = originalSegments[segmentIndex];
      final previewLength = segmentText.length > 100 ? 100 : segmentText.length;
      preview = segmentText.substring(0, previewLength);
      if (segmentText.length > previewLength) {
        preview += '...';
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            SizedBox(
              width: 140,
              child: Text(
                'Position in segment:',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
            Expanded(
              child: Text(
                positionInfo,
                style: const TextStyle(fontSize: 13),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            SizedBox(
              width: 140,
              child: Text(
                'Segment text length:',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
            Expanded(
              child: Text(
                segmentIndex < originalSegments.length
                    ? '${originalSegments[segmentIndex].length}'
                    : 'N/A',
                style: const TextStyle(fontSize: 13),
              ),
            ),
          ],
        ),
        if (preview.isNotEmpty) ...<Widget>[
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              SizedBox(
                width: 140,
                child: Text(
                  'Segment preview:',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              Expanded(
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    preview,
                    style: const TextStyle(fontSize: 12),
                    maxLines: 5,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildSegmentBoundariesDebugInfo(
    BuildContext context,
    int entityStart,
    int? calculatedSegmentIndex,
  ) {
    final buffer = StringBuffer();
    buffer.writeln('=== Segment Boundaries Debug Info ===');
    buffer.writeln('Entity start position: $entityStart');
    buffer.writeln('Total segments: ${segmentBoundaries.length - 1}');
    buffer.writeln('Total boundaries: ${segmentBoundaries.length}');
    buffer.writeln();

    if (segmentBoundaries.isNotEmpty) {
      buffer.writeln('Nearby boundaries:');
      for (int i = 0; i < segmentBoundaries.length; i++) {
        final boundary = segmentBoundaries[i];
        final diff = (entityStart - boundary).abs();
        if (diff < 100 ||
            (i > 0 &&
                entityStart >= segmentBoundaries[i - 1] &&
                entityStart < boundary)) {
          final marker =
              entityStart >= (i > 0 ? segmentBoundaries[i - 1] : 0) &&
                      entityStart < boundary
                  ? ' <-- entity here'
                  : '';
          buffer.writeln(
            '  Boundary[$i] = $boundary (diff: ${entityStart > boundary ? entityStart - boundary : boundary - entityStart})$marker',
          );
        }
      }
      buffer.writeln();
    }

    int? actualSegmentIndex;
    for (int i = 0; i < segmentBoundaries.length - 1; i++) {
      if (entityStart >= segmentBoundaries[i] &&
          entityStart < segmentBoundaries[i + 1]) {
        actualSegmentIndex = i;
        break;
      }
    }

    if (actualSegmentIndex != null) {
      buffer.writeln(
        'Boundary-based segment: Segment ${actualSegmentIndex + 1} (0-based: $actualSegmentIndex)',
      );
      buffer.writeln(
        '  Range: ${segmentBoundaries[actualSegmentIndex]} - ${segmentBoundaries[actualSegmentIndex + 1]}',
      );
    } else {
      buffer
          .writeln('✗ Entity position does not match any segment boundaries!');
      if (segmentBoundaries.isNotEmpty) {
        int closestIndex = 0;
        int minDiff = (entityStart - segmentBoundaries[0]).abs();
        for (int i = 1; i < segmentBoundaries.length - 1; i++) {
          final diff = (entityStart - segmentBoundaries[i]).abs();
          if (diff < minDiff) {
            minDiff = diff;
            closestIndex = i;
          }
        }
        buffer.writeln(
          '  Closest segment: $closestIndex (boundary at ${segmentBoundaries[closestIndex]}, diff: $minDiff)',
        );
      }
    }

    if (calculatedSegmentIndex != null) {
      buffer.writeln(
        'Calculated segment index: Segment ${calculatedSegmentIndex + 1} (0-based: $calculatedSegmentIndex)',
      );
      if (actualSegmentIndex != null &&
          actualSegmentIndex != calculatedSegmentIndex) {
        buffer.writeln(
          '⚠ MISMATCH: Boundary-based ($actualSegmentIndex) differs from calculated ($calculatedSegmentIndex)',
        );
        if (actualSegmentIndex < segmentBoundaries.length - 1) {
          buffer.writeln(
            '  Actual range: ${segmentBoundaries[actualSegmentIndex]} - ${segmentBoundaries[actualSegmentIndex + 1]}',
          );
        }
        if (calculatedSegmentIndex < segmentBoundaries.length - 1) {
          buffer.writeln(
            '  Calculated range: ${segmentBoundaries[calculatedSegmentIndex]} - ${segmentBoundaries[calculatedSegmentIndex + 1]}',
          );
        }
      }
    }

    buffer.writeln();
    buffer.writeln('Text-based verification:');
    final entityText = entity['text']?.toString() ?? '';
    if (entityText.isNotEmpty) {
      int? textBasedSegmentIndex;
      for (int i = 0; i < originalSegments.length; i++) {
        if (originalSegments[i].contains(entityText)) {
          textBasedSegmentIndex = i;
          break;
        }
      }
      if (textBasedSegmentIndex != null) {
        buffer.writeln(
          '  Text found in segment: $textBasedSegmentIndex (Segment ${textBasedSegmentIndex + 1})',
        );
        if (actualSegmentIndex != null &&
            actualSegmentIndex != textBasedSegmentIndex) {
          buffer.writeln(
            '  ⚠ MISMATCH: Position-based ($actualSegmentIndex) vs Text-based ($textBasedSegmentIndex)',
          );
        }
        if (calculatedSegmentIndex != null &&
            calculatedSegmentIndex != textBasedSegmentIndex) {
          buffer.writeln(
            '  ⚠ MISMATCH: Calculated ($calculatedSegmentIndex) vs Text-based ($textBasedSegmentIndex)',
          );
        }
      } else {
        buffer.writeln('  ✗ Entity text not found in any segment!');
      }
    }

    final displaySegmentIndex = entityText.isNotEmpty
        ? (() {
            for (int i = 0; i < originalSegments.length; i++) {
              if (originalSegments[i].contains(entityText)) {
                return i;
              }
            }
            return calculatedSegmentIndex ?? actualSegmentIndex;
          })()
        : (calculatedSegmentIndex ?? actualSegmentIndex);

    if (displaySegmentIndex != null &&
        displaySegmentIndex < originalSegments.length) {
      buffer.writeln();
      buffer.writeln('Current Segment ${displaySegmentIndex + 1} preview:');
      final segmentText = originalSegments[displaySegmentIndex];
      final preview = segmentText.length > 100
          ? '${segmentText.substring(0, 100)}...'
          : segmentText;
      buffer.writeln('  $preview');

      if (displaySegmentIndex > 0) {
        buffer.writeln();
        buffer.writeln('Previous Segment $displaySegmentIndex preview:');
        final prevSegmentText = originalSegments[displaySegmentIndex - 1];
        final prevPreview = prevSegmentText.length > 100
            ? '${prevSegmentText.substring(0, 100)}...'
            : prevSegmentText;
        buffer.writeln('  $prevPreview');
      }

      if (displaySegmentIndex < originalSegments.length - 1) {
        buffer.writeln();
        buffer.writeln('Next Segment ${displaySegmentIndex + 2} preview:');
        final nextSegmentText = originalSegments[displaySegmentIndex + 1];
        final nextPreview = nextSegmentText.length > 100
            ? '${nextSegmentText.substring(0, 100)}...'
            : nextSegmentText;
        buffer.writeln('  $nextPreview');
      }
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.errorContainer.withOpacity(0.2),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: Theme.of(context).colorScheme.error.withOpacity(0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                Icons.bug_report,
                size: 16,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(width: 8),
              Text(
                'Debug Info',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            buffer.toString(),
            style: TextStyle(
              fontSize: 11,
              fontFamily: 'monospace',
              color: Theme.of(context).colorScheme.onErrorContainer,
            ),
          ),
        ],
      ),
    );
  }

  String _buildEntityDetailsText() {
    final text = entity['text']?.toString() ?? 'N/A';
    final type = entity['type']?.toString() ?? 'Unknown';
    final placeholder = entity['placeholder']?.toString() ?? 'N/A';
    final start = entity['start'] as int?;
    final end = entity['end'] as int?;
    final confidence = entity['score']?.toString() ?? 'N/A';
    final segmentIndex = entity['segmentIndex'] as int?;

    final buffer = StringBuffer();
    buffer.writeln('Entity Details');
    buffer.writeln('=' * 40);
    buffer.writeln('Text: $text');
    buffer.writeln('Type: $type');
    buffer.writeln('Placeholder: $placeholder');
    buffer.writeln('Confidence: $confidence');

    if (start != null && end != null) {
      buffer.writeln(
        'Position in full text: $start-$end (length: ${end - start})',
      );
    }

    if (segmentIndex != null) {
      buffer.writeln(
        'Segment index: Segment ${segmentIndex + 1} (0-based: $segmentIndex)',
      );

      if (start != null &&
          originalSegments.isNotEmpty &&
          segmentIndex < originalSegments.length) {
        final segmentText = originalSegments[segmentIndex];

        int segmentStartInFullText = 0;
        if (segmentBoundaries.isNotEmpty &&
            segmentIndex < segmentBoundaries.length - 1) {
          segmentStartInFullText = segmentBoundaries[segmentIndex];
        }

        final positionInSegment = start - segmentStartInFullText;
        final endInSegment = positionInSegment + text.length;

        buffer.writeln('Position in segment: $positionInSegment-$endInSegment');
        buffer.writeln('Segment text length: ${segmentText.length}');
        final previewLength =
            segmentText.length > 200 ? 200 : segmentText.length;
        buffer.writeln(
          'Segment preview: ${segmentText.substring(0, previewLength)}${segmentText.length > previewLength ? '...' : ''}',
        );
      }
    } else {
      buffer.writeln('Segment index: Not calculated');
    }

    if (start != null && segmentBoundaries.isNotEmpty) {
      buffer.writeln();
      buffer.writeln('=== Segment Boundaries Debug Info ===');
      buffer.writeln('Entity start position: $start');
      buffer.writeln('Total segments: ${segmentBoundaries.length - 1}');
      buffer.writeln();

      int? actualSegmentIndex;
      for (int i = 0; i < segmentBoundaries.length - 1; i++) {
        if (start >= segmentBoundaries[i] && start < segmentBoundaries[i + 1]) {
          actualSegmentIndex = i;
          break;
        }
      }

      if (actualSegmentIndex != null) {
        buffer.writeln(
          'Boundary-based segment: $actualSegmentIndex (Segment ${actualSegmentIndex + 1})',
        );
      } else {
        buffer.writeln(
          '✗ Entity position does not match any segment boundaries!',
        );
      }

      if (segmentIndex != null) {
        buffer.writeln(
          'Calculated segment index: Segment ${segmentIndex + 1} (0-based: $segmentIndex)',
        );
        if (actualSegmentIndex != null && actualSegmentIndex != segmentIndex) {
          buffer.writeln(
            '⚠ Note: Boundary-based calculation differs from text-based search.',
          );
          buffer.writeln(
            '  Text-based search (using segments list) is more reliable.',
          );
        }
      }

      if (segmentIndex != null && segmentIndex < originalSegments.length) {
        buffer.writeln();
        buffer.writeln('Current Segment ${segmentIndex + 1} preview:');
        final segmentText = originalSegments[segmentIndex];
        final preview = segmentText.length > 200
            ? '${segmentText.substring(0, 200)}...'
            : segmentText;
        buffer.writeln('  $preview');

        if (segmentIndex > 0) {
          buffer.writeln();
          buffer.writeln('Previous Segment $segmentIndex preview:');
          final prevSegmentText = originalSegments[segmentIndex - 1];
          final prevPreview = prevSegmentText.length > 200
              ? '${prevSegmentText.substring(0, 200)}...'
              : prevSegmentText;
          buffer.writeln('  $prevPreview');
        }

        if (segmentIndex < originalSegments.length - 1) {
          buffer.writeln();
          buffer.writeln('Next Segment ${segmentIndex + 2} preview:');
          final nextSegmentText = originalSegments[segmentIndex + 1];
          final nextPreview = nextSegmentText.length > 200
              ? '${nextSegmentText.substring(0, 200)}...'
              : nextSegmentText;
          buffer.writeln('  $nextPreview');
        }
      }
    }

    return buffer.toString();
  }
}
