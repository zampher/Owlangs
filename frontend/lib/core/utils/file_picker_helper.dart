// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;

// Web: use dart:html directly (avoids file_picker's unreliable focus heuristic).
// Non-web: delegate to FilePicker.platform.
import 'file_picker_helper_stub.dart'
    if (dart.library.html) 'file_picker_helper_web.dart'
    as web;

/// Unified file picker helper.
///
/// On Flutter Web this uses [dart:html] directly to avoid [file_picker]'s
/// ``window.focus`` cancellation detection, which fires spuriously inside
/// Flutter's canvas and causes the picker to return ``null``.
class FilePickerHelper {
  /// Pick files.
  ///
  /// On web the implementation bypasses the [file_picker] package entirely
  /// and uses a direct ``<input type="file">`` element for reliable operation.
  /// On desktop/native it delegates to [FilePicker.platform.pickFiles].
  static Future<FilePickerResult?> pickFiles({
    FileType type = FileType.any,
    List<String>? allowedExtensions,
    bool allowMultiple = false,
    bool withData = false,
    bool withReadStream = false,
    bool lockParentWindow = false,
    String? dialogTitle,
  }) async {
    if (kIsWeb) {
      return web.webPickFiles(
        dialogTitle: dialogTitle,
        type: type,
        allowedExtensions: allowedExtensions,
        allowMultiple: allowMultiple,
        withData: true, // always required on web
        withReadStream: withReadStream,
        lockParentWindow: lockParentWindow,
      );
    }

    // Desktop / mobile: delegate to file_picker plugin.
    return FilePicker.platform.pickFiles(
      type: type,
      allowedExtensions: allowedExtensions,
      allowMultiple: allowMultiple,
      withData: withData,
      withReadStream: withReadStream,
      lockParentWindow: lockParentWindow,
      dialogTitle: dialogTitle,
    );
  }

  /// Save file with Web-optimized settings
  ///
  /// On Web platform, this uses browser's download functionality.
  /// On desktop platforms, it uses the platform-specific save dialog.
  ///
  /// Note: This method only returns the save path. To actually save file content,
  /// use FileSaver on Web or write to the returned path on desktop.
  static Future<String?> saveFile({
    String? fileName,
    String? dialogTitle,
    FileType type = FileType.any,
    List<String>? allowedExtensions,
    bool lockParentWindow = false,
  }) async {
    // On Web, file_picker automatically uses browser download dialog
    // On desktop, it uses native save dialog
    return FilePicker.platform.saveFile(
      fileName: fileName,
      dialogTitle: dialogTitle,
      type: type,
      allowedExtensions: allowedExtensions,
      lockParentWindow: lockParentWindow,
    );
  }

  /// Pick a directory (desktop only).
  ///
  /// Returns the absolute path of the selected directory, or ``null`` if the
  /// user cancelled the dialog.  Returns ``null`` on web where directory
  /// picking is not supported by the [file_picker] plugin.
  static Future<String?> pickDirectory({String? dialogTitle}) async {
    if (kIsWeb) return null;
    return FilePicker.platform.getDirectoryPath(dialogTitle: dialogTitle);
  }

  /// Pick a directory on web and return its files.
  ///
  /// Uses the HTML ``webkitdirectory`` attribute to let the user select a
  /// folder.  Each returned [PlatformFile] has its [PlatformFile.name] set to
  /// the path relative to the selected directory root.
  ///
  /// Returns ``null`` when cancelled, or on non-web platforms.
  static Future<List<PlatformFile>?> pickDirectoryFiles({
    String? dialogTitle,
  }) async {
    if (kIsWeb) {
      return web.webPickDirectoryFiles(dialogTitle: dialogTitle);
    }
    return null;
  }

  /// Check if running on Web platform
  static bool get isWeb => kIsWeb;

  /// Check if running on desktop platform
  static bool get isDesktop => !kIsWeb;
}
