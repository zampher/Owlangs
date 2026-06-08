// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'dart:io' if (dart.library.html) '../../../shared/utils/io_stub.dart'
    as io;
import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/utils/download_filename_builder.dart';
import '../../../shared/providers/settings_provider.dart';

// Conditional import for web platform
import '../../../shared/utils/html_stub.dart' if (dart.library.html) 'dart:html'
    as html;
import '../../../shared/utils/ui_web_stub.dart'
    if (dart.library.html) 'dart:ui_web' as ui_web;

void _htmlPreviewLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('HtmlPreview', message, level: level);
}

// Intent class for exit fullscreen
class _ExitFullscreenIntent extends Intent {
  const _ExitFullscreenIntent();
}

/// HTML preview widget for displaying translated content as HTML
class HtmlPreview extends ConsumerStatefulWidget {
  // Download callback

  const HtmlPreview({
    required this.taskId,
    super.key,
    this.flowId,
    this.downloads,
    this.onDownload,
  });
  final String taskId;
  final String? flowId;
  final Map<String, String>? downloads; // Download URLs by file type
  final Function(String fileType, String url)? onDownload;

  @override
  ConsumerState<HtmlPreview> createState() => _HtmlPreviewState();
}

class _HtmlPreviewState extends ConsumerState<HtmlPreview> {
  String? _htmlContent;
  bool _loading = true;
  String? _error;
  String? _viewId; // Store view ID for iframe
  bool _iframeRegistered = false; // Track if iframe is registered
  final Map<String, bool> _downloading =
      <String, bool>{}; // Track download state for each file type
  bool _isFullscreen = false;
  OverlayEntry? _fullscreenOverlayEntry;

  @override
  void initState() {
    super.initState();
    _loadHtmlContent();
  }

  @override
  void dispose() {
    _fullscreenOverlayEntry?.remove();
    _fullscreenOverlayEntry = null;
    super.dispose();
  }

  Future<void> _loadHtmlContent() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final TranslationService svc = TranslationService();

      // Build download URL for HTML
      final String downloadUrl = svc.buildDownloadUrl(widget.taskId, 'html');
      _htmlPreviewLog('Loading HTML from: $downloadUrl');

      // Download HTML file
      final List<int> bytes = await svc.downloadFile(downloadUrl);

      if (bytes.isEmpty) {
        throw Exception('HTML file is empty');
      }

      // Decode HTML content
      final String htmlContent = utf8.decode(bytes);

      if (mounted) {
        setState(() {
          _htmlContent = htmlContent;
          _loading = false;
          _viewId = null;
          _iframeRegistered = false;
        });
        _htmlPreviewLog(
          'HTML loaded successfully, length: ${htmlContent.length}',
        );
      }
    } catch (e) {
      _htmlPreviewLog('Failed to load HTML: $e', level: LogLevel.error);
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
        MessageService.showError(context, 'Failed to load HTML preview: $e');
      }
    }
  }

  void _toggleFullscreen() {
    if (_isFullscreen) {
      _exitFullscreen();
    } else {
      _enterFullscreen();
    }
  }

  void _enterFullscreen() {
    if (_isFullscreen || !mounted) return;
    final OverlayState overlay = Overlay.of(context, rootOverlay: true);
    _fullscreenOverlayEntry = OverlayEntry(
      builder: (BuildContext overlayContext) => RepaintBoundary(
        child: Material(
          color: Colors.black.withOpacity(0.78),
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
                      BoxShadow(
                        blurRadius: 20,
                        color: Colors.black26,
                      ),
                    ],
                  ),
                  child: _buildFullscreenContent(),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    overlay.insert(_fullscreenOverlayEntry!);
    setState(() {
      _isFullscreen = true;
    });
  }

  void _exitFullscreen() {
    if (!_isFullscreen) return;
    _fullscreenOverlayEntry?.remove();
    _fullscreenOverlayEntry = null;
    if (mounted) {
      setState(() {
        _isFullscreen = false;
      });
    }
  }

  Widget _buildFullscreenContent() => Shortcuts(
        shortcuts: const <ShortcutActivator, Intent>{
          SingleActivator(LogicalKeyboardKey.escape): _ExitFullscreenIntent(),
        },
        child: Actions(
          actions: <Type, Action<Intent>>{
            _ExitFullscreenIntent: CallbackAction<_ExitFullscreenIntent>(
              onInvoke: (_) {
                _exitFullscreen();
                return null;
              },
            ),
          },
          child: Focus(
            autofocus: true,
            child: Column(
              children: <Widget>[
                // Toolbar with refresh, copy, download, and exit fullscreen buttons
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    border: Border(
                      bottom: BorderSide(
                        color: Theme.of(context).dividerColor,
                      ),
                    ),
                  ),
                  child: Row(
                    children: <Widget>[
                      // Download buttons: DOCX, MD, HTML (always show these three formats)
                      const SizedBox(width: 8),
                      _buildDownloadButton('docx'),
                      _buildDownloadButton('md'),
                      _buildDownloadButton('html'),
                      const SizedBox(width: 16),
                      const Spacer(),
                      IconButton(
                        icon: const Icon(Icons.refresh),
                        tooltip: 'Reload',
                        onPressed: _loadHtmlContent,
                      ),
                      IconButton(
                        icon: const Icon(Icons.copy),
                        tooltip: 'Copy HTML',
                        onPressed: _copyHtmlContent,
                      ),
                      IconButton(
                        icon: const Icon(Icons.fullscreen_exit),
                        tooltip: 'Exit Fullscreen (ESC)',
                        onPressed: _exitFullscreen,
                      ),
                    ],
                  ),
                ),
                // HTML content display
                Expanded(
                  child: _buildHtmlRenderer(),
                ),
              ],
            ),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    // If in fullscreen mode, return empty widget (content is shown in overlay)
    if (_isFullscreen) {
      return const SizedBox.shrink();
    }

    if (_loading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Loading HTML preview...'),
          ],
        ),
      );
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            Icon(Icons.error_outline, size: 48, color: Colors.red.shade700),
            const SizedBox(height: 16),
            Text(
              'Failed to load HTML preview',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: Colors.red.shade700,
              ),
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Text(
                _error!,
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey.shade600),
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadHtmlContent,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (_htmlContent == null || _htmlContent!.isEmpty) {
      return const Center(
        child: Text('No HTML content available'),
      );
    }

    // Display HTML content with toolbar
    return Column(
      children: <Widget>[
        // Toolbar with refresh, copy, and download buttons
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).dividerColor,
              ),
            ),
          ),
          child: Row(
            children: <Widget>[
              // Download buttons: DOCX, MD, HTML (always show these three formats)
              const SizedBox(width: 8),
              _buildDownloadButton('docx'),
              _buildDownloadButton('md'),
              _buildDownloadButton('html'),
              const SizedBox(width: 16),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh),
                tooltip: 'Reload',
                onPressed: _loadHtmlContent,
              ),
              IconButton(
                icon: const Icon(Icons.copy),
                tooltip: 'Copy HTML',
                onPressed: _copyHtmlContent,
              ),
              IconButton(
                icon: Icon(
                  _isFullscreen ? Icons.fullscreen_exit : Icons.fullscreen,
                  size: 20,
                ),
                tooltip: _isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen',
                onPressed: _toggleFullscreen,
              ),
            ],
          ),
        ),
        // HTML content display
        Expanded(
          child: _buildHtmlRenderer(),
        ),
      ],
    );
  }

  Widget _buildHtmlRenderer() {
    if (kIsWeb) {
      return _buildWebIframe();
    } else {
      // For desktop, show HTML source with option to open in browser
      // In the future, we can add webview_flutter for better rendering
      return Container(
        padding: const EdgeInsets.all(16),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blue.shade200),
                ),
                child: Row(
                  children: <Widget>[
                    Icon(
                      Icons.info_outline,
                      color: Colors.blue.shade700,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'For better HTML rendering, click "Open in browser" button above.',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.blue.shade900,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              _buildHtmlContent(),
            ],
          ),
        ),
      );
    }
  }

  Widget _buildWebIframe() {
    if (!kIsWeb || _htmlContent == null || _htmlContent!.isEmpty) {
      return const SizedBox.shrink();
    }

    try {
      // Create a unique view ID for the iframe (only once, when HTML content is first loaded)
      _viewId ??=
          'html_preview_${widget.taskId}_${DateTime.now().millisecondsSinceEpoch}';

      // Check if view factory is already registered
      // If HTML content changed, we need to update the iframe src
      // For large HTML files, use blob URL instead of data URL
      String iframeSrc;
      if (_htmlContent!.length > 1000000) {
        // For large files (>1MB), create a blob URL
        _htmlPreviewLog(
          'HTML content is large (${_htmlContent!.length} bytes), using blob URL',
        );
        final html.Blob blob = html.Blob(<dynamic>[_htmlContent], 'text/html');
        iframeSrc = html.Url.createObjectUrlFromBlob(blob);
      } else {
        // For smaller files, use data URL
        iframeSrc =
            'data:text/html;charset=utf-8,${Uri.encodeComponent(_htmlContent!)}';
      }

      // Create iframe element
      final html.IFrameElement iframe = html.IFrameElement()
        ..src = iframeSrc
        ..style.border = 'none'
        ..style.width = '100%'
        ..style.height = '100%'
        ..allowFullscreen = true;

      // Register the iframe with Flutter (only register once per viewId)
      if (kIsWeb && _viewId != null && !_iframeRegistered) {
        try {
          // ignore: undefined_prefixed_name
          ui_web.platformViewRegistry.registerViewFactory(
            _viewId!,
            (int viewId) {
              _htmlPreviewLog(
                'Registering iframe with viewId: $_viewId, src length: ${iframeSrc.length}',
              );
              return iframe;
            },
          );
          _htmlPreviewLog('Iframe registered successfully');
          _iframeRegistered = true;
        } catch (e) {
          _htmlPreviewLog(
            'Error registering iframe: $e',
            level: LogLevel.error,
          );
          // If registration fails, try with a new viewId
          _viewId =
              'html_preview_${widget.taskId}_${DateTime.now().millisecondsSinceEpoch}';
          try {
            // ignore: undefined_prefixed_name
            ui_web.platformViewRegistry.registerViewFactory(
              _viewId!,
              (int viewId) => iframe,
            );
            _iframeRegistered = true;
            _htmlPreviewLog('Iframe registered with new viewId: $_viewId');
          } catch (e2) {
            _htmlPreviewLog(
              'Failed to register iframe with new viewId: $e2',
              level: LogLevel.error,
            );
          }
        }
      }

      // Return HtmlElementView to display the iframe
      return HtmlElementView(
        viewType: _viewId!,
        onPlatformViewCreated: (id) {
          _htmlPreviewLog('HtmlElementView created with id: $id');
        },
      );
    } catch (e, stackTrace) {
      _htmlPreviewLog(
        'Error creating iframe: $e\n$stackTrace',
        level: LogLevel.error,
      );
      // Fallback to HTML source view
      return Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: <Widget>[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.orange.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.orange.shade200),
              ),
              child: Row(
                children: <Widget>[
                  Icon(
                    Icons.warning_amber_rounded,
                    color: Colors.orange.shade700,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Failed to render HTML in iframe. Showing source code instead.',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.orange.shade900,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: SingleChildScrollView(
                child: _buildHtmlContent(),
              ),
            ),
          ],
        ),
      );
    }
  }

  Widget _buildHtmlContent() {
    // Display HTML content in a formatted way (fallback)
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: SelectableText.rich(
          TextSpan(
            text: _htmlContent,
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
            ),
          ),
        ),
      ),
    );
  }

  /// Copy rendered content from HTML preview to clipboard
  /// Simulates Ctrl+A and Ctrl+C to preserve formatting, images, and tables
  Future<void> _copyHtmlContent() async {
    if (_htmlContent == null || _htmlContent!.isEmpty) {
      MessageService.showWarning(context, 'No HTML content to copy');
      return;
    }

    try {
      if (kIsWeb) {
        // For Web: Use Clipboard API directly with original HTML content
        // This ensures we have complete HTML with base64 images and table formatting
        final bool success = await _copyHtmlWithClipboardAPI();
        if (success) {
          if (mounted) {
            MessageService.showSuccess(context, 'Content copied to clipboard');
          }
          return;
        } else {
          // Fallback: Try to copy from iframe
          _htmlPreviewLog('Direct copy failed, trying iframe copy');
          final bool iframeSuccess = await _copyFromIframe();
          if (iframeSuccess) {
            if (mounted) {
              MessageService.showSuccess(
                context,
                'Content copied to clipboard',
              );
            }
            return;
          } else {
            _htmlPreviewLog(
              'Iframe copy also failed, falling back to text extraction',
            );
          }
        }
      }

      // Fallback: Extract text content from HTML (for desktop or if iframe copy fails)
      final String textContent = _extractTextFromHtml(_htmlContent!);

      if (textContent.isEmpty) {
        MessageService.showWarning(context, 'No text content found in HTML');
        return;
      }

      await Clipboard.setData(ClipboardData(text: textContent));
      if (mounted) {
        MessageService.showSuccess(context, 'Text content copied to clipboard');
      }
    } catch (e) {
      _htmlPreviewLog('Error copying content: $e', level: LogLevel.error);
      if (mounted) {
        MessageService.showError(context, 'Failed to copy content: $e');
      }
    }
  }

  /// Copy HTML content directly using Clipboard API
  /// This uses the original HTML content which includes base64 images and complete formatting
  Future<bool> _copyHtmlWithClipboardAPI() async {
    if (!kIsWeb || _htmlContent == null || _htmlContent!.isEmpty) {
      return false;
    }

    try {
      if (html.window.navigator.clipboard == null) {
        _htmlPreviewLog('Clipboard API not available', level: LogLevel.warn);
        return false;
      }

      // Extract text content for plain text fallback
      final String textContent = _extractTextFromHtml(_htmlContent!);

      // Use JavaScript to write to clipboard with both HTML and text
      final html.ScriptElement script = html.ScriptElement()
        ..text = '''
        (function() {
          try {
            var htmlContent = ${jsonEncode(_htmlContent)};
            var textContent = ${jsonEncode(textContent)};
            
            if (!navigator.clipboard || !navigator.clipboard.write) {
              window.dispatchEvent(new CustomEvent('directCopyError', {detail: 'Clipboard API not available'}));
              return;
            }
            
            var htmlBlob = new Blob([htmlContent], {type: 'text/html'});
            var textBlob = new Blob([textContent], {type: 'text/plain'});
            
            navigator.clipboard.write([
              new ClipboardItem({
                'text/html': htmlBlob,
                'text/plain': textBlob
              })
            ]).then(function() {
              window.dispatchEvent(new CustomEvent('directCopySuccess'));
            }).catch(function(e) {
              console.error('Direct copy error:', e);
              window.dispatchEvent(new CustomEvent('directCopyError', {detail: e.toString()}));
            });
          } catch (e) {
            console.error('Error in direct copy script:', e);
            window.dispatchEvent(new CustomEvent('directCopyError', {detail: e.toString()}));
          }
        })();
        ''';

      // Set up event listeners
      html.EventListener? successListener;
      html.EventListener? errorListener;
      final Completer<bool> completer = Completer<bool>();

      successListener = (e) {
        html.window.removeEventListener('directCopySuccess', successListener);
        html.window.removeEventListener('directCopyError', errorListener);
        if (!completer.isCompleted) {
          completer.complete(true);
        }
      };

      errorListener = (e) {
        html.window.removeEventListener('directCopySuccess', successListener);
        html.window.removeEventListener('directCopyError', errorListener);
        if (!completer.isCompleted) {
          completer.complete(false);
        }
      };

      html.window.addEventListener('directCopySuccess', successListener);
      html.window.addEventListener('directCopyError', errorListener);

      // Execute script
      final html.Document document = html.window.document;
      final html.Element? body = document.querySelector('body');
      if (body != null) {
        body.append(script);
      } else {
        return false;
      }

      // Wait for result
      try {
        final bool result = await completer.future.timeout(
          const Duration(seconds: 3),
          onTimeout: () {
            _htmlPreviewLog(
              'Direct copy operation timed out',
              level: LogLevel.warn,
            );
            return false;
          },
        );

        script.remove();
        html.window.removeEventListener('directCopySuccess', successListener);
        html.window.removeEventListener('directCopyError', errorListener);

        return result;
      } catch (e) {
        script.remove();
        html.window.removeEventListener('directCopySuccess', successListener);
        html.window.removeEventListener('directCopyError', errorListener);
        return false;
      }
    } catch (e) {
      _htmlPreviewLog('Error in direct HTML copy: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Copy content from iframe by simulating Ctrl+A and Ctrl+C
  /// Returns true if successful, false otherwise
  Future<bool> _copyFromIframe() async {
    if (!kIsWeb || _viewId == null) {
      return false;
    }

    try {
      // Use JavaScript to execute copy operation in iframe
      // We'll use js_util or direct JavaScript execution via dart:js_interop
      return await _executeIframeCopyJs();
    } catch (e) {
      _htmlPreviewLog('Error in iframe copy: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Execute JavaScript to copy from iframe using js_util
  Future<bool> _executeIframeCopyJs() async {
    if (!kIsWeb || _viewId == null) {
      return false;
    }

    try {
      // Use dart:js_interop to execute JavaScript
      // Since we need to access iframe content, we'll use a JavaScript function
      // that can be called from Dart

      // First, try to find and access the iframe
      final List<html.Element> iframes =
          html.window.document.querySelectorAll('iframe');
      html.IFrameElement? targetIframe;

      for (html.Element element in iframes) {
        if (element is html.IFrameElement) {
          final String src = element.src ?? '';
          // Check if this is our iframe by matching src pattern
          if (src.contains('html_preview_${widget.taskId}') ||
              src.startsWith('blob:') ||
              src.startsWith('data:text/html')) {
            targetIframe = element;
            break;
          }
        }
      }

      if (targetIframe == null) {
        _htmlPreviewLog('Iframe not found for copying', level: LogLevel.warn);
        return false;
      }

      // Use a workaround by injecting a script into the main document
      // that can access the iframe and perform the copy operation
      return await _injectCopyScript(targetIframe);
    } catch (e) {
      _htmlPreviewLog('Error executing iframe copy: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Inject a script into the iframe to perform copy operation
  Future<bool> _injectCopyScript(html.IFrameElement iframe) async {
    try {
      // For blob: and data: URLs, contentDocument should be accessible
      // We need to use JavaScript to access it properly
      // Since dart:html's IFrameElement may not expose contentDocument directly,
      // we'll use a workaround by creating a temporary script element

      // Create a script that will be executed in the main window context
      // but can access the iframe
      final html.ScriptElement script = html.ScriptElement()
        ..text = '''
          (function() {
            try {
              var iframes = document.querySelectorAll('iframe');
              var targetIframe = null;
              
              for (var i = 0; i < iframes.length; i++) {
                var src = iframes[i].src || '';
                if (src.includes('html_preview_${widget.taskId}') || 
                    src.startsWith('blob:') || 
                    src.startsWith('data:text/html')) {
                  targetIframe = iframes[i];
                  break;
                }
              }
              
              if (!targetIframe || !targetIframe.contentDocument) {
                return false;
              }
              
              var doc = targetIframe.contentDocument;
              var win = targetIframe.contentWindow;
              
              win.focus();
              
              var selection = win.getSelection();
              var range = doc.createRange();
              range.selectNodeContents(doc.body);
              selection.removeAllRanges();
              selection.addRange(range);
              
              // Use Clipboard API directly with the full HTML content
              // This ensures images (base64) and table formatting are preserved
              if (!navigator.clipboard || !navigator.clipboard.write) {
                window.dispatchEvent(new CustomEvent('iframeCopyError', {detail: 'Clipboard API not available'}));
                return false;
              }
              
              // Get the full HTML content from the iframe document
              // Include head for styles, and body for content
              var htmlContent = '<!DOCTYPE html><html>';
              if (doc.head) {
                htmlContent += doc.head.outerHTML;
              }
              htmlContent += '<body>' + doc.body.innerHTML + '</body></html>';
              var textContent = doc.body.innerText || doc.body.textContent || '';
              
              // Create blobs with proper MIME types
              var htmlBlob = new Blob([htmlContent], {type: 'text/html'});
              var textBlob = new Blob([textContent], {type: 'text/plain'});
              
              navigator.clipboard.write([
                new ClipboardItem({
                  'text/html': htmlBlob,
                  'text/plain': textBlob
                })
              ]).then(function() {
                window.dispatchEvent(new CustomEvent('iframeCopySuccess'));
              }).catch(function(e) {
                console.error('Clipboard API error:', e);
                window.dispatchEvent(new CustomEvent('iframeCopyError', {detail: e.toString()}));
              });
              
              return true;
            } catch (e) {
              console.error('Error in copy script:', e);
              window.dispatchEvent(new CustomEvent('iframeCopyError', {detail: e}));
              return false;
            }
          })();
        ''';

      // Set up event listeners for success/error
      html.EventListener? successListener;
      html.EventListener? errorListener;

      final Completer<bool> completer = Completer<bool>();

      successListener = (e) {
        html.window.removeEventListener('iframeCopySuccess', successListener);
        html.window.removeEventListener('iframeCopyError', errorListener);
        if (!completer.isCompleted) {
          completer.complete(true);
        }
      };

      errorListener = (e) {
        html.window.removeEventListener('iframeCopySuccess', successListener);
        html.window.removeEventListener('iframeCopyError', errorListener);
        if (!completer.isCompleted) {
          completer.complete(false);
        }
      };

      html.window.addEventListener('iframeCopySuccess', successListener);
      html.window.addEventListener('iframeCopyError', errorListener);

      // Execute the script
      final html.Document document = html.window.document;
      final html.Element? body = document.querySelector('body');
      if (body != null) {
        body.append(script);
      } else {
        script.remove();
        return false;
      }

      // Wait for result with timeout
      try {
        final bool result = await completer.future.timeout(
          const Duration(seconds: 2),
          onTimeout: () {
            _htmlPreviewLog('Copy operation timed out', level: LogLevel.warn);
            return false;
          },
        );

        // Clean up
        script.remove();
        html.window.removeEventListener('iframeCopySuccess', successListener);
        html.window.removeEventListener('iframeCopyError', errorListener);

        return result;
      } catch (e) {
        script.remove();
        html.window.removeEventListener('iframeCopySuccess', successListener);
        html.window.removeEventListener('iframeCopyError', errorListener);
        return false;
      }
    } catch (e) {
      _htmlPreviewLog('Error injecting copy script: $e', level: LogLevel.error);
      return false;
    }
  }

  /// Extract plain text from HTML content
  /// Removes HTML tags, scripts, styles, and normalizes whitespace
  String _extractTextFromHtml(String html) {
    // Remove script and style tags with their content
    var text = html
        .replaceAll(
          RegExp(r'<script[^>]*>[\s\S]*?</script>', caseSensitive: false),
          '',
        )
        .replaceAll(
          RegExp(r'<style[^>]*>[\s\S]*?</style>', caseSensitive: false),
          '',
        );

    // Replace block-level elements with newlines to preserve structure
    text = text
        .replaceAll(
          RegExp(
            '</(p|div|h[1-6]|li|tr|td|th|br|hr)[^>]*>',
            caseSensitive: false,
          ),
          '\n',
        )
        .replaceAll(
          RegExp(
            '<(p|div|h[1-6]|li|tr|td|th|br|hr)[^>]*>',
            caseSensitive: false,
          ),
          '\n',
        );

    // Replace other block elements
    text = text
        .replaceAll(
          RegExp(
            '</(blockquote|pre|code|ul|ol|table|thead|tbody|tfoot)[^>]*>',
            caseSensitive: false,
          ),
          '\n',
        )
        .replaceAll(
          RegExp(
            '<(blockquote|pre|code|ul|ol|table|thead|tbody|tfoot)[^>]*>',
            caseSensitive: false,
          ),
          '\n',
        );

    // Remove all remaining HTML tags
    text = text.replaceAll(RegExp('<[^>]+>'), '');

    // Decode HTML entities
    text = text
        .replaceAll('&nbsp;', ' ')
        .replaceAll('&amp;', '&')
        .replaceAll('&lt;', '<')
        .replaceAll('&gt;', '>')
        .replaceAll('&quot;', '"')
        .replaceAll('&#39;', "'")
        .replaceAll('&apos;', "'");

    // Normalize whitespace: collapse multiple spaces/tabs to single space
    text = text.replaceAll(RegExp(r'[ \t]+'), ' ');

    // Normalize line breaks: collapse multiple newlines to double newline (paragraph break)
    text = text.replaceAll(RegExp(r'\n\s*\n\s*\n+'), '\n\n');

    // Remove leading/trailing whitespace from each line
    final List<String> lines = text.split('\n');
    final Iterable<String> cleanedLines = lines
        .map((String line) => line.trim())
        .where((String line) => line.isNotEmpty);
    text = cleanedLines.join('\n');

    return text.trim();
  }

  /// Build individual download button for a specific format
  Widget _buildDownloadButton(String format) {
    final bool isDownloading = _downloading[format] ?? false;
    // Always enable download buttons - _handleDirectDownload will build URL from taskId
    final bool isEnabled = !isDownloading;

    // Get icon for each format
    IconData formatIcon;
    switch (format.toLowerCase()) {
      case 'docx':
        formatIcon = Icons.description;
        break;
      case 'md':
        formatIcon = Icons.text_snippet;
        break;
      case 'html':
        formatIcon = Icons.code;
        break;
      default:
        formatIcon = Icons.insert_drive_file;
    }

    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: IconButton(
        icon: isDownloading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                ),
              )
            : Stack(
                clipBehavior: Clip.none,
                children: <Widget>[
                  Icon(formatIcon, size: 20),
                  Positioned(
                    right: -4,
                    top: -4,
                    child: Container(
                      padding: const EdgeInsets.all(2),
                      decoration: BoxDecoration(
                        color: Colors.green.shade700,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.download,
                        size: 10,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
        tooltip: 'Download ${format.toUpperCase()}',
        onPressed: isEnabled ? () => _handleDirectDownload(format) : null,
        style: IconButton.styleFrom(
          backgroundColor:
              isEnabled ? Colors.green.shade700 : Colors.grey.shade400,
          foregroundColor: Colors.white,
        ),
      ),
    );
  }

  /// Handle direct download (same logic as Translate page)
  /// This ensures consistent behavior and proper file naming
  Future<void> _handleDirectDownload(String fileType) async {
    if (_downloading[fileType] ?? false) return;

    setState(() {
      _downloading[fileType] = true;
    });

    try {
      final TranslationService svc = TranslationService();

      // Build download URL using taskId
      // Backend will rebuild document from segments (including failed segments)
      final String downloadUrl = svc.buildDownloadUrl(widget.taskId, fileType);

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

      // Generate filename using shared utility with configurable suffix
      final suffix = ref.read(globalSettingsProvider).translateOutputSuffix;
      final originalName = (widget.downloads != null && widget.downloads!.isNotEmpty)
          ? 'translated_${widget.taskId}'
          : 'translated';
      final String extension = fileType == 'md' ? 'md' : fileType;
      final String filename = buildDownloadFilename(
        originalName: originalName,
        extension: extension,
        suffix: suffix,
      );
      // Base name without extension for FileSaver
      final String nameWithoutExt = filename.endsWith('.$extension')
          ? filename.substring(0, filename.length - extension.length - 1)
          : filename;

      // Save file (Web or Desktop)
      if (kIsWeb) {
        // Web: use FileSaver
        final mimeType = _getMimeTypeEnum(fileType);
        await FileSaver.instance.saveFile(
          name: nameWithoutExt,
          bytes: Uint8List.fromList(bytes),
          ext: extension,
          mimeType: mimeType,
        );
        if (mounted) {
          MessageService.showSuccess(context, 'File downloaded: $filename');
        }
      } else {
        // Desktop: use FilePicker to save
        final String? path = await FilePicker.platform.saveFile(
          dialogTitle: 'Save Translated File',
          fileName: filename,
          type: FileType.custom,
          allowedExtensions: <String>[extension],
        );
        if (path != null) {
          final io.File file = io.File(path);
          await file.writeAsBytes(bytes, flush: true);
          if (mounted) {
            MessageService.showSuccess(context, 'File saved: $filename');
          }
        }
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to download $fileType: $e');
      }
    } finally {
      if (mounted) {
        setState(() {
          _downloading[fileType] = false;
        });
      }
    }
  }

  /// Get MimeType enum for file type
  dynamic _getMimeTypeEnum(String fileType) {
    switch (fileType.toLowerCase()) {
      case 'docx':
        return MimeType.microsoftWord;
      case 'pdf':
        return MimeType.pdf;
      case 'html':
      case 'txt':
      case 'md':
      case 'epub':
      case 'mobi':
      case 'azw':
      case 'ts':
        return MimeType.other;
      default:
        return MimeType.other;
    }
  }
}

/// HTML content preview widget that accepts HTML content directly
/// Reuses HtmlPreview's rendering logic but doesn't download from server
class HtmlContentPreview extends StatefulWidget {
  // Used for generating unique view ID

  const HtmlContentPreview({
    required this.htmlContent,
    required this.taskId,
    super.key,
  });
  final String htmlContent;
  final String taskId;

  @override
  State<HtmlContentPreview> createState() => _HtmlContentPreviewState();
}

class _HtmlContentPreviewState extends State<HtmlContentPreview> {
  String? _viewId;
  bool _iframeRegistered = false;

  @override
  Widget build(BuildContext context) {
    if (widget.htmlContent.isEmpty) {
      return const SizedBox.shrink();
    }

    if (kIsWeb) {
      return _buildWebIframe();
    } else {
      // For desktop, show HTML source with option to open in browser
      return Container(
        padding: const EdgeInsets.all(16),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blue.shade200),
                ),
                child: Row(
                  children: <Widget>[
                    Icon(
                      Icons.info_outline,
                      color: Colors.blue.shade700,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'HTML content preview (desktop rendering limited)',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.blue.shade900,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              _buildHtmlContent(),
            ],
          ),
        ),
      );
    }
  }

  Widget _buildWebIframe() {
    if (!kIsWeb || widget.htmlContent.isEmpty) {
      return const SizedBox.shrink();
    }

    try {
      // Create a unique view ID for the iframe (only once)
      _viewId ??=
          'html_content_preview_${widget.taskId}_${DateTime.now().millisecondsSinceEpoch}';

      // Always use blob URL to avoid CSP issues with data URLs
      final html.Blob blob =
          html.Blob(<dynamic>[widget.htmlContent], 'text/html');
      final String iframeSrc = html.Url.createObjectUrlFromBlob(blob);

      // Create iframe element
      final html.IFrameElement iframe = html.IFrameElement()
        ..src = iframeSrc
        ..style.border = 'none'
        ..style.width = '100%'
        ..style.height = '100%'
        ..allowFullscreen = true;

      // Register the iframe with Flutter (only register once per viewId)
      if (!_iframeRegistered) {
        try {
          // ignore: undefined_prefixed_name
          ui_web.platformViewRegistry.registerViewFactory(
            _viewId!,
            (int viewId) => iframe,
          );
          _iframeRegistered = true;
        } catch (e) {
          _htmlPreviewLog(
            'Error registering iframe: $e',
            level: LogLevel.error,
          );
          // If registration fails, try with a new viewId
          _viewId =
              'html_content_preview_${widget.taskId}_${DateTime.now().millisecondsSinceEpoch}';
          try {
            // ignore: undefined_prefixed_name
            ui_web.platformViewRegistry.registerViewFactory(
              _viewId!,
              (int viewId) => iframe,
            );
            _iframeRegistered = true;
          } catch (e2) {
            _htmlPreviewLog(
              'Failed to register iframe with new viewId: $e2',
              level: LogLevel.error,
            );
          }
        }
      }

      // Return HtmlElementView to display the iframe
      return HtmlElementView(
        viewType: _viewId!,
        onPlatformViewCreated: (id) {
          _htmlPreviewLog('HtmlElementView created with id: $id');
        },
      );
    } catch (e, stackTrace) {
      _htmlPreviewLog(
        'Error creating iframe: $e\n$stackTrace',
        level: LogLevel.error,
      );
      // Fallback to HTML source view
      return Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: <Widget>[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.orange.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.orange.shade200),
              ),
              child: Row(
                children: <Widget>[
                  Icon(
                    Icons.warning_amber_rounded,
                    color: Colors.orange.shade700,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Failed to render HTML in iframe. Showing source code instead.',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.orange.shade900,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: SingleChildScrollView(
                child: _buildHtmlContent(),
              ),
            ),
          ],
        ),
      );
    }
  }

  Widget _buildHtmlContent() {
    // Display HTML content in a formatted way (fallback)
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: SelectableText.rich(
          TextSpan(
            text: widget.htmlContent,
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
            ),
          ),
        ),
      ),
    );
  }
}
