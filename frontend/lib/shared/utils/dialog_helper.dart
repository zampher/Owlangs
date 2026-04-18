// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart' hide showDialog, showGeneralDialog;
import 'package:flutter/material.dart' as FlutterMaterial
    show showDialog, showGeneralDialog;
import 'package:flutter/foundation.dart' show kIsWeb;
// Conditional import for web platform (for iframe pointer-events control)
import 'html_stub.dart' if (dart.library.html) 'dart:html' as html;
import 'app_logger.dart';

void _dialogHelperLog(String message, {LogLevel level = LogLevel.debug}) {
  AppLogger.log('DialogHelper', message, level: level);
}

/// Helper class for showing dialogs with automatic iframe pointer-events control
/// This ensures dialogs are not blocked by preview iframes on Flutter Web
class DialogHelper {
  /// Disable pointer-events on preview iframes (to prevent them from blocking dialogs)
  /// This is a defense-in-depth approach: CSS z-index ensures dialogs are above,
  /// but pointer-events ensures iframe doesn't intercept clicks even if z-index fails
  static void disablePreviewPointerEvents() {
    if (kIsWeb) {
      try {
        // Use JavaScript to disable pointer-events on all preview iframes
        // This includes both the iframe element and the flt-platform-view wrapper
        const String script = '''
          (function() {
            // Disable pointer-events on iframes
            var iframes = document.querySelectorAll('iframe[data-preview-iframe="true"]');
            for (var i = 0; i < iframes.length; i++) {
              iframes[i].style.pointerEvents = 'none';
            }
            // Also try to find iframes by ID pattern
            var allIframes = document.querySelectorAll('iframe');
            for (var i = 0; i < allIframes.length; i++) {
              if (allIframes[i].id && (allIframes[i].id.includes('unified_preview_iframe_') ||
                  allIframes[i].id.includes('html_preview_') ||
                  allIframes[i].id.includes('html_content_preview_'))) {
                allIframes[i].style.pointerEvents = 'none';
              }
            }
            // Also disable pointer-events on flt-platform-view containers that wrap iframes
            var platformViews = document.querySelectorAll('flt-platform-view');
            for (var i = 0; i < platformViews.length; i++) {
              var iframe = platformViews[i].querySelector('iframe');
              if (iframe && (iframe.hasAttribute('data-preview-iframe') ||
                  iframe.id && (iframe.id.includes('unified_preview_iframe_') ||
                  iframe.id.includes('html_preview_') ||
                  iframe.id.includes('html_content_preview_')))) {
                platformViews[i].style.pointerEvents = 'none';
              }
            }
          })();
        ''';
        // Execute script using ScriptElement
        final html.ScriptElement scriptElement = html.ScriptElement()
          ..text = script;
        html.document.body?.append(scriptElement);
        // Remove script element after execution
        Future.delayed(const Duration(milliseconds: 100), scriptElement.remove);
        // Disabled preview iframe pointer-events (logging removed)
      } catch (e) {
        _dialogHelperLog(
          '[Dialog] Failed to disable iframe pointer-events: $e',
          level: LogLevel.warn,
        );
      }
    }
  }

  /// Enable pointer-events on preview iframes (after dialog closes)
  static void enablePreviewPointerEvents() {
    if (kIsWeb) {
      try {
        const String script = '''
          (function() {
            // Enable pointer-events on iframes
            var iframes = document.querySelectorAll('iframe[data-preview-iframe="true"]');
            for (var i = 0; i < iframes.length; i++) {
              iframes[i].style.pointerEvents = 'auto';
            }
            // Also try to find iframes by ID pattern
            var allIframes = document.querySelectorAll('iframe');
            for (var i = 0; i < allIframes.length; i++) {
              if (allIframes[i].id && (allIframes[i].id.includes('unified_preview_iframe_') ||
                  allIframes[i].id.includes('html_preview_') ||
                  allIframes[i].id.includes('html_content_preview_'))) {
                allIframes[i].style.pointerEvents = 'auto';
              }
            }
            // Also enable pointer-events on flt-platform-view containers
            var platformViews = document.querySelectorAll('flt-platform-view');
            for (var i = 0; i < platformViews.length; i++) {
              var iframe = platformViews[i].querySelector('iframe');
              if (iframe && (iframe.hasAttribute('data-preview-iframe') ||
                  iframe.id && (iframe.id.includes('unified_preview_iframe_') ||
                  iframe.id.includes('html_preview_') ||
                  iframe.id.includes('html_content_preview_')))) {
                platformViews[i].style.pointerEvents = 'auto';
              }
            }
          })();
        ''';
        // Execute script using ScriptElement
        final html.ScriptElement scriptElement = html.ScriptElement()
          ..text = script;
        html.document.body?.append(scriptElement);
        // Remove script element after execution
        Future.delayed(const Duration(milliseconds: 100), scriptElement.remove);
        // Enabled preview iframe pointer-events (logging removed)
      } catch (e) {
        _dialogHelperLog(
          '[Dialog] Failed to enable iframe pointer-events: $e',
          level: LogLevel.warn,
        );
      }
    }
  }

  /// Show a dialog with automatic iframe pointer-events control
  /// This is a wrapper around Flutter's showDialog that automatically handles iframe blocking
  static Future<T?> showDialog<T>({
    required BuildContext context,
    required WidgetBuilder builder,
    bool barrierDismissible = true,
    Color? barrierColor,
    String? barrierLabel,
    bool useRootNavigator = false,
    RouteSettings? routeSettings,
    Offset? anchorPoint,
  }) async {
    _dialogHelperLog('[Dialog] Showing dialog with iframe control');

    // Disable pointer-events on iframe if present (to prevent it from blocking dialog)
    disablePreviewPointerEvents();

    // Wait a bit to ensure iframe pointer-events are disabled before showing dialog
    await Future.delayed(const Duration(milliseconds: 100));

    try {
      // Use Flutter's showDialog directly (not recursive)
      // Import showDialog from material.dart with alias to avoid recursion
      final T? result = await FlutterMaterial.showDialog<T>(
        context: context,
        builder: builder,
        barrierDismissible: barrierDismissible,
        barrierColor: barrierColor,
        barrierLabel: barrierLabel,
        useRootNavigator: useRootNavigator,
        routeSettings: routeSettings,
        anchorPoint: anchorPoint,
      );
      // Re-enable pointer-events after dialog closes
      enablePreviewPointerEvents();
      return result;
    } catch (e) {
      // Re-enable pointer-events even if dialog failed
      enablePreviewPointerEvents();
      rethrow;
    }
  }

  /// Show a general dialog with automatic iframe pointer-events control
  /// This is a wrapper around Flutter's showGeneralDialog that automatically handles iframe blocking
  static Future<T?> showGeneralDialog<T>({
    required BuildContext context,
    required RoutePageBuilder pageBuilder,
    bool barrierDismissible = true,
    Color? barrierColor,
    String? barrierLabel,
    bool useRootNavigator = false,
    RouteSettings? routeSettings,
    Offset? anchorPoint,
    RouteTransitionsBuilder? transitionBuilder,
    Duration transitionDuration = const Duration(milliseconds: 200),
  }) async {
    // Showing general dialog with iframe control (logging removed)

    // Disable pointer-events on iframe if present (to prevent it from blocking dialog)
    disablePreviewPointerEvents();

    // Wait a bit to ensure iframe pointer-events are disabled before showing dialog
    await Future.delayed(const Duration(milliseconds: 100));

    try {
      // Use Flutter's showGeneralDialog directly (not recursive)
      final T? result = await FlutterMaterial.showGeneralDialog<T>(
        context: context,
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
      // Re-enable pointer-events after dialog closes
      enablePreviewPointerEvents();
      return result;
    } catch (e) {
      // Re-enable pointer-events even if dialog failed
      enablePreviewPointerEvents();
      rethrow;
    }
  }
}
