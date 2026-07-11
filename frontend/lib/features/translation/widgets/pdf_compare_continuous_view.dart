// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:math' as math;

import 'dart:typed_data';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:pdfx/pdfx.dart';

import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/app_logger.dart';
import 'pdf_continuous_page.dart';
import 'pdf_page_utils.dart';
import 'pdf_continuous_scroll_view.dart';
import 'translation_result/preview_viewport.dart';
import 'translation_result/preview_url_utils.dart';

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
    this.highlightBboxes,
    this.sourceHighlightBboxes,
    this.viewportController,
    this.bboxEditMode = false,
    this.editBboxRect,
    this.onEditBboxChanged,
    this.onEditBboxReset,
    this.onLoadSettled,
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

  /// Bboxes in PDF points to highlight on the matching page.
  final List<List<double>>? highlightBboxes;

  /// Original (non-overridden) bboxes for the source (left) side highlight.
  final List<List<double>>? sourceHighlightBboxes;

  /// When provided, [InteractiveViewer] zoom is bidirectionally synced with
  /// this controller so toolbar buttons (zoom In/Out/Reset) mirror the child's
  /// zoom state and vice versa.
  final PreviewViewportController? viewportController;

  /// Whether bbox edit mode is active.
  final bool bboxEditMode;

  /// Bbox for the edit overlay in display-pixel coordinates.
  final Rect? editBboxRect;

  /// Called when the user finishes dragging a bbox overlay.
  final BboxEditChangedCallback? onEditBboxChanged;

  /// Called when the user taps reset on a specific bbox overlay.
  final BboxEditResetCallback? onEditBboxReset;

  /// Called after PDF compare load attempt finishes (success or failure).
  final VoidCallback? onLoadSettled;

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
  bool _syncingViewport = false;
  bool _ctrlHeld = false;

  @override
  void initState() {
    super.initState();
    AppLogger.log(
      'PdfCompareContinuousView',
      'initState source=${widget.sourceDownloadUrl}',
      level: LogLevel.info,
    );
    _scrollController.addListener(_handleLinkedScroll);
    _targetScrollController.addListener(_handleTargetScroll);
    widget.navigationController?._attach(this);
    _sourceZoomController.addListener(_onSourceZoomChanged);
    _targetZoomController.addListener(_onTargetZoomChanged);
    widget.viewportController?.addListener(_onViewportScaleChanged);
    if (widget.viewportController != null) {
      widget.viewportController!.childManagesZoom = true;
    }
    HardwareKeyboard.instance.addHandler(_onKeyEvent);
    _loadDocuments();
  }

  bool _onKeyEvent(KeyEvent event) {
    if (!mounted) return false;
    if (event is KeyDownEvent || event is KeyRepeatEvent) {
      if (event.logicalKey == LogicalKeyboardKey.controlLeft ||
          event.logicalKey == LogicalKeyboardKey.controlRight) {
        if (!_ctrlHeld && mounted) {
          setState(() {
            _ctrlHeld = true;
          });
        }
        return false;
      }
    }
    if (event is KeyUpEvent) {
      if (event.logicalKey == LogicalKeyboardKey.controlLeft ||
          event.logicalKey == LogicalKeyboardKey.controlRight) {
        if (mounted) {
          setState(() {
            _ctrlHeld = false;
          });
        }
        return false;
      }
    }
    return false;
  }

  void _onSourceZoomChanged() {
    if (_syncingZoom) return;
    _syncingZoom = true;
    _targetZoomController.value = _sourceZoomController.value;
    _syncScaleToViewport(_sourceZoomController.value);
    _syncingZoom = false;
  }

  void _onTargetZoomChanged() {
    if (_syncingZoom) return;
    _syncingZoom = true;
    _sourceZoomController.value = _targetZoomController.value;
    _syncScaleToViewport(_targetZoomController.value);
    _syncingZoom = false;
  }

  void _syncScaleToViewport(Matrix4 matrix) {
    final PreviewViewportController? vc = widget.viewportController;
    if (vc == null || _syncingViewport) return;
    _syncingViewport = true;
    vc.setScale(matrix.getMaxScaleOnAxis());
    _syncingViewport = false;
  }

  void _onViewportScaleChanged() {
    final PreviewViewportController? vc = widget.viewportController;
    if (vc == null || _syncingViewport) return;
    final double scale = vc.scale;
    _syncingViewport = true;
    final Matrix4 matrix = Matrix4.diagonal3Values(scale, scale, 1.0);
    _sourceZoomController.value = matrix;
    _targetZoomController.value = matrix;
    _syncingViewport = false;
  }

  @override
  void didUpdateWidget(covariant PdfCompareContinuousView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.viewportController != widget.viewportController) {
      oldWidget.viewportController
          ?.removeListener(_onViewportScaleChanged);
      if (oldWidget.viewportController != null) {
        oldWidget.viewportController!.childManagesZoom = false;
      }
      widget.viewportController?.addListener(_onViewportScaleChanged);
      if (widget.viewportController != null) {
        widget.viewportController!.childManagesZoom = true;
      }
    }
    if (oldWidget.navigationController != widget.navigationController) {
      oldWidget.navigationController?._detach(this);
      widget.navigationController?._attach(this);
    }
    if (oldWidget.sourceDownloadUrl != widget.sourceDownloadUrl ||
        oldWidget.targetDownloadUrl != widget.targetDownloadUrl ||
        oldWidget.targetRendererType != widget.targetRendererType) {
      final bool sourceUnchanged = previewUrlsEquivalent(
        oldWidget.sourceDownloadUrl,
        widget.sourceDownloadUrl,
      );
      final bool targetUnchanged = previewUrlsEquivalent(
        oldWidget.targetDownloadUrl,
        widget.targetDownloadUrl,
      );
      if (sourceUnchanged &&
          targetUnchanged &&
          oldWidget.targetRendererType == widget.targetRendererType) {
        AppLogger.log(
          'PdfCompareContinuousView',
          'Skipping redundant PDF reload (equivalent URLs)',
          level: LogLevel.debug,
        );
        return;
      }
      AppLogger.log(
        'PdfCompareContinuousView',
        'Reloading compare PDFs: sourceChanged=${!sourceUnchanged} '
        'targetChanged=${!targetUnchanged} '
        'rendererChanged=${oldWidget.targetRendererType != widget.targetRendererType}',
        level: LogLevel.info,
      );
      _linkedRowHeights = null;
      _targetRowHeights = null;
      _lastReportedPage = 0;
      _loadDocuments(reason: 'url-change');
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

  bool _isCtrlPressed() => previewCtrlKeyPressed();

  void _onPointerSignal(PointerSignalEvent event) {
    if (!_isCtrlPressed() || event is! PointerScrollEvent || !mounted) return;
    final PointerScrollEvent scroll = event;
    final double dy = scroll.scrollDelta.dy;
    if (dy == 0) return;
    final double currentScale = _sourceZoomController.value.getMaxScaleOnAxis();
    final double nextScale = previewApplyCtrlWheelZoom(
      currentScale,
      dy,
      minScale: 0.5,
      maxScale: 5.0,
    );
    final Matrix4 matrix = Matrix4.diagonal3Values(nextScale, nextScale, 1.0);
    // _onSourceZoomChanged syncs target and viewport automatically.
    _sourceZoomController.value = matrix;
  }

  @override
  void dispose() {
    AppLogger.log(
      'PdfCompareContinuousView',
      'dispose source=${widget.sourceDownloadUrl}',
      level: LogLevel.info,
    );
    HardwareKeyboard.instance.removeHandler(_onKeyEvent);
    widget.navigationController?._detach(this);
    _scrollController.removeListener(_handleLinkedScroll);
    _targetScrollController.removeListener(_handleTargetScroll);
    _scrollController.dispose();
    _sourceScrollController.dispose();
    _targetScrollController.dispose();
    widget.viewportController
        ?.removeListener(_onViewportScaleChanged);
    if (widget.viewportController != null) {
      widget.viewportController!.childManagesZoom = false;
    }
    _sourceZoomController.removeListener(_onSourceZoomChanged);
    _targetZoomController.removeListener(_onTargetZoomChanged);
    _sourceZoomController.dispose();
    _targetZoomController.dispose();

    // Delay document close until after the next frame so that child
    // PdfContinuousPage._renderPage() calls (which may be awaiting
    // getPage() or page.render()) have time to complete before the
    // underlying native document is freed. Closing while native
    // rendering is in-flight can cause a native crash in pdfx.
    final PdfDocument? sourceDoc = _sourceDocument;
    final PdfDocument? targetDoc = _targetDocument;
    _sourceDocument = null;
    _targetDocument = null;
    if (sourceDoc != null || targetDoc != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        sourceDoc?.close();
        targetDoc?.close();
      });
    }

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
      await safeClosePdfPage(page);
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

  bool _loadInProgress = false;
  bool _loadPending = false;

  Future<void> _loadDocuments({String reason = 'initial'}) async {
    // Guard against concurrent calls: if already loading, mark pending and
    // the current load will re-invoke when it completes.
    if (_loadInProgress) {
      _loadPending = true;
      return;
    }
    _loadInProgress = true;
    _loadPending = false;

    AppLogger.log(
      'PdfCompareContinuousView',
      'Loading compare PDFs (reason=$reason, hasContent=${_sourceDocument != null && _targetDocument != null})',
      level: LogLevel.info,
    );

    // Only show the loading spinner when we have nothing to display.
    // When documents are already loaded (e.g. URL change from revision
    // update), keep the old content visible to avoid a flash.
    final bool hasContent = _sourceDocument != null && _targetDocument != null;
    if (!hasContent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      // Download new documents while old content stays visible.
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

      // Open new documents BEFORE closing old ones, so there is no
      // window where _sourceDocument / _targetDocument are null while
      // the build method may still access them (when hasContent is true).
      final PdfDocument newSource =
          await PdfDocument.openData(Uint8List.fromList(results[0]));
      final PdfDocument newTarget =
          await PdfDocument.openData(Uint8List.fromList(results[1]));
      if (!mounted) {
        await newSource.close();
        await newTarget.close();
        return;
      }

      // Atomically swap in new documents, then close old ones.
      // The download time ensures in-flight PdfContinuousPage renders
      // on the old documents have completed, preventing native crashes.
      final PdfDocument? oldSource = _sourceDocument;
      final PdfDocument? oldTarget = _targetDocument;
      _sourceDocument = newSource;
      _targetDocument = newTarget;

      setState(() {
        _loading = false;
        _error = null;
      });

      await oldSource?.close();
      await oldTarget?.close();

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
    } finally {
      _loadInProgress = false;
    }

    // If another URL change was requested while we were loading, process it now.
    if (_loadPending && mounted) {
      _loadPending = false;
      unawaited(_loadDocuments(reason: 'queued'));
      return;
    }
    widget.onLoadSettled?.call();
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

    return Listener(
      behavior: HitTestBehavior.translucent,
      onPointerSignal: _onPointerSignal,
      child: Scrollbar(
        controller: _scrollController,
        thumbVisibility: true,
        child: ListView.builder(
          controller: _scrollController,
          physics: _ctrlHeld
              ? const NeverScrollableScrollPhysics()
              : const ClampingScrollPhysics(
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
                              highlightBboxes: (widget.highlightPageNumber ==
                                      pageNumber)
                                  ? (widget.sourceHighlightBboxes ??
                                      widget.highlightBboxes)
                                  : null,
                              transformController: _sourceZoomController,
                              scaleEnabled: false,
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
                              highlightBboxes: (widget.highlightPageNumber ==
                                      pageNumber)
                                  ? widget.highlightBboxes
                                  : null,
                              transformController: _targetZoomController,
                              scaleEnabled: false,
                              bboxEditMode: (widget.highlightPageNumber ==
                                      pageNumber)
                                  ? widget.bboxEditMode
                                  : false,
                              onEditBboxChanged: (widget.highlightPageNumber ==
                                      pageNumber)
                                  ? widget.onEditBboxChanged
                                  : null,
                              onEditBboxReset: (widget.highlightPageNumber ==
                                      pageNumber)
                                  ? widget.onEditBboxReset
                                  : null,
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
      ),
    );
  }

  Widget _buildIndependentCompare(PdfDocument source, PdfDocument target) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          child: Listener(
            behavior: HitTestBehavior.translucent,
            onPointerSignal: _onPointerSignal,
            child: Scrollbar(
              controller: _sourceScrollController,
              thumbVisibility: true,
              child: ListView.builder(
                controller: _sourceScrollController,
                physics: _ctrlHeld
                    ? const NeverScrollableScrollPhysics()
                    : const ClampingScrollPhysics(
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
                          highlightBboxes:
                              (widget.highlightPageNumber == pageNumber)
                                  ? (widget.sourceHighlightBboxes ??
                                      widget.highlightBboxes)
                                  : null,
                          transformController: _sourceZoomController,
                          scaleEnabled: false,
                        );
                      },
                    ),
                  );
                },
              ),
            ),
          ),
        ),
        SizedBox(width: widget.columnGap),
        Expanded(
          child: Listener(
            behavior: HitTestBehavior.translucent,
            onPointerSignal: _onPointerSignal,
            child: Scrollbar(
              controller: _targetScrollController,
              thumbVisibility: true,
              child: ListView.builder(
                controller: _targetScrollController,
                physics: _ctrlHeld
                    ? const NeverScrollableScrollPhysics()
                    : const ClampingScrollPhysics(
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
                          highlightBboxes:
                              (widget.highlightPageNumber == pageNumber)
                                  ? widget.highlightBboxes
                                  : null,
                          transformController: _targetZoomController,
                          scaleEnabled: false,
                          bboxEditMode: (widget.highlightPageNumber ==
                                  pageNumber)
                              ? widget.bboxEditMode
                              : false,
                          onEditBboxChanged: (widget.highlightPageNumber ==
                                  pageNumber)
                              ? widget.onEditBboxChanged
                              : null,
                          onEditBboxReset: (widget.highlightPageNumber ==
                                  pageNumber)
                              ? widget.onEditBboxReset
                              : null,
                        );
                      },
                    ),
                  );
                },
              ),
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
