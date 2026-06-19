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

/// Scroll navigation for [PdfCompareContinuousView].
class PdfCompareContinuousScrollController {
  _PdfCompareContinuousViewState? _state;
  int? _pendingPageNumber;

  Future<void> jumpToPage(int pageNumber) async {
    if (pageNumber < 1) {
      return;
    }
    final _PdfCompareContinuousViewState? state = _state;
    if (state != null) {
      await state.jumpToPage(pageNumber);
      return;
    }
    _pendingPageNumber = pageNumber;
  }

  void _attach(_PdfCompareContinuousViewState state) {
    _state = state;
    final int? pending = _pendingPageNumber;
    if (pending != null) {
      _pendingPageNumber = null;
      jumpToPage(pending);
    }
  }

  void _detach(_PdfCompareContinuousViewState state) {
    if (_state == state) {
      _state = null;
    }
  }

  void dispose() {
    _state = null;
    _pendingPageNumber = null;
  }
}

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
    this.navigationController,
    this.highlightPageNumber,
    this.highlightBbox,
  });

  final String sourceDownloadUrl;
  final String targetDownloadUrl;
  final String? targetRendererType;
  final bool linkedScroll;
  final double pageGap;
  final double columnGap;
  final void Function(int page, int totalPages)? onVisiblePageChanged;
  final PdfCompareContinuousScrollController? navigationController;

  /// When non-null, the page number (1-based) whose bbox should be highlighted.
  final int? highlightPageNumber;

  /// Bbox in PDF points `[x0, y0, x1, y1]` to highlight on the matching page.
  final List<double>? highlightBbox;

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
  int? _pendingJumpPageNumber;
  final TransformationController _sourceZoomController =
      TransformationController();
  final TransformationController _targetZoomController =
      TransformationController();
  bool _syncingZoom = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_handleLinkedScroll);
    _targetScrollController.addListener(_handleTargetScroll);
    widget.navigationController?._attach(this);
    _sourceZoomController.addListener(_onSourceZoomChanged);
    _targetZoomController.addListener(_onTargetZoomChanged);
    _loadDocuments();
  }

  void _onSourceZoomChanged() {
    if (_syncingZoom) return;
    _syncingZoom = true;
    _targetZoomController.value = _sourceZoomController.value;
    _syncingZoom = false;
  }

  void _onTargetZoomChanged() {
    if (_syncingZoom) return;
    _syncingZoom = true;
    _sourceZoomController.value = _targetZoomController.value;
    _syncingZoom = false;
  }

  @override
  void didUpdateWidget(covariant PdfCompareContinuousView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.navigationController != widget.navigationController) {
      oldWidget.navigationController?._detach(this);
      widget.navigationController?._attach(this);
    }
    if (oldWidget.sourceDownloadUrl != widget.sourceDownloadUrl ||
        oldWidget.targetDownloadUrl != widget.targetDownloadUrl ||
        oldWidget.targetRendererType != widget.targetRendererType) {
      _linkedRowHeights = null;
      _targetRowHeights = null;
      _lastReportedPage = 0;
      _loadDocuments();
      return;
    }
    if (oldWidget.linkedScroll != widget.linkedScroll) {
      _linkedRowHeights = null;
      _targetRowHeights = null;
      _lastReportedPage = 0;
      if (_contentWidth > 0) {
        unawaited(_preloadRowHeights(_contentWidth));
      }
    }
  }

  @override
  void dispose() {
    widget.navigationController?._detach(this);
    _scrollController.removeListener(_handleLinkedScroll);
    _targetScrollController.removeListener(_handleTargetScroll);
    _scrollController.dispose();
    _sourceScrollController.dispose();
    _targetScrollController.dispose();
    _sourceZoomController.removeListener(_onSourceZoomChanged);
    _targetZoomController.removeListener(_onTargetZoomChanged);
    _sourceZoomController.dispose();
    _targetZoomController.dispose();
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
      _maybeApplyPendingJump();
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
    _maybeApplyPendingJump();
  }

  Future<void> jumpToPage(int pageNumber) async {
    if (!mounted || pageNumber < 1) {
      return;
    }
    final List<double>? pageHeights =
        widget.linkedScroll ? _linkedRowHeights : _targetRowHeights;
    final ScrollController controller =
        widget.linkedScroll ? _scrollController : _targetScrollController;
    if (pageHeights == null || pageHeights.isEmpty) {
      _pendingJumpPageNumber = pageNumber;
      return;
    }
    final int index = pageNumber - 1;
    if (index >= pageHeights.length) {
      return;
    }
    double offset = widget.pageGap;
    for (int i = 0; i < index; i++) {
      offset += pageHeights[i] + widget.pageGap;
    }
    if (!controller.hasClients) {
      _pendingJumpPageNumber = pageNumber;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          unawaited(jumpToPage(pageNumber));
        }
      });
      return;
    }
    _pendingJumpPageNumber = null;
    await controller.animateTo(
      offset.clamp(0.0, controller.position.maxScrollExtent),
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
    );
    _reportVisiblePage(controller, pageHeights);
  }

  void _maybeApplyPendingJump() {
    final int? pending = _pendingJumpPageNumber;
    if (pending == null) {
      return;
    }
    unawaited(jumpToPage(pending));
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
                              highlightBbox: (widget.highlightPageNumber ==
                                      pageNumber)
                                  ? widget.highlightBbox
                                  : null,
                              transformController: _sourceZoomController,
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
                              highlightBbox: (widget.highlightPageNumber ==
                                      pageNumber)
                                  ? widget.highlightBbox
                                  : null,
                              transformController: _targetZoomController,
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
                        highlightBbox:
                            (widget.highlightPageNumber == pageNumber)
                                ? widget.highlightBbox
                                : null,
                        transformController: _sourceZoomController,
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
                        highlightBbox:
                            (widget.highlightPageNumber == pageNumber)
                                ? widget.highlightBbox
                                : null,
                        transformController: _targetZoomController,
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
