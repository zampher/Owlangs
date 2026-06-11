// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../../../shared/services/translation_service.dart';
import '../utils/app_logger.dart';
import '../utils/message_service.dart';
import '../utils/dialog_helper.dart';
import '../../features/translation/providers/format_settings_provider.dart';
import 'unified_preview.dart';
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'dart:io' if (dart.library.html) '../utils/io_stub.dart' as io;

void _unifiedPreviewWidgetLog(
  String message, {
  LogLevel level = LogLevel.debug,
}) {
  AppLogger.log('UnifiedPreviewWidget', message, level: level);
}

/// Unified preview widget with toolbar (Settings and Download buttons)
/// Can be used for both Convert and Translation Preview
class UnifiedPreviewWidget extends ConsumerStatefulWidget {
  const UnifiedPreviewWidget({
    required this.taskId,
    required this.downloads,
    required this.title,
    required this.icon,
    super.key,
    this.flowId,
    this.onDownload,
    this.previewType = 'html',
    this.enableStatusPolling = false,
    this.showProgressBar = false,
    this.onCancel,
    this.onStatusUpdate,
  });

  /// Task ID
  final String taskId;

  /// Flow ID (optional)
  final String? flowId;

  /// Download URLs by file type
  final Map<String, String> downloads;

  /// Download callback
  final Function(String fileType, String url)? onDownload;

  /// Title to display in toolbar (e.g., "Convert" or "Translation Preview")
  final String title;

  /// Icon to display in toolbar
  final IconData icon;

  /// Preview type: 'html' or 'md' (default: 'html')
  final String previewType;

  /// Enable status polling (for Convert, not needed for Translation Preview)
  final bool enableStatusPolling;

  /// Show progress bar (for Convert, not needed for Translation Preview)
  final bool showProgressBar;

  /// Cancel callback (for Convert, not needed for Translation Preview)
  /// Should return Future<void> to handle async cancellation
  final Future<void> Function()? onCancel;

  /// Status update callback (for Convert, to update translation state)
  /// Called when status changes (completed, failed, cancelled)
  final void Function(
    Map<String, dynamic> status,
    Map<String, String> downloads,
  )? onStatusUpdate;

  @override
  ConsumerState<UnifiedPreviewWidget> createState() =>
      _UnifiedPreviewWidgetState();
}

class _UnifiedPreviewWidgetState extends ConsumerState<UnifiedPreviewWidget> {
  Timer? _statusTimer;
  bool _isPolling = false;
  Map<String, dynamic>? _currentStatus;
  Map<String, String> _currentDownloads = <String, String>{};
  // Format settings are now managed by formatSettingsProviderFamily
  // Removed: String? _selectedTableFormat;
  // Removed: String? _selectedEquationFormat;
  String? _previewContent; // MD or HTML preview content
  String _previewType = 'html'; // Use HTML preview by default
  bool _loadingPreview = false; // Track preview loading state
  Map<String, Map<String, String>>? _imageDataMap; // Image data map for preview
  final Map<String, bool> _downloading =
      <String, bool>{}; // Track downloading state for each format
  bool _isCancelling = false;
  bool _hasShownFinalStatusMessage = false;
  int? _progress;
  String? _statusText;
  String? _displayMessage;
  FormatSettings?
      _lastFormatSettings; // Track last format settings to detect changes

  bool get _isPdfWorkflow => widget.downloads.containsKey('pdf');

  @override
  void initState() {
    super.initState();
    _currentDownloads = widget.downloads;
    _previewType = widget.previewType;
    if (widget.enableStatusPolling) {
      _startStatusPolling();
    } else {
      _loadPreviewContent();
    }
  }

  @override
  void didUpdateWidget(UnifiedPreviewWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Update downloads if widget.downloads changed
    if (widget.downloads != oldWidget.downloads) {
      _currentDownloads = widget.downloads;
      if (_previewContent == null) {
        _loadPreviewContent();
      }
    }
    // Update preview type if changed
    if (widget.previewType != oldWidget.previewType) {
      _previewType = widget.previewType;
      _loadPreviewContent();
    }
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    super.dispose();
  }

  void _startStatusPolling() {
    if (_isPolling) return;
    _isPolling = true;

    _statusTimer =
        Timer.periodic(const Duration(seconds: 2), (Timer timer) async {
      if (!mounted) {
        timer.cancel();
        return;
      }

      try {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> status = await svc.getStatus(widget.taskId);
        final String currentStatus =
            (status['status'] ?? '').toString().toLowerCase();

        if (mounted) {
          setState(() {
            _currentStatus = status;
            _statusText = status['status']?.toString();
            _displayMessage = status['message']?.toString();
            _progress = status['progress'] as int?;

            // Update downloads from status
            if (status['downloads'] != null) {
              final Map<dynamic, dynamic> rawDownloads =
                  status['downloads'] as Map;
              _currentDownloads = rawDownloads.map(
                (k, v) => MapEntry(k.toString(), v.toString()),
              );
            }
          });
        }

        // Handle final status
        if (currentStatus == 'completed' ||
            currentStatus == 'failed' ||
            currentStatus == 'cancelled') {
          timer.cancel();
          _isPolling = false;
          if (mounted) {
            _handleFinalStatus(status);
            // Call status update callback if provided
            if (widget.onStatusUpdate != null) {
              final Map<dynamic, dynamic>? rawDownloads =
                  status['downloads'] as Map?;
              final Map<String, String> downloads = rawDownloads != null
                  ? rawDownloads.map(
                      (k, v) => MapEntry(k.toString(), v.toString()),
                    )
                  : <String, String>{};
              widget.onStatusUpdate!(status, downloads);
            }
            // Only load preview if completed
            if (currentStatus == 'completed') {
              _loadPreviewContent();
            }
          }
        }
      } catch (e) {
        _unifiedPreviewWidgetLog(
          'Status polling error: $e',
          level: LogLevel.warn,
        );
      }
    });
  }

  void _handleFinalStatus(Map<String, dynamic> status) {
    if (_hasShownFinalStatusMessage) return;
    final String statusText = (status['status'] ?? '').toString().toLowerCase();
    if (statusText != 'failed') {
      return;
    }
    final String message = status['message']?.toString() ?? '';
    final String errorMessage = status['error']?.toString() ?? '';
    final String displayMessage = message.isNotEmpty
        ? message
        : (errorMessage.isNotEmpty ? errorMessage : 'Operation failed.');
    MessageService.showError(context, displayMessage);
    _hasShownFinalStatusMessage = true;
  }

  /// Load preview content (MD or HTML)
  Future<void> _loadPreviewContent() async {
    if (_loadingPreview) return;

    setState(() {
      _loadingPreview = true;
    });

    try {
      // Refresh status first to get latest image_data_map (after format change)
      try {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> status = await svc.getStatus(widget.taskId);
        if (mounted) {
          setState(() {
            _currentStatus = status;
          });
          _unifiedPreviewWidgetLog(
            '[Preview] Refreshed status, image_data_map count: ${status['image_data_map'] != null ? (status['image_data_map'] as Map).length : 0}',
          );
        }
      } catch (e) {
        _unifiedPreviewWidgetLog(
          '[Preview] Failed to refresh status: $e',
          level: LogLevel.warn,
        );
      }

      final TranslationService svc = TranslationService();

      // Try to get from downloads first, then build URL directly if not available
      String? downloadUrl;
      var contentType = _previewType;

      if (_currentDownloads.containsKey(_previewType)) {
        downloadUrl = svc.buildDownloadUrl(widget.taskId, _previewType);
        _unifiedPreviewWidgetLog(
          'Using $_previewType download: $downloadUrl',
          level: LogLevel.info,
        );
      } else if (_previewType == 'md' &&
          _currentDownloads.containsKey('html')) {
        // Fallback to HTML if markdown not available
        downloadUrl = svc.buildDownloadUrl(widget.taskId, 'html');
        contentType = 'html';
        _unifiedPreviewWidgetLog(
          'Using HTML download (fallback): $downloadUrl',
          level: LogLevel.info,
        );
      } else if (_previewType == 'html' &&
          _currentDownloads.containsKey('md')) {
        // Fallback to MD if HTML not available
        downloadUrl = svc.buildDownloadUrl(widget.taskId, 'md');
        contentType = 'md';
        _unifiedPreviewWidgetLog(
          'Using MD download (fallback): $downloadUrl',
          level: LogLevel.info,
        );
      } else {
        // If not in downloads, try to build URL directly (backend may have it)
        _unifiedPreviewWidgetLog(
          'No $_previewType in downloads, trying to build URL directly...',
          level: LogLevel.info,
        );
        try {
          downloadUrl = svc.buildDownloadUrl(widget.taskId, _previewType);
          _unifiedPreviewWidgetLog(
            'Built $_previewType download URL: $downloadUrl',
            level: LogLevel.info,
          );
        } catch (e) {
          // If preferred type fails, try fallback
          final String fallbackType = _previewType == 'md' ? 'html' : 'md';
          try {
            downloadUrl = svc.buildDownloadUrl(widget.taskId, fallbackType);
            contentType = fallbackType;
            _unifiedPreviewWidgetLog(
              'Built $fallbackType download URL (fallback): $downloadUrl',
              level: LogLevel.info,
            );
          } catch (e2) {
            _unifiedPreviewWidgetLog(
              'Failed to build download URL: $e2',
              level: LogLevel.error,
            );
            throw Exception('Failed to build download URL: $e2');
          }
        }
      }

      // Add format parameters as query parameters
      final Uri uri = Uri.parse(downloadUrl);
      final Map<String, String> queryParams =
          Map<String, String>.from(uri.queryParameters);

      // Get format settings from provider (with backend defaults)
      final FormatSettings formatSettings = ref.read(
        formatSettingsProviderFamily(widget.taskId),
      );

      queryParams['table_body_format'] =
          formatSettings.getTableFormat(isPdfWorkflow: _isPdfWorkflow);
      queryParams['equation_format'] =
          formatSettings.getEquationFormat(isPdfWorkflow: _isPdfWorkflow);
      queryParams['chart_body_format'] =
          formatSettings.getChartFormat(isPdfWorkflow: _isPdfWorkflow);

      if (formatSettings.bilingualExport == true) {
        queryParams['bilingual_export'] = 'true';
        queryParams['bilingual_order'] =
            formatSettings.bilingualOrder ?? 'target_after_source';
      }

      downloadUrl = uri.replace(queryParameters: queryParams).toString();
      _unifiedPreviewWidgetLog(
        'Final download URL: $downloadUrl, tableFormat=${formatSettings.getTableFormat(isPdfWorkflow: _isPdfWorkflow)}, equationFormat=${formatSettings.getEquationFormat(isPdfWorkflow: _isPdfWorkflow)}, chartFormat=${formatSettings.getChartFormat(isPdfWorkflow: _isPdfWorkflow)}',
        level: LogLevel.info,
      );

      // Download preview content
      _unifiedPreviewWidgetLog(
        'Downloading preview content...',
      );
      final List<int> bytes = await svc.downloadFile(downloadUrl);
      _unifiedPreviewWidgetLog(
        'Downloaded ${bytes.length} bytes',
        level: LogLevel.info,
      );

      if (bytes.isEmpty) {
        _unifiedPreviewWidgetLog(
          'ERROR: Preview content is empty',
          level: LogLevel.error,
        );
        throw Exception('Preview content is empty');
      }

      // Decode content
      final String content = utf8.decode(bytes);
      _unifiedPreviewWidgetLog(
        'Decoded content length: ${content.length} characters',
      );

      // Refresh status to get updated image_data_map (which may have been updated during HTML generation)
      try {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> updatedStatus =
            await svc.getStatus(widget.taskId);
        if (mounted) {
          setState(() {
            _currentStatus = updatedStatus;
          });
        }
      } catch (e) {
        _unifiedPreviewWidgetLog(
          '[Preview] Failed to refresh status after download: $e',
          level: LogLevel.warn,
        );
      }

      // Get image data map from status if available
      final Map<String, dynamic>? status = _currentStatus;
      Map<String, Map<String, String>>? imageMap;
      if (status != null && status['image_data_map'] != null) {
        try {
          final Map<dynamic, dynamic> rawMap = status['image_data_map'] as Map;
          imageMap = rawMap.map((k, v) {
            final String key = k.toString();
            if (v is Map) {
              final Map<String, dynamic> valueMap = v.cast<String, dynamic>();
              final String dataValue = valueMap['data']?.toString() ?? '';
              final String altValue = valueMap['alt']?.toString() ?? '';

              // If data is empty, try to preserve existing data from _imageDataMap
              var finalDataValue = dataValue;
              if (dataValue.isEmpty &&
                  _imageDataMap != null &&
                  _imageDataMap!.containsKey(key)) {
                final String existingData =
                    _imageDataMap![key]?['data']?.toString() ?? '';
                if (existingData.isNotEmpty) {
                  finalDataValue = existingData;
                }
              }

              return MapEntry(key, <String, String>{
                'data': finalDataValue,
                'alt': altValue,
              });
            }
            return MapEntry(key, <String, String>{'data': '', 'alt': ''});
          });
          _unifiedPreviewWidgetLog(
            '[Preview] Loaded ${imageMap.length} images from image_data_map',
          );
        } catch (e, stackTrace) {
          _unifiedPreviewWidgetLog(
            'Failed to parse image_data_map: $e\n$stackTrace',
            level: LogLevel.error,
          );
        }
      }

      if (mounted) {
        setState(() {
          _previewContent = content;
          _previewType = contentType;
          _imageDataMap = imageMap;
          _loadingPreview = false;
        });
        _unifiedPreviewWidgetLog(
          '[Preview] Loaded $_previewType successfully, length: ${content.length}',
        );
      }
    } catch (e, stackTrace) {
      _unifiedPreviewWidgetLog(
        'ERROR: Failed to load preview content: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        setState(() {
          _loadingPreview = false;
        });
        MessageService.showError(context, 'Failed to load preview: $e');
      }
    }
  }

  /// Show preview settings dialog (for table, equation, and chart formats)
  Future<void> _showPreviewSettingsDialog(
    bool hasTables,
    bool hasInterlineEquations,
    bool hasCharts,
  ) async {
    _unifiedPreviewWidgetLog('[Dialog] Showing preview settings dialog');

    try {
      // Get current format settings from provider
      final FormatSettings formatSettings = ref.read(
        formatSettingsProviderFamily(widget.taskId),
      );
      // Create state variables for dialog with current settings or defaults
      var tableFormat =
          formatSettings.getTableFormat(isPdfWorkflow: _isPdfWorkflow);
      var equationFormat =
          formatSettings.getEquationFormat(isPdfWorkflow: _isPdfWorkflow);
      var chartFormat =
          formatSettings.getChartFormat(isPdfWorkflow: _isPdfWorkflow);

      await DialogHelper.showGeneralDialog(
        context: context,
        barrierColor: Colors.black54,
        barrierLabel: 'Preview Settings',
        useRootNavigator: true,
        pageBuilder: (
          dialogContext,
          animation,
          secondaryAnimation,
        ) =>
            StatefulBuilder(
          builder: (BuildContext context, setDialogState) => Material(
            type: MaterialType.transparency,
            child: AlertDialog(
              title: const Text('Preview Settings'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    if (hasTables) ...<Widget>[
                      const Text(
                        'Table Format:',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      RadioListTile<String>(
                        title: const Text('Image'),
                        subtitle: const Text('Display tables as images'),
                        value: 'image',
                        groupValue: tableFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              tableFormat = value;
                            });
                          }
                        },
                      ),
                      RadioListTile<String>(
                        title: const Text('HTML'),
                        subtitle: const Text('Display tables as HTML'),
                        value: 'html',
                        groupValue: tableFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              tableFormat = value;
                            });
                          }
                        },
                      ),
                      const SizedBox(height: 16),
                    ],
                    if (hasInterlineEquations) ...<Widget>[
                      const Text(
                        'Equation Format:',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      RadioListTile<String>(
                        title: const Text('Image'),
                        subtitle: const Text('Display equations as images'),
                        value: 'image',
                        groupValue: equationFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              equationFormat = value;
                            });
                          }
                        },
                      ),
                      RadioListTile<String>(
                        title: const Text('LaTeX'),
                        subtitle: const Text('Display equations as LaTeX text'),
                        value: 'text',
                        groupValue: equationFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              equationFormat = value;
                            });
                          }
                        },
                      ),
                    ],
                    if (hasCharts) ...<Widget>[
                      const SizedBox(height: 16),
                      const Text(
                        'Chart Format:',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      RadioListTile<String>(
                        title: const Text('Image'),
                        subtitle: const Text('Display charts as images (recommended)'),
                        value: 'image',
                        groupValue: chartFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              chartFormat = value;
                            });
                          }
                        },
                      ),
                      RadioListTile<String>(
                        title: const Text('HTML'),
                        subtitle: const Text('Display charts as HTML tables'),
                        value: 'html',
                        groupValue: chartFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              chartFormat = value;
                            });
                          }
                        },
                      ),
                    ],
                  ],
                ),
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
                TextButton.icon(
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: const Text('Save as Default'),
                  onPressed: () async {
                    // Apply settings to provider first
                    final FormatSettingsNotifier formatNotifier = ref.read(
                      formatSettingsProviderFamily(widget.taskId).notifier,
                    );
                    formatNotifier.setFormats(
                      tableFormat: tableFormat,
                      equationFormat: equationFormat,
                      chartFormat: chartFormat,
                    );
                    // Save as user defaults
                    await formatNotifier.saveAsUserDefaults();
                    // Use dialogContext instead of context to show message in dialog
                    MessageService.showSuccess(
                      context,
                      'Default format settings saved',
                    );
                  },
                ),
                ElevatedButton(
                  onPressed: () {
                    Navigator.of(context).pop();
                    // Apply settings to provider
                    final FormatSettingsNotifier formatNotifier = ref.read(
                      formatSettingsProviderFamily(widget.taskId).notifier,
                    );
                    formatNotifier.setFormats(
                      tableFormat: tableFormat,
                      equationFormat: equationFormat,
                      chartFormat: chartFormat,
                    );
                    // Reload preview with new formats after dialog closes
                    // Use addPostFrameCallback to ensure state is updated before reloading
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      _loadPreviewContent();
                    });
                  },
                  child: const Text('Apply'),
                ),
              ],
            ),
          ),
        ),
        transitionBuilder: (
          BuildContext context,
          Animation<double> animation,
          Animation<double> secondaryAnimation,
          Widget child,
        ) =>
            FadeTransition(
          opacity: animation,
          child: child,
        ),
      );
    } catch (e, stackTrace) {
      _unifiedPreviewWidgetLog(
        'Error showing preview settings dialog: $e\n$stackTrace',
        level: LogLevel.error,
      );
    }
  }

  /// Show download dialog with format settings
  Future<void> _showDownloadDialog() async {
    _unifiedPreviewWidgetLog('[Dialog] Showing download dialog');

    try {
      final List<Map<String, dynamic>> downloadOptions =
          <Map<String, dynamic>>[];

      // Check available download formats
      // For MD, add two options: embedded and with images folder
      if (_currentDownloads.containsKey('md')) {
        downloadOptions.add(<String, dynamic>{
          'type': 'md',
          'label': 'MD (Embedded Images)',
          'embedImages': true,
        });
        downloadOptions.add(<String, dynamic>{
          'type': 'md',
          'label': 'MD (With Images Folder)',
          'embedImages': false,
        });
      }
      if (_currentDownloads.containsKey('html')) {
        downloadOptions.add(<String, dynamic>{
          'type': 'html',
          'label': 'HTML',
          'embedImages': null,
        });
      }
      if (_currentDownloads.containsKey('docx')) {
        downloadOptions.add(<String, dynamic>{
          'type': 'docx',
          'label': 'DOCX',
          'embedImages': null,
        });
      }
      // For Convert, skip PDF download option (not supported yet)
      if (_currentDownloads.containsKey('pdf') && !widget.enableStatusPolling) {
        downloadOptions.add(<String, dynamic>{
          'type': 'pdf',
          'label': 'PDF',
          'embedImages': null,
        });
      }
      if (_currentDownloads.containsKey('pptx')) {
        downloadOptions.add(<String, dynamic>{
          'type': 'pptx',
          'label': 'PPTX',
          'embedImages': null,
        });
      }
      if (_currentDownloads.containsKey('xlsx')) {
        downloadOptions.add(<String, dynamic>{
          'type': 'xlsx',
          'label': 'XLSX',
          'embedImages': null,
        });
      }
      if (_currentDownloads.containsKey('ts')) {
        downloadOptions.add(<String, dynamic>{
          'type': 'ts',
          'label': 'TS',
          'embedImages': null,
        });
      }

      if (downloadOptions.isEmpty) {
        MessageService.showWarning(context, 'No download formats available');
        return;
      }

      // Get current status to check for tables, equations, charts
      final Map<String, dynamic>? status = _currentStatus;
      final bool hasTables = status?['has_tables'] == true;
      final bool hasInterlineEquations = status?['has_interline_equations'] == true;
      final bool hasCharts = status?['has_charts'] == true;

      // Get current format settings from provider
      final FormatSettings formatSettings = ref.read(
        formatSettingsProviderFamily(widget.taskId),
      );

      // Create state variables for dialog with current settings
      var tableFormat = formatSettings.getTableFormat(isPdfWorkflow: _isPdfWorkflow);
      var equationFormat = formatSettings.getEquationFormat(isPdfWorkflow: _isPdfWorkflow);
      var chartFormat = formatSettings.getChartFormat(isPdfWorkflow: _isPdfWorkflow);

      await DialogHelper.showDialog(
        context: context,
        builder: (BuildContext context) => StatefulBuilder(
          builder: (BuildContext context, StateSetter setDialogState) => AlertDialog(
            title: const Text('Export Document'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  // Format Settings Section (only for PDF workflow)
                  if (_isPdfWorkflow) ...<Widget>[
                    const Text(
                      'Format Settings',
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
                    ),
                    const SizedBox(height: 8),
                    if (hasTables) ...<Widget>[
                      const Text(
                        'Table Format:',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      RadioListTile<String>(
                        title: const Text('Image'),
                        subtitle: const Text('Export tables as images'),
                        value: 'image',
                        groupValue: tableFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              tableFormat = value;
                            });
                          }
                        },
                      ),
                      RadioListTile<String>(
                        title: const Text('HTML'),
                        subtitle: const Text('Export tables as HTML'),
                        value: 'html',
                        groupValue: tableFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              tableFormat = value;
                            });
                          }
                        },
                      ),
                      const SizedBox(height: 8),
                    ],
                    if (hasInterlineEquations) ...<Widget>[
                      const Text(
                        'Equation Format:',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      RadioListTile<String>(
                        title: const Text('Image'),
                        subtitle: const Text('Export equations as images (best quality)'),
                        value: 'image',
                        groupValue: equationFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              equationFormat = value;
                            });
                          }
                        },
                      ),
                      RadioListTile<String>(
                        title: const Text('LaTeX'),
                        subtitle: const Text('Export equations as LaTeX text'),
                        value: 'text',
                        groupValue: equationFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              equationFormat = value;
                            });
                          }
                        },
                      ),
                      const SizedBox(height: 8),
                    ],
                    if (hasCharts) ...<Widget>[
                      const Text(
                        'Chart Format:',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      RadioListTile<String>(
                        title: const Text('Image'),
                        subtitle: const Text('Export charts as images (recommended)'),
                        value: 'image',
                        groupValue: chartFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              chartFormat = value;
                            });
                          }
                        },
                      ),
                      RadioListTile<String>(
                        title: const Text('HTML'),
                        subtitle: const Text('Export charts as HTML tables'),
                        value: 'html',
                        groupValue: chartFormat,
                        onChanged: (value) {
                          if (value != null) {
                            setDialogState(() {
                              chartFormat = value;
                            });
                          }
                        },
                      ),
                      const SizedBox(height: 8),
                    ],
                    const Divider(),
                    const SizedBox(height: 8),
                  ],
                  const Text(
                    'Export Format:',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
                  ),
                  const SizedBox(height: 8),
                  ...downloadOptions.map((Map<String, dynamic> option) {
                    final String fileType = option['type'] as String;
                    final String label = option['label'] as String;
                    final bool? embedImages = option['embedImages'] as bool?;
                    final String downloadKey = embedImages != null
                        ? '${fileType}_${embedImages ? 'embedded' : 'with_images'}'
                        : fileType;
                    final bool isFormatDownloading =
                        _downloading[downloadKey] ?? false;
                    return ListTile(
                      enabled: !isFormatDownloading,
                      leading: isFormatDownloading
                          ? const SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Icon(_getFormatIcon(fileType)),
                      title: Text(label),
                      onTap: isFormatDownloading
                          ? null
                          : () {
                              // Apply format settings to provider before download
                              if (_isPdfWorkflow) {
                                final FormatSettingsNotifier formatNotifier = ref.read(
                                  formatSettingsProviderFamily(widget.taskId).notifier,
                                );
                                formatNotifier.setFormats(
                                  tableFormat: tableFormat,
                                  equationFormat: equationFormat,
                                  chartFormat: chartFormat,
                                );
                              }
                              Navigator.of(context).pop();
                              _handleDownload(fileType, embedImages: embedImages);
                            },
                    );
                  }).toList(),
                ],
              ),
            ),
            actions: <Widget>[
              if (_isPdfWorkflow)
                TextButton.icon(
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: const Text('Save as Default'),
                  onPressed: () async {
                    // Apply settings to provider
                    final FormatSettingsNotifier formatNotifier = ref.read(
                      formatSettingsProviderFamily(widget.taskId).notifier,
                    );
                    formatNotifier.setFormats(
                      tableFormat: tableFormat,
                      equationFormat: equationFormat,
                      chartFormat: chartFormat,
                    );
                    // Save as user defaults
                    await formatNotifier.saveAsUserDefaults();
                    if (context.mounted) {
                      MessageService.showSuccess(
                        context,
                        'Default format settings saved',
                      );
                    }
                  },
                ),
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
            ],
          ),
        ),
      );
    } catch (e, stackTrace) {
      _unifiedPreviewWidgetLog(
        'Error showing download dialog: $e\n$stackTrace',
        level: LogLevel.error,
      );
    }
  }

  /// Handle download
  Future<void> _handleDownload(String fileType, {bool? embedImages}) async {
    if (widget.onDownload != null) {
      try {
        final TranslationService svc = TranslationService();
        var downloadUrl = svc.buildDownloadUrl(widget.taskId, fileType);

        // Add format parameters as query parameters for MD, HTML, DOCX, PDF
        // Use default format settings (image for both table and equation) to match preview
        if (fileType == 'md' ||
            fileType == 'html' ||
            fileType == 'docx' ||
            fileType == 'pdf') {
          final Uri uri = Uri.parse(downloadUrl);
          final Map<String, String> queryParams =
              Map<String, String>.from(uri.queryParameters);

          // Get format settings from provider (with backend defaults)
          final FormatSettings formatSettings = ref.read(
            formatSettingsProviderFamily(widget.taskId),
          );

          queryParams['table_body_format'] =
              formatSettings.getTableFormat(isPdfWorkflow: _isPdfWorkflow);
          queryParams['equation_format'] =
              formatSettings.getEquationFormat(isPdfWorkflow: _isPdfWorkflow);
          queryParams['chart_body_format'] =
              formatSettings.getChartFormat(isPdfWorkflow: _isPdfWorkflow);

          // For MD downloads, add embed_images parameter
          if (fileType == 'md' && embedImages != null) {
            queryParams['embed_images'] = embedImages.toString();
          }

          if (formatSettings.bilingualExport == true) {
            queryParams['bilingual_export'] = 'true';
            queryParams['bilingual_order'] =
                formatSettings.bilingualOrder ?? 'target_after_source';
            if (formatSettings.sourceTextItalic != null) {
              queryParams['source_text_italic'] =
                  formatSettings.sourceTextItalic.toString();
            }
            if (formatSettings.sourceTextColor != null) {
              queryParams['source_text_color'] =
                  formatSettings.sourceTextColor!;
            }
            if (formatSettings.targetTextItalic != null) {
              queryParams['target_text_italic'] =
                  formatSettings.targetTextItalic.toString();
            }
            if (formatSettings.targetTextColor != null &&
                formatSettings.targetTextColor!.isNotEmpty) {
              queryParams['target_text_color'] =
                  formatSettings.targetTextColor!;
            }
          }

          downloadUrl = uri.replace(queryParameters: queryParams).toString();
        }

        await widget.onDownload!(fileType, downloadUrl);
      } catch (e) {
        MessageService.showError(context, 'Failed to download: $e');
      }
      return;
    }

    // Fallback: direct download
    final String downloadKey = embedImages != null
        ? '${fileType}_${embedImages ? 'embedded' : 'with_images'}'
        : fileType;
    if (_downloading[downloadKey] ?? false) {
      return;
    }

    setState(() {
      _downloading[downloadKey] = true;
    });

    try {
      final TranslationService svc = TranslationService();
      var downloadUrl = svc.buildDownloadUrl(widget.taskId, fileType);

      // Add format parameters as query parameters for MD, HTML, DOCX, PDF
      // Use default format settings (image for both table and equation) to match preview
      if (fileType == 'md' ||
          fileType == 'html' ||
          fileType == 'docx' ||
          fileType == 'pdf') {
        final Uri uri = Uri.parse(downloadUrl);
        final Map<String, String> queryParams =
            Map<String, String>.from(uri.queryParameters);

        // Get format settings from provider (with backend defaults)
        final FormatSettings formatSettings = ref.read(
          formatSettingsProviderFamily(widget.taskId),
        );

        queryParams['table_body_format'] =
            formatSettings.getTableFormat(isPdfWorkflow: _isPdfWorkflow);
        queryParams['equation_format'] =
            formatSettings.getEquationFormat(isPdfWorkflow: _isPdfWorkflow);
        queryParams['chart_body_format'] =
            formatSettings.getChartFormat(isPdfWorkflow: _isPdfWorkflow);

        // For MD downloads, add embed_images parameter
        if (fileType == 'md' && embedImages != null) {
          queryParams['embed_images'] = embedImages.toString();
        }

        if (formatSettings.bilingualExport == true) {
          queryParams['bilingual_export'] = 'true';
          queryParams['bilingual_order'] =
              formatSettings.bilingualOrder ?? 'target_after_source';
          if (formatSettings.sourceTextItalic != null) {
            queryParams['source_text_italic'] =
                formatSettings.sourceTextItalic.toString();
          }
          if (formatSettings.sourceTextColor != null) {
            queryParams['source_text_color'] =
                formatSettings.sourceTextColor!;
          }
          if (formatSettings.targetTextItalic != null) {
            queryParams['target_text_italic'] =
                formatSettings.targetTextItalic.toString();
          }
          if (formatSettings.targetTextColor != null &&
              formatSettings.targetTextColor!.isNotEmpty) {
            queryParams['target_text_color'] =
                formatSettings.targetTextColor!;
          }
        }

        downloadUrl = uri.replace(queryParameters: queryParams).toString();
      }

      // Download file bytes
      final List<int> bytes = await svc.downloadFile(downloadUrl);

      if (bytes.isEmpty) {
        if (mounted) {
          MessageService.showError(
            context,
            'Failed to download $fileType: Empty response',
          );
        }
        return;
      }

      // Generate filename
      final String extension = fileType == 'md'
          ? (embedImages == false
              ? 'zip'
              : 'md') // ZIP for MD with images folder
          : fileType;
      final String filename =
          '${widget.title.toLowerCase().replaceAll(' ', '_')}.$extension';
      final String nameWithoutExt =
          widget.title.toLowerCase().replaceAll(' ', '_');

      // Save file (Web or Desktop)
      if (kIsWeb) {
        // Web: use FileSaver
        // For MD with images folder, use ZIP mime type
        final MimeType mimeType = (fileType == 'md' && embedImages == false)
            ? MimeType.zip
            : _getMimeTypeEnum(fileType);
        await FileSaver.instance.saveFile(
          name: nameWithoutExt,
          bytes: Uint8List.fromList(bytes),
          ext: extension,
          mimeType: mimeType,
        );
      } else {
        // Desktop: use FilePicker to save
        final String? path = await FilePicker.platform.saveFile(
          dialogTitle: 'Save File',
          fileName: filename,
          type: FileType.custom,
          allowedExtensions: <String>[extension],
        );
        if (path != null) {
          // On desktop, io.File accepts a path parameter
          // The stub version doesn't accept parameters, but this code only runs on desktop
          // ignore: avoid_dynamic_calls, invalid_use_of_visible_for_testing_member
          final file = (io.File as dynamic)(path);
          await file.writeAsBytes(bytes, flush: true);
        }
      }

      if (mounted) {
        MessageService.showSuccess(context, 'File downloaded: $filename');
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to download $fileType: $e');
      }
    } finally {
      if (mounted) {
        setState(() {
          _downloading[downloadKey] = false;
        });
      }
    }
  }

  /// Get icon for file format
  IconData _getFormatIcon(String format) {
    switch (format.toLowerCase()) {
      case 'md':
        return Icons.description;
      case 'html':
        return Icons.code;
      case 'docx':
        return Icons.description;
      case 'pdf':
        return Icons.picture_as_pdf;
      default:
        return Icons.file_download;
    }
  }

  /// Get MimeType enum for file type
  MimeType _getMimeTypeEnum(String fileType) {
    switch (fileType.toLowerCase()) {
      case 'docx':
        return MimeType.microsoftWord;
      case 'pdf':
        return MimeType.pdf;
      case 'html':
      case 'md':
      default:
        return MimeType.other;
    }
  }

  Color _getStatusColor(String? status) {
    if (status == null) return Colors.blue;
    switch (status.toLowerCase()) {
      case 'completed':
        return Colors.green;
      case 'failed':
      case 'error':
        return Colors.red;
      case 'cancelled':
        return Colors.orange;
      default:
        return Colors.blue;
    }
  }

  String _getStatusDisplayText(String? status) {
    if (status == null) return 'Processing...';
    switch (status.toLowerCase()) {
      case 'completed':
        return 'Completed';
      case 'failed':
      case 'error':
        return 'Failed';
      case 'cancelled':
        return 'Cancelled';
      case 'processing':
        return 'Processing...';
      default:
        return status.isNotEmpty ? status : 'Processing...';
    }
  }

  Future<void> _cancelOperation() async {
    if (widget.onCancel == null) return;
    if (_isCancelling) return;

    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text('Cancel Operation'),
        content: const Text('Are you sure you want to cancel?'),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('No'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Yes'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() {
      _isCancelling = true;
    });

    try {
      await widget.onCancel!();
    } finally {
      if (mounted) {
        setState(() {
          _isCancelling = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch format settings to automatically reload preview when they change
    final FormatSettings formatSettings = ref.watch(
      formatSettingsProviderFamily(widget.taskId),
    );

    // Check if format settings changed and reload preview if needed
    if (_lastFormatSettings != null &&
        _lastFormatSettings != formatSettings &&
        _previewContent != null &&
        !_loadingPreview) {
      // Format settings changed, reload preview
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _loadPreviewContent();
        }
      });
    }
    _lastFormatSettings = formatSettings;

    // Get status to check for tables, equations, and charts
    final Map<String, dynamic>? status = _currentStatus;
    final bool hasTables = status?['has_tables'] == true;
    final bool hasInterlineEquations =
        status?['has_interline_equations'] == true;
    final bool hasCharts = status?['has_charts'] == true;
    final bool isCompleted = status != null &&
        ((status['status'] ?? '').toString().toLowerCase() == 'completed' ||
            (status['status'] ?? '').toString().toLowerCase() == 'failed');
    final bool isActive = status != null &&
        (status['status'] ?? '').toString().toLowerCase() == 'processing';
    final bool showProgress =
        widget.showProgressBar && isActive && !isCompleted;

    return Column(
      children: <Widget>[
        // Toolbar with Settings and Download buttons
        _buildToolbar(
          hasTables,
          hasInterlineEquations,
          hasCharts,
          isActive,
          isCompleted,
          showProgress,
          _progress ?? 0,
          _statusText,
          _displayMessage,
        ),

        // Main preview content
        Expanded(
          child: _loadingPreview
              ? const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32),
                    child: CircularProgressIndicator(),
                  ),
                )
              : _previewContent != null
                  ? _buildPreviewContent()
                  : const Center(
                      child: Padding(
                        padding: EdgeInsets.all(32),
                        child: Text('Preview will be loaded...'),
                      ),
                    ),
        ),
      ],
    );
  }

  /// Build toolbar with Settings and Download buttons
  Widget _buildToolbar(
    bool hasTables,
    bool hasInterlineEquations,
    bool hasCharts,
    bool isActive,
    bool isCompleted,
    bool showProgressBar,
    int progress,
    String? statusText,
    String? displayMessage,
  ) =>
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        constraints: const BoxConstraints(
          minHeight: 36,
          maxHeight: 36,
        ), // Fixed height at 36px
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          border:
              Border(bottom: BorderSide(color: Theme.of(context).dividerColor)),
        ),
        child: Row(
          children: <Widget>[
            Icon(
              widget.icon,
              size: 20,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 8),
            Text(
              widget.title,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (showProgressBar) ...<Widget>[
              const SizedBox(width: 16),
              SizedBox(
                width: 100,
                height: 6,
                child: LinearProgressIndicator(
                  value: progress / 100.0,
                  backgroundColor: Colors.grey.shade300,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    _getStatusColor(statusText),
                  ),
                  minHeight: 6,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '$progress%',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(width: 8),
              Icon(
                Icons.info,
                size: 16,
                color: _getStatusColor(statusText),
              ),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  _getStatusDisplayText(statusText),
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: _getStatusColor(statusText),
                  ),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 1,
                ),
              ),
              if (widget.onCancel != null) ...<Widget>[
                const SizedBox(width: 8),
                if (!_isCancelling)
                  TextButton.icon(
                    onPressed: _cancelOperation,
                    icon: const Icon(Icons.cancel, size: 14),
                    label: const Text('Cancel'),
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.red,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      minimumSize: const Size(0, 0),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                if (_isCancelling)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ],
            const Spacer(),
            // Settings and Download buttons (only show when completed or if not using status polling)
            if (isCompleted || !widget.enableStatusPolling) ...<Widget>[
              IconButton(
                icon: const Icon(Icons.settings, size: 16),
                tooltip: 'Preview Settings',
                onPressed: () {
                  _unifiedPreviewWidgetLog('[Toolbar] Settings button pressed');
                  try {
                    _showPreviewSettingsDialog(
                      hasTables,
                      hasInterlineEquations,
                      hasCharts,
                    );
                    _unifiedPreviewWidgetLog('[Toolbar] Settings dialog shown');
                  } catch (e, stackTrace) {
                    _unifiedPreviewWidgetLog(
                      '[Toolbar] Error showing settings dialog: $e\n$stackTrace',
                      level: LogLevel.error,
                    );
                  }
                },
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
              const SizedBox(width: 3),
              IconButton(
                icon: const Icon(Icons.download, size: 16),
                tooltip: 'Export Document',
                onPressed: () {
                  _unifiedPreviewWidgetLog('[Toolbar] Download button pressed');
                  try {
                    _showDownloadDialog();
                    _unifiedPreviewWidgetLog('[Toolbar] Download dialog shown');
                  } catch (e, stackTrace) {
                    _unifiedPreviewWidgetLog(
                      '[Toolbar] Error showing download dialog: $e\n$stackTrace',
                      level: LogLevel.error,
                    );
                  }
                },
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(
                  minWidth: 28,
                  minHeight: 28,
                ),
              ),
            ],
          ],
        ),
      );

  /// Build preview content widget
  Widget _buildPreviewContent() {
    if (_previewContent == null) return const SizedBox.shrink();

    // Use UnifiedPreview widget for consistent rendering
    return UnifiedPreview(
      content: _previewContent!,
      contentType: _previewType,
      imageDataMap: _imageDataMap,
      taskId: widget.taskId,
    );
  }
}
