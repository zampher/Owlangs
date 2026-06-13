// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:math' as math;

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../../../shared/services/translation_service.dart';
import 'pdf_continuous_page.dart';
import 'pdf_continuous_scroll_view.dart';

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
    this.onVisiblePageChanged,
  });

  final String sourceDownloadUrl;
  final String targetDownloadUrl;
  final String? targetRendererType;
  final bool linkedScroll;
  final double pageGap;
  final double columnGap;
  final void Function(int page, int totalPages)? onVisiblePageChanged;

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
  double _contentWidth = 0;
  List<double>? _linkedRowHeights;
  List<double>? _targetRowHeights;
  int _lastReportedPage = 0;
  int _totalPages = 0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_handleLinkedScroll);
    _targetScrollController.addListener(_handleTargetScroll);
    _loadDocuments();
  }

  @override
  void didUpdateWidget(covariant PdfCompareContinuousView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.sourceDownloadUrl != widget.sourceDownloadUrl ||
        oldWidget.targetDownloadUrl != widget.targetDownloadUrl ||
        oldWidget.targetRendererType != widget.targetRendererType ||
        oldWidget.linkedScroll != widget.linkedScroll) {
      _linkedRowHeights = null;
      _targetRowHeights = null;
      _lastReportedPage = 0;
      _loadDocuments();
    }
  }

  @override
  void dispose() {
    _scrollController.removeListener(_handleLinkedScroll);
    _targetScrollController.removeListener(_handleTargetScroll);
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

  Future<double> _pageDisplayHeight(
    PdfDocument document,
    int pageNumber,
    double maxWidth,
  ) async {
    if (pageNumber < 1 || pageNumber > document.pagesCount || maxWidth <= 0) {
      return 0;
    }
    PdfPage? page;
    try {
      page = await document.getPage(pageNumber);
      return maxWidth * page.height / page.width;
    } catch (_) {
      return maxWidth * 1.414;
    } finally {
      await page?.close();
    }
  }

  Future<void> _preloadRowHeights(double totalWidth) async {
    final PdfDocument? source = _sourceDocument;
    final PdfDocument? target = _targetDocument;
    if (source == null || target == null || totalWidth <= 0) {
      return;
    }

    final double columnWidth =
        ((totalWidth - widget.columnGap - 16) / 2 - 16).clamp(120.0, totalWidth);

    if (widget.linkedScroll) {
      final int rowCount = math.max(source.pagesCount, target.pagesCount);
      final List<double> heights = <double>[];
      for (int pageNumber = 1; pageNumber <= rowCount; pageNumber++) {
        final double sourceHeight = pageNumber <= source.pagesCount
            ? await _pageDisplayHeight(source, pageNumber, columnWidth)
            : 0;
        final double targetHeight = pageNumber <= target.pagesCount
            ? await _pageDisplayHeight(target, pageNumber, columnWidth)
            : 0;
        if (!mounted) {
          return;
        }
        heights.add(math.max(sourceHeight, targetHeight));
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _linkedRowHeights = heights;
        _totalPages = rowCount;
      });
      _reportVisiblePage(_scrollController, heights);
      return;
    }

    final List<double> targetHeights = <double>[];
    for (int pageNumber = 1; pageNumber <= target.pagesCount; pageNumber++) {
      targetHeights.add(
        await _pageDisplayHeight(target, pageNumber, columnWidth),
      );
      if (!mounted) {
        return;
      }
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _targetRowHeights = targetHeights;
      _totalPages = target.pagesCount;
    });
    _reportVisiblePage(_targetScrollController, targetHeights);
  }

  void _handleLinkedScroll() {
    if (!widget.linkedScroll) {
      return;
    }
    _reportVisiblePage(_scrollController, _linkedRowHeights);
  }

  void _handleTargetScroll() {
    if (widget.linkedScroll) {
      return;
    }
    _reportVisiblePage(_targetScrollController, _targetRowHeights);
  }

  void _reportVisiblePage(
    ScrollController controller,
    List<double>? pageHeights,
  ) {
    final void Function(int page, int totalPages)? callback =
        widget.onVisiblePageChanged;
    if (callback == null ||
        pageHeights == null ||
        pageHeights.isEmpty ||
        !controller.hasClients) {
      return;
    }
    final int page = visiblePdfPageAtScrollOffset(
      scrollOffset: controller.offset,
      viewportExtent: controller.position.viewportDimension,
      pageHeights: pageHeights,
      pageGap: widget.pageGap,
    );
    if (page == _lastReportedPage) {
      return;
    }
    _lastReportedPage = page;
    callback(page, _totalPages);
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
      if (_contentWidth > 0) {
        await _preloadRowHeights(_contentWidth);
      }
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

    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final double width = constraints.maxWidth;
        if (_contentWidth != width) {
          _contentWidth = width;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              unawaited(_preloadRowHeights(width));
            }
          });
        }
        return ColoredBox(
          color: const Color(0xFFD6D6D6),
          child: widget.linkedScroll
              ? _buildLinkedCompare(source, target)
              : _buildIndependentCompare(source, target),
        );
      },
    );
  }
}
