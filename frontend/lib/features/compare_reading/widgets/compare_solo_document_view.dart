// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../../../shared/utils/app_logger.dart';
import '../../../shared/widgets/unified_preview.dart';
import '../../translation/widgets/pdf_continuous_scroll_view.dart';
import '../../translation/widgets/translation_result/preview_viewport.dart';
import '../models/compare_document_model.dart';

/// Single-document pane for source-only / target-only compare reading.
class CompareSoloDocumentView extends StatefulWidget {
  const CompareSoloDocumentView({
    required this.document,
    required this.paneKey,
    this.viewportController,
    super.key,
  });

  final CompareDocumentModel document;
  final String paneKey;
  final PreviewViewportController? viewportController;

  @override
  State<CompareSoloDocumentView> createState() =>
      _CompareSoloDocumentViewState();
}

class _CompareSoloDocumentViewState extends State<CompareSoloDocumentView> {
  PdfDocument? _pdfDocument;
  Object? _pdfError;
  bool _pdfLoading = false;
  final TransformationController _imageTransformController =
      TransformationController();
  final ScrollController _textScrollController = ScrollController();
  bool _syncingViewport = false;

  @override
  void initState() {
    super.initState();
    _imageTransformController.addListener(_onImageTransformChanged);
    widget.viewportController?.addListener(_onViewportScaleChanged);
    if (widget.document.kind == ComparePaneKind.pdf) {
      _openPdf();
    } else if (widget.viewportController != null &&
        widget.document.kind == ComparePaneKind.image) {
      widget.viewportController!.childManagesZoom = true;
    }
  }

  @override
  void didUpdateWidget(covariant CompareSoloDocumentView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.viewportController != widget.viewportController) {
      oldWidget.viewportController?.removeListener(_onViewportScaleChanged);
      widget.viewportController?.addListener(_onViewportScaleChanged);
    }
    if (oldWidget.document != widget.document ||
        oldWidget.document.pdfBytes != widget.document.pdfBytes) {
      if (widget.document.kind == ComparePaneKind.pdf) {
        _openPdf();
      } else {
        _closePdf();
      }
    }
  }

  @override
  void dispose() {
    widget.viewportController?.removeListener(_onViewportScaleChanged);
    if (widget.viewportController != null) {
      widget.viewportController!.childManagesZoom = false;
    }
    _imageTransformController.removeListener(_onImageTransformChanged);
    _imageTransformController.dispose();
    _textScrollController.dispose();
    _closePdf();
    super.dispose();
  }

  Future<void> _closePdf() async {
    final PdfDocument? doc = _pdfDocument;
    _pdfDocument = null;
    await doc?.close();
  }

  Future<void> _openPdf() async {
    final Uint8List? bytes = widget.document.pdfBytes;
    if (bytes == null || bytes.isEmpty) {
      setState(() {
        _pdfError = StateError('Empty PDF bytes');
        _pdfLoading = false;
      });
      return;
    }
    setState(() {
      _pdfLoading = true;
      _pdfError = null;
    });
    try {
      final PdfDocument doc = await PdfDocument.openData(bytes);
      if (!mounted) {
        await doc.close();
        return;
      }
      final PdfDocument? old = _pdfDocument;
      _pdfDocument = doc;
      setState(() {
        _pdfLoading = false;
      });
      await old?.close();
    } catch (e, st) {
      AppLogger.log(
        'CompareSoloDocumentView',
        'Failed to open PDF: $e\n$st',
        level: LogLevel.error,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _pdfError = e;
        _pdfLoading = false;
      });
    }
  }

  bool _isCtrlPressed() => previewCtrlKeyPressed();

  void _onPointerSignal(PointerSignalEvent event) {
    if (widget.document.kind != ComparePaneKind.image) {
      return;
    }
    if (!_isCtrlPressed() || event is! PointerScrollEvent || !mounted) {
      return;
    }
    final double dy = event.scrollDelta.dy;
    if (dy == 0) {
      return;
    }
    final double currentScale =
        _imageTransformController.value.getMaxScaleOnAxis();
    final double nextScale = previewApplyCtrlWheelZoom(
      currentScale,
      dy,
      minScale: 0.5,
      maxScale: 5.0,
    );
    _imageTransformController.value =
        Matrix4.diagonal3Values(nextScale, nextScale, 1.0);
  }

  void _onImageTransformChanged() {
    final PreviewViewportController? vc = widget.viewportController;
    if (vc == null || _syncingViewport) {
      return;
    }
    _syncingViewport = true;
    vc.setScale(_imageTransformController.value.getMaxScaleOnAxis());
    _syncingViewport = false;
  }

  void _onViewportScaleChanged() {
    if (widget.document.kind != ComparePaneKind.image) {
      return;
    }
    final PreviewViewportController? vc = widget.viewportController;
    if (vc == null || _syncingViewport) {
      return;
    }
    final double scale = vc.scale;
    _syncingViewport = true;
    _imageTransformController.value =
        Matrix4.diagonal3Values(scale, scale, 1.0);
    _syncingViewport = false;
  }

  Widget _buildContent() {
    final CompareDocumentModel doc = widget.document;
    switch (doc.kind) {
      case ComparePaneKind.pdf:
        if (_pdfLoading) {
          return const Center(child: CircularProgressIndicator());
        }
        if (_pdfError != null) {
          return Center(child: Text('$_pdfError'));
        }
        final PdfDocument? pdf = _pdfDocument;
        if (pdf == null) {
          return const SizedBox.shrink();
        }
        return PdfContinuousScrollView(
          document: pdf,
          viewportController: widget.viewportController,
        );
      case ComparePaneKind.image:
        final Uint8List? bytes = doc.imageBytes;
        if (bytes == null) {
          return const SizedBox.shrink();
        }
        return Listener(
          behavior: HitTestBehavior.translucent,
          onPointerSignal: _onPointerSignal,
          child: ClipRect(
            child: InteractiveViewer(
              transformationController: _imageTransformController,
              constrained: true,
              minScale: 0.5,
              maxScale: 5.0,
              child: Center(
                child: Image.memory(bytes, fit: BoxFit.contain),
              ),
            ),
          ),
        );
      case ComparePaneKind.scrollable:
        final String content = doc.textContent ?? '';
        if (doc.contentType == 'html') {
          // Desktop WebView must fill a bounded box; nesting it in
          // SingleChildScrollView triggers semantics.parentDataDirty on Windows.
          if (kIsWeb) {
            return Scrollbar(
              controller: _textScrollController,
              thumbVisibility: true,
              child: SingleChildScrollView(
                controller: _textScrollController,
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                child: UnifiedPreview(
                  content: content,
                  contentType: 'html',
                  taskId: 'compare-solo-${widget.paneKey}',
                  comparePaneKey: 'solo-${widget.paneKey}',
                  embedInCompareScroll: true,
                ),
              ),
            );
          }
          return UnifiedPreview(
            content: content,
            contentType: 'html',
            taskId: 'compare-solo-${widget.paneKey}',
            comparePaneKey: 'solo-${widget.paneKey}',
            embedInCompareScroll: false,
          );
        }
        final Widget body;
        if (doc.contentType == 'plain') {
          body = SelectableText(
            content,
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 13,
              height: 1.45,
            ),
          );
        } else {
          body = UnifiedPreview(
            content: content,
            contentType: 'md',
            taskId: 'compare-solo-${widget.paneKey}',
            comparePaneKey: 'solo-${widget.paneKey}',
            embedInCompareScroll: false,
          );
        }
        return Scrollbar(
          controller: _textScrollController,
          thumbVisibility: true,
          child: SingleChildScrollView(
            controller: _textScrollController,
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
            child: body,
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return _buildContent();
  }
}
