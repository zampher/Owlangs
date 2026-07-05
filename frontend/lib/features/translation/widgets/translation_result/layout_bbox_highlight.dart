// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// 1 logical pixel outline; interior stays fully transparent.
const double kLayoutBboxHighlightBorderWidth = 1;

BoxDecoration layoutBboxHighlightDecoration() {
  return BoxDecoration(
    border: Border.all(
      color: Colors.red.withOpacity(0.85),
      width: kLayoutBboxHighlightBorderWidth,
    ),
    color: Colors.transparent,
  );
}

/// Outward frame so the border inner edge aligns with [bboxRect] (stroke not centered
/// on the bbox edge, which would occlude half a pixel inside the region).
Rect layoutBboxHighlightFrameRect(
  Rect bboxRect, {
  double borderWidth = kLayoutBboxHighlightBorderWidth,
}) {
  final double half = borderWidth / 2;
  return Rect.fromLTWH(
    bboxRect.left - half,
    bboxRect.top - half,
    bboxRect.width + borderWidth,
    bboxRect.height + borderWidth,
  );
}

Widget layoutBboxHighlightPositioned({
  required Rect bboxRect,
  required Widget child,
}) {
  final Rect frame = layoutBboxHighlightFrameRect(bboxRect);
  if (!frame.width.isFinite ||
      !frame.height.isFinite ||
      !frame.left.isFinite ||
      !frame.top.isFinite ||
      frame.width <= 0 ||
      frame.height <= 0) {
    return const SizedBox.shrink();
  }
  return Positioned(
    left: frame.left,
    top: frame.top,
    width: frame.width,
    height: frame.height,
    child: child,
  );
}

/// Stack multiple bbox highlight overlays (same group / multi-block segment).
List<Widget> layoutBboxHighlightOverlays(
  Iterable<Rect> bboxRects, {
  Color borderColor = const Color(0xD9FF0000),
}) {
  final List<Widget> overlays = <Widget>[];
  for (final Rect bboxRect in bboxRects) {
    overlays.add(
      layoutBboxHighlightPositioned(
        bboxRect: bboxRect,
        child: IgnorePointer(
          child: Container(
            decoration: BoxDecoration(
              border: Border.all(
                color: borderColor,
                width: kLayoutBboxHighlightBorderWidth,
              ),
              color: Colors.transparent,
            ),
          ),
        ),
      ),
    );
  }
  return overlays;
}
