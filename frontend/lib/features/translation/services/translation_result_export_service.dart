// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:typed_data';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'dart:io' if (dart.library.html) '../../../shared/utils/io_stub.dart'
    as io;
import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/app_logger.dart';

/// Service for handling translation result export and download
class TranslationResultExportService {
  TranslationResultExportService(this.taskId, this.fileName);

  final String taskId;
  final String? fileName;

  /// Build download URL with format parameters
  String buildDownloadUrl(
    String fileType, {
    String? tableFormat,
    String? equationFormat,
    bool? embedImages,
  }) {
    final svc = TranslationService();
    String downloadUrl = svc.buildDownloadUrl(taskId, fileType);

    // Add format parameters as query parameters for MD, HTML, DOCX, PDF
    if (fileType == 'md' ||
        fileType == 'html' ||
        fileType == 'docx' ||
        fileType == 'pdf') {
      final uri = Uri.parse(downloadUrl);
      final queryParams = Map<String, String>.from(uri.queryParameters);

      // Add table format parameter if selected
      if (tableFormat != null) {
        queryParams['table_body_format'] = tableFormat;
      }

      // Add equation format parameter if selected
      if (equationFormat != null) {
        queryParams['equation_format'] = equationFormat;
      }

      // For MD downloads, add embed_images parameter
      if (fileType == 'md' && embedImages != null) {
        queryParams['embed_images'] = embedImages.toString();
      }

      // Rebuild URI with query parameters
      downloadUrl = uri.replace(queryParameters: queryParams).toString();
    }

    return downloadUrl;
  }

  /// Download and save file
  Future<void> downloadAndSave(
    String fileType, {
    String? tableFormat,
    String? equationFormat,
    bool? embedImages,
  }) async {
    try {
      final svc = TranslationService();
      final downloadUrl = buildDownloadUrl(
        fileType,
        tableFormat: tableFormat,
        equationFormat: equationFormat,
        embedImages: embedImages,
      );

      AppLogger.log(
        'TranslationResultExportService',
        '[Download] Building download URL for taskId: $taskId, fileType: $fileType',
        level: LogLevel.info,
      );
      AppLogger.log(
        'TranslationResultExportService',
        '[Download] Download URL: $downloadUrl',
        level: LogLevel.info,
      );

      // Download file bytes
      final bytes = await svc.downloadFile(downloadUrl);

      if (bytes.isEmpty) {
        throw Exception('Failed to download $fileType: Empty response');
      }

      // Generate filename based on original file name or default
      final originalName = fileName ?? 'translated';
      // Remove all extensions from original filename (handle cases like document.md.md)
      // Split by '.' and take all parts except the last one, then join them
      final nameParts = originalName.split('.');
      String nameWithoutExt;
      if (nameParts.length > 1) {
        // Remove the last part (extension) and join the rest
        nameWithoutExt = nameParts.sublist(0, nameParts.length - 1).join('.');
      } else {
        // No extension found, use the whole name
        nameWithoutExt = originalName;
      }
      // Remove '_translated' suffix if it already exists to avoid duplication
      if (nameWithoutExt.endsWith('_translated')) {
        nameWithoutExt = nameWithoutExt.substring(
          0,
          nameWithoutExt.length - '_translated'.length,
        );
      }
      final extension = fileType == 'md' ? 'md' : fileType;
      final filename = '${nameWithoutExt}_translated.$extension';

      // Save file (Web or Desktop)
      if (kIsWeb) {
        // Web: use FileSaver
        await _saveFileWeb(filename, bytes, fileType);
      } else {
        // Desktop: use FilePicker to save
        await _saveFileDesktop(filename, bytes, fileType);
      }

      AppLogger.log(
        'TranslationResultExportService',
        'File exported successfully: $filename',
        level: LogLevel.info,
      );
    } catch (e) {
      AppLogger.log(
        'TranslationResultExportService',
        'Failed to export $fileType: $e',
        level: LogLevel.error,
      );
      rethrow;
    }
  }

  Future<void> _saveFileWeb(
    String filename,
    List<int> bytes,
    String fileType,
  ) async {
    // Map file type to MimeType enum
    final mimeType = _getMimeTypeEnum(fileType);

    // Extract name without extension for FileSaver
    // FileSaver will add the extension from 'ext' parameter
    String nameWithoutExt = filename;
    if (filename.contains('.')) {
      final lastDotIndex = filename.lastIndexOf('.');
      nameWithoutExt = filename.substring(0, lastDotIndex);
    }

    await FileSaver.instance.saveFile(
      name: nameWithoutExt,
      bytes: Uint8List.fromList(bytes),
      ext: fileType,
      mimeType: mimeType,
    );
  }

  Future<void> _saveFileDesktop(
    String filename,
    List<int> bytes,
    String fileType,
  ) async {
    if (kIsWeb) {
      // Fallback to web save method if somehow called on web
      await _saveFileWeb(filename, bytes, fileType);
      return;
    }

    final path = await FilePicker.platform.saveFile(
      dialogTitle: 'Save Exported File',
      fileName: filename,
      type: FileType.custom,
      allowedExtensions: <String>[fileType],
    );

    if (path != null) {
      // Write file bytes to path (only on non-web platforms)
      await _writeFileBytes(path, bytes);
    }
  }

  /// Helper function to write file bytes (only works on non-web platforms)
  Future<void> _writeFileBytes(String path, List<int> bytes) async {
    if (kIsWeb) {
      throw UnsupportedError('File.writeAsBytes is not supported on web');
    }
    // This will only compile on non-web platforms due to conditional import
    final file = io.File(path);
    await file.writeAsBytes(bytes, flush: true);
  }

  MimeType _getMimeTypeEnum(String fileType) {
    switch (fileType.toLowerCase()) {
      case 'docx':
        return MimeType.microsoftWord;
      case 'pdf':
        return MimeType.pdf;
      case 'html':
        return MimeType.other; // HTML as other (file_saver doesn't have html)
      case 'md':
        return MimeType.other; // Markdown as text/plain
      case 'ts':
        return MimeType.other; // Qt .ts file as XML
      default:
        return MimeType.other;
    }
  }

  /// Get icon for file format
  static IconData getFormatIcon(String format) {
    switch (format.toLowerCase()) {
      case 'md':
        return Icons.description;
      case 'html':
        return Icons.code;
      case 'docx':
        return Icons.description;
      case 'pdf':
        return Icons.picture_as_pdf;
      default:
        return Icons.file_download;
    }
  }
}
