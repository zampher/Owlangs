// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../../../shared/services/translation_service.dart';
import 'pdf_continuous_page.dart';

/// Word-style continuous vertical scroll through all PDF pages (pixel rendering).
class PdfContinuousScrollView extends StatefulWidget {
  const PdfContinuousScrollView({
    required this.document,
    super.key,
    this.scrollController,
    this.pageGap = 16,
    this.horizontalPadding = 12,
    this.backgroundColor = const Color(0xFFD6D6D6),
    this.onPageVisible,
  });

  final PdfDocument document;
  final ScrollController? scrollController;
  final double pageGap;
  final double horizontalPadding;
  final Color backgroundColor;
  final void Function(int pageNumber)? onPageVisible;

  @override
  State<PdfContinuousScrollView> createState() =>
      _PdfContinuousScrollViewState();
}

class _PdfContinuousScrollViewState extends State<PdfContinuousScrollView> {
  late ScrollController _scrollController;
  bool _ownsScrollController = false;

  @override
  void initState() {
    super.initState();
    if (widget.scrollController != null) {
      _scrollController = widget.scrollController!;
    } else {
      _scrollController = ScrollController();
      _ownsScrollController = true;
    }
  }

  @override
  void dispose() {
    if (_ownsScrollController) {
      _scrollController.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final int pageCount = widget.document.pagesCount;
    return ColoredBox(
      color: widget.backgroundColor,
      child: LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          final double pageWidth =
              (constraints.maxWidth - widget.horizontalPadding * 2)
                  .clamp(120.0, constraints.maxWidth);
          return Scrollbar(
            controller: _scrollController,
            thumbVisibility: true,
            child: ListView.builder(
              controller: _scrollController,
              physics: const ClampingScrollPhysics(
                parent: AlwaysScrollableScrollPhysics(),
              ),
              padding: EdgeInsets.symmetric(
                vertical: widget.pageGap,
                horizontal: widget.horizontalPadding,
              ),
              itemCount: pageCount,
              itemBuilder: (BuildContext context, int index) {
                final int pageNumber = index + 1;
                return Padding(
                  padding: EdgeInsets.only(
                    bottom: index == pageCount - 1 ? 0 : widget.pageGap,
                  ),
                  child: PdfContinuousPage(
                    document: widget.document,
                    pageNumber: pageNumber,
                    maxWidth: pageWidth,
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}

/// Loads a PDF from a download URL and shows [PdfContinuousScrollView].
class PdfContinuousPreviewLoader extends StatefulWidget {
  const PdfContinuousPreviewLoader({
    required this.downloadUrl,
    super.key,
    this.rendererType,
    this.scrollController,
    this.onDocumentLoaded,
    this.onPageVisible,
  });

  final String downloadUrl;
  final String? rendererType;
  final ScrollController? scrollController;
  final void Function(PdfDocument document)? onDocumentLoaded;
  final void Function(int pageNumber)? onPageVisible;

  @override
  State<PdfContinuousPreviewLoader> createState() =>
      _PdfContinuousPreviewLoaderState();
}

class _PdfContinuousPreviewLoaderState extends State<PdfContinuousPreviewLoader> {
  PdfDocument? _document;
  bool _loading = true;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant PdfContinuousPreviewLoader oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.downloadUrl != widget.downloadUrl ||
        oldWidget.rendererType != widget.rendererType) {
      _load();
    }
  }

  String _buildUrl() {
    if (widget.rendererType == null) {
      return widget.downloadUrl;
    }
    final Uri uri = Uri.parse(widget.downloadUrl);
    final Map<String, String> params = Map<String, String>.from(
      uri.queryParameters,
    );
    params['renderer_type'] = widget.rendererType!;
    return uri.replace(queryParameters: params).toString();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    await _document?.close();
    _document = null;

    try {
      final TranslationService svc = TranslationService();
      final List<int> data = await svc.downloadFile(_buildUrl());
      if (!mounted) {
        return;
      }
      if (data.isEmpty) {
        throw StateError('Downloaded PDF is empty');
      }
      final PdfDocument document =
          await PdfDocument.openData(Uint8List.fromList(data));
      if (!mounted) {
        await document.close();
        return;
      }
      setState(() {
        _document = document;
        _loading = false;
      });
      widget.onDocumentLoaded?.call(document);
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  @override
  void dispose() {
    _document?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              const Icon(Icons.picture_as_pdf, color: Colors.redAccent),
              const SizedBox(height: 12),
              Text(
                'Failed to load PDF',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text(
                '$_error',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }
    final PdfDocument? document = _document;
    if (document == null) {
      return const SizedBox.shrink();
    }
    return PdfContinuousScrollView(
      document: document,
      scrollController: widget.scrollController,
      onPageVisible: widget.onPageVisible,
    );
  }
}
