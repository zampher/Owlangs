// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import 'translation_result/layout_bbox_highlight.dart';

/// Renders one PDF page at [maxWidth] using pdfium/pdf.js for pixel-accurate output.
///
/// When [highlightBbox] is provided (list of 4 doubles in PDF points:
/// [x0, y0, x1, y1]), a 1px red outline is overlaid on the
/// page image to indicate the segment's bounding box.
class PdfContinuousPage extends StatefulWidget {
  const PdfContinuousPage({
    required this.document,
    required this.pageNumber,
    required this.maxWidth,
    this.highlightBbox,
    this.transformController,
    super.key,
  });

  final PdfDocument document;
  final int pageNumber;
  final double maxWidth;

  /// Optional highlight bounding box in PDF points: [x0, y0, x1, y1].
  final List<double>? highlightBbox;

  /// Optional controller to enable zoom/pan via [InteractiveViewer].
  final TransformationController? transformController;

  @override
  State<PdfContinuousPage> createState() => _PdfContinuousPageState();
}

class _PdfContinuousPageState extends State<PdfContinuousPage> {
  PdfPageImage? _image;
  double _displayHeight = 0;
  double _pdfPageWidth = 0;
  double _pdfPageHeight = 0;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _renderPage();
  }

  @override
  void didUpdateWidget(covariant PdfContinuousPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.document.id != widget.document.id ||
        oldWidget.pageNumber != widget.pageNumber ||
        oldWidget.maxWidth != widget.maxWidth) {
      _renderPage();
    }
    // Highlight bbox changes do not need a page re-render; overlay is
    // recomputed in build() from the stored page dimensions.
  }

  Future<void> _renderPage() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
      _image = null;
    });

    PdfPage? page;
    try {
      page = await widget.document.getPage(widget.pageNumber);
      _pdfPageWidth = page.width;
      _pdfPageHeight = page.height;
      final double aspectRatio = page.height / page.width;
      final double displayHeight = widget.maxWidth * aspectRatio;
      final double dpr = MediaQuery.devicePixelRatioOf(context);
      final PdfPageImage? rendered = await page.render(
        width: widget.maxWidth * dpr,
        height: displayHeight * dpr,
        format: PdfPageImageFormat.png,
        backgroundColor: '#ffffff',
        quality: 100,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _image = rendered;
        _displayHeight = displayHeight;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error;
        _loading = false;
      });
    } finally {
      await page?.close();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return SizedBox(
        width: widget.maxWidth,
        height: widget.maxWidth * 1.414,
        child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (_error != null) {
      return SizedBox(
        width: widget.maxWidth,
        height: 120,
        child: Center(
          child: Text(
            'Page ${widget.pageNumber}',
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ),
      );
    }
    final PdfPageImage? image = _image;
    if (image == null) {
      return const SizedBox.shrink();
    }

    Rect? screenRect;
    if (widget.highlightBbox != null &&
        _pdfPageWidth > 0 &&
        _pdfPageHeight > 0) {
      final double scale = widget.maxWidth / _pdfPageWidth;
      final List<double> bbox = widget.highlightBbox!;
      if (bbox.length >= 4) {
        screenRect = Rect.fromLTWH(
          bbox[0] * scale,
          bbox[1] * scale,
          (bbox[2] - bbox[0]) * scale,
          (bbox[3] - bbox[1]) * scale,
        );
      }
    }

    return PdfContinuousPageFrame(
      width: widget.maxWidth,
      height: _displayHeight,
      imageBytes: image.bytes,
      highlightRect: screenRect,
      transformController: widget.transformController,
    );
  }
}

/// Word-like white page tile on a neutral canvas.
///
/// When [highlightRect] is provided (in display-pixel coordinates relative
/// to the page image), a 1px red outline is rendered on top of the page.
class PdfContinuousPageFrame extends StatelessWidget {
  const PdfContinuousPageFrame({
    required this.width,
    required this.height,
    required this.imageBytes,
    this.highlightRect,
    this.transformController,
    super.key,
  });

  final double width;
  final double height;
  final Uint8List imageBytes;
  final Rect? highlightRect;

  /// Optional controller to enable zoom/pan via [InteractiveViewer].
  final TransformationController? transformController;

  @override
  Widget build(BuildContext context) {
    final Widget pageContent = DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x40000000),
            blurRadius: 6,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Image.memory(
        imageBytes,
        width: width,
        height: height,
        fit: BoxFit.fill,
        filterQuality: FilterQuality.high,
        gaplessPlayback: true,
      ),
    );

    final Widget tile = highlightRect == null
        ? pageContent
        : Stack(
            children: <Widget>[
              pageContent,
              layoutBboxHighlightPositioned(
                bboxRect: highlightRect!,
                child: IgnorePointer(
                  child: Container(
                    decoration: layoutBboxHighlightDecoration(),
                  ),
                ),
              ),
            ],
          );

    final Widget centered = Center(child: tile);

    if (transformController == null) {
      return centered;
    }

    return ClipRect(
      child: InteractiveViewer(
        transformationController: transformController,
        constrained: true,
        child: centered,
      ),
    );
  }
}
