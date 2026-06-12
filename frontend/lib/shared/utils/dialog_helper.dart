// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/foundation.dart' show kIsWeb, ValueNotifier;
import 'package:flutter/material.dart' hide showDialog, showGeneralDialog;
import 'package:flutter/material.dart' as FlutterMaterial
    show showDialog, showGeneralDialog;
// Conditional import for web platform (for iframe pointer-events control)
import 'html_stub.dart' if (dart.library.html) 'dart:html' as html;
import 'app_logger.dart';

void _dialogHelperLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('DialogHelper', message, level: level);
}

/// Helper class for showing dialogs with automatic preview-layer suppression.
/// Web iframes and desktop WebView2 HWNDs can render above Flutter modal routes.
class DialogHelper {
  /// Number of dialogs currently open (supports nested dialogs).
  static final ValueNotifier<int> activeDialogCount = ValueNotifier<int>(0);

  static bool get isDialogOpen => activeDialogCount.value > 0;

  /// Prefer root navigator context so modals sit above preview tabs/WebViews.
  static BuildContext dialogContext(BuildContext context) {
    return Navigator.of(context, rootNavigator: true).context;
  }

  static void _beginDialog() {
    activeDialogCount.value++;
    _suppressPreviewLayers();
  }

  static void _endDialog() {
    if (activeDialogCount.value > 0) {
      activeDialogCount.value--;
    }
    if (activeDialogCount.value == 0) {
      _restorePreviewLayers();
    }
  }

  static const String _previewIframeScript = '''
    (function() {
      function isPreviewIframe(iframe) {
        if (!iframe) return false;
        if (iframe.getAttribute('data-preview-iframe') === 'true') return true;
        var id = iframe.id || '';
        return id.indexOf('unified_preview_iframe_') >= 0 ||
          id.indexOf('unified_preview_compare_iframe_') >= 0 ||
          id.indexOf('html_preview_') >= 0 ||
          id.indexOf('html_content_preview_') >= 0 ||
          id.indexOf('html_compare_reader_iframe_') >= 0;
      }

      function forEachPreviewIframe(callback) {
        var seen = new Set();
        var tagged = document.querySelectorAll('iframe[data-preview-iframe="true"]');
        for (var i = 0; i < tagged.length; i++) {
          if (!seen.has(tagged[i])) {
            seen.add(tagged[i]);
            callback(tagged[i]);
          }
        }
        var allIframes = document.querySelectorAll('iframe');
        for (var j = 0; j < allIframes.length; j++) {
          if (isPreviewIframe(allIframes[j]) && !seen.has(allIframes[j])) {
            seen.add(allIframes[j]);
            callback(allIframes[j]);
          }
        }
      }

      window.__owlangsPreviewLayerRestore = window.__owlangsPreviewLayerRestore || [];

      window.__owlangsHidePreviewLayers = function() {
        window.__owlangsPreviewLayerRestore = [];
        forEachPreviewIframe(function(iframe) {
          window.__owlangsPreviewLayerRestore.push({
            node: iframe,
            visibility: iframe.style.visibility,
            pointerEvents: iframe.style.pointerEvents
          });
          iframe.style.visibility = 'hidden';
          iframe.style.pointerEvents = 'none';
        });
        var platformViews = document.querySelectorAll('flt-platform-view');
        for (var k = 0; k < platformViews.length; k++) {
          var view = platformViews[k];
          var iframe = view.querySelector('iframe');
          if (!isPreviewIframe(iframe)) continue;
          window.__owlangsPreviewLayerRestore.push({
            node: view,
            visibility: view.style.visibility,
            pointerEvents: view.style.pointerEvents
          });
          view.style.visibility = 'hidden';
          view.style.pointerEvents = 'none';
        }
      };

      window.__owlangsRestorePreviewLayers = function() {
        var entries = window.__owlangsPreviewLayerRestore || [];
        for (var i = 0; i < entries.length; i++) {
          var entry = entries[i];
          if (!entry || !entry.node) continue;
          entry.node.style.visibility = entry.visibility || '';
          entry.node.style.pointerEvents = entry.pointerEvents || '';
        }
        window.__owlangsPreviewLayerRestore = [];
      };
    })();
  ''';

  static bool _previewScriptInstalled = false;

  static void _ensurePreviewIframeScript() {
    if (!kIsWeb || _previewScriptInstalled) {
      return;
    }
    try {
      final html.ScriptElement scriptElement = html.ScriptElement()
        ..text = _previewIframeScript;
      html.document.body?.append(scriptElement);
      Future<void>.delayed(
        const Duration(milliseconds: 100),
        scriptElement.remove,
      );
      _previewScriptInstalled = true;
    } catch (e) {
      _dialogHelperLog(
        '[Dialog] Failed to install preview layer script: $e',
        level: LogLevel.warn,
      );
    }
  }

  static void _runWebPreviewScript(String invoke) {
    if (!kIsWeb) {
      return;
    }
    try {
      _ensurePreviewIframeScript();
      final html.ScriptElement scriptElement = html.ScriptElement()
        ..text = invoke;
      html.document.body?.append(scriptElement);
      Future<void>.delayed(
        const Duration(milliseconds: 100),
        scriptElement.remove,
      );
    } catch (e) {
      _dialogHelperLog(
        '[Dialog] Failed to run preview layer script: $e',
        level: LogLevel.warn,
      );
    }
  }

  static void _suppressPreviewLayers() {
    _runWebPreviewScript(
      'window.__owlangsHidePreviewLayers && window.__owlangsHidePreviewLayers();',
    );
  }

  static void _restorePreviewLayers() {
    _runWebPreviewScript(
      'window.__owlangsRestorePreviewLayers && window.__owlangsRestorePreviewLayers();',
    );
  }

  /// Disable pointer-events on preview iframes (legacy API, kept for callers).
  static void disablePreviewPointerEvents() {
    _suppressPreviewLayers();
  }

  /// Enable pointer-events on preview iframes (legacy API, kept for callers).
  static void enablePreviewPointerEvents() {
    if (!isDialogOpen) {
      _restorePreviewLayers();
    }
  }

  /// Show a dialog with automatic preview-layer suppression.
  static Future<T?> showDialog<T>({
    required BuildContext context,
    required WidgetBuilder builder,
    bool barrierDismissible = true,
    Color? barrierColor,
    String? barrierLabel,
    bool useRootNavigator = true,
    RouteSettings? routeSettings,
    Offset? anchorPoint,
  }) async {
    _dialogHelperLog('[Dialog] Showing dialog with preview layer control');
    _beginDialog();
    await Future<void>.delayed(const Duration(milliseconds: 50));

    try {
      final T? result = await FlutterMaterial.showDialog<T>(
        context: dialogContext(context),
        builder: builder,
        barrierDismissible: barrierDismissible,
        barrierColor: barrierColor,
        barrierLabel: barrierLabel,
        useRootNavigator: useRootNavigator,
        routeSettings: routeSettings,
        anchorPoint: anchorPoint,
      );
      return result;
    } finally {
      _endDialog();
    }
  }

  /// Show a general dialog with automatic preview-layer suppression.
  static Future<T?> showGeneralDialog<T>({
    required BuildContext context,
    required RoutePageBuilder pageBuilder,
    bool barrierDismissible = true,
    Color? barrierColor,
    String? barrierLabel,
    bool useRootNavigator = true,
    RouteSettings? routeSettings,
    Offset? anchorPoint,
    RouteTransitionsBuilder? transitionBuilder,
    Duration transitionDuration = const Duration(milliseconds: 200),
  }) async {
    _beginDialog();
    await Future<void>.delayed(const Duration(milliseconds: 50));

    try {
      return await FlutterMaterial.showGeneralDialog<T>(
        context: dialogContext(context),
        pageBuilder: pageBuilder,
        barrierDismissible: barrierDismissible,
        barrierColor: barrierColor ?? Colors.black54,
        barrierLabel: barrierLabel,
        useRootNavigator: useRootNavigator,
        routeSettings: routeSettings,
        anchorPoint: anchorPoint,
        transitionBuilder: transitionBuilder,
        transitionDuration: transitionDuration,
      );
    } finally {
      _endDialog();
    }
  }
}
