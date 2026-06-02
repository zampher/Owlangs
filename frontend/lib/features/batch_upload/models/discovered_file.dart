// SPDX-FileCopyrightText: 2026 Owlangs
// SPDX-License-Identifier: MPL-2.0

/// A file discovered during batch folder / ZIP scanning.
///
/// Holds metadata and byte content so it can be submitted as a queued
/// translation task without re-reading the source.
class DiscoveredFile {
  final String fileName;
  final int fileSizeBytes;
  List<int>? fileBytes;
  String? filePath;
  String? relativePath;
  bool isSelected;

  DiscoveredFile({
    required this.fileName,
    required this.fileSizeBytes,
    this.fileBytes,
    this.filePath,
    this.relativePath,
    this.isSelected = true,
  });

  String get extension {
    final dot = fileName.lastIndexOf('.');
    return dot >= 0 ? fileName.substring(dot + 1) : '';
  }

  String get formattedSize {
    if (fileSizeBytes < 1024) return '$fileSizeBytes B';
    if (fileSizeBytes < 1024 * 1024) {
      return '${(fileSizeBytes / 1024).toStringAsFixed(1)} KB';
    }
    return '${(fileSizeBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}
