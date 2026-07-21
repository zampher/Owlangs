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
        : folderName;
    final Archive? inner = _decodeZipBytes(fileBytes);
    if (inner != null) {
      for (final ArchiveFile file in inner.files) {
        if (!file.isFile) {
          continue;
        }
        String innerPath = file.name.replaceAll('\\', '/');
        if (innerPath.toLowerCase().endsWith('.zip')) {
          // Never nest an inner zip payload.
          continue;
        }
        if (innerPath.toLowerCase().endsWith('.md')) {
          innerPath = mdFileName;
        } else {
          final int imagesIdx = innerPath.toLowerCase().indexOf('images/');
          if (imagesIdx >= 0) {
            innerPath = innerPath.substring(imagesIdx);
          } else if (!innerPath.contains('/')) {
            innerPath = 'images/$innerPath';
          }
        }
        final String entryName = _resolveArchiveEntryConflict(
          '$folderPrefix/$innerPath',
          dirCounters,
        );
        archive.addFile(ArchiveFile(entryName, file.size, file.content));
      }
      return;
    }
    // Not a ZIP (or decode failed): store as a plain markdown file under the folder.
    final String entryName = _resolveArchiveEntryConflict(
      '$folderPrefix/$mdFileName',
      dirCounters,
    );
    archive.addFile(ArchiveFile(entryName, fileBytes.length, fileBytes));
    return;
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

Archive? _decodeZipBytes(List<int> fileBytes) {
  try {
    return ZipDecoder().decodeBytes(fileBytes);
  } catch (_) {
    try {
      return ZipDecoder().decodeBytes(fileBytes, verify: false);
    } catch (_) {
      return null;
    }
  }
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
