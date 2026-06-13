// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

/// Builds the left-hand translation segment panel for PDF revision mode.
typedef PdfRevisionSegmentPanelBuilder = Widget Function({
  required Set<int> selectedSegmentIndices,
  required void Function(int index, bool selected) onSegmentSelectionToggle,
  required Set<int> Function() getFilteredSelectableSegmentIndices,
  required void Function(Set<int> indices) onBulkSelectAll,
  required void Function(Set<int> indices) onBulkInvertSelection,
});
