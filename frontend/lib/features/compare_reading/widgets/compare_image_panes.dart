// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import '../../translation/widgets/translation_result/preview_viewport.dart';

/// Side-by-side image compare with optional linked pan/zoom transforms.
class CompareImagePanes extends StatefulWidget {
  const CompareImagePanes({
    required this.sourceBytes,
    required this.targetBytes,
    required this.linkedScroll,
    this.viewportController,
    super.key,
  });

  final Uint8List sourceBytes;
  final Uint8List targetBytes;
  final bool linkedScroll;
  final PreviewViewportController? viewportController;

  @override
  State<CompareImagePanes> createState() => _CompareImagePanesState();
}

class _CompareImagePanesState extends State<CompareImagePanes> {
  final TransformationController _sourceTransformController =
      TransformationController();
  final TransformationController _targetTransformController =
      TransformationController();
  bool _syncingTransform = false;
  bool _syncingViewport = false;

  @override
  void initState() {
    super.initState();
    _sourceTransformController.addListener(_onSourceTransformChanged);
    _targetTransformController.addListener(_onTargetTransformChanged);
    widget.viewportController?.addListener(_onViewportScaleChanged);
    if (widget.viewportController != null) {
      widget.viewportController!.childManagesZoom = true;
    }
  }

  @override
  void didUpdateWidget(covariant CompareImagePanes oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.viewportController != widget.viewportController) {
      oldWidget.viewportController?.removeListener(_onViewportScaleChanged);
      if (oldWidget.viewportController != null) {
        oldWidget.viewportController!.childManagesZoom = false;
      }
      widget.viewportController?.addListener(_onViewportScaleChanged);
      if (widget.viewportController != null) {
        widget.viewportController!.childManagesZoom = true;
      }
    }
    if (oldWidget.linkedScroll && !widget.linkedScroll) {
      // Keep current matrices; stop future sync only.
      return;
    }
    if (!oldWidget.linkedScroll && widget.linkedScroll) {
      _syncingTransform = true;
      _targetTransformController.value = _sourceTransformController.value;
      _syncingTransform = false;
    }
  }

  @override
  void dispose() {
    widget.viewportController?.removeListener(_onViewportScaleChanged);
    if (widget.viewportController != null) {
      widget.viewportController!.childManagesZoom = false;
    }
    _sourceTransformController.removeListener(_onSourceTransformChanged);
    _targetTransformController.removeListener(_onTargetTransformChanged);
    _sourceTransformController.dispose();
    _targetTransformController.dispose();
    super.dispose();
  }

  bool _isCtrlPressed() => previewCtrlKeyPressed();

  void _onPointerSignal(PointerSignalEvent event) {
    if (!_isCtrlPressed() || event is! PointerScrollEvent || !mounted) {
      return;
    }
    final double dy = event.scrollDelta.dy;
    if (dy == 0) {
      return;
    }
    final double currentScale =
        _sourceTransformController.value.getMaxScaleOnAxis();
    final double nextScale = previewApplyCtrlWheelZoom(
      currentScale,
      dy,
      minScale: 0.5,
      maxScale: 5.0,
    );
    _sourceTransformController.value =
        Matrix4.diagonal3Values(nextScale, nextScale, 1.0);
  }

  void _onSourceTransformChanged() {
    if (_syncingTransform) {
      return;
    }
    _syncScaleToViewport(_sourceTransformController.value);
    if (!widget.linkedScroll) {
      return;
    }
    _syncingTransform = true;
    _targetTransformController.value = _sourceTransformController.value;
    _syncingTransform = false;
  }

  void _onTargetTransformChanged() {
    if (_syncingTransform || !widget.linkedScroll) {
      return;
    }
    _syncingTransform = true;
    _sourceTransformController.value = _targetTransformController.value;
    _syncScaleToViewport(_targetTransformController.value);
    _syncingTransform = false;
  }

  void _syncScaleToViewport(Matrix4 matrix) {
    final PreviewViewportController? vc = widget.viewportController;
    if (vc == null || _syncingViewport) {
      return;
    }
    _syncingViewport = true;
    vc.setScale(matrix.getMaxScaleOnAxis());
    _syncingViewport = false;
  }

  void _onViewportScaleChanged() {
    final PreviewViewportController? vc = widget.viewportController;
    if (vc == null || _syncingViewport) {
      return;
    }
    final double scale = vc.scale;
    final Matrix4 matrix = Matrix4.diagonal3Values(scale, scale, 1.0);
    _syncingTransform = true;
    _sourceTransformController.value = matrix;
    if (widget.linkedScroll) {
      _targetTransformController.value = matrix;
    }
    _syncingTransform = false;
  }

  Widget _buildPane({
    required Uint8List bytes,
    required TransformationController transformController,
  }) {
    return ClipRect(
      child: InteractiveViewer(
        transformationController: transformController,
        constrained: true,
        minScale: 0.5,
        maxScale: 5.0,
        child: Center(
          child: Image.memory(bytes, fit: BoxFit.contain),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Listener(
      behavior: HitTestBehavior.translucent,
      onPointerSignal: _onPointerSignal,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Expanded(
            child: _buildPane(
              bytes: widget.sourceBytes,
              transformController: _sourceTransformController,
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: _buildPane(
              bytes: widget.targetBytes,
              transformController: _targetTransformController,
            ),
          ),
        ],
      ),
    );
  }
}
