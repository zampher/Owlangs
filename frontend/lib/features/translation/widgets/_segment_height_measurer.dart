// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../utils/segment_height_cache.dart';

/// Widget that measures segment height and updates the cache
/// Wraps segment widgets to automatically measure and cache their heights
class _SegmentHeightMeasurer extends StatefulWidget {
  const _SegmentHeightMeasurer({
    required this.index,
    required this.heightCache,
    required this.segmentPairKey,
    required this.child,
  });
  final int index;
  final SegmentHeightCache heightCache;
  final GlobalKey? segmentPairKey;
  final Widget child;

  @override
  State<_SegmentHeightMeasurer> createState() => _SegmentHeightMeasurerState();
}

class _SegmentHeightMeasurerState extends State<_SegmentHeightMeasurer> {
  bool _hasMeasured = false;

  @override
  void initState() {
    super.initState();
    // Measure after first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _measureHeight();
    });
  }

  @override
  void didUpdateWidget(_SegmentHeightMeasurer oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Re-measure if index or key changed
    if (oldWidget.index != widget.index ||
        oldWidget.segmentPairKey != widget.segmentPairKey) {
      _hasMeasured = false;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _measureHeight();
      });
    }
  }

  void _measureHeight() {
    if (_hasMeasured) return;

    if (widget.segmentPairKey != null) {
      final bool measured = widget.heightCache.measureAndCacheHeight(
        widget.index,
        widget.segmentPairKey,
      );
      if (measured) {
        _hasMeasured = true;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Measure again after build (in case widget was rebuilt)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _measureHeight();
    });

    return widget.child;
  }
}
