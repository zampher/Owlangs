// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// Proportional linked scroll between two panes plus a shared master scrollbar.
class ProportionalLinkedPaneScrollCoordinator {
  ProportionalLinkedPaneScrollCoordinator({
    required ScrollController leadingController,
    required ScrollController trailingController,
    required ScrollController masterController,
  })  : _leading = leadingController,
        _trailing = trailingController,
        _master = masterController;

  final ScrollController _leading;
  final ScrollController _trailing;
  final ScrollController _master;

  bool enabled = false;
  bool _propagating = false;
  VoidCallback? _onMetricsChanged;

  ScrollController get masterController => _master;

  double get masterScrollExtent {
    final double leadingMax =
        _leading.hasClients ? _leading.position.maxScrollExtent : 0;
    final double trailingMax =
        _trailing.hasClients ? _trailing.position.maxScrollExtent : 0;
    return leadingMax > trailingMax ? leadingMax : trailingMax;
  }

  void attach({VoidCallback? onMetricsChanged}) {
    _onMetricsChanged = onMetricsChanged;
    _leading.addListener(_onLeadingScrolled);
    _trailing.addListener(_onTrailingScrolled);
    _master.addListener(_onMasterScrolled);
  }

  void dispose() {
    _leading.removeListener(_onLeadingScrolled);
    _trailing.removeListener(_onTrailingScrolled);
    _master.removeListener(_onMasterScrolled);
    _onMetricsChanged = null;
  }

  void refreshMetrics() {
    _onMetricsChanged?.call();
  }

  void _onLeadingScrolled() {
    if (!enabled || _propagating) {
      return;
    }
    _syncProportional(_leading, _trailing);
    _updateMasterFrom(_leading);
  }

  void _onTrailingScrolled() {
    if (!enabled || _propagating) {
      return;
    }
    _syncProportional(_trailing, _leading);
    _updateMasterFrom(_trailing);
  }

  void _onMasterScrolled() {
    if (!enabled || _propagating) {
      return;
    }
    _applyMasterToPanes();
  }

  void _syncProportional(ScrollController source, ScrollController target) {
    if (!source.hasClients || !target.hasClients) {
      return;
    }
    final double sourceMax = source.position.maxScrollExtent;
    final double targetMax = target.position.maxScrollExtent;
    if (sourceMax <= 0 || targetMax <= 0) {
      return;
    }
    final double ratio = source.offset / sourceMax;
    final double targetOffset = ratio * targetMax;
    if ((target.offset - targetOffset).abs() <= 15) {
      return;
    }
    _propagating = true;
    try {
      target.jumpTo(targetOffset);
    } finally {
      _propagating = false;
    }
  }

  void _updateMasterFrom(ScrollController source) {
    if (!_master.hasClients) {
      return;
    }
    final double maxExtent = masterScrollExtent;
    if (maxExtent <= 0 || !source.hasClients) {
      return;
    }
    final double sourceMax = source.position.maxScrollExtent;
    if (sourceMax <= 0) {
      return;
    }
    final double masterOffset = source.offset / sourceMax * maxExtent;
    if ((_master.offset - masterOffset).abs() <= 2) {
      return;
    }
    _propagating = true;
    try {
      _master.jumpTo(masterOffset);
    } finally {
      _propagating = false;
    }
  }

  void _applyMasterToPanes() {
    if (!_master.hasClients) {
      return;
    }
    final double maxExtent = masterScrollExtent;
    if (maxExtent <= 0) {
      return;
    }
    final double ratio = _master.offset / maxExtent;
    _propagating = true;
    try {
      if (_leading.hasClients) {
        final double max = _leading.position.maxScrollExtent;
        if (max > 0) {
          _leading.jumpTo(ratio * max);
        }
      }
      if (_trailing.hasClients) {
        final double max = _trailing.position.maxScrollExtent;
        if (max > 0) {
          _trailing.jumpTo(ratio * max);
        }
      }
    } finally {
      _propagating = false;
    }
  }
}

/// Shared vertical scrollbar placed between two proportionally linked panes.
class ProportionalLinkedPaneScrollBar extends StatelessWidget {
  const ProportionalLinkedPaneScrollBar({
    required this.coordinator,
    required this.viewportHeight,
    super.key,
  });

  final ProportionalLinkedPaneScrollCoordinator coordinator;
  final double viewportHeight;

  @override
  Widget build(BuildContext context) {
    if (!coordinator.enabled) {
      return const SizedBox.shrink();
    }

    final double extent = coordinator.masterScrollExtent;
    if (extent <= 0) {
      return const SizedBox(
        width: 14,
        child: Center(
          child: SizedBox(
            width: 4,
            height: 48,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: Color(0x33000000),
                borderRadius: BorderRadius.all(Radius.circular(2)),
              ),
            ),
          ),
        ),
      );
    }

    final ScrollController masterController = coordinator.masterController;
    final double childHeight = extent + viewportHeight;
    return SizedBox(
      width: 14,
      child: Scrollbar(
        controller: masterController,
        thumbVisibility: true,
        child: SingleChildScrollView(
          controller: masterController,
          physics: const ClampingScrollPhysics(),
          child: SizedBox(height: childHeight),
        ),
      ),
    );
  }
}
