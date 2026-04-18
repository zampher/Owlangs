// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:html' as html;
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';

import '../../../shared/services/translation_service.dart';

class PdfPreview extends StatefulWidget {
  const PdfPreview({
    required this.downloadUrl,
    required this.viewerUrl,
    super.key,
    this.onDownload,
  });
  final String downloadUrl;
  final String viewerUrl;
  final void Function(String format, String url)? onDownload;

  @override
  State<PdfPreview> createState() => _PdfPreviewWebState();
}

class _PdfPreviewWebState extends State<PdfPreview> {
  bool _loading = true;
  String? _error;
  html.IFrameElement? _iframe;
  String? _blobUrl;

  // Static flag to ensure registration only happens once
  static bool _factoryRegistered = false;

  @override
  void initState() {
    super.initState();
    _registerViewFactory(); // Register view factory early
    _loadPdf();
  }

  @override
  void dispose() {
    // Clean up blob URL to free memory
    if (_blobUrl != null) {
      try {
        html.Url.revokeObjectUrl(_blobUrl!);
      } catch (e) {
        print('[PDF Preview] Error revoking blob URL: $e');
      }
    }
    super.dispose();
  }

  void _registerViewFactory() {
    if (_factoryRegistered) {
      print('[PDF Preview] View factory already registered, skipping.');
      return;
    }

    try {
      // Use dart:ui_web's platformViewRegistry for proper registration
      ui_web.platformViewRegistry.registerViewFactory(
        'pdf-iframe-view',
        (int viewId) {
          print('[PDF Preview] Creating container for viewId: $viewId');
          final container = html.DivElement()
            ..id = 'pdf-iframe-container-$viewId'
            ..style.width = '100%'
            ..style.height = '100%'
            ..style.margin = '0'
            ..style.padding = '0'
            ..style.overflow = 'hidden';
          return container;
        },
      );
      _factoryRegistered = true;
      print('[PDF Preview] View factory registered successfully');
    } catch (e, stackTrace) {
      print('[PDF Preview] Error registering view factory: $e');
      print('[PDF Preview] Stack trace: $stackTrace');
    }
  }

  Future<void> _loadPdf() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      print('[PDF Preview] Starting to load PDF from: ${widget.downloadUrl}');

      final svc = TranslationService();
      final data = await svc.downloadFile(widget.downloadUrl);

      if (data.isEmpty) {
        throw Exception('Downloaded PDF data is empty');
      }

      print(
        '[PDF Preview] Downloaded ${data.length} bytes, creating blob URL...',
      );

      // Create a Blob from the PDF data
      final blob = html.Blob(<dynamic>[data], 'application/pdf');
      _blobUrl = html.Url.createObjectUrlFromBlob(blob);

      print('[PDF Preview] Blob URL created: $_blobUrl');

      // Create iframe element
      _iframe = html.IFrameElement()
        ..src = _blobUrl
        ..style.width = '100%'
        ..style.height = '100%'
        ..style.border = 'none'
        ..allowFullscreen = true;

      // Wait a bit for iframe to load
      _iframe?.onLoad.listen((_) {
        print('[PDF Preview] Iframe loaded successfully');
        if (mounted) {
          setState(() {
            _loading = false;
          });
        }
      });

      _iframe?.onError.listen((error) {
        print('[PDF Preview] Iframe load error: $error');
        if (mounted) {
          setState(() {
            _loading = false;
            _error = 'Failed to load PDF in iframe';
          });
        }
      });

      // Set loading to false after a short delay (iframe may not trigger onLoad)
      Future.delayed(const Duration(seconds: 1), () {
        if (mounted && _loading) {
          setState(() {
            _loading = false;
          });
        }
      });
    } catch (e, stackTrace) {
      print('[PDF Preview] Error loading PDF: $e');
      print('[PDF Preview] Stack trace: $stackTrace');
      setState(() {
        _loading = false;
        _error = 'Failed to load PDF: ${e.toString()}';
      });
    }
  }

  void _attachIframeToView(int viewId) {
    try {
      // Find the container div created by the view factory
      final container =
          html.document.getElementById('pdf-iframe-container-$viewId');
      if (container != null && _iframe != null) {
        // Clear and append iframe
        container.children.clear();
        container.append(_iframe!);
        print('[PDF Preview] Iframe attached to view $viewId');
      } else {
        print(
          '[PDF Preview] Warning: Could not find container for viewId $viewId or iframe is null. Attempting direct attachment.',
        );
        // Fallback: try to find by platform view selector if container not found
        html.window.requestAnimationFrame((_) {
          final platformView = html.document
              .querySelector('flt-platform-view[view-id="$viewId"]');
          if (platformView != null && _iframe != null) {
            var innerContainer = platformView.querySelector('div');
            if (innerContainer == null) {
              innerContainer = html.DivElement()
                ..style.width = '100%'
                ..style.height = '100%'
                ..style.margin = '0'
                ..style.padding = '0';
              platformView.append(innerContainer);
            }
            innerContainer.children.clear();
            innerContainer.append(_iframe!);
            print(
              '[PDF Preview] Iframe attached directly to platform view $viewId',
            );
          } else {
            print(
              '[PDF Preview] Critical: Could not attach iframe to any view for viewId $viewId',
            );
          }
        });
      }
    } catch (e, stackTrace) {
      print('[PDF Preview] Error attaching iframe to view: $e');
      print('[PDF Preview] Stack trace: $stackTrace');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            const Icon(Icons.picture_as_pdf, size: 48, color: Colors.redAccent),
            const SizedBox(height: 16),
            Text(
              'Failed to load PDF',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: Colors.redAccent),
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              alignment: WrapAlignment.center,
              children: <Widget>[
                ElevatedButton.icon(
                  onPressed: _loadPdf,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry'),
                ),
                OutlinedButton.icon(
                  onPressed: () {
                    widget.onDownload?.call('pdf', widget.downloadUrl);
                  },
                  icon: const Icon(Icons.download),
                  label: const Text('Download'),
                ),
              ],
            ),
          ],
        ),
      );
    }

    if (_iframe == null) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Initializing PDF viewer...'),
          ],
        ),
      );
    }

    return Column(
      children: <Widget>[
        _buildToolbar(context),
        const Divider(height: 1),
        Expanded(
          child: HtmlElementView(
            viewType: 'pdf-iframe-view',
            onPlatformViewCreated: (int viewId) {
              // Attach iframe after platform view is created
              html.window.requestAnimationFrame((_) {
                _attachIframeToView(viewId);
              });
            },
          ),
        ),
      ],
    );
  }

  Widget _buildToolbar(BuildContext context) => Container(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: <Widget>[
            const Text('PDF Viewer (Browser Native)'),
            const Spacer(),
            IconButton(
              tooltip: 'Download PDF',
              onPressed: () {
                widget.onDownload?.call('pdf', widget.downloadUrl);
              },
              icon: const Icon(Icons.download),
            ),
          ],
        ),
      );
}
