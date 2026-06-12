// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../../../shared/services/translation_service.dart';
import 'pdf_continuous_page.dart';

/// Side-by-side PDF compare with linked (single) or independent scrollbars.
class PdfCompareContinuousView extends StatefulWidget {
  const PdfCompareContinuousView({
    required this.sourceDownloadUrl,
    required this.targetDownloadUrl,
    super.key,
    this.targetRendererType,
    this.linkedScroll = true,
    this.pageGap = 16,
    this.columnGap = 1,
  });

  final String sourceDownloadUrl;
  final String targetDownloadUrl;
  final String? targetRendererType;
  final bool linkedScroll;
  final double pageGap;
  final double columnGap;

  @override
  State<PdfCompareContinuousView> createState() =>
      _PdfCompareContinuousViewState();
}

class _PdfCompareContinuousViewState extends State<PdfCompareContinuousView> {
  PdfDocument? _sourceDocument;
  PdfDocument? _targetDocument;
  bool _loading = true;
  Object? _error;
  final ScrollController _scrollController = ScrollController();
  final ScrollController _sourceScrollController = ScrollController();
  final ScrollController _targetScrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _loadDocuments();
  }

  @override
  void didUpdateWidget(covariant PdfCompareContinuousView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.sourceDownloadUrl != widget.sourceDownloadUrl ||
        oldWidget.targetDownloadUrl != widget.targetDownloadUrl ||
        oldWidget.targetRendererType != widget.targetRendererType) {
      _loadDocuments();
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _sourceScrollController.dispose();
    _targetScrollController.dispose();
    _sourceDocument?.close();
    _targetDocument?.close();
    super.dispose();
  }

  String _withRenderer(String url, String? rendererType) {
    if (rendererType == null) {
      return url;
    }
    final Uri uri = Uri.parse(url);
    final Map<String, String> params = Map<String, String>.from(
      uri.queryParameters,
    );
    params['renderer_type'] = rendererType;
    return uri.replace(queryParameters: params).toString();
  }

  Future<void> _loadDocuments() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    await _sourceDocument?.close();
    await _targetDocument?.close();
    _sourceDocument = null;
    _targetDocument = null;

    try {
      final TranslationService svc = TranslationService();
      final String targetUrl =
          _withRenderer(widget.targetDownloadUrl, widget.targetRendererType);
      final List<List<int>> results = await Future.wait(<Future<List<int>>>[
        svc.downloadFile(widget.sourceDownloadUrl),
        svc.downloadFile(targetUrl),
      ]);
      if (!mounted) {
        return;
      }
      _sourceDocument =
          await PdfDocument.openData(Uint8List.fromList(results[0]));
      _targetDocument =
          await PdfDocument.openData(Uint8List.fromList(results[1]));
      if (!mounted) {
        return;
      }
      setState(() {
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
    }
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            const Icon(Icons.compare_arrows, color: Colors.redAccent),
            const SizedBox(height: 12),
            Text(
              'Failed to load compare PDFs',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text('$_error', textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadDocuments,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLinkedCompare(PdfDocument source, PdfDocument target) {
    final int rowCount = source.pagesCount > target.pagesCount
        ? source.pagesCount
        : target.pagesCount;

    return Scrollbar(
      controller: _scrollController,
      thumbVisibility: true,
      child: ListView.builder(
        controller: _scrollController,
        physics: const ClampingScrollPhysics(
          parent: AlwaysScrollableScrollPhysics(),
        ),
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
        itemCount: rowCount,
        itemBuilder: (BuildContext context, int index) {
          final int pageNumber = index + 1;
          return Padding(
            padding: EdgeInsets.only(
              bottom: index == rowCount - 1 ? 0 : widget.pageGap,
            ),
            child: LayoutBuilder(
              builder: (BuildContext context, BoxConstraints constraints) {
                final double columnWidth =
                    (constraints.maxWidth - widget.columnGap) / 2;
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(
                      child: pageNumber <= source.pagesCount
                          ? PdfContinuousPage(
                              document: source,
                              pageNumber: pageNumber,
                              maxWidth: columnWidth - 16,
                            )
                          : const SizedBox.shrink(),
                    ),
                    SizedBox(width: widget.columnGap),
                    Expanded(
                      child: pageNumber <= target.pagesCount
                          ? PdfContinuousPage(
                              document: target,
                              pageNumber: pageNumber,
                              maxWidth: columnWidth - 16,
                            )
                          : const SizedBox.shrink(),
                    ),
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }

  Widget _buildIndependentCompare(PdfDocument source, PdfDocument target) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          child: Scrollbar(
            controller: _sourceScrollController,
            thumbVisibility: true,
            child: ListView.builder(
              controller: _sourceScrollController,
              physics: const ClampingScrollPhysics(
                parent: AlwaysScrollableScrollPhysics(),
              ),
              padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
              itemCount: source.pagesCount,
              itemBuilder: (BuildContext context, int index) {
                final int pageNumber = index + 1;
                return Padding(
                  padding: EdgeInsets.only(
                    bottom: index == source.pagesCount - 1 ? 0 : widget.pageGap,
                  ),
                  child: LayoutBuilder(
                    builder: (BuildContext context, BoxConstraints constraints) {
                      return PdfContinuousPage(
                        document: source,
                        pageNumber: pageNumber,
                        maxWidth: constraints.maxWidth - 16,
                      );
                    },
                  ),
                );
              },
            ),
          ),
        ),
        SizedBox(width: widget.columnGap),
        Expanded(
          child: Scrollbar(
            controller: _targetScrollController,
            thumbVisibility: true,
            child: ListView.builder(
              controller: _targetScrollController,
              physics: const ClampingScrollPhysics(
                parent: AlwaysScrollableScrollPhysics(),
              ),
              padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
              itemCount: target.pagesCount,
              itemBuilder: (BuildContext context, int index) {
                final int pageNumber = index + 1;
                return Padding(
                  padding: EdgeInsets.only(
                    bottom: index == target.pagesCount - 1 ? 0 : widget.pageGap,
                  ),
                  child: LayoutBuilder(
                    builder: (BuildContext context, BoxConstraints constraints) {
                      return PdfContinuousPage(
                        document: target,
                        pageNumber: pageNumber,
                        maxWidth: constraints.maxWidth - 16,
                      );
                    },
                  ),
                );
              },
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return _buildErrorState();
    }

    final PdfDocument source = _sourceDocument!;
    final PdfDocument target = _targetDocument!;

    return ColoredBox(
      color: const Color(0xFFD6D6D6),
      child: widget.linkedScroll
          ? _buildLinkedCompare(source, target)
          : _buildIndependentCompare(source, target),
    );
  }
}
