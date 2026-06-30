// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:archive/archive.dart';

import 'download_filename_builder.dart';

/// Add one downloaded file into a batch archive, flattening md_zip instead of nesting ZIPs.
void addDownloadBytesToBatchArchive({
  required Archive archive,
  required List<int> fileBytes,
  required String formatKey,
  required String baseName,
  required String suffix,
  required String relativePath,
  required String taskId,
  required Map<String, int> dirCounters,
}) {
  final String ext = _extensionForFormat(formatKey);

  if (formatKey == 'md_zip') {
    final String folderName = makeBatchFolderName(
      originalName: baseName,
      taskId: taskId,
      suffix: suffix,
    );
    final String mdFileName = buildDownloadFilename(
      originalName: baseName,
      extension: 'md',
      suffix: suffix,
    );
    final String folderPrefix = relativePath.isNotEmpty
        ? '$relativePath/$folderName'
        : '$taskId/$folderName';
    try {
      final Archive inner = ZipDecoder().decodeBytes(fileBytes);
      for (final ArchiveFile file in inner.files) {
        if (!file.isFile) {
          continue;
        }
        String innerPath = file.name.replaceAll('\\', '/');
        if (innerPath.toLowerCase().endsWith('.md')) {
          innerPath = mdFileName;
        }
        final String entryName = _resolveArchiveEntryConflict(
          '$folderPrefix/$innerPath',
          dirCounters,
        );
        archive.addFile(ArchiveFile(entryName, file.size, file.content));
      }
      return;
    } catch (_) {
      final String entryName = _resolveArchiveEntryConflict(
        relativePath.isNotEmpty
            ? '$relativePath/${buildDownloadFilename(originalName: baseName, extension: ext, suffix: suffix)}'
            : '$taskId/${buildDownloadFilename(originalName: baseName, extension: ext, suffix: suffix)}',
        dirCounters,
      );
      archive.addFile(ArchiveFile(entryName, fileBytes.length, fileBytes));
      return;
    }
  }

  final String fileName = buildDownloadFilename(
    originalName: baseName,
    extension: ext,
    suffix: suffix,
  );
  final String entryName = relativePath.isNotEmpty
      ? _resolveArchiveEntryConflict('$relativePath/$fileName', dirCounters)
      : _resolveArchiveEntryConflict('$taskId/$fileName', dirCounters);
  archive.addFile(ArchiveFile(entryName, fileBytes.length, fileBytes));
}

String _extensionForFormat(String formatKey) {
  switch (formatKey) {
    case 'docx':
      return 'docx';
    case 'html':
      return 'html';
    case 'md':
      return 'md';
    case 'md_zip':
      return 'zip';
    case 'pdf':
    case 'pdf_reflow':
      return 'pdf';
    case 'txt':
      return 'txt';
    default:
      return formatKey;
  }
}

String _resolveArchiveEntryConflict(String name, Map<String, int> dirCounters) {
  final int count = (dirCounters[name] ?? 0) + 1;
  dirCounters[name] = count;
  if (count == 1) {
    return name;
  }
  if (name.contains('.')) {
    final int dot = name.lastIndexOf('.');
    final String base = name.substring(0, dot);
    final String ext = name.substring(dot + 1);
    return '$base ($count).$ext';
  }
  return '$name ($count)';
}
