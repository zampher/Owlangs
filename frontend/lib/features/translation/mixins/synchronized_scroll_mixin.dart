// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'package:flutter/material.dart';

/// Entry for tracking scroll history
class _ScrollHistoryEntry {
  _ScrollHistoryEntry(this.offset, this.timestamp);
  final double offset;
  final DateTime timestamp;
}

/// Mixin for synchronized scrolling between two scroll controllers
/// Used in Extract, Glossary, and Translate tabs
mixin SynchronizedScrollMixin<T extends StatefulWidget> on State<T> {
  ScrollController? scrollController1;
  ScrollController? scrollController2;

  /// When false, scroll events are ignored (bind/unbind without disposing).
  bool synchronizedScrollEnabled = true;

  // Track which controller is currently being synced (prevents recursive calls from same controller)
  ScrollController? _syncingController;

  // Throttle mechanism: limit sync frequency to ~60fps (16ms) for smoother scrolling
  Timer? _syncTimer1;
  Timer? _syncTimer2;
  DateTime _lastSyncTime1 = DateTime(0);
  DateTime _lastSyncTime2 = DateTime(0);
  static const Duration _throttleDuration =
      Duration(milliseconds: 16); // ~60fps for smoother feel

  // Track pending sync operations to avoid duplicate work
  bool _pendingSync1 = false;
  bool _pendingSync2 = false;

  // Track which controller is being actively scrolled by user
  ScrollController? _activeScrollController;
  Timer? _activeScrollTimer;

  // Track if isScrollingNotifier listeners were successfully added
  bool _hasScrollingNotifier1 = false;
  bool _hasScrollingNotifier2 = false;

  // Track consecutive scroll events from each controller for fallback detection
  int _consecutiveScrolls1 = 0;
  int _consecutiveScrolls2 = 0;
  static const int _consecutiveScrollThreshold =
      3; // After 3 consecutive scrolls, assume it's the active controller

  // Track scroll history for speed calculation
  final Map<ScrollController, List<_ScrollHistoryEntry>> _scrollHistory =
      <ScrollController, List<_ScrollHistoryEntry>>{};
  static const int _maxHistoryEntries = 5;
  static const Duration _historyWindow = Duration(milliseconds: 100);

  /// Initialize scroll controllers
  void initSynchronizedScroll({
    ScrollController? controller1,
    ScrollController? controller2,
  }) {
    scrollController1 = controller1 ?? ScrollController();
    scrollController2 = controller2 ?? ScrollController();

    // Listen to scroll events and synchronize
    scrollController1?.addListener(_onScroll1);
    scrollController2?.addListener(_onScroll2);

    // Initialize scroll history
    _scrollHistory[scrollController1!] = <_ScrollHistoryEntry>[];
    _scrollHistory[scrollController2!] = <_ScrollHistoryEntry>[];

    // Use isScrollingNotifier to detect when scrolling starts/stops
    // Try to add listeners immediately and also retry after a delay
    void tryAddListeners() {
      if (mounted &&
          (scrollController1?.hasClients ?? false) &&
          !_hasScrollingNotifier1) {
        try {
          scrollController1?.position.isScrollingNotifier
              .addListener(_onScrollingStateChanged1);
          _hasScrollingNotifier1 = true;
        } catch (e) {
          _hasScrollingNotifier1 = false;
        }
      }
      if (mounted &&
          (scrollController2?.hasClients ?? false) &&
          !_hasScrollingNotifier2) {
        try {
          scrollController2?.position.isScrollingNotifier
              .addListener(_onScrollingStateChanged2);
          _hasScrollingNotifier2 = true;
        } catch (e) {
          _hasScrollingNotifier2 = false;
        }
      }

      // If isScrollingNotifier is not available, use fallback: set active controller on first scroll
    }

    // Try immediately
    WidgetsBinding.instance.addPostFrameCallback((_) {
      tryAddListeners();

      // Retry after a delay if controllers weren't ready
      if (!_hasScrollingNotifier1 || !_hasScrollingNotifier2) {
        Future.delayed(const Duration(milliseconds: 500), () {
          if (mounted) {
            tryAddListeners();
          }
        });
      }
    });
  }

  void _onScrollingStateChanged1() {
    final isScrolling =
        scrollController1?.position.isScrollingNotifier.value ?? false;
    if (isScrolling) {
      _activeScrollController = scrollController1;
      _activeScrollTimer?.cancel();
    } else {
      // Scrolling stopped, clear active controller after a short delay
      _activeScrollTimer?.cancel();
      _activeScrollTimer = Timer(const Duration(milliseconds: 100), () {
        if (_activeScrollController == scrollController1) {
          _activeScrollController = null;
        }
      });
    }
  }

  void _onScrollingStateChanged2() {
    final isScrolling =
        scrollController2?.position.isScrollingNotifier.value ?? false;
    if (isScrolling) {
      _activeScrollController = scrollController2;
      _activeScrollTimer?.cancel();
    } else {
      // Scrolling stopped, clear active controller after a short delay
      _activeScrollTimer?.cancel();
      _activeScrollTimer = Timer(const Duration(milliseconds: 100), () {
        if (_activeScrollController == scrollController2) {
          _activeScrollController = null;
        }
      });
    }
  }

  void _onScroll1() {
    if (!synchronizedScrollEnabled) {
      return;
    }
    final offset = scrollController1?.offset ?? 0;

    // Update scroll history for speed calculation
    _updateScrollHistory(scrollController1!, offset);

    // Track consecutive scrolls from controller1
    _consecutiveScrolls1++;
    _consecutiveScrolls2 = 0; // Reset counter for controller2

    // If isScrollingNotifier is not available, use fallback: set active controller on first scroll
    if (!_hasScrollingNotifier1) {
      // Fallback mode: set active controller if not set, or if it's controller1
      if (_activeScrollController == null ||
          _activeScrollController == scrollController1) {
        _activeScrollController = scrollController1;
      } else {
        // Another controller is active, skip
        return;
      }
    } else {
      // isScrollingNotifier is available, but may not trigger
      // Use fallback: if we get consecutive scrolls from controller1, assume it's active
      if (_activeScrollController != scrollController1) {
        if (_consecutiveScrolls1 >= _consecutiveScrollThreshold) {
          // After threshold consecutive scrolls, assume this is the active controller
          _activeScrollController = scrollController1;
        } else {
          return;
        }
      }
    }

    if (!mounted) {
      return;
    }

    if (scrollController1 == null || !scrollController1!.hasClients) {
      return;
    }

    // Immediately cancel any pending operations for this controller
    // This ensures we only process the latest scroll event
    _syncTimer1?.cancel();
    _syncTimer1 = null;
    _pendingSync1 = false;

    // Throttle: only sync if enough time has passed
    final now = DateTime.now();
    final timeSinceLastSync = now.difference(_lastSyncTime1);
    if (timeSinceLastSync < _throttleDuration) {
      // Mark as pending and schedule sync for later
      _pendingSync1 = true;
      _syncTimer1 = Timer(_throttleDuration, () {
        if (mounted &&
            _activeScrollController == scrollController1 &&
            _pendingSync1) {
          _pendingSync1 = false;
          _performSync(scrollController1!, scrollController2);
        }
      });
      return;
    }

    _lastSyncTime1 = now;

    // Perform immediate sync
    if (mounted && _activeScrollController == scrollController1) {
      _performSync(scrollController1!, scrollController2);
    }
  }

  void _onScroll2() {
    if (!synchronizedScrollEnabled) {
      return;
    }
    final offset = scrollController2?.offset ?? 0;

    // Update scroll history for speed calculation
    _updateScrollHistory(scrollController2!, offset);

    // Track consecutive scrolls from controller2
    _consecutiveScrolls2++;
    _consecutiveScrolls1 = 0; // Reset counter for controller1

    // If isScrollingNotifier is not available, use fallback: set active controller on first scroll
    if (!_hasScrollingNotifier2) {
      // Fallback mode: set active controller if not set, or if it's controller2
      if (_activeScrollController == null ||
          _activeScrollController == scrollController2) {
        _activeScrollController = scrollController2;
      } else {
        // Another controller is active, skip
        return;
      }
    } else {
      // isScrollingNotifier is available, but may not trigger
      // Use fallback: if we get consecutive scrolls from controller2, assume it's active
      if (_activeScrollController != scrollController2) {
        if (_consecutiveScrolls2 >= _consecutiveScrollThreshold) {
          // After threshold consecutive scrolls, assume this is the active controller
          _activeScrollController = scrollController2;
        } else {
          return;
        }
      }
    }

    if (!mounted) {
      return;
    }

    if (scrollController2 == null || !scrollController2!.hasClients) {
      return;
    }

    // Immediately cancel any pending operations for this controller
    // This ensures we only process the latest scroll event
    _syncTimer2?.cancel();
    _syncTimer2 = null;
    _pendingSync2 = false;

    // Throttle: only sync if enough time has passed
    final now = DateTime.now();
    final timeSinceLastSync = now.difference(_lastSyncTime2);
    if (timeSinceLastSync < _throttleDuration) {
      // Mark as pending and schedule sync for later
      _pendingSync2 = true;
      _syncTimer2 = Timer(_throttleDuration, () {
        if (mounted &&
            _activeScrollController == scrollController2 &&
            _pendingSync2) {
          _pendingSync2 = false;
          _performSync(scrollController2!, scrollController1);
        }
      });
      return;
    }

    _lastSyncTime2 = now;

    // Perform immediate sync
    if (mounted && _activeScrollController == scrollController2) {
      _performSync(scrollController2!, scrollController1);
    }
  }

  void _updateScrollHistory(ScrollController controller, double offset) {
    final history = _scrollHistory[controller];
    if (history == null) return;

    final now = DateTime.now();
    history.add(_ScrollHistoryEntry(offset, now));

    // Remove old entries outside the time window
    final cutoff = now.subtract(_historyWindow);
    history.removeWhere(
      (entry) => entry.timestamp.isBefore(cutoff),
    );

    // Limit history size
    if (history.length > _maxHistoryEntries) {
      history.removeRange(0, history.length - _maxHistoryEntries);
    }
  }

  double _calculateScrollSpeed(ScrollController controller) {
    final history = _scrollHistory[controller];
    if (history == null || history.length < 2) return 0;

    final now = DateTime.now();
    final cutoff = now.subtract(_historyWindow);
    final recentEntries =
        history.where((entry) => entry.timestamp.isAfter(cutoff)).toList();

    if (recentEntries.length < 2) return 0;

    final oldest = recentEntries.first;
    final newest = recentEntries.last;

    final timeDiff =
        newest.timestamp.difference(oldest.timestamp).inMilliseconds;
    if (timeDiff == 0) return 0;

    final offsetDiff = (newest.offset - oldest.offset).abs();
    return offsetDiff / timeDiff; // pixels per millisecond
  }

  void _performSync(ScrollController source, ScrollController? target) {
    if (!mounted) {
      return;
    }
    if (!source.hasClients) {
      return;
    }
    if (target == null || !target.hasClients) {
      return;
    }

    // Check if we're already syncing from the same controller to avoid recursive calls
    // But allow syncing from different controllers (e.g., if user switches controllers quickly)
    if (_syncingController == source) {
      return;
    }

    // Mark this controller as syncing
    final previousSyncing = _syncingController;
    _syncingController = source;

    try {
      _syncScroll(source, target);
    } finally {
      // Reset syncing flag immediately after sync completes
      // This allows the next scroll event to be processed without delay
      _syncingController = previousSyncing;
    }
  }

  void _syncScroll(ScrollController source, ScrollController? target) {
    // Check if controllers are still valid and have clients
    if (!source.hasClients) {
      return;
    }
    if (target == null || !target.hasClients) {
      return;
    }
    if (!mounted) {
      return;
    }

    try {
      final sourceOffset = source.offset;
      final sourceMaxScroll = source.position.maxScrollExtent;
      final targetMaxScroll = target.position.maxScrollExtent;

      if (sourceMaxScroll == 0 || targetMaxScroll == 0) {
        return;
      }

      // Calculate proportional scroll position
      final ratio = sourceOffset / sourceMaxScroll;
      final targetOffset = ratio * targetMaxScroll;
      final currentTargetOffset = target.offset;

      // Only scroll if the difference is significant (avoid jitter)
      final diff = (currentTargetOffset - targetOffset).abs();
      if (diff <= 15) {
        // Difference is too small, skip sync
        return;
      }

      // Calculate scroll speed to determine sync strategy
      final scrollSpeed = _calculateScrollSpeed(source);
      final isFastScrolling = scrollSpeed > 2.0; // pixels per millisecond

      // Use jumpTo for fast scrolling or large jumps (immediate response)
      // Use animateTo for slow scrolling and small adjustments (smooth)
      final isLargeJump = diff > 100;

      if (isFastScrolling || isLargeJump) {
        // Fast scrolling or large jump: use jumpTo for immediate response
        try {
          target.jumpTo(targetOffset);
        } catch (e) {
          // Silently ignore errors
        }
      } else {
        // Slow scrolling and small adjustment: use animateTo for smoothness
        try {
          target.animateTo(
            targetOffset,
            duration: const Duration(
              milliseconds: 16,
            ), // One frame for smooth animation
            curve: Curves.linear,
          );
        } catch (e) {
          // Fallback to jumpTo if animateTo fails
          try {
            target.jumpTo(targetOffset);
          } catch (e2) {
            // Silently ignore errors
          }
        }
      }
    } catch (e) {
      // Controller may have been disposed, silently ignore
    }
  }

  /// Scroll both controllers to a specific segment index
  void scrollToSegment(int index, {double itemHeight = 100.0}) {
    if (!mounted) return;

    final targetOffset = index * itemHeight;

    try {
      if (scrollController1?.hasClients ?? false) {
        scrollController1!.animateTo(
          targetOffset.clamp(0.0, scrollController1!.position.maxScrollExtent),
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
        );
      }
    } catch (e) {
      // Silently ignore errors
    }

    try {
      if (scrollController2?.hasClients ?? false) {
        scrollController2!.animateTo(
          targetOffset.clamp(0.0, scrollController2!.position.maxScrollExtent),
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
        );
      }
    } catch (e) {
      // Silently ignore errors
    }
  }

  @override
  void dispose() {
    // Cancel timers
    _syncTimer1?.cancel();
    _syncTimer2?.cancel();
    _activeScrollTimer?.cancel();

    // Remove listeners first to prevent callbacks after dispose
    scrollController1?.removeListener(_onScroll1);
    scrollController2?.removeListener(_onScroll2);

    // Remove isScrollingNotifier listeners
    try {
      scrollController1?.position.isScrollingNotifier
          .removeListener(_onScrollingStateChanged1);
    } catch (_) {}
    try {
      scrollController2?.position.isScrollingNotifier
          .removeListener(_onScrollingStateChanged2);
    } catch (_) {}

    // Clear references to prevent further use
    scrollController1 = null;
    scrollController2 = null;
    _activeScrollController = null;
    _syncingController = null;
    _scrollHistory.clear();

    super.dispose();
  }
}
