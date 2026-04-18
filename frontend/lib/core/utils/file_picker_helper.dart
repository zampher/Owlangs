// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;

/// Unified file picker helper
class FilePickerHelper {
  /// Pick files
  static Future<FilePickerResult?> pickFiles({
    FileType type = FileType.any,
    List<String>? allowedExtensions,
    bool allowMultiple = false,
    bool withData = false,
    bool withReadStream = false,
    bool lockParentWindow = false,
    String? dialogTitle,
  }) async {
    // Ensure withData is true on Web (required for file access)
    final bool effectiveWithData = kIsWeb ? true : withData;

    return FilePicker.platform.pickFiles(
      type: type,
      allowedExtensions: allowedExtensions,
      allowMultiple: allowMultiple,
      withData: effectiveWithData,
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

  /// Check if running on Web platform
  static bool get isWeb => kIsWeb;

  /// Check if running on desktop platform
  static bool get isDesktop => !kIsWeb;
}
