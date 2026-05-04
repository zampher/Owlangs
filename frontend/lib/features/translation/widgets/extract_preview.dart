import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/foundation.dart' show kDebugMode, kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/utils/dialog_helper.dart';
import '../../../shared/utils/pagination.dart';
import '../../../shared/utils/paginated_scroll_manager.dart';
import '../../../shared/widgets/pagination_bar.dart';
import '../../../shared/widgets/page_size_selector.dart';
import '../../../shared/widgets/paginated_sliver_list.dart';
import '../widgets/common/segment_numbered_item.dart';
import '../widgets/common/exclusion_panel_widget.dart';
import '../widgets/common/exclusion_panel_button.dart';
import '../models/exclusion_reason.dart';
import '../utils/segment_height_cache.dart';
import '../utils/segment_height_calculator.dart';
import '../../tasks/providers/flow_provider.dart';
import '../../../shared/services/anonymize_service.dart';
import '../../tasks/models/flow.dart';
import 'dart:async';
import '../../anonymize/providers/anonymize_completion_provider.dart';
import '../services/tab_background_update_service.dart';
import '../providers/translation_state_provider.dart';
import '../providers/translation_state_provider_family.dart';
import '../providers/exclusion_update_provider.dart';
import '../providers/excluded_segments_provider.dart';
import '../providers/extract_refresh_provider.dart';
import '../providers/chunk_tokens_provider.dart';
import '../../../shared/config/pagination_config.dart';
import '../../../shared/providers/settings_provider.dart';
import '../../settings/screens/settings_screen.dart';
import '../widgets/translation_quick_settings.dart';
import '../providers/translation_refresh_provider.dart';
import 'extract_preview/extract_preview_state.dart';
import 'extract_preview/extract_preview_data_loader.dart';
import 'extract_preview/extract_preview_exclusion_handler.dart';
import 'extract_preview/extract_preview_ui_builder.dart';
import 'extract_preview/extract_preview_pagination.dart';
import 'extract_preview/extract_preview_progress.dart';
import 'extract_preview/extract_preview_language_match.dart';
import '../../../../shared/widgets/segment_search_box.dart';

class ExtractPreview extends ConsumerStatefulWidget {
  // If true, this tab is waiting for a real taskId

  const ExtractPreview({
    required this.taskId,
    super.key,
    this.flowId,
    this.onAnonymizeComplete,
    this.isPending = false,
  });
  final String taskId;
  final String? flowId;
  final VoidCallback? onAnonymizeComplete;
  final bool isPending;

  @override
  ConsumerState<ExtractPreview> createState() => _ExtractPreviewState();
}

class _ExtractPreviewState extends ConsumerState<ExtractPreview>
    with
        AutomaticKeepAliveClientMixin,
        ExtractPreviewStateMixin,
        ExtractPreviewDataLoaderMixin,
        ExtractPreviewExclusionHandlerMixin,
        ExtractPreviewUIBuilderMixin,
        ExtractPreviewPaginationMixin,
        ExtractPreviewProgressMixin,
        ExtractPreviewLanguageMatchMixin {
  void _log(String message, {LogLevel level = LogLevel.debug}) {
    String formatted = message;
    if (formatted.startsWith('[ExtractPreview]')) {
      formatted = formatted.replaceFirst('[ExtractPreview]', '').trimLeft();
    }
    AppLogger.log('ExtractPreview', formatted, level: level);
  }

  // Note: All state variables are now defined in ExtractPreviewStateMixin
  // They are accessed without the underscore prefix (e.g., allSegments instead of allSegments)

  @override
  bool get wantKeepAlive => true; // Keep widget alive even when not visible

  @override
  void initState() {
    super.initState();

    // Initialize pagination controller for segments (left panel)
    // Use allSegments list directly (similar to chunks pagination)
    // This ensures segments reflect excluded state from getLayoutExtract API
    paginationController = PagedListController<String>(
      initialPageSize:
          defaultSegmentPreviewLimit, // Use config value instead of default 200
      fetcher: (int offset, int limit) async {
        // For rebuild mode: use filtered segment indices
        // For page mode: use all segments (filtering happens in itemBuilder)
        if (filterMode == 'rebuild' && selectedExclusionFilters.isNotEmpty) {
          // Rebuild mode: use filtered indices
          filteredSegmentIndices = _getFilteredSegmentIndices();
          final filteredIndices = filteredSegmentIndices!;
          final int start = offset;
          final int end = (offset + limit).clamp(0, filteredIndices.length);
          final List<String> filteredItems = filteredIndices
              .sublist(start, end)
              .map((index) => allSegments[index])
              .toList();
          return <String, dynamic>{
            'items': filteredItems,
            'total': filteredIndices.length,
            'offset': offset,
            'limit': limit,
          };
        } else {
          // Page mode or no filters: use all segments
          final int start = offset;
          final int end = (offset + limit).clamp(0, allSegments.length);
          return <String, dynamic>{
            'items': allSegments.sublist(start, end),
            'total': allSegments.length,
            'offset': offset,
            'limit': limit,
          };
        }
      },
      // itemConverter not needed - items are already String type
    );

    // Initialize pagination controller for chunks (right panel)
    chunksPaginationController = PagedListController<String>(
      fetcher: (int offset, int limit) async {
        // For chunks, we'll use a simple list-based pagination
        // since chunks are already loaded in allChunks
        final int start = offset;
        final int end = (offset + limit).clamp(0, allChunks.length);
        return <String, dynamic>{
          'items': allChunks.sublist(start, end),
          'total': allChunks.length,
          'offset': offset,
          'limit': limit,
        };
      },
      // itemConverter not needed - items are already String type
    );

    // Initialize height cache and scroll manager
    segmentsHeightCache = SegmentHeightCache(
      listPadding: 0, // ListView.separated doesn't have padding by default
    );

    segmentsScrollManager = PaginatedScrollManager(
      scrollController: segmentsScrollController,
      paginationController: paginationController,
      heightCache: segmentsHeightCache!,
      itemKeys: segmentKeys,
      totalItems: allSegments.length,
    );

    // Listen to pagination changes
    paginationController.addListener(_onPaginationChanged);

    // If this is a pending tab, wait for real taskId before loading data
    if (widget.isPending) {
      // For pending tabs, wait for taskId to be available from translation state
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          waitForRealTaskId();
        }
      });
    } else {
      // Try to restore segments from FlowContext cache first
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && widget.flowId != null) {
          tryRestoreSegmentsFromCache();
        }
      });

      // Load initial data immediately for real taskId
      _startPreparePolling();
      _loadInitialData();

      // Note: chunk_size change detection is handled in build() method using ref.watch()
      // This ensures chunks are refreshed when chunk_size changes (e.g., after resplit)

      // Check if anonymization is already in progress and restore state
      // Use addPostFrameCallback to ensure ref is available
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          checkAndRestoreAnonymizeProgress();
        }
      });
    }
  }

  // Moved to ExtractPreviewDataLoaderMixin.tryRestoreSegmentsFromCache()
  void _tryRestoreSegmentsFromCache() => tryRestoreSegmentsFromCache();

  // Moved to ExtractPreviewPaginationMixin.onPaginationChanged()
  void _onPaginationChanged() => onPaginationChanged();

  // Moved to ExtractPreviewPaginationMixin.updateSegmentKeys()
  void _updateSegmentKeys() => updateSegmentKeys();

  @override
  void dispose() {
    // Cancel all timers first
    prepareTimer?.cancel();
    prepareTimer = null;
    progressTimer?.cancel();
    progressTimer = null;

    // Unregister from background service
    if (widget.flowId != null && currentPollingWorkflowId != null) {
      try {
        final TabBackgroundUpdateService bgService =
            ref.read(tabBackgroundUpdateServiceProvider);
        bgService.unregisterUpdate(
          flowId: widget.flowId!,
          taskId: currentPollingWorkflowId!,
          updateType: 'anonymize',
        );
      } catch (e) {
        // Ignore errors during dispose
        if (kDebugMode) {
          _log(
            '[ExtractPreview] Error unregistering from background service: $e',
          );
        }
      }
    }

    currentPollingWorkflowId = null;

    // Reset progress state to prevent stale updates
    // Translation phase state
    isTranslating = false;
    translationProgress = 0.0;
    translationStatus = '';
    // Anonymization workflow state
    isAnonymizing = false;
    anonymizeProgress = 0.0;
    anonymizeStatus = '';
    progressInFlight = false;

    // Remove listeners and dispose controllers
    paginationController.removeListener(_onPaginationChanged);
    segmentsScrollManager?.dispose();
    paginationController.dispose();
    segmentsScrollController.dispose();
    chunksScrollController.dispose();
    super.dispose();
  }

  // Moved to ExtractPreviewPaginationMixin.highlightSegment()
  void _highlightSegment(int localIndex) => highlightSegment(localIndex);

  // Moved to ExtractPreviewPaginationMixin.precalculateAllHeights()
  void _precalculateAllHeights([double? actualWidth]) =>
      precalculateAllHeights(actualWidth);

  // Moved to ExtractPreviewProgressMixin.handleProgressUpdate()
  void _handleProgressUpdate(
    Map<String, dynamic> progress,
    String workflowId,
  ) =>
      handleProgressUpdate(progress, workflowId);

  // Moved to ExtractPreviewProgressMixin.startAnonymizeProgressPolling()
  void _startAnonymizeProgressPolling(String workflowId) =>
      startAnonymizeProgressPolling(workflowId);

  /// Public method to force refresh chunks (e.g., after resplit)
  /// This can be called from outside to trigger a refresh
  Future<void> refreshChunks() async {
    if (kDebugMode) {
      _log(
        '[ExtractPreview] refreshChunks() called, forcing reload. '
        'taskId=${widget.taskId}, flowId=${widget.flowId}, '
        'current allSegments=${allSegments.length}, allChunks=${allChunks.length}',
      );
    }
    // Reset scroll controllers to prevent ScrollPosition errors
    if (segmentsScrollController.hasClients) {
      segmentsScrollController.jumpTo(0);
    }
    if (chunksScrollController.hasClients) {
      chunksScrollController.jumpTo(0);
    }
    setState(() {
      allSegments = <String>[];
      allChunks = <String>[];
      allSeparators = <String>[];
      initialDataLoaded = false;
    });
    if (kDebugMode) {
      _log(
        '[ExtractPreview] refreshChunks() state cleared. '
        'taskId=${widget.taskId}, will call _loadInitialData(forceReload: true)',
      );
    }
    await _loadInitialData(forceReload: true);
  }

  /// Apply exclude references state to Flow-level state and refresh chunks
  Future<void> _applyExcludeReferencesState(bool exclude) async {
    if (!mounted || referenceSegmentIndices.isEmpty) {
      _log(
        '[ExtractPreview] _applyExcludeReferencesState: Early return - mounted=$mounted, referenceSegmentIndices=${referenceSegmentIndices.length}',
        level: LogLevel.info,
      );
      return;
    }

    _log(
      '[ExtractPreview] _applyExcludeReferencesState START: exclude=$exclude, referenceSegmentIndices=${referenceSegmentIndices.length}, current allSegments=${allSegments.length}, current allChunks=${allChunks.length}',
      level: LogLevel.info,
    );

    try {
      // CRITICAL: Update Flow-level state
      if (widget.flowId != null) {
        final TranslationStateFamilyNotifier translationNotifier =
            ref.read(translationStateProviderFamily(widget.flowId!).notifier);
        final Set<int> currentExcluded = ref
            .read(translationStateProviderFamily(widget.flowId!))
            .excludedSegmentIndices;

        _log(
          '[ExtractPreview] Current Flow-level excludedSegmentIndices: ${currentExcluded.length} indices',
          level: LogLevel.info,
        );

        Set<int> updatedExcluded;
        if (exclude) {
          // Add reference segments to excluded set
          updatedExcluded = <int>{
            ...currentExcluded,
            ...referenceSegmentIndices,
          };
          _log(
            '[ExtractPreview] Adding ${referenceSegmentIndices.length} reference segments to excluded set',
            level: LogLevel.info,
          );
        } else {
          // Remove reference segments from excluded set
          updatedExcluded =
              currentExcluded.difference(referenceSegmentIndices.toSet());
          _log(
            '[ExtractPreview] Removing ${referenceSegmentIndices.length} reference segments from excluded set',
            level: LogLevel.info,
          );
        }

        translationNotifier.setExcludedSegmentIndices(updatedExcluded);

        _log(
          '[ExtractPreview] Updated Flow-level excludedSegmentIndices: ${updatedExcluded.length} indices (exclude=$exclude, references=${referenceSegmentIndices.length})',
          level: LogLevel.info,
        );
      }

      // CRITICAL: Reload chunks with updated exclusion state
      // Get current chunk_size from global settings
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);

      // Get excluded segment indices from Flow-level state
      final List<int> excludedIndices = widget.flowId != null
          ? ref
              .read(translationStateProviderFamily(widget.flowId!))
              .excludedSegmentIndices
              .toList()
          : (exclude ? referenceSegmentIndices : <int>[]);

      // Get target language from Quick Settings for language match detection
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final String? targetLang = qs.toLang.isNotEmpty ? qs.toLang : null;

      // Check if this is a PDF file - only PDF files support layout-extract API
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> status = await svc.getStatus(widget.taskId);
      final String originalFilename =
          status['original_filename'] as String? ?? '';
      final bool isPdfFile = originalFilename.toLowerCase().endsWith('.pdf');

      if (isPdfFile) {
        _log(
          '[ExtractPreview] PDF file detected, calling getLayoutExtract API: taskId=${widget.taskId}, excludedIndices=${excludedIndices.length}, targetLang=$targetLang',
          level: LogLevel.info,
        );

        final Map<String, dynamic> updatedLayoutData =
            await svc.getLayoutExtract(
          widget.taskId,
          excludedSegmentIndices: excludedIndices,
          targetLang: targetLang,
        );

        if (updatedLayoutData['ready'] == true) {
          // Parse updated segments and chunks
          var updatedSegments = <String>[];
          var updatedChunks = <String>[];

          try {
            // Update segments (left panel) from updatedLayoutData
            final List<dynamic> segmentsData =
                updatedLayoutData['segments'] as List<dynamic>? ?? <dynamic>[];
            segmentExclusionReasons.clear(); // Clear old exclusion reasons
            updatedSegments = segmentsData.asMap().entries.map((entry) {
              final int index = entry.key;
              final seg = entry.value;
              if (seg is Map) {
                // Extract exclusion_reason if available
                final String? exclusionReason =
                    seg['exclusion_reason'] as String?;
                if (exclusionReason != null) {
                  segmentExclusionReasons[index] = exclusionReason;
                  // Extract exclusion_metadata if available
                  final dynamic exclusionMetadata = seg['exclusion_metadata'];
                  if (exclusionMetadata is Map) {
                    segmentExclusionMetadata[index] =
                        Map<String, dynamic>.from(exclusionMetadata);
                  }
                } else {
                  // Remove if no longer excluded
                  segmentExclusionReasons.remove(index);
                  segmentExclusionMetadata.remove(index);
                }
                return seg['text'] as String? ?? '';
              }
              return seg.toString();
            }).toList();

            _log(
              '[ExtractPreview] Parsed segments: ${updatedSegments.length} segments (exclude=$exclude), before update: ${allSegments.length}',
              level: LogLevel.info,
            );

            // First try chunks_text (simpler format, list of strings)
            final chunksTextRaw = updatedLayoutData['chunks_text'];
            if (chunksTextRaw != null && chunksTextRaw is List) {
              updatedChunks =
                  chunksTextRaw.map((chunk) => chunk.toString()).toList();
              _log(
                '[ExtractPreview] Using chunks_text: ${updatedChunks.length} chunks, before update: ${allChunks.length}',
                level: LogLevel.info,
              );
            } else {
              // Fallback to chunks (list of dicts)
              final chunksRaw = updatedLayoutData['chunks'];
              if (chunksRaw != null && chunksRaw is List) {
                updatedChunks = chunksRaw.map((chunk) {
                  if (chunk is Map) {
                    return chunk['text'] as String? ?? '';
                  }
                  return chunk.toString();
                }).toList();
                _log(
                  '[ExtractPreview] Using chunks: ${updatedChunks.length} chunks, before update: ${allChunks.length}',
                  level: LogLevel.info,
                );
              }
            }

            if (updatedChunks.isEmpty) {
              _log(
                '[ExtractPreview] WARNING: No chunks found in updatedLayoutData. Keeping existing chunks.',
                level: LogLevel.warn,
              );
              return;
            }

            // Update total estimated input tokens
            final rawTokensValue =
                updatedLayoutData['total_estimated_input_tokens'];
            final int? updatedTotalTokens = rawTokensValue is int
                ? rawTokensValue
                : (rawTokensValue is num ? rawTokensValue.toInt() : null);

            if (mounted) {
              _log(
                '[ExtractPreview] Calling setState to update segments and chunks: ${updatedSegments.length} segments, ${updatedChunks.length} chunks (exclude=$exclude)',
                level: LogLevel.info,
              );

              // CRITICAL: Update excludedSegmentsProviderFamily BEFORE setState to ensure UI updates correctly
              // This ensures that segments show the correct excluded status when checkbox is toggled
              final String providerKey = widget.flowId ?? widget.taskId;
              final ExcludedSegmentsNotifier excludedNotifier = ref
                  .read(excludedSegmentsProviderFamily(providerKey).notifier);

              // Build excluded set from updated segments data
              final Set<int> updatedExcludedSet = <int>{};
              for (var i = 0; i < segmentsData.length; i++) {
                final seg = segmentsData[i];
                if (seg is Map) {
                  final bool isExcluded = seg['is_excluded'] as bool? ?? false;
                  if (isExcluded) {
                    updatedExcludedSet.add(i);
                  }
                }
              }

              _log(
                '[ExtractPreview] Updating excludedSegmentsProviderFamily: ${updatedExcludedSet.length} excluded segments (exclude=$exclude)',
                level: LogLevel.info,
              );
              excludedNotifier.setExcluded(updatedExcludedSet);

              // CRITICAL: Update allChunks BEFORE setState to ensure fetcher uses latest data
              // Store old chunks count to detect changes
              final int oldChunksCount = allChunks.length;
              final int newChunksCount = updatedChunks.length;
              final bool chunksCountChanged = oldChunksCount != newChunksCount;

              _log(
                '[ExtractPreview] Chunks count changed: $oldChunksCount -> $newChunksCount (exclude=$exclude)',
                level: LogLevel.info,
              );

              // Log chunks content preview for debugging
              if (updatedChunks.isNotEmpty) {
                final List<String> chunksPreview =
                    updatedChunks.take(3).map((String chunk) {
                  final String preview = chunk.length > 100
                      ? '${chunk.substring(0, 100)}...'
                      : chunk;
                  return preview;
                }).toList();
                _log(
                  '[ExtractPreview] Updated chunks preview (first 3): $chunksPreview',
                );
              }

              setState(() {
                allSegments = updatedSegments;
                allChunks = updatedChunks;
                if (updatedTotalTokens != null) {
                  totalEstimatedInputTokens = updatedTotalTokens;
                }
              });

              _log(
                '[ExtractPreview] setState completed: allSegments=${allSegments.length}, allChunks=${allChunks.length}',
                level: LogLevel.info,
              );

              // Pre-calculate all segment heights after text content changes
              // This ensures stable maxScrollExtent and prevents scrollbar jitter
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted && segmentsScrollManager != null) {
                  _precalculateAllHeights();
                }
              });

              // Verify chunks were correctly updated
              if (allChunks.length != newChunksCount) {
                _log(
                  '[ExtractPreview] ERROR: allChunks length mismatch after setState: expected $newChunksCount, got ${allChunks.length}',
                  level: LogLevel.error,
                );
              } else {
                _log(
                  '[ExtractPreview] Verified: allChunks correctly updated to ${allChunks.length} chunks',
                  level: LogLevel.info,
                );
              }

              // Update token provider
              if (updatedTotalTokens != null && updatedTotalTokens > 0) {
                _setTotalTokens(updatedTotalTokens, 'layout-extract-checkbox');
              }

              // CRITICAL: Refresh both segments and chunks pagination controllers
              // IMPORTANT: Always reset chunks pagination to first page when chunks count changes
              // This ensures fetcher uses the latest allChunks data
              _log(
                '[ExtractPreview] Scheduling pagination refresh: segments controller total=${paginationController.total}, chunks count changed=$chunksCountChanged',
                level: LogLevel.info,
              );

              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) {
                  _log(
                    '[ExtractPreview] PostFrameCallback: Refreshing segments pagination controller (loadFirstPage)',
                    level: LogLevel.info,
                  );
                  // Refresh segments pagination to show updated is_excluded status
                  paginationController.loadFirstPage();

                  // CRITICAL: Always reset chunks pagination to first page when chunks are updated
                  // This ensures fetcher uses the latest allChunks data and prevents index out of range errors
                  Future.delayed(const Duration(milliseconds: 150), () async {
                    if (!mounted) {
                      _log(
                        '[ExtractPreview] Delayed callback: Widget not mounted, skipping chunks refresh',
                        level: LogLevel.warn,
                      );
                      return;
                    }

                    // Verify allChunks has been updated
                    if (allChunks.length != newChunksCount) {
                      _log(
                        '[ExtractPreview] WARNING: allChunks length mismatch: expected $newChunksCount, got ${allChunks.length}',
                        level: LogLevel.warn,
                      );
                    }

                    _log(
                      '[ExtractPreview] Delayed callback: Refreshing chunks pagination controller (loadFirstPage), allChunks=${allChunks.length}',
                      level: LogLevel.info,
                    );

                    // Log chunks content preview before refresh
                    if (allChunks.isNotEmpty) {
                      final List<String> chunksPreviewBefore =
                          allChunks.take(3).map((String chunk) {
                        final String preview = chunk.length > 100
                            ? '${chunk.substring(0, 100)}...'
                            : chunk;
                        return preview;
                      }).toList();
                      _log(
                        '[ExtractPreview] Chunks content before refresh (first 3): $chunksPreviewBefore',
                      );
                    }

                    // Always reset to first page to ensure fetcher uses latest allChunks
                    await chunksPaginationController.loadFirstPage();

                    // Log chunks content preview after refresh
                    if (chunksPaginationController.items.isNotEmpty) {
                      final List<String> chunksPreviewAfter =
                          chunksPaginationController.items
                              .take(3)
                              .map((String chunk) {
                        final String preview = chunk.length > 100
                            ? '${chunk.substring(0, 100)}...'
                            : chunk;
                        return preview;
                      }).toList();
                      _log(
                        '[ExtractPreview] Chunks content after refresh (first 3): $chunksPreviewAfter',
                      );
                    }

                    _log(
                      '[ExtractPreview] Chunks pagination controller refreshed: ${allChunks.length} chunks available, pagination items=${chunksPaginationController.items.length}, total=${chunksPaginationController.total}',
                      level: LogLevel.info,
                    );
                  });
                } else {
                  _log(
                    '[ExtractPreview] PostFrameCallback: Widget not mounted, skipping pagination refresh',
                    level: LogLevel.warn,
                  );
                }
              });

              _log(
                '[ExtractPreview] _applyExcludeReferencesState COMPLETED: exclude=$exclude',
                level: LogLevel.info,
              );
            } else {
              _log(
                '[ExtractPreview] Widget not mounted, skipping setState and pagination refresh',
                level: LogLevel.warn,
              );
            }
          } catch (e) {
            _log(
              '[ExtractPreview] ERROR parsing segments/chunks: $e. Keeping existing data.',
              level: LogLevel.error,
            );
          }
        } else {
          _log(
            '[ExtractPreview] WARNING: updatedLayoutData is not ready. ready=${updatedLayoutData['ready']}',
            level: LogLevel.warn,
          );
        }
      } else {
        _log(
          '[ExtractPreview] Non-PDF file ($originalFilename), skipping layout-extract API call. Chunks will be managed locally.',
          level: LogLevel.info,
        );
      }
    } catch (e, stackTrace) {
      _log(
        '[ExtractPreview] Error applying exclude references state: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to update references exclusion: $e',
        );
      }
    }
  }

  /// Apply exclude headers state (similar to _applyExcludeReferencesState)
  Future<void> _applyExcludeHeadersState(bool exclude) async {
    if (!mounted || headerSegmentIndices.isEmpty) {
      return;
    }

    try {
      // Update Flow-level state
      if (widget.flowId != null) {
        final TranslationStateFamilyNotifier translationNotifier =
            ref.read(translationStateProviderFamily(widget.flowId!).notifier);
        final Set<int> currentExcluded = ref
            .read(translationStateProviderFamily(widget.flowId!))
            .excludedSegmentIndices;

        Set<int> updatedExcluded;
        if (exclude) {
          updatedExcluded = <int>{
            ...currentExcluded,
            ...headerSegmentIndices,
          };
        } else {
          updatedExcluded =
              currentExcluded.difference(headerSegmentIndices.toSet());
        }

        translationNotifier.setExcludedSegmentIndices(updatedExcluded);
      }

      // Reload chunks with updated exclusion state
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);

      // CRITICAL: Pass current excluded minus header indices so backend keeps other exclusions (e.g. language_match).
      // When flowId is null we must not pass [] or backend re-detects and re-excludes all, flipping Language Match checkbox.
      final List<int> excludedIndices;
      if (widget.flowId != null) {
        excludedIndices = ref
            .read(translationStateProviderFamily(widget.flowId!))
            .excludedSegmentIndices
            .toList();
      } else {
        final String providerKey = widget.flowId ?? widget.taskId;
        final Set<int> currentExcluded =
            ref.read(excludedSegmentsProviderFamily(providerKey));
        final Set<int> afterToggle = exclude
            ? (currentExcluded.toSet()..addAll(headerSegmentIndices))
            : currentExcluded.difference(headerSegmentIndices.toSet());
        excludedIndices = afterToggle.toList();
      }

      // Get target language from Quick Settings for language match detection
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final String? targetLang = qs.toLang.isNotEmpty ? qs.toLang : null;

      // Check if this is a PDF file - only PDF files support layout-extract API
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> status = await svc.getStatus(widget.taskId);
      final String originalFilename =
          status['original_filename'] as String? ?? '';
      final bool isPdfFile = originalFilename.toLowerCase().endsWith('.pdf');

      if (isPdfFile) {
        _log(
          '[ExtractPreview] PDF file detected, calling getLayoutExtract API for headers: taskId=${widget.taskId}, excludedIndices=${excludedIndices.length}, targetLang=$targetLang',
          level: LogLevel.info,
        );

        final Map<String, dynamic> updatedLayoutData =
            await svc.getLayoutExtract(
          widget.taskId,
          excludedSegmentIndices: excludedIndices,
          targetLang: targetLang,
        );

        if (updatedLayoutData['ready'] == true) {
          var updatedSegments = <String>[];
          var updatedChunks = <String>[];

          try {
            final List<dynamic> segmentsData =
                updatedLayoutData['segments'] as List<dynamic>? ?? <dynamic>[];
            // Extract exclusion_reason for all segments
            segmentsData.asMap().entries.forEach((entry) {
              final int index = entry.key;
              final seg = entry.value;
              if (seg is Map) {
                final String? exclusionReason =
                    seg['exclusion_reason'] as String?;
                if (exclusionReason != null) {
                  segmentExclusionReasons[index] = exclusionReason;
                } else {
                  // Backfill from blockType for formula segments
                  final String? blockType = seg['block_type'] as String?;
                  if (blockType == 'interline_equation') {
                    segmentExclusionReasons.putIfAbsent(
                      index,
                      () => ExclusionReason.formula.value,
                    );
                  } else {
                    // Remove if no longer excluded
                    segmentExclusionReasons.remove(index);
                  }
                }
              }
            });
            updatedSegments = segmentsData.map((seg) {
              if (seg is Map) {
                return seg['text'] as String? ?? '';
              }
              return seg.toString();
            }).toList();

            final chunksTextRaw = updatedLayoutData['chunks_text'];
            if (chunksTextRaw != null && chunksTextRaw is List) {
              updatedChunks =
                  chunksTextRaw.map((chunk) => chunk.toString()).toList();
            } else {
              final chunksRaw = updatedLayoutData['chunks'];
              if (chunksRaw != null && chunksRaw is List) {
                updatedChunks = chunksRaw.map((chunk) {
                  if (chunk is Map) {
                    return chunk['text'] as String? ?? '';
                  }
                  return chunk.toString();
                }).toList();
              }
            }

            if (updatedChunks.isEmpty) {
              return;
            }

            final rawTokensValue =
                updatedLayoutData['total_estimated_input_tokens'];
            final int? updatedTotalTokens = rawTokensValue is int
                ? rawTokensValue
                : (rawTokensValue is num ? rawTokensValue.toInt() : null);

            if (mounted) {
              final String providerKey = widget.flowId ?? widget.taskId;
              final ExcludedSegmentsNotifier excludedNotifier = ref
                  .read(excludedSegmentsProviderFamily(providerKey).notifier);

              final Set<int> updatedExcludedSet = <int>{};
              for (var i = 0; i < segmentsData.length; i++) {
                final seg = segmentsData[i];
                if (seg is Map) {
                  final bool isExcluded = seg['is_excluded'] as bool? ?? false;
                  if (isExcluded) {
                    updatedExcludedSet.add(i);
                  }
                }
              }

              excludedNotifier.setExcluded(updatedExcludedSet);

              setState(() {
                allSegments = updatedSegments;
                allChunks = updatedChunks;
                if (updatedTotalTokens != null) {
                  totalEstimatedInputTokens = updatedTotalTokens;
                }
              });

              if (updatedTotalTokens != null && updatedTotalTokens > 0) {
                _setTotalTokens(updatedTotalTokens, 'layout-extract-headers');
              }

              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) {
                  paginationController.loadFirstPage();
                  Future.delayed(const Duration(milliseconds: 150), () async {
                    if (mounted) {
                      await chunksPaginationController.loadFirstPage();
                    }
                  });
                }
              });
            }
          } catch (e) {
            _log(
              '[ExtractPreview] ERROR parsing segments/chunks for headers: $e',
              level: LogLevel.error,
            );
          }
        }
      } else {
        _log(
          '[ExtractPreview] Non-PDF file ($originalFilename), skipping layout-extract API call for headers. Chunks will be managed locally.',
          level: LogLevel.info,
        );
      }
    } catch (e, stackTrace) {
      _log(
        '[ExtractPreview] Error applying exclude headers state: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to update headers exclusion: $e',
        );
      }
    }
  }

  /// Apply exclude footers state (similar to _applyExcludeReferencesState)
  Future<void> _applyExcludeFootersState(bool exclude) async {
    if (!mounted || footerSegmentIndices.isEmpty) {
      return;
    }

    try {
      // Update Flow-level state
      if (widget.flowId != null) {
        final TranslationStateFamilyNotifier translationNotifier =
            ref.read(translationStateProviderFamily(widget.flowId!).notifier);
        final Set<int> currentExcluded = ref
            .read(translationStateProviderFamily(widget.flowId!))
            .excludedSegmentIndices;

        Set<int> updatedExcluded;
        if (exclude) {
          updatedExcluded = <int>{
            ...currentExcluded,
            ...footerSegmentIndices,
          };
        } else {
          updatedExcluded =
              currentExcluded.difference(footerSegmentIndices.toSet());
        }

        translationNotifier.setExcludedSegmentIndices(updatedExcluded);
      }

      // Reload chunks with updated exclusion state
      final GlobalSettings globalSettings = ref.read(globalSettingsProvider);

      // CRITICAL: Pass current excluded minus footer indices so backend keeps other exclusions (e.g. language_match).
      // When flowId is null we must not pass [] or backend re-detects and re-excludes all, flipping Language Match checkbox.
      final List<int> excludedIndices;
      if (widget.flowId != null) {
        excludedIndices = ref
            .read(translationStateProviderFamily(widget.flowId!))
            .excludedSegmentIndices
            .toList();
      } else {
        final String providerKey = widget.flowId ?? widget.taskId;
        final Set<int> currentExcluded =
            ref.read(excludedSegmentsProviderFamily(providerKey));
        final Set<int> afterToggle = exclude
            ? (currentExcluded.toSet()..addAll(footerSegmentIndices))
            : currentExcluded.difference(footerSegmentIndices.toSet());
        excludedIndices = afterToggle.toList();
      }

      // Get target language from Quick Settings for language match detection
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final String? targetLang = qs.toLang.isNotEmpty ? qs.toLang : null;

      // Check if this is a PDF file - only PDF files support layout-extract API
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> status = await svc.getStatus(widget.taskId);
      final String originalFilename =
          status['original_filename'] as String? ?? '';
      final bool isPdfFile = originalFilename.toLowerCase().endsWith('.pdf');

      if (isPdfFile) {
        _log(
          '[ExtractPreview] PDF file detected, calling getLayoutExtract API for footers: taskId=${widget.taskId}, excludedIndices=${excludedIndices.length}, targetLang=$targetLang',
          level: LogLevel.info,
        );

        final Map<String, dynamic> updatedLayoutData =
            await svc.getLayoutExtract(
          widget.taskId,
          excludedSegmentIndices: excludedIndices,
          targetLang: targetLang,
        );

        if (updatedLayoutData['ready'] == true) {
          var updatedSegments = <String>[];
          var updatedChunks = <String>[];

          try {
            final List<dynamic> segmentsData =
                updatedLayoutData['segments'] as List<dynamic>? ?? <dynamic>[];
            // Extract exclusion_reason for all segments
            segmentsData.asMap().entries.forEach((entry) {
              final int index = entry.key;
              final seg = entry.value;
              if (seg is Map) {
                final String? exclusionReason =
                    seg['exclusion_reason'] as String?;
                if (exclusionReason != null) {
                  segmentExclusionReasons[index] = exclusionReason;
                } else {
                  // Backfill from blockType for formula segments
                  final String? blockType = seg['block_type'] as String?;
                  if (blockType == 'interline_equation') {
                    segmentExclusionReasons.putIfAbsent(
                      index,
                      () => ExclusionReason.formula.value,
                    );
                  } else {
                    // Remove if no longer excluded
                    segmentExclusionReasons.remove(index);
                  }
                }
              }
            });
            updatedSegments = segmentsData.map((seg) {
              if (seg is Map) {
                return seg['text'] as String? ?? '';
              }
              return seg.toString();
            }).toList();

            final chunksTextRaw = updatedLayoutData['chunks_text'];
            if (chunksTextRaw != null && chunksTextRaw is List) {
              updatedChunks =
                  chunksTextRaw.map((chunk) => chunk.toString()).toList();
            } else {
              final chunksRaw = updatedLayoutData['chunks'];
              if (chunksRaw != null && chunksRaw is List) {
                updatedChunks = chunksRaw.map((chunk) {
                  if (chunk is Map) {
                    return chunk['text'] as String? ?? '';
                  }
                  return chunk.toString();
                }).toList();
              }
            }

            if (updatedChunks.isEmpty) {
              return;
            }

            final rawTokensValue =
                updatedLayoutData['total_estimated_input_tokens'];
            final int? updatedTotalTokens = rawTokensValue is int
                ? rawTokensValue
                : (rawTokensValue is num ? rawTokensValue.toInt() : null);

            if (mounted) {
              final String providerKey = widget.flowId ?? widget.taskId;
              final ExcludedSegmentsNotifier excludedNotifier = ref
                  .read(excludedSegmentsProviderFamily(providerKey).notifier);

              final Set<int> updatedExcludedSet = <int>{};
              for (var i = 0; i < segmentsData.length; i++) {
                final seg = segmentsData[i];
                if (seg is Map) {
                  final bool isExcluded = seg['is_excluded'] as bool? ?? false;
                  if (isExcluded) {
                    updatedExcludedSet.add(i);
                  }
                }
              }

              excludedNotifier.setExcluded(updatedExcludedSet);

              setState(() {
                allSegments = updatedSegments;
                allChunks = updatedChunks;
                if (updatedTotalTokens != null) {
                  totalEstimatedInputTokens = updatedTotalTokens;
                }
              });

              if (updatedTotalTokens != null && updatedTotalTokens > 0) {
                _setTotalTokens(updatedTotalTokens, 'layout-extract-footers');
              }

              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) {
                  paginationController.loadFirstPage();
                  Future.delayed(const Duration(milliseconds: 150), () async {
                    if (mounted) {
                      await chunksPaginationController.loadFirstPage();
                    }
                  });
                }
              });
            }
          } catch (e) {
            _log(
              '[ExtractPreview] ERROR parsing segments/chunks for footers: $e',
              level: LogLevel.error,
            );
          }
        }
      } else {
        _log(
          '[ExtractPreview] Non-PDF file ($originalFilename), skipping layout-extract API call for footers. Chunks will be managed locally.',
          level: LogLevel.info,
        );
      }
    } catch (e, stackTrace) {
      _log(
        '[ExtractPreview] Error applying exclude footers state: $e\n$stackTrace',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to update footers exclusion: $e',
        );
      }
    }
  }

  /// Handle checkbox state change for excluding headers
  Future<void> _handleExcludeHeadersChanged(bool exclude) async {
    if (!mounted) {
      return;
    }

    setState(() {
      excludeHeaders = exclude;
    });

    await _applyExcludeHeadersState(exclude);
  }

  /// Handle checkbox state change for excluding footers
  Future<void> _handleExcludeFootersChanged(bool exclude) async {
    if (!mounted) {
      return;
    }

    setState(() {
      excludeFooters = exclude;
    });

    await _applyExcludeFootersState(exclude);
  }

  /// Handle checkbox state change for excluding references
  /// This method is called when user toggles the "Exclude References" checkbox
  /// It updates Flow-level state and refreshes segments and chunks in real-time
  Future<void> _handleExcludeReferencesChanged(bool exclude) async {
    if (!mounted) {
      _log(
        '[ExtractPreview] _handleExcludeReferencesChanged: Widget not mounted, returning',
        level: LogLevel.warn,
      );
      return;
    }

    _log(
      '[ExtractPreview] _handleExcludeReferencesChanged START: exclude=$exclude, current excludeReferences=$excludeReferences',
      level: LogLevel.info,
    );

    // Update local state
    _log(
      '[ExtractPreview] Updating local state: excludeReferences from $excludeReferences to $exclude',
      level: LogLevel.info,
    );
    setState(() {
      excludeReferences = exclude;
    });

    _log(
      '[ExtractPreview] Local state updated, calling _applyExcludeReferencesState',
      level: LogLevel.info,
    );

    // Apply the exclusion state
    await _applyExcludeReferencesState(exclude);

    _log(
      '[ExtractPreview] _handleExcludeReferencesChanged COMPLETED: exclude=$exclude',
      level: LogLevel.info,
    );
  }

  /// Load initial data: full segments for original text reconstruction, then load first page
  /// [forceReload] If true, force reload even if segments are already loaded (e.g., after resplit)
  Future<void> _loadInitialData({bool forceReload = false}) async {
    try {
      // Web-only: warn user if the document has too many pages.
      // This check is placed BEFORE the early-return so we don't miss it
      // when segments are already loaded (e.g. on polling re-entry).
      if (kIsWeb && !hasShownLargeFileWarning) {
        final TranslationService svc = TranslationService();
        final Map<String, dynamic> status = await svc.getStatus(widget.taskId);
        if (mounted) {
          final int pageCount = (status['page_count'] as int?) ?? 0;
          _log(
            '[LARGE-FILE-WARN] _loadInitialData: pageCount=$pageCount, '
            'threshold=500, willShow=${pageCount > 500}, taskId=${widget.taskId}',
            level: LogLevel.info,
          );
          if (pageCount > 500) {
            hasShownLargeFileWarning = true;
            _log(
              '[LARGE-FILE-WARN] Showing large-file warning for $pageCount pages, taskId=${widget.taskId}',
              level: LogLevel.warn,
            );
            MessageService.showWarning(
              context,
              'This document has $pageCount pages. Large documents may cause the browser to run out of memory. '
              'For files over 500 pages, please use the desktop application.',
            );
          }
        }
      }

      // Skip loading if segments were already restored from cache (unless forceReload is true)
      // forceReload is used when resplit completes to ensure chunks are regenerated with new chunk_size
      if (!forceReload && allSegments.isNotEmpty && allSeparators.isNotEmpty) {
        if (kDebugMode) {}
        // Still need to load first page for pagination
        await paginationController.loadFirstPage();
        if (!mounted) return;
        if (mounted) {
          setState(() {
            initialDataLoaded = true;
            isPreparing = false;
            isExclusionPanelExpanded =
                true; // Default to expanded in Extract phase
          });
          prepareTimer?.cancel();
        }
        return;
      }

      // If forceReload is true, clear existing data to ensure fresh load
      if (forceReload) {
        // Reset scroll controllers to prevent ScrollPosition errors
        if (segmentsScrollController.hasClients) {
          segmentsScrollController.jumpTo(0);
        }
        if (chunksScrollController.hasClients) {
          chunksScrollController.jumpTo(0);
        }
        if (kDebugMode) {}
        setState(() {
          allSegments = <String>[];
          allChunks = <String>[];
          allSeparators = <String>[];
          initialDataLoaded = false;
        });
      }

      // Load full segments for original text reconstruction (one-time)
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> status = await svc.getStatus(widget.taskId);

      // Check mounted after first async operation
      if (!mounted) return;

      // CRITICAL: Check target language consistency before processing
      // Frontend target language takes priority - if backend differs, update backend first
      final TranslationQuickSettings qs = widget.flowId != null
          ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
          : ref.read(translationQuickSettingsProvider);
      final String? frontendTargetLang =
          qs.toLang.isNotEmpty ? qs.toLang : null;

      final Map<String, dynamic>? segmentsMetadata =
          status['segments_metadata'] as Map<String, dynamic>?;
      final String? backendTargetLang =
          segmentsMetadata?['last_target_lang_for_language_match'] as String?;

      // CRITICAL: If frontend and backend target languages differ, update backend first
      // This ensures MinerU processing uses the correct target language
      // After updating, trigger Language Match re-detection and refresh
      bool needsReDetection = false;
      if (frontendTargetLang != null &&
          backendTargetLang != null &&
          frontendTargetLang != backendTargetLang) {
        _log(
          '[ExtractPreview] Target language mismatch detected during refresh: '
          'frontend=$frontendTargetLang, backend=$backendTargetLang. '
          'Updating backend to match frontend and triggering re-detection.',
          level: LogLevel.info,
        );
        try {
          // Update backend to match frontend target language and trigger Language Match re-detection
          await svc.updateExcludedSegmentsForLanguage(
            widget.taskId,
            frontendTargetLang,
          );
          _log(
            '[ExtractPreview] Backend target language updated to match frontend: $frontendTargetLang. '
            'Language Match re-detection completed.',
            level: LogLevel.info,
          );
          needsReDetection = true; // Trigger refresh after re-detection
        } catch (e) {
          _log(
            '[ExtractPreview] Failed to update backend target language: $e',
            level: LogLevel.warn,
          );
          // Continue with processing even if update fails
        }
      } else if (frontendTargetLang != null && backendTargetLang == null) {
        // First time setting target language - update backend and trigger detection
        _log(
          '[ExtractPreview] Backend target language not set, updating to frontend value: $frontendTargetLang',
          level: LogLevel.info,
        );
        try {
          await svc.updateExcludedSegmentsForLanguage(
            widget.taskId,
            frontendTargetLang,
          );
          needsReDetection = true; // Trigger refresh after detection
        } catch (e) {
          _log(
            '[ExtractPreview] Failed to set backend target language: $e',
            level: LogLevel.warn,
          );
        }
      }

      // CRITICAL: If Language Match re-detection was triggered, reload data to reflect changes
      if (needsReDetection && mounted) {
        _log(
          '[ExtractPreview] Language Match re-detection completed, reloading data to reflect changes',
          level: LogLevel.info,
        );
        // Reload data after a brief delay to ensure backend has processed the update
        await Future.delayed(const Duration(milliseconds: 500));
        // Continue with normal data loading below, which will use the updated target language
      }

      final String statusText =
          (status['status'] ?? '').toString().toLowerCase();
              if (statusText == 'failed') {
                final String failureMessage =
                    status['message']?.toString() ?? '';
                final String errorMessage =
                    status['error']?.toString() ?? '';
        final String combinedMessage = failureMessage.isNotEmpty
            ? failureMessage
            : (errorMessage.isNotEmpty
                ? errorMessage
                      : AppLocalizations.of(context)!
                          .extractFormatConversionFailed);
        setState(() {
          initialDataLoaded = true;
          isPreparing = false;
          prepareErrorMessage = combinedMessage;
        });
        // Use addPostFrameCallback to ensure context is fully initialized
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && context.mounted) {
            MessageService.showError(context, combinedMessage);
          }
        });
        return;
      }

      // Check if this is a PDF file - try layout-extract API first
      final String originalFilename =
          status['original_filename'] as String? ?? '';
      final bool isPdfFile = originalFilename.toLowerCase().endsWith('.pdf');

      if (isPdfFile) {
        try {
          if (kDebugMode) {
            _log(
              '[ExtractPreview] PDF file detected, trying layout-extract API (will use current chunk_size from settings)',
            );
          }
          // Get current chunk_size from global settings to ensure chunks are regenerated with current setting
          final GlobalSettings globalSettings =
              ref.read(globalSettingsProvider);
          // Get target language from Quick Settings for language match detection
          final TranslationQuickSettings qs = widget.flowId != null
              ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
              : ref.read(translationQuickSettingsProvider);
          final String? targetLang = qs.toLang.isNotEmpty ? qs.toLang : null;

          // CRITICAL: Check target language consistency before loading data
          // Get status to check last_target_lang_for_language_match
          final Map<String, dynamic> status =
              await svc.getStatus(widget.taskId);
          final Map<String, dynamic>? segmentsMetadata =
              status['segments_metadata'] as Map<String, dynamic>?;
          final String? storedTargetLang =
              segmentsMetadata?['last_target_lang_for_language_match']
                  as String?;

          // Check if target language has changed
          if (targetLang != null &&
              storedTargetLang != null &&
              storedTargetLang != targetLang) {
            _log(
              '[ExtractPreview] Target language mismatch detected: stored=$storedTargetLang, current=$targetLang. '
              'Triggering Language Match re-detection.',
              level: LogLevel.info,
            );
            // Trigger re-detection by calling updateExcludedSegmentsForLanguage
            // This will update backend and refresh the data
            try {
              await svc.updateExcludedSegmentsForLanguage(
                widget.taskId,
                targetLang,
              );
              _log(
                '[ExtractPreview] Language Match re-detection triggered successfully.',
                level: LogLevel.info,
              );
            } catch (e) {
              _log(
                '[ExtractPreview] Failed to trigger Language Match re-detection: $e',
                level: LogLevel.warn,
              );
              // Continue loading data even if re-detection fails
            }
          } else if (targetLang != null && storedTargetLang == null) {
            // First time setting target language - trigger detection
            _log(
              '[ExtractPreview] First time setting target language: $targetLang. '
              'Triggering Language Match detection.',
              level: LogLevel.info,
            );
            try {
              await svc.updateExcludedSegmentsForLanguage(
                widget.taskId,
                targetLang,
              );
              _log(
                '[ExtractPreview] Language Match detection triggered successfully.',
                level: LogLevel.info,
              );
            } catch (e) {
              _log(
                '[ExtractPreview] Failed to trigger Language Match detection: $e',
                level: LogLevel.warn,
              );
              // Continue loading data even if detection fails
            }
          }

          // CRITICAL: Re-read targetLang right before calling getLayoutExtract to ensure we use the latest value
          // This prevents race conditions where language was changed but we're still using the old value
          final TranslationQuickSettings latestQs = widget.flowId != null
              ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
              : ref.read(translationQuickSettingsProvider);
          final String? latestTargetLang =
              latestQs.toLang.isNotEmpty ? latestQs.toLang : null;

          _log(
            '[ExtractPreview] Re-reading targetLang before getLayoutExtract: previous=$targetLang, latest=$latestTargetLang',
            level: LogLevel.info,
          );

          // CRITICAL: For PDF files, pass excluded_segment_indices to avoid duplicate API calls
          // Get excluded segment indices from excludedSegmentsProviderFamily
          final String providerKey = widget.flowId ?? widget.taskId;
          final Set<int> excludedSegments =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          final List<int> excludedIndices = excludedSegments.toList();

          // Always pass chunk_size to force regeneration of chunks with current setting
          // On 404 (layout not ready), poll status until completed then retry once so Extract completes after conversion
          Map<String, dynamic>? layoutData;
          try {
            layoutData = await svc.getLayoutExtract(
              widget.taskId,
              excludedSegmentIndices: excludedIndices,
              targetLang:
                  latestTargetLang, // Use latest value instead of cached value
            );
          } catch (e) {
            if (kDebugMode) {
              _log(
                '[ExtractPreview] Layout-extract failed (will retry if task still processing): $e',
              );
            }
            final Map<String, dynamic> currentStatus =
                await svc.getStatus(widget.taskId);
            final String st =
                (currentStatus['status'] ?? '').toString().toLowerCase();
            if (st == 'processing' || st == 'pending') {
              const Duration maxWait = Duration(seconds: 300);
              const Duration interval = Duration(seconds: 2);
              final DateTime deadline = DateTime.now().add(maxWait);
              while (DateTime.now().isBefore(deadline) && mounted) {
                await Future.delayed(interval);
                final Map<String, dynamic> pollStatus =
                    await svc.getStatus(widget.taskId);
                final String pollSt =
                    (pollStatus['status'] ?? '').toString().toLowerCase();
                if (pollSt == 'completed' || pollSt == 'failed') break;
              }
              if (mounted) {
                try {
                  layoutData = await svc.getLayoutExtract(
                    widget.taskId,
                    excludedSegmentIndices: excludedIndices,
                    targetLang: latestTargetLang,
                  );
                } catch (retryE) {
                  if (kDebugMode) {
                    _log(
                      '[ExtractPreview] Layout-extract retry failed: $retryE',
                    );
                  }
                  layoutData = null;
                }
              } else {
                layoutData = null;
              }
            } else {
              layoutData = null;
            }
          }

          if (layoutData != null &&
              layoutData['ready'] == true &&
              layoutData['segments'] != null) {
            // Load segments (left panel - Deep split fragments)
            final List<dynamic> segmentsData =
                layoutData['segments'] as List<dynamic>? ?? <dynamic>[];
            segmentExclusionReasons.clear(); // Clear old exclusion reasons
            segmentTypeInfo.clear(); // Clear old type info
            // Store segment exclusion status from backend for checkbox state calculation
            final Map<int, bool> segmentExcludedStatus = <int, bool>{};

            allSegments = segmentsData.asMap().entries.map((entry) {
              final int index = entry.key;
              final seg = entry.value;
              if (seg is Map) {
                // CRITICAL: Read both exclusion_reason and detected_exclusion_reason
                // detected_exclusion_reason includes all detected types (even if not excluded)
                // This is essential for displaying correct tags and statistics when target_lang changes
                final String? exclusionReason =
                    seg['exclusion_reason'] as String?;
                final String? detectedExclusionReason =
                    seg['detected_exclusion_reason'] as String?;

                // Use detected_exclusion_reason if available (includes all detected types, even if not excluded)
                // Otherwise use exclusion_reason (only for excluded segments)
                final String? reasonToUse =
                    detectedExclusionReason ?? exclusionReason;

                if (reasonToUse != null) {
                  segmentExclusionReasons[index] = reasonToUse;
                }

                // Store is_excluded status from backend for checkbox state calculation
                final bool isExcluded = seg['is_excluded'] as bool? ?? false;
                segmentExcludedStatus[index] = isExcluded;

                // Store type information for all segments (for statistics and filtering)
                final String? blockType = seg['block_type'] as String?;
                final bool? isTableBody = seg['is_table_body'] as bool?;
                final bool? isImage = seg['is_image'] as bool?;
                if (blockType != null ||
                    isTableBody != null ||
                    isImage != null) {
                  segmentTypeInfo[index] = <String, dynamic>{
                    'block_type': blockType,
                    'is_table_body': isTableBody,
                    'is_image': isImage,
                  };
                }

                // Backfill exclusionReason from blockType when backend omits it
                if (blockType == 'interline_equation') {
                  segmentExclusionReasons.putIfAbsent(
                    index,
                    () => ExclusionReason.formula.value,
                  );
                }

                return seg['text'] as String? ?? '';
              }
              return seg.toString();
            }).toList();

            // Load chunks (right panel - Merged segments for translation)
            final List<dynamic> chunksData =
                layoutData['chunks'] as List<dynamic>? ?? <dynamic>[];
            allChunks = chunksData.map((chunk) {
              if (chunk is Map) {
                return chunk['text'] as String? ?? '';
              }
              return chunk.toString();
            }).toList();

            // Load total estimated input tokens
            final rawTokensValue = layoutData['total_estimated_input_tokens'];
            totalEstimatedInputTokens = rawTokensValue is int
                ? rawTokensValue
                : (rawTokensValue is num ? rawTokensValue.toInt() : null);

            // Update provider for toolbar display
            if (totalEstimatedInputTokens != null &&
                totalEstimatedInputTokens! > 0) {
              _setTotalTokens(
                totalEstimatedInputTokens!,
                'layout-extract-total',
              );
            } else {
              // If not provided, calculate from chunks
              var calculatedTotal = 0;
              for (final chunk in chunksData) {
                if (chunk is Map) {
                  final int? tokens = chunk['estimated_input_tokens'] as int?;
                  if (tokens != null && tokens > 0) {
                    calculatedTotal += tokens;
                  }
                }
              }
              if (calculatedTotal > 0) {
                totalEstimatedInputTokens = calculatedTotal;
                _setTotalTokens(calculatedTotal, 'layout-extract-chunks');
              }
            }

            // Force rebuild to ensure token display updates
            if (mounted) {
              setState(() {});
            }

            if (kDebugMode) {
              _log(
                '[ExtractPreview] Loaded ${allChunks.length} chunks from layout-extract',
              );
            }

            // Load image data map (already in correct format from backend)
            final Map<String, dynamic>? imageDataMapRaw =
                layoutData['image_data_map'] as Map<String, dynamic>?;
            if (imageDataMapRaw != null) {
              imageDataMap = imageDataMapRaw.map((String key, value) {
                if (value is Map) {
                  return MapEntry(
                    key,
                    Map<String, String>.from(
                      value.map((k, v) => MapEntry(k.toString(), v.toString())),
                    ),
                  );
                }
                return MapEntry(key, <String, String>{});
              });
              if (kDebugMode) {
                _log(
                  '[ExtractPreview] Loaded ${imageDataMap.length} images in image_data_map from layout-extract',
                );
              }
            }

            // Auto-exclude segments marked as excluded (images, pure numbers, etc.)
            // Unified handling for all workflows (PDF, DOCX, XLSX, etc.)
            // CRITICAL: Clear old excluded state and rebuild from API response
            // This ensures that when language changes, old exclusions are cleared
            final String providerKey = widget.flowId ?? widget.taskId;
            final ExcludedSegmentsNotifier excludedNotifier =
                ref.read(excludedSegmentsProviderFamily(providerKey).notifier);
            final Set<int> newExcluded = <int>{};

            for (var i = 0; i < segmentsData.length; i++) {
              final seg = segmentsData[i];
              if (seg is Map) {
                // Default-not-excluded: do not add structural (header/footer) to excluded set on initial load
                // so checkbox state stays unchecked even if backend sent is_excluded=true for them
                final String? blockType = seg['block_type'] as String?;
                if (blockType == 'header' ||
                    blockType == 'page_header' ||
                    blockType == 'footer' ||
                    blockType == 'page_footer') {
                  final bool isExcluded = seg['is_excluded'] as bool? ?? false;
                  if (isExcluded && kDebugMode) {
                    _log(
                      '[ExtractPreview] Skipping structural segment index $i (block_type=$blockType) from initial excluded set (default not exclude)',
                      level: LogLevel.info,
                    );
                  }
                  continue;
                }
                final bool isExcluded = seg['is_excluded'] as bool? ?? false;
                if (isExcluded) {
                  newExcluded.add(i);
                }
              }
            }

            // Always update excluded state (even if empty) to clear old exclusions
            excludedNotifier.setExcluded(newExcluded);
            if (kDebugMode) {
              _log(
                '[ExtractPreview] Auto-excluded ${newExcluded.length} segments (unified detection for all workflows)',
              );
            }

            // Set separators (empty for layout-based extract)
            allSeparators = List.generate(allSegments.length, (_) => '\n\n');

            if (kDebugMode) {
              _log(
                '[ExtractPreview] Loaded ${allSegments.length} segments and ${allChunks.length} chunks from layout-extract',
              );
            }


            setState(() {
              initialDataLoaded = true;
              isPreparing = false;
              isExclusionPanelExpanded =
                  true; // Default to expanded in Extract phase
            });

            // DEBUG: Log exclusion statistics after data load (PDF/DOCX)
            final Map<String, int> exclusionCounts =
                _calculateExclusionCounts();
            final String debugProviderKey = widget.flowId ?? widget.taskId;
            final Set<int> excludedSegments =
                ref.read(excludedSegmentsProviderFamily(debugProviderKey));
            _log(
              '[ExtractPreview] === Exclusion Statistics After Data Load (PDF/DOCX) ===\n'
              'Total segments: ${allSegments.length}\n'
              'Excluded segments: ${excludedSegments.length}\n'
              'Type counts:\n${exclusionCounts.entries.where((e) => e.value > 0).map((e) => '  ${e.key}: ${e.value}').join('\n')}\n'
              'Stored indices:\n'
              '  referenceSegmentIndices: ${referenceSegmentIndices.length}\n'
              '  headerSegmentIndices: ${headerSegmentIndices.length}\n'
              '  footerSegmentIndices: ${footerSegmentIndices.length}\n'
              '  tableSegmentIndices: ${tableSegmentIndices.length}\n'
              '  identifierSegmentIndices: ${identifierSegmentIndices.length}\n'
              '  languageMatchedSegmentIndices: ${languageMatchedSegmentIndices.length}\n'
              '  userSelectedSegmentIndices: ${userSelectedSegmentIndices.length}\n'
              '  languageMatchedSegmentCount: $languageMatchedSegmentCount\n'
              'segmentExclusionReasons count: ${segmentExclusionReasons.length}\n'
              '${segmentExclusionReasons.isNotEmpty ? segmentExclusionReasons.values.fold<Map<String, int>>(<String, int>{}, (map, reason) => map..[reason] = (map[reason] ?? 0) + 1).entries.map((e) => '  ${e.key}: ${e.value}').join('\n') : ''}\n'
              '==========================================',
            );

            // Check language exclusion state after data is loaded
            final TranslationQuickSettings qs = widget.flowId != null
                ? ref.read(
                    translationQuickSettingsProviderFamily(widget.flowId!),
                  )
                : ref.read(translationQuickSettingsProvider);
            // CRITICAL: Always re-detect exclusions with current target_lang to ensure consistency
            // This fixes the issue where initial detection might have used wrong target_lang (None or 'en')
            await _validateAndRefreshExclusionsForTargetLang(qs.toLang);

            // Pre-calculate all segment heights using SegmentHeightCalculator
            // This ensures stable maxScrollExtent and prevents scrollbar jitter
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted && segmentsScrollManager != null) {
                _precalculateAllHeights();
              }
            });

            // Check for references (bibliography), headers, and footers in PDF/DOCX files
            // Store segment indices for checkbox display
            // Clear and reuse Mixin variables
            referenceSegmentIndices.clear();
            headerSegmentIndices.clear();
            footerSegmentIndices.clear();

            // Check if this is PDF or DOCX workflow
            final bool isPdfFile =
                originalFilename.toLowerCase().endsWith('.pdf');
            final bool isDocxFile =
                originalFilename.toLowerCase().endsWith('.docx');
            final bool isPdfOrDocx = isPdfFile || isDocxFile;

            // Track table and formula segments (for exclusion checkboxes)
            tableSegmentIndices.clear();
            formulaSegmentIndices.clear();
            // Track identifier, language_match, and user_selected segments
            identifierSegmentIndices.clear();
            languageMatchedSegmentIndices.clear();
            userSelectedSegmentIndices.clear();

            for (var i = 0; i < segmentsData.length; i++) {
              final seg = segmentsData[i];
              if (seg is Map) {
                final String? blockType = seg['block_type'] as String?;
                final bool? isTableBody = seg['is_table_body'] as bool?;
                final String? exclusionReason =
                    seg['exclusion_reason'] as String?;

                // Debug: log all block types for first 20 segments to help diagnose
                if (i < 20) {
                  _log(
                    '[ExtractPreview] Segment $i: block_type=$blockType, is_table_body=$isTableBody, exclusion_reason=$exclusionReason, isPdfOrDocx=$isPdfOrDocx',
                  );
                }

                if (blockType == 'ref_text') {
                  referenceSegmentIndices.add(i);
                } else if (isPdfOrDocx &&
                    (blockType == 'header' || blockType == 'page_header')) {
                  headerSegmentIndices.add(i);
                  _log(
                    '[ExtractPreview] Found header segment at index $i: block_type=$blockType',
                    level: LogLevel.info,
                  );
                } else if (isPdfOrDocx &&
                    (blockType == 'footer' || blockType == 'page_footer')) {
                  footerSegmentIndices.add(i);
                  _log(
                    '[ExtractPreview] Found footer segment at index $i: block_type=$blockType',
                    level: LogLevel.info,
                  );
                } else if (blockType == 'table_body' ||
                    (isTableBody ?? false)) {
                  // Track table body segments only (table_caption and table_footnote are treated as normal text)
                  tableSegmentIndices.add(i);
                  _log(
                    '[ExtractPreview] Found table segment at index $i: block_type=$blockType, is_table_body=$isTableBody',
                    level: LogLevel.info,
                  );
                } else if (blockType == 'interline_equation') {
                  // Track formula (interline equation) segments
                  formulaSegmentIndices.add(i);
                  // Ensure exclusion reason is recorded so the EX badge shows "EX: Formula"
                  segmentExclusionReasons.putIfAbsent(
                    i,
                    () => ExclusionReason.formula.value,
                  );
                }

                // Track identifier, language_match, and user_selected segments
                // CRITICAL: Check both detected_exclusion_reason and exclusion_reason to identify segments
                // detected_exclusion_reason includes all detected types (even if not excluded)
                // This ensures we identify segments correctly when target_lang changes
                final String? detectedExclusionReason =
                    seg['detected_exclusion_reason'] as String?;
                final bool isExcluded = seg['is_excluded'] as bool? ?? false;

                // Use detected_exclusion_reason if available (includes all detected types, even if not excluded)
                // Otherwise use exclusion_reason (only for excluded segments)
                final String? reasonToUse =
                    detectedExclusionReason ?? exclusionReason;

                if (reasonToUse != null) {
                  if (reasonToUse == ExclusionReason.identifier.value) {
                    identifierSegmentIndices.add(i);
                  } else if (reasonToUse ==
                      ExclusionReason.languageMatch.value) {
                    languageMatchedSegmentIndices.add(i);
                  } else if (reasonToUse ==
                          ExclusionReason.userSelected.value ||
                      reasonToUse == ExclusionReason.unknown.value) {
                    userSelectedSegmentIndices.add(i);
                  } else if (reasonToUse == ExclusionReason.formula.value) {
                    // Formula segments detected by exclusion reason (DOCX/PPTX without block_type)
                    if (!formulaSegmentIndices.contains(i)) {
                      formulaSegmentIndices.add(i);
                    }
                  }
                } else if (isExcluded) {
                  // If segment is excluded but has no exclusion_reason, it might be a newly excluded segment
                  // Check if it's in the excluded set to identify its type
                  // Note: This is a fallback, ideally exclusion_reason should always be set
                }
              }
            }

            // Rebuild cached Sets so hot-path contains() checks are O(1)
            invalidateIndexSets();

            // If references found, update state and set initial checkbox state
            if (referenceSegmentIndices.isNotEmpty) {
              _log(
                '[ExtractPreview] Found ${referenceSegmentIndices.length} reference segments: ${referenceSegmentIndices.toList()}',
                level: LogLevel.info,
              );

              // Reference segment indices are already updated above
              if (mounted) {
                // CRITICAL: Check if references are already excluded by backend
                // Backend may have already excluded references during extraction
                // Only call exclusion API if references are not already excluded
                final String providerKey = widget.flowId ?? widget.taskId;
                final Set<int> currentExcluded =
                    ref.read(excludedSegmentsProviderFamily(providerKey));
                final int excludedReferenceCount = currentExcluded
                    .where((index) => referenceSegmentIndices.contains(index))
                    .length;

                if (excludedReferenceCount == referenceSegmentIndices.length) {
                  // All references are already excluded by backend
                  // Just update local state, no need to call API
                  _log(
                    '[ExtractPreview] All ${referenceSegmentIndices.length} reference segments are already excluded by backend, skipping exclusion API call',
                    level: LogLevel.info,
                  );
                  setState(() {
                    excludeReferences = true;
                  });
                } else if (excludedReferenceCount == 0) {
                  // No references are excluded, need to exclude them
                  // Use new method that supports all formats and has optimistic update
                  _log(
                    '[ExtractPreview] No reference segments are excluded, calling exclusion API',
                    level: LogLevel.info,
                  );
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (mounted) {
                      _handleExcludeReferenceSegments(true);
                    }
                  });
                } else {
                  // Partial exclusion - some references are excluded, some are not
                  // Update local state to reflect current backend state
                  _log(
                    '[ExtractPreview] Partial reference exclusion: $excludedReferenceCount/${referenceSegmentIndices.length} excluded, updating local state only',
                    level: LogLevel.info,
                  );
                  setState(() {
                    excludeReferences = excludedReferenceCount > 0;
                  });
                }
              }
            } else {
              // No references found, clear state
              if (mounted) {
                setState(() {
                  referenceSegmentIndices = <int>[];
                  invalidateIndexSets();
                  excludeReferences = false;
                  categoryExclusionStates['reference'] = false;
                });
              }
            }

            // If headers found, update state (default to NOT exclude)
            if (headerSegmentIndices.isNotEmpty) {
              _log(
                '[ExtractPreview] Found ${headerSegmentIndices.length} header segments: ${headerSegmentIndices.toList()}',
                level: LogLevel.info,
              );
              if (mounted) {
                setState(() {
                  excludeHeaders = false; // Default to NOT exclude
                  // Always set structural to false when headers exist and we default to not exclude
                  categoryExclusionStates['structural'] = false;
                });
                _log(
                  '[ExtractPreview] Structural (header) exclusion state initialized: default not exclude, checkbox=false',
                  level: LogLevel.info,
                );
              }
            } else {
              if (mounted) {
                setState(() {
                  headerSegmentIndices = <int>[];
                  invalidateIndexSets();
                  excludeHeaders = false;
                });
              }
            }

            // If footers found, update state (default to NOT exclude)
            if (footerSegmentIndices.isNotEmpty) {
              _log(
                '[ExtractPreview] Found ${footerSegmentIndices.length} footer segments: ${footerSegmentIndices.toList()}',
                level: LogLevel.info,
              );
              if (mounted) {
                setState(() {
                  excludeFooters = false; // Default to NOT exclude
                  // Always set structural to false when footers exist and we default to not exclude
                  categoryExclusionStates['structural'] = false;
                });
                _log(
                  '[ExtractPreview] Structural (footer) exclusion state initialized: default not exclude, checkbox=false',
                  level: LogLevel.info,
                );
              }
            } else {
              if (mounted) {
                setState(() {
                  footerSegmentIndices = <int>[];
                  invalidateIndexSets();
                  excludeFooters = false;
                });
              }
            }

            // If tables found, update state based on backend is_excluded status (default to NOT exclude)
            if (tableSegmentIndices.isNotEmpty) {
              _log(
                '[ExtractPreview] Found ${tableSegmentIndices.length} table segments: ${tableSegmentIndices.toList()}',
                level: LogLevel.info,
              );
              // Table segment indices are already updated above
              if (mounted) {
                // Check backend is_excluded status for all table segments
                // Default state is determined by backend, not frontend
                int excludedTableCount = 0;
                for (final tableIdx in tableSegmentIndices) {
                  if (tableIdx < segmentsData.length) {
                    final seg = segmentsData[tableIdx];
                    if (seg is Map) {
                      final bool isExcluded =
                          seg['is_excluded'] as bool? ?? false;
                      if (isExcluded) {
                        excludedTableCount++;
                      }
                    }
                  }
                }
                // If all table segments are excluded, checkbox should be checked
                // Otherwise, checkbox should be unchecked (default state from backend)
                final bool allTablesExcluded =
                    excludedTableCount == tableSegmentIndices.length;
                setState(() {
                  // Initialize table exclusion state based on backend is_excluded status
                  categoryExclusionStates['table'] = allTablesExcluded;
                });
                _log(
                  '[ExtractPreview] Table exclusion state initialized from backend: $excludedTableCount/${tableSegmentIndices.length} tables excluded, checkbox=$allTablesExcluded',
                  level: LogLevel.info,
                );
              }
            } else {
              // No tables found, clear state
              if (mounted) {
                setState(() {
                  tableSegmentIndices = <int>[];
                  invalidateIndexSets();
                  categoryExclusionStates['table'] = false;
                });
              }
            }

            // Store identifier, language_match, and user_selected segment indices
            // Also initialize checkbox states based on backend is_excluded status
            // Note: Segment indices are already updated above, no need to reassign
            if (mounted) {
              setState(() {
                // Initialize checkbox states based on backend is_excluded status
                // This ensures checkbox state matches backend configuration
                if (identifierSegmentIndices.isNotEmpty) {
                  // Check how many identifier segments are excluded according to backend
                  int excludedIdentifierCount = 0;
                  for (final idx in identifierSegmentIndices) {
                    if (idx < segmentsData.length) {
                      final seg = segmentsData[idx];
                      if (seg is Map) {
                        final bool isExcluded =
                            seg['is_excluded'] as bool? ?? false;
                        if (isExcluded) {
                          excludedIdentifierCount++;
                        }
                      }
                    }
                  }
                  categoryExclusionStates['identifier'] =
                      excludedIdentifierCount > 0;
                  _log(
                    '[ExtractPreview] Found ${identifierSegmentIndices.length} identifier segments: ${identifierSegmentIndices.toList()}, '
                    'excluded count from backend: $excludedIdentifierCount, checkbox=${categoryExclusionStates['identifier']}',
                    level: LogLevel.info,
                  );
                }
                if (languageMatchedSegmentIndices.isNotEmpty) {
                  // Check how many language-matched segments are excluded according to backend
                  int excludedLanguageCount = 0;
                  for (final idx in languageMatchedSegmentIndices) {
                    if (idx < segmentsData.length) {
                      final seg = segmentsData[idx];
                      if (seg is Map) {
                        final bool isExcluded =
                            seg['is_excluded'] as bool? ?? false;
                        if (isExcluded) {
                          excludedLanguageCount++;
                        }
                      }
                    }
                  }
                  categoryExclusionStates['language_match'] =
                      excludedLanguageCount > 0;
                  _log(
                    '[ExtractPreview] Found ${languageMatchedSegmentIndices.length} language-matched segments: ${languageMatchedSegmentIndices.toList()}, '
                    'excluded count from backend: $excludedLanguageCount, checkbox=${categoryExclusionStates['language_match']}',
                    level: LogLevel.info,
                  );
                }
                if (userSelectedSegmentIndices.isNotEmpty) {
                  // Check how many user-selected segments are excluded according to backend
                  int excludedUserSelectedCount = 0;
                  for (final idx in userSelectedSegmentIndices) {
                    if (idx < segmentsData.length) {
                      final seg = segmentsData[idx];
                      if (seg is Map) {
                        final bool isExcluded =
                            seg['is_excluded'] as bool? ?? false;
                        if (isExcluded) {
                          excludedUserSelectedCount++;
                        }
                      }
                    }
                  }
                  categoryExclusionStates['user_selected'] =
                      excludedUserSelectedCount > 0;
                  _log(
                    '[ExtractPreview] Found ${userSelectedSegmentIndices.length} user-selected segments: ${userSelectedSegmentIndices.toList()}, '
                    'excluded count from backend: $excludedUserSelectedCount, checkbox=${categoryExclusionStates['user_selected']}',
                    level: LogLevel.info,
                  );
                }
              });
            }

            // Refresh pagination controllers with new data
            // For segments pagination, it uses API fetcher, so just refresh
            // For chunks pagination, it uses allChunks list, so refresh will reload from updated list
            await paginationController.loadFirstPage();
            if (!mounted) return;

            // CRITICAL: Also refresh chunks pagination controller to display chunks in right panel
            // Use addPostFrameCallback to ensure UI is updated before refreshing chunks pagination
            WidgetsBinding.instance.addPostFrameCallback((_) async {
              if (!mounted) return;

              if (kDebugMode) {
                _log(
                  '[ExtractPreview] PostFrameCallback (PDF): Refreshing chunks pagination controller, allChunks=${allChunks.length}',
                  level: LogLevel.info,
                );
              }

              await chunksPaginationController.loadFirstPage();

              if (kDebugMode && mounted) {
                _log(
                  '[ExtractPreview] Chunks pagination refreshed (PDF): items=${chunksPaginationController.items.length}, total=${chunksPaginationController.total}',
                  level: LogLevel.info,
                );
              }
            });
          } else {
            // Layout-extract not ready or failed (including after retry); stop loading and show reason
            if (mounted) {
              setState(() {
                isPreparing = false;
                initialDataLoaded = true;
              });
            }
            // Check if conversion failed (more accurate error message)
            try {
              final Map<String, dynamic> status =
                  await svc.getStatus(widget.taskId);
              final String taskStatus =
                  status['status']?.toString().toLowerCase() ?? '';
              final bool errorFlag = status['error_flag'] as bool? ?? false;
              final String errorMsg = status['error']?.toString() ?? '';

              if (errorFlag || taskStatus == 'failed') {
                // Conversion failed, show error message
                if (mounted) {
                  final String userErrorMsg = errorMsg.isNotEmpty
                      ? 'File conversion failed: ${errorMsg.length > 100 ? "${errorMsg.substring(0, 100)}..." : errorMsg}'
                      : 'File conversion failed. Please check your network connection and try again.';
                  MessageService.showError(context, userErrorMsg);
                }
                if (kDebugMode) {
                  _log(
                    '[ExtractPreview] Layout-extract failed: conversion failed. Error: $errorMsg',
                  );
                }
              } else {
                // Likely cached conversion (no error, but no layout_document)
                if (kDebugMode) {
                  _log(
                    '[ExtractPreview] Layout-extract failed: layout_document not available. This PDF file may have been processed with cached conversion. Falling back to source-preview (may not have deep split).',
                  );
                }
                // Show warning to user that deep split may not be available
                if (mounted) {
                  MessageService.showWarning(
                    context,
                    'PDF file was processed with cached conversion. Deep split segments may not be available. Please re-import the file to enable full layout-based extraction.',
                  );
                }
              }
            } catch (statusError) {
              // If status check fails, show generic warning
              if (kDebugMode) {
                _log(
                  '[ExtractPreview] Layout-extract failed: layout_document not available. Status check failed: $statusError',
                );
              }
              if (mounted) {
                MessageService.showWarning(
                  context,
                  'PDF file was processed with cached conversion. Deep split segments may not be available. Please re-import the file to enable full layout-based extraction.',
                );
              }
            }
          }
        } catch (e) {
          if (kDebugMode) {
            _log(
              '[ExtractPreview] Layout-extract failed, falling back to source-preview: $e',
            );
          }
        }
      } else {
        // For non-PDF files (DOCX, PPTX, HTML, etc.), use source-preview API
        try {
          if (kDebugMode) {
            _log(
              '[ExtractPreview] Non-PDF file detected, using source-preview API',
            );
          }

          // Get current chunk_size from global settings
          final GlobalSettings globalSettings =
              ref.read(globalSettingsProvider);

          // Get target language from Quick Settings for language match detection
          final TranslationQuickSettings qs = widget.flowId != null
              ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
              : ref.read(translationQuickSettingsProvider);
          final String? targetLang = qs.toLang.isNotEmpty ? qs.toLang : null;

          // CRITICAL: Check target language consistency before loading data
          // Get status to check last_target_lang_for_language_match
          final Map<String, dynamic> status =
              await svc.getStatus(widget.taskId);
          final Map<String, dynamic>? segmentsMetadata =
              status['segments_metadata'] as Map<String, dynamic>?;
          final String? storedTargetLang =
              segmentsMetadata?['last_target_lang_for_language_match']
                  as String?;

          // Check if target language has changed
          if (targetLang != null &&
              storedTargetLang != null &&
              storedTargetLang != targetLang) {
            _log(
              '[ExtractPreview] Target language mismatch detected: stored=$storedTargetLang, current=$targetLang. '
              'Triggering Language Match re-detection.',
              level: LogLevel.info,
            );
            // Trigger re-detection by calling updateExcludedSegmentsForLanguage
            // This will update backend and refresh the data
            try {
              await svc.updateExcludedSegmentsForLanguage(
                widget.taskId,
                targetLang,
              );
              _log(
                '[ExtractPreview] Language Match re-detection triggered successfully.',
                level: LogLevel.info,
              );
            } catch (e) {
              _log(
                '[ExtractPreview] Failed to trigger Language Match re-detection: $e',
                level: LogLevel.warn,
              );
              // Continue loading data even if re-detection fails
            }
          } else if (targetLang != null && storedTargetLang == null) {
            // First time setting target language - trigger detection
            _log(
              '[ExtractPreview] First time setting target language: $targetLang. '
              'Triggering Language Match detection.',
              level: LogLevel.info,
            );
            try {
              await svc.updateExcludedSegmentsForLanguage(
                widget.taskId,
                targetLang,
              );
              _log(
                '[ExtractPreview] Language Match detection triggered successfully.',
                level: LogLevel.info,
              );
            } catch (e) {
              _log(
                '[ExtractPreview] Failed to trigger Language Match detection: $e',
                level: LogLevel.warn,
              );
              // Continue loading data even if detection fails
            }
          }

          // Load segments from source-preview API with pagination support
          // First, get total count and first page
          final Map<String, dynamic> firstPageRes = await svc.getSourcePreview(
            widget.taskId,
            limit: defaultSegmentPreviewLimit,
            targetLang: targetLang,
          );

          // CRITICAL: Extract image_data_map from source-preview API response
          // This is needed for MOBI/EPUB files to display images in segments
          final Map<String, dynamic>? imageDataMapRaw =
              firstPageRes['image_data_map'] as Map<String, dynamic>?;
          if (imageDataMapRaw != null) {
            imageDataMap = imageDataMapRaw.map((String key, value) {
              if (value is Map) {
                return MapEntry(
                  key,
                  Map<String, String>.from(
                    value.map((k, v) => MapEntry(k.toString(), v.toString())),
                  ),
                );
              }
              return MapEntry(key, <String, String>{});
            });
            if (kDebugMode) {
              _log(
                '[ExtractPreview] Loaded ${imageDataMap.length} images in image_data_map from source-preview',
              );
            }
          }

          final int? totalSegments = firstPageRes['total_segments'] as int? ??
              firstPageRes['total'] as int?;
          final List<dynamic>? firstPageList =
              firstPageRes['segments'] as List<dynamic>? ??
                  firstPageRes['items'] as List<dynamic>?;

          _log(
            '[ExtractPreview] _loadInitialData: First page response - '
            'total_segments=$totalSegments, '
            'returned_count=${firstPageList?.length ?? 0}, '
            'limit=$defaultSegmentPreviewLimit, '
            'ready=${firstPageRes['ready']}',
            level: LogLevel.info,
          );

          if (firstPageRes['ready'] == true && firstPageList != null) {
            // Collect all segments (will be populated with pagination if needed)
            final List<dynamic> allSegmentsList = <dynamic>[];
            allSegmentsList.addAll(firstPageList);

            // If there are more segments, fetch them in batches
            if (totalSegments != null &&
                totalSegments > allSegmentsList.length) {
              _log(
                '[ExtractPreview] _loadInitialData: Need to load more segments - '
                'total=$totalSegments, '
                'loaded=${allSegmentsList.length}, '
                'remaining=${totalSegments - allSegmentsList.length}',
                level: LogLevel.info,
              );

              var offset = allSegmentsList.length;
              int pageCount = 1;
              int consecutiveEmptyPages = 0;
              const int maxConsecutiveEmptyPages =
                  3; // Stop after 3 consecutive empty pages

              while (offset < totalSegments) {
                pageCount++;
                final Map<String, dynamic> nextPageRes =
                    await svc.getSourcePreview(
                  widget.taskId,
                  offset: offset,
                  limit: defaultSegmentPreviewLimit,
                  targetLang: targetLang,
                );
                final List<dynamic>? nextPageList =
                    nextPageRes['segments'] as List<dynamic>? ??
                        nextPageRes['items'] as List<dynamic>?;

                if (nextPageList == null || nextPageList.isEmpty) {
                  consecutiveEmptyPages++;
                  _log(
                    '[ExtractPreview] _loadInitialData: WARNING - Empty page at offset $offset '
                    '(consecutive empty: $consecutiveEmptyPages/$maxConsecutiveEmptyPages). '
                    'Expected $totalSegments total segments, loaded ${allSegmentsList.length}',
                    level: LogLevel.warn,
                  );

                  // Stop if we get too many consecutive empty pages
                  // This indicates backend doesn't have more segments despite total_segments
                  if (consecutiveEmptyPages >= maxConsecutiveEmptyPages) {
                    _log(
                      '[ExtractPreview] _loadInitialData: Stopping pagination after $consecutiveEmptyPages '
                      'consecutive empty pages. Backend may not have all segments despite total_segments=$totalSegments. '
                      'Loaded ${allSegmentsList.length} segments.',
                      level: LogLevel.warn,
                    );
                    break;
                  }

                  // Try next offset (increment by limit to skip ahead)
                  offset += defaultSegmentPreviewLimit;
                  continue;
                }

                // Reset consecutive empty pages counter on successful page
                consecutiveEmptyPages = 0;
                allSegmentsList.addAll(nextPageList);
                offset = allSegmentsList.length;

                _log(
                  '[ExtractPreview] _loadInitialData: Loaded page $pageCount - '
                  'offset=${offset - nextPageList.length}, '
                  'count=${nextPageList.length}, '
                  'total_loaded=${allSegmentsList.length}/$totalSegments',
                  level: LogLevel.info,
                );
              }

              _log(
                '[ExtractPreview] _loadInitialData: Completed loading all segments - '
                'total_pages=$pageCount, '
                'total_loaded=${allSegmentsList.length}, '
                'expected=$totalSegments',
                level: LogLevel.info,
              );
            }

            // Load segments (left panel)
            final List<dynamic> segmentsList = allSegmentsList;
            segmentTypeInfo.clear(); // Clear old type info
            segmentExclusionReasons.clear(); // Clear old exclusion reasons

            // Track formula, identifier, language_match, and user_selected segments
            formulaSegmentIndices.clear();
            identifierSegmentIndices.clear();
            languageMatchedSegmentIndices.clear();
            userSelectedSegmentIndices.clear();

            // Store segment exclusion status from backend for checkbox state calculation
            final Map<int, bool> segmentExcludedStatus = <int, bool>{};

            allSegments = segmentsList.asMap().entries.map((entry) {
              final int index = entry.key;
              final seg = entry.value;
              if (seg is String) {
                return seg;
              } else if (seg is Map) {
                // Extract exclusion_reason if available
                final String? exclusionReason =
                    seg['exclusion_reason'] as String?;
                // CRITICAL: Also check detected_exclusion_reason for all detected types (including non-excluded)
                // This allows frontend to display identifier, language_match, etc. even if not excluded
                final String? detectedExclusionReason =
                    seg['detected_exclusion_reason'] as String?;
                final bool isExcluded = seg['is_excluded'] as bool? ?? false;

                // DEBUG: Log first 20 segments to check exclusion_reason
                if (index < 20) {
                  _log(
                    '[ExtractPreview] Segment $index: exclusion_reason=$exclusionReason, detected_exclusion_reason=$detectedExclusionReason, is_excluded=$isExcluded, '
                    'seg keys: ${seg.keys.toList()}',
                  );
                }

                // Use detected_exclusion_reason if available (includes all detected types, even if not excluded)
                // Otherwise use exclusion_reason (only for excluded segments)
                final String? reasonToUse =
                    detectedExclusionReason ?? exclusionReason;

                if (reasonToUse != null) {
                  // Store in segmentExclusionReasons for statistics and filtering
                  segmentExclusionReasons[index] = reasonToUse;

                  // Track formula, identifier, language_match, and user_selected segments by reason
                  if (reasonToUse == ExclusionReason.identifier.value) {
                    identifierSegmentIndices.add(index);
                  } else if (reasonToUse ==
                      ExclusionReason.languageMatch.value) {
                    languageMatchedSegmentIndices.add(index);
                  } else if (reasonToUse ==
                          ExclusionReason.userSelected.value ||
                      reasonToUse == ExclusionReason.unknown.value) {
                    userSelectedSegmentIndices.add(index);
                  } else if (reasonToUse == ExclusionReason.formula.value) {
                    formulaSegmentIndices.add(index);
                  }
                } else if (isExcluded) {
                  // DEBUG: Log segments that are excluded but have no exclusion_reason
                  if (index < 20) {
                    _log(
                      '[ExtractPreview] WARNING: Segment $index is excluded (is_excluded=true) but has no exclusion_reason!',
                      level: LogLevel.warn,
                    );
                  }
                }

                // Store is_excluded status from backend for checkbox state calculation
                segmentExcludedStatus[index] = isExcluded;

                // Store type information for all segments (for statistics and filtering)
                final String? blockType = seg['block_type'] as String?;
                final bool? isTableBody = seg['is_table_body'] as bool?;
                final bool? isImage = seg['is_image'] as bool?;
                if (blockType != null ||
                    isTableBody != null ||
                    isImage != null) {
                  segmentTypeInfo[index] = <String, dynamic>{
                    'block_type': blockType,
                    'is_table_body': isTableBody,
                    'is_image': isImage,
                  };
                }

                // Backfill exclusionReason from blockType when backend omits it
                if (blockType == 'interline_equation') {
                  segmentExclusionReasons.putIfAbsent(
                    index,
                    () => ExclusionReason.formula.value,
                  );
                  if (!formulaSegmentIndices.contains(index)) {
                    formulaSegmentIndices.add(index);
                  }
                }

                // Extract text from object (API returns 'text' or 'source_text')
                return (seg['text'] as String?) ??
                    (seg['source_text'] as String?) ??
                    '';
              }
              return seg.toString();
            }).toList();

            // Rebuild cached Sets so hot-path contains() checks are O(1)
            invalidateIndexSets();

            // Store identifier, language_match, and user_selected segment indices
            // Also initialize checkbox states based on backend is_excluded status
            // Note: Segment indices are already updated above, no need to reassign
            if (mounted) {
              setState(() {
                // Initialize checkbox states based on backend is_excluded status
                // This ensures checkbox state matches backend configuration
                if (identifierSegmentIndices.isNotEmpty) {
                  // Check how many identifier segments are excluded according to backend
                  final int excludedIdentifierCount = identifierSegmentIndices
                      .where((idx) => segmentExcludedStatus[idx] ?? false)
                      .length;
                  categoryExclusionStates['identifier'] =
                      excludedIdentifierCount > 0;
                  _log(
                    '[ExtractPreview] Found ${identifierSegmentIndices.length} identifier segments from source-preview: ${identifierSegmentIndices.toList()}, '
                    'excluded count from backend: $excludedIdentifierCount, checkbox=${categoryExclusionStates['identifier']}',
                    level: LogLevel.info,
                  );
                }
                if (languageMatchedSegmentIndices.isNotEmpty) {
                  // Check how many language-matched segments are excluded according to backend
                  final int excludedLanguageCount =
                      languageMatchedSegmentIndices
                          .where((idx) => segmentExcludedStatus[idx] ?? false)
                          .length;
                  categoryExclusionStates['language_match'] =
                      excludedLanguageCount > 0;
                  _log(
                    '[ExtractPreview] Found ${languageMatchedSegmentIndices.length} language-matched segments from source-preview: ${languageMatchedSegmentIndices.toList()}, '
                    'excluded count from backend: $excludedLanguageCount, checkbox=${categoryExclusionStates['language_match']}',
                    level: LogLevel.info,
                  );
                }
                if (userSelectedSegmentIndices.isNotEmpty) {
                  // Check how many user-selected segments are excluded according to backend
                  final int excludedUserSelectedCount =
                      userSelectedSegmentIndices
                          .where((idx) => segmentExcludedStatus[idx] ?? false)
                          .length;
                  categoryExclusionStates['user_selected'] =
                      excludedUserSelectedCount > 0;
                  _log(
                    '[ExtractPreview] Found ${userSelectedSegmentIndices.length} user-selected segments from source-preview: ${userSelectedSegmentIndices.toList()}, '
                    'excluded count from backend: $excludedUserSelectedCount, checkbox=${categoryExclusionStates['user_selected']}',
                    level: LogLevel.info,
                  );
                }
              });
            }

            // Load chunks (right panel) if available
            final List<dynamic> chunksData =
                firstPageRes['chunks'] as List<dynamic>? ?? <dynamic>[];
            allChunks = chunksData.map((chunk) {
              if (chunk is String) {
                return chunk;
              } else if (chunk is Map) {
                return (chunk['text'] as String?) ?? chunk.toString();
              }
              return chunk.toString();
            }).toList();

            // Auto-exclude segments marked as excluded
            // CRITICAL: Clear old excluded state and rebuild from API response
            // This ensures that when language changes, old exclusions are cleared
            final String providerKey = widget.flowId ?? widget.taskId;
            final ExcludedSegmentsNotifier excludedNotifier =
                ref.read(excludedSegmentsProviderFamily(providerKey).notifier);
            final Set<int> newExcluded = <int>{};

            // Check items array for excluded segments (more reliable than segments array)
            // Use allSegmentsList for items (already contains all segments from pagination)
            final List<dynamic> itemsList = allSegmentsList;
            for (var i = 0; i < itemsList.length; i++) {
              final item = itemsList[i];
              if (item is Map) {
                // Default-not-excluded: skip structural (header/footer) on initial load
                final String? blockType = item['block_type'] as String?;
                if (blockType == 'header' ||
                    blockType == 'page_header' ||
                    blockType == 'footer' ||
                    blockType == 'page_footer') {
                  continue;
                }
                final bool isExcluded = item['is_excluded'] as bool? ?? false;
                if (isExcluded) {
                  newExcluded.add(i);
                }
              }
            }

            // Always update excluded state (even if empty) to clear old exclusions
            excludedNotifier.setExcluded(newExcluded);
            if (kDebugMode) {
              _log(
                '[ExtractPreview] Auto-excluded ${newExcluded.length} segments from source-preview',
              );
            }

            // Set separators (empty for non-PDF files)
            allSeparators = List.generate(allSegments.length, (_) => '\n\n');

            // Log final segment count for debugging
            _log(
              '[ExtractPreview] _loadInitialData: Final segment count - '
              'allSegments.length=${allSegments.length}, '
              'expected_total=$totalSegments, '
              'separators=${allSeparators.length}',
              level: LogLevel.info,
            );


            if (kDebugMode) {
              _log(
                '[ExtractPreview] Loaded ${allSegments.length} segments and ${allChunks.length} chunks from source-preview',
              );
            }

            setState(() {
              initialDataLoaded = true;
              isPreparing = false;
              isExclusionPanelExpanded =
                  true; // Default to expanded in Extract phase
            });

            // DEBUG: Log exclusion statistics after data load (source-preview)
            final Map<String, int> exclusionCounts =
                _calculateExclusionCounts();
            final String debugProviderKey = widget.flowId ?? widget.taskId;
            final Set<int> excludedSegments =
                ref.read(excludedSegmentsProviderFamily(debugProviderKey));
            _log(
              '[ExtractPreview] === Exclusion Statistics After Data Load (source-preview) ===\n'
              'Total segments: ${allSegments.length}\n'
              'Excluded segments: ${excludedSegments.length}\n'
              'Type counts:\n${exclusionCounts.entries.where((e) => e.value > 0).map((e) => '  ${e.key}: ${e.value}').join('\n')}\n'
              'Stored indices:\n'
              '  referenceSegmentIndices: ${referenceSegmentIndices.length}\n'
              '  headerSegmentIndices: ${headerSegmentIndices.length}\n'
              '  footerSegmentIndices: ${footerSegmentIndices.length}\n'
              '  tableSegmentIndices: ${tableSegmentIndices.length}\n'
              '  identifierSegmentIndices: ${identifierSegmentIndices.length}\n'
              '  languageMatchedSegmentIndices: ${languageMatchedSegmentIndices.length}\n'
              '  userSelectedSegmentIndices: ${userSelectedSegmentIndices.length}\n'
              '  languageMatchedSegmentCount: $languageMatchedSegmentCount\n'
              'segmentExclusionReasons count: ${segmentExclusionReasons.length}\n'
              '${segmentExclusionReasons.isNotEmpty ? segmentExclusionReasons.values.fold<Map<String, int>>(<String, int>{}, (map, reason) => map..[reason] = (map[reason] ?? 0) + 1).entries.map((e) => '  ${e.key}: ${e.value}').join('\n') : ''}\n'
              '==========================================',
            );

            // Check language exclusion state after data is loaded
            final TranslationQuickSettings qs = widget.flowId != null
                ? ref.read(
                    translationQuickSettingsProviderFamily(widget.flowId!),
                  )
                : ref.read(translationQuickSettingsProvider);
            // CRITICAL: Always re-detect exclusions with current target_lang to ensure consistency
            // This fixes the issue where initial detection might have used wrong target_lang (None or 'en')
            await _validateAndRefreshExclusionsForTargetLang(qs.toLang);

            // Measure heights after initial data load (text content loaded)
            // This ensures scrollToIndex works correctly with loaded content
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted && segmentsScrollManager != null) {
                _precalculateAllHeights();
              }
            });

            // Refresh pagination controllers with new data
            await paginationController.loadFirstPage();
            if (!mounted) return;

            // CRITICAL: Also refresh chunks pagination controller to display chunks in right panel
            // Use addPostFrameCallback to ensure UI is updated before refreshing chunks pagination
            WidgetsBinding.instance.addPostFrameCallback((_) async {
              if (!mounted) return;

              if (kDebugMode) {
                _log(
                  '[ExtractPreview] PostFrameCallback: Refreshing chunks pagination controller, allChunks=${allChunks.length}',
                  level: LogLevel.info,
                );
              }

              await chunksPaginationController.loadFirstPage();

              if (kDebugMode && mounted) {
                _log(
                  '[ExtractPreview] Chunks pagination refreshed: items=${chunksPaginationController.items.length}, total=${chunksPaginationController.total}',
                  level: LogLevel.info,
                );
              }
            });
          } else {
            // Preview not ready yet - check if this is a terminal state
            // (backend completed but preview failed, e.g., WPS format file)
            final Map<String, dynamic> statusCheck =
                await svc.getStatus(widget.taskId);
            final String statusText = (statusCheck['status'] ?? '').toString();
            final String statusLower = statusText.toLowerCase();
            final int progress =
                (statusCheck['progress'] as num?)?.toInt() ?? 0;
            final Map<String, dynamic>? sourcePreviewCheck =
                statusCheck['source_preview'] as Map<String, dynamic>?;
            final bool previewReadyCheck = sourcePreviewCheck?['ready'] == true;
            final String? errorMessageCheck = statusCheck['error']?.toString();
            final String messageCheck =
                statusCheck['message']?.toString() ?? '';

            // If backend reports completion but preview is still not ready and we have no segments,
            // this is a terminal state (file format issue, e.g., WPS format)
            if (statusLower == 'completed' &&
                progress >= 100 &&
                !previewReadyCheck &&
                allSegments.isEmpty) {
              // Build a more informative error message
              String combinedMessage;
              if (errorMessageCheck?.isNotEmpty ?? false) {
                combinedMessage = errorMessageCheck!;
              } else {
                // Check if filename suggests WPS format
                final String? originalFilename =
                    statusCheck['original_filename']?.toString();
                final bool isWpsFile = originalFilename != null &&
                    (originalFilename.toLowerCase().contains('_wps.') ||
                        originalFilename.toLowerCase().contains('.wps'));

                if (isWpsFile) {
                  combinedMessage =
                      'Failed to extract segments from file. This appears to be a WPS format file (.wps.docx), which is not supported. Please convert the file to standard DOCX format using Microsoft Word or another compatible application.';
                } else if (messageCheck.isNotEmpty &&
                    messageCheck.toLowerCase() !=
                        'format conversion completed successfully') {
                  // Use message if it's not the generic success message
                  combinedMessage = 'Failed to extract segments: $messageCheck';
                } else {
                  // Generic error message
                  combinedMessage =
                      'Failed to extract segments from file. The file may be corrupted, encrypted by a third-party system, '
                      'in an unsupported format (e.g., WPS format), or incompatible with the extraction process. '
                      'Please try converting the file to a standard format (e.g., standard DOCX) and try again. '
                      'If the problem persists, please contact the developer.';
                }
              }

              _log(
                '[ExtractPreview] _loadInitialData detected terminal state (completed but preview not ready): $combinedMessage',
                level: LogLevel.warn,
              );
              if (mounted) {
                setState(() {
                  isPreparing = false;
                  initialDataLoaded = true;
                  prepareProgress = 0.0;
                  prepareStatus = '';
                  prepareErrorMessage = combinedMessage;
                });
                MessageService.showError(context, combinedMessage);
              }
              return; // Stop loading - terminal state detected
            }

            // Preview not ready yet, will be loaded by polling
            if (kDebugMode) {
              _log(
                '[ExtractPreview] Source-preview not ready yet, will continue polling',
              );
            }
          }
        } catch (e) {
          if (kDebugMode) {
            _log(
              '[ExtractPreview] Failed to load source-preview: $e',
            );
          }
          if (mounted) {
            setState(() {
              initialDataLoaded = true;
              isPreparing = false;
              prepareErrorMessage = 'Failed to load preview: $e';
            });
          }
        }
      }
    } catch (e) {
      if (kDebugMode) {
        _log('[ExtractPreview] Error loading initial data: $e');
      }
      if (mounted) {
        setState(() {
          initialDataLoaded = true;
          isPreparing = false;
          prepareErrorMessage = 'Failed to load data: $e';
        });
      }
    }
  }

  // Moved to ExtractPreviewProgressMixin.handleCancelExtraction()
  Future<void> _handleCancelExtraction() async => handleCancelExtraction();

  // Moved to ExtractPreviewProgressMixin.startPreparePolling()
  void _startPreparePolling() => startPreparePolling();

  // Public method for Mixin to call _loadInitialData
  // This is needed because private methods cannot be accessed via dynamic calls
  Future<void> loadInitialDataForMixin({bool forceReload = false}) async =>
      _loadInitialData(forceReload: forceReload);

  Widget _buildToolbar() {

    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor,
          ),
        ),
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 4,
      ), // Adjusted padding to achieve 36px total height
      constraints: const BoxConstraints(
        minHeight: 36,
        maxHeight: 36,
      ), // Fixed height at 36px
      child: Row(
        children: <Widget>[
          Icon(
            Icons.segment,
            size: 16, // Further reduced from 18 to 16
            color: Colors.green.shade700,
          ),
          const SizedBox(width: 4), // Further reduced spacing
          Text(
            'Extract',
            style: TextStyle(
              fontSize: 13, // Further reduced from 15 to 13
              fontWeight: FontWeight.bold,
              color: Colors.green.shade700,
            ),
          ),
          const SizedBox(width: 6), // Further reduced spacing
          // Show chunk count instead of chunk size and input tokens
          Builder(
            builder: (BuildContext context) {
              if (initialDataLoaded && !isPreparing && allChunks.isNotEmpty) {
                return Text(
                  'Chunks: ${allChunks.length}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                        fontSize: 10, // Further reduced from 11 to 10
                      ),
                );
              } else {
                return const SizedBox.shrink();
              }
            },
          ),
          const SizedBox(width: 12),
          // Filter buttons (shown only when data is loaded, hidden during preparation)
          if (initialDataLoaded && !isPreparing && allSegments.isNotEmpty)
            Consumer(
              builder: (context, ref, child) {
                // Get excluded segments from provider
                final String providerKey = widget.flowId ?? widget.taskId;
                final Set<int> excludedSegments = ref.watch(
                  excludedSegmentsProviderFamily(providerKey),
                );
                final int excludedCount = excludedSegments.length;
                final int totalSegments = allSegments.length;

                final l10n = AppLocalizations.of(context)!;
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    // All button (compact - only show count)
                    _buildCompactFilterButton(
                      context: context,
                      label: l10n.translationToolbarFilterAll,
                      count: totalSegments,
                      isSelected: selectedExclusionFilters.isEmpty,
                      onTap: () {
                        // CRITICAL: Use addPostFrameCallback to avoid setState during layout
                        WidgetsBinding.instance.addPostFrameCallback((_) {
                          if (!mounted) return;
                          setState(() {
                            selectedExclusionFilters = <String>{};
                          });
                          // PERFORMANCE: Clear cache and update immediately
                          clearFilteredCountCache();
                          _updatePaginationForFilters();
                          paginationController.loadFirstPage();
                        });
                      },
                      color: Colors.blue,
                    ),
                    const SizedBox(width: 3),
                    // Included button (compact - only show count)
                    _buildCompactFilterButton(
                      context: context,
                      label: l10n.translationToolbarFilterIncluded,
                      count: totalSegments - excludedCount,
                      isSelected: selectedExclusionFilters.contains('included'),
                      onTap: () {
                        // CRITICAL: Use addPostFrameCallback to avoid setState during layout
                        WidgetsBinding.instance.addPostFrameCallback((_) {
                          if (!mounted) return;
                          setState(() {
                            selectedExclusionFilters = <String>{'included'};
                          });
                          // PERFORMANCE: Clear cache and update immediately
                          clearFilteredCountCache();
                          _updatePaginationForFilters();
                          paginationController.loadFirstPage();
                        });
                      },
                      color: Colors.green,
                    ),
                    const SizedBox(width: 3),
                    // All Excluded button (compact - only show count)
                    _buildCompactFilterButton(
                      context: context,
                      label: l10n.translationToolbarFilterExcluded,
                      count: excludedCount,
                      isSelected:
                          selectedExclusionFilters.contains('all_excluded'),
                      onTap: () {
                        // CRITICAL: Use addPostFrameCallback to avoid setState during layout
                        WidgetsBinding.instance.addPostFrameCallback((_) {
                          if (!mounted) return;
                          setState(() {
                            selectedExclusionFilters = <String>{'all_excluded'};
                          });
                          // PERFORMANCE: Clear cache and update immediately
                          clearFilteredCountCache();
                          _updatePaginationForFilters();
                          paginationController.loadFirstPage();
                        });
                      },
                      color: Colors.red,
                    ),
                  ],
                );
              },
            ),
          const SizedBox(width: 8), // Spacing after filter buttons
          // Pagination bar and page size selector (placed right after filter buttons)
          if (initialDataLoaded && !isPreparing && allSegments.isNotEmpty)
            ListenableBuilder(
              listenable: paginationController,
              builder: (BuildContext context, _) => Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  // Pagination bar
                  PaginationBar(
                    currentPage: paginationController.currentPage,
                    totalPages: paginationController.totalPages,
                    hasPrev: paginationController.hasPrev,
                    hasNext: paginationController.hasMore,
                    onPrevPage: paginationController.isLoading
                        ? null
                        : paginationController.loadPrevPage,
                    onNextPage: paginationController.isLoading
                        ? null
                        : paginationController.loadNextPage,
                    onJumpToPage: paginationController.isLoading
                        ? null
                        : paginationController.jumpToPage,
                    showPageJump: false,
                    height: 28, // Compact height to match toolbar
                  ),
                  const SizedBox(width: 8),
                  // Page size selector
                  PageSizeSelector(
                    currentPageSize: paginationController.pageSize,
                    onPageSizeChanged: (int size) =>
                        paginationController.setPageSize(size),
                    preferenceKey: 'extract_preview_segments_page_size',
                    pageSizeOptions: const <int>[50, 100, 200, 500, 1000, 2000],
                    showLabel: false, // Hide label to save space in toolbar
                  ),
                ],
              ),
            ),
          // Progress info and Cancel button (shown when preparing Extract phase)
          if (isPreparing && !isTranslating) ...<Widget>[
            const SizedBox(width: 12),
            Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: <Widget>[
                // Progress bar is placed FIRST so its position never shifts
                // when surrounding text changes.
                SizedBox(
                  width: 200,
                  height: 4, // Reduced from default to 4
                  child: LinearProgressIndicator(
                    value: prepareProgress == 0.0 ? null : prepareProgress,
                    backgroundColor: Colors.grey.shade300,
                    valueColor: AlwaysStoppedAnimation<Color>(
                      Colors.green.shade700,
                    ),
                    minHeight: 4, // Reduced from 6 to 4
                  ),
                ),
                const SizedBox(width: 4), // Further reduced spacing
                // Cancel button placed right next to the progress bar
                OutlinedButton(
                  onPressed: _handleCancelExtraction,
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6, // Further reduced from 8
                      vertical: 2, // Further reduced from 4
                    ),
                    minimumSize: const Size(0, 28), // Increased button height
                  ),
                  child: Text(
                    AppLocalizations.of(context)!.extractToolbarCancel,
                    style: const TextStyle(fontSize: 10),
                  ), // Further reduced font size
                ),
                const SizedBox(width: 4), // Further reduced spacing
                Text(
                  prepareProgress > 0 ? '${(prepareProgress * 100).toInt()}%' : '',
                  style: TextStyle(
                    fontSize: 10, // Further reduced from 11 to 10
                    fontWeight: FontWeight.w600,
                    color: Colors.green.shade700,
                  ),
                ),
                // Task type label (e.g., "Detect Identifier", "Detect Language")
                if (prepareTaskType.isNotEmpty) ...<Widget>[
                  const SizedBox(width: 6),
                  Text(
                    prepareTaskType,
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: Colors.green.shade700,
                    ),
                  ),
                ],
                // PDF split part label
                if (extractPdfPartCurrent > 0 && extractPdfPartTotal > 0) ...<Widget>[
                  const SizedBox(width: 6),
                  Text(
                    'Part $extractPdfPartCurrent/$extractPdfPartTotal',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: Colors.green.shade700,
                    ),
                  ),
                ],
                if (prepareStatus.isNotEmpty) ...<Widget>[
                  const SizedBox(width: 4), // Further reduced spacing
                  Flexible(
                    child: Text(
                      prepareStatus == 'Extraction cancelled'
                          ? AppLocalizations.of(context)!.extractExtractionCancelled
                          : prepareStatus,
                      style: TextStyle(
                        fontSize: 10, // Reduced from 11 to 10
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ],
            ),
          ],
          const Spacer(),
          // Segments statistics (moved to the right side for free expansion)
          if (initialDataLoaded && !isPreparing && allSegments.isNotEmpty)
            Flexible(
              child: ListenableBuilder(
                listenable: paginationController,
                builder: (BuildContext context, _) => Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Icon(
                      Icons.format_list_numbered,
                      size: 16,
                      color: Colors.blue.shade700,
                    ),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(
                        AppLocalizations.of(context)!.extractToolbarSegments(
                          paginationController.endIndex.toString(),
                          paginationController.startIndex.toString(),
                          paginationController.total.toString(),
                        ),
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: Colors.blue.shade700,
                          fontSize: 10,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(width: 12),
          // Search button (shown when data is loaded)
          if (initialDataLoaded && !isPreparing && allSegments.isNotEmpty)
            IconButton(
              icon: Icon(
                isSearchBoxVisible ? Icons.search_off : Icons.search,
                size: 16,
              ),
              tooltip: AppLocalizations.of(context)!.translationToolbarSearchTooltip,
              onPressed: () {
                // CRITICAL: Use addPostFrameCallback to avoid setState during layout
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (!mounted) return;
                  setState(() {
                    isSearchBoxVisible = !isSearchBoxVisible;
                    if (!isSearchBoxVisible) {
                      // Clear search when closing
                      searchQuery = '';
                      searchMatchIndices.clear();
                      currentSearchMatchIndex = 0;
                    }
                  });
                });
              },
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(
                minWidth: 28,
                minHeight: 28,
              ),
            ),
          // Translation progress bar (shown when translating)
          if (isTranslating) ...<Widget>[
            const SizedBox(width: 6), // Further reduced spacing
            Flexible(
              child: SizedBox(
                height: 4, // Reduced from default to 4
                child: LinearProgressIndicator(
                  value:
                      translationProgress == 0.0 ? null : translationProgress,
                  backgroundColor: Colors.grey.shade300,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    Colors.blue
                        .shade700, // Use blue for translation to distinguish from Extract (green)
                  ),
                  minHeight: 4, // Reduced from 6 to 4
                ),
              ),
            ),
            const SizedBox(width: 4), // Further reduced spacing
            Text(
              translationProgress > 0
                  ? '${(translationProgress * 100).toInt()}%'
                  : '',
              style: TextStyle(
                fontSize: 10, // Further reduced from 11 to 10
                fontWeight: FontWeight.w600,
                color: Colors.blue.shade700, // Use blue for translation
              ),
            ),
            if (translationStatus.isNotEmpty) ...<Widget>[
              const SizedBox(width: 4), // Further reduced spacing
              Flexible(
                child: Text(
                  translationStatus,
                  style: TextStyle(
                    fontSize: 10, // Reduced from 11 to 10
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }

  /// Build a compact filter button for the toolbar (simplified text, minimal margins)
  Widget _buildCompactFilterButton({
    required BuildContext context,
    required String label,
    required int count,
    required bool isSelected,
    required VoidCallback onTap,
    required MaterialColor color,
  }) =>
      Tooltip(
        message: '$label ($count)',
        child: ActionChip(
          label: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (isSelected)
                Icon(
                  Icons.check,
                  size: 12, // Smaller checkmark icon
                  color: color.shade700,
                ),
              if (isSelected) const SizedBox(width: 2),
              Text(
                '$label ($count)', // Show label with count
                style: TextStyle(
                  fontSize: 10,
                  color: isSelected ? color.shade700 : Colors.grey.shade700,
                ),
                // Remove overflow ellipsis to allow full text display when space is available
                // ActionChip will handle overflow naturally if space is truly limited
              ),
            ],
          ),
          onPressed: onTap,
          backgroundColor: isSelected ? color.shade100 : Colors.grey.shade200,
          // Explicit stadium shape: compact chips + small icons otherwise look almost square.
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(999),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: 6,
            vertical: 2,
          ),
          visualDensity: VisualDensity.compact,
          side: BorderSide(
            color: isSelected ? color.shade300 : Colors.grey.shade400,
          ),
        ),
      );

  /// Build error message display (shown below toolbar)
  Widget _buildErrorMessage() {
    if (prepareErrorMessage.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(8), // Reduced padding
      margin: const EdgeInsets.only(top: 4), // Reduced margin
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.red.shade100),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(
            Icons.error_outline,
            color: Colors.red.shade700,
            size: 16, // Reduced icon size
          ),
          const SizedBox(width: 6), // Reduced spacing
          Expanded(
            child: SelectableText(
              prepareErrorMessage,
              style: TextStyle(
                fontSize: 11, // Reduced font size
                color: Colors.red.shade800,
                height: 1.3,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Calculate excluded segments count
  // Moved to ExtractPreviewExclusionHandlerMixin.calculateExcludedCount()
  int _calculateExcludedCount() => calculateExcludedCount();

  // Moved to ExtractPreviewExclusionHandlerMixin.matchesFilter()
  bool _matchesFilter(int index, Set<int> excludedSegments) =>
      matchesFilter(index, excludedSegments);

  // Moved to ExtractPreviewExclusionHandlerMixin.getFilteredSegmentIndices()
  List<int> _getFilteredSegmentIndices() => getFilteredSegmentIndices();

  // Moved to ExtractPreviewExclusionHandlerMixin.calculateFilteredSegmentCount()
  int _calculateFilteredSegmentCount() => calculateFilteredSegmentCount();

  /// Update pagination controller when filters change
  void _updatePaginationForFilters() {
    if (!mounted) return;

    final int filteredCount = _calculateFilteredSegmentCount();
    final int currentTotal = paginationController.total;

    // Only update if count changed
    if (filteredCount != currentTotal) {
      _log(
        '[ExtractPreview] Updating pagination total: $currentTotal -> $filteredCount (mode: $filterMode, filters: $selectedExclusionFilters)',
        level: LogLevel.info,
      );

      // Reset to first page when filters change
      // Note: loadFirstPage() is called by the caller after this method
      // to ensure proper sequencing
    }
  }

  // Moved to ExtractPreviewExclusionHandlerMixin.updatePaginationForFilterMode()
  void _updatePaginationForFilterMode() {
    _log(
      '[ExtractPreview] Filter mode changed to: $filterMode',
      level: LogLevel.info,
    );
    updatePaginationForFilterMode();
  }

  // Moved to ExtractPreviewExclusionHandlerMixin.calculateExclusionCounts()
  Map<String, int> _calculateExclusionCounts() => calculateExclusionCounts();

  // Moved to ExtractPreviewExclusionHandlerMixin.getCategoryExclusionStates()
  // Pass exclusionDefaults from config so 0-count categories (e.g. Language Match) get correct checkbox default
  Map<String, bool> _getCategoryExclusionStates(Set<int> excludedSegments) =>
      getCategoryExclusionStates(
        excludedSegments,
        exclusionDefaults: ref.read(globalSettingsProvider).exclusionDefaults,
      );

  /// Handle category exclusion state change from panel
  /// Wrapper method that handles logging and structural case, then delegates to Mixin
  Future<void> _handleCategoryExclusionChanged(
    String category,
    bool exclude,
  ) async {
    _log(
      '[ExtractPreview] Exclusion checkbox clicked: category=$category, exclude=$exclude, '
      'taskId=${widget.taskId}',
      level: LogLevel.info,
    );

    // Serialize exclusion operations to prevent race conditions:
    // if a previous batch exclude/unexclude is still in-flight, do not allow
    // another exclusion checkbox change to start.
    final String exclusionKey = widget.flowId ?? widget.taskId;
    final int exclusionInFlight =
        ref.read(exclusionUpdateInFlightProviderFamily(exclusionKey));
    if (exclusionInFlight > 0) {
      MessageService.showWarning(
        context,
        '排除/取消排除正在更新中，请稍后再进行下一次操作。',
      );
      return;
    }

    // Handle structural case separately (uses methods not yet moved to Mixin)
    if (category == 'structural') {
      // Toggle both headers and footers together
      if (headerSegmentIndices.isNotEmpty) {
        await _applyExcludeHeadersState(exclude);
        setState(() {
          excludeHeaders = exclude;
        });
      }
      if (footerSegmentIndices.isNotEmpty) {
        await _applyExcludeFootersState(exclude);
        setState(() {
          excludeFooters = exclude;
        });
      }
      setState(() {
        categoryExclusionStates['structural'] = exclude;
      });
      return;
    }

    // Delegate other cases to Mixin method
    await handleCategoryExclusionChanged(category, exclude);

    // Add logging for specific cases (Mixin doesn't have access to _log)
    switch (category) {
      case 'language_match':
        final int languageMatchedCount =
            languageMatchedSegmentIndices.isNotEmpty
                ? languageMatchedSegmentIndices.length
                : languageMatchedSegmentCount;
        if (languageMatchedCount > 0) {
          _log(
            '[ExtractPreview] Language match exclusion checkbox updated: exclude=$exclude, '
            'languageMatchedCount=$languageMatchedCount, '
            'languageMatchedIndicesCount=${languageMatchedSegmentIndices.length}, '
            'storedCount=$languageMatchedSegmentCount',
            level: LogLevel.info,
          );
        } else {
          _log(
            '[ExtractPreview] Language match exclusion checkbox clicked but no language-matched segments found '
            '(indices: ${languageMatchedSegmentIndices.length}, storedCount: $languageMatchedSegmentCount)',
            level: LogLevel.warn,
          );
        }
        break;
      case 'identifier':
        _log(
          '[ExtractPreview] Identifier exclusion checkbox updated: exclude=$exclude, '
          'identifierSegmentCount=${identifierSegmentIndices.length}',
          level: LogLevel.info,
        );
        break;
      case 'table':
        _log(
          '[ExtractPreview] Table exclusion checkbox updated: exclude=$exclude, '
          'tableSegmentCount=${tableSegmentIndices.length}',
          level: LogLevel.info,
        );
        break;
      case 'user_selected':
        _log(
          '[ExtractPreview] User selected exclusion checkbox updated: exclude=$exclude, '
          'userSelectedSegmentCount=${userSelectedSegmentIndices.length}',
          level: LogLevel.info,
        );
        break;
    }
  }

  /// Exclude all segments (user exclusion for any not already excluded by category).
  Future<void> _handleExcludeAll() async {
    final String providerKey = widget.flowId ?? widget.taskId;
    try {
      final Map<String, dynamic> result =
          await TranslationService().excludeAllSegments(widget.taskId);
      if (!mounted) return;
      final bool success = result['success'] as bool? ?? false;
      if (!success) {
        MessageService.showError(
          context,
          result['message'] as String? ?? 'Failed to exclude all segments',
        );
        return;
      }
      final List<dynamic> raw =
          (result['excluded_segment_indices'] as List<dynamic>?) ?? <dynamic>[];
      final Set<int> indices =
          raw.map((e) => (e is int) ? e : (e as num).toInt()).toSet();
      ref.read(excludedSegmentsProviderFamily(providerKey).notifier).setExcluded(indices);
      final int? totalSegments = result['total_segments'] is int
          ? result['total_segments'] as int
          : (result['total'] is int ? result['total'] as int : null);
      if (totalSegments != null &&
          totalSegments > 0 &&
          indices.length >= totalSegments) {
        final l10n = AppLocalizations.of(context)!;
        MessageService.showInfo(
          context,
          l10n.translationSnackAllSegmentsExcludedSkipped,
        );
      }
      setState(() {});
      _log(
        '[ExtractPreview] Exclude All: ${indices.length} segments excluded',
        level: LogLevel.info,
      );
    } catch (e, st) {
      if (mounted) {
        MessageService.showError(context, 'Exclude All failed: $e');
      }
      _log('Exclude All error: $e\n$st', level: LogLevel.error);
    }
  }

  /// Restore exclusion state to what Extract completed with (content-based auto-detection).
  /// Clears user manual exclusions and one-click excludes, then triggers layout-extract to re-detect.
  Future<void> _handleRestoreAutoExclusion() async {
    final String providerKey = widget.flowId ?? widget.taskId;
    try {
      final Map<String, dynamic> result =
          await TranslationService().cancelUserExclusion(widget.taskId);
      if (!mounted) return;
      final bool success = result['success'] as bool? ?? false;
      if (!success) {
        MessageService.showError(
          context,
          result['message'] as String? ?? 'Failed to restore auto exclusion',
        );
        return;
      }
      final List<dynamic> raw =
          (result['excluded_segment_indices'] as List<dynamic>?) ?? <dynamic>[];
      final Set<int> indices = raw.map((e) => (e is int) ? e : (e as num).toInt()).toSet();
      ref.read(excludedSegmentsProviderFamily(providerKey).notifier).setExcluded(indices);
      setState(() {});
      _log(
        '[ExtractPreview] Restore Auto Exclusion: ${indices.length} segments excluded, triggering re-detect',
        level: LogLevel.info,
      );
      // CRITICAL: Trigger layout-extract to re-detect exclusions (user_unexcluded cleared on backend)
      if (mounted) await refreshChunks();
    } catch (e, st) {
      if (mounted) {
        MessageService.showError(context, 'Restore auto exclusion failed: $e');
      }
      _log('Restore auto exclusion error: $e\n$st', level: LogLevel.error);
    }
  }

  /// Clear all exclusions except image segments.
  Future<void> _handleClearAllExclusionsExceptImage() async {
    final String providerKey = widget.flowId ?? widget.taskId;
    try {
      final Map<String, dynamic> result =
          await TranslationService().clearAllExclusionsExceptImage(widget.taskId);
      if (!mounted) return;
      final bool success = result['success'] as bool? ?? false;
      if (!success) {
        MessageService.showError(
          context,
          result['message'] as String? ?? 'Failed to clear all exclusions',
        );
        return;
      }
      final List<dynamic> raw =
          (result['excluded_segment_indices'] as List<dynamic>?) ?? <dynamic>[];
      final Set<int> indices = raw.map((e) => (e is int) ? e : (e as num).toInt()).toSet();
      ref.read(excludedSegmentsProviderFamily(providerKey).notifier).setExcluded(indices);
      setState(() {});
      _log(
        '[ExtractPreview] Clear All Exclusions Except Image: ${indices.length} image segments still excluded',
        level: LogLevel.info,
      );
    } catch (e, st) {
      if (mounted) {
        MessageService.showError(context, 'Clear all exclusions failed: $e');
      }
      _log('Clear all exclusions error: $e\n$st', level: LogLevel.error);
    }
  }

  // Moved to ExtractPreviewExclusionHandlerMixin.handleExcludeTableSegments()
  Future<void> _handleExcludeTableSegments(bool exclude) async =>
      handleExcludeTableSegments(exclude);

  // Moved to ExtractPreviewExclusionHandlerMixin.handleExcludeIdentifierSegments()
  Future<void> _handleExcludeIdentifierSegments(bool exclude) async =>
      handleExcludeIdentifierSegments(exclude);

  // Moved to ExtractPreviewExclusionHandlerMixin.handleExcludeUserSelectedSegments()
  Future<void> _handleExcludeUserSelectedSegments(bool exclude) async =>
      handleExcludeUserSelectedSegments(exclude);

  // Moved to ExtractPreviewExclusionHandlerMixin.handleExcludeReferenceSegments()
  Future<void> _handleExcludeReferenceSegments(bool exclude) async =>
      handleExcludeReferenceSegments(exclude);

  String _formatTokenCount(int count) {
    if (count < 1000) return '$count';
    if (count < 1000000) return '${(count / 1000).toStringAsFixed(1)}K';
    return '${(count / 1000000).toStringAsFixed(1)}M';
  }

  /// Build language-based exclusion checkbox (unified style with Exclude References)
  Widget _buildLanguageExclusionButtons() {
    // Get current target language
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.watch(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.watch(translationQuickSettingsProvider);
    final String targetLang = qs.toLang;

    // CRITICAL: If target language changed, trigger re-detection and refresh
    if (currentTargetLangForExclusion != null &&
        currentTargetLangForExclusion != targetLang) {
      _log(
        '[ExtractPreview] Target language changed from $currentTargetLangForExclusion to $targetLang. '
        'Triggering re-detection and refresh.',
        level: LogLevel.info,
      );
      // CRITICAL: Trigger re-detection and refresh when target language changes
      // This ensures statistics and segment labels are updated with the new target language
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (mounted) {
          await _validateAndRefreshExclusionsForTargetLang(targetLang);
        }
      });
      // Update current target language immediately to prevent duplicate triggers
      currentTargetLangForExclusion = targetLang;
      // Reset state while re-detection is in progress
      isLanguageExclusionActive = false;
      languageMatchedSegmentCount = 0;
      return const SizedBox.shrink(); // Return empty widget while re-detecting
    }

    // Update current target language if not set
    currentTargetLangForExclusion ??= targetLang;

    // Check current state asynchronously
    _checkLanguageExclusionState(targetLang);

    // Only show if there are language-matched segments
    if (languageMatchedSegmentCount == 0) {
      return const SizedBox.shrink();
    }

    return Tooltip(
      message: isLanguageExclusionActive
          ? 'Clear language exclusion to include target language segments'
          : 'Exclude target language segments to save token consumption',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          SizedBox(
            width: 18, // Reduced checkbox size
            height: 18, // Reduced checkbox size
            child: Checkbox(
              value: isLanguageExclusionActive,
              onChanged: (value) {
                if (value != null) {
                  _log(
                    '[ExtractPreview] Checkbox clicked: language exclusion changed from $isLanguageExclusionActive to $value',
                    level: LogLevel.info,
                  );
                  _handleExcludeLanguageSegments(
                    targetLang,
                    value,
                  );
                }
              },
              materialTapTargetSize:
                  MaterialTapTargetSize.shrinkWrap, // Reduce tap target
            ),
          ),
          const SizedBox(width: 4),
          Text(
            'Exclude Target Language ($languageMatchedSegmentCount)',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  fontSize: 10, // Reduced font size
                ),
          ),
        ],
      ),
    );
  }

  // Moved to ExtractPreviewLanguageMatchMixin.validateAndRefreshExclusionsForTargetLang()
  Future<void> _validateAndRefreshExclusionsForTargetLang(
    String targetLang,
  ) async =>
      validateAndRefreshExclusionsForTargetLang(targetLang);

  // Moved to ExtractPreviewLanguageMatchMixin.reloadLayoutDataForTargetLang()
  Future<void> _reloadLayoutDataForTargetLang(String targetLang) async =>
      reloadLayoutDataForTargetLang(targetLang);

  // Moved to ExtractPreviewLanguageMatchMixin.reloadSourcePreviewDataForTargetLang()
  Future<void> _reloadSourcePreviewDataForTargetLang(String targetLang) async =>
      reloadSourcePreviewDataForTargetLang(targetLang);

  // Moved to ExtractPreviewLanguageMatchMixin.checkLanguageExclusionState()
  Future<void> _checkLanguageExclusionState(String targetLang) async =>
      checkLanguageExclusionState(targetLang);

  /// Handle exclude/clear language segments
  // Moved to ExtractPreviewExclusionHandlerMixin.handleExcludeLanguageSegments()
  Future<void> _handleExcludeLanguageSegments(
    String targetLang,
    bool exclude,
  ) async =>
      handleExcludeLanguageSegments(targetLang, exclude);

  // Moved to ExtractPreviewLanguageMatchMixin.setTotalTokens()
  void _setTotalTokens(int tokens, String source) =>
      setTotalTokens(tokens, source);

  @override
  Widget build(BuildContext context) {
    super.build(context); // Required for AutomaticKeepAliveClientMixin

    // CRITICAL: Watch target language changes to trigger re-detection and refresh
    final TranslationQuickSettings qs = widget.flowId != null
        ? ref.watch(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.watch(translationQuickSettingsProvider);
    final String currentTargetLang = qs.toLang;

    // CRITICAL: If target language changed and initial data is loaded, trigger re-detection
    if (initialDataLoaded &&
        currentTargetLangForExclusion != null &&
        currentTargetLangForExclusion != currentTargetLang) {
      _log(
        '[ExtractPreview] build() detected target language change from $currentTargetLangForExclusion to $currentTargetLang. '
        'Triggering re-detection and refresh.',
        level: LogLevel.info,
      );
      // Schedule re-detection after build completes
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (mounted && context.mounted) {
          await _validateAndRefreshExclusionsForTargetLang(currentTargetLang);
        }
      });
    }

    // Watch translation operation to clear error message immediately when Re-extract starts.
    // Global translationStateProvider (TranslationState) has no currentOperation; only flow-scoped family does.
    final TranslationOperation currentOperation = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!).select((s) => s.currentOperation))
        : TranslationOperation.none;
    if (currentOperation == TranslationOperation.extracting && prepareErrorMessage.isNotEmpty) {
      setState(() {
        prepareErrorMessage = '';
      });
    }

    // Watch refresh trigger to detect resplit completion
    final int refreshTrigger = ref.watch(extractRefreshProvider);
    if (lastRefreshTrigger != null && lastRefreshTrigger != refreshTrigger) {
      if (kDebugMode) {
        _log(
          '[ExtractPreview] build() detected refresh trigger change from $lastRefreshTrigger to $refreshTrigger, scheduling refresh',
        );
      }
      // Schedule refresh after build completes
      // Use a small delay to ensure context is fully initialized
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && context.mounted) {
          Future.delayed(const Duration(milliseconds: 100), () {
            if (mounted && context.mounted) {
              refreshChunks();
            }
          });
        }
      });
    }
    lastRefreshTrigger = refreshTrigger;


    // CRITICAL: Watch workflowId to detect when translation starts
    // When translation starts (workflowId becomes available), stop Extract phase polling
    // and start translation progress polling
    // This is the CORRECT way: detect translation start proactively, not reactively via Extract polling
    String? currentWorkflowId;
    if (widget.flowId != null) {
      try {
        final FlowStateModel flow =
            ref.watch(flowProviderFamily(widget.flowId!));
        currentWorkflowId = flow.context.anonymize.workflowId;

        // Log workflowId status for debugging
        if (currentWorkflowId != null && currentWorkflowId.isNotEmpty) {
          _log(
            '[ExtractPreview] build() watching workflowId: $currentWorkflowId, currentPollingWorkflowId=$currentPollingWorkflowId, prepareTimer=${prepareTimer != null}, isTranslating=$isTranslating',
            level: LogLevel.info,
          );
        }

        // Check if workflowId just became available (translation started) and we haven't started translation polling yet
        // CRITICAL: Only trigger if workflowId exists, is not empty, and we're not already polling for it.
        // currentTranslationTaskId != currentWorkflowId means: no task polled yet, or a NEW task (e.g. second Translate All/Retry).
        // For the same task we do not re-enter (prevents infinite loop). For a new task we must start polling so the progress bar shows again.
        if (currentWorkflowId != null &&
            currentWorkflowId.isNotEmpty &&
            currentTranslationTaskId != currentWorkflowId) {
          // Translation just started (or new task) - stop Extract phase polling (if still running) and start translation progress polling
          _log(
            '[ExtractPreview] build() detected translation start: workflowId=$currentWorkflowId. Stopping Extract polling (if running) and starting translation progress polling.',
            level: LogLevel.info,
          );

          // CRITICAL: Update currentTranslationTaskId IMMEDIATELY to prevent infinite loop
          // This must be done BEFORE addPostFrameCallback to prevent multiple triggers
          currentTranslationTaskId = currentWorkflowId;

          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              // Stop Extract phase polling (no longer needed once translation starts)
              prepareTimer?.cancel();
              prepareTimer = null;
              prepareInFlight = false;

              // Update UI state
              final double oldTranslationProgress = translationProgress;
              final double oldPrepareProgress = prepareProgress;
              setState(() {
                isTranslating = true;
                translationProgress =
                    0.1; // Start at 10% (translation starts at 10%)
                translationStatus = 'Translating...';
                isPreparing = false;
                prepareProgress = 1.0;
                prepareStatus = 'Extract Complete';
                initialDataLoaded =
                    true; // Mark as loaded so Extract polling won't restart
                isExclusionPanelExpanded =
                    true; // Default to expanded in Extract phase
              });

              // Sync translationStateProvider so translation result toolbar progress bar shows (e.g. on second Translate All/Retry)
              if (widget.flowId != null) {
                final translationNotifier = ref
                    .read(translationStateProviderFamily(widget.flowId!).notifier);
                translationNotifier.setTranslating(true);
                translationNotifier.setProgress(10);
                translationNotifier.setStatusText('processing');
              }

              // Log progress change
              if ((oldTranslationProgress * 100).round() != 10) {
                _log(
                  '[ExtractPreview] Progress changed: translationProgress ${(oldTranslationProgress * 100).toStringAsFixed(1)}% -> 10.0% (translation started, workflowId=$currentWorkflowId)',
                  level: LogLevel.info,
                );
              }
              if ((oldPrepareProgress * 100).round() != 100) {
                _log(
                  '[ExtractPreview] Progress changed: prepareProgress ${(oldPrepareProgress * 100).toStringAsFixed(1)}% -> 100.0% (Extract complete)',
                  level: LogLevel.info,
                );
              }

              // CRITICAL: Start INDEPENDENT translation polling (not Extract polling)
              // Translation uses /service/status/{taskId} but with its own timer
              // currentWorkflowId is guaranteed to be non-null here due to the if condition above
              _log(
                '[ExtractPreview] Translation started (workflowId=$currentWorkflowId). Starting independent translation polling.',
                level: LogLevel.info,
              );
              startTranslationPolling(currentWorkflowId!);
            }
          });
        }
      } catch (e) {
        // Flow context not available yet, ignore
        if (kDebugMode) {
          _log(
            '[ExtractPreview] build() failed to watch workflowId: $e',
          );
        }
      }
    }

    return Stack(
      children: <Widget>[
        // Use Positioned.fill to ensure Column takes all available space in Stack
        Positioned.fill(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
            // Toolbar
            _buildToolbar(),
            // Error message (if any)
            _buildErrorMessage(),
            // Content
            // Use LayoutBuilder to detect view size changes and trigger height measurement
            Expanded(
              child: LayoutBuilder(
                builder: (BuildContext context, BoxConstraints constraints) {
                  // CRITICAL: Avoid any state changes or side effects during layout
                  // Only read constraints and return widget tree
                  final currentSize =
                      Size(constraints.maxWidth, constraints.maxHeight);

                  // CRITICAL: Avoid any state mutations during layout
                  // Only read constraints and compare with lastViewSize (read-only operation)
                  // Schedule all state changes AFTER layout completes
                  final bool sizeChanged =
                      lastViewSize != null && lastViewSize != currentSize;
                  final bool isFirstTime = lastViewSize == null;

                  if (sizeChanged || isFirstTime) {
                    // View size changed or first time, schedule height recalculation AFTER layout completes
                    final actualWidth = constraints.maxWidth;
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (mounted) {
                        // Update lastViewSize first to prevent duplicate callbacks
                        lastViewSize = currentSize;
                        // Clear filtered count cache when UI size changes (may affect pagination)
                        clearFilteredCountCache();
                        // Then trigger height recalculation
                        if (segmentsScrollManager != null) {
                          _precalculateAllHeights(actualWidth);
                        }
                      }
                    });
                  }

                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      // Left: Segments (Deep split fragments, same as Translate's Source Text)
                      Expanded(
                        flex: 2, // Left panel takes 2/3 of the width
                        child: Card(
                          elevation: 2,
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                // Content list (header controls moved to toolbar)
                                Expanded(
                                  child:
                                      paginationController.isLoading &&
                                              paginationController.items.isEmpty
                                          ? const Center(
                                              child: CircularProgressIndicator(
                                                strokeWidth: 2,
                                              ),
                                            )
                                          : paginationController.error != null
                                              ? Center(
                                                  child: Column(
                                                    mainAxisAlignment:
                                                        MainAxisAlignment
                                                            .center,
                                                    children: <Widget>[
                                                      Text(
                                                        AppLocalizations.of(context)!.extractErrorLabel(
                                                          paginationController.error ?? '',
                                                        ),
                                                        style: const TextStyle(
                                                          color: Colors.red,
                                                        ),
                                                      ),
                                                      const SizedBox(height: 8),
                                                      ElevatedButton(
                                                        onPressed: () =>
                                                            paginationController
                                                                .refresh(),
                                                        child: Text(
                                                          AppLocalizations.of(context)!.extractRetry,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                )
                                              : Consumer(
                                                  builder: (
                                                    BuildContext context,
                                                    WidgetRef ref,
                                                    Widget? child,
                                                  ) {
                                                    // CRITICAL: Use Consumer to ensure ListView rebuilds when excludedSegmentsProviderFamily changes
                                                    final String providerKey =
                                                        widget.flowId ??
                                                            widget.taskId;
                                                    final Set<int> excludedSegments =
                                                        ref.watch(
                                                      excludedSegmentsProviderFamily(
                                                        providerKey,
                                                      ),
                                                    );

                                                    // Use standard ListView with pixel-based scrolling
                                                    final itemCount =
                                                        paginationController
                                                            .items.length;
                                                    // Log itemCount changes to track if ListView itemCount is causing maxScrollExtent changes
                                                    if (kDebugMode &&
                                                        lastListViewItemCount !=
                                                            null &&
                                                        lastListViewItemCount !=
                                                            itemCount) {
                                                      _log(
                                                        'ListView itemCount changed: $lastListViewItemCount -> $itemCount (offset=${paginationController.offset}, total=${paginationController.total})',
                                                        level: LogLevel.warn,
                                                      );
                                                    }
                                                    lastListViewItemCount =
                                                        itemCount;

                                                    // Use PaginatedSliverList for optimized scrolling
                                                    // This prevents maxScrollExtent from fluctuating during scrolling
                                                    // CRITICAL: Use filtered segment count when filters are active
                                                    // This ensures pagination shows correct total pages for filtered segments
                                                    final int totalItems =
                                                        _calculateFilteredSegmentCount();
                                                    return PaginatedSliverList<
                                                        String>(
                                                      paginationController:
                                                          paginationController,
                                                      heightCache:
                                                          segmentsHeightCache!,
                                                      scrollController:
                                                          segmentsScrollController,
                                                      totalItems: totalItems,
                                                      itemKeys: segmentKeys,
                                                      itemBuilder: (
                                                        BuildContext context,
                                                        int i,
                                                        String item,
                                                        GlobalKey<State<StatefulWidget>> itemKey,
                                                      ) {
                                                        final int buildStartTime =
                                                            DateTime.now()
                                                                .millisecondsSinceEpoch;

                                                        // Calculate globalIndex based on filter mode
                                                        int globalIndex;
                                                        if (filterMode ==
                                                                'rebuild' &&
                                                            selectedExclusionFilters
                                                                .isNotEmpty &&
                                                            filteredSegmentIndices !=
                                                                null) {
                                                          // Rebuild mode: use filtered indices
                                                          final int filteredOffset =
                                                              paginationController
                                                                  .offset;
                                                          final filteredIndices =
                                                              filteredSegmentIndices!;
                                                          if (filteredOffset +
                                                                  i <
                                                              filteredIndices
                                                                  .length) {
                                                            globalIndex =
                                                                filteredIndices[
                                                                    filteredOffset +
                                                                        i];
                                                          } else {
                                                            // Fallback (should not happen)
                                                            globalIndex =
                                                                paginationController
                                                                        .offset +
                                                                    i;
                                                          }
                                                        } else {
                                                          // Page mode or no filters: use direct offset
                                                          globalIndex =
                                                              paginationController
                                                                      .offset +
                                                                  i;
                                                        }

                                                        // Get excluded segments from provider
                                                        // Use flowId if available, otherwise use taskId
                                                        // flowId is consistent across Extract and Translate, while taskId changes
                                                        final ExcludedSegmentsNotifier excludedNotifier =
                                                            ref.read(
                                                          excludedSegmentsProviderFamily(
                                                            providerKey,
                                                          ).notifier,
                                                        );
                                                        final bool isExcluded =
                                                            excludedSegments
                                                                .contains(
                                                          globalIndex,
                                                        );

                                                        // Apply filter: only for page mode
                                                        // In rebuild mode, filtering is done in fetcher
                                                        if (filterMode ==
                                                                'page' &&
                                                            selectedExclusionFilters
                                                                .isNotEmpty) {
                                                          // Special case: "included" filter - show only included segments (will be translated)
                                                          if (selectedExclusionFilters
                                                              .contains(
                                                            'included',
                                                          )) {
                                                            if (isExcluded) {
                                                              return const SizedBox
                                                                  .shrink();
                                                            }
                                                          } else {
                                                            // Normal filter: show only segments matching selected types
                                                            // Use _matchesFilter helper method
                                                            if (!_matchesFilter(
                                                              globalIndex,
                                                              excludedSegments,
                                                            )) {
                                                              return const SizedBox
                                                                  .shrink();
                                                            }
                                                          }
                                                        }

                                                        // Excluded status is logged once when segments are loaded (see _loadInitialData)

                                                        // Items are already converted to strings in fetcher
                                                        // itemKey is provided by PaginatedSliverList for use by SegmentNumberedItem
                                                        final int buildEndTime =
                                                            DateTime.now()
                                                                .millisecondsSinceEpoch;
                                                        if (kDebugMode &&
                                                            buildEndTime -
                                                                    buildStartTime >
                                                                10) {
                                                          _log(
                                                            '[ExtractPreview] itemBuilder[$i]: slow build (duration=${buildEndTime - buildStartTime}ms, textLen=${item.length})',
                                                          );
                                                        }
                                                        // Return Column with SegmentNumberedItem and Divider
                                                        // The key will be set by PaginatedSliverList for height measurement
                                                        return Column(
                                                          mainAxisSize:
                                                              MainAxisSize.min,
                                                          children: <Widget>[
                                                            SegmentNumberedItem(
                                                              itemKey: itemKey,
                                                              text: item,
                                                              index:
                                                                  globalIndex,
                                                              isHighlighted: highlightedIndex ==
                                                                      i ||
                                                                  (searchMatchIndices
                                                                          .isNotEmpty &&
                                                                      currentSearchMatchIndex <
                                                                          searchMatchIndices
                                                                              .length &&
                                                                      searchMatchIndices[
                                                                              currentSearchMatchIndex] ==
                                                                          globalIndex),
                                                              onTap: () =>
                                                                  _highlightSegment(
                                                                i,
                                                              ),
                                                              badgeColor: Colors
                                                                  .blue.shade50,
                                                              badgeTextColor:
                                                                  Colors.blue
                                                                      .shade700,
                                                              imageDataMap:
                                                                  imageDataMap,
                                                              isExcluded:
                                                                  isExcluded,
                                                              exclusionReason:
                                                                  segmentExclusionReasons[
                                                                      globalIndex],
                                                              taskId:
                                                                  widget.taskId,
                                                              onExclude: (
                                                                int index,
                                                              ) async {
                                                                _log(
                                                                  '[ExtractPreview] onExclude called for segment $index',
                                                                  level:
                                                                      LogLevel
                                                                          .info,
                                                                );

                                                                // CRITICAL: Call API to update backend first (similar to unexclude)
                                                                if (widget
                                                                    .taskId
                                                                    .isNotEmpty) {
                                                                  try {
                                                                    _log(
                                                                      '[ExtractPreview] Calling updateExclusionReason API to exclude segment $index',
                                                                      level: LogLevel
                                                                          .info,
                                                                    );
                                                                    final TranslationService svc =
                                                                        TranslationService();
                                                                beginExclusionUpdate(
                                                                  ref,
                                                                  widget.flowId ??
                                                                      widget.taskId,
                                                                );
                                                                try {
                                                                  await svc
                                                                      .updateExclusionReason(
                                                                    widget
                                                                        .taskId,
                                                                    index,
                                                                    ExclusionReason
                                                                        .userSelected
                                                                        .value, // Set as user_selected
                                                                  );
                                                                } finally {
                                                                  endExclusionUpdate(
                                                                    ref,
                                                                    widget.flowId ??
                                                                        widget.taskId,
                                                                  );
                                                                }
                                                                    _log(
                                                                      '[ExtractPreview] Successfully excluded segment $index via API',
                                                                      level: LogLevel
                                                                          .info,
                                                                    );
                                                                  } catch (e) {
                                                                    _log(
                                                                      '[ExtractPreview] Failed to exclude segment $index via API: $e',
                                                                      level: LogLevel
                                                                          .warn,
                                                                    );
                                                                    if (mounted) {
                                                                      MessageService
                                                                          .showError(
                                                                        context,
                                                                        'Failed to exclude segment: $e',
                                                                      );
                                                                    }
                                                                    return; // Don't update local state if API call failed
                                                                  }
                                                                }

                                                                // Update local state AFTER API call succeeds
                                                                excludedNotifier
                                                                    .exclude(
                                                                  index,
                                                                );

                                                                // CRITICAL: Update local exclusion state immediately for UI update
                                                                // This ensures statistics are updated correctly
                                                                segmentExclusionReasons[
                                                                        index] =
                                                                    ExclusionReason
                                                                        .userSelected
                                                                        .value;
                                                                if (!userSelectedSegmentIndices
                                                                    .contains(
                                                                  index,
                                                                )) {
                                                                  userSelectedSegmentIndices
                                                                      .add(
                                                                    index,
                                                                  );
                                                                }

                                                                if (mounted) {
                                                                  // Update UI immediately to reflect exclusion state
                                                                  setState(
                                                                    () {},
                                                                  );

                                                                  MessageService
                                                                      .showInfo(
                                                                    context,
                                                                    'Segment excluded from translation',
                                                                  );

                                                                  // CRITICAL: Notify parent to reload data from backend
                                                                  // This ensures chunks are updated correctly when exclusion changes
                                                                  // Use the same callback pattern as onExclusionUpdated
                                                                  WidgetsBinding
                                                                      .instance
                                                                      .addPostFrameCallback(
                                                                          (_) async {
                                                                    if (!mounted) {
                                                                      return;
                                                                    }

                                                                    try {
                                                                      // Check if this is a PDF file - only PDF files support layout-extract API
                                                                      final TranslationService svc =
                                                                          TranslationService();
                                                                      final Map<String, dynamic> status =
                                                                          await svc
                                                                              .getStatus(widget.taskId);
                                                                      final String originalFilename =
                                                                          status['original_filename'] as String? ??
                                                                              '';
                                                                      final bool isPdfFile =
                                                                          originalFilename
                                                                              .toLowerCase()
                                                                              .endsWith('.pdf');

                                                                      if (isPdfFile) {
                                                                        // Get current chunk_size from global settings
                                                                        final GlobalSettings globalSettings =
                                                                            ref.read(globalSettingsProvider);

                                                                        // Get excluded segment indices from Flow-level state
                                                                        final List<int> excludedIndices = widget.flowId !=
                                                                                null
                                                                            ? ref.read(translationStateProviderFamily(widget.flowId!)).excludedSegmentIndices.toList()
                                                                            : <int>[];

                                                                        // Get target language from Quick Settings for language match detection
                                                                        final TranslationQuickSettings qs =
                                                                            widget.flowId != null
                                                                                ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
                                                                                : ref.read(translationQuickSettingsProvider);
                                                                        final String? targetLang =
                                                                            qs.toLang.isNotEmpty
                                                                                ? qs.toLang
                                                                                : null;

                                                                        _log(
                                                                          '[ExtractPreview] Reloading layout data after exclusion: taskId=${widget.taskId}, excludedIndices=${excludedIndices.length}, targetLang=$targetLang',
                                                                          level:
                                                                              LogLevel.info,
                                                                        );

                                                                        final TranslationService svc =
                                                                            TranslationService();
                                                                        final Map<String, dynamic> updatedLayoutData =
                                                                            await svc.getLayoutExtract(
                                                                          widget
                                                                              .taskId,
                                                                          excludedSegmentIndices:
                                                                              excludedIndices,
                                                                          targetLang:
                                                                              targetLang,
                                                                        );

                                                                        if (updatedLayoutData['ready'] ==
                                                                                true &&
                                                                            mounted) {
                                                                          // Parse and update segments
                                                                          final List<dynamic> segmentsData =
                                                                              updatedLayoutData['segments'] as List<dynamic>? ?? <dynamic>[];
                                                                          final List<String> updatedSegments =
                                                                              <String>[];
                                                                          segmentExclusionReasons
                                                                              .clear();
                                                                          segmentExclusionMetadata
                                                                              .clear();
                                                                          for (var i = 0;
                                                                              i < segmentsData.length;
                                                                              i++) {
                                                                            final seg =
                                                                                segmentsData[i];
                                                                            if (seg
                                                                                is Map) {
                                                                              final String? segmentText = seg['text'] as String?;
                                                                              if (segmentText != null) {
                                                                                updatedSegments.add(segmentText);
                                                                              } else {
                                                                                updatedSegments.add('');
                                                                              }

                                                                              final String? exclusionReason = seg['exclusion_reason'] as String?;
                                                                              if (exclusionReason != null) {
                                                                                segmentExclusionReasons[i] = exclusionReason;
                                                                              }

                                                                              final Map<String, dynamic>? exclusionMetadata = seg['exclusion_metadata'] as Map<String, dynamic>?;
                                                                              if (exclusionMetadata != null) {
                                                                                segmentExclusionMetadata[i] = exclusionMetadata;
                                                                              }
                                                                            } else {
                                                                              updatedSegments.add('');
                                                                            }
                                                                          }

                                                                          // Update excluded segments provider
                                                                          final String providerKey =
                                                                              widget.flowId ?? widget.taskId;
                                                                          final ExcludedSegmentsNotifier excludedNotifier =
                                                                              ref.read(excludedSegmentsProviderFamily(providerKey).notifier);
                                                                          final Set<int> updatedExcludedSet =
                                                                              <int>{};
                                                                          for (var i = 0;
                                                                              i < segmentsData.length;
                                                                              i++) {
                                                                            final seg =
                                                                                segmentsData[i];
                                                                            if (seg
                                                                                is Map) {
                                                                              final bool isExcluded = seg['is_excluded'] as bool? ?? false;
                                                                              if (isExcluded) {
                                                                                updatedExcludedSet.add(i);
                                                                              }
                                                                            }
                                                                          }
                                                                          excludedNotifier
                                                                              .setExcluded(updatedExcludedSet);

                                                                          // CRITICAL: Update allSegments and clear height cache
                                                                          // This ensures height calculations are correct after exclusion changes
                                                                          if (mounted) {
                                                                            setState(() {
                                                                              allSegments = updatedSegments;
                                                                              // Clear height cache to force recalculation
                                                                              if (segmentsHeightCache != null) {
                                                                                segmentsHeightCache!.clear();
                                                                              }
                                                                            });

                                                                            // Recalculate heights after state update
                                                                            WidgetsBinding.instance.addPostFrameCallback((_) {
                                                                              if (mounted && segmentsScrollManager != null) {
                                                                                _precalculateAllHeights();
                                                                              }
                                                                            });
                                                                          }

                                                                          // Refresh pagination
                                                                          paginationController
                                                                              .refresh();

                                                                          _log(
                                                                            '[ExtractPreview] Layout data reloaded after exclusion: ${segmentsData.length} segments, ${updatedExcludedSet.length} excluded, height cache cleared',
                                                                            level:
                                                                                LogLevel.info,
                                                                          );
                                                                        }
                                                                      } else {
                                                                        // For non-PDF files (XLSX, DOCX, etc.), reload source-preview data
                                                                        // to update exclusion reasons and statistics
                                                                        _log(
                                                                          '[ExtractPreview] Non-PDF file ($originalFilename), reloading source-preview data to update exclusion state.',
                                                                          level:
                                                                              LogLevel.info,
                                                                        );

                                                                        // Get target language from Quick Settings
                                                                        final TranslationQuickSettings qs =
                                                                            widget.flowId != null
                                                                                ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
                                                                                : ref.read(translationQuickSettingsProvider);
                                                                        final String? targetLang =
                                                                            qs.toLang.isNotEmpty
                                                                                ? qs.toLang
                                                                                : null;

                                                                        // Reload source-preview data to get updated exclusion state
                                                                        await _loadInitialData(
                                                                          forceReload:
                                                                              true,
                                                                        );

                                                                        _log(
                                                                          '[ExtractPreview] Source-preview data reloaded after exclusion: updated exclusion reasons and statistics',
                                                                          level:
                                                                              LogLevel.info,
                                                                        );
                                                                      }
                                                                    } catch (e) {
                                                                      _log(
                                                                        '[ExtractPreview] Failed to reload layout data after exclusion: $e',
                                                                        level: LogLevel
                                                                            .warn,
                                                                      );
                                                                    }
                                                                  });
                                                                }
                                                              },
                                                              onUnexclude:
                                                                  (int index) {
                                                                excludedNotifier
                                                                    .unexclude(
                                                                  index,
                                                                );
                                                                if (mounted) {
                                                                  MessageService
                                                                      .showInfo(
                                                                    context,
                                                                    'Segment unexcluded from translation',
                                                                  );
                                                                }
                                                              },
                                                              onExclusionUpdated:
                                                                  (
                                                                int index,
                                                              ) async {
                                                                // CRITICAL: Reload data from backend to ensure consistency
                                                                // This ensures chunks are updated correctly when exclusion changes
                                                                // Use addPostFrameCallback to avoid setState during layout
                                                                if (mounted) {
                                                                  WidgetsBinding
                                                                      .instance
                                                                      .addPostFrameCallback(
                                                                          (_) async {
                                                                    if (!mounted) {
                                                                      return;
                                                                    }

                                                                    try {
                                                                      // Check if this is a PDF file - only PDF files support layout-extract API
                                                                      final TranslationService svc =
                                                                          TranslationService();
                                                                      final Map<String, dynamic> status =
                                                                          await svc
                                                                              .getStatus(widget.taskId);
                                                                      final String originalFilename =
                                                                          status['original_filename'] as String? ??
                                                                              '';
                                                                      final bool isPdfFile =
                                                                          originalFilename
                                                                              .toLowerCase()
                                                                              .endsWith('.pdf');

                                                                      if (isPdfFile) {
                                                                        // Get current chunk_size from global settings
                                                                        final GlobalSettings globalSettings =
                                                                            ref.read(globalSettingsProvider);

                                                                        // Get excluded segment indices from Flow-level state
                                                                        final List<int> excludedIndices = widget.flowId !=
                                                                                null
                                                                            ? ref.read(translationStateProviderFamily(widget.flowId!)).excludedSegmentIndices.toList()
                                                                            : <int>[];

                                                                        // Get target language from Quick Settings for language match detection
                                                                        final TranslationQuickSettings qs =
                                                                            widget.flowId != null
                                                                                ? ref.read(translationQuickSettingsProviderFamily(widget.flowId!))
                                                                                : ref.read(translationQuickSettingsProvider);
                                                                        final String? targetLang =
                                                                            qs.toLang.isNotEmpty
                                                                                ? qs.toLang
                                                                                : null;

                                                                        // Reload data from backend
                                                                        final TranslationService svc =
                                                                            TranslationService();
                                                                        final Map<String, dynamic> updatedLayoutData =
                                                                            await svc.getLayoutExtract(
                                                                          widget
                                                                              .taskId,
                                                                          excludedSegmentIndices:
                                                                              excludedIndices,
                                                                          targetLang:
                                                                              targetLang,
                                                                        );

                                                                        if (!mounted) {
                                                                          return;
                                                                        }

                                                                        if (updatedLayoutData['ready'] ==
                                                                            true) {
                                                                          // Update segments and exclusion reasons
                                                                          final List<dynamic> segmentsData =
                                                                              updatedLayoutData['segments'] as List<dynamic>? ?? <dynamic>[];

                                                                          // Update exclusion reasons cache
                                                                          for (var i = 0;
                                                                              i < segmentsData.length;
                                                                              i++) {
                                                                            final seg =
                                                                                segmentsData[i];
                                                                            if (seg
                                                                                is Map) {
                                                                              final String? exclusionReason = seg['exclusion_reason'] as String?;
                                                                              if (exclusionReason != null) {
                                                                                segmentExclusionReasons[i] = exclusionReason;
                                                                                final dynamic exclusionMetadata = seg['exclusion_metadata'];
                                                                                if (exclusionMetadata is Map) {
                                                                                  segmentExclusionMetadata[i] = Map<String, dynamic>.from(exclusionMetadata);
                                                                                }
                                                                              } else {
                                                                                segmentExclusionReasons.remove(i);
                                                                                segmentExclusionMetadata.remove(i);
                                                                              }
                                                                            }
                                                                          }

                                                                          // Update excluded segments provider
                                                                          final String providerKey =
                                                                              widget.flowId ?? widget.taskId;
                                                                          final ExcludedSegmentsNotifier excludedNotifier =
                                                                              ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

                                                                          final Set<int> updatedExcludedSet =
                                                                              <int>{};
                                                                          for (var i = 0;
                                                                              i < segmentsData.length;
                                                                              i++) {
                                                                            final seg =
                                                                                segmentsData[i];
                                                                            if (seg
                                                                                is Map) {
                                                                              final bool isExcluded = seg['is_excluded'] as bool? ?? false;
                                                                              if (isExcluded) {
                                                                                updatedExcludedSet.add(i);
                                                                              }
                                                                            }
                                                                          }

                                                                          excludedNotifier
                                                                              .setExcluded(updatedExcludedSet);

                                                                          // Update chunks if needed
                                                                          final chunksTextRaw =
                                                                              updatedLayoutData['chunks_text'];
                                                                          if (chunksTextRaw != null &&
                                                                              chunksTextRaw is List) {
                                                                            final updatedChunks =
                                                                                chunksTextRaw.map((chunk) => chunk.toString()).toList();
                                                                            if (mounted) {
                                                                              // Use addPostFrameCallback to ensure setState is called after layout
                                                                              WidgetsBinding.instance.addPostFrameCallback((_) {
                                                                                if (mounted) {
                                                                                  setState(() {
                                                                                    allChunks = updatedChunks;
                                                                                  });

                                                                                  // Refresh chunks pagination
                                                                                  Future.delayed(const Duration(milliseconds: 100), () async {
                                                                                    if (mounted) {
                                                                                      await chunksPaginationController.loadFirstPage();
                                                                                    }
                                                                                  });
                                                                                }
                                                                              });
                                                                            }
                                                                          }

                                                                          // Refresh segments pagination
                                                                          if (mounted) {
                                                                            WidgetsBinding.instance.addPostFrameCallback((_) {
                                                                              if (mounted) {
                                                                                paginationController.refresh();
                                                                              }
                                                                            });
                                                                          }
                                                                        }
                                                                      } else {
                                                                        _log(
                                                                          '[ExtractPreview] Non-PDF file ($originalFilename), skipping layout-extract API call in unexclude callback. Chunks will be managed locally.',
                                                                          level:
                                                                              LogLevel.info,
                                                                        );
                                                                      }
                                                                    } catch (e) {
                                                                      _log(
                                                                        '[ExtractPreview] Error updating exclusion: $e',
                                                                        level: LogLevel
                                                                            .error,
                                                                      );
                                                                      if (mounted) {
                                                                        MessageService
                                                                            .showError(
                                                                          context,
                                                                          'Failed to update exclusion: $e',
                                                                        );
                                                                      }
                                                                    }
                                                                  });
                                                                }
                                                              },
                                                            ),
                                                            const Divider(
                                                              height: 2,
                                                            ), // Reduced from 8 to 2 for more compact display
                                                          ],
                                                        );
                                                      },
                                                      // No padding for ExtractPreview (listPadding: 0.0)
                                                    );
                                                  },
                                                ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      // Right: Exclusion panel (only show when data is loaded and panel is expanded)
                      if (initialDataLoaded &&
                          !isPreparing &&
                          isExclusionPanelExpanded)
                        Expanded(
                          child: Consumer(
                            builder: (context, ref, child) {
                              // Watch excludedSegmentsProviderFamily to recalculate when exclusions change
                              final String providerKey =
                                  widget.flowId ?? widget.taskId;
                              final Set<int> excludedSegments = ref.watch(
                                excludedSegmentsProviderFamily(providerKey),
                              );

                              return Card(
                                elevation: 2,
                                child: SingleChildScrollView(
                                  child: Padding(
                                    padding: const EdgeInsets.all(12),
                                    child: ExclusionPanelWidget(
                                      exclusionCounts:
                                          _calculateExclusionCounts(),
                                      totalSegments: allSegments.length,
                                      excludedCount: excludedSegments.length,
                                      failedCount:
                                          0, // No failed segments in Extract phase
                                      selectedFilters: selectedExclusionFilters,
                                      filterMode: filterMode,
                                      onFilterModeChanged: (mode) {
                                        setState(() {
                                          filterMode = mode;
                                          _updatePaginationForFilterMode();
                                        });
                                      },
                                      onFiltersChanged: (filters) {
                                        setState(() {
                                          selectedExclusionFilters = filters;
                                        });
                                        // PERFORMANCE: Clear cache and update immediately instead of using addPostFrameCallback
                                        clearFilteredCountCache();
                                        _updatePaginationForFilters();
                                        // Reset to first page and refresh segment list to apply filters
                                        paginationController.loadFirstPage();
                                      },
                                      // Category exclusion controls (only in Extract phase)
                                      // CRITICAL: Pass excludedSegments from Consumer's ref.watch()
                                      // This ensures checkbox states update when excludedSegments changes
                                      categoryExclusionStates:
                                          _getCategoryExclusionStates(
                                        excludedSegments,
                                      ),
                                      onCategoryExclusionChanged:
                                          _handleCategoryExclusionChanged,
                                      onExcludeAll: _handleExcludeAll,
                                      onCancelUserExclusion: _handleRestoreAutoExclusion,
                                      onClearAllExclusionsExceptImage: _handleClearAllExclusionsExceptImage,
                                      // Callback when panel is collapsed from inside (Extract phase)
                                      onPanelCollapsed: () {
                                        setState(() {
                                          isExclusionPanelExpanded = false;
                                        });
                                      },
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        )
                      else
                        // Show placeholder when data is not loaded
                        const Expanded(
                          child: Card(
                            elevation: 2,
                            child: Center(
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                              ),
                            ),
                          ),
                        ),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
        ), // Close Positioned.fill
        // Floating search box (similar to Cursor Terminal search)
        if (isSearchBoxVisible)
          Positioned(
            top: 48, // Position below toolbar (36px) + some spacing
            right: 12,
            child: SegmentSearchBox(
              initialQuery: searchQuery,
              matchCount: searchMatchIndices.length,
              currentMatchIndex: currentSearchMatchIndex,
              onSearch: _handleSearch,
              onClose: () {
                setState(() {
                  isSearchBoxVisible = false;
                  searchQuery = '';
                  searchMatchIndices.clear();
                  currentSearchMatchIndex = 0;
                });
              },
              onNextMatch: searchMatchIndices.isNotEmpty
                  ? () {
                      setState(() {
                        currentSearchMatchIndex =
                            (currentSearchMatchIndex + 1) %
                                searchMatchIndices.length;
                        // Clear previous highlight before scrolling to new match
                        highlightedIndex = null;
                        _scrollToSearchMatch();
                      });
                    }
                  : null,
              onPreviousMatch: searchMatchIndices.isNotEmpty
                  ? () {
                      setState(() {
                        currentSearchMatchIndex = (currentSearchMatchIndex -
                                1 +
                                searchMatchIndices.length) %
                            searchMatchIndices.length;
                        // Clear previous highlight before scrolling to new match
                        highlightedIndex = null;
                        _scrollToSearchMatch();
                      });
                    }
                  : null,
            ),
          ),
      ],
    );
  }

  /// Handle search query changes
  void _handleSearch(String query) {
    setState(() {
      searchQuery = query;
      if (query.isEmpty) {
        searchMatchIndices.clear();
        currentSearchMatchIndex = 0;
        // Clear highlight when search is cleared
        highlightedIndex = null;
      } else {
        // Search in all segments
        searchMatchIndices.clear();
        final queryLower = query.toLowerCase();
        for (int i = 0; i < allSegments.length; i++) {
          if (allSegments[i].toLowerCase().contains(queryLower)) {
            searchMatchIndices.add(i);
          }
        }
        if (searchMatchIndices.isNotEmpty) {
          currentSearchMatchIndex = 0;
          // Clear previous highlight before scrolling to new match
          highlightedIndex = null;
          _scrollToSearchMatch();
        } else {
          currentSearchMatchIndex = 0;
          // Clear highlight when no matches found
          highlightedIndex = null;
        }
      }
    });
  }

  /// Scroll to current search match
  void _scrollToSearchMatch() {
    if (searchMatchIndices.isEmpty) return;
    final targetIndex = searchMatchIndices[currentSearchMatchIndex];

    // Try to scroll to the segment
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;

      // Check if the segment is in the current page
      final currentPageItems = paginationController.items;
      final currentPageStart = paginationController.startIndex;

      if (targetIndex >= currentPageStart &&
          targetIndex < currentPageStart + currentPageItems.length) {
        // Segment is in current page, scroll to it
        final localIndex = targetIndex - currentPageStart;
        // Set highlightedIndex to show the segment as selected
        setState(() {
          highlightedIndex = localIndex;
        });
        if (segmentsScrollManager != null) {
          segmentsScrollManager!.scrollToIndex(localIndex);
        }
      } else {
        // Segment is not in current page, load the page containing it
        final pageSize = paginationController.pageSize;
        final targetPage = (targetIndex / pageSize).floor();
        paginationController.jumpToPage(targetPage).then((_) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            final localIndex = targetIndex % pageSize;
            // Set highlightedIndex to show the segment as selected
            setState(() {
              highlightedIndex = localIndex;
            });
            if (segmentsScrollManager != null) {
              segmentsScrollManager!.scrollToIndex(localIndex);
            }
          });
        });
      }
    });
  }

  /// Show dialog to prompt user to configure MinerU settings
  Future<void> _showMineruSettingsDialog(String errorMessage) async {
    if (!mounted || !context.mounted) return;

    final l10n = AppLocalizations.of(context)!;
    await DialogHelper.showDialog(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: Text(l10n.extractMineruConfigRequiredTitle),
        content: Text(
          l10n.extractMineruConfigRequiredContent(errorMessage),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text(l10n.translationToolbarCancelButton),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              // Navigate to Settings screen and switch to AI Platform tab (index 1)
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (ctx) => Scaffold(
                    appBar: AppBar(
                      title: Text(AppLocalizations.of(ctx)!.homeNavSettings),
                      leading: IconButton(
                        icon: const Icon(Icons.arrow_back),
                        onPressed: () => Navigator.of(context).pop(),
                      ),
                    ),
                    body: const SafeArea(
                      child: SettingsScreen(initialTabIndex: 1),
                    ),
                  ),
                ),
              );
            },
            child: Text(l10n.extractOpenSettings),
          ),
        ],
      ),
    );
  }
}
