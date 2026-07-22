// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/utils/app_logger.dart';
import '../models/compare_document_model.dart';
import '../models/compare_reading_layout_mode.dart';

/// In-memory compare-reading session (survives route pop while app runs).
class CompareReadingSession {
  const CompareReadingSession({
    this.source,
    this.target,
    this.linkedScroll = true,
    this.layoutMode = CompareReadingLayoutMode.compare,
  });

  final CompareDocumentModel? source;
  final CompareDocumentModel? target;
  final bool linkedScroll;
  final CompareReadingLayoutMode layoutMode;

  bool get bothReady =>
      source != null &&
      target != null &&
      source!.isReady &&
      target!.isReady;

  bool get kindsMatch => bothReady && source!.kind == target!.kind;

  bool get canShowCompare => bothReady && kindsMatch;

  CompareReadingSession copyWith({
    CompareDocumentModel? source,
    CompareDocumentModel? target,
    bool? linkedScroll,
    CompareReadingLayoutMode? layoutMode,
    bool clearSource = false,
    bool clearTarget = false,
  }) {
    return CompareReadingSession(
      source: clearSource ? null : (source ?? this.source),
      target: clearTarget ? null : (target ?? this.target),
      linkedScroll: linkedScroll ?? this.linkedScroll,
      layoutMode: layoutMode ?? this.layoutMode,
    );
  }
}

class CompareReadingSessionNotifier
    extends StateNotifier<CompareReadingSession> {
  CompareReadingSessionNotifier() : super(const CompareReadingSession());

  void setSource(CompareDocumentModel? doc) {
    state = state.copyWith(source: doc, clearSource: doc == null);
  }

  void setTarget(CompareDocumentModel? doc) {
    state = state.copyWith(target: doc, clearTarget: doc == null);
  }

  void setLinkedScroll(bool enabled) {
    if (state.linkedScroll == enabled) {
      return;
    }
    state = state.copyWith(linkedScroll: enabled);
  }

  void setLayoutMode(CompareReadingLayoutMode mode) {
    if (state.layoutMode == mode) {
      return;
    }
    AppLogger.log(
      'CompareReadingSession',
      'layoutMode ${state.layoutMode} -> $mode',
      level: LogLevel.info,
    );
    state = state.copyWith(layoutMode: mode);
  }

  /// Double-tap source: enter source-only, or return to compare from source-only.
  void toggleSourceSolo() {
    if (state.layoutMode == CompareReadingLayoutMode.sourceOnly) {
      setLayoutMode(CompareReadingLayoutMode.compare);
    } else {
      setLayoutMode(CompareReadingLayoutMode.sourceOnly);
    }
  }

  /// Double-tap target: enter target-only, or return to compare from target-only.
  void toggleTargetSolo() {
    if (state.layoutMode == CompareReadingLayoutMode.targetOnly) {
      setLayoutMode(CompareReadingLayoutMode.compare);
    } else {
      setLayoutMode(CompareReadingLayoutMode.targetOnly);
    }
  }

  void clearSession() {
    state = const CompareReadingSession();
  }
}

/// Kept alive so leaving compare reading and returning restores open files.
final StateNotifierProvider<CompareReadingSessionNotifier,
        CompareReadingSession> compareReadingSessionProvider =
    StateNotifierProvider<CompareReadingSessionNotifier, CompareReadingSession>(
  (StateNotifierProviderRef<CompareReadingSessionNotifier,
          CompareReadingSession>
      ref) {
    ref.keepAlive();
    return CompareReadingSessionNotifier();
  },
);
