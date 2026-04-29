import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/utils/paginated_scroll_manager.dart';
import '../../../../shared/utils/pagination.dart';
import '../../utils/segment_height_cache.dart';

/// Mixin for managing ExtractPreview state variables
///
/// This mixin centralizes all state variable definitions for the ExtractPreview widget.
/// It provides a clean separation of state management from business logic.
mixin ExtractPreviewStateMixin<T extends ConsumerStatefulWidget>
    on ConsumerState<T> {
  // ============================================================================
  // Segment Data
  // ============================================================================

  /// Left panel: Segments (Deep split fragments, same as Translate's Source Text)
  List<String> allSegments = <String>[];

  /// Separators between segments
  List<String> allSeparators = <String>[];

  /// Right panel: Chunks (Merged segments for translation)
  List<String> allChunks = <String>[];

  // ============================================================================
  // Exclusion Data
  // ============================================================================

  /// Store exclusion reasons for each segment (index -> exclusion_reason)
  Map<int, String> segmentExclusionReasons = <int, String>{};

  /// Store exclusion metadata for each segment (index -> exclusion_metadata)
  Map<int, Map<String, dynamic>> segmentExclusionMetadata =
      <int, Map<String, dynamic>>{};

  /// Store segment types for all segments (index -> type info)
  /// This is used for statistics and filtering based on type, not exclusion status
  Map<int, Map<String, dynamic>> segmentTypeInfo =
      <int, Map<String, dynamic>>{};

  // ============================================================================
  // Segment Type Indices
  // ============================================================================

  /// Track reference segments and exclusion state
  List<int> referenceSegmentIndices = <int>[];
  bool excludeReferences = true; // Default to exclude references

  /// Track header and footer segments and exclusion state
  List<int> headerSegmentIndices = <int>[];
  List<int> footerSegmentIndices = <int>[];
  bool excludeHeaders = false; // Default to NOT exclude headers
  bool excludeFooters = false; // Default to NOT exclude footers

  /// Track table segments and exclusion state
  List<int> tableSegmentIndices = <int>[];

  /// Track formula segments (for checkbox and filtering)
  List<int> formulaSegmentIndices = <int>[];

  /// Track identifier segments (for checkbox and filtering)
  List<int> identifierSegmentIndices = <int>[];

  /// Track language-matched segments (for checkbox and filtering)
  List<int> languageMatchedSegmentIndices = <int>[];

  /// Track user-selected segments (for checkbox and filtering)
  List<int> userSelectedSegmentIndices = <int>[];

  // ============================================================================
  // Cached Sets for O(1) Containment Checks (Performance)
  // ============================================================================
  // The List<int> fields above are the source-of-truth populated during segment
  // loading. These cached Sets mirror them for O(1) `.contains()` in hot loops
  // (matchesFilter, getCategoryExclusionStates) which iterate up to 100K+
  // segments.  Invalidated lazily via _indexSetsGeneration.

  int _indexSetsGeneration = 0;
  int _indexSetsCachedGeneration = -1;

  Set<int> _referenceSet = const <int>{};
  Set<int> _headerSet = const <int>{};
  Set<int> _footerSet = const <int>{};
  Set<int> _tableSet = const <int>{};
  Set<int> _formulaSet = const <int>{};
  Set<int> _identifierSet = const <int>{};
  Set<int> _languageMatchedSet = const <int>{};
  Set<int> _userSelectedSet = const <int>{};

  /// Call after modifying any *SegmentIndices list so cached Sets are rebuilt.
  void invalidateIndexSets() {
    _indexSetsGeneration++;
  }

  /// Ensure cached Sets match the current Lists (lazy rebuild).
  void _ensureIndexSets() {
    if (_indexSetsCachedGeneration == _indexSetsGeneration) return;
    _referenceSet = referenceSegmentIndices.toSet();
    _headerSet = headerSegmentIndices.toSet();
    _footerSet = footerSegmentIndices.toSet();
    _tableSet = tableSegmentIndices.toSet();
    _formulaSet = formulaSegmentIndices.toSet();
    _identifierSet = identifierSegmentIndices.toSet();
    _languageMatchedSet = languageMatchedSegmentIndices.toSet();
    _userSelectedSet = userSelectedSegmentIndices.toSet();
    _indexSetsCachedGeneration = _indexSetsGeneration;
  }

  /// O(1) containment check against the cached set for a category.
  bool indexSetContains(String category, int index) {
    _ensureIndexSets();
    switch (category) {
      case 'reference':
        return _referenceSet.contains(index);
      case 'header':
        return _headerSet.contains(index);
      case 'footer':
        return _footerSet.contains(index);
      case 'table':
        return _tableSet.contains(index);
      case 'formula':
        return _formulaSet.contains(index);
      case 'identifier':
        return _identifierSet.contains(index);
      case 'language_match':
        return _languageMatchedSet.contains(index);
      case 'user_selected':
        return _userSelectedSet.contains(index);
      default:
        return false;
    }
  }

  /// Return the cached Set for a given category (for batch operations).
  Set<int> indexSetFor(String category) {
    _ensureIndexSets();
    switch (category) {
      case 'reference':
        return _referenceSet;
      case 'header':
        return _headerSet;
      case 'footer':
        return _footerSet;
      case 'table':
        return _tableSet;
      case 'formula':
        return _formulaSet;
      case 'identifier':
        return _identifierSet;
      case 'language_match':
        return _languageMatchedSet;
      case 'user_selected':
        return _userSelectedSet;
      default:
        return const <int>{};
    }
  }

  // ============================================================================
  // Language Match State
  // ============================================================================

  /// Track language-based exclusion state for current target language
  String? currentTargetLangForExclusion;
  bool isLanguageExclusionActive = false;

  /// Count of segments matching target language
  int languageMatchedSegmentCount = 0;

  /// Flag to prevent concurrent calls to validateAndRefreshExclusionsForTargetLang
  bool isValidatingExclusions = false;

  /// Generation counter for bulk exclusion operations.
  /// Incremented when a new bulk exclude/unexclude starts so the previous
  /// in-flight operation can detect it was superseded and abort early.
  int exclusionOperationGeneration = 0;

  // ============================================================================
  // Exclusion Panel State
  // ============================================================================

  /// Selected exclusion filters
  Set<String> selectedExclusionFilters = <String>{};

  /// Category exclusion states (for checkboxes)
  Map<String, bool> categoryExclusionStates = <String, bool>{};

  /// Filter mode: 'rebuild' (default) or 'page'
  String filterMode = 'rebuild';

  /// Cached filtered segment indices for rebuild mode
  List<int>? filteredSegmentIndices;

  /// Cached filtered segment count for page mode (performance optimization)
  /// Cache key: (selectedExclusionFilters, excludedSegments.length, allSegments.length)
  /// Note: Made non-private so ExtractPreviewExclusionHandlerMixin can access it
  int? cachedFilteredCount;
  Set<String>? cachedFilteredCountFilters;
  int? cachedFilteredCountExcludedLength;
  int? cachedFilteredCountSegmentsLength;

  /// Whether exclusion panel is expanded
  bool isExclusionPanelExpanded = false;

  // ============================================================================
  // UI State
  // ============================================================================

  /// Highlighted segment index
  int? highlightedIndex;

  /// Scroll controllers
  final ScrollController segmentsScrollController = ScrollController();
  final ScrollController chunksScrollController = ScrollController();

  /// Segment keys for scroll management
  final Map<int, GlobalKey> segmentKeys =
      <int, GlobalKey<State<StatefulWidget>>>{};

  /// Scroll manager for maintaining scroll position during pagination
  PaginatedScrollManager? segmentsScrollManager;
  SegmentHeightCache? segmentsHeightCache;

  // ============================================================================
  // Pagination Controllers
  // ============================================================================

  /// Pagination controller for segments (left panel)
  late PagedListController<String> paginationController;

  /// Pagination controller for chunks (right panel)
  late PagedListController<String> chunksPaginationController;

  // ============================================================================
  // Preparation Progress
  // ============================================================================

  /// Preparation (upload + splitting) progress
  bool isPreparing = true;
  double prepareProgress = 0;
  String prepareStatus = 'Preparing...';
  String prepareTaskType =
      ''; // Current task type (e.g., "Detect Identifier", "Detect Language")
  String prepareErrorMessage = '';
  Timer? prepareTimer;
  bool prepareInFlight = false;
  bool initialDataLoaded = false;

  /// Simulated progress that increases by 1% per second up to 90%
  int simulatedProgressPercent = 0;

  /// PDF split extraction part tracking (e.g. Part 3/12)
  int extractPdfPartCurrent = 0;
  int extractPdfPartTotal = 0;
  int lastExtractPdfPartCurrent = 0;

  // ============================================================================
  // Translation Progress (Translate Phase)
  // ============================================================================
  // These variables track the translation phase progress (AI translation stage).
  // They are separate from Extract phase (prepareProgress) and Anonymize phase.

  /// Whether translation phase is active
  bool isTranslating = false;

  /// Translation progress (0.0-1.0)
  double translationProgress = 0;

  /// Translation status message
  String translationStatus = '';

  /// Translation progress timer (independent from Extract timer)
  Timer? translationTimer;
  bool translationInFlight = false;
  int? translationInFlightStartTime; // Track when translationInFlight was set
  String?
      currentTranslationTaskId; // Track which taskId we're polling for translation

  // ============================================================================
  // Anonymization Progress (Anonymize Workflow)
  // ============================================================================
  // These variables track the anonymization workflow progress.
  // This is a separate workflow from translation, used for anonymization tasks.

  /// Whether anonymization workflow is active
  bool isAnonymizing = false;

  /// Anonymization progress (0.0-1.0)
  double anonymizeProgress = 0;

  /// Anonymization status message
  String anonymizeStatus = '';

  /// Progress timer for anonymization workflow
  Timer? progressTimer;
  bool progressInFlight = false;
  String?
      currentPollingWorkflowId; // Track which workflowId we're polling for anonymization

  // ============================================================================
  // Other State
  // ============================================================================

  /// Total estimated input tokens
  int? totalEstimatedInputTokens;

  /// Track last known chunk_size to detect changes
  int? lastKnownChunkSize;

  /// Track last view size to detect size changes
  Size? lastViewSize;

  /// Track last refresh trigger to detect refresh requests
  int? lastRefreshTrigger;

  /// Track if toolbar debug logs have been output for current taskId
  String? lastToolbarLogTaskId;

  /// Track last pagination offset to detect real changes
  int? lastPaginationOffset;

  /// Track last ListView itemCount to detect changes
  int? lastListViewItemCount;

  /// Track if MinerU settings dialog has been shown for this error
  bool hasShownMineruSettingsDialog = false;

  /// Image data map: {placeholder_id: {"data": "data:image/jpeg;base64,...", "alt": "title"}}
  Map<String, Map<String, String>> imageDataMap =
      <String, Map<String, String>>{};

  // ============================================================================
  // Search State
  // ============================================================================

  /// Whether search box is visible
  bool isSearchBoxVisible = false;

  /// Current search query
  String searchQuery = '';

  /// List of segment indices that match the search query
  List<int> searchMatchIndices = <int>[];

  /// Current match index (0-based)
  int currentSearchMatchIndex = 0;

  // ============================================================================
  // State Initialization
  // ============================================================================

  /// Initialize all state variables to their default values
  void initializeExtractPreviewState() {
    allSegments = <String>[];
    allSeparators = <String>[];
    allChunks = <String>[];
    segmentExclusionReasons = <int, String>{};
    segmentExclusionMetadata = <int, Map<String, dynamic>>{};
    segmentTypeInfo = <int, Map<String, dynamic>>{};
    referenceSegmentIndices = <int>[];
    excludeReferences = true;
    headerSegmentIndices = <int>[];
    footerSegmentIndices = <int>[];
    excludeHeaders = false;
    excludeFooters = false;
    tableSegmentIndices = <int>[];
    identifierSegmentIndices = <int>[];
    languageMatchedSegmentIndices = <int>[];
    userSelectedSegmentIndices = <int>[];
    invalidateIndexSets(); // Rebuild cached Sets on next access
    currentTargetLangForExclusion = null;
    isLanguageExclusionActive = false;
    languageMatchedSegmentCount = 0;
    selectedExclusionFilters = <String>{};
    categoryExclusionStates = <String, bool>{};
    filterMode = 'rebuild';
    filteredSegmentIndices = null;
    highlightedIndex = null;
    isPreparing = true;
    prepareProgress = 0;
    prepareStatus = 'Preparing...';
    prepareTaskType = '';
    prepareErrorMessage = '';
    prepareTimer = null;
    prepareInFlight = false;
    initialDataLoaded = false;
    simulatedProgressPercent = 0;
    extractPdfPartCurrent = 0;
    extractPdfPartTotal = 0;
    lastExtractPdfPartCurrent = 0;
    // Translation phase state
    isTranslating = false;
    translationProgress = 0;
    translationStatus = '';
    translationTimer = null;
    translationInFlight = false;
    currentTranslationTaskId = null;
    // Anonymization workflow state
    isAnonymizing = false;
    anonymizeProgress = 0;
    anonymizeStatus = '';
    progressTimer = null;
    progressInFlight = false;
    currentPollingWorkflowId = null;
    totalEstimatedInputTokens = null;
    lastKnownChunkSize = null;
    lastViewSize = null;
    lastRefreshTrigger = null;
    lastToolbarLogTaskId = null;
    hasShownMineruSettingsDialog = false;
    imageDataMap = <String, Map<String, String>>{};
    // Search state
    isSearchBoxVisible = false;
    searchQuery = '';
    searchMatchIndices = <int>[];
    currentSearchMatchIndex = 0;
  }

  // ============================================================================
  // State Cleanup
  // ============================================================================

  /// Clean up all state variables and resources
  void disposeExtractPreviewState() {
    prepareTimer?.cancel();
    segmentsScrollController.dispose();
    chunksScrollController.dispose();
    segmentsScrollManager?.dispose();
    // Note: SegmentHeightCache doesn't have a dispose method
    // segmentsHeightCache?.dispose();
  }
}
