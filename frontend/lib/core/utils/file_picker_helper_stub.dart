// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

/// Stub for [webPickFiles] — delegates to [FilePicker.platform.pickFiles].
library;

import 'package:file_picker/file_picker.dart';

/// Picks files on desktop/native platforms via the file_picker plugin.
Future<FilePickerResult?> webPickFiles({
  String? dialogTitle,
  FileType type = FileType.any,
  List<String>? allowedExtensions,
  bool allowMultiple = false,
  bool withData = false,
  bool withReadStream = false,
  bool lockParentWindow = false,
}) {
  return FilePicker.platform.pickFiles(
    dialogTitle: dialogTitle,
    type: type,
    allowedExtensions: allowedExtensions,
    allowMultiple: allowMultiple,
    withData: withData,
    withReadStream: withReadStream,
    lockParentWindow: lockParentWindow,
  );
}
