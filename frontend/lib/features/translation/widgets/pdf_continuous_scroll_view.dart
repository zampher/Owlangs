// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../../../shared/services/translation_service.dart';
import 'pdf_continuous_page.dart';
import 'pdf_page_utils.dart';

/// Returns the 1-based page number whose body contains [anchorOffset].
int visiblePdfPageAtScrollOffset({
  required double scrollOffset,
  required double viewportExtent,
  required List<double> pageHeights,
  required double pageGap,
}) {
  if (pageHeights.isEmpty) {
    return 1;
  }
  final double anchor = scrollOffset + viewportExtent / 2;
  double top = pageGap;
  for (int index = 0; index < pageHeights.length; index++) {
    final double bottom = top + pageHeights[index];
    if (anchor <= bottom + pageGap / 2) {
      return index + 1;
    }
    top = bottom + pageGap;
  }
  return pageHeights.length;
}

/// Scroll navigation for [PdfContinuousScrollView].
class PdfContinuousScrollController {
  _PdfContinuousScrollViewState? _state;
  int? _pendingPageNumber;
  double? _preservedScrollOffset;

  bool get isAttached => _state != null;

  void _attach(_PdfContinuousScrollViewState state) {
    _state = state;
    final int? pending = _pendingPageNumber;
    if (pending != null) {
      _pendingPageNumber = null;
      jumpToPage(pending);
    }
  }

  void _detach(_PdfContinuousScrollViewState state) {
    if (_state == state) {
      _state = null;
    }
  }

  void preserveScrollPosition() {
    final _PdfContinuousScrollViewState? state = _state;
    if (state != null && state._scrollController.hasClients) {
      _preservedScrollOffset = state._scrollController.offset;
    }
  }

  void restoreScrollPosition() {
    final _PdfContinuousScrollViewState? state = _state;
    final double? offset = _preservedScrollOffset;
    if (state == null || offset == null) {
      return;
    }
    _preservedScrollOffset = null;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!state.mounted || !state._scrollController.hasClients) {
        return;
      }
      state._scrollController.jumpTo(
        offset.clamp(0.0, state._scrollController.position.maxScrollExtent),
      );
    });
  }

  Future<void> jumpToPage(int pageNumber) async {
    if (pageNumber < 1) {
      return;
    }
    if (_state != null) {
      await _state!.jumpToPage(pageNumber);
      return;
    }
    _pendingPageNumber = pageNumber;
  }

  void dispose() {
    _state = null;
    _pendingPageNumber = null;
  }
}

/// Word-style continuous vertical scroll through all PDF pages (pixel rendering).
///
/// When both [highlightPageNumber] and [highlightBbox] are non-null, a
/// semi-transparent blue rectangle is rendered on the specified page at the
/// given bounding box coordinates (in PDF points).
class PdfContinuousScrollView extends StatefulWidget {
  const PdfContinuousScrollView({
    required this.document,
    super.key,
    this.scrollController,
    this.navigationController,
    this.pageGap = 16,
    this.horizontalPadding = 12,
    this.backgroundColor = const Color(0xFFD6D6D6),
    this.onPageVisible,
    this.showScrollbar = true,
    this.highlightPageNumber,
    this.highlightBbox,
    this.bboxEditMode = false,
    this.onEditBboxChanged,
    this.onEditBboxReset,
  });

  final PdfDocument document;
  final ScrollController? scrollController;
  final PdfContinuousScrollController? navigationController;
  final double pageGap;
  final double horizontalPadding;
  final Color backgroundColor;
  final void Function(int pageNumber)? onPageVisible;
  final bool showScrollbar;

  /// 1-based page number to render the highlight rectangle on.
  final int? highlightPageNumber;

  /// Bounding box in PDF points: [x0, y0, x1, y1].
  final List<double>? highlightBbox;

  /// Whether bbox edit mode is active.
  final bool bboxEditMode;

  /// Called when the user finishes dragging the bbox overlay.
  final ValueChanged<Rect>? onEditBboxChanged;

  /// Called when the user taps the reset button.
  final VoidCallback? onEditBboxReset;

  @override
  State<PdfContinuousScrollView> createState() =>
      _PdfContinuousScrollViewState();
}

class _PdfContinuousScrollViewState extends State<PdfContinuousScrollView> {
  late ScrollController _scrollController;
  bool _ownsScrollController = false;
  double _pageWidth = 0;
  List<double>? _pageDisplayHeights;
  int _lastReportedPage = 0;

  @override
  void initState() {
    super.initState();
    if (widget.scrollController != null) {
      _scrollController = widget.scrollController!;
    } else {
      _scrollController = ScrollController();
      _ownsScrollController = true;
    }
    _scrollController.addListener(_handleScroll);
    widget.navigationController?._attach(this);
    _preloadPageHeights();
  }

  @override
  void didUpdateWidget(covariant PdfContinuousScrollView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.navigationController != widget.navigationController) {
      oldWidget.navigationController?._detach(this);
      widget.navigationController?._attach(this);
    }
    if (oldWidget.document.id != widget.document.id) {
      _pageDisplayHeights = null;
      _lastReportedPage = 0;
      _preloadPageHeights();
    }
  }

  void _handleScroll() {
    _reportVisiblePage();
  }

  void _reportVisiblePage() {
    final void Function(int pageNumber)? callback = widget.onPageVisible;
    if (callback == null || !_scrollController.hasClients) {
      return;
    }
    final List<double>? heights = _pageDisplayHeights;
    if (heights == null || heights.isEmpty) {
      return;
    }
    final int page = visiblePdfPageAtScrollOffset(
      scrollOffset: _scrollController.offset,
      viewportExtent: _scrollController.position.viewportDimension,
      pageHeights: heights,
      pageGap: widget.pageGap,
    );
    if (page == _lastReportedPage) {
      return;
    }
    _lastReportedPage = page;
    callback(page);
  }

  Future<void> _preloadPageHeights() async {
    if (_pageWidth <= 0) {
      return;
    }
    final List<double> heights = <double>[];
    for (int pageNumber = 1;
        pageNumber <= widget.document.pagesCount;
        pageNumber++) {
      PdfPage? page;
      try {
        page = await widget.document.getPage(pageNumber);
        heights.add(_pageWidth * page.height / page.width);
      } catch (_) {
        heights.add(_pageWidth * 1.414);
      } finally {
        await safeClosePdfPage(page);
      }
      if (!mounted) {
        return;
      }
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _pageDisplayHeights = heights;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _reportVisiblePage();
      }
    });
  }

  Future<void> jumpToPage(int pageNumber) async {
    if (!mounted || pageNumber < 1) {
      return;
    }
    if (_pageWidth <= 0) {
      _pendingJumpPageNumber = pageNumber;
      return;
    }
    if (_pageDisplayHeights == null) {
      _pendingJumpPageNumber = pageNumber;
      await _preloadPageHeights();
    }
    if (!mounted || _pageDisplayHeights == null) {
      return;
    }
    final int index = pageNumber - 1;
    if (index >= _pageDisplayHeights!.length) {
      return;
    }
    double offset = widget.pageGap;
    for (int i = 0; i < index; i++) {
      offset += _pageDisplayHeights![i] + widget.pageGap;
    }
    if (!_scrollController.hasClients) {
      _pendingJumpPageNumber = pageNumber;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          unawaited(jumpToPage(pageNumber));
        }
      });
      return;
    }
    _pendingJumpPageNumber = null;
    await _scrollController.animateTo(
      offset.clamp(0.0, _scrollController.position.maxScrollExtent),
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
    );
    _reportVisiblePage();
  }

  int? _pendingJumpPageNumber;

  void _maybeApplyPendingJump() {
    final int? pending = _pendingJumpPageNumber;
    if (pending == null) {
      return;
    }
    unawaited(jumpToPage(pending));
  }

  @override
  void dispose() {
    _scrollController.removeListener(_handleScroll);
    widget.navigationController?._detach(this);
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
          if (_pageWidth != pageWidth) {
            _pageWidth = pageWidth;
            _pageDisplayHeights = null;
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) {
                unawaited(_preloadPageHeights().then((_) {
                  _maybeApplyPendingJump();
                }));
              }
            });
          }
          final Widget listView = ListView.builder(
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
              final List<double>? pageHighlightBbox =
                  (widget.highlightPageNumber == pageNumber)
                      ? widget.highlightBbox
                      : null;
              final bool pageEditMode =
                  widget.bboxEditMode && widget.highlightPageNumber == pageNumber;
              return Padding(
                padding: EdgeInsets.only(
                  bottom: index == pageCount - 1 ? 0 : widget.pageGap,
                ),
                child: PdfContinuousPage(
                  document: widget.document,
                  pageNumber: pageNumber,
                  maxWidth: pageWidth,
                  highlightBbox: pageHighlightBbox,
                  bboxEditMode: pageEditMode,
                  onEditBboxChanged: pageEditMode ? widget.onEditBboxChanged : null,
                  onEditBboxReset: pageEditMode ? widget.onEditBboxReset : null,
                ),
              );
            },
          );
          if (!widget.showScrollbar) {
            return listView;
          }
          return Scrollbar(
            controller: _scrollController,
            thumbVisibility: true,
            child: listView,
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
    this.navigationController,
    this.onDocumentLoaded,
    this.onPageVisible,
    this.showScrollbar = true,
    this.highlightPageNumber,
    this.highlightBbox,
    this.bboxEditMode = false,
    this.onEditBboxChanged,
    this.onEditBboxReset,
  });

  final String downloadUrl;
  final String? rendererType;
  final ScrollController? scrollController;
  final PdfContinuousScrollController? navigationController;
  final void Function(PdfDocument document)? onDocumentLoaded;
  final void Function(int pageNumber)? onPageVisible;
  final bool showScrollbar;

  /// 1-based page number to render the highlight rectangle on.
  final int? highlightPageNumber;

  /// Bounding box in PDF points: [x0, y0, x1, y1].
  final List<double>? highlightBbox;

  /// Whether bbox edit mode is active.
  final bool bboxEditMode;

  /// Called when the user finishes dragging the bbox overlay.
  final ValueChanged<Rect>? onEditBboxChanged;

  /// Called when the user taps the reset button.
  final VoidCallback? onEditBboxReset;

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
    widget.navigationController?.preserveScrollPosition();
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final TranslationService svc = TranslationService();
      final List<int> data = await svc.downloadFile(_buildUrl());
      if (!mounted) {
        return;
      }
      if (data.isEmpty) {
        throw StateError('Downloaded PDF is empty');
      }

      // Close the old document AFTER downloading the new one. The download
      // gives in-flight PdfContinuousPage._renderPage() calls (which may be
      // awaiting getPage() or page.render() on the old document) time to
      // complete before we close the document. Closing while native rendering
      // is in-flight can cause a native crash in pdfx.
      await _document?.close();
      _document = null;

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
      widget.navigationController?.restoreScrollPosition();
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
    // Delay document close until after the next frame so that child
    // PdfContinuousPage._renderPage() calls (which may be awaiting
    // getPage() or page.render()) have time to complete before the
    // underlying native document is freed. Closing while native
    // rendering is in-flight can cause a native crash in pdfx.
    final PdfDocument? doc = _document;
    _document = null;
    if (doc != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        doc.close();
      });
    }
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
      navigationController: widget.navigationController,
      onPageVisible: widget.onPageVisible,
      showScrollbar: widget.showScrollbar,
      highlightPageNumber: widget.highlightPageNumber,
      highlightBbox: widget.highlightBbox,
      bboxEditMode: widget.bboxEditMode,
      onEditBboxChanged: widget.onEditBboxChanged,
      onEditBboxReset: widget.onEditBboxReset,
    );
  }
}
