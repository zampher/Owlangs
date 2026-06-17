// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// Builds the translation segment panel for PDF revision mode.
typedef PdfRevisionSegmentPanelBuilder = Widget Function({
  required Set<int> selectedSegmentIndices,
  ValueListenable<Set<int>>? selectedSegmentIndicesListenable,
  required void Function(int index, bool selected) onSegmentSelectionToggle,
  Set<int> Function()? getFilteredSelectableSegmentIndices,
  required void Function(Set<int> indices) onBulkSelectAll,
  required void Function(Set<int> indices) onBulkInvertSelection,
  Future<void> Function()? onBatchFontApply,
  Future<void> Function(double delta)? onBatchFontSizeStep,
  ScrollController? segmentScrollController,
  bool showSegmentScrollbar,
});
