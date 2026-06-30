/// Shared utility for constructing download filenames with a configurable suffix.
///
/// Used by html_preview, translation_result_export_service, translation_queue_screen,
/// and translation_screen to avoid duplicated filename-building logic.

import 'dart:convert';

/// Legacy suffixes baked into older exports; strip before applying current suffix.
const List<String> kLegacyOutputSuffixes = <String>[
  '_translated',
  '_converted',
];

String stripLegacyOutputSuffix(String name) {
  for (final String legacy in kLegacyOutputSuffixes) {
    if (name.endsWith(legacy)) {
      return name.substring(0, name.length - legacy.length);
    }
  }
  return name;
}

/// Build a download filename from an original name, extension, and optional suffix.
///
/// When [suffix] is empty, no suffix is appended.
/// Already-present suffixes are stripped to avoid duplication (e.g. "doc_translated_translated.pdf").
String buildDownloadFilename({
  required String originalName,
  required String extension,
  String suffix = '_translated',
}) {
  String nameWithoutExt = originalName.contains('.')
      ? originalName.substring(0, originalName.lastIndexOf('.'))
      : originalName;
  nameWithoutExt = stripLegacyOutputSuffix(nameWithoutExt);
  // Strip configured suffix to avoid duplication
  if (suffix.isNotEmpty && nameWithoutExt.endsWith(suffix)) {
    nameWithoutExt =
        nameWithoutExt.substring(0, nameWithoutExt.length - suffix.length);
  }
  return '$nameWithoutExt$suffix.$extension';
}

/// Build a folder/basename prefix without file extension (e.g. for md_zip flatten folders).
String buildDownloadBasename({
  required String originalName,
  String suffix = '_translated',
}) {
  String nameWithoutExt = originalName.contains('.')
      ? originalName.substring(0, originalName.lastIndexOf('.'))
      : originalName;
  nameWithoutExt = stripLegacyOutputSuffix(nameWithoutExt);
  if (suffix.isNotEmpty && nameWithoutExt.endsWith(suffix)) {
    nameWithoutExt =
        nameWithoutExt.substring(0, nameWithoutExt.length - suffix.length);
  }
  return '$nameWithoutExt$suffix';
}

const int _kMaxBatchFolderUtf8Bytes = 80;
final RegExp _invalidZipChars = RegExp(r'[<>:"|?*\x00-\x1f]');

String _sanitizeZipPathComponent(String name) {
  String cleaned = name.trim().replaceAll(_invalidZipChars, '_');
  cleaned = cleaned.replaceAll(RegExp(r'[. ]+$'), '');
  return cleaned.isEmpty ? 'document' : cleaned;
}

String _truncateUtf8(String text, int maxBytes) {
  final List<int> bytes = utf8.encode(text);
  if (bytes.length <= maxBytes) {
    return text;
  }
  var cut = maxBytes;
  while (cut > 0 && (bytes[cut - 1] & 0xC0) == 0x80) {
    cut--;
  }
  if (cut <= 0) {
    return 'document';
  }
  return utf8.decode(bytes.sublist(0, cut), allowMalformed: true);
}

/// Short folder name for batch md_zip export; MD file keeps the full original stem.
String makeBatchFolderName({
  required String originalName,
  required String taskId,
  String suffix = '',
}) {
  final String stem =
      _sanitizeZipPathComponent(buildDownloadBasename(
    originalName: originalName,
    suffix: suffix,
  ));
  if (utf8.encode(stem).length <= _kMaxBatchFolderUtf8Bytes) {
    return stem;
  }
  final String tid = _sanitizeZipPathComponent(
    taskId.length > 8 ? taskId.substring(0, 8) : taskId,
  );
  final int budget =
      _kMaxBatchFolderUtf8Bytes - utf8.encode('_$tid').length;
  return '${_truncateUtf8(stem, budget.clamp(8, stem.length))}_$tid';
}
