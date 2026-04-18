// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../../../shared/widgets/unified_preview.dart';

/// Translation Preview Content Widget
/// Loads and displays preview content (MD/HTML) with format parameters
/// Uses UnifiedPreview widget for rendering
class TranslationPreviewContentWidget extends ConsumerStatefulWidget {
  const TranslationPreviewContentWidget({
    required this.taskId,
    super.key,
    this.flowId,
    this.downloads,
    this.onDownload,
    this.tableFormat,
    this.equationFormat,
  });
  final String taskId;
  final String? flowId;
  final Map<String, String>? downloads;
  final Function(String fileType, String url)? onDownload;
  final String? tableFormat; // Selected table format: 'image' or 'html'
  final String? equationFormat;

  @override
  ConsumerState<TranslationPreviewContentWidget> createState() =>
      _TranslationPreviewContentWidgetState();
}

class _TranslationPreviewContentWidgetState
    extends ConsumerState<TranslationPreviewContentWidget> {
  String? _previewContent;
  bool _loadingPreview = false;
  Map<String, Map<String, String>>? _imageDataMap;
  String _previewType = 'md'; // Use markdown preview like before

  @override
  void initState() {
    super.initState();
    AppLogger.log(
      'TranslationPreviewContentWidget',
      'initState: taskId=${widget.taskId}, flowId=${widget.flowId}, downloads=${widget.downloads?.keys.toList()}',
      level: LogLevel.info,
    );
    _loadPreviewContent();
  }

  @override
  void didUpdateWidget(TranslationPreviewContentWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Reload if format parameters changed
    if (oldWidget.tableFormat != widget.tableFormat ||
        oldWidget.equationFormat != widget.equationFormat) {
      AppLogger.log(
        'TranslationPreviewContentWidget',
        'Format parameters changed, reloading: tableFormat=${widget.tableFormat}, equationFormat=${widget.equationFormat}',
        level: LogLevel.info,
      );
      _loadPreviewContent();
    }
  }

  /// Load preview content (MD or HTML, prefer MD like before)
  Future<void> _loadPreviewContent() async {
    if (_loadingPreview) {
      AppLogger.log(
        'TranslationPreviewContentWidget',
        '_loadPreviewContent: Already loading, skipping',
      );
      return;
    }

    AppLogger.log(
      'TranslationPreviewContentWidget',
      '_loadPreviewContent: Starting, taskId=${widget.taskId}, downloads=${widget.downloads?.keys.toList()}',
      level: LogLevel.info,
    );

    setState(() {
      _loadingPreview = true;
    });

    try {
      final svc = TranslationService();

      // Try markdown first (like the old markdown preview)
      String? downloadUrl;
      String contentType = 'md';

      if (widget.downloads != null && widget.downloads!.containsKey('md')) {
        downloadUrl = svc.buildDownloadUrl(widget.taskId, 'md');
        AppLogger.log(
          'TranslationPreviewContentWidget',
          'Using markdown download: $downloadUrl',
          level: LogLevel.info,
        );
      } else if (widget.downloads != null &&
          widget.downloads!.containsKey('html')) {
        // Fallback to HTML if markdown not available
        downloadUrl = svc.buildDownloadUrl(widget.taskId, 'html');
        contentType = 'html';
        AppLogger.log(
          'TranslationPreviewContentWidget',
          'Using HTML download (fallback): $downloadUrl',
          level: LogLevel.info,
        );
      } else {
        AppLogger.log(
          'TranslationPreviewContentWidget',
          'ERROR: No markdown or HTML download available. Downloads: ${widget.downloads?.keys.toList()}',
          level: LogLevel.error,
        );
        throw Exception('No markdown or HTML download available');
      }

      // Add format parameters as query parameters
      final uri = Uri.parse(downloadUrl);
      final queryParams = Map<String, String>.from(uri.queryParameters);

      // Use provided format parameters or default to 'image'
      final tableFormat = widget.tableFormat ?? 'image';
      final equationFormat = widget.equationFormat ?? 'image';

      queryParams['table_body_format'] = tableFormat;
      queryParams['equation_format'] = equationFormat;

      downloadUrl = uri.replace(queryParameters: queryParams).toString();
      AppLogger.log(
        'TranslationPreviewContentWidget',
        'Final download URL: $downloadUrl, tableFormat=$tableFormat, equationFormat=$equationFormat',
        level: LogLevel.info,
      );

      // Download preview content
      AppLogger.log(
        'TranslationPreviewContentWidget',
        'Downloading preview content...',
      );
      final bytes = await svc.downloadFile(downloadUrl);
      AppLogger.log(
        'TranslationPreviewContentWidget',
        'Downloaded ${bytes.length} bytes',
        level: LogLevel.info,
      );

      if (bytes.isEmpty) {
        AppLogger.log(
          'TranslationPreviewContentWidget',
          'ERROR: Preview content is empty',
          level: LogLevel.error,
        );
        throw Exception('Preview content is empty');
      }

      // Decode content
      final content = utf8.decode(bytes);
      AppLogger.log(
        'TranslationPreviewContentWidget',
        'Decoded content length: ${content.length} characters',
      );

      // Refresh status to get updated image_data_map
      try {
        AppLogger.log(
          'TranslationPreviewContentWidget',
          'Refreshing status to get image_data_map...',
        );
        final status = await svc.getStatus(widget.taskId);
        Map<String, Map<String, String>>? imageMap;
        if (status['image_data_map'] != null) {
          final rawMap = status['image_data_map'] as Map;
          AppLogger.log(
            'TranslationPreviewContentWidget',
            'Found image_data_map with ${rawMap.length} entries',
            level: LogLevel.info,
          );
          imageMap = rawMap.map((k, v) {
            final key = k.toString();
            if (v is Map) {
              final valueMap = v.cast<String, dynamic>();
              final dataValue = valueMap['data']?.toString() ?? '';
              final altValue = valueMap['alt']?.toString() ?? '';
              return MapEntry(key, <String, String>{
                'data': dataValue,
                'alt': altValue,
              });
            }
            return MapEntry(key, <String, String>{'data': '', 'alt': ''});
          });
        } else {
          AppLogger.log(
            'TranslationPreviewContentWidget',
            'No image_data_map in status',
          );
        }

        if (mounted) {
          setState(() {
            _previewContent = content;
            _previewType = contentType;
            _imageDataMap = imageMap;
            _loadingPreview = false;
          });
          AppLogger.log(
            'TranslationPreviewContentWidget',
            'Preview content loaded successfully: contentType=$contentType, imageMap size=${imageMap?.length ?? 0}',
            level: LogLevel.info,
          );
        }
      } catch (e) {
        AppLogger.log(
          'TranslationPreviewContentWidget',
          'WARNING: Failed to refresh status, but using content anyway: $e',
          level: LogLevel.warn,
        );
        // If status refresh fails, still use the content
        if (mounted) {
          setState(() {
            _previewContent = content;
            _previewType = contentType;
            _loadingPreview = false;
          });
          AppLogger.log(
            'TranslationPreviewContentWidget',
            'Preview content loaded (without image_data_map)',
            level: LogLevel.info,
          );
        }
      }
    } catch (e, stackTrace) {
      AppLogger.log(
        'TranslationPreviewContentWidget',
        'ERROR: Failed to load preview content: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        setState(() {
          _loadingPreview = false;
        });
        // Do not show a global error message here.
        // Preview failures are transient and later steps (or manual refresh)
        // may succeed; keeping a persistent snackbar would be confusing.
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loadingPreview) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: CircularProgressIndicator(),
        ),
      );
    }

    if (_previewContent == null) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(32),
          child: Text('Preview will be loaded...'),
        ),
      );
    }

    // Use UnifiedPreview widget for consistent rendering (supports both MD and HTML)
    return UnifiedPreview(
      content: _previewContent!,
      contentType: _previewType,
      imageDataMap: _imageDataMap,
      taskId: widget.taskId,
    );
  }
}
