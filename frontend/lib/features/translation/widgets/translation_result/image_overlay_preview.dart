// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../../../app/app_config.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/services/translation_service.dart';
import 'preview_viewport.dart';
import 'layout_bbox_highlight.dart';

/// Single-pane overlay image preview (translated raster export).
///
/// When [highlightRect] is provided (in **image pixel** coordinates:
/// [x0, y0, x1, y1] relative to the raster), a semi-transparent rectangle
/// is overlaid on the image and follows zoom/pan transforms.
class ImageOverlayPreviewView extends StatefulWidget {
  const ImageOverlayPreviewView({
    required this.imageUrl,
    super.key,
    this.panelLabel,
    this.viewportController,
    this.highlightRect,
  });

  final String imageUrl;
  final String? panelLabel;
  final PreviewViewportController? viewportController;
  final Rect? highlightRect;

  @override
  State<ImageOverlayPreviewView> createState() =>
      _ImageOverlayPreviewViewState();
}

class _ImageOverlayPreviewViewState extends State<ImageOverlayPreviewView> {
  Uint8List? _bytes;
  Object? _error;
  bool _loading = true;
  final GlobalKey _imageKey = GlobalKey();
  Size? _imageSize;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant ImageOverlayPreviewView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.imageUrl != widget.imageUrl) {
      _load();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _imageSize = null;
    });
    try {
      final String url = widget.imageUrl.startsWith('http')
          ? widget.imageUrl
          : '${AppConfig.baseUrl}${widget.imageUrl}';
      final List<int> data = await TranslationService().downloadFile(url);
      if (!mounted) {
        return;
      }
      setState(() {
        _bytes = Uint8List.fromList(data);
        _loading = false;
      });
      _resolveImageSize();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  void _resolveImageSize() {
    final Uint8List? bytes = _bytes;
    if (bytes == null) return;
    final Image imageWidget = Image.memory(
      bytes,
      key: _imageKey,
      fit: BoxFit.contain,
    );
    final ImageStream stream = imageWidget.image.resolve(ImageConfiguration.empty);
    stream.addListener(ImageStreamListener((ImageInfo info, bool sync) {
      if (!mounted) return;
      setState(() {
        _imageSize = Size(
          info.image.width.toDouble(),
          info.image.height.toDouble(),
        );
      });
    }));
  }

  Rect? _computeDisplayRect(BoxConstraints constraints) {
    return layoutImageRectToDisplayRect(
      layoutRect: widget.highlightRect,
      imageSize: _imageSize,
      containerWidth: constraints.maxWidth,
      containerHeight: constraints.maxHeight,
    );
  }

  Widget _buildHighlightOverlay(BoxConstraints constraints) {
    final Rect? screenRect = _computeDisplayRect(constraints);
    if (screenRect == null) return const SizedBox.shrink();
    return buildImageBboxHighlightOverlay(screenRect);
  }

  Widget _buildImageStack(Uint8List bytes, BoxConstraints constraints) {
    return Stack(
      clipBehavior: Clip.none,
      alignment: Alignment.center,
      children: <Widget>[
        // Must match [ImageOverlayCompareView] and [layoutImageRectToDisplayRect]
        // centering so bbox overlay aligns with BoxFit.contain letterboxing.
        Center(child: Image.memory(bytes, fit: BoxFit.contain)),
        _buildHighlightOverlay(constraints),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text('Failed to load image preview: $_error'),
        ),
      );
    }
    final Uint8List? bytes = _bytes;
    if (bytes == null || bytes.isEmpty) {
      return const Center(child: Text('Image preview is empty'));
    }

    final Widget imageContent = LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        return _buildImageStack(bytes, constraints);
      },
    );

    if (widget.viewportController != null) {
      return PreviewZoomableViewport(
        controller: widget.viewportController!,
        child: Center(child: imageContent),
      );
    }
    return InteractiveViewer(
      constrained: true,
      child: Center(child: imageContent),
    );
  }
}

/// Map a bbox in image pixel space to widget coordinates for [BoxFit.contain].
Rect? layoutImageRectToDisplayRect({
  required Rect? layoutRect,
  required Size? imageSize,
  required double containerWidth,
  required double containerHeight,
}) {
  if (layoutRect == null || imageSize == null) {
    return null;
  }
  if (!_isFinitePositive(layoutRect.width) ||
      !_isFinitePositive(layoutRect.height) ||
      !layoutRect.left.isFinite ||
      !layoutRect.top.isFinite) {
    return null;
  }

  final double imageW = imageSize.width;
  final double imageH = imageSize.height;
  if (!_isFinitePositive(imageW) || !_isFinitePositive(imageH)) {
    return null;
  }

  double effectiveWidth = containerWidth;
  double effectiveHeight = containerHeight;

  // Unbounded viewport height (e.g. inside scroll/zoom): infer display height
  // from width and image aspect ratio, matching [BoxFit.contain] behavior.
  if (!effectiveHeight.isFinite || effectiveHeight <= 0) {
    if (!_isFinitePositive(effectiveWidth)) {
      return null;
    }
    effectiveHeight = imageH * (effectiveWidth / imageW);
  }
  if (!effectiveWidth.isFinite || effectiveWidth <= 0) {
    if (!effectiveHeight.isFinite || effectiveHeight <= 0) {
      return null;
    }
    effectiveWidth = imageW * (effectiveHeight / imageH);
  }
  if (!_isFinitePositive(effectiveWidth) || !_isFinitePositive(effectiveHeight)) {
    return null;
  }

  final double scale =
      math.min(effectiveWidth / imageW, effectiveHeight / imageH);
  if (!scale.isFinite || scale <= 0) {
    return null;
  }
  final double displayW = imageW * scale;
  final double displayH = imageH * scale;
  final double offsetX = (effectiveWidth - displayW) / 2;
  final double offsetY = (effectiveHeight - displayH) / 2;
  final Rect screenRect = Rect.fromLTWH(
    layoutRect.left * scale + offsetX,
    layoutRect.top * scale + offsetY,
    layoutRect.width * scale,
    layoutRect.height * scale,
  );
  if (!_isFinitePositive(screenRect.width) ||
      !_isFinitePositive(screenRect.height) ||
      !screenRect.left.isFinite ||
      !screenRect.top.isFinite) {
    return null;
  }
  return screenRect;
}

bool _isFinitePositive(double value) {
  return value.isFinite && value > 0;
}

/// Normalize [x0, y0, x1, y1] layout bbox into a finite [Rect].
Rect? layoutBlockBboxToImageRect(List<double> bbox) {
  if (bbox.length < 4) {
    return null;
  }
  final double x0 = bbox[0];
  final double y0 = bbox[1];
  final double x1 = bbox[2];
  final double y1 = bbox[3];
  if (!x0.isFinite || !y0.isFinite || !x1.isFinite || !y1.isFinite) {
    return null;
  }
  final Rect rect = Rect.fromLTRB(
    math.min(x0, x1),
    math.min(y0, y1),
    math.max(x0, x1),
    math.max(y0, y1),
  );
  if (!_isFinitePositive(rect.width) || !_isFinitePositive(rect.height)) {
    return null;
  }
  return rect;
}

Widget buildImageBboxHighlightOverlay(Rect screenRect) {
  if (!_isFinitePositive(screenRect.width) ||
      !_isFinitePositive(screenRect.height) ||
      !screenRect.left.isFinite ||
      !screenRect.top.isFinite) {
    return const SizedBox.shrink();
  }
  return layoutBboxHighlightPositioned(
    bboxRect: screenRect,
    child: IgnorePointer(
      child: Container(
        decoration: layoutBboxHighlightDecoration(),
      ),
    ),
  );
}

/// Side-by-side source vs overlay image compare preview.
class ImageOverlayCompareView extends StatefulWidget {
  const ImageOverlayCompareView({
    required this.sourceImageUrl,
    required this.targetImageUrl,
    required this.linkedScroll,
    super.key,
    this.highlightRect,
  });

  final String sourceImageUrl;
  final String targetImageUrl;
  final bool linkedScroll;

  /// Bbox rectangle (in image pixel coordinates) to highlight on both panes.
  final Rect? highlightRect;

  @override
  State<ImageOverlayCompareView> createState() =>
      _ImageOverlayCompareViewState();
}

class _ImageOverlayCompareViewState extends State<ImageOverlayCompareView> {
  Uint8List? _sourceBytes;
  Uint8List? _targetBytes;
  Object? _error;
  bool _loading = true;
  Size? _sourceImageSize;
  Size? _targetImageSize;
  final TransformationController _sourceTransformController =
      TransformationController();
  final TransformationController _targetTransformController =
      TransformationController();
  bool _syncingTransform = false;

  @override
  void initState() {
    super.initState();
    _sourceTransformController.addListener(_onSourceTransformChanged);
    _targetTransformController.addListener(_onTargetTransformChanged);
    _load();
  }

  void _onSourceTransformChanged() {
    if (_syncingTransform) return;
    _syncingTransform = true;
    _targetTransformController.value = _sourceTransformController.value;
    _syncingTransform = false;
  }

  void _onTargetTransformChanged() {
    if (_syncingTransform) return;
    _syncingTransform = true;
    _sourceTransformController.value = _targetTransformController.value;
    _syncingTransform = false;
  }

  @override
  void dispose() {
    _sourceTransformController.removeListener(_onSourceTransformChanged);
    _targetTransformController.removeListener(_onTargetTransformChanged);
    _sourceTransformController.dispose();
    _targetTransformController.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant ImageOverlayCompareView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.sourceImageUrl != widget.sourceImageUrl ||
        oldWidget.targetImageUrl != widget.targetImageUrl) {
      _load();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _sourceImageSize = null;
      _targetImageSize = null;
    });
    try {
      final TranslationService svc = TranslationService();
      Future<List<int>> fetch(String relativeOrAbsolute) {
        final String url = relativeOrAbsolute.startsWith('http')
            ? relativeOrAbsolute
            : '${AppConfig.baseUrl}$relativeOrAbsolute';
        return svc.downloadFile(url);
      }

      final List<List<int>> results = await Future.wait(<Future<List<int>>>[
        fetch(widget.sourceImageUrl),
        fetch(widget.targetImageUrl),
      ]);
      if (!mounted) {
        return;
      }
      setState(() {
        _sourceBytes = Uint8List.fromList(results[0]);
        _targetBytes = Uint8List.fromList(results[1]);
        _loading = false;
      });
      _resolveImageSizes();
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  void _resolveImageSize(Uint8List bytes, void Function(Size size) onSize) {
    final MemoryImage memoryImage = MemoryImage(bytes);
    memoryImage.resolve(ImageConfiguration.empty).addListener(
      ImageStreamListener((ImageInfo info, bool sync) {
        if (!mounted) return;
        onSize(
          Size(
            info.image.width.toDouble(),
            info.image.height.toDouble(),
          ),
        );
      }),
    );
  }

  void _resolveImageSizes() {
    final Uint8List? source = _sourceBytes;
    final Uint8List? target = _targetBytes;
    if (source != null && source.isNotEmpty) {
      _resolveImageSize(source, (Size size) {
        setState(() {
          _sourceImageSize = size;
        });
      });
    }
    if (target != null && target.isNotEmpty) {
      _resolveImageSize(target, (Size size) {
        setState(() {
          _targetImageSize = size;
        });
      });
    }
  }

  Widget _buildBboxOverlay(BoxConstraints constraints, Size? imageSize) {
    final Rect? screenRect = layoutImageRectToDisplayRect(
      layoutRect: widget.highlightRect,
      imageSize: imageSize,
      containerWidth: constraints.maxWidth,
      containerHeight: constraints.maxHeight,
    );
    if (screenRect == null) {
      return const SizedBox.shrink();
    }
    return buildImageBboxHighlightOverlay(screenRect);
  }

  Widget _buildPane({
    required String label,
    required Uint8List bytes,
    required Size? imageSize,
    required bool showHighlight,
    required TransformationController transformController,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Text(
            label,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ),
        Expanded(
          child: ClipRect(
            child: InteractiveViewer(
              transformationController: transformController,
              constrained: true,
              child: LayoutBuilder(
                builder: (BuildContext context, BoxConstraints constraints) {
                  return Stack(
                    clipBehavior: Clip.none,
                    children: <Widget>[
                      Center(
                        child: Image.memory(bytes, fit: BoxFit.contain),
                      ),
                      if (showHighlight)
                        _buildBboxOverlay(constraints, imageSize),
                    ],
                  );
                },
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCompareRow({
    required AppLocalizations l10n,
    required Uint8List source,
    required Uint8List target,
  }) {
    final bool showHighlight = widget.highlightRect != null;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          child: _buildPane(
            label: l10n.translationPreviewPanelSource,
            bytes: source,
            imageSize: _sourceImageSize,
            showHighlight: showHighlight,
            transformController: _sourceTransformController,
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          child: _buildPane(
            label: l10n.translationPreviewPanelTarget,
            bytes: target,
            imageSize: _targetImageSize,
            showHighlight: showHighlight,
            transformController: _targetTransformController,
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(child: Text('Failed to load image compare: $_error'));
    }
    final Uint8List? source = _sourceBytes;
    final Uint8List? target = _targetBytes;
    if (source == null ||
        target == null ||
        source.isEmpty ||
        target.isEmpty) {
      return Center(child: Text(l10n.translationPreviewNoExtraOptions));
    }

    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final double height = constraints.maxHeight.isFinite
            ? constraints.maxHeight
            : MediaQuery.sizeOf(context).height * 0.75;
        final double width = constraints.maxWidth.isFinite
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        return SizedBox(
          width: width,
          height: height,
          child: _buildCompareRow(
            l10n: l10n,
            source: source,
            target: target,
          ),
        );
      },
    );
  }
}
