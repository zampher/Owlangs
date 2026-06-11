import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../models/exclusion_reason.dart';
import '../../providers/excluded_segments_provider.dart';
import '../../providers/translation_refresh_provider.dart';
import '../../widgets/translation_quick_settings.dart';
import '../../providers/exclusion_update_provider.dart';
import '../../../../shared/services/translation_service.dart';
import '../../../../shared/utils/message_service.dart';
import '../../../../shared/utils/app_logger.dart';
import '../extract_preview.dart';
import 'extract_preview_state.dart';

// Note: Additional imports will be added as methods are moved from extract_preview.dart
// Required imports (to be added when methods are moved):
// - ../../../../shared/services/translation_service.dart
// - ../../../../shared/utils/message_service.dart
// - ../../models/exclusion_reason.dart
// - ../../providers/excluded_segments_provider.dart
// - ../../widgets/translation_quick_settings.dart

/// Mixin for handling exclusion operations in ExtractPreview
///
/// This mixin provides methods for:
/// - Handling category exclusion state changes (checkboxes)
/// - Bulk exclude/unexclude operations for different exclusion types
/// - Calculating exclusion statistics and counts
/// - Filtering segments based on exclusion reasons
/// - Managing filter mode (rebuild vs page)
///
/// **Note**: These methods handle the core exclusion logic and interact with
/// the backend API to update exclusion states.
mixin ExtractPreviewExclusionHandlerMixin<T extends ConsumerStatefulWidget>
    on ConsumerState<T>, ExtractPreviewStateMixin<T> {
  // ============================================================================
  // Required Methods (inherited from State class)
  // ============================================================================

  // Note: The following are available from ConsumerState<T>:
  // - BuildContext get context
  // - T get widget
  // - void setState(VoidCallback fn)
  // - bool get mounted
  //
  // The following should be provided by the State class:
  // - void _log(String message, {LogLevel level = LogLevel.debug})

  // ============================================================================
  // Exclusion Statistics and Counts
  // ============================================================================

  /// Calculate total excluded segments count
  int calculateExcludedCount() {
    // Use excludedSegmentsProviderFamily to get actual excluded count
    final ExtractPreview extractWidget = widget as ExtractPreview;
    final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
    final Set<int> excludedSegments = ref.read(
      excludedSegmentsProviderFamily(providerKey),
    );
    return excludedSegments.length;
  }

  /// Calculate exclusion counts by type
  /// Returns a map of exclusion reason -> count
  Map<String, int> calculateExclusionCounts() {
    final Map<String, int> counts = <String, int>{};

    // Count by type for ALL segments (not just excluded ones)
    // This ensures counts don't change when user checks/unchecks exclusion
    for (var index = 0; index < allSegments.length; index++) {
      final Map<String, dynamic>? typeInfo = segmentTypeInfo[index];
      final String? blockType = typeInfo?['block_type'] as String?;
      final bool? isTableBody = typeInfo?['is_table_body'] as bool?;
      final bool? isImage = typeInfo?['is_image'] as bool?;

      // Determine segment type based on block_type and other flags
      if (isImage ?? false) {
        // Image segments
        counts[ExclusionReason.image.value] =
            (counts[ExclusionReason.image.value] ?? 0) + 1;
      } else if (blockType == 'ref_text') {
        // Reference segments
        counts[ExclusionReason.reference.value] =
            (counts[ExclusionReason.reference.value] ?? 0) + 1;
      } else if (blockType == 'header' || blockType == 'page_header') {
        // Header segments (structural)
        counts['structural_header'] = (counts['structural_header'] ?? 0) + 1;
      } else if (blockType == 'footer' || blockType == 'page_footer') {
        // Footer segments (structural)
        counts['structural_footer'] = (counts['structural_footer'] ?? 0) + 1;
      } else if (blockType == 'table_body' || (isTableBody ?? false)) {
        // Table body segments only (table_caption is treated as normal text)
        counts[ExclusionReason.table.value] =
            (counts[ExclusionReason.table.value] ?? 0) + 1;
      } else if (blockType == 'interline_equation') {
        // Formula segments
        counts[ExclusionReason.formula.value] =
            (counts[ExclusionReason.formula.value] ?? 0) + 1;
      } else {
        // Check exclusion_reason for other types (identifier, language_match, formula, etc.)
        // Note: For identifier, language_match, and formula, we need to check exclusion_reason
        // as they might not have a specific block_type (especially for DOCX/PPTX files)
        final String? exclusionReason = segmentExclusionReasons[index];
        if (exclusionReason != null) {
          if (exclusionReason == ExclusionReason.identifier.value) {
            counts[ExclusionReason.identifier.value] =
                (counts[ExclusionReason.identifier.value] ?? 0) + 1;
          } else if (exclusionReason == ExclusionReason.languageMatch.value) {
            // Language match - will be updated below with total count
            counts[ExclusionReason.languageMatch.value] =
                (counts[ExclusionReason.languageMatch.value] ?? 0) + 1;
          } else if (exclusionReason == ExclusionReason.formula.value) {
            // Formula segments (for DOCX/PPTX files that don't have block_type)
            counts[ExclusionReason.formula.value] =
                (counts[ExclusionReason.formula.value] ?? 0) + 1;
          } else if (exclusionReason == ExclusionReason.structural.value) {
            // Other structural types (footnote, etc.)
            counts[ExclusionReason.structural.value] =
                (counts[ExclusionReason.structural.value] ?? 0) + 1;
          } else if (exclusionReason == ExclusionReason.unknown.value ||
              exclusionReason == ExclusionReason.userSelected.value) {
            // User selected - count separately
            counts[ExclusionReason.userSelected.value] =
                (counts[ExclusionReason.userSelected.value] ?? 0) + 1;
          }
        }
      }
    }

    // CRITICAL: Use stored indices for formula, reference, header, footer, table, chart, identifier, language_match, user_selected counts
    // These are more reliable than parsing block_type or exclusion_reason for each segment
    // and are set during initial data load
    if (formulaSegmentIndices.isNotEmpty) {
      counts[ExclusionReason.formula.value] = formulaSegmentIndices.length;
    }
    if (referenceSegmentIndices.isNotEmpty) {
      counts[ExclusionReason.reference.value] = referenceSegmentIndices.length;
    }
    if (headerSegmentIndices.isNotEmpty) {
      counts['structural_header'] = headerSegmentIndices.length;
    }
    if (footerSegmentIndices.isNotEmpty) {
      counts['structural_footer'] = footerSegmentIndices.length;
    }
    if (tableSegmentIndices.isNotEmpty) {
      counts[ExclusionReason.table.value] = tableSegmentIndices.length;
    }
    if (chartSegmentIndices.isNotEmpty) {
      counts[ExclusionReason.chart.value] = chartSegmentIndices.length;
    }
    if (identifierSegmentIndices.isNotEmpty) {
      counts[ExclusionReason.identifier.value] =
          identifierSegmentIndices.length;
    }
    if (languageMatchedSegmentIndices.isNotEmpty) {
      counts[ExclusionReason.languageMatch.value] =
          languageMatchedSegmentIndices.length;
    }
    if (userSelectedSegmentIndices.isNotEmpty) {
      counts[ExclusionReason.userSelected.value] =
          userSelectedSegmentIndices.length;
    }

    // CRITICAL: For Language Match, also use languageMatchedSegmentCount if available
    // This includes both excluded and potentially matching segments (from API detection)
    // Use the larger value to ensure we show the correct count
    if (languageMatchedSegmentCount > 0) {
      final int storedCount = languageMatchedSegmentIndices.length;
      counts[ExclusionReason.languageMatch.value] =
          languageMatchedSegmentCount > storedCount
              ? languageMatchedSegmentCount
              : storedCount;
    }

    // Ensure all exclusion reason types are included (with 0 count if not present)
    for (final reason in ExclusionReason.values) {
      if (reason == ExclusionReason.structural) {
        // For Structural, add header and footer counts
        if (!counts.containsKey('structural_header')) {
          counts['structural_header'] = 0;
        }
        if (!counts.containsKey('structural_footer')) {
          counts['structural_footer'] = 0;
        }
        // Also keep the general structural count for other types
        if (!counts.containsKey(reason.value)) {
          counts[reason.value] = 0;
        }
      } else if (reason == ExclusionReason.unknown) {
        // Skip unknown - it's merged into user_selected
        continue;
      } else {
        if (!counts.containsKey(reason.value)) {
          counts[reason.value] = 0;
        }
      }
    }

    return counts;
  }

  /// All category keys used in Exclusion panel (for default state from config)
  static const List<String> _allCategoryKeys = <String>[
    'image',
    'formula',
    'reference',
    'identifier',
    'structural',
    'table',
    'chart',
    'language_match',
    'user_selected',
  ];

  /// Get category exclusion states for checkboxes
  /// Returns a map of category -> isExcluded (bool)
  /// [exclusionDefaults] from system config: used for categories with 0 segments so checkbox follows config.
  /// PERFORMANCE: Uses Set.intersection for O(min(a,b)) instead of
  /// List.contains inside .where() which was O(|excluded| × |list|).
  Map<String, bool> getCategoryExclusionStates(
    Set<int> excludedSegments, {
    Map<String, bool>? exclusionDefaults,
  }) {
    final Map<String, bool> states = <String, bool>{};

    // Image exclusion: segments with is_image in segmentTypeInfo
    for (var i = 0; i < allSegments.length; i++) {
      if (segmentTypeInfo[i]?['is_image'] == true) {
        if (excludedSegments.contains(i)) {
          states['image'] = true;
          break;
        }
      }
    }
    if (!states.containsKey('image')) {
      final hasImage = segmentTypeInfo.values.any((m) => m['is_image'] == true);
      if (hasImage) states['image'] = false;
    }

    // Reference exclusion - check if any reference segments are currently excluded
    // CRITICAL: Always calculate based on current excludedSegments, not cached state
    // This ensures the checkbox reflects the real-time exclusion status
    // PERFORMANCE: indexSetFor() returns a cached Set<int> for O(min(a,b))
    // intersection instead of O(|excluded| × |list|) from List.contains.
    if (referenceSegmentIndices.isNotEmpty) {
      final int excludedReferenceCount =
          excludedSegments.intersection(indexSetFor('reference')).length;
      // If any reference segments are excluded, checkbox should be checked
      states['reference'] = excludedReferenceCount > 0;
    }

    // Structural exclusion (headers and footers) - check if any header/footer segments are currently excluded
    // CRITICAL: Always calculate based on current excludedSegments, not cached state
    // This ensures the checkbox reflects the real-time exclusion status (default not excluded)
    if (headerSegmentIndices.isNotEmpty || footerSegmentIndices.isNotEmpty) {
      // Check how many header/footer segments are currently excluded
      final int excludedHeaderCount =
          excludedSegments.intersection(indexSetFor('header')).length;
      final int excludedFooterCount =
          excludedSegments.intersection(indexSetFor('footer')).length;
      // Structural checkbox checked only when any header or footer is excluded
      states['structural'] = excludedHeaderCount > 0 || excludedFooterCount > 0;
      // Sync cache so other code paths see consistent state; log for diagnostics
      categoryExclusionStates['structural'] = states['structural']!;
      AppLogger.log(
        'ExtractPreview',
        'Structural exclusion state: header excluded=$excludedHeaderCount/${headerSegmentIndices.length}, '
            'footer excluded=$excludedFooterCount/${footerSegmentIndices.length}, checkbox=${states['structural']}',
      );
    } else {
      // No header/footer segments: ensure key is present and false
      states['structural'] = false;
      categoryExclusionStates['structural'] = false;
    }

    // Language match exclusion
    // CRITICAL: Use languageMatchedSegmentIndices and check excluded status
    // This ensures we correctly identify language-matched segments even when they're not yet excluded
    // Always check excludedSegmentsProviderFamily to get real-time state, not cached categoryExclusionStates
    if (languageMatchedSegmentIndices.isNotEmpty ||
        languageMatchedSegmentCount > 0) {
      // Always check how many language-matched segments are currently excluded
      // This ensures checkbox state reflects actual exclusion status, not cached state
      final int excludedLanguageCount =
          excludedSegments.intersection(indexSetFor('language_match')).length;
      // If any language-matched segments are excluded, checkbox should be checked
      states['language_match'] = excludedLanguageCount > 0;

      // Update cached state to match actual state
      categoryExclusionStates['language_match'] = states['language_match']!;
    }

    // Formula exclusion - check if any formula segments are currently excluded
    // CRITICAL: Always calculate based on current excludedSegments, not cached state
    if (formulaSegmentIndices.isNotEmpty) {
      final int excludedFormulaCount =
          excludedSegments.intersection(indexSetFor('formula')).length;
      states['formula'] = excludedFormulaCount > 0;
    }

    // Identifier exclusion - check if any identifier segments are currently excluded
    // CRITICAL: Always calculate based on current excludedSegments, not cached state
    // This ensures the checkbox reflects the real-time exclusion status
    if (identifierSegmentIndices.isNotEmpty) {
      // Always calculate based on current excludedSegments
      final int excludedIdentifierCount =
          excludedSegments.intersection(indexSetFor('identifier')).length;
      // If any identifier segments are excluded, checkbox should be checked
      states['identifier'] = excludedIdentifierCount > 0;
    }

    // Table exclusion - check if any table segments are currently excluded
    // Default to false (not excluded) if table segments exist, same as structural (headers/footers)
    // CRITICAL: Use tableSegmentIndices and check is_excluded status, not exclusion_reason
    // This ensures we correctly identify tables even when they're not yet excluded
    if (tableSegmentIndices.isNotEmpty) {
      // Check how many table segments are currently excluded
      final int excludedTableCount =
          excludedSegments.intersection(indexSetFor('table')).length;
      // If any table segments are excluded, checkbox should be checked
      // This allows partial exclusion (user can exclude some tables but not all)
      states['table'] = excludedTableCount > 0;
    }

    // Chart exclusion - check if any chart segments are currently excluded
    // Default to false (not excluded) if chart segments exist, same as table
    // CRITICAL: Use chartSegmentIndices and check is_excluded status, not exclusion_reason
    // This ensures we correctly identify charts even when they're not yet excluded
    if (chartSegmentIndices.isNotEmpty) {
      // Check how many chart segments are currently excluded
      final int excludedChartCount =
          excludedSegments.intersection(indexSetFor('chart')).length;
      // If any chart segments are excluded, checkbox should be checked
      // This allows partial exclusion (user can exclude some charts but not all)
      states['chart'] = excludedChartCount > 0;
    }

    // User Selected exclusion - check if any user_selected or unknown segments are currently excluded
    // CRITICAL: Use userSelectedSegmentIndices and check excluded status
    // This ensures we correctly identify user-selected segments even when they're not yet excluded
    if (userSelectedSegmentIndices.isNotEmpty) {
      // Check how many user-selected segments are currently excluded
      final int excludedUserSelectedCount =
          excludedSegments.intersection(indexSetFor('user_selected')).length;
      // If any user-selected segments are excluded, checkbox should be checked
      // This allows partial exclusion (user can exclude some user-selected segments but not all)
      states['user_selected'] = excludedUserSelectedCount > 0;
    }

    // Fill missing categories from config (exclusion_defaults) so e.g. Language Match (0) has correct default
    for (final key in _allCategoryKeys) {
      states.putIfAbsent(key, () => exclusionDefaults?[key] ?? false);
    }

    return states;
  }

  // ============================================================================
  // Filtering Methods
  // ============================================================================

  /// Check if a segment matches the current filters
  bool matchesFilter(int index, Set<int> excludedSegments) {
    final bool isExcluded = excludedSegments.contains(index);
    final String? exclusionReason = segmentExclusionReasons[index];

    // Special case: "included" filter - show only included segments (will be translated)
    if (selectedExclusionFilters.contains('included')) {
      return !isExcluded;
    }

    // Special case: "all_excluded" filter - show only excluded segments
    if (selectedExclusionFilters.contains('all_excluded')) {
      return isExcluded;
    }

    // Normal filter: check if segment type matches selected filters
    final Map<String, dynamic>? typeInfo = segmentTypeInfo[index];
    final String? blockType = typeInfo?['block_type'] as String?;
    final bool? isTableBody = typeInfo?['is_table_body'] as bool?;
    final bool? isImage = typeInfo?['is_image'] as bool?;

    // Determine segment type (same logic as in itemBuilder)
    String? segmentType;
    if (isImage ?? false) {
      segmentType = ExclusionReason.image.value;
    } else if (blockType == 'ref_text') {
      segmentType = ExclusionReason.reference.value;
    } else if (blockType == 'header' || blockType == 'page_header') {
      segmentType = 'structural_header';
    } else if (blockType == 'footer' || blockType == 'page_footer') {
      segmentType = 'structural_footer';
    } else if (blockType == 'table_body' || (isTableBody ?? false)) {
      segmentType = ExclusionReason.table.value;
    } else if (blockType == 'interline_equation') {
      segmentType = ExclusionReason.formula.value;
    } else if (exclusionReason != null) {
      // Use exclusion_reason for identifier, language_match, formula, etc.
      segmentType = exclusionReason;
    } else {
      // CRITICAL: If exclusionReason is null (e.g., after unexclude),
      // check stored indices to identify segment type
      // This ensures filtering works even when segments are not currently excluded
      // PERFORMANCE: Use cached Set<int> for O(1) contains instead of List O(n)
      if (indexSetContains('identifier', index)) {
        segmentType = ExclusionReason.identifier.value;
      } else if (indexSetContains('language_match', index)) {
        segmentType = ExclusionReason.languageMatch.value;
      } else if (indexSetContains('reference', index)) {
        segmentType = ExclusionReason.reference.value;
      } else if (indexSetContains('header', index)) {
        segmentType = 'structural_header';
      } else if (indexSetContains('footer', index)) {
        segmentType = 'structural_footer';
      } else if (indexSetContains('table', index)) {
        segmentType = ExclusionReason.table.value;
      } else if (indexSetContains('chart', index)) {
        segmentType = ExclusionReason.chart.value;
      } else if (indexSetContains('formula', index)) {
        segmentType = ExclusionReason.formula.value;
      } else if (indexSetContains('user_selected', index)) {
        segmentType = ExclusionReason.userSelected.value;
      }
    }

    // Check if segment type matches any selected filter
    return segmentType != null &&
        selectedExclusionFilters.contains(segmentType);
  }

  /// Get filtered segment indices (for rebuild mode)
  List<int> getFilteredSegmentIndices() {
    // If no filters are selected, return all indices
    if (selectedExclusionFilters.isEmpty) {
      return List.generate(allSegments.length, (i) => i);
    }

    final ExtractPreview extractWidget = widget as ExtractPreview;
    final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
    final Set<int> excludedSegments = ref.read(
      excludedSegmentsProviderFamily(providerKey),
    );

    final List<int> filteredIndices = <int>[];
    for (var index = 0; index < allSegments.length; index++) {
      if (matchesFilter(index, excludedSegments)) {
        filteredIndices.add(index);
      }
    }

    return filteredIndices;
  }

  /// Calculate filtered segments count based on current filters
  /// This is used to update pagination totalItems when filters are active
  /// PERFORMANCE: Uses caching to avoid expensive recalculation on every call
  int calculateFilteredSegmentCount() {
    if (filterMode == 'rebuild') {
      // For rebuild mode, use cached filtered indices
      filteredSegmentIndices = getFilteredSegmentIndices();
      return filteredSegmentIndices?.length ?? allSegments.length;
    } else {
      // For page mode, use cached count if available and still valid
      final ExtractPreview extractWidget = widget as ExtractPreview;
      final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
      final Set<int> excludedSegments = ref.read(
        excludedSegmentsProviderFamily(providerKey),
      );

      // Check if cache is still valid
      final bool cacheValid = cachedFilteredCount != null &&
          cachedFilteredCountFilters != null &&
          cachedFilteredCountExcludedLength != null &&
          cachedFilteredCountSegmentsLength != null &&
          cachedFilteredCountFilters == selectedExclusionFilters &&
          cachedFilteredCountExcludedLength == excludedSegments.length &&
          cachedFilteredCountSegmentsLength == allSegments.length;

      if (cacheValid) {
        return cachedFilteredCount!;
      }

      // Cache miss or invalid - recalculate
      int filteredCount = 0;
      for (var index = 0; index < allSegments.length; index++) {
        if (matchesFilter(index, excludedSegments)) {
          filteredCount++;
        }
      }

      // Update cache
      cachedFilteredCount = filteredCount;
      cachedFilteredCountFilters = Set<String>.from(selectedExclusionFilters);
      cachedFilteredCountExcludedLength = excludedSegments.length;
      cachedFilteredCountSegmentsLength = allSegments.length;

      return filteredCount;
    }
  }

  /// Clear cached filtered count (call when filters, excluded segments, or UI size changes)
  void clearFilteredCountCache() {
    cachedFilteredCount = null;
    cachedFilteredCountFilters = null;
    cachedFilteredCountExcludedLength = null;
    cachedFilteredCountSegmentsLength = null;
  }

  /// Update pagination for filter mode changes
  void updatePaginationForFilterMode() {
    if (!mounted) return;

    // Logging should be done by the State class's _log method
    // _log('[ExtractPreview] Filter mode changed to: $filterMode', level: LogLevel.info);

    // Clear cached filtered indices
    filteredSegmentIndices = null;

    // Reset to first page and refresh
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        paginationController.loadFirstPage();
        paginationController.refresh();
      }
    });
  }

  // ============================================================================
  // Category Exclusion Handlers
  // ============================================================================

  /// Handle category exclusion state change from panel
  /// This is the main entry point for checkbox clicks
  Future<void> handleCategoryExclusionChanged(
    String category,
    bool exclude,
  ) async {
    // CRITICAL: Increment generation counter so any in-flight bulk operation
    // from a previous click detects it was superseded and aborts early.
    exclusionOperationGeneration++;

    final ExtractPreview extractWidget = widget as ExtractPreview;

    switch (category) {
      case 'formula':
        // Formula exclusion - bulk exclude/unexclude all formula segments
        await handleExcludeFormulaSegments(exclude);
        setState(() {
          categoryExclusionStates['formula'] = exclude;
        });
        break;
      case 'reference':
        if (referenceSegmentIndices.isNotEmpty) {
          // CRITICAL: Use new method that supports all formats (EPUB, PDF, etc.)
          // Similar to Identifier, this uses individual API calls with optimistic update
          await handleExcludeReferenceSegments(exclude);
        }
        break;
      case 'structural':
        // Structural case is handled by the wrapper method in main file
        // because _applyExcludeHeadersState and _applyExcludeFootersState are still there
        // TODO: Move _applyExcludeHeadersState and _applyExcludeFootersState to Mixin
        // This should not be called - main file handles it
        return;
      case 'language_match':
        // Language exclusion is handled differently
        // CRITICAL: Use languageMatchedSegmentIndices.length instead of languageMatchedSegmentCount
        // because languageMatchedSegmentCount may be 0 if backend skipped re-detection (target_lang unchanged)
        final int languageMatchedCount =
            languageMatchedSegmentIndices.isNotEmpty
                ? languageMatchedSegmentIndices.length
                : languageMatchedSegmentCount;

        if (languageMatchedCount > 0) {
          final TranslationQuickSettings qs = extractWidget.flowId != null
              ? ref.read(
                  translationQuickSettingsProviderFamily(extractWidget.flowId!),
                )
              : ref.read(translationQuickSettingsProvider);
          await handleExcludeLanguageSegments(qs.toLang, exclude);
          setState(() {
            isLanguageExclusionActive = exclude;
            categoryExclusionStates['language_match'] = exclude;
          });
          // Logging should be done by the State class's _log method
          // _log('[ExtractPreview] Language match exclusion checkbox updated: exclude=$exclude, ...', level: LogLevel.info);
        } else {
          // Logging should be done by the State class's _log method
          // _log('[ExtractPreview] Language match exclusion checkbox clicked but no language-matched segments found ...', level: LogLevel.warn);
        }
        break;
      case 'identifier':
        // Identifier exclusion - bulk exclude/unexclude all identifier segments
        await handleExcludeIdentifierSegments(exclude);
        setState(() {
          categoryExclusionStates['identifier'] = exclude;
        });
        // Logging should be done by the State class's _log method
        // _log('[ExtractPreview] Identifier exclusion checkbox updated: exclude=$exclude, ...', level: LogLevel.info);
        break;
      case 'table':
        // Table exclusion - bulk exclude/unexclude all table segments
        await handleExcludeTableSegments(exclude);
        setState(() {
          categoryExclusionStates['table'] = exclude;
        });
        // Logging should be done by the State class's _log method
        // _log('[ExtractPreview] Table exclusion checkbox updated: exclude=$exclude, ...', level: LogLevel.info);
        break;
      case 'chart':
        // Chart exclusion - bulk exclude/unexclude all chart segments
        await handleExcludeChartSegments(exclude);
        setState(() {
          categoryExclusionStates['chart'] = exclude;
        });
        // Logging should be done by the State class's _log method
        // _log('[ExtractPreview] Chart exclusion checkbox updated: exclude=$exclude, ...', level: LogLevel.info);
        break;
      case 'user_selected':
        // User Selected exclusion - bulk exclude/unexclude all user_selected and unknown segments
        await handleExcludeUserSelectedSegments(exclude);
        setState(() {
          categoryExclusionStates['user_selected'] = exclude;
        });
        // Logging should be done by the State class's _log method
        // _log('[ExtractPreview] User selected exclusion checkbox updated: exclude=$exclude, ...', level: LogLevel.info);
        break;
    }

    // Safety net: refresh pagination after handler completes to catch any state
    // drift from backend sync (e.g., partial API failures that changed the
    // excluded set).  Each handler already does an immediate loadFirstPage after
    // its optimistic update, so in the common (no-failure) case this is a no-op
    // rebuild.  With O(1) cached-set containment checks the cost is ~O(n) for n
    // segments, i.e. ~1-5 ms even for 100K segments.
    if (mounted &&
        filterMode == 'rebuild' &&
        selectedExclusionFilters.isNotEmpty) {
      clearFilteredCountCache();
      await paginationController.loadFirstPage();
    }
  }

  // ============================================================================
  // Specific Exclusion Type Handlers
  // ============================================================================

  /// Handle exclude/unexclude identifier segments in bulk
  Future<void> handleExcludeIdentifierSegments(bool exclude) async {
    final ExtractPreview extractWidget = widget as ExtractPreview;
    // Capture the current generation so we can detect if a newer operation supersedes us
    final int myGeneration = exclusionOperationGeneration;
    AppLogger.log(
      'ExtractPreview',
      '_handleExcludeIdentifierSegments called: exclude=$exclude, '
          'identifierSegmentCount=${identifierSegmentIndices.length}, '
          'generation=$myGeneration, taskId=${extractWidget.taskId}',
      level: LogLevel.info,
    );

    final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
    try {
      beginExclusionUpdate(ref, providerKey);
      // Use cached set for O(1) lookups (avoids List.toSet() allocation each time)
      final Set<int> identifierSegments = indexSetFor('identifier');

      if (identifierSegments.isEmpty) {
        AppLogger.log(
          'ExtractPreview',
          'No identifier segments to ${exclude ? "exclude" : "unexclude"}',
          level: LogLevel.warn,
        );
        return;
      }

      // CRITICAL: Optimistic update - update UI state immediately for better UX
      if (mounted) {
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> optimisticExcluded;
        if (exclude) {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = <int>{
            ...currentExcluded,
            ...identifierSegments,
          };
        } else {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = currentExcluded.difference(identifierSegments);
        }

        excludedNotifier.setExcluded(optimisticExcluded);

        for (final index in identifierSegments) {
          if (exclude) {
            segmentExclusionReasons[index] = ExclusionReason.identifier.value;
          } else {
            segmentExclusionReasons.remove(index);
            segmentExclusionMetadata.remove(index);
          }
        }

        setState(() {});

        AppLogger.log(
          'ExtractPreview',
          'Optimistic update: exclude=$exclude, '
              'updated ${identifierSegments.length} segments immediately for instant UI feedback',
          level: LogLevel.info,
        );

        // CRITICAL: When filter is active, refresh pagination immediately after
        // optimistic update so the user sees the correct filtered list right away
        // instead of stale items with wrong badges for several seconds while API
        // calls are in progress.
        if (filterMode == 'rebuild' && selectedExclusionFilters.isNotEmpty) {
          clearFilteredCountCache();
          await paginationController.loadFirstPage();
        }
      }

      final TranslationService svc = TranslationService();
      int successCount = 0;
      int failCount = 0;

      if (exclude) {
        for (final index in identifierSegments) {
          // Abort if a newer operation has started
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Identifier exclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.excludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to exclude identifier segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          MessageService.showInfo(
            context,
            'Excluded $successCount identifier segment(s)${failCount > 0 ? ' ($failCount failed)' : ''}',
          );
        }
      } else {
        for (final index in identifierSegments) {
          // Abort if a newer operation has started
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Identifier unexclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.unexcludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to unexclude identifier segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          if (failCount > 0) {
            MessageService.showWarning(
              context,
              'Unexcluded $successCount identifier segment(s), $failCount failed (content-based exclusions cannot be removed)',
            );
          } else {
            MessageService.showInfo(
              context,
              'Unexcluded $successCount identifier segment(s)',
            );
          }
        }
      }

      // Skip backend refresh/sync if superseded
      if (exclusionOperationGeneration != myGeneration) {
        AppLogger.log(
          'ExtractPreview',
          'Identifier exclusion post-sync skipped: superseded '
              '(my=$myGeneration, current=$exclusionOperationGeneration)',
          level: LogLevel.info,
        );
        return;
      }

      Set<int>? backendExcluded;
      if (mounted && !exclude) {
        try {
          final Map<String, dynamic> statusData =
              await svc.getStatus(extractWidget.taskId);
          // Re-check after await
          if (exclusionOperationGeneration != myGeneration) return;
          final Map<String, dynamic>? segmentsMetadata =
              statusData['segments_metadata'] as Map<String, dynamic>?;

          if (segmentsMetadata != null) {
            final List<dynamic>? excludedIndicesList =
                segmentsMetadata['excluded_segment_indices'] as List<dynamic>?;
            backendExcluded = excludedIndicesList != null
                ? excludedIndicesList.map((idx) => idx as int).toSet()
                : <int>{};
            final List<dynamic>? userUnexcludedList =
                segmentsMetadata['user_unexcluded_segments'] as List<dynamic>?;
            if (userUnexcludedList != null && userUnexcludedList.isNotEmpty) {
              final Set<int> userUnexcluded =
                  userUnexcludedList.map((idx) => idx as int).toSet();
              backendExcluded = backendExcluded.difference(userUnexcluded);
            }

            AppLogger.log(
              'ExtractPreview',
              'Refreshed excluded segments from backend after unexclude: '
                  'backend excluded count=${backendExcluded.length}, identifier segments=${identifierSegments.length}',
              level: LogLevel.info,
            );
          }
        } catch (e) {
          AppLogger.log(
            'ExtractPreview',
            'Failed to refresh excluded segments from backend after unexclude: $e',
            level: LogLevel.warn,
          );
        }
      }

      // Final sync — only if still the latest operation
      if (mounted && exclusionOperationGeneration == myGeneration) {
        final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> finalExcluded;
        if (exclude) {
          if (failCount > 0) {
            try {
              final Map<String, dynamic> statusData =
                  await svc.getStatus(extractWidget.taskId);
              if (exclusionOperationGeneration != myGeneration) return;
              final Map<String, dynamic>? segmentsMetadata =
                  statusData['segments_metadata'] as Map<String, dynamic>?;
              if (segmentsMetadata != null) {
                final List<dynamic>? excludedIndicesList =
                    segmentsMetadata['excluded_segment_indices']
                        as List<dynamic>?;
                if (excludedIndicesList != null) {
                  finalExcluded =
                      excludedIndicesList.map((idx) => idx as int).toSet();
                  excludedNotifier.setExcluded(finalExcluded);
                  AppLogger.log(
                    'ExtractPreview',
                    'Synced excluded segments with backend after partial failures: '
                        'backend excluded count=${finalExcluded.length}',
                    level: LogLevel.info,
                  );
                }
              }
            } catch (e) {
              AppLogger.log(
                'ExtractPreview',
                'Failed to sync with backend after partial failures: $e',
                level: LogLevel.warn,
              );
            }
          }
        } else {
          if (backendExcluded != null) {
            finalExcluded = backendExcluded;
            excludedNotifier.setExcluded(finalExcluded);
            AppLogger.log(
              'ExtractPreview',
              'Synced excluded segments with backend after unexclude: '
                  'backend excluded count=${finalExcluded.length}',
              level: LogLevel.info,
            );
          }
        }

        AppLogger.log(
          'ExtractPreview',
          'Final identifier exclusion state: exclude=$exclude, '
              'success=$successCount, failed=$failCount',
          level: LogLevel.info,
        );
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Error handling identifier exclusion: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Error handling identifier exclusion: $e',
        );
      }
    } finally {
      endExclusionUpdate(ref, providerKey);
    }
  }

  /// Handle exclude/unexclude language-matched segments in bulk
  Future<void> handleExcludeLanguageSegments(
    String targetLang,
    bool exclude,
  ) async {
    final ExtractPreview extractWidget = widget as ExtractPreview;
    AppLogger.log(
      'ExtractPreview',
      '_handleExcludeLanguageSegments called: exclude=$exclude, '
          'targetLang=$targetLang, languageMatchedCount=$languageMatchedSegmentCount, '
          'taskId=${extractWidget.taskId}',
      level: LogLevel.info,
    );

    try {
      AppLogger.log(
        'ExtractPreview',
        '${exclude ? "Excluding" : "Clearing exclusion for"} language-matched segments for target_lang=$targetLang',
        level: LogLevel.info,
      );

      final TranslationService svc = TranslationService();
      Map<String, dynamic> result;

      if (exclude) {
        // Exclude language-matched segments
        result = await svc.updateExcludedSegmentsForLanguage(
          extractWidget.taskId,
          targetLang,
          autoExclude: true,
        );

        final int excludedCount = result['excluded_count'] as int? ?? 0;
        int languageMatchedCount =
            result['language_matched_count'] as int? ?? 0;

        // CRITICAL: If backend returns 0 (e.g., target_lang unchanged, skipped re-detection),
        // but we have stored language-matched indices, use the stored count instead
        if (languageMatchedCount == 0 &&
            languageMatchedSegmentIndices.isNotEmpty) {
          languageMatchedCount = languageMatchedSegmentIndices.length;
          AppLogger.log(
            'ExtractPreview',
            'Backend returned languageMatchedCount=0 (likely skipped re-detection), '
                'using stored indices count: $languageMatchedCount',
            level: LogLevel.info,
          );
        }

        if (mounted) {
          setState(() {
            languageMatchedSegmentCount = languageMatchedCount;
          });
          MessageService.showInfo(
            context,
            'Excluded $excludedCount segment(s) that match the target language "$targetLang"',
          );
        }
      } else {
        // Clear language-based exclusions (keep non-language exclusions)
        result = await svc.updateExcludedSegmentsForLanguage(
          extractWidget.taskId,
          targetLang,
        );

        final int excludedCount = result['excluded_count'] as int? ?? 0;
        int languageMatchedCount =
            result['language_matched_count'] as int? ?? 0;

        // CRITICAL: If backend returns 0 (e.g., target_lang unchanged, skipped re-detection),
        // but we have stored language-matched indices, use the stored count instead
        if (languageMatchedCount == 0 &&
            languageMatchedSegmentIndices.isNotEmpty) {
          languageMatchedCount = languageMatchedSegmentIndices.length;
          AppLogger.log(
            'ExtractPreview',
            'Backend returned languageMatchedCount=0 (likely skipped re-detection), '
                'using stored indices count: $languageMatchedCount',
            level: LogLevel.info,
          );
        }

        if (mounted) {
          setState(() {
            languageMatchedSegmentCount = languageMatchedCount;
          });
          MessageService.showInfo(
            context,
            'Cleared language-based exclusions. $excludedCount non-language segment(s) remain excluded.',
          );
        }
      }

      // Update exclusion state locally without full refresh
      // This is more efficient than calling refreshChunks() which reloads all data
      if (mounted) {
        // CRITICAL: When clearing exclusions (exclude=false), use the excluded_segment_indices
        // from the API response to ensure we have the correct state from the backend
        // This is more reliable than manually removing language-matched segments
        final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        // Get language-matched segment indices from cached set (avoids List.toSet() allocation)
        Set<int> languageMatchedSegments =
            Set<int>.from(indexSetFor('language_match'));

        // If API returned language-matched segments, use them
        if (result.containsKey('language_matched_segments')) {
          final List<dynamic>? languageMatchedSegmentsList =
              result['language_matched_segments'] as List<dynamic>?;
          if (languageMatchedSegmentsList != null &&
              languageMatchedSegmentsList.isNotEmpty) {
            languageMatchedSegments = languageMatchedSegmentsList
                .map((seg) => seg['index'] as int? ?? -1)
                .where((idx) => idx >= 0)
                .toSet();
            // Update stored indices
            setState(() {
              languageMatchedSegmentIndices = languageMatchedSegments.toList();
            });
          }
        }

        Set<int> updatedExcluded;
        if (exclude) {
          // Add language-matched segments to excluded set
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          updatedExcluded = <int>{
            ...currentExcluded,
            ...languageMatchedSegments,
          };
        } else {
          // CRITICAL: When clearing exclusions, use excluded_segment_indices from API response
          // This ensures we have the correct state from the backend after clearing
          final List<dynamic>? excludedIndicesList =
              result['excluded_segment_indices'] as List<dynamic>?;
          if (excludedIndicesList != null) {
            // Use the excluded_segment_indices from the API response
            updatedExcluded = excludedIndicesList
                .map((idx) => idx as int? ?? -1)
                .where((idx) => idx >= 0)
                .toSet();
          } else {
            // Fallback: Remove language-matched segments from excluded set
            final Set<int> currentExcluded =
                ref.read(excludedSegmentsProviderFamily(providerKey));
            updatedExcluded =
                currentExcluded.difference(languageMatchedSegments);
          }
        }

        excludedNotifier.setExcluded(updatedExcluded);

        // Update local segment exclusion reasons
        for (final index in languageMatchedSegments) {
          if (exclude) {
            // Mark as excluded with LANGUAGE_MATCH reason
            segmentExclusionReasons[index] =
                ExclusionReason.languageMatch.value;
          } else {
            // Remove exclusion reason
            segmentExclusionReasons.remove(index);
            segmentExclusionMetadata.remove(index);
          }
        }

        // Update local state
        setState(() {
          isLanguageExclusionActive = exclude;
          categoryExclusionStates['language_match'] = exclude;
        });

        AppLogger.log(
          'ExtractPreview',
          'Updated language-match exclusion state locally: exclude=$exclude, '
              'updated ${languageMatchedSegments.length} segments, excluded count: ${updatedExcluded.length}',
          level: LogLevel.info,
        );

        // Only refresh chunks if chunks count might have changed
        // For language-match exclusion, chunks count typically doesn't change
        // So we can skip the full refresh for better performance
        // await refreshChunks();

        // Also trigger translation refresh
        triggerTranslationRefresh(ref);
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Failed to ${exclude ? "exclude" : "clear exclusion for"} language segments: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to ${exclude ? "exclude" : "clear exclusion for"} language segments: $e',
        );
      }
    }
  }

  /// Handle exclude/unexclude table segments in bulk
  /// Handle exclude/unexclude formula segments in bulk
  Future<void> handleExcludeFormulaSegments(bool exclude) async {
    final ExtractPreview extractWidget = widget as ExtractPreview;
    final int myGeneration = exclusionOperationGeneration;
    AppLogger.log(
      'ExtractPreview',
      '_handleExcludeFormulaSegments called: exclude=$exclude, '
          'formulaSegmentCount=${formulaSegmentIndices.length}, '
          'generation=$myGeneration, taskId=${extractWidget.taskId}',
      level: LogLevel.info,
    );

    final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
    try {
      beginExclusionUpdate(ref, providerKey);
      if (formulaSegmentIndices.isEmpty) {
        AppLogger.log(
          'ExtractPreview',
          'No formula segments found (formulaSegmentIndices is empty)',
          level: LogLevel.warn,
        );
        return;
      }

      // Use cached set for O(1) lookups (avoids List.toSet() allocation)
      final Set<int> formulaSegments = indexSetFor('formula');

      // Optimistic update — update UI state immediately
      if (mounted) {
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> optimisticExcluded;
        if (exclude) {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = <int>{...currentExcluded, ...formulaSegments};
        } else {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = currentExcluded.difference(formulaSegments);
        }

        excludedNotifier.setExcluded(optimisticExcluded);

        for (final index in formulaSegments) {
          if (exclude) {
            segmentExclusionReasons[index] = ExclusionReason.formula.value;
          } else {
            segmentExclusionReasons.remove(index);
            segmentExclusionMetadata.remove(index);
          }
        }

        setState(() {});

        // CRITICAL: When filter is active, refresh pagination immediately after
        // optimistic update so the filtered list reflects the change right away.
        if (filterMode == 'rebuild' && selectedExclusionFilters.isNotEmpty) {
          clearFilteredCountCache();
          await paginationController.loadFirstPage();
        }
      }

      final TranslationService svc = TranslationService();
      int successCount = 0;
      int failCount = 0;

      if (exclude) {
        for (final index in formulaSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Formula exclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.excludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to exclude formula segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          MessageService.showInfo(
            context,
            'Excluded $successCount formula segment(s)${failCount > 0 ? ' ($failCount failed)' : ''}',
          );
        }
      } else {
        for (final index in formulaSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Formula unexclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.unexcludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to unexclude formula segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          if (failCount > 0) {
            MessageService.showWarning(
              context,
              'Unexcluded $successCount formula segment(s), $failCount failed',
            );
          } else {
            MessageService.showInfo(
              context,
              'Unexcluded $successCount formula segment(s)',
            );
          }
        }
      }

      // Skip backend refresh if superseded
      if (exclusionOperationGeneration != myGeneration) {
        AppLogger.log(
          'ExtractPreview',
          'Formula exclusion post-sync skipped: superseded '
              '(my=$myGeneration, current=$exclusionOperationGeneration)',
          level: LogLevel.info,
        );
        return;
      }

      // After unexclude, refresh excluded segments from backend
      if (mounted && !exclude) {
        try {
          final Map<String, dynamic> statusData =
              await svc.getStatus(extractWidget.taskId);
          if (exclusionOperationGeneration != myGeneration) return;
          final Map<String, dynamic>? segmentsMetadata =
              statusData['segments_metadata'] as Map<String, dynamic>?;
          if (segmentsMetadata != null) {
            final List<dynamic>? excludedIndicesList =
                segmentsMetadata['excluded_segment_indices'] as List<dynamic>?;
            if (excludedIndicesList != null) {
              Set<int> backendExcluded =
                  excludedIndicesList.map((idx) => idx as int).toSet();
              final List<dynamic>? userUnexcludedList =
                  segmentsMetadata['user_unexcluded_segments']
                      as List<dynamic>?;
              if (userUnexcludedList != null && userUnexcludedList.isNotEmpty) {
                final Set<int> userUnexcluded =
                    userUnexcludedList.map((idx) => idx as int).toSet();
                backendExcluded = backendExcluded.difference(userUnexcluded);
              }
              if (exclusionOperationGeneration == myGeneration) {
                final ExcludedSegmentsNotifier excludedNotifier = ref
                    .read(excludedSegmentsProviderFamily(providerKey).notifier);
                excludedNotifier.setExcluded(backendExcluded);
              }
            }
          }
        } catch (e) {
          AppLogger.log(
            'ExtractPreview',
            'Failed to refresh excluded segments after formula unexclude: $e',
            level: LogLevel.warn,
          );
        }
      }

      // Trigger UI refresh (pagination sync is handled by handleCategoryExclusionChanged)
      if (mounted && exclusionOperationGeneration == myGeneration) {
        setState(() {});
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Error in handleExcludeFormulaSegments: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to ${exclude ? "exclude" : "unexclude"} formula segments: $e',
        );
      }
    } finally {
      endExclusionUpdate(ref, providerKey);
    }
  }

  Future<void> handleExcludeTableSegments(bool exclude) async {
    final ExtractPreview extractWidget = widget as ExtractPreview;
    final int myGeneration = exclusionOperationGeneration;
    AppLogger.log(
      'ExtractPreview',
      '_handleExcludeTableSegments called: exclude=$exclude, '
          'tableSegmentCount=${tableSegmentIndices.length}, '
          'generation=$myGeneration, taskId=${extractWidget.taskId}',
      level: LogLevel.info,
    );

    final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
    try {
      beginExclusionUpdate(ref, providerKey);
      if (tableSegmentIndices.isEmpty) {
        AppLogger.log(
          'ExtractPreview',
          'No table segments found (tableSegmentIndices is empty)',
          level: LogLevel.warn,
        );
        return;
      }

      // Use cached set for O(1) lookups (avoids List.toSet() allocation)
      final Set<int> tableSegments = indexSetFor('table');

      // Optimistic update
      if (mounted) {
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> optimisticExcluded;
        if (exclude) {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = <int>{...currentExcluded, ...tableSegments};
        } else {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = currentExcluded.difference(tableSegments);
        }

        excludedNotifier.setExcluded(optimisticExcluded);

        for (final index in tableSegments) {
          if (exclude) {
            segmentExclusionReasons[index] = ExclusionReason.table.value;
          } else {
            segmentExclusionReasons.remove(index);
            segmentExclusionMetadata.remove(index);
          }
        }

        setState(() {});

        AppLogger.log(
          'ExtractPreview',
          'Optimistic update: exclude=$exclude, '
              'updated ${tableSegments.length} table segments immediately for instant UI feedback',
          level: LogLevel.info,
        );

        // CRITICAL: When filter is active, refresh pagination immediately after
        // optimistic update so the filtered list reflects the change right away.
        if (filterMode == 'rebuild' && selectedExclusionFilters.isNotEmpty) {
          clearFilteredCountCache();
          await paginationController.loadFirstPage();
        }
      }

      final TranslationService svc = TranslationService();
      int successCount = 0;
      int failCount = 0;

      if (exclude) {
        for (final index in tableSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Table exclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.excludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to exclude table segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          MessageService.showInfo(
            context,
            'Excluded $successCount table segment(s)${failCount > 0 ? ' ($failCount failed)' : ''}',
          );
        }
      } else {
        for (final index in tableSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Table unexclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.unexcludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to unexclude table segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          if (failCount > 0) {
            MessageService.showWarning(
              context,
              'Unexcluded $successCount table segment(s), $failCount failed (content-based exclusions cannot be removed)',
            );
          } else {
            MessageService.showInfo(
              context,
              'Unexcluded $successCount table segment(s)',
            );
          }
        }
      }

      // Skip backend refresh if superseded
      if (exclusionOperationGeneration != myGeneration) {
        AppLogger.log(
          'ExtractPreview',
          'Table exclusion post-sync skipped: superseded '
              '(my=$myGeneration, current=$exclusionOperationGeneration)',
          level: LogLevel.info,
        );
        return;
      }

      Set<int>? backendExcluded;
      if (mounted && !exclude) {
        try {
          final Map<String, dynamic> statusData =
              await svc.getStatus(extractWidget.taskId);
          if (exclusionOperationGeneration != myGeneration) return;
          final Map<String, dynamic>? segmentsMetadata =
              statusData['segments_metadata'] as Map<String, dynamic>?;

          if (segmentsMetadata != null) {
            final List<dynamic>? excludedIndicesList =
                segmentsMetadata['excluded_segment_indices'] as List<dynamic>?;
            backendExcluded = excludedIndicesList != null
                ? excludedIndicesList.map((idx) => idx as int).toSet()
                : <int>{};
            final List<dynamic>? userUnexcludedList =
                segmentsMetadata['user_unexcluded_segments'] as List<dynamic>?;
            if (userUnexcludedList != null && userUnexcludedList.isNotEmpty) {
              final Set<int> userUnexcluded =
                  userUnexcludedList.map((idx) => idx as int).toSet();
              backendExcluded = backendExcluded.difference(userUnexcluded);
            }

            AppLogger.log(
              'ExtractPreview',
              'Refreshed excluded segments from backend after unexclude: '
                  'backend excluded count=${backendExcluded.length}, table segments=${tableSegments.length}',
              level: LogLevel.info,
            );
          }
        } catch (e) {
          AppLogger.log(
            'ExtractPreview',
            'Failed to refresh excluded segments from backend after unexclude: $e',
            level: LogLevel.warn,
          );
        }
      }

      // Final sync — only if still the latest operation
      if (mounted && exclusionOperationGeneration == myGeneration) {
        final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> finalExcluded;
        if (exclude) {
          if (failCount > 0) {
            try {
              final Map<String, dynamic> statusData =
                  await svc.getStatus(extractWidget.taskId);
              if (exclusionOperationGeneration != myGeneration) return;
              final Map<String, dynamic>? segmentsMetadata =
                  statusData['segments_metadata'] as Map<String, dynamic>?;
              if (segmentsMetadata != null) {
                final List<dynamic>? excludedIndicesList =
                    segmentsMetadata['excluded_segment_indices']
                        as List<dynamic>?;
                if (excludedIndicesList != null) {
                  finalExcluded =
                      excludedIndicesList.map((idx) => idx as int).toSet();
                  excludedNotifier.setExcluded(finalExcluded);
                  AppLogger.log(
                    'ExtractPreview',
                    'Synced excluded segments with backend after partial failures: '
                        'backend excluded count=${finalExcluded.length}',
                    level: LogLevel.info,
                  );
                }
              }
            } catch (e) {
              AppLogger.log(
                'ExtractPreview',
                'Failed to sync with backend after partial failures: $e',
                level: LogLevel.warn,
              );
            }
          }
        } else {
          if (backendExcluded != null) {
            finalExcluded = backendExcluded;
            excludedNotifier.setExcluded(finalExcluded);
            AppLogger.log(
              'ExtractPreview',
              'Synced excluded segments with backend after unexclude: '
                  'backend excluded count=${finalExcluded.length}',
              level: LogLevel.info,
            );
          }
        }

        AppLogger.log(
          'ExtractPreview',
          'Final table exclusion state: exclude=$exclude, '
              'success=$successCount, failed=$failCount',
          level: LogLevel.info,
        );
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Error handling table exclusion: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Error handling table exclusion: $e',
        );
      }
    } finally {
      endExclusionUpdate(ref, providerKey);
    }
  }

  /// Handle exclude/unexclude chart segments in bulk
  Future<void> handleExcludeChartSegments(bool exclude) async {
    final ExtractPreview extractWidget = widget as ExtractPreview;
    final int myGeneration = exclusionOperationGeneration;
    AppLogger.log(
      'ExtractPreview',
      '_handleExcludeChartSegments called: exclude=$exclude, '
          'chartSegmentCount=${chartSegmentIndices.length}, '
          'generation=$myGeneration, taskId=${extractWidget.taskId}',
      level: LogLevel.info,
    );

    final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
    try {
      beginExclusionUpdate(ref, providerKey);
      if (chartSegmentIndices.isEmpty) {
        AppLogger.log(
          'ExtractPreview',
          'No chart segments found (chartSegmentIndices is empty)',
          level: LogLevel.warn,
        );
        return;
      }

      // Use cached set for O(1) lookups (avoids List.toSet() allocation)
      final Set<int> chartSegments = indexSetFor('chart');

      // Optimistic update
      if (mounted) {
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> optimisticExcluded;
        if (exclude) {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = <int>{...currentExcluded, ...chartSegments};
        } else {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = currentExcluded.difference(chartSegments);
        }

        excludedNotifier.setExcluded(optimisticExcluded);

        for (final index in chartSegments) {
          if (exclude) {
            segmentExclusionReasons[index] = ExclusionReason.chart.value;
          } else {
            segmentExclusionReasons.remove(index);
            segmentExclusionMetadata.remove(index);
          }
        }

        setState(() {});

        AppLogger.log(
          'ExtractPreview',
          'Optimistic update: exclude=$exclude, '
              'updated ${chartSegments.length} chart segments immediately for instant UI feedback',
          level: LogLevel.info,
        );

        // CRITICAL: When filter is active, refresh pagination immediately after
        // optimistic update so the filtered list reflects the change right away.
        if (filterMode == 'rebuild' && selectedExclusionFilters.isNotEmpty) {
          clearFilteredCountCache();
          await paginationController.loadFirstPage();
        }
      }

      final TranslationService svc = TranslationService();
      int successCount = 0;
      int failCount = 0;

      if (exclude) {
        for (final index in chartSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Chart exclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.excludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to exclude chart segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          MessageService.showInfo(
            context,
            'Excluded $successCount chart segment(s)${failCount > 0 ? ' ($failCount failed)' : ''}',
          );
        }
      } else {
        for (final index in chartSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Chart unexclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.unexcludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to unexclude chart segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          if (failCount > 0) {
            MessageService.showWarning(
              context,
              'Unexcluded $successCount chart segment(s), $failCount failed (content-based exclusions cannot be removed)',
            );
          } else {
            MessageService.showInfo(
              context,
              'Unexcluded $successCount chart segment(s)',
            );
          }
        }
      }

      // Skip backend refresh if superseded
      if (exclusionOperationGeneration != myGeneration) {
        AppLogger.log(
          'ExtractPreview',
          'Chart exclusion post-sync skipped: superseded '
              '(my=$myGeneration, current=$exclusionOperationGeneration)',
          level: LogLevel.info,
        );
        return;
      }

      Set<int>? backendExcluded;
      if (mounted && !exclude) {
        try {
          final Map<String, dynamic> statusData =
              await svc.getStatus(extractWidget.taskId);
          if (exclusionOperationGeneration != myGeneration) return;
          final Map<String, dynamic>? segmentsMetadata =
              statusData['segments_metadata'] as Map<String, dynamic>?;

          if (segmentsMetadata != null) {
            final List<dynamic>? excludedIndicesList =
                segmentsMetadata['excluded_segment_indices'] as List<dynamic>?;
            backendExcluded = excludedIndicesList != null
                ? excludedIndicesList.map((idx) => idx as int).toSet()
                : <int>{};
            final List<dynamic>? userUnexcludedList =
                segmentsMetadata['user_unexcluded_segments'] as List<dynamic>?;
            if (userUnexcludedList != null && userUnexcludedList.isNotEmpty) {
              final Set<int> userUnexcluded =
                  userUnexcludedList.map((idx) => idx as int).toSet();
              backendExcluded = backendExcluded.difference(userUnexcluded);
            }

            AppLogger.log(
              'ExtractPreview',
              'Refreshed excluded segments from backend after unexclude: '
                  'backend excluded count=${backendExcluded.length}, chart segments=${chartSegments.length}',
              level: LogLevel.info,
            );
          }
        } catch (e) {
          AppLogger.log(
            'ExtractPreview',
            'Failed to refresh excluded segments from backend after unexclude: $e',
            level: LogLevel.warn,
          );
        }
      }

      // Final sync — only if still the latest operation
      if (mounted && exclusionOperationGeneration == myGeneration) {
        final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> finalExcluded;
        if (exclude) {
          if (failCount > 0) {
            try {
              final Map<String, dynamic> statusData =
                  await svc.getStatus(extractWidget.taskId);
              if (exclusionOperationGeneration != myGeneration) return;
              final Map<String, dynamic>? segmentsMetadata =
                  statusData['segments_metadata'] as Map<String, dynamic>?;
              if (segmentsMetadata != null) {
                final List<dynamic>? excludedIndicesList =
                    segmentsMetadata['excluded_segment_indices']
                        as List<dynamic>?;
                if (excludedIndicesList != null) {
                  finalExcluded =
                      excludedIndicesList.map((idx) => idx as int).toSet();
                  excludedNotifier.setExcluded(finalExcluded);
                  AppLogger.log(
                    'ExtractPreview',
                    'Synced excluded segments with backend after partial failures: '
                        'backend excluded count=${finalExcluded.length}',
                    level: LogLevel.info,
                  );
                }
              }
            } catch (e) {
              AppLogger.log(
                'ExtractPreview',
                'Failed to sync with backend after partial failures: $e',
                level: LogLevel.warn,
              );
            }
          }
        } else {
          if (backendExcluded != null) {
            finalExcluded = backendExcluded;
            excludedNotifier.setExcluded(finalExcluded);
            AppLogger.log(
              'ExtractPreview',
              'Synced excluded segments with backend after unexclude: '
                  'backend excluded count=${finalExcluded.length}',
              level: LogLevel.info,
            );
          }
        }

        AppLogger.log(
          'ExtractPreview',
          'Final chart exclusion state: exclude=$exclude, '
              'success=$successCount, failed=$failCount',
          level: LogLevel.info,
        );
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Error handling chart exclusion: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Error handling chart exclusion: $e',
        );
      }
    } finally {
      endExclusionUpdate(ref, providerKey);
    }
  }

  /// Handle exclude/unexclude user-selected segments in bulk
  /// This includes both user_selected and unknown segments (merged together)
  Future<void> handleExcludeUserSelectedSegments(bool exclude) async {
    final ExtractPreview extractWidget = widget as ExtractPreview;
    final int myGeneration = exclusionOperationGeneration;
    AppLogger.log(
      'ExtractPreview',
      '_handleExcludeUserSelectedSegments called: exclude=$exclude, '
          'userSelectedSegmentCount=${userSelectedSegmentIndices.length}, '
          'generation=$myGeneration, taskId=${extractWidget.taskId}',
      level: LogLevel.info,
    );

    final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
    try {
      beginExclusionUpdate(ref, providerKey);
      // Use cached set for O(1) lookups (avoids List.toSet() allocation)
      final Set<int> userSelectedSegments = indexSetFor('user_selected');

      if (userSelectedSegments.isEmpty) {
        AppLogger.log(
          'ExtractPreview',
          'No user-selected segments to ${exclude ? "exclude" : "unexclude"}',
          level: LogLevel.warn,
        );
        return;
      }

      // Optimistic update
      if (mounted) {
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> optimisticExcluded;
        if (exclude) {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = <int>{
            ...currentExcluded,
            ...userSelectedSegments,
          };
        } else {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = currentExcluded.difference(userSelectedSegments);
        }

        excludedNotifier.setExcluded(optimisticExcluded);

        for (final index in userSelectedSegments) {
          if (exclude) {
            segmentExclusionReasons[index] = ExclusionReason.userSelected.value;
          } else {
            segmentExclusionReasons.remove(index);
            segmentExclusionMetadata.remove(index);
          }
        }

        setState(() {});

        AppLogger.log(
          'ExtractPreview',
          'Optimistic update: exclude=$exclude, '
              'updated ${userSelectedSegments.length} user-selected segments immediately',
          level: LogLevel.info,
        );

        // CRITICAL: When filter is active, refresh pagination immediately after
        // optimistic update so the filtered list reflects the change right away.
        if (filterMode == 'rebuild' && selectedExclusionFilters.isNotEmpty) {
          clearFilteredCountCache();
          await paginationController.loadFirstPage();
        }
      }

      final TranslationService svc = TranslationService();
      int successCount = 0;
      int failCount = 0;

      if (exclude) {
        for (final index in userSelectedSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'UserSelected exclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.excludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to exclude user selected segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          MessageService.showInfo(
            context,
            'Excluded $successCount user selected segment(s)${failCount > 0 ? ' ($failCount failed)' : ''}',
          );
        }
      } else {
        for (final index in userSelectedSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'UserSelected unexclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.unexcludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to unexclude user selected segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          MessageService.showInfo(
            context,
            'Unexcluded $successCount user selected segment(s)${failCount > 0 ? ' ($failCount failed)' : ''}',
          );
        }
      }

      // Skip backend refresh if superseded
      if (exclusionOperationGeneration != myGeneration) {
        AppLogger.log(
          'ExtractPreview',
          'UserSelected exclusion post-sync skipped: superseded '
              '(my=$myGeneration, current=$exclusionOperationGeneration)',
          level: LogLevel.info,
        );
        return;
      }

      Set<int>? backendExcluded;
      if (mounted && !exclude) {
        try {
          final Map<String, dynamic> statusData =
              await svc.getStatus(extractWidget.taskId);
          if (exclusionOperationGeneration != myGeneration) return;
          final Map<String, dynamic>? segmentsMetadata =
              statusData['segments_metadata'] as Map<String, dynamic>?;
          if (segmentsMetadata != null) {
            final List<dynamic>? excludedIndicesList =
                segmentsMetadata['excluded_segment_indices'] as List<dynamic>?;
            if (excludedIndicesList != null) {
              backendExcluded =
                  excludedIndicesList.map((idx) => idx as int).toSet();
              AppLogger.log(
                'ExtractPreview',
                'Refreshed excluded segments from backend after unexclude: '
                    'backend excluded count=${backendExcluded.length}',
                level: LogLevel.info,
              );
            }
          }
        } catch (e) {
          AppLogger.log(
            'ExtractPreview',
            'Failed to refresh excluded segments from backend after unexclude: $e',
            level: LogLevel.warn,
          );
        }
      }

      // Final sync — only if still the latest operation
      if (mounted && exclusionOperationGeneration == myGeneration) {
        final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> finalExcluded;
        if (exclude) {
          if (failCount > 0) {
            try {
              final Map<String, dynamic> statusData =
                  await svc.getStatus(extractWidget.taskId);
              if (exclusionOperationGeneration != myGeneration) return;
              final Map<String, dynamic>? segmentsMetadata =
                  statusData['segments_metadata'] as Map<String, dynamic>?;
              if (segmentsMetadata != null) {
                final List<dynamic>? excludedIndicesList =
                    segmentsMetadata['excluded_segment_indices']
                        as List<dynamic>?;
                if (excludedIndicesList != null) {
                  finalExcluded =
                      excludedIndicesList.map((idx) => idx as int).toSet();
                  excludedNotifier.setExcluded(finalExcluded);
                  AppLogger.log(
                    'ExtractPreview',
                    'Synced excluded segments with backend after partial failures: '
                        'backend excluded count=${finalExcluded.length}',
                    level: LogLevel.info,
                  );
                }
              }
            } catch (e) {
              AppLogger.log(
                'ExtractPreview',
                'Failed to sync with backend after partial failures: $e',
                level: LogLevel.warn,
              );
            }
          }
        } else {
          if (backendExcluded != null) {
            finalExcluded = backendExcluded;
            excludedNotifier.setExcluded(finalExcluded);
            AppLogger.log(
              'ExtractPreview',
              'Synced excluded segments with backend after unexclude: '
                  'backend excluded count=${finalExcluded.length}',
              level: LogLevel.info,
            );
          }
        }

        AppLogger.log(
          'ExtractPreview',
          'Final user-selected exclusion state: exclude=$exclude, '
              'success=$successCount, failed=$failCount',
          level: LogLevel.info,
        );
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Error handling user selected exclusion: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Error handling user selected exclusion: $e',
        );
      }
    } finally {
      endExclusionUpdate(ref, providerKey);
    }
  }

  /// Handle exclude/unexclude reference segments in bulk
  /// Similar to Identifier, this uses individual API calls with optimistic update
  /// This supports all formats (EPUB, PDF, DOCX, etc.), unlike _applyExcludeReferencesState which only works for PDF/DOCX
  Future<void> handleExcludeReferenceSegments(bool exclude) async {
    final ExtractPreview extractWidget = widget as ExtractPreview;
    final int myGeneration = exclusionOperationGeneration;
    AppLogger.log(
      'ExtractPreview',
      '_handleExcludeReferenceSegments called: exclude=$exclude, '
          'referenceSegmentCount=${referenceSegmentIndices.length}, '
          'generation=$myGeneration, taskId=${extractWidget.taskId}',
      level: LogLevel.info,
    );

    final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
    try {
      beginExclusionUpdate(ref, providerKey);
      // Use cached set for O(1) lookups (avoids List.toSet() allocation)
      final Set<int> referenceSegments = indexSetFor('reference');

      if (referenceSegments.isEmpty) {
        AppLogger.log(
          'ExtractPreview',
          'No reference segments found (referenceSegments is empty)',
          level: LogLevel.warn,
        );
        return;
      }

      // Optimistic update
      if (mounted) {
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> optimisticExcluded;
        if (exclude) {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = <int>{
            ...currentExcluded,
            ...referenceSegments,
          };
        } else {
          final Set<int> currentExcluded =
              ref.read(excludedSegmentsProviderFamily(providerKey));
          optimisticExcluded = currentExcluded.difference(referenceSegments);
        }

        excludedNotifier.setExcluded(optimisticExcluded);

        for (final index in referenceSegments) {
          if (exclude) {
            segmentExclusionReasons[index] = ExclusionReason.reference.value;
          } else {
            segmentExclusionReasons.remove(index);
            segmentExclusionMetadata.remove(index);
          }
        }

        setState(() {});

        AppLogger.log(
          'ExtractPreview',
          'Optimistic update: exclude=$exclude, '
              'updated ${referenceSegments.length} reference segments immediately',
          level: LogLevel.info,
        );

        // CRITICAL: When filter is active, refresh pagination immediately after
        // optimistic update so the filtered list reflects the change right away.
        if (filterMode == 'rebuild' && selectedExclusionFilters.isNotEmpty) {
          clearFilteredCountCache();
          await paginationController.loadFirstPage();
        }
      }

      final TranslationService svc = TranslationService();
      int successCount = 0;
      int failCount = 0;

      if (exclude) {
        for (final index in referenceSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Reference exclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.excludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to exclude reference segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          MessageService.showInfo(
            context,
            'Excluded $successCount reference segment(s)${failCount > 0 ? ' ($failCount failed)' : ''}',
          );
        }
      } else {
        for (final index in referenceSegments) {
          if (exclusionOperationGeneration != myGeneration) {
            AppLogger.log(
              'ExtractPreview',
              'Reference unexclude aborted: superseded by newer operation '
                  '(my=$myGeneration, current=$exclusionOperationGeneration)',
              level: LogLevel.info,
            );
            return;
          }
          try {
            await svc.unexcludeSegment(extractWidget.taskId, index);
            successCount++;
          } catch (e) {
            AppLogger.log(
              'ExtractPreview',
              'Failed to unexclude reference segment $index: $e',
              level: LogLevel.warn,
            );
            failCount++;
          }
        }
        if (mounted && exclusionOperationGeneration == myGeneration) {
          if (failCount > 0) {
            MessageService.showWarning(
              context,
              'Unexcluded $successCount reference segment(s), $failCount failed',
            );
          } else {
            MessageService.showInfo(
              context,
              'Unexcluded $successCount reference segment(s)',
            );
          }
        }
      }

      // Skip backend refresh if superseded
      if (exclusionOperationGeneration != myGeneration) {
        AppLogger.log(
          'ExtractPreview',
          'Reference exclusion post-sync skipped: superseded '
              '(my=$myGeneration, current=$exclusionOperationGeneration)',
          level: LogLevel.info,
        );
        return;
      }

      Set<int>? backendExcluded;
      if (mounted && !exclude) {
        try {
          final Map<String, dynamic> statusData =
              await svc.getStatus(extractWidget.taskId);
          if (exclusionOperationGeneration != myGeneration) return;
          final Map<String, dynamic>? segmentsMetadata =
              statusData['segments_metadata'] as Map<String, dynamic>?;
          if (segmentsMetadata != null) {
            final List<dynamic>? excludedIndicesList =
                segmentsMetadata['excluded_segment_indices'] as List<dynamic>?;
            if (excludedIndicesList != null) {
              backendExcluded =
                  excludedIndicesList.map((idx) => idx as int).toSet();
              AppLogger.log(
                'ExtractPreview',
                'Refreshed excluded segments from backend after unexclude: '
                    'backend excluded count=${backendExcluded.length}',
                level: LogLevel.info,
              );
            }
          }
        } catch (e) {
          AppLogger.log(
            'ExtractPreview',
            'Failed to refresh excluded segments from backend after unexclude: $e',
            level: LogLevel.warn,
          );
        }
      }

      // Final sync — only if still the latest operation
      if (mounted && exclusionOperationGeneration == myGeneration) {
        final String providerKey = extractWidget.flowId ?? extractWidget.taskId;
        final ExcludedSegmentsNotifier excludedNotifier =
            ref.read(excludedSegmentsProviderFamily(providerKey).notifier);

        Set<int> finalExcluded;
        if (exclude) {
          if (failCount > 0) {
            try {
              final Map<String, dynamic> statusData =
                  await svc.getStatus(extractWidget.taskId);
              if (exclusionOperationGeneration != myGeneration) return;
              final Map<String, dynamic>? segmentsMetadata =
                  statusData['segments_metadata'] as Map<String, dynamic>?;
              if (segmentsMetadata != null) {
                final List<dynamic>? excludedIndicesList =
                    segmentsMetadata['excluded_segment_indices']
                        as List<dynamic>?;
                if (excludedIndicesList != null) {
                  finalExcluded =
                      excludedIndicesList.map((idx) => idx as int).toSet();
                  excludedNotifier.setExcluded(finalExcluded);
                  AppLogger.log(
                    'ExtractPreview',
                    'Synced excluded segments with backend after partial failures: '
                        'backend excluded count=${finalExcluded.length}',
                    level: LogLevel.info,
                  );
                }
              }
            } catch (e) {
              AppLogger.log(
                'ExtractPreview',
                'Failed to sync with backend after partial failures: $e',
                level: LogLevel.warn,
              );
            }
          }
        } else {
          if (backendExcluded != null) {
            finalExcluded = backendExcluded;
            excludedNotifier.setExcluded(finalExcluded);
            AppLogger.log(
              'ExtractPreview',
              'Synced excluded segments with backend after unexclude: '
                  'backend excluded count=${finalExcluded.length}',
              level: LogLevel.info,
            );
          }
        }

        AppLogger.log(
          'ExtractPreview',
          'Final reference exclusion state: exclude=$exclude, '
              'success=$successCount, failed=$failCount',
          level: LogLevel.info,
        );
      }
    } catch (e) {
      AppLogger.log(
        'ExtractPreview',
        'Error handling reference exclusion: $e',
        level: LogLevel.error,
      );
      if (mounted) {
        MessageService.showError(
          context,
          'Error handling reference exclusion: $e',
        );
      }
    } finally {
      endExclusionUpdate(ref, providerKey);
    }
  }
}
