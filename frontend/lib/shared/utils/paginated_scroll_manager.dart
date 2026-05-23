// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'dart:async';
import '../../features/translation/utils/segment_height_cache.dart';
import 'pagination.dart';
import 'app_logger.dart';
import 'linear_scroll_mapper.dart';

/// Manager for maintaining scroll position in paginated lists with variable item heights
///
/// This manager provides:
/// - Precise scroll-to-index using height cache
/// - Scroll position preservation during pagination
/// - Cross-page navigation support
/// - Automatic height measurement and caching
class PaginatedScrollManager {
  PaginatedScrollManager({
    required this.scrollController,
    required this.paginationController,
    required this.heightCache,
    required this.itemKeys,
    this.totalItems,
    this.onPageLoad,
  }) {
    // Initialize linear scroll mapper with current totalItems
    // Note: totalItems may be 0 initially, will be updated when data loads
    _scrollMapper = LinearScrollMapper(
      heightCache: heightCache,
      totalItems: _totalItemsCount > 0
          ? _totalItemsCount
          : 1, // Use 1 as placeholder to avoid clamp errors
    );

    // Listen to scroll events to measure visible items
    scrollController.addListener(_onScroll);

    // Listen to pagination changes to update totalItems
    paginationController.addListener(_onPaginationDataChanged);
  }

  /// Callback when pagination data changes (to update totalItems)
  void _onPaginationDataChanged() {
    final currentTotal = _totalItemsCount;
    if (_scrollMapper != null &&
        currentTotal > 0 &&
        _scrollMapper!.totalItems != currentTotal) {
      AppLogger.log(
        'PaginatedScrollManager',
        '_onPaginationDataChanged: Updating totalItems from ${_scrollMapper!.totalItems} to $currentTotal',
      );
      _scrollMapper!.updateTotalItems(currentTotal);
    } else if (_scrollMapper != null && currentTotal == 0) {
      AppLogger.log(
        'PaginatedScrollManager',
        '_onPaginationDataChanged: totalItems is still 0, mapper.totalItems=${_scrollMapper!.totalItems}',
      );
    }

    // CRITICAL: When pagination changes (new page loaded), measure visible items
    // This allows us to correct predicted heights based on actual measurements
    // Use a delay to ensure items are rendered before measuring
    Future.delayed(const Duration(milliseconds: 200), () {
      if (scrollController.hasClients) {
        measureVisibleItems(reason: 'pagination_changed: new_page_loaded');
      }
    });
  }

  final ScrollController scrollController;
  final PagedListController paginationController;
  final SegmentHeightCache heightCache;
  final Map<int, GlobalKey> itemKeys;
  final int? totalItems; // Total number of items (if known)
  final Future<void> Function(int page)?
      onPageLoad; // Callback when page needs to be loaded

  // Linear scroll mapper for position <-> index conversion
  LinearScrollMapper? _scrollMapper;

  // Saved state for scroll position restoration
  int? _savedVisibleIndex;
  int? _savedPaginationOffset;

  // Stable maxScrollExtent for scroll position calculation
  // This prevents jitter when heights are measured during scrolling
  double? _stableMaxScrollExtent;
  DateTime _lastMaxScrollExtentUpdate = DateTime.now();

  /// Get total number of items
  /// Prefer paginationController.total (updated when data loads) over static totalItems parameter
  int get _totalItemsCount {
    final controllerTotal = paginationController.total;
    // Prefer controller's total if it's valid (> 0), otherwise use provided totalItems
    if (controllerTotal > 0) {
      return controllerTotal;
    }
    return totalItems ?? 0;
  }

  /// Get current pagination offset
  int get _currentOffset => paginationController.offset;

  /// Get current page size
  int get _pageSize => paginationController.pageSize;

  /// Scroll to a specific index with optional alignment
  ///
  /// [targetIndex] - Target segment index (0-based)
  /// [alignment] - Where to position the segment (0.0 = top, 0.5 = center, 1.0 = bottom)
  /// [ensureVisible] - If true, load the page containing targetIndex if not currently loaded
  /// [animate] - Whether to animate the scroll (default: false for instant response)
  Future<void> scrollToIndex(
    int targetIndex, {
    double alignment = 0.1,
    bool ensureVisible = true,
    bool animate = false,
  }) async {
    if (targetIndex < 0 || targetIndex >= _totalItemsCount) {
      AppLogger.log(
        'PaginatedScrollManager',
        'scrollToIndex: Invalid targetIndex=$targetIndex (total=$_totalItemsCount)',
        level: LogLevel.warn,
      );
      return;
    }

    if (!scrollController.hasClients) {
      AppLogger.log(
        'PaginatedScrollManager',
        'scrollToIndex: ScrollController has no clients',
        level: LogLevel.warn,
      );
      return;
    }

    AppLogger.log(
      'PaginatedScrollManager',
      'scrollToIndex: targetIndex=$targetIndex, alignment=$alignment, ensureVisible=$ensureVisible, animate=$animate',
    );

    // CRITICAL: Check if target is already fully visible in viewport
    // If so, skip scrolling to avoid unnecessary movement
    final targetKey = itemKeys[targetIndex];
    if (targetKey != null) {
      final context = targetKey.currentContext;
      if (context != null) {
        try {
          final renderBox = context.findRenderObject() as RenderBox?;
          if (renderBox != null && renderBox.hasSize) {
            final scrollable = Scrollable.of(context);
            final scrollableRenderBox =
                scrollable.context.findRenderObject() as RenderBox?;
            if (scrollableRenderBox != null) {
              final itemGlobalTop = renderBox.localToGlobal(Offset.zero);
              final itemGlobalBottom =
                  itemGlobalTop + Offset(0, renderBox.size.height);
              final scrollableGlobalTop =
                  scrollableRenderBox.localToGlobal(Offset.zero);
              final scrollableGlobalBottom = scrollableGlobalTop +
                  Offset(0, scrollController.position.viewportDimension);

              // Check if item's top edge is already visible in the viewport.
              // We check the top edge only — not "fully visible" — because
              // segments taller than the viewport would never be "fully visible",
              // causing re-scroll on every tap (very disruptive when reading
              // long segments).
              const margin = 20;
              final topVisible = itemGlobalTop.dy >=
                      (scrollableGlobalTop.dy - margin) &&
                  itemGlobalTop.dy < scrollableGlobalBottom.dy;

              if (topVisible) {
                // Target's top edge is already visible, no need to scroll
                AppLogger.log(
                  'PaginatedScrollManager',
                  'scrollToIndex: Target top already visible, skipping scroll. '
                      'targetIndex=$targetIndex, itemTop=${itemGlobalTop.dy.toStringAsFixed(1)}, '
                      'scrollableTop=${scrollableGlobalTop.dy.toStringAsFixed(1)}, '
                      'scrollableBottom=${scrollableGlobalBottom.dy.toStringAsFixed(1)}',
                );
                return;
              }
            }
          }
        } catch (e) {
          // If visibility check fails, proceed with normal scrolling
          AppLogger.log(
            'PaginatedScrollManager',
            'scrollToIndex: Error checking visibility, proceeding with scroll: $e',
          );
        }
      }
    }

    // Check if target index is in current page
    final currentPageStart = _currentOffset;
    final currentPageEnd = _currentOffset + paginationController.items.length;

    if (targetIndex < currentPageStart || targetIndex >= currentPageEnd) {
      if (ensureVisible) {
        // Calculate which page contains the target index
        final targetPage = (targetIndex ~/ _pageSize) + 1;

        AppLogger.log(
          'PaginatedScrollManager',
          'scrollToIndex: Target not in current page, loading page $targetPage (currentOffset=$currentPageStart, targetIndex=$targetIndex)',
        );

        // Load the target page
        await paginationController.jumpToPage(targetPage);

        // Wait for page to load and render
        await Future.delayed(const Duration(milliseconds: 150));

        // Measure heights of newly loaded items
        measureVisibleItems(reason: 'scrollToIndex: page_loaded');

        // Wait a bit more for measurements to complete
        await Future.delayed(const Duration(milliseconds: 50));
      } else {
        // Target not in current page and ensureVisible is false
        AppLogger.log(
          'PaginatedScrollManager',
          'scrollToIndex: Target not in current page and ensureVisible=false',
          level: LogLevel.warn,
        );
        return;
      }
    }

    // CRITICAL: Force measure target index and nearby indices before calculating scroll position
    // This reduces cumulative error, especially for indices far from current position
    // Measure a range around target index to ensure accurate calculation
    // For far indices, use a larger range to reduce cumulative error
    final currentScrollIndex = getFirstVisibleIndex() ?? _currentOffset;
    final distanceFromCurrent = (targetIndex - currentScrollIndex).abs();
    // Use larger range for far indices: ±5 for nearby, ±10 for medium distance, ±15 for far
    final measureRangeSize =
        distanceFromCurrent < 10 ? 5 : (distanceFromCurrent < 30 ? 10 : 15);
    final measureStartIndex =
        (targetIndex - measureRangeSize).clamp(0, _totalItemsCount - 1);
    final measureEndIndex =
        (targetIndex + measureRangeSize).clamp(0, _totalItemsCount - 1);

    AppLogger.log(
      'PaginatedScrollManager',
      'scrollToIndex: Measuring range [$measureStartIndex, $measureEndIndex] for targetIndex=$targetIndex (distance=$distanceFromCurrent, rangeSize=$measureRangeSize)',
    );

    // Measure in multiple passes to ensure accuracy
    measureRange(measureStartIndex, measureEndIndex);

    // Wait for measurements to complete (especially important for far indices)
    // Use post-frame callback to ensure measurements are done after rendering
    await Future.delayed(const Duration(milliseconds: 100));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // Re-measure to ensure accuracy after rendering
      measureRange(measureStartIndex, measureEndIndex);
    });
    await Future.delayed(const Duration(milliseconds: 100));

    // Calculate scroll offset using linear mapper (with height cache corrections)
    final viewportHeight = scrollController.position.viewportDimension;
    final isHeightCached = heightCache.isHeightCached(targetIndex);
    final scrollOffset = _scrollMapper?.indexToScrollPosition(
          targetIndex,
          viewportHeight: viewportHeight,
          alignment: alignment,
        ) ??
        heightCache.calculateScrollOffset(
          targetIndex,
          viewportHeight,
          alignment,
        );

    // Clamp to valid range
    final maxScrollExtent = scrollController.position.maxScrollExtent;
    final clampedOffset = scrollOffset.clamp(0.0, maxScrollExtent);

    AppLogger.log(
      'PaginatedScrollManager',
      'scrollToIndex: Calculated offset=$scrollOffset, clamped=$clampedOffset, maxScrollExtent=$maxScrollExtent, '
          'viewportHeight=$viewportHeight, heightCached=$isHeightCached, measuredRange=[$measureStartIndex, $measureEndIndex]',
    );

    // Scroll to the calculated position
    if (animate) {
      await scrollController.animateTo(
        clampedOffset,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      scrollController.jumpTo(clampedOffset);
    }

    // Wait for scroll animation to complete
    await Future.delayed(const Duration(milliseconds: 350));

    // CRITICAL: Measure heights after scrolling to update cache
    // This ensures height cache is up-to-date for correction logic
    measureVisibleItems(reason: 'scrollToIndex: after_scroll_before_verify');

    // Wait longer for measurements to complete, especially when items are not yet rendered
    // Use multiple post-frame callbacks to ensure items are rendered before verification
    await Future.delayed(const Duration(milliseconds: 150));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // Re-measure after first frame to catch newly rendered items
      measureVisibleItems(
        reason: 'scrollToIndex: after_scroll_before_verify (post_frame)',
      );
    });
    await Future.delayed(const Duration(milliseconds: 100));

    // CRITICAL: Verify target is visible and correct if needed
    // This handles cumulative error for far indices
    // IMPORTANT: Only correct if user is NOT actively scrolling to avoid jump
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!scrollController.hasClients) return;

      // CRITICAL: Check if user is actively scrolling (mouse wheel or scrollbar drag)
      // If so, skip correction to avoid interfering with user input
      final isUserScrolling =
          scrollController.position.isScrollingNotifier.value;
      if (isUserScrolling) {
        AppLogger.log(
          'PaginatedScrollManager',
          'scrollToIndex: User is actively scrolling, skipping correction to avoid jump',
        );
        // Still measure heights for future use, but don't correct position
        measureVisibleItems(
          reason: 'scrollToIndex: after_scroll (user_scrolling)',
        );
        return;
      }

      // CRITICAL: Check measurement failure rate - if too high, items may not be rendered yet
      // In this case, we should retry verification after a longer delay
      final currentScrollIndex = getFirstVisibleIndex() ?? _currentOffset;
      final distanceFromTarget = (targetIndex - currentScrollIndex).abs();

      // If distance is large and measurement failed, wait longer and retry
      if (distanceFromTarget > 10) {
        AppLogger.log(
          'PaginatedScrollManager',
          'scrollToIndex: Large distance from target ($distanceFromTarget indices), will verify with retry mechanism. targetIndex=$targetIndex, currentIndex=$currentScrollIndex',
        );

        // Wait longer for items to render, then verify
        Future.delayed(const Duration(milliseconds: 300), () {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            _verifyAndCorrectScrollPosition(
              targetIndex,
              alignment,
              measureStartIndex,
              measureEndIndex,
            );
          });
        });
        return;
      }

      // Check if target index is actually visible
      final targetKey = itemKeys[targetIndex];
      if (targetKey == null) {
        // Key doesn't exist - item may not be rendered yet
        // Try using ensureVisible if context becomes available after a delay
        // Use retry mechanism with multiple attempts for better reliability
        AppLogger.log(
          'PaginatedScrollManager',
          'scrollToIndex: Target key not found, item may not be rendered yet. targetIndex=$targetIndex. Will retry with ensureVisible (multiple attempts).',
          level: LogLevel.warn,
        );

        // Retry mechanism: try multiple times with increasing delays
        _retryEnsureVisible(targetIndex, targetKey, alignment);
        return;
      }

      final context = targetKey.currentContext;
      if (context == null) {
        // Context not available - item not rendered yet
        // Try using ensureVisible after a delay with retry mechanism
        AppLogger.log(
          'PaginatedScrollManager',
          'scrollToIndex: Target context not available, item may not be rendered yet. targetIndex=$targetIndex. Will retry with ensureVisible (multiple attempts).',
          level: LogLevel.warn,
        );

        // Retry mechanism: try multiple times with increasing delays
        _retryEnsureVisible(targetIndex, targetKey, alignment);
        return;
      }

      try {
        final renderBox = context.findRenderObject() as RenderBox?;
        if (renderBox == null || !renderBox.hasSize) {
          // RenderBox not ready - try ensureVisible after a delay with retry mechanism
          AppLogger.log(
            'PaginatedScrollManager',
            'scrollToIndex: RenderBox not ready, waiting. targetIndex=$targetIndex. Will retry with ensureVisible (multiple attempts).',
          );

          // Retry mechanism: try multiple times with increasing delays
          _retryEnsureVisible(targetIndex, targetKey, alignment);
          return;
        }

        final scrollable = Scrollable.of(context);
        final scrollableRenderBox =
            scrollable.context.findRenderObject() as RenderBox?;
        if (scrollableRenderBox != null) {
          final itemGlobalTop = renderBox.localToGlobal(Offset.zero);
          final itemGlobalBottom =
              itemGlobalTop + Offset(0, renderBox.size.height);
          final scrollableGlobalTop =
              scrollableRenderBox.localToGlobal(Offset.zero);
          final scrollableGlobalBottom = scrollableGlobalTop +
              Offset(0, scrollController.position.viewportDimension);

          // Check if item is fully visible (with margin for alignment)
          // Use smaller margin for correction to avoid over-correction
          const margin = 30;
          final isFullyVisible =
              itemGlobalTop.dy >= (scrollableGlobalTop.dy - margin) &&
                  itemGlobalBottom.dy <= (scrollableGlobalBottom.dy + margin);

          if (!isFullyVisible) {
            // Calculate the delta (difference) using actual rendered position
            // This is more accurate than recalculating from height cache

            // Calculate where the item actually is relative to scrollable viewport
            final itemRelativeY = itemGlobalTop.dy - scrollableGlobalTop.dy;

            // Calculate where the item should be positioned based on alignment
            // alignment=0.1 means 10% from top of viewport
            // If item is at position Y relative to viewport, and we want it at alignment*viewportHeight,
            // we need to adjust scroll by: delta = itemRelativeY - (viewportHeight * alignment)
            final targetRelativeY = viewportHeight * alignment;
            final delta = itemRelativeY - targetRelativeY;

            // Only correct if delta is significant (>= 10px) to avoid micro-adjustments
            if (delta.abs() >= 10.0) {
              AppLogger.log(
                'PaginatedScrollManager',
                'scrollToIndex: Target not fully visible, correcting position. '
                    'targetIndex=$targetIndex, delta=${delta.toStringAsFixed(1)}, '
                    'itemTop=${itemGlobalTop.dy.toStringAsFixed(1)}, '
                    'itemRelativeY=${itemRelativeY.toStringAsFixed(1)}, '
                    'targetRelativeY=${targetRelativeY.toStringAsFixed(1)}, '
                    'scrollableTop=${scrollableGlobalTop.dy.toStringAsFixed(1)}, '
                    'scrollableBottom=${scrollableGlobalBottom.dy.toStringAsFixed(1)}',
                level: LogLevel.warn,
              );

              // Re-measure target and nearby indices to ensure accurate correction
              // Use post-frame callback to ensure measurements are done after rendering
              measureRange(measureStartIndex, measureEndIndex);
              WidgetsBinding.instance.addPostFrameCallback((_) {
                measureRange(measureStartIndex, measureEndIndex);
              });

              // Wait for measurement, then apply correction
              Future.delayed(const Duration(milliseconds: 150), () {
                if (!scrollController.hasClients) return;

                // Double-check user is still not scrolling before correcting
                final stillScrolling =
                    scrollController.position.isScrollingNotifier.value;
                if (stillScrolling) {
                  AppLogger.log(
                    'PaginatedScrollManager',
                    'scrollToIndex: User started scrolling during correction, aborting',
                  );
                  return;
                }

                // Apply delta directly to current scroll position
                // This is more accurate than recalculating from height cache
                // Get current position again (may have changed during delay)
                final currentPositionAfterDelay =
                    scrollController.position.pixels;
                final newScrollPosition = (currentPositionAfterDelay + delta)
                    .clamp(0.0, scrollController.position.maxScrollExtent);

                AppLogger.log(
                  'PaginatedScrollManager',
                  'scrollToIndex: Correcting scroll position using delta. '
                      'currentPosition=${currentPositionAfterDelay.toStringAsFixed(1)}, '
                      'delta=${delta.toStringAsFixed(1)}, '
                      'newPosition=${newScrollPosition.toStringAsFixed(1)}, '
                      'itemRelativeY=${itemRelativeY.toStringAsFixed(1)}, '
                      'targetRelativeY=${targetRelativeY.toStringAsFixed(1)}',
                  level: LogLevel.info,
                );

                // Use smooth animation for small corrections to avoid jump
                // Use jumpTo for large corrections (faster response)
                if (delta.abs() < 100.0) {
                  // Small correction: use smooth animation
                  scrollController.animateTo(
                    newScrollPosition,
                    duration: const Duration(milliseconds: 200),
                    curve: Curves.easeOut,
                  );
                } else {
                  // Large correction: use jumpTo for immediate response
                  scrollController.jumpTo(newScrollPosition);
                }

                // Verify correction after a delay (with retry if needed)
                Future.delayed(const Duration(milliseconds: 250), () {
                  if (!scrollController.hasClients) return;

                  // Check again if target is visible
                  final context = targetKey.currentContext;
                  if (context != null) {
                    try {
                      final renderBox =
                          context.findRenderObject() as RenderBox?;
                      if (renderBox != null && renderBox.hasSize) {
                        final scrollable = Scrollable.of(context);
                        final scrollableRenderBox =
                            scrollable.context.findRenderObject() as RenderBox?;
                        if (scrollableRenderBox != null) {
                          final itemGlobalTopAfter =
                              renderBox.localToGlobal(Offset.zero);
                          final itemGlobalBottomAfter = itemGlobalTopAfter +
                              Offset(0, renderBox.size.height);
                          final scrollableGlobalTopAfter =
                              scrollableRenderBox.localToGlobal(Offset.zero);
                          final scrollableGlobalBottomAfter =
                              scrollableGlobalTopAfter +
                                  Offset(
                                    0,
                                    scrollController.position.viewportDimension,
                                  );

                          final isFullyVisibleAfter = itemGlobalTopAfter.dy >=
                                  (scrollableGlobalTopAfter.dy - margin) &&
                              itemGlobalBottomAfter.dy <=
                                  (scrollableGlobalBottomAfter.dy + margin);

                          if (!isFullyVisibleAfter) {
                            // Still not visible, use Scrollable.ensureVisible as fallback
                            // This is more reliable than manual delta calculation
                            AppLogger.log(
                              'PaginatedScrollManager',
                              'scrollToIndex: Target still not visible after correction, using ensureVisible. '
                                  'targetIndex=$targetIndex',
                              level: LogLevel.warn,
                            );

                            // Use Scrollable.ensureVisible as a more reliable fallback
                            try {
                              Scrollable.ensureVisible(
                                context,
                                duration: const Duration(milliseconds: 200),
                                curve: Curves.easeOut,
                                alignment: alignment,
                              );

                              // Verify again after ensureVisible
                              Future.delayed(const Duration(milliseconds: 300),
                                  () {
                                if (!scrollController.hasClients) return;

                                // Final verification
                                final contextFinal = targetKey.currentContext;
                                if (contextFinal != null) {
                                  try {
                                    final renderBoxFinal = contextFinal
                                        .findRenderObject() as RenderBox?;
                                    if (renderBoxFinal != null &&
                                        renderBoxFinal.hasSize) {
                                      final scrollableFinal =
                                          Scrollable.of(contextFinal);
                                      final scrollableRenderBoxFinal =
                                          scrollableFinal.context
                                              .findRenderObject() as RenderBox?;
                                      if (scrollableRenderBoxFinal != null) {
                                        final itemGlobalTopFinal =
                                            renderBoxFinal
                                                .localToGlobal(Offset.zero);
                                        final itemGlobalBottomFinal =
                                            itemGlobalTopFinal +
                                                Offset(
                                                  0,
                                                  renderBoxFinal.size.height,
                                                );
                                        final scrollableGlobalTopFinal =
                                            scrollableRenderBoxFinal
                                                .localToGlobal(Offset.zero);
                                        final scrollableGlobalBottomFinal =
                                            scrollableGlobalTopFinal +
                                                Offset(
                                                  0,
                                                  scrollController.position
                                                      .viewportDimension,
                                                );

                                        const margin = 30;
                                        final isFullyVisibleFinal =
                                            itemGlobalTopFinal.dy >=
                                                    (scrollableGlobalTopFinal
                                                            .dy -
                                                        margin) &&
                                                itemGlobalBottomFinal.dy <=
                                                    (scrollableGlobalBottomFinal
                                                            .dy +
                                                        margin);

                                        if (!isFullyVisibleFinal) {
                                          // Still not visible, retry with ensureVisible
                                          AppLogger.log(
                                            'PaginatedScrollManager',
                                            'scrollToIndex: Target still not visible after ensureVisible. '
                                                'targetIndex=$targetIndex. Will retry with ensureVisible (multiple attempts).',
                                            level: LogLevel.warn,
                                          );
                                          // Retry with ensureVisible
                                          _retryEnsureVisible(
                                            targetIndex,
                                            targetKey,
                                            alignment,
                                            maxAttempts: 3,
                                          );
                                        } else {
                                          AppLogger.log(
                                            'PaginatedScrollManager',
                                            'scrollToIndex: Target is now visible after ensureVisible. '
                                                'targetIndex=$targetIndex',
                                            level: LogLevel.info,
                                          );
                                        }
                                      }
                                    }
                                  } catch (e) {
                                    // Ignore errors in final verification
                                  }
                                }
                              });
                            } catch (e) {
                              AppLogger.log(
                                'PaginatedScrollManager',
                                'scrollToIndex: Error using ensureVisible: $e',
                                level: LogLevel.warn,
                              );
                            }
                          }
                        }
                      }
                    } catch (e) {
                      // Ignore errors in verification
                    }
                  }
                });
              });
            } else {
              // Delta is small, no correction needed
              AppLogger.log(
                'PaginatedScrollManager',
                'scrollToIndex: Target position is acceptable (delta=${delta.toStringAsFixed(1)} < 10px), no correction needed',
              );
            }
          } else {
            // Target is fully visible, no correction needed
            AppLogger.log(
              'PaginatedScrollManager',
              'scrollToIndex: Target is fully visible after scroll, no correction needed',
            );
          }
        }
      } catch (e) {
        // If verification fails, log but don't crash
        AppLogger.log(
          'PaginatedScrollManager',
          'scrollToIndex: Error in verification block: $e',
          level: LogLevel.warn,
        );
      }

      // Measure heights after scrolling (for items that just became visible)
      // This is needed for scrollToIndex to work correctly with newly loaded items
      measureVisibleItems(reason: 'scrollToIndex: after_scroll');
    });
  }

  /// Save current scroll position (based on visible index, not pixel offset)
  void saveScrollPosition() {
    if (!scrollController.hasClients) return;

    _savedVisibleIndex = getFirstVisibleIndex();
    _savedPaginationOffset = _currentOffset;

    AppLogger.log(
      'PaginatedScrollManager',
      'saveScrollPosition: savedVisibleIndex=$_savedVisibleIndex, savedPaginationOffset=$_savedPaginationOffset, '
          'currentScrollOffset=${scrollController.offset}',
    );
  }

  /// Restore scroll position after pagination change
  /// Simplified: Do NOT restore during scrolling to avoid jitter
  /// Let scroll position naturally follow user input without programmatic adjustments
  void restoreScrollPosition() {
    // Simplified: Don't restore during scrolling to avoid feedback loops
    // Scroll position should only change from user input, not from programmatic adjustments
    if (_savedVisibleIndex != null) {
      AppLogger.log(
        'PaginatedScrollManager',
        'restoreScrollPosition: Skipping restore to avoid jitter - let scroll position follow user input naturally',
      );
      _savedVisibleIndex = null;
      _savedPaginationOffset = null;
    }
  }

  // Helper to check if manager is still valid (for async callbacks)
  bool get mounted => scrollController.hasClients;

  /// Get the index of the first visible item using linear mapping
  /// Returns null if unable to determine
  ///
  /// CRITICAL: This method reads maxScrollExtent, which may change during scrolling.
  /// Only call this method when scrolling has stopped to avoid scrollbar jitter.
  int? getFirstVisibleIndex() {
    if (!scrollController.hasClients || _scrollMapper == null) return null;

    final scrollOffset = scrollController.offset;
    final currentPageEnd = _currentOffset + paginationController.items.length;

    // Update mapper's totalItems if it changed (do this first, and always check)
    final currentTotal = _totalItemsCount;
    if (_scrollMapper != null &&
        currentTotal > 0 &&
        _scrollMapper!.totalItems != currentTotal) {
      AppLogger.log(
        'PaginatedScrollManager',
        'getFirstVisibleIndex: Updating totalItems from ${_scrollMapper!.totalItems} to $currentTotal',
      );
      _scrollMapper!.updateTotalItems(currentTotal);
    }

    // CRITICAL: Check if user is actively scrolling - if so, use cached stable maxScrollExtent
    // to avoid reading the changing maxScrollExtent which causes scrollbar jitter
    final isUserScrolling = scrollController.position.isScrollingNotifier.value;
    double? maxScrollExtent;

    if (isUserScrolling) {
      // User is actively scrolling - use stable maxScrollExtent only
      // Do NOT read current maxScrollExtent as it may be changing
      maxScrollExtent = _stableMaxScrollExtent;
      if (maxScrollExtent == null || maxScrollExtent <= 0) {
        // No stable value yet, cannot calculate accurately - return null to avoid jitter
        return null;
      }
    } else {
      // User is not scrolling - safe to read current maxScrollExtent
      final currentMaxScrollExtent = scrollController.position.maxScrollExtent;
      final now = DateTime.now();
      final timeSinceLastUpdate =
          now.difference(_lastMaxScrollExtentUpdate).inMilliseconds;

      // Update stable maxScrollExtent only if:
      // 1. It's not set yet, or
      // 2. Scrolling has been slow/stopped for > 500ms (stable state), or
      // 3. The change is significant (> 10% difference)
      if (_stableMaxScrollExtent == null ||
          (timeSinceLastUpdate > 500 && currentMaxScrollExtent > 0) ||
          (_stableMaxScrollExtent != null &&
              (currentMaxScrollExtent - _stableMaxScrollExtent!).abs() /
                      _stableMaxScrollExtent! >
                  0.1)) {
        _stableMaxScrollExtent = currentMaxScrollExtent;
        _lastMaxScrollExtentUpdate = now;
      }

      // Use stable maxScrollExtent for calculation to avoid jitter
      maxScrollExtent = _stableMaxScrollExtent ?? currentMaxScrollExtent;
    }

    // At this point, maxScrollExtent is guaranteed to be non-null and > 0
    // (either from stable value in scrolling case, or from current value in non-scrolling case)
    final estimatedIndex = _scrollMapper!.scrollPositionToIndex(
      scrollOffset,
      currentPageStart: _currentOffset,
      currentPageEnd: currentPageEnd,
      actualMaxScrollExtent: maxScrollExtent > 0 ? maxScrollExtent : null,
    );

    // Clamp to current page bounds (with safe bounds check)
    int result;
    if (currentPageEnd > _currentOffset) {
      result = estimatedIndex.clamp(_currentOffset, currentPageEnd - 1);
    } else {
      // Invalid page bounds, return current offset
      result = _currentOffset;
    }

    return result;
  }

  /// Measure and cache heights for currently visible items
  ///
  /// This should be called when:
  /// - Text content changes (segments updated)
  /// - View size changes (window resize, layout change)
  /// - Edit/preview mode changes
  ///
  /// NOT called during scrolling to avoid interfering with scroll position.
  ///
  /// [reason] - Optional reason for measurement (for debugging)
  void measureVisibleItems({String? reason}) {
    // Log measurement trigger with reason and context
    final isUserScrolling = scrollController.hasClients
        ? scrollController.position.isScrollingNotifier.value
        : false;
    final currentOffset =
        scrollController.hasClients ? scrollController.position.pixels : 0.0;
    final maxExtent = scrollController.hasClients
        ? scrollController.position.maxScrollExtent
        : 0.0;

    AppLogger.log(
      'PaginatedScrollManager',
      'measureVisibleItems CALLED: reason=${reason ?? "unknown"}, '
          'isUserScrolling=$isUserScrolling, offset=${currentOffset.toStringAsFixed(1)}, '
          'maxExtent=${maxExtent.toStringAsFixed(1)}, hasClients=${scrollController.hasClients}',
      level: LogLevel.info,
    );

    if (!scrollController.hasClients) {
      AppLogger.log(
        'PaginatedScrollManager',
        'measureVisibleItems: Early return - ScrollController has no clients',
      );
      return;
    }

    final firstVisible = getFirstVisibleIndex() ?? _currentOffset;
    final viewportHeight = scrollController.position.viewportDimension;
    final estimatedHeight = heightCache.getHeight(firstVisible);
    final visibleCount =
        (viewportHeight / estimatedHeight).ceil() + 2; // +2 for buffer

    final int itemCount = paginationController.items.length;
    if (itemCount <= 0) return;

    final startIndex = firstVisible.clamp(
      _currentOffset,
      _currentOffset + itemCount - 1,
    );
    final endIndex = (startIndex + visibleCount).clamp(
      _currentOffset,
      _currentOffset + itemCount - 1,
    );

    int measured = 0;
    int alreadyCached = 0;
    int failed = 0;
    double totalMeasuredHeight = 0;

    for (int i = startIndex; i <= endIndex; i++) {
      // Only try to measure if key exists
      if (!itemKeys.containsKey(i)) {
        // Key doesn't exist yet (item not rendered), skip
        continue;
      }

      if (heightCache.isHeightCached(i)) {
        alreadyCached++;
      } else {
        // Try to measure, but check if context is ready
        final key = itemKeys[i];
        if (key?.currentContext == null) {
          // Context not ready yet, will retry later
          failed++;
          continue;
        }

        // Get predicted height before measurement (if available)
        // This allows us to calculate correction factor
        final predictedHeight = heightCache.getHeight(i);

        if (heightCache.measureAndCacheHeight(
          i,
          key,
          predictedHeight: predictedHeight,
        )) {
          measured++;
          final actualHeight = heightCache.getHeight(i);
          totalMeasuredHeight += actualHeight;

          // Calculate correction factor for logging
          final correctionFactor = predictedHeight > 0
              ? (actualHeight / predictedHeight).toStringAsFixed(2)
              : 'N/A';

          AppLogger.log(
            'PaginatedScrollManager',
            'measureVisibleItems: Measured index=$i, predicted=${predictedHeight.toStringAsFixed(1)}, actual=${actualHeight.toStringAsFixed(1)}, correctionFactor=$correctionFactor',
          );
        } else {
          // Measurement failed (e.g., renderBox not ready)
          failed++;
        }
      }
    }

    // Calculate average measured height for this batch
    final avgMeasuredHeight = measured > 0
        ? (totalMeasuredHeight / measured).toStringAsFixed(1)
        : 'N/A';
    final cacheHitRate = (measured + alreadyCached) > 0
        ? (alreadyCached / (measured + alreadyCached) * 100).toStringAsFixed(1)
        : '0.0';

    // Log measurement results and maxScrollExtent changes
    final totalAttempted = measured + alreadyCached + failed;
    final maxExtentAfter = scrollController.hasClients
        ? scrollController.position.maxScrollExtent
        : 0.0;
    final maxExtentChanged = (maxExtent - maxExtentAfter).abs() > 1.0;

    AppLogger.log(
      'PaginatedScrollManager',
      'measureVisibleItems COMPLETED: reason=${reason ?? "unknown"}, '
          'firstVisible=$firstVisible, range=[$startIndex, $endIndex], '
          'measured=$measured, alreadyCached=$alreadyCached, failed=$failed, totalAttempted=$totalAttempted, '
          'cacheHitRate=$cacheHitRate%, cacheSize=${heightCache.getCacheSize()}, '
          'estimatedHeight=${estimatedHeight.toStringAsFixed(1)}, avgMeasuredHeight=$avgMeasuredHeight, '
          'maxExtent_before=${maxExtent.toStringAsFixed(1)}, maxExtent_after=${maxExtentAfter.toStringAsFixed(1)}, '
          'maxExtent_changed=$maxExtentChanged',
      level: LogLevel.info,
    );

    // Warn if maxScrollExtent changed significantly (this may cause scrollbar jitter)
    if (maxExtentChanged && maxExtent > 0) {
      final changePercent =
          ((maxExtentAfter - maxExtent) / maxExtent * 100).toStringAsFixed(1);
      AppLogger.log(
        'PaginatedScrollManager',
        'measureVisibleItems: WARNING - maxScrollExtent changed by $changePercent% '
            '(${maxExtent.toStringAsFixed(1)} -> ${maxExtentAfter.toStringAsFixed(1)}). '
            'This may cause scrollbar position recalculation.',
        level: LogLevel.warn,
      );
    }

    // Warn if too many failures
    if (failed > 5 && totalAttempted > 0) {
      final failureRate = (failed / totalAttempted * 100).toStringAsFixed(1);
      AppLogger.log(
        'PaginatedScrollManager',
        'measureVisibleItems: WARNING - High failure rate: $failureRate% ($failed/$totalAttempted) - items may not be rendered yet',
        level: LogLevel.warn,
      );
    }
  }

  /// Handle scroll events
  ///
  /// No operations are performed during scrolling to avoid interfering with Flutter's
  /// native scrolling behavior. Height measurement is only triggered by explicit calls
  /// to measureVisibleItems() when content changes (text, view size, mode changes).
  void _onScroll() {
    // Empty - scrolling is handled by Flutter natively
  }

  /// Batch measure heights for a range of indices
  /// Useful when loading a new page
  void measureRange(int startIndex, int endIndex) {
    for (int i = startIndex; i <= endIndex && i < _totalItemsCount; i++) {
      if (itemKeys.containsKey(i)) {
        heightCache.measureAndCacheHeight(i, itemKeys[i]);
      }
    }
  }

  /// Clear saved scroll position
  void clearSavedPosition() {
    _savedVisibleIndex = null;
    _savedPaginationOffset = null;
  }

  /// Verify and correct scroll position for target index
  /// This is a helper method extracted from scrollToIndex for retry logic
  void _verifyAndCorrectScrollPosition(
    int targetIndex,
    double alignment,
    int measureStartIndex,
    int measureEndIndex,
  ) {
    if (!scrollController.hasClients) return;

    // Check if user is actively scrolling
    final isUserScrolling = scrollController.position.isScrollingNotifier.value;
    if (isUserScrolling) {
      AppLogger.log(
        'PaginatedScrollManager',
        '_verifyAndCorrectScrollPosition: User is actively scrolling, skipping',
      );
      return;
    }

    // Check if target index is actually visible
    final targetKey = itemKeys[targetIndex];
    if (targetKey == null) {
      // Key doesn't exist - retry with ensureVisible
      AppLogger.log(
        'PaginatedScrollManager',
        '_verifyAndCorrectScrollPosition: Target key not found, retrying with ensureVisible. targetIndex=$targetIndex',
        level: LogLevel.warn,
      );
      _retryEnsureVisible(targetIndex, null, alignment);
      return;
    }

    final context = targetKey.currentContext;
    if (context == null) {
      // Context not available - retry with ensureVisible
      AppLogger.log(
        'PaginatedScrollManager',
        '_verifyAndCorrectScrollPosition: Target context not available, retrying with ensureVisible. targetIndex=$targetIndex',
        level: LogLevel.warn,
      );
      _retryEnsureVisible(targetIndex, targetKey, alignment, maxAttempts: 5);
      return;
    }

    try {
      final renderBox = context.findRenderObject() as RenderBox?;
      if (renderBox == null || !renderBox.hasSize) {
        // RenderBox not ready - retry with ensureVisible
        AppLogger.log(
          'PaginatedScrollManager',
          '_verifyAndCorrectScrollPosition: RenderBox not ready, retrying with ensureVisible. targetIndex=$targetIndex',
        );
        _retryEnsureVisible(targetIndex, targetKey, alignment);
        return;
      }

      final scrollable = Scrollable.of(context);
      final scrollableRenderBox =
          scrollable.context.findRenderObject() as RenderBox?;
      if (scrollableRenderBox != null) {
        final itemGlobalTop = renderBox.localToGlobal(Offset.zero);
        final itemGlobalBottom =
            itemGlobalTop + Offset(0, renderBox.size.height);
        final scrollableGlobalTop =
            scrollableRenderBox.localToGlobal(Offset.zero);
        final scrollableGlobalBottom = scrollableGlobalTop +
            Offset(0, scrollController.position.viewportDimension);

        const margin = 30;
        final isFullyVisible =
            itemGlobalTop.dy >= (scrollableGlobalTop.dy - margin) &&
                itemGlobalBottom.dy <= (scrollableGlobalBottom.dy + margin);

        if (!isFullyVisible) {
          // Calculate delta and correct
          final viewportHeight = scrollController.position.viewportDimension;
          final itemRelativeY = itemGlobalTop.dy - scrollableGlobalTop.dy;
          final targetRelativeY = viewportHeight * alignment;
          final delta = itemRelativeY - targetRelativeY;

          if (delta.abs() >= 10.0) {
            AppLogger.log(
              'PaginatedScrollManager',
              '_verifyAndCorrectScrollPosition: Target not fully visible, correcting. '
                  'targetIndex=$targetIndex, delta=${delta.toStringAsFixed(1)}',
              level: LogLevel.warn,
            );

            // Re-measure before correction
            measureRange(measureStartIndex, measureEndIndex);
            WidgetsBinding.instance.addPostFrameCallback((_) {
              measureRange(measureStartIndex, measureEndIndex);
            });

            Future.delayed(const Duration(milliseconds: 150), () {
              if (!scrollController.hasClients) return;
              final stillScrolling =
                  scrollController.position.isScrollingNotifier.value;
              if (stillScrolling) return;

              final currentPosition = scrollController.position.pixels;
              final newScrollPosition = (currentPosition + delta)
                  .clamp(0.0, scrollController.position.maxScrollExtent);

              if (delta.abs() < 100.0) {
                scrollController.animateTo(
                  newScrollPosition,
                  duration: const Duration(milliseconds: 200),
                  curve: Curves.easeOut,
                );
              } else {
                scrollController.jumpTo(newScrollPosition);
              }

              // Verify again after correction
              Future.delayed(const Duration(milliseconds: 250), () {
                if (!scrollController.hasClients) return;
                final ctx = targetKey.currentContext;
                if (ctx != null) {
                  try {
                    final rb = ctx.findRenderObject() as RenderBox?;
                    if (rb != null && rb.hasSize) {
                      final scrollable = Scrollable.of(ctx);
                      final scrollableRenderBox =
                          scrollable.context.findRenderObject() as RenderBox?;
                      if (scrollableRenderBox != null) {
                        final itemGlobalTopAfter =
                            rb.localToGlobal(Offset.zero);
                        final itemGlobalBottomAfter =
                            itemGlobalTopAfter + Offset(0, rb.size.height);
                        final scrollableGlobalTopAfter =
                            scrollableRenderBox.localToGlobal(Offset.zero);
                        final scrollableGlobalBottomAfter =
                            scrollableGlobalTopAfter +
                                Offset(
                                  0,
                                  scrollController.position.viewportDimension,
                                );

                        final isFullyVisibleAfter = itemGlobalTopAfter.dy >=
                                (scrollableGlobalTopAfter.dy - margin) &&
                            itemGlobalBottomAfter.dy <=
                                (scrollableGlobalBottomAfter.dy + margin);

                        if (!isFullyVisibleAfter) {
                          // Still not visible, use ensureVisible as fallback
                          AppLogger.log(
                            'PaginatedScrollManager',
                            '_verifyAndCorrectScrollPosition: Target still not visible after correction, using ensureVisible. targetIndex=$targetIndex',
                            level: LogLevel.warn,
                          );
                          _retryEnsureVisible(
                            targetIndex,
                            targetKey,
                            alignment,
                            maxAttempts: 3,
                          );
                        }
                      }
                    }
                  } catch (e) {
                    // Ignore errors
                  }
                }
              });
            });
          }
        } else {
          AppLogger.log(
            'PaginatedScrollManager',
            '_verifyAndCorrectScrollPosition: Target is fully visible. targetIndex=$targetIndex',
          );
        }
      }
    } catch (e) {
      AppLogger.log(
        'PaginatedScrollManager',
        '_verifyAndCorrectScrollPosition: Error: $e',
        level: LogLevel.warn,
      );
    }
  }

  /// Retry ensureVisible with multiple attempts
  /// This is used when target item is not yet rendered or context is not available
  /// Simplified: First attempt scrolls to predicted position, then waits and retries
  void _retryEnsureVisible(
    int targetIndex,
    GlobalKey? targetKey,
    double alignment, {
    int maxAttempts = 10,
    int attempt = 1,
  }) {
    if (attempt > maxAttempts || !scrollController.hasClients) {
      AppLogger.log(
        'PaginatedScrollManager',
        '_retryEnsureVisible: Max attempts reached or scrollController has no clients. targetIndex=$targetIndex, attempt=$attempt, maxAttempts=$maxAttempts',
        level: LogLevel.warn,
      );
      return;
    }

    // Simplified logic: First attempt scrolls to predicted position immediately, then waits
    // Subsequent attempts only check context without scrolling
    if (attempt == 1) {
      // Get current viewport range for logging (using actual rendered items)
      int? firstVisibleIndex;
      int? lastVisibleIndex;
      if (scrollController.hasClients) {
        firstVisibleIndex = getFirstVisibleIndex();
        if (firstVisibleIndex != null) {
          // Find actual visible items by checking which items have context and are visible
          final currentPageStart = _currentOffset;
          final currentPageEnd =
              _currentOffset + paginationController.items.length;
          int? actualFirstVisible;
          int? actualLastVisible;

          for (int i = currentPageStart; i < currentPageEnd; i++) {
            final key = itemKeys[i];
            if (key?.currentContext != null) {
              try {
                final renderBox =
                    key!.currentContext!.findRenderObject() as RenderBox?;
                if (renderBox != null && renderBox.hasSize) {
                  final scrollable = Scrollable.of(key.currentContext!);
                  final scrollableRenderBox =
                      scrollable.context.findRenderObject() as RenderBox?;
                  if (scrollableRenderBox != null) {
                    final itemGlobalTop = renderBox.localToGlobal(Offset.zero);
                    final itemGlobalBottom =
                        itemGlobalTop + Offset(0, renderBox.size.height);
                    final scrollableGlobalTop =
                        scrollableRenderBox.localToGlobal(Offset.zero);
                    final scrollableGlobalBottom = scrollableGlobalTop +
                        Offset(0, scrollController.position.viewportDimension);

                    // Check if item is at least partially visible
                    final isVisible =
                        itemGlobalBottom.dy > scrollableGlobalTop.dy &&
                            itemGlobalTop.dy < scrollableGlobalBottom.dy;

                    if (isVisible) {
                      actualFirstVisible ??= i;
                      actualLastVisible = i;
                    }
                  }
                }
              } catch (e) {
                // Ignore errors when checking visibility
              }
            }
          }

          firstVisibleIndex = actualFirstVisible ?? firstVisibleIndex;
          lastVisibleIndex = actualLastVisible;
        }
      }

      // First attempt: Scroll to predicted position immediately
      AppLogger.log(
        'PaginatedScrollManager',
        '_retryEnsureVisible: First attempt, scrolling to predicted position. targetIndex=$targetIndex, viewportRange=[$firstVisibleIndex, $lastVisibleIndex]',
        level: LogLevel.info,
      );

      // Calculate predicted scroll position for target index
      final viewportHeight = scrollController.position.viewportDimension;
      final predictedOffset = _scrollMapper?.indexToScrollPosition(
            targetIndex,
            viewportHeight: viewportHeight,
            alignment: alignment,
          ) ??
          heightCache.calculateScrollOffset(
            targetIndex,
            viewportHeight,
            alignment,
          );

      // Get current position
      final currentPosition = scrollController.position.pixels;
      final maxScrollExtent = scrollController.position.maxScrollExtent;
      final clampedOffset = predictedOffset.clamp(0.0, maxScrollExtent);

      AppLogger.log(
        'PaginatedScrollManager',
        '_retryEnsureVisible: Scrolling to predicted position. targetIndex=$targetIndex, currentPosition=${currentPosition.toStringAsFixed(1)}, predictedOffset=${predictedOffset.toStringAsFixed(1)}, clampedOffset=${clampedOffset.toStringAsFixed(1)}',
        level: LogLevel.info,
      );

      // Scroll to predicted position (use jumpTo for faster response)
      scrollController.jumpTo(clampedOffset);

      // Wait for scroll and rendering to complete, then retry
      Future.delayed(const Duration(milliseconds: 600), () {
        if (!scrollController.hasClients) return;
        // Measure heights around target after scrolling
        const measureRangeSize = 10;
        final measureStartIndex =
            (targetIndex - measureRangeSize).clamp(0, _totalItemsCount - 1);
        final measureEndIndex =
            (targetIndex + measureRangeSize).clamp(0, _totalItemsCount - 1);
        measureRange(measureStartIndex, measureEndIndex);

        // Wait a bit more for measurements to complete
        Future.delayed(const Duration(milliseconds: 200), () {
          if (!scrollController.hasClients) return;
          // Retry after scrolling to predicted position
          _retryEnsureVisible(
            targetIndex,
            targetKey,
            alignment,
            maxAttempts: maxAttempts,
            attempt: attempt + 1,
          );
        });
      });
      return;
    }

    // Subsequent attempts: Check if context is available, with fixed delay
    const delayMs = 300; // Fixed 300ms delay for all attempts
    const delay = Duration(milliseconds: delayMs);

    // Get current viewport range for logging (using actual rendered items)
    int? firstVisibleIndex;
    int? lastVisibleIndex;
    if (scrollController.hasClients) {
      firstVisibleIndex = getFirstVisibleIndex();
      if (firstVisibleIndex != null) {
        // Find actual visible items by checking which items have context and are visible
        final currentPageStart = _currentOffset;
        final currentPageEnd =
            _currentOffset + paginationController.items.length;
        int? actualFirstVisible;
        int? actualLastVisible;

        for (int i = currentPageStart; i < currentPageEnd; i++) {
          final key = itemKeys[i];
          if (key?.currentContext != null) {
            try {
              final renderBox =
                  key!.currentContext!.findRenderObject() as RenderBox?;
              if (renderBox != null && renderBox.hasSize) {
                final scrollable = Scrollable.of(key.currentContext!);
                final scrollableRenderBox =
                    scrollable.context.findRenderObject() as RenderBox?;
                if (scrollableRenderBox != null) {
                  final itemGlobalTop = renderBox.localToGlobal(Offset.zero);
                  final itemGlobalBottom =
                      itemGlobalTop + Offset(0, renderBox.size.height);
                  final scrollableGlobalTop =
                      scrollableRenderBox.localToGlobal(Offset.zero);
                  final scrollableGlobalBottom = scrollableGlobalTop +
                      Offset(0, scrollController.position.viewportDimension);

                  // Check if item is at least partially visible
                  final isVisible =
                      itemGlobalBottom.dy > scrollableGlobalTop.dy &&
                          itemGlobalTop.dy < scrollableGlobalBottom.dy;

                  if (isVisible) {
                    actualFirstVisible ??= i;
                    actualLastVisible = i;
                  }
                }
              }
            } catch (e) {
              // Ignore errors when checking visibility
            }
          }
        }

        firstVisibleIndex = actualFirstVisible ?? firstVisibleIndex;
        lastVisibleIndex = actualLastVisible;
      }
    }

    // Check if target is in viewport range
    final bool isTargetInViewport = firstVisibleIndex != null &&
        lastVisibleIndex != null &&
        targetIndex >= firstVisibleIndex &&
        targetIndex <= lastVisibleIndex;

    AppLogger.log(
      'PaginatedScrollManager',
      '_retryEnsureVisible: Attempt $attempt/$maxAttempts for targetIndex=$targetIndex, delay=${delayMs}ms, viewportRange=[$firstVisibleIndex, $lastVisibleIndex], isTargetInViewport=$isTargetInViewport',
    );

    Future.delayed(delay, () {
      if (!scrollController.hasClients) return;

      // If target is not in viewport and we've tried a few times, scroll again
      // This handles cases where the initial scroll didn't reach the target
      if (!isTargetInViewport && attempt >= 3 && attempt <= 6) {
        AppLogger.log(
          'PaginatedScrollManager',
          '_retryEnsureVisible: Target not in viewport after $attempt attempts, scrolling again. targetIndex=$targetIndex, viewportRange=[$firstVisibleIndex, $lastVisibleIndex]',
          level: LogLevel.info,
        );

        // Recalculate predicted position (may be more accurate now with updated height cache)
        final viewportHeight = scrollController.position.viewportDimension;
        final predictedOffset = _scrollMapper?.indexToScrollPosition(
              targetIndex,
              viewportHeight: viewportHeight,
              alignment: alignment,
            ) ??
            heightCache.calculateScrollOffset(
              targetIndex,
              viewportHeight,
              alignment,
            );

        final currentPosition = scrollController.position.pixels;
        final maxScrollExtent = scrollController.position.maxScrollExtent;
        final clampedOffset = predictedOffset.clamp(0.0, maxScrollExtent);

        // Calculate distance to target
        final distanceToTarget = (clampedOffset - currentPosition).abs();

        AppLogger.log(
          'PaginatedScrollManager',
          '_retryEnsureVisible: Re-scrolling to predicted position. targetIndex=$targetIndex, currentPosition=${currentPosition.toStringAsFixed(1)}, predictedOffset=${predictedOffset.toStringAsFixed(1)}, clampedOffset=${clampedOffset.toStringAsFixed(1)}, distance=${distanceToTarget.toStringAsFixed(1)}',
          level: LogLevel.info,
        );

        // Scroll to predicted position
        scrollController.jumpTo(clampedOffset);

        // Measure heights around target after scrolling
        const measureRangeSize = 10;
        final measureStartIndex =
            (targetIndex - measureRangeSize).clamp(0, _totalItemsCount - 1);
        final measureEndIndex =
            (targetIndex + measureRangeSize).clamp(0, _totalItemsCount - 1);
        measureRange(measureStartIndex, measureEndIndex);

        // Wait for scroll and rendering, then retry
        Future.delayed(const Duration(milliseconds: 400), () {
          if (!scrollController.hasClients) return;
          _retryEnsureVisible(
            targetIndex,
            targetKey,
            alignment,
            maxAttempts: maxAttempts,
            attempt: attempt + 1,
          );
        });
        return;
      }

      // Try to get the key if it wasn't provided
      final key = targetKey ?? itemKeys[targetIndex];
      if (key == null) {
        // Key still doesn't exist, retry
        if (attempt < maxAttempts) {
          _retryEnsureVisible(
            targetIndex,
            null,
            alignment,
            maxAttempts: maxAttempts,
            attempt: attempt + 1,
          );
        }
        return;
      }

      final context = key.currentContext;
      if (context == null) {
        // Context still not available, retry
        if (attempt < maxAttempts) {
          _retryEnsureVisible(
            targetIndex,
            key,
            alignment,
            maxAttempts: maxAttempts,
            attempt: attempt + 1,
          );
        }
        return;
      }

      try {
        final renderBox = context.findRenderObject() as RenderBox?;
        if (renderBox == null || !renderBox.hasSize) {
          // RenderBox not ready, retry
          if (attempt < maxAttempts) {
            _retryEnsureVisible(
              targetIndex,
              key,
              alignment,
              maxAttempts: maxAttempts,
              attempt: attempt + 1,
            );
          }
          return;
        }

        // Measure height before ensureVisible
        if (itemKeys.containsKey(targetIndex)) {
          heightCache.measureAndCacheHeight(targetIndex, key);
        }

        // Use ensureVisible to scroll to the target
        Scrollable.ensureVisible(
          context,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
          alignment: alignment,
        );

        AppLogger.log(
          'PaginatedScrollManager',
          '_retryEnsureVisible: Successfully used ensureVisible on attempt $attempt. targetIndex=$targetIndex',
          level: LogLevel.info,
        );

        // Verify after a delay
        Future.delayed(const Duration(milliseconds: 300), () {
          if (!scrollController.hasClients) return;
          final ctx = key.currentContext;
          if (ctx != null) {
            try {
              final rb = ctx.findRenderObject() as RenderBox?;
              if (rb != null && rb.hasSize) {
                final scrollable = Scrollable.of(ctx);
                final scrollableRenderBox =
                    scrollable.context.findRenderObject() as RenderBox?;
                if (scrollableRenderBox != null) {
                  final itemGlobalTop = rb.localToGlobal(Offset.zero);
                  final itemGlobalBottom =
                      itemGlobalTop + Offset(0, rb.size.height);
                  final scrollableGlobalTop =
                      scrollableRenderBox.localToGlobal(Offset.zero);
                  final scrollableGlobalBottom = scrollableGlobalTop +
                      Offset(0, scrollController.position.viewportDimension);

                  const margin = 30;
                  final isFullyVisible =
                      itemGlobalTop.dy >= (scrollableGlobalTop.dy - margin) &&
                          itemGlobalBottom.dy <=
                              (scrollableGlobalBottom.dy + margin);

                  if (!isFullyVisible && attempt < maxAttempts) {
                    // Still not visible, retry
                    AppLogger.log(
                      'PaginatedScrollManager',
                      '_retryEnsureVisible: Target not fully visible after ensureVisible, retrying. targetIndex=$targetIndex, attempt=$attempt',
                      level: LogLevel.warn,
                    );
                    _retryEnsureVisible(
                      targetIndex,
                      key,
                      alignment,
                      maxAttempts: maxAttempts,
                      attempt: attempt + 1,
                    );
                  } else if (isFullyVisible) {
                    AppLogger.log(
                      'PaginatedScrollManager',
                      '_retryEnsureVisible: Target is now fully visible. targetIndex=$targetIndex',
                      level: LogLevel.info,
                    );
                  }
                }
              }
            } catch (e) {
              AppLogger.log(
                'PaginatedScrollManager',
                '_retryEnsureVisible: Error in verification: $e',
                level: LogLevel.warn,
              );
            }
          }
        });
      } catch (e) {
        AppLogger.log(
          'PaginatedScrollManager',
          '_retryEnsureVisible: Error on attempt $attempt: $e. Will retry.',
          level: LogLevel.warn,
        );
        // Retry on error
        if (attempt < maxAttempts) {
          _retryEnsureVisible(
            targetIndex,
            key,
            alignment,
            maxAttempts: maxAttempts,
            attempt: attempt + 1,
          );
        }
      }
    });
  }

  /// Dispose resources
  void dispose() {
    scrollController.removeListener(_onScroll);
    paginationController.removeListener(_onPaginationDataChanged);
    clearSavedPosition();
  }
}
