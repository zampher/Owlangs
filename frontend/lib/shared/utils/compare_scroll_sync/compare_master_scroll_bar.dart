// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

import 'compare_scroll_sync_base.dart';

/// Single shared vertical scrollbar for full-document HTML compare preview.
class CompareMasterScrollBar extends StatefulWidget {
  const CompareMasterScrollBar({
    required this.group,
    required this.viewportHeight,
    super.key,
  });

  final CompareScrollSyncGroup group;
  final double viewportHeight;

  @override
  State<CompareMasterScrollBar> createState() => _CompareMasterScrollBarState();
}

class _CompareMasterScrollBarState extends State<CompareMasterScrollBar> {
  final ScrollController _controller = ScrollController();

  @override
  void initState() {
    super.initState();
    widget.group.attachMasterScroll(
      controller: _controller,
      onMetricsChanged: () {
        if (mounted) {
          setState(() {});
        }
      },
    );
    for (final int delayMs in <int>[200, 500, 1000, 2000, 4000]) {
      Future<void>.delayed(Duration(milliseconds: delayMs), () {
        if (mounted) {
          widget.group.refreshScrollMetrics();
        }
      });
    }
  }

  @override
  void didUpdateWidget(covariant CompareMasterScrollBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.group != widget.group ||
        oldWidget.viewportHeight != widget.viewportHeight) {
      oldWidget.group.detachMasterScroll();
      widget.group.attachMasterScroll(
        controller: _controller,
        onMetricsChanged: () {
          if (mounted) {
            setState(() {});
          }
        },
      );
    }
  }

  @override
  void dispose() {
    widget.group.detachMasterScroll();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.group.enabled) {
      return const SizedBox.shrink();
    }

    final double extent = widget.group.masterScrollExtent;
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

    final double childHeight = extent + widget.viewportHeight;
    return SizedBox(
      width: 14,
      child: Scrollbar(
        controller: _controller,
        thumbVisibility: true,
        child: SingleChildScrollView(
          controller: _controller,
          physics: const ClampingScrollPhysics(),
          child: SizedBox(height: childHeight),
        ),
      ),
    );
  }
}
