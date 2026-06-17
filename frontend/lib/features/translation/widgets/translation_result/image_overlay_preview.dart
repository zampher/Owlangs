// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../../../app/app_config.dart';
import '../../../../l10n/app_localizations.dart';
import '../../../../shared/services/translation_service.dart';
import 'preview_viewport.dart';

/// Single-pane overlay image preview (translated raster export).
class ImageOverlayPreviewView extends StatefulWidget {
  const ImageOverlayPreviewView({
    required this.imageUrl,
    super.key,
    this.panelLabel,
    this.viewportController,
  });

  final String imageUrl;
  final String? panelLabel;
  final PreviewViewportController? viewportController;

  @override
  State<ImageOverlayPreviewView> createState() =>
      _ImageOverlayPreviewViewState();
}

class _ImageOverlayPreviewViewState extends State<ImageOverlayPreviewView> {
  Uint8List? _bytes;
  Object? _error;
  bool _loading = true;

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

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
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
    final Widget image = Image.memory(bytes, fit: BoxFit.contain);
    if (widget.viewportController != null) {
      return PreviewZoomableViewport(
        controller: widget.viewportController!,
        child: Center(child: image),
      );
    }
    return InteractiveViewer(child: Center(child: image));
  }
}

/// Side-by-side source vs overlay image compare preview.
class ImageOverlayCompareView extends StatefulWidget {
  const ImageOverlayCompareView({
    required this.sourceImageUrl,
    required this.targetImageUrl,
    required this.linkedScroll,
    super.key,
  });

  final String sourceImageUrl;
  final String targetImageUrl;
  final bool linkedScroll;

  @override
  State<ImageOverlayCompareView> createState() =>
      _ImageOverlayCompareViewState();
}

class _ImageOverlayCompareViewState extends State<ImageOverlayCompareView> {
  Uint8List? _sourceBytes;
  Uint8List? _targetBytes;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
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

  Widget _buildPane({
    required String label,
    required Uint8List bytes,
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
              constrained: true,
              child: Center(
                child: Image.memory(bytes, fit: BoxFit.contain),
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
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          child: _buildPane(
            label: l10n.translationPreviewPanelSource,
            bytes: source,
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(
          child: _buildPane(
            label: l10n.translationPreviewPanelTarget,
            bytes: target,
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
