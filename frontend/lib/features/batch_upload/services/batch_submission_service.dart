// SPDX-FileCopyrightText: 2026 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';

import 'dart:io' if (dart.library.html) '../../../shared/utils/io_stub.dart' as io;

import '../../../shared/services/translation_service.dart';
import '../../../shared/services/file_format_service.dart';
import '../models/discovered_file.dart';

/// Result of a batch submission.
class BatchSubmissionResult {
  final List<String> successfulTaskIds;
  final List<String> failedFileNames;
  final List<String> errorMessages;
  final int totalSubmitted;
  final int totalRequested;

  const BatchSubmissionResult({
    required this.successfulTaskIds,
    required this.failedFileNames,
    required this.errorMessages,
    required this.totalSubmitted,
    required this.totalRequested,
  });
}

/// Progress event emitted during batch submission.
class BatchSubmissionProgress {
  final int completed;
  final int total;
  final String currentFileName;
  final bool isSuccess;
  final String? errorMessage;

  const BatchSubmissionProgress({
    required this.completed,
    required this.total,
    required this.currentFileName,
    required this.isSuccess,
    this.errorMessage,
  });

  double get fraction => total > 0 ? completed / total : 0.0;
}

/// Orchestrates sequential submission of multiple discovered files.
///
/// Each file is submitted to the existing ``POST /service/translate`` endpoint
/// with ``execution_mode: 'queued'`` so all files enter the backend FIFO pool.
///
/// Translation parameters (target language, model, prompt) come from the
/// supplied ``basePayload`` — typically the user's current global settings.
class BatchSubmissionService {
  BatchSubmissionService();

  final TranslationService _translationService = TranslationService();

  StreamController<BatchSubmissionProgress>? _controller;
  bool _cancelled = false;

  /// Whether the user has requested cancellation.
  bool get isCancelled => _cancelled;

  /// Cancel any ongoing batch submission.
  void cancel() {
    _cancelled = true;
  }

  /// Submit all [files] sequentially and report progress via the returned
  /// stream.  When the stream closes, call [result] to obtain the final tally.
  Stream<BatchSubmissionProgress> submitBatch({
    required List<DiscoveredFile> files,
    required Map<String, dynamic> basePayload,
    required String batchId,
  }) {
    _cancelled = false;
    _controller = StreamController<BatchSubmissionProgress>.broadcast();
    final successfulTaskIds = <String>[];
    final failedFileNames = <String>[];
    final errorMessages = <String>[];
    int completed = 0;
    final total = files.length;

    _processNext(
      files: files,
      index: 0,
      basePayload: basePayload,
      batchId: batchId,
      completed: completed,
      total: total,
      successfulTaskIds: successfulTaskIds,
      failedFileNames: failedFileNames,
      errorMessages: errorMessages,
    );

    return _controller!.stream;
  }

  Future<void> _processNext({
    required List<DiscoveredFile> files,
    required int index,
    required Map<String, dynamic> basePayload,
    required String batchId,
    required int completed,
    required int total,
    required List<String> successfulTaskIds,
    required List<String> failedFileNames,
    required List<String> errorMessages,
  }) async {
    if (_cancelled || index >= files.length) {
      // Collect result from accumulated lists.
      _controller?.close();
      return;
    }

    final file = files[index];

    // Build per-file payload with auto-detected workflow type.
    final workflowType = FileFormatService.inferWorkflowType(file.extension);
    final payload = Map<String, dynamic>.from(basePayload);
    payload['workflow_type'] = workflowType;

    try {
      // Read bytes lazily from disk if needed.
      List<int> bytes;
      if (file.fileBytes != null && file.fileBytes!.isNotEmpty) {
        bytes = file.fileBytes!;
      } else if (file.filePath != null && file.filePath!.isNotEmpty) {
        bytes = await io.File(file.filePath!).readAsBytes();
        // Cache for potential retries.
        file.fileBytes = bytes;
      } else {
        throw Exception(
          'No file data available for ${file.fileName} '
          '(missing bytes and path)',
        );
      }

      final response = await _translationService.submitTask(
        fileBytes: bytes,
        fileName: file.fileName,
        payload: payload,
        executionMode: 'queued',
        relativePath: (file.relativePath != null &&
                file.relativePath!.trim().isNotEmpty)
            ? file.relativePath
            : null,
        batchId: batchId,
      );

      final taskId = response['task_id'] as String? ?? 'unknown';
      successfulTaskIds.add(taskId);

      completed++;
      _controller?.add(BatchSubmissionProgress(
        completed: completed,
        total: total,
        currentFileName: file.fileName,
        isSuccess: true,
      ));
    } catch (e) {
      failedFileNames.add(file.fileName);
      errorMessages.add('${file.fileName}: $e');
      completed++;
      _controller?.add(BatchSubmissionProgress(
        completed: completed,
        total: total,
        currentFileName: file.fileName,
        isSuccess: false,
        errorMessage: e.toString(),
      ));
    }

    // Continue to next file.
    _processNext(
      files: files,
      index: index + 1,
      basePayload: basePayload,
      batchId: batchId,
      completed: completed,
      total: total,
      successfulTaskIds: successfulTaskIds,
      failedFileNames: failedFileNames,
      errorMessages: errorMessages,
    );
  }
}
