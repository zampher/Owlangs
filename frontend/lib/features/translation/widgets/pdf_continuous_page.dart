// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

/// Renders one PDF page at [maxWidth] using pdfium/pdf.js for pixel-accurate output.
class PdfContinuousPage extends StatefulWidget {
  const PdfContinuousPage({
    required this.document,
    required this.pageNumber,
    required this.maxWidth,
    super.key,
  });

  final PdfDocument document;
  final int pageNumber;
  final double maxWidth;

  @override
  State<PdfContinuousPage> createState() => _PdfContinuousPageState();
}

class _PdfContinuousPageState extends State<PdfContinuousPage> {
  PdfPageImage? _image;
  double _displayHeight = 0;
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

    return PdfContinuousPageFrame(
      width: widget.maxWidth,
      height: _displayHeight,
      imageBytes: image.bytes,
    );
  }
}

/// Word-like white page tile on a neutral canvas.
class PdfContinuousPageFrame extends StatelessWidget {
  const PdfContinuousPageFrame({
    required this.width,
    required this.height,
    required this.imageBytes,
    super.key,
  });

  final double width;
  final double height;
  final Uint8List imageBytes;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: DecoratedBox(
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
      ),
    );
  }
}
