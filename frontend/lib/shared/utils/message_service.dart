// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show debugPrint;

/// Unified message service for displaying copyable error/success messages
///
/// **IMPORTANT: All error and info messages MUST use this service to ensure they are copyable.**
///
/// Usage examples:
/// ```dart
/// // Show error (red background)
/// MessageService.showError(context, 'Failed to save: $e');
///
/// // Show success (green background)
/// MessageService.showSuccess(context, 'File saved successfully');
///
/// // Show warning (orange background)
/// MessageService.showWarning(context, 'Warning: Invalid input');
///
/// // Show info (blue background)
/// MessageService.showInfo(context, 'Processing...');
///
/// // Custom color and duration
/// MessageService.showMessage(context, 'Custom message',
///   color: Colors.purple,
///   duration: Duration(seconds: 10)
/// );
/// ```
///
/// Features:
/// - All messages are selectable (SelectableText)
/// - All messages have a "Copy" button for easy error reporting
/// - All messages have a close button (X icon) to dismiss manually
/// - Consistent styling and behavior across the app
/// - Floating behavior for better visibility
///
/// **DO NOT use ScaffoldMessenger.showSnackBar directly for error messages.**
/// Always use MessageService to ensure messages are copyable.
class MessageService {
  /// Show a message with copy functionality
  ///
  /// [context] - BuildContext to show the message
  /// [message] - Message text to display (will be selectable and copyable)
  /// [color] - Background color (default: red for errors)
  /// [duration] - How long to show the message (default: 6 seconds)
  /// [icon] - Optional icon to show before the message
  static void showMessage(
    BuildContext context,
    String message, {
    Color color = Colors.red,
    Duration? duration,
    IconData? icon,
  }) {
    // Use maybeOf to avoid exceptions when ancestor is deactivated
    final ScaffoldMessengerState? messenger =
        ScaffoldMessenger.maybeOf(context);
    if (messenger == null) {
      // Context is no longer valid; silently ignore to avoid crashing
      return;
    }

    // Wrap showSnackBar in try-catch as context may become invalid between maybeOf check and showSnackBar call
    try {
      messenger.showSnackBar(
        SnackBar(
          content: Row(
            children: <Widget>[
              if (icon != null) ...<Widget>[
                Icon(icon, color: Colors.white, size: 20),
                const SizedBox(width: 8),
              ],
              Expanded(
                child: SelectableText(
                  message,
                  style: const TextStyle(color: Colors.white),
                ),
              ),
              const SizedBox(width: 8),
              // Copy button - copy message to clipboard
              TextButton(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: message));
                  final ScaffoldMessengerState? m =
                      ScaffoldMessenger.maybeOf(context);
                  if (m == null) return;
                  m.hideCurrentSnackBar();
                  m.showSnackBar(
                    const SnackBar(
                      content: Row(
                        children: <Widget>[
                          Icon(
                            Icons.check_circle,
                            color: Colors.white,
                            size: 20,
                          ),
                          SizedBox(width: 8),
                          Text('Message copied to clipboard'),
                        ],
                      ),
                      backgroundColor: Colors.green,
                      duration: Duration(seconds: 2),
                      behavior: SnackBarBehavior.floating,
                      margin: EdgeInsets.all(16),
                    ),
                  );
                },
                child: const Text(
                  'Copy',
                  style: TextStyle(color: Colors.white),
                ),
              ),
              const SizedBox(width: 4),
              // Close button - allows user to dismiss the message manually (at the rightmost position)
              IconButton(
                icon: const Icon(Icons.close, color: Colors.white, size: 20),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                onPressed: () {
                  final ScaffoldMessengerState? m =
                      ScaffoldMessenger.maybeOf(context);
                  if (m != null) {
                    m.hideCurrentSnackBar();
                  }
                },
              ),
            ],
          ),
          backgroundColor: color,
          duration: duration ?? const Duration(seconds: 6),
          behavior: SnackBarBehavior.floating,
          margin: const EdgeInsets.all(16),
        ),
      );
    } catch (e) {
      // Context became invalid between maybeOf check and showSnackBar call
      // Silently ignore to avoid crashing
      debugPrint(
        'MessageService: Failed to show message (context invalid): $e',
      );
    }
  }

  /// Show an error message (red background)
  static void showError(
    BuildContext context,
    String message, {
    Duration? duration,
  }) {
    showMessage(
      context,
      message,
      icon: Icons.error,
      duration: duration,
    );
  }

  /// Show a success message (green background)
  static void showSuccess(
    BuildContext context,
    String message, {
    Duration? duration,
  }) {
    showMessage(
      context,
      message,
      color: Colors.green,
      icon: Icons.check_circle,
      duration: duration ?? const Duration(seconds: 3),
    );
  }

  /// Show a warning message (orange background)
  static void showWarning(
    BuildContext context,
    String message, {
    Duration? duration,
  }) {
    showMessage(
      context,
      message,
      color: Colors.orange,
      icon: Icons.warning,
      duration: duration,
    );
  }

  /// Show an info message (blue background)
  static void showInfo(
    BuildContext context,
    String message, {
    Duration? duration,
  }) {
    showMessage(
      context,
      message,
      color: Colors.blue,
      icon: Icons.info,
      duration: duration ?? const Duration(seconds: 4),
    );
  }
}
