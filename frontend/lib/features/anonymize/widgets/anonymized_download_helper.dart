// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb, kDebugMode;
import 'dart:developer' show log;
import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'dart:convert';
import '../../../shared/utils/message_service.dart';
import '../../../shared/services/anonymize_service.dart';

/// Helper class for downloading anonymized documents
class AnonymizedDownloadHelper {
  /// Get MimeType enum for file format
  static MimeType getMimeTypeEnum(String fileType) {
    switch (fileType.toLowerCase()) {
      case 'docx':
        return MimeType.microsoftWord;
      case 'pdf':
        return MimeType.pdf;
      case 'html':
      case 'txt':
      case 'md':
      case 'epub':
      case 'mobi':
      case 'azw':
        return MimeType.other;
      default:
        return MimeType.other;
    }
  }

  /// Download anonymized text in text mode
  static Future<void> downloadTextMode({
    required BuildContext context,
    required String anonymizedText,
    required String originalFileName,
  }) async {
    final String fileExtension = originalFileName.contains('.')
        ? originalFileName.split('.').last.toLowerCase()
        : 'txt';

    final List<String> textBasedFormats = <String>[
      'txt',
      'md',
      'json',
      'csv',
      'html',
      'htm',
      'xml',
    ];
    var finalExtension = fileExtension;
    var fileName =
        'anonymized_${originalFileName.replaceAll(RegExp(r'\.[^.]+$'), '')}';

    if (textBasedFormats.contains(fileExtension)) {
      finalExtension = fileExtension;
    } else {
      finalExtension = 'txt';
      fileName = '${fileName}_as_text';
    }

    final Uint8List bytes = utf8.encode(anonymizedText);
    final String finalFileName = '$fileName.$finalExtension';

    if (kIsWeb) {
      await FileSaver.instance.saveFile(
        name: fileName,
        bytes: bytes,
        ext: finalExtension,
      );
    } else {
      final String? path = await FilePicker.platform.saveFile(
        dialogTitle: 'Save Anonymized Document',
        fileName: finalFileName,
        type: FileType.custom,
        allowedExtensions: <String>[finalExtension],
      );
      if (path != null) {
        final File file = File(path);
        await file.writeAsBytes(bytes, flush: true);
      }
    }

    if (context.mounted) {
      if (finalExtension != fileExtension) {
        MessageService.showInfo(
          context,
          'Document saved as .txt (format conversion not available). Content matches panel display.',
        );
      } else {
        MessageService.showSuccess(
          context,
          'Anonymized document downloaded successfully',
        );
      }
    }
  }

  /// Download anonymized document in segment mode
  static Future<void> downloadSegmentMode({
    required BuildContext context,
    required String workflowId,
    required List<String> originalSegments,
    required List<String> anonymizedSegments,
    required String originalFileName,
  }) async {
    if (originalSegments.isEmpty || anonymizedSegments.isEmpty) {
      if (context.mounted) {
        MessageService.showError(
          context,
          'Segments not loaded. Please wait for segments to load.',
        );
      }
      return;
    }

    if (anonymizedSegments.length != originalSegments.length) {
      if (context.mounted) {
        MessageService.showError(
          context,
          'Segment count mismatch. Please reload segments.',
        );
      }
      return;
    }

    if (kDebugMode) {
      var hasPlaceholders = false;
      for (final String seg in anonymizedSegments) {
        if (seg.contains('[') && seg.contains(']')) {
          hasPlaceholders = true;
          break;
        }
      }
      log(
        '[AnonymizedDownloadHelper] Download: hasPlaceholders=$hasPlaceholders, segmentCount=${anonymizedSegments.length}',
      );
      if (anonymizedSegments.isNotEmpty) {
        log(
          '[AnonymizedDownloadHelper] First anonymized segment preview: ${anonymizedSegments[0].substring(0, anonymizedSegments[0].length > 100 ? 100 : anonymizedSegments[0].length)}',
        );
      }
    }

    final List<Map<String, dynamic>> segmentsData = <Map<String, dynamic>>[];
    for (var i = 0; i < anonymizedSegments.length; i++) {
      final String originalSeg =
          i < originalSegments.length ? originalSegments[i] : '';
      final String anonymizedSeg = anonymizedSegments[i];

      segmentsData.add(<String, dynamic>{
        'segment_index': i,
        'original_text': originalSeg,
        'anonymized_text': anonymizedSeg,
      });

      if (kDebugMode && i < 3) {
        log(
          '[AnonymizedDownloadHelper] Segment $i: original_len=${originalSeg.length}, anonymized_len=${anonymizedSeg.length}',
        );
        log(
          '[AnonymizedDownloadHelper] Segment $i anonymized preview: ${anonymizedSeg.substring(0, anonymizedSeg.length > 50 ? 50 : anonymizedSeg.length)}',
        );
      }
    }

    try {
      final AnonymizeService anonymizeService = AnonymizeService();
      final Uint8List bytes =
          await anonymizeService.rebuildDocumentFromSegments(
        workflowId,
        segmentsData,
      );

      final String fileExtension = originalFileName.contains('.')
          ? originalFileName.split('.').last.toLowerCase()
          : 'txt';
      final String nameWithoutExt =
          originalFileName.replaceAll(RegExp(r'\.[^.]+$'), '');
      final String baseName = 'anonymized_$nameWithoutExt';
      final String filename = '$baseName.$fileExtension';

      if (kIsWeb) {
        final MimeType mimeType = getMimeTypeEnum(fileExtension);
        await FileSaver.instance.saveFile(
          name: baseName,
          bytes: bytes,
          ext: fileExtension,
          mimeType: mimeType,
        );
      } else {
        final String? path = await FilePicker.platform.saveFile(
          dialogTitle: 'Save Anonymized Document',
          fileName: filename,
          type: FileType.custom,
          allowedExtensions: <String>[fileExtension],
        );
        if (path != null) {
          final File file = File(path);
          await file.writeAsBytes(bytes, flush: true);
        }
      }

      if (context.mounted) {
        MessageService.showSuccess(
          context,
          'Anonymized document downloaded: $filename',
        );
      }
    } catch (e) {
      if (context.mounted) {
        MessageService.showError(
          context,
          'Failed to rebuild document from segments: $e',
        );
      }
    }
  }
}
