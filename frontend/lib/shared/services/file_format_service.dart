// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

// OpenSource edition removes donor/pro authorization gating for supported formats.

/// Service for managing file format support based on user edition
class FileFormatService {
  factory FileFormatService() => _instance;
  FileFormatService._internal();
  static final FileFormatService _instance = FileFormatService._internal();

  // Basic formats available to Standard edition (no activation required)
  static const List<String> _freeFormats = <String>[
    'pdf',
    'docx',
    'txt',
    'md',
    'html',
    'htm',
    'srt',
  ];

  // Pro-only formats (EPUB, MOBI, and others); require activation to use
  static const List<String> _donorFormats = <String>[
    'pptx',
    'xlsx',
    'xls',
    'csv',
    'epub',
    'mobi',
    'azw',
    'json',
    'arb',
    'ts',
    'png',
    'jpg',
    'jpeg',
  ];

  /// Get all supported formats (free + donor)
  List<String> getAllFormats() => <String>[..._freeFormats, ..._donorFormats];

  /// Get formats available to free users
  List<String> getFreeFormats() => List<String>.unmodifiable(_freeFormats);

  /// Get formats available only to donor users
  List<String> getDonorFormats() => List<String>.unmodifiable(_donorFormats);

  /// Get formats available to current user.
  ///
  /// OpenSource edition enables all supported formats on both desktop and web.
  Future<List<String>> getAvailableFormats() async {
    // OpenSource edition: desktop + web do not enforce donor/pro authorization.
    // All formats are available.
    return getAllFormats();
  }

  /// Check if a file format is supported for current user
  Future<bool> isFormatSupported(String extension) async {
    final normalizedExt = extension.toLowerCase().replaceAll('.', '');
    final availableFormats = await getAvailableFormats();
    return availableFormats.contains(normalizedExt);
  }

  /// Check if a file format requires donor activation
  bool isDonorOnlyFormat(String extension) {
    final normalizedExt = extension.toLowerCase().replaceAll('.', '');
    return _donorFormats.contains(normalizedExt);
  }

  /// Check if a file format is free (available to all users)
  bool isFreeFormat(String extension) {
    final normalizedExt = extension.toLowerCase().replaceAll('.', '');
    return _freeFormats.contains(normalizedExt);
  }

  /// Get user-friendly format name
  String getFormatDisplayName(String extension) {
    final normalizedExt = extension.toLowerCase().replaceAll('.', '');
    final formatNames = <String, String>{
      'pdf': 'PDF',
      'docx': 'Word (DOCX)',
      'pptx': 'PowerPoint (PPTX)',
      'xlsx': 'Excel (XLSX)',
      'csv': 'CSV',
      'txt': 'Text',
      'md': 'Markdown',
      'html': 'HTML',
      'htm': 'HTML',
      'epub': 'EPUB',
      'mobi': 'MOBI',
      'json': 'JSON',
      'arb': 'ARB (JSON)',
      'srt': 'Subtitle (SRT)',
      'ts': 'Qt Translation (TS)',
      'png': 'PNG Image',
      'jpg': 'JPEG Image',
      'jpeg': 'JPEG Image',
    };
    return formatNames[normalizedExt] ?? normalizedExt.toUpperCase();
  }

  /// Get error message for unsupported format (Pro-only: English hint for activation)
  String getUnsupportedFormatMessage(String extension) {
    // Since OpenSource edition enables all formats, this message should only
    // be shown for truly unknown/unsupported extensions.
    return 'File format ${getFormatDisplayName(extension)} is not supported.';
  }

  /// Display string listing all supported formats (for upload area hint)
  String getSupportedFormatsDisplayString() {
    final names = getAllFormats().map(getFormatDisplayName).toSet();
    return names.join(', ');
  }
}
