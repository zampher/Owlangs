import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';

enum TranslationOperation {
  none,
  importing,
  extracting,
  generatingGlossary,
  converting,
  translating,
  retranslating,
}

class TranslationStateFamily {
  // Excluded segment indices (e.g., references) - Flow-level state

  const TranslationStateFamily({
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
  final Map<String, int>?
      tokenUsage; // Token usage statistics: input_tokens, cached_tokens, output_tokens, reasoning_tokens, total_tokens
  final Set<int> excludedSegmentIndices;

  TranslationStateFamily copyWith({
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
      TranslationStateFamily(
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
        tokenUsage: clearTokenUsage ? null : (tokenUsage ?? this.tokenUsage),
        excludedSegmentIndices: clearExcludedSegmentIndices
            ? const <int>{}
            : (excludedSegmentIndices ?? this.excludedSegmentIndices),
      );
}

class TranslationStateFamilyNotifier
    extends StateNotifier<TranslationStateFamily> {
  TranslationStateFamilyNotifier() : super(const TranslationStateFamily());

  void setPickedFile(PlatformFile? file) {
    state = state.copyWith(pickedFile: file);
  }

  void setTranslating(bool v) {
    state = state.copyWith(isTranslating: v);
  }

  void setCurrentOperation(TranslationOperation op) {
    state = state.copyWith(currentOperation: op);
  }

  void setTaskId(String? id) {
    state = state.copyWith(taskId: id);
  }

  void setProgress(int p) {
    state = state.copyWith(progress: p);
  }

  void setStatusText(String t) {
    state = state.copyWith(statusText: t);
  }

  void setDownloads(Map<String, String> d) {
    state = state.copyWith(downloads: d);
  }

  void setDownloading(String fileType, bool downloading) {
    final updated = Map<String, bool>.from(state.downloading);
    updated[fileType] = downloading;
    state = state.copyWith(downloading: updated);
  }

  void setStartTime(DateTime? v) {
    state = state.copyWith(startTime: v);
  }

  void setEndTime(DateTime? v) {
    state = state.copyWith(endTime: v);
  }

  void setTotalDuration(Duration? v) {
    state = state.copyWith(totalDuration: v);
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
    state = const TranslationStateFamily();
  }
}

final StateNotifierProviderFamily<TranslationStateFamilyNotifier,
        TranslationStateFamily, String> translationStateProviderFamily =
    StateNotifierProvider.family<TranslationStateFamilyNotifier,
        TranslationStateFamily, String>((
  ref,
  flowId,
) {
  // Keep provider alive to avoid reloading when switching flows
  ref.keepAlive();
  return TranslationStateFamilyNotifier();
});
