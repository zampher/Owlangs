/// Shared utility for constructing download filenames with a configurable suffix.
///
/// Used by html_preview, translation_result_export_service, translation_queue_screen,
/// and translation_screen to avoid duplicated filename-building logic.

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
  // Strip existing suffix to avoid duplication
  if (suffix.isNotEmpty && nameWithoutExt.endsWith(suffix)) {
    nameWithoutExt =
        nameWithoutExt.substring(0, nameWithoutExt.length - suffix.length);
  }
  return '$nameWithoutExt$suffix.$extension';
}
