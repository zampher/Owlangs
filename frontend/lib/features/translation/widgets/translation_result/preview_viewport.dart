// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../l10n/app_localizations.dart';

/// Scope for nested preview children (e.g. [PdfView]) to cooperate with
/// [PreviewZoomableViewport] wheel routing when zoomed.
class PreviewViewportScope extends InheritedNotifier<PreviewViewportController> {
  const PreviewViewportScope({
    required PreviewViewportController super.notifier,
    required this.delegateVerticalScrollToChild,
    required this.registerWheelFlipHandler,
    required this.resetScrollPosition,
    required super.child,
  });

  final bool delegateVerticalScrollToChild;
  final void Function(Future<void> Function(double delta)? handler)
      registerWheelFlipHandler;
  final VoidCallback resetScrollPosition;

  PreviewViewportController get controller => notifier!;

  static PreviewViewportScope? maybeOf(BuildContext context) {
    return context
        .dependOnInheritedWidgetOfExactType<PreviewViewportScope>();
  }
}

/// Controls zoom level for preview viewports (PDF/HTML compare, single preview).
/// Zoom is toolbar-only so mouse wheel stays with child scroll / PDF paging.
class PreviewViewportController extends ChangeNotifier {
  PreviewViewportController({
    this.minScale = 0.5,
    this.maxScale = 3.0,
  });

  final double minScale;
  final double maxScale;
  double _scale = 1.0;

  /// When true, the child widget (e.g. [InteractiveViewer]) owns zoom
  /// and [PreviewZoomableViewport] should not apply its own [Transform.scale].
  bool childManagesZoom = false;

  double get scale => _scale;

  int get scalePercent => (_scale * 100).round();

  void zoomIn() {
    _applyScale(_scale * 1.25);
  }

  void zoomOut() {
    _applyScale(_scale / 1.25);
  }

  void resetZoom() {
    _applyScale(1.0);
  }

  /// Sets scale from an external source (e.g. [InteractiveViewer] wheel zoom).
  /// Call [notifyListeners] so toolbar buttons react.
  void setScale(double value) {
    _applyScale(value);
  }

  void _applyScale(double next) {
    final double clamped = next.clamp(minScale, maxScale);
    if (clamped == _scale) {
      return;
    }
    _scale = clamped;
    notifyListeners();
  }
}

/// Applies toolbar-driven scale; shows scrollbars when zoomed content overflows.
class PreviewZoomableViewport extends StatefulWidget {
  const PreviewZoomableViewport({
    required this.controller,
    required this.child,
    super.key,
    this.delegateVerticalScrollToChild = false,
    this.childHandlesVerticalScroll = false,
  });

  final PreviewViewportController controller;
  final Widget child;

  /// When true (e.g. PDF panes), vertical scroll stays on the child; only
  /// horizontal pan/zoom overflow is handled by this viewport.
  final bool delegateVerticalScrollToChild;

  /// When true, the child owns vertical scrolling (e.g. continuous PDF list).
  final bool childHandlesVerticalScroll;

  @override
  State<PreviewZoomableViewport> createState() => _PreviewZoomableViewportState();
}

class _PreviewZoomableViewportState extends State<PreviewZoomableViewport> {
  final ScrollController _horizontalController = ScrollController();
  final ScrollController _verticalController = ScrollController();
  final GlobalKey _contentMeasureKey = GlobalKey();
  double _lastScale = 1.0;
  Size _measuredContentSize = Size.zero;
  Size _frozenLayoutBase = Size.zero;
  Future<void> Function(double delta)? _wheelFlipHandler;

  @override
  void initState() {
    super.initState();
    _lastScale = widget.controller.scale;
    widget.controller.addListener(_handleScaleChanged);
  }

  @override
  void didUpdateWidget(covariant PreviewZoomableViewport oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_handleScaleChanged);
      widget.controller.addListener(_handleScaleChanged);
      _lastScale = widget.controller.scale;
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_handleScaleChanged);
    _horizontalController.dispose();
    _verticalController.dispose();
    super.dispose();
  }

  void _handleScaleChanged() {
    final double scale = widget.controller.scale;
    if (scale == _lastScale) {
      return;
    }
    _lastScale = scale;
    if (scale <= 1.0) {
      _frozenLayoutBase = Size.zero;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _horizontalController.hasClients) {
          _horizontalController.jumpTo(0);
        }
        if (mounted && _verticalController.hasClients) {
          _verticalController.jumpTo(0);
        }
      });
    }
  }

  void _scheduleMeasureContent() {
    if (widget.controller.scale > 1.0) {
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      final BuildContext? context = _contentMeasureKey.currentContext;
      if (context == null) {
        return;
      }
      final RenderObject? renderObject = context.findRenderObject();
      if (renderObject is! RenderBox || !renderObject.hasSize) {
        return;
      }
      final Size nextSize = renderObject.size;
      if (nextSize != _measuredContentSize) {
        setState(() {
          _measuredContentSize = nextSize;
        });
      }
    });
  }

  double _layoutWidth(double viewportWidth) {
    if (widget.delegateVerticalScrollToChild) {
      return viewportWidth;
    }
    if (_frozenLayoutBase.width > 0) {
      return _frozenLayoutBase.width;
    }
    if (_measuredContentSize.width > 0) {
      return _measuredContentSize.width;
    }
    return viewportWidth;
  }

  double _layoutHeight(double viewportHeight) {
    if (widget.delegateVerticalScrollToChild) {
      return viewportHeight;
    }
    if (_frozenLayoutBase.height > 0) {
      return _frozenLayoutBase.height;
    }
    if (_measuredContentSize.height > 0) {
      return _measuredContentSize.height;
    }
    return viewportHeight;
  }

  void _registerWheelFlipHandler(Future<void> Function(double delta)? handler) {
    _wheelFlipHandler = handler;
  }

  void _handleDelegatedWheelScroll(PointerScrollEvent event) {
    final double deltaY = event.scrollDelta.dy;
    final double deltaX = event.scrollDelta.dx;

    if (deltaY != 0 && _verticalController.hasClients) {
      final ScrollPosition position = _verticalController.position;
      final double nextPixels = (position.pixels + deltaY).clamp(
        position.minScrollExtent,
        position.maxScrollExtent,
      );
      if (nextPixels != position.pixels) {
        _verticalController.jumpTo(nextPixels);
        return;
      }
      final Future<void> Function(double delta)? flipHandler = _wheelFlipHandler;
      if (flipHandler != null) {
        flipHandler(deltaY);
      }
      return;
    }

    if (deltaX != 0 && _horizontalController.hasClients) {
      final ScrollPosition position = _horizontalController.position;
      final double nextPixels = (position.pixels + deltaX).clamp(
        position.minScrollExtent,
        position.maxScrollExtent,
      );
      if (nextPixels != position.pixels) {
        _horizontalController.jumpTo(nextPixels);
      }
    }
  }

  Widget _wrapDelegatedWheelScroll(Widget scrollSurface) {
    return Stack(
      clipBehavior: Clip.none,
      children: <Widget>[
        scrollSurface,
        Positioned.fill(
          child: Listener(
            behavior: HitTestBehavior.translucent,
            onPointerSignal: (PointerSignalEvent event) {
              if (event is PointerScrollEvent) {
                _handleDelegatedWheelScroll(event);
              }
            },
          ),
        ),
      ],
    );
  }

  void _resetScrollPosition() {
    if (_horizontalController.hasClients) {
      _horizontalController.jumpTo(0);
    }
    if (_verticalController.hasClients) {
      _verticalController.jumpTo(0);
    }
  }

  Widget _buildViewportScope({required Widget child}) {
    return PreviewViewportScope(
      notifier: widget.controller,
      delegateVerticalScrollToChild: widget.delegateVerticalScrollToChild,
      registerWheelFlipHandler: _registerWheelFlipHandler,
      resetScrollPosition: _resetScrollPosition,
      child: child,
    );
  }

  void _freezeLayoutBase({
    required double viewportWidth,
    required double viewportHeight,
  }) {
    if (_frozenLayoutBase.width > 0 && _frozenLayoutBase.height > 0) {
      return;
    }
    if (widget.delegateVerticalScrollToChild) {
      _frozenLayoutBase = Size(viewportWidth, viewportHeight);
      return;
    }
    _frozenLayoutBase = Size(
      _measuredContentSize.width > 0 ? _measuredContentSize.width : viewportWidth,
      _measuredContentSize.height > 0
          ? _measuredContentSize.height
          : viewportHeight,
    );
  }

  Widget _buildScaledChild({
    required double layoutWidth,
    required double layoutHeight,
    required double scale,
  }) {
    return Transform.scale(
      scale: scale,
      alignment: Alignment.topLeft,
      child: SizedBox(
        key: _contentMeasureKey,
        width: layoutWidth,
        height: layoutHeight,
        child: widget.child,
      ),
    );
  }

  Widget _buildZoomedScrollSurface({
    required double viewportWidth,
    required double viewportHeight,
    required double scale,
  }) {
    final double layoutWidth = _layoutWidth(viewportWidth);
    final double layoutHeight = _layoutHeight(viewportHeight);
    final double scrollWidth = layoutWidth * scale;
    final double scrollHeight = layoutHeight * scale;

    final ScrollPhysics scrollPhysics = widget.delegateVerticalScrollToChild
        ? const NeverScrollableScrollPhysics()
        : const ClampingScrollPhysics();

    final Widget scrollSurface = Scrollbar(
      controller: _verticalController,
      thumbVisibility: true,
      child: SingleChildScrollView(
        controller: _verticalController,
        physics: scrollPhysics,
        child: Scrollbar(
          controller: _horizontalController,
          thumbVisibility: true,
          notificationPredicate: (ScrollNotification notification) {
            return notification.depth == 1;
          },
          child: SingleChildScrollView(
            controller: _horizontalController,
            scrollDirection: Axis.horizontal,
            physics: scrollPhysics,
            child: SizedBox(
              width: scrollWidth,
              height: scrollHeight,
              child: _buildScaledChild(
                layoutWidth: layoutWidth,
                layoutHeight: layoutHeight,
                scale: scale,
              ),
            ),
          ),
        ),
      ),
    );

    return widget.delegateVerticalScrollToChild
        ? _wrapDelegatedWheelScroll(scrollSurface)
        : scrollSurface;
  }

  @override
  Widget build(BuildContext context) {
    return _buildViewportScope(
      child: ListenableBuilder(
        listenable: widget.controller,
        builder: (BuildContext context, Widget? _) {
          final double scale = widget.controller.scale;
          return LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final double viewportWidth = constraints.maxWidth;
              final double viewportHeight = constraints.maxHeight;

              if (scale <= 1.0) {
                _scheduleMeasureContent();
                if (widget.childHandlesVerticalScroll) {
                  if (widget.controller.childManagesZoom) {
                    return ClipRect(child: widget.child);
                  }
                  return ClipRect(
                    child: Transform.scale(
                      scale: scale,
                      alignment: Alignment.topCenter,
                      child: widget.child,
                    ),
                  );
                }
                if (widget.delegateVerticalScrollToChild) {
                  return ClipRect(
                    child: Center(
                      child: Transform.scale(
                        scale: scale,
                        alignment: Alignment.center,
                        child: SizedBox(
                          key: _contentMeasureKey,
                          width: viewportWidth,
                          height: viewportHeight,
                          child: widget.child,
                        ),
                      ),
                    ),
                  );
                }
                return ClipRect(
                  child: SingleChildScrollView(
                    child: Transform.scale(
                      scale: scale,
                      alignment: Alignment.topCenter,
                      child: SizedBox(
                        key: _contentMeasureKey,
                        width: viewportWidth,
                        child: widget.child,
                      ),
                    ),
                  ),
                );
              }

              _freezeLayoutBase(
                viewportWidth: viewportWidth,
                viewportHeight: viewportHeight,
              );
              if (widget.childHandlesVerticalScroll) {
                if (widget.controller.childManagesZoom) {
                  return ClipRect(child: widget.child);
                }
                return ClipRect(
                  child: Transform.scale(
                    scale: scale,
                    alignment: Alignment.topCenter,
                    child: widget.child,
                  ),
                );
              }
              return _buildZoomedScrollSurface(
                viewportWidth: viewportWidth,
                viewportHeight: viewportHeight,
                scale: scale,
              );
            },
          );
        },
      ),
    );
  }
}

class _ExitPreviewFullscreenIntent extends Intent {
  const _ExitPreviewFullscreenIntent();
}

/// Zoom controls (out / percent / in) for preview toolbars.
class PreviewZoomToolbarActions extends StatelessWidget {
  const PreviewZoomToolbarActions({
    required this.viewportController,
    super.key,
    this.iconSize = 18,
    this.compact = false,
  });

  final PreviewViewportController viewportController;
  final double iconSize;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    return ListenableBuilder(
      listenable: viewportController,
      builder: (BuildContext context, Widget? _) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            IconButton(
              icon: Icon(Icons.zoom_out, size: iconSize),
              tooltip: l10n.translationPreviewZoomOut,
              visualDensity: VisualDensity.compact,
              onPressed: viewportController.scale <= viewportController.minScale
                  ? null
                  : viewportController.zoomOut,
            ),
            if (!compact)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Text(
                  '${viewportController.scalePercent}%',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            IconButton(
              icon: Icon(Icons.zoom_in, size: iconSize),
              tooltip: l10n.translationPreviewZoomIn,
              visualDensity: VisualDensity.compact,
              onPressed: viewportController.scale >= viewportController.maxScale
                  ? null
                  : viewportController.zoomIn,
            ),
          ],
        );
      },
    );
  }
}

/// Reset zoom and fullscreen — placed at the far right of preview toolbars.
class PreviewViewportTrailingActions extends StatelessWidget {
  const PreviewViewportTrailingActions({
    required this.viewportController,
    required this.isFullscreen,
    required this.onToggleFullscreen,
    super.key,
    this.iconSize = 18,
  });

  final PreviewViewportController viewportController;
  final bool isFullscreen;
  final VoidCallback onToggleFullscreen;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    return ListenableBuilder(
      listenable: viewportController,
      builder: (BuildContext context, Widget? _) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            IconButton(
              icon: Icon(Icons.fit_screen, size: iconSize),
              tooltip: l10n.translationPreviewZoomReset,
              visualDensity: VisualDensity.compact,
              onPressed: viewportController.scale == 1.0
                  ? null
                  : viewportController.resetZoom,
            ),
            IconButton(
              icon: Icon(
                isFullscreen ? Icons.fullscreen_exit : Icons.fullscreen,
                size: iconSize,
              ),
              tooltip: isFullscreen
                  ? l10n.translationToolbarExitFullscreenTooltip
                  : l10n.translationToolbarEnterFullscreenTooltip,
              visualDensity: VisualDensity.compact,
              onPressed: onToggleFullscreen,
            ),
          ],
        );
      },
    );
  }
}

/// Zoom and fullscreen actions for preview toolbars (single-row layout).
class PreviewViewportToolbarActions extends StatelessWidget {
  const PreviewViewportToolbarActions({
    required this.viewportController,
    required this.isFullscreen,
    required this.onToggleFullscreen,
    super.key,
    this.iconSize = 18,
    this.compact = false,
  });

  final PreviewViewportController viewportController;
  final bool isFullscreen;
  final VoidCallback onToggleFullscreen;
  final double iconSize;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        PreviewZoomToolbarActions(
          viewportController: viewportController,
          iconSize: iconSize,
          compact: compact,
        ),
        PreviewViewportTrailingActions(
          viewportController: viewportController,
          isFullscreen: isFullscreen,
          onToggleFullscreen: onToggleFullscreen,
          iconSize: iconSize,
        ),
      ],
    );
  }
}

/// Shows preview content in a root overlay fullscreen layer (ESC to exit).
class PreviewFullscreenOverlay {
  PreviewFullscreenOverlay({
    required this.onExit,
  });

  final VoidCallback onExit;
  OverlayEntry? _entry;
  bool _visible = false;

  bool get isVisible => _visible;

  void enter({
    required BuildContext context,
    required Widget Function(BuildContext context) builder,
  }) {
    if (_visible) {
      return;
    }
    final OverlayState overlay = Overlay.of(context, rootOverlay: true);
    _entry = OverlayEntry(
      builder: (BuildContext overlayContext) => RepaintBoundary(
        child: Material(
          color: Colors.black.withValues(alpha: 0.78),
          child: SafeArea(
            child: Theme(
              data: Theme.of(context),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: const <BoxShadow>[
                      BoxShadow(blurRadius: 20, color: Colors.black26),
                    ],
                  ),
                  child: Shortcuts(
                    shortcuts: const <ShortcutActivator, Intent>{
                      SingleActivator(LogicalKeyboardKey.escape):
                          _ExitPreviewFullscreenIntent(),
                    },
                    child: Actions(
                      actions: <Type, Action<Intent>>{
                        _ExitPreviewFullscreenIntent:
                            CallbackAction<_ExitPreviewFullscreenIntent>(
                          onInvoke: (_) {
                            exit();
                            return null;
                          },
                        ),
                      },
                      child: Focus(
                        autofocus: true,
                        child: builder(overlayContext),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    overlay.insert(_entry!);
    _visible = true;
  }

  void markNeedsBuild() {
    _entry?.markNeedsBuild();
  }

  void exit() {
    if (!_visible) {
      return;
    }
    _entry?.remove();
    _entry = null;
    _visible = false;
    onExit();
  }

  void dispose() {
    exit();
  }
}
