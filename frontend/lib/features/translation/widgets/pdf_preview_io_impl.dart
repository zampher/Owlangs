// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

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
  State<PdfPreview> createState() => _PdfPreviewIoState();
}

class _PdfPreviewIoState extends State<PdfPreview> {
  PdfControllerPinch? _controller;
  bool _loading = true;
  String? _error;
  int _currentPage = 1;
  int _totalPages = 0;
  bool _useHighFidelity = false;

  @override
  void initState() {
    super.initState();
    _loadPdf();
  }

  String _buildPdfUrl() {
    final uri = Uri.parse(widget.downloadUrl);
    final params = Map<String, String>.from(uri.queryParameters);
    if (_useHighFidelity) {
      params['renderer_type'] = 'typst_overlay';
    } else {
      params.remove('renderer_type');
    }
    return uri.replace(queryParameters: params).toString();
  }

  Future<void> _loadPdf() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final svc = TranslationService();
      final url = _buildPdfUrl();
      final data = await svc.downloadFile(url);
      final documentFuture = PdfDocument.openData(Uint8List.fromList(data));
      _controller?.dispose();
      _controller = PdfControllerPinch(document: documentFuture);
      setState(() {
        _loading = false;
        _totalPages = 0;
        _currentPage = 1;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
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

    return Column(
      children: <Widget>[
        _buildToolbar(context),
        const Divider(height: 1),
        Expanded(
          child: PdfViewPinch(
            controller: _controller!,
            padding: 16,
            onDocumentLoaded: (details) {
              setState(() {
                _totalPages = details.pagesCount;
              });
            },
            onPageChanged: (page) {
              setState(() {
                _currentPage = page;
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
            Text(
              'Page $_currentPage / $_totalPages',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const Spacer(),
            IconButton(
              tooltip: 'Previous page',
              onPressed: _currentPage > 1
                  ? () {
                      _controller?.previousPage(
                        duration: const Duration(milliseconds: 200),
                        curve: Curves.easeInOut,
                      );
                    }
                  : null,
              icon: const Icon(Icons.chevron_left),
            ),
            IconButton(
              tooltip: 'Next page',
              onPressed: _currentPage < _totalPages
                  ? () {
                      _controller?.nextPage(
                        duration: const Duration(milliseconds: 200),
                        curve: Curves.easeInOut,
                      );
                    }
                  : null,
              icon: const Icon(Icons.chevron_right),
            ),
            const SizedBox(width: 8),
            IconButton(
              tooltip: _useHighFidelity
                  ? 'Switch to Standard PDF'
                  : 'Switch to High-Fidelity PDF',
              onPressed: () {
                setState(() {
                  _useHighFidelity = !_useHighFidelity;
                });
                _loadPdf();
              },
              icon: Icon(
                _useHighFidelity ? Icons.high_quality : Icons.hd,
                color: _useHighFidelity ? Colors.blue : null,
              ),
            ),
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
