// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../../l10n/app_localizations.dart';

/// Toolbar button for exclusion panel
/// Displays excluded count and toggle panel expansion
class ExclusionPanelButton extends StatelessWidget {
  const ExclusionPanelButton({
    required this.excludedCount,
    required this.isExpanded,
    required this.onToggle,
    super.key,
  });

  final int excludedCount;
  final bool isExpanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    // Use filter_list icon for better recognition, with color indicating state
    final Color iconColor = isExpanded
        ? (excludedCount > 0 ? Colors.orange.shade700 : Colors.blue.shade700)
        : (excludedCount > 0 ? Colors.orange.shade600 : Colors.grey.shade600);

    return IconButton(
      icon: Icon(
        Icons.filter_list,
        size: 16,
        color: iconColor,
      ),
      tooltip: isExpanded
          ? l10n.exclusionPanelCollapseFilterPanel
          : l10n.exclusionPanelExpandFilterPanel,
      onPressed: onToggle,
      padding: EdgeInsets.zero,
      constraints: const BoxConstraints(
        minWidth: 28,
        minHeight: 28,
      ),
    );
  }
}
