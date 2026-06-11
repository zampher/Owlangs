// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

/// Web-native file picker that uses [dart:html] directly, bypassing the
/// [file_picker] package's unreliable ``window.focus`` cancellation detection.
///
/// [file_picker 6.2.1] registers a ``window.focus`` listener to detect when
/// the user cancels the file dialog.  On Flutter Web the ``focus`` event fires
/// far more often than expected (Flutter's internal focus management), which
/// causes the picker to return ``null`` spuriously.
///
/// This implementation uses only the ``change`` / ``cancel`` events on the
/// hidden ``<input type="file">`` element and adds a generous timeout as
/// cancellation fallback, avoiding the problematic ``focus`` heuristic.
library;

import 'dart:async';
import 'dart:html';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show debugPrint, kDebugMode;

/// Picks files on web via a direct ``<input type="file">`` element.
///
/// Returns a [FilePickerResult] compatible with the rest of the codebase, or
/// ``null`` if the user cancelled / the dialog was blocked.
Future<FilePickerResult?> webPickFiles({
  String? dialogTitle,
  FileType type = FileType.any,
  List<String>? allowedExtensions,
  bool allowMultiple = false,
  bool withData = true,
  bool withReadStream = false,
  bool lockParentWindow = false,
}) async {
  final completer = Completer<FilePickerResult?>();
  bool resolved = false;

  // Build the accept attribute from allowed extensions.
  String accept = '';
  if (type == FileType.custom && allowedExtensions != null) {
    accept = allowedExtensions.map((ext) => '.$ext').join(',');
  } else {
    accept = _acceptFromType(type);
  }

  final input = document.createElement('input') as InputElement
    ..type = 'file'
    ..accept = accept
    ..multiple = allowMultiple
    ..style.display = 'none';

  void resolve(FilePickerResult? result) {
    if (resolved) return;
    resolved = true;
    if (input.parentNode != null) input.remove();
    completer.complete(result);
  }

  // --- Change event: file(s) selected ---
  input.addEventListener('change', (e) {
    final files = input.files;
    if (files == null || files.isEmpty) {
      resolve(null);
      return;
    }

    final pickedFiles = <PlatformFile>[];
    int remaining = files.length;

    for (final file in files) {
      final reader = FileReader();

      reader.addEventListener('loadend', (_) {
        pickedFiles.add(PlatformFile(
          name: file.name,
          size: file.size,
          bytes: reader.result is Uint8List ? reader.result as Uint8List : null,
        ));
        remaining--;
        if (remaining == 0) {
          resolve(FilePickerResult(List.unmodifiable(pickedFiles)));
        }
      });

      reader.addEventListener('error', (_) {
        remaining--;
        if (remaining == 0) {
          // Return whatever we managed to read so far.
          resolve(
            pickedFiles.isNotEmpty
                ? FilePickerResult(List.unmodifiable(pickedFiles))
                : null,
          );
        }
      });

      reader.readAsArrayBuffer(file);
    }
  });

  // --- Cancel event: user pressed Escape / Cancel button ---
  // Not supported in all browsers, but a nice fast-path when available.
  input.addEventListener('cancel', (_) => resolve(null));

  // --- Timeout fallback (5 minutes) ---
  // If the user opens the dialog and walks away, don't leak the completer.
  final timeout = Timer(const Duration(minutes: 5), () {
    if (kDebugMode) {
      print('[FilePickerWeb] Timeout after 5 minutes, cancelling');
    }
    resolve(null);
  });

  // Attach to DOM and trigger click.
  document.body!.append(input);

  // Use a microtask to ensure the element is in the DOM before clicking.
  await Future<void>.microtask(() {});
  input.click();

  final result = await completer.future;
  timeout.cancel();
  return result;
}

/// Picks a directory on web via ``<input type="file" webkitdirectory>``.
///
/// Returns the list of files with their [PlatformFile.name] set to the
/// path relative to the selected directory (e.g. ``"subdir/file.docx"``),
/// or ``null`` if the user cancelled.
Future<List<PlatformFile>?> webPickDirectoryFiles({
  String? dialogTitle,
}) async {
  final completer = Completer<List<PlatformFile>?>();
  bool resolved = false;

  final input = document.createElement('input') as InputElement
    ..type = 'file'
    ..setAttribute('webkitdirectory', '')
    ..style.display = 'none';

  void resolveResult(List<PlatformFile>? result) {
    if (resolved) return;
    resolved = true;
    if (input.parentNode != null) input.remove();
    completer.complete(result);
  }

  input.addEventListener('change', (e) {
    final files = input.files;
    if (files == null || files.isEmpty) {
      resolveResult(null);
      return;
    }

    final pickedFiles = <PlatformFile>[];
    int remaining = files.length;

    for (final file in files) {
      final reader = FileReader();

      reader.addEventListener('loadend', (_) {
        // Access webkitRelativePath via dynamic cast to preserve directory structure
        // when the user picks a folder. The webkitdirectory attribute ensures this
        // property is available on File objects from directory selection.
        String relPath;
        try {
          final dynamic fileDynamic = file;
          final wrp = fileDynamic.webkitRelativePath;
          relPath = (wrp is String && wrp.isNotEmpty) ? wrp : file.name;
        } catch (_) {
          relPath = file.name;
        }
        debugPrint('[FilePickerWeb] Directory file: name=${file.name}, webkitRelativePath=$relPath');
        pickedFiles.add(PlatformFile(
          name: relPath,
          size: file.size,
          bytes: reader.result is Uint8List ? reader.result as Uint8List : null,
        ));
        remaining--;
        if (remaining == 0) {
          resolveResult(List.unmodifiable(pickedFiles));
        }
      });

      reader.addEventListener('error', (_) {
        remaining--;
        if (remaining == 0) {
          resolveResult(
            pickedFiles.isNotEmpty ? List.unmodifiable(pickedFiles) : null,
          );
        }
      });

      reader.readAsArrayBuffer(file);
    }
  });

  input.addEventListener('cancel', (_) => resolveResult(null));

  final timeout = Timer(const Duration(minutes: 5), () {
    if (kDebugMode) {
      print('[FilePickerWeb] Directory picker timeout after 5 minutes');
    }
    resolveResult(null);
  });

  document.body!.append(input);
  await Future<void>.microtask(() {});
  input.click();

  final result = await completer.future;
  timeout.cancel();
  return result;
}

String _acceptFromType(FileType type) {
  switch (type) {
    case FileType.any:
      return '';
    case FileType.image:
      return 'image/*';
    case FileType.video:
      return 'video/*';
    case FileType.audio:
      return 'audio/*';
    case FileType.media:
      return 'video/*,image/*';
    case FileType.custom:
      return '';
  }
}
