import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'translation_state_provider_family.dart' show TranslationOperation;

/// Translation screen state (standalone `/translation` route without [flowId]).
/// Fields mirror [TranslationStateFamily] where the translation UI reads them.
class TranslationState {
  const TranslationState({
    this.pickedFile,
    this.isTranslating = false,
    this.currentOperation = TranslationOperation.none,
    this.taskId,
    this.progress = 0,
    this.statusText = '',
    this.downloads = const <String, String>{},
    this.downloading = const <String, bool>{},
    this.startTime,
    this.endTime,
    this.totalDuration,
    this.successCount,
    this.failCount,
    this.totalSegments,
    this.tokenUsage,
    this.excludedSegmentIndices = const <int>{},
  });
  final PlatformFile? pickedFile;
  final bool isTranslating;
  final TranslationOperation currentOperation;
  final String? taskId;
  final int progress;
  final String statusText;
  final Map<String, String> downloads;
  final Map<String, bool> downloading;
  final DateTime? startTime;
  final DateTime? endTime;
  final Duration? totalDuration;
  final int? successCount;
  final int? failCount;
  final int? totalSegments;
  final Map<String, int>? tokenUsage;
  final Set<int> excludedSegmentIndices;

  TranslationState copyWith({
    PlatformFile? pickedFile,
    bool? isTranslating,
    TranslationOperation? currentOperation,
    String? taskId,
    int? progress,
    String? statusText,
    Map<String, String>? downloads,
    Map<String, bool>? downloading,
    DateTime? startTime,
    DateTime? endTime,
    Duration? totalDuration,
    int? successCount,
    int? failCount,
    int? totalSegments,
    Map<String, int>? tokenUsage,
    Set<int>? excludedSegmentIndices,
    bool clearSuccessCount = false,
    bool clearFailCount = false,
    bool clearTotalSegments = false,
    bool clearTokenUsage = false,
    bool clearExcludedSegmentIndices = false,
  }) =>
      TranslationState(
        pickedFile: pickedFile ?? this.pickedFile,
        isTranslating: isTranslating ?? this.isTranslating,
        currentOperation: currentOperation ?? this.currentOperation,
        taskId: taskId ?? this.taskId,
        progress: progress ?? this.progress,
        statusText: statusText ?? this.statusText,
        downloads: downloads ?? this.downloads,
        downloading: downloading ?? this.downloading,
        startTime: startTime ?? this.startTime,
        endTime: endTime ?? this.endTime,
        totalDuration: totalDuration ?? this.totalDuration,
        successCount:
            clearSuccessCount ? null : (successCount ?? this.successCount),
        failCount: clearFailCount ? null : (failCount ?? this.failCount),
        totalSegments:
            clearTotalSegments ? null : (totalSegments ?? this.totalSegments),
        tokenUsage:
            clearTokenUsage ? null : (tokenUsage ?? this.tokenUsage),
        excludedSegmentIndices: clearExcludedSegmentIndices
            ? const <int>{}
            : (excludedSegmentIndices ?? this.excludedSegmentIndices),
      );
}

/// Translation state provider
final StateNotifierProvider<TranslationStateNotifier, TranslationState>
    translationStateProvider =
    StateNotifierProvider<TranslationStateNotifier, TranslationState>(
  (
    StateNotifierProviderRef<TranslationStateNotifier, TranslationState> ref,
  ) =>
      TranslationStateNotifier(),
);

class TranslationStateNotifier extends StateNotifier<TranslationState> {
  TranslationStateNotifier() : super(const TranslationState());

  void setPickedFile(PlatformFile? file) {
    state = state.copyWith(pickedFile: file);
  }

  void setTranslating(bool isTranslating) {
    state = state.copyWith(isTranslating: isTranslating);
  }

  void setCurrentOperation(TranslationOperation op) {
    state = state.copyWith(currentOperation: op);
  }

  void setTaskId(String? taskId) {
    state = state.copyWith(taskId: taskId);
  }

  void setProgress(int progress) {
    state = state.copyWith(progress: progress);
  }

  void setStatusText(String statusText) {
    state = state.copyWith(statusText: statusText);
  }

  void setDownloads(Map<String, String> downloads) {
    state = state.copyWith(downloads: downloads);
  }

  void setDownloading(String fileType, bool downloading) {
    final Map<String, bool> updated = Map<String, bool>.from(state.downloading);
    updated[fileType] = downloading;
    state = state.copyWith(downloading: updated);
  }

  void setStartTime(DateTime? startTime) {
    state = state.copyWith(startTime: startTime);
  }

  void setEndTime(DateTime? endTime) {
    state = state.copyWith(endTime: endTime);
  }

  void setTotalDuration(Duration? totalDuration) {
    state = state.copyWith(totalDuration: totalDuration);
  }

  void setTranslationStats({
    int? successCount,
    int? failCount,
    int? totalSegments,
    Map<String, int>? tokenUsage,
  }) {
    state = state.copyWith(
      successCount: successCount,
      failCount: failCount,
      totalSegments: totalSegments,
      tokenUsage: tokenUsage,
    );
  }

  void setExcludedSegmentIndices(Set<int> indices) {
    state = state.copyWith(excludedSegmentIndices: indices);
  }

  void addExcludedSegmentIndices(Set<int> indices) {
    state = state.copyWith(
      excludedSegmentIndices: <int>{
        ...state.excludedSegmentIndices,
        ...indices,
      },
    );
  }

  void resetTranslation() {
    state = const TranslationState();
  }

  void updateTranslationStatus({
    String? statusText,
    int? progress,
    DateTime? endTime,
    Map<String, String>? downloads,
  }) {
    Duration? totalDuration;
    if (endTime != null && state.startTime != null) {
      totalDuration = endTime.difference(state.startTime!);
    }
    state = state.copyWith(
      statusText: statusText,
      progress: progress,
      endTime: endTime,
      totalDuration: totalDuration,
      downloads: downloads,
    );
  }
}
