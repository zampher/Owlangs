// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:desktop_drop/desktop_drop.dart'
    if (dart.library.html) 'desktop_drop_stub.dart';
import '../../l10n/app_localizations.dart';
import '../utils/html_stub.dart' if (dart.library.html) 'dart:html' as html;
import 'dart:typed_data';
import 'dart:async';

/// File upload area widget that displays a drop zone for file selection
class FileUploadArea extends StatefulWidget {
  const FileUploadArea({
    required this.isDisabled,
    super.key,
    this.onTap,
    this.onCancel,
    this.onFileDropped,
    this.disabledMessage,
    this.supportedFormats,
  });
  final bool isDisabled;
  final VoidCallback? onTap;
  final VoidCallback? onCancel;
  final Function(PlatformFile)? onFileDropped;
  /// When null, localized message is used.
  final String? disabledMessage;
  /// When null, localized default supported formats text is used.
  final String? supportedFormats;

  @override
  State<FileUploadArea> createState() => _FileUploadAreaState();
}

class _FileUploadAreaState extends State<FileUploadArea> {
  bool _isDragging = false;

  @override
  void initState() {
    super.initState();
    if (kIsWeb) {
      _setupDragAndDrop();
    }
  }

  @override
  void dispose() {
    if (kIsWeb) {
      _cleanupDragAndDrop();
    }
    super.dispose();
  }

  void _setupDragAndDrop() {
    if (!kIsWeb) return;

    // Use a small delay to ensure the widget is built
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;

      // Find the render object and get the HTML element
      final context = this.context;
      final renderObject = context.findRenderObject();
      if (renderObject == null) return;

      // Use platform view registry to get the element
      // For web, we'll use a different approach - attach listeners to the window
      _attachWindowListeners();
    });
  }

  void _attachWindowListeners() {
    if (!kIsWeb) return;

    html.window.addEventListener('dragover', _handleDragOver);
    html.window.addEventListener('dragleave', _handleDragLeave);
    html.window.addEventListener('drop', _handleDrop);
  }

  void _cleanupDragAndDrop() {
    if (!kIsWeb) return;

    html.window.removeEventListener('dragover', _handleDragOver);
    html.window.removeEventListener('dragleave', _handleDragLeave);
    html.window.removeEventListener('drop', _handleDrop);
  }

  void _handleDragOver(html.Event e) {
    if (widget.isDisabled) return;
    if (!mounted) return;
    e.preventDefault();
    e.stopPropagation();
    if (!_isDragging) {
      setState(() {
        _isDragging = true;
      });
    }
  }

  void _handleDragLeave(html.Event e) {
    if (!mounted) return;
    e.preventDefault();
    // Only update state if leaving the window
    try {
      final relatedTarget = (e as dynamic).relatedTarget;
      if (relatedTarget == null) {
        if (_isDragging) {
          setState(() {
            _isDragging = false;
          });
        }
      }
    } catch (_) {
      // Not a drag event, ignore
    }
  }

  Future<void> _handleDrop(html.Event e) async {
    if (widget.isDisabled) return;
    if (!mounted) return;

    e.preventDefault();
    e.stopPropagation();

    if (_isDragging) {
      setState(() {
        _isDragging = false;
      });
    }

    // Check if event has dataTransfer property (DragEvent)
    try {
      final dataTransfer = (e as dynamic).dataTransfer;
      if (dataTransfer != null) {
        final files = dataTransfer.files;
        if (files != null && files.isNotEmpty) {
          _processDroppedFile(files[0]);
        }
      }
    } catch (_) {
      // Not a drag event, ignore
    }
  }

  Future<void> _processDroppedFile(file) async {
    if (widget.onFileDropped == null) return;

    // Read file as bytes
    final reader = html.FileReader();
    final completer = Completer<Uint8List?>();

    reader.onLoadEnd.listen((_) {
      if (reader.readyState == html.FileReader.DONE) {
        completer.complete(reader.result as Uint8List?);
      }
    });

    reader.onError.listen((e) {
      completer.completeError('Failed to read file: ${file.name}');
    });

    reader.readAsArrayBuffer(file);

    try {
      final bytes = await completer.future;
      if (!mounted) return;
      final platformFile = PlatformFile(
        name: file.name,
        size: file.size,
        bytes: bytes,
      );
      widget.onFileDropped!(platformFile);
    } catch (e) {
      // Error reading file, ignore
    }
  }

  Widget _buildInnerContent(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final disabledMessage =
        widget.disabledMessage ?? l10n.fileUploadDisabledMessage;
    final supportedFormats =
        widget.supportedFormats ?? l10n.fileUploadSupportedFormats;
    // Fill all available space and add a small right margin for visual comfort
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: SizedBox.expand(
        child: Card(
          elevation: 4,
          margin: EdgeInsets.zero,
          child: InkWell(
            onTap: widget.isDisabled
                ? null
                : () {
                    if (widget.onTap != null) {
                      widget.onTap!();
                    }
                  },
            child: DecoratedBox(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(4),
                border: _isDragging && !widget.isDisabled
                    ? Border.all(
                        color: Theme.of(context).colorScheme.primary,
                        width: 2,
                      )
                    : null,
                color: _isDragging && !widget.isDisabled
                    ? Theme.of(context)
                        .colorScheme
                        .primaryContainer
                        .withOpacity(0.3)
                    : null,
              ),
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: <Widget>[
                    Icon(
                      _isDragging && !widget.isDisabled
                          ? Icons.file_download
                          : Icons.cloud_upload_outlined,
                      size: 64,
                      color: widget.isDisabled
                          ? Theme.of(context)
                              .colorScheme
                              .onSurfaceVariant
                              .withOpacity(0.4)
                          : _isDragging
                              ? Theme.of(context).colorScheme.primary
                              : Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      widget.isDisabled
                          ? disabledMessage
                          : _isDragging
                              ? l10n.fileUploadDropHere
                              : l10n.fileUploadHint,
                      style: TextStyle(
                        fontSize: 16,
                        color: widget.isDisabled
                            ? Theme.of(context)
                                .colorScheme
                                .onSurfaceVariant
                                .withOpacity(0.4)
                            : _isDragging
                                ? Theme.of(context).colorScheme.primary
                                : Theme.of(context).colorScheme.onSurfaceVariant,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      supportedFormats,
                      style: TextStyle(
                        fontSize: 12,
                        color: widget.isDisabled
                            ? Theme.of(context)
                                .colorScheme
                                .onSurfaceVariant
                                .withOpacity(0.4)
                            : Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (widget.isDisabled && widget.onCancel != null)
                      ...<Widget>[
                        const SizedBox(height: 12),
                        ElevatedButton.icon(
                          onPressed: widget.onCancel,
                          icon: const Icon(Icons.cancel, size: 18),
                          label: Text(l10n.fileUploadCancelTask),
                          style: ElevatedButton.styleFrom(
                            backgroundColor:
                                Theme.of(context).colorScheme.errorContainer,
                            foregroundColor:
                                Theme.of(context).colorScheme.onErrorContainer,
                          ),
                        ),
                      ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final inner = _buildInnerContent(context);

    // Web: use HTML drag-and-drop listeners via _setupDragAndDrop()
    if (kIsWeb) {
      return inner;
    }

    // Desktop / other non-web platforms: use DropTarget for OS-level file drops
    return DropTarget(
      onDragEntered: (detail) {
        if (widget.isDisabled) return;
        if (mounted) {
          setState(() {
            _isDragging = true;
          });
        }
      },
      onDragExited: (detail) {
        if (mounted) {
          setState(() {
            _isDragging = false;
          });
        }
      },
      onDragDone: (detail) {
        if (widget.isDisabled || widget.onFileDropped == null) return;
        if (mounted) {
          setState(() {
            _isDragging = false;
          });
        }
        if (detail.files.isEmpty) {
          return;
        }

        final file = detail.files.first;
        // For desktop, pass a PlatformFile with name and path.
        // _processFile will prefer bytes if available, otherwise read from path.
        final platformFile = PlatformFile(
          name: file.name,
          size: 0,
          path: file.path,
        );
        widget.onFileDropped!(platformFile);
      },
      child: inner,
    );
  }
}
