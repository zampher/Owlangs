// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// Custom painter that draws a dashed rectangle outline.
class BboxEditBorderPainter extends CustomPainter {
  const BboxEditBorderPainter({
    required this.rect,
    required this.color,
    this.strokeWidth = 2.0,
    this.dashLength = 6.0,
    this.gapLength = 4.0,
  });

  final Rect rect;
  final Color color;
  final double strokeWidth;
  final double dashLength;
  final double gapLength;

  @override
  void paint(Canvas canvas, Size size) {
    final Paint paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    // Draw four dashed edges
    _drawDashedLine(canvas, paint, rect.topLeft, rect.topRight);
    _drawDashedLine(canvas, paint, rect.topRight, rect.bottomRight);
    _drawDashedLine(canvas, paint, rect.bottomRight, rect.bottomLeft);
    _drawDashedLine(canvas, paint, rect.bottomLeft, rect.topLeft);
  }

  void _drawDashedLine(Canvas canvas, Paint paint, Offset start, Offset end) {
    final double totalLength = (end - start).distance;
    final double dx = (end.dx - start.dx) / totalLength;
    final double dy = (end.dy - start.dy) / totalLength;

    double drawn = 0;
    while (drawn < totalLength) {
      final double segmentEnd = drawn + dashLength;
      if (segmentEnd > totalLength) {
        final double left = totalLength - drawn;
        if (left > 0) {
          canvas.drawLine(
            Offset(start.dx + dx * drawn, start.dy + dy * drawn),
            end,
            paint,
          );
        }
        break;
      }
      canvas.drawLine(
        Offset(start.dx + dx * drawn, start.dy + dy * drawn),
        Offset(start.dx + dx * segmentEnd, start.dy + dy * segmentEnd),
        paint,
      );
      drawn = segmentEnd + gapLength;
    }
  }

  @override
  bool shouldRepaint(covariant BboxEditBorderPainter oldDelegate) {
    return rect != oldDelegate.rect ||
        color != oldDelegate.color ||
        strokeWidth != oldDelegate.strokeWidth;
  }
}
