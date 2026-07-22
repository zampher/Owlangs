// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

import '../models/compare_reading_layout_mode.dart';

/// Detects double-taps to toggle compare / source-only / target-only layout.
///
/// In [CompareReadingLayoutMode.compare], left half toggles source solo and
/// right half toggles target solo. In solo modes, any double-tap returns to
/// compare. Uses [Listener] so scroll / pan gestures are not blocked.
class CompareLayoutDoubleTapDetector extends StatefulWidget {
  const CompareLayoutDoubleTapDetector({
    required this.layoutMode,
    required this.onToggleSourceSolo,
    required this.onToggleTargetSolo,
    required this.child,
    super.key,
  });

  final CompareReadingLayoutMode layoutMode;
  final VoidCallback onToggleSourceSolo;
  final VoidCallback onToggleTargetSolo;
  final Widget child;

  @override
  State<CompareLayoutDoubleTapDetector> createState() =>
      _CompareLayoutDoubleTapDetectorState();
}

class _CompareLayoutDoubleTapDetectorState
    extends State<CompareLayoutDoubleTapDetector> {
  static const Duration _doubleTapTimeout = Duration(milliseconds: 300);
  static const double _doubleTapSlop = 48;

  DateTime? _lastTapAt;
  Offset? _lastTapLocal;

  void _onPointerDown(PointerDownEvent event) {
    final DateTime now = DateTime.now();
    final Offset pos = event.localPosition;
    final DateTime? lastAt = _lastTapAt;
    final Offset? lastPos = _lastTapLocal;
    if (lastAt != null &&
        lastPos != null &&
        now.difference(lastAt) <= _doubleTapTimeout &&
        (pos - lastPos).distance <= _doubleTapSlop) {
      _lastTapAt = null;
      _lastTapLocal = null;
      _handleDoubleTap(pos);
      return;
    }
    _lastTapAt = now;
    _lastTapLocal = pos;
  }

  void _handleDoubleTap(Offset localPosition) {
    switch (widget.layoutMode) {
      case CompareReadingLayoutMode.sourceOnly:
        widget.onToggleSourceSolo();
        return;
      case CompareReadingLayoutMode.targetOnly:
        widget.onToggleTargetSolo();
        return;
      case CompareReadingLayoutMode.compare:
        final RenderBox? box = context.findRenderObject() as RenderBox?;
        if (box == null || !box.hasSize) {
          return;
        }
        if (localPosition.dx < box.size.width / 2) {
          widget.onToggleSourceSolo();
        } else {
          widget.onToggleTargetSolo();
        }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Listener(
      behavior: HitTestBehavior.translucent,
      onPointerDown: _onPointerDown,
      child: widget.child,
    );
  }
}
