// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

import 'bbox_edit_painter.dart';

/// Minimum bbox size in display pixels to prevent degenerate rectangles.
const double _kMinBboxSizePx = 20.0;

/// Corner handle visual size.
const double _kHandleRadius = 6.0;
const double _kHandleBorderWidth = 1.5;
const Color _kHandleFillColor = Colors.white;
const Color _kHandleBorderColor = Colors.blue;
const Color _kOverlayBorderColor = Colors.blue;

/// Reset button dimensions.
const double _kResetButtonSize = 28.0;
const double _kResetButtonGap = 4.0;

/// Which part of the bbox is being dragged.
enum _DragTarget {
  body,
  topLeft,
  topRight,
  bottomLeft,
  bottomRight,
}

/// Interactive overlay for editing a bounding box on a page image.
///
/// Renders a blue dashed border with 4 corner drag handles and a body drag
/// area. A reset button is placed at the top-right outside corner.
class LayoutBboxEditOverlay extends StatefulWidget {
  const LayoutBboxEditOverlay({
    required this.bboxRect,
    required this.imageSize,
    required this.onChanged,
    this.onReset,
    super.key,
  });

  /// Current bbox position and size in display-pixel coordinates (relative
  /// to the page image origin at top-left).
  final Rect bboxRect;

  /// Dimensions of the containing page image in display pixels.
  final Size imageSize;

  /// Called on drag end with the final display-pixel bbox.
  final ValueChanged<Rect> onChanged;

  /// Called when the reset button is tapped (restore default bbox).
  final VoidCallback? onReset;

  @override
  State<LayoutBboxEditOverlay> createState() => _LayoutBboxEditOverlayState();
}

class _LayoutBboxEditOverlayState extends State<LayoutBboxEditOverlay> {
  // Working bbox that updates during drag (separate from widget.bboxRect
  // which represents the committed value from the parent).
  late Rect _rect;
  _DragTarget? _dragTarget;
  Offset? _dragStartLocal;

  @override
  void initState() {
    super.initState();
    _rect = widget.bboxRect;
  }

  @override
  void didUpdateWidget(covariant LayoutBboxEditOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Only reset from parent when not actively dragging.
    if (_dragTarget == null && widget.bboxRect != oldWidget.bboxRect) {
      _rect = widget.bboxRect;
    }
  }

  Rect _clampRect(Rect r) {
    final double w = widget.imageSize.width;
    final double h = widget.imageSize.height;
    return Rect.fromLTRB(
      r.left.clamp(0.0, w),
      r.top.clamp(0.0, h),
      r.right.clamp(0.0, w),
      r.bottom.clamp(0.0, h),
    );
  }

  Rect _clampMinSize(Rect r) {
    final double minW = _kMinBboxSizePx;
    final double minH = _kMinBboxSizePx;
    if (r.width < minW) {
      final double diff = (minW - r.width) / 2;
      r = Rect.fromLTRB(r.left - diff, r.top, r.right + diff, r.bottom);
    }
    if (r.height < minH) {
      final double diff = (minH - r.height) / 2;
      r = Rect.fromLTRB(r.left, r.top - diff, r.right, r.bottom + diff);
    }
    return r;
  }

  void _onPanStart(_DragTarget target, Offset localPosition) {
    _dragTarget = target;
    _dragStartLocal = localPosition;
  }

  void _onPanUpdate(Offset localPosition) {
    if (_dragTarget == null || _dragStartLocal == null) {
      return;
    }
    final Offset delta = localPosition - _dragStartLocal!;
    _dragStartLocal = localPosition;

    Rect newRect;
    switch (_dragTarget!) {
      case _DragTarget.body:
        newRect = _rect.translate(delta.dx, delta.dy);
      case _DragTarget.topLeft:
        newRect = Rect.fromLTRB(
          _rect.left + delta.dx,
          _rect.top + delta.dy,
          _rect.right,
          _rect.bottom,
        );
      case _DragTarget.topRight:
        newRect = Rect.fromLTRB(
          _rect.left,
          _rect.top + delta.dy,
          _rect.right + delta.dx,
          _rect.bottom,
        );
      case _DragTarget.bottomLeft:
        newRect = Rect.fromLTRB(
          _rect.left + delta.dx,
          _rect.top,
          _rect.right,
          _rect.bottom + delta.dy,
        );
      case _DragTarget.bottomRight:
        newRect = Rect.fromLTRB(
          _rect.left,
          _rect.top,
          _rect.right + delta.dx,
          _rect.bottom + delta.dy,
        );
    }

    newRect = _clampMinSize(newRect);
    newRect = _clampRect(newRect);

    setState(() {
      _rect = newRect;
    });
  }

  void _onPanEnd() {
    if (_dragTarget != null) {
      widget.onChanged(_rect);
    }
    _dragTarget = null;
    _dragStartLocal = null;
  }

  Widget _buildHandle(Offset center, _DragTarget target) {
    return Positioned(
      left: center.dx - _kHandleRadius,
      top: center.dy - _kHandleRadius,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onPanStart: (details) => _onPanStart(target, details.localPosition),
        onPanUpdate: (details) => _onPanUpdate(details.localPosition),
        onPanEnd: (_) => _onPanEnd(),
        child: Container(
          width: _kHandleRadius * 2,
          height: _kHandleRadius * 2,
          decoration: BoxDecoration(
            color: _kHandleFillColor,
            shape: BoxShape.circle,
            border: Border.all(
              color: _kHandleBorderColor,
              width: _kHandleBorderWidth,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildResetButton() {
    final VoidCallback? onReset = widget.onReset;
    final double buttonTop = _rect.top - _kResetButtonSize - _kResetButtonGap;
    final double effectiveTop =
        buttonTop.clamp(0.0, widget.imageSize.height - _kResetButtonSize);
    final double effectiveLeft =
        (_rect.right).clamp(0.0, widget.imageSize.width - _kResetButtonSize);

    return Positioned(
      left: effectiveLeft,
      top: effectiveTop,
      child: GestureDetector(
        onTap: onReset,
        child: Container(
          width: _kResetButtonSize,
          height: _kResetButtonSize,
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            border: Border.all(color: _kHandleBorderColor, width: 1.5),
            boxShadow: const <BoxShadow>[
              BoxShadow(
                color: Color(0x30000000),
                blurRadius: 3,
                offset: Offset(0, 1),
              ),
            ],
          ),
          child: const Icon(Icons.refresh, size: 16, color: Colors.blue),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final Rect rect = _rect;

    return Stack(
      clipBehavior: Clip.none,
      children: <Widget>[
        // Dashed border via CustomPaint
        Positioned.fill(
          child: IgnorePointer(
            child: CustomPaint(
              painter: BboxEditBorderPainter(
                rect: rect,
                color: _kOverlayBorderColor,
                strokeWidth: 2.0,
              ),
            ),
          ),
        ),
        // Body drag area
        Positioned(
          left: rect.left,
          top: rect.top,
          width: rect.width,
          height: rect.height,
          child: GestureDetector(
            behavior: HitTestBehavior.translucent,
            onPanStart: (details) =>
                _onPanStart(_DragTarget.body, details.localPosition),
            onPanUpdate: (details) =>
                _onPanUpdate(details.localPosition),
            onPanEnd: (_) => _onPanEnd(),
          ),
        ),
        // Corner handles
        _buildHandle(rect.topLeft, _DragTarget.topLeft),
        _buildHandle(rect.topRight, _DragTarget.topRight),
        _buildHandle(rect.bottomLeft, _DragTarget.bottomLeft),
        _buildHandle(rect.bottomRight, _DragTarget.bottomRight),
        // Reset button (top-right outside corner)
        if (widget.onReset != null) _buildResetButton(),
      ],
    );
  }
}
