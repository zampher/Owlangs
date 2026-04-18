// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../../l10n/app_localizations.dart';
import 'exclusion_filter_section.dart';
import 'exclusion_statistics_section.dart';

/// Main exclusion panel widget
/// Combines statistics, filter, and category exclusion control sections
class ExclusionPanelWidget extends StatefulWidget {
  const ExclusionPanelWidget({
    required this.exclusionCounts,
    required this.totalSegments,
    required this.excludedCount,
    required this.failedCount,
    required this.selectedFilters,
    required this.onFiltersChanged,
    required this.filterMode,
    required this.onFilterModeChanged,
    this.categoryExclusionStates,
    this.onCategoryExclusionChanged,
    this.onPanelCollapsed, // Callback when panel is collapsed (Translate phase only)
    this.onExcludeAll, // Extract phase: exclude all segments (user exclusion for rest)
    this.onCancelUserExclusion, // Extract phase: cancel only user exclusions
    this.onClearAllExclusionsExceptImage, // Extract phase: clear all exclusions except image segments
    super.key,
  });

  final Map<String, int> exclusionCounts;
  final int totalSegments;
  final int excludedCount;
  final int failedCount; // Number of failed segments
  final Set<String> selectedFilters;
  final Function(Set<String>) onFiltersChanged;
  final String filterMode; // 'rebuild' or 'page'
  final Function(String) onFilterModeChanged;
  final Map<String, bool>? categoryExclusionStates;
  final Function(String category, bool exclude)? onCategoryExclusionChanged;
  final VoidCallback? onPanelCollapsed; // Callback when panel is collapsed
  /// Called when "Exclude All" is tapped (Extract phase). Parent should call API and refresh.
  final Future<void> Function()? onExcludeAll;
    /// Called when "Restore Auto Exclusion" is tapped (Extract phase). Restores to Extract completion state.
  final Future<void> Function()? onCancelUserExclusion;
  /// Called when "Clear All Exclusions" is tapped (Extract phase). Removes all exclusions except image segments.
  final Future<void> Function()? onClearAllExclusionsExceptImage;

  @override
  State<ExclusionPanelWidget> createState() => _ExclusionPanelWidgetState();
}

class _ExclusionPanelWidgetState extends State<ExclusionPanelWidget> {
  // Session-level state: track if panel has been collapsed in this session
  static bool _hasBeenCollapsedInSession = false;
  bool _isCollapsed = false;
  bool _excludeAllLoading = false;
  bool _cancelUserExclusionLoading = false;
  bool _clearAllExclusionsLoading = false;

  // Check if this is Translate phase
  bool get _isTranslatePhase => widget.categoryExclusionStates == null;

  @override
  void initState() {
    super.initState();
    // Always start expanded when panel is opened
    // The session-level state is only used to remember preference, but when panel is reopened,
    // we want it to be expanded so user can see the content
    _isCollapsed = false;
  }

  void _toggleCollapse() {
    setState(() {
      _isCollapsed = !_isCollapsed;
      if (_isCollapsed) {
        _hasBeenCollapsedInSession = true;
        // Notify parent to close the panel completely (both Translate and Extract phases)
        // This ensures the panel is fully closed and can be reopened properly
        if (widget.onPanelCollapsed != null) {
          widget.onPanelCollapsed!();
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    // In Translate phase: completely hide when collapsed
    if (_isTranslatePhase && _isCollapsed) {
      return const SizedBox.shrink();
    }

    return AnimatedSize(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeInOut,
      child: Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          border: Border(
            top: BorderSide(
              color: Theme.of(context).dividerColor,
            ),
          ),
        ),
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            // Statistics section (only shown in Extract phase when categoryExclusionStates is provided)
            if (widget.categoryExclusionStates != null &&
                widget.onCategoryExclusionChanged != null) ...<Widget>[
              ExclusionStatisticsSection(
                exclusionCounts: widget.exclusionCounts,
                totalSegments: widget.totalSegments,
                excludedCount: widget.excludedCount,
                categoryExclusionStates: widget.categoryExclusionStates,
                onCategoryExclusionChanged: widget.onCategoryExclusionChanged,
              ),
              if (widget.onExcludeAll != null ||
                  widget.onCancelUserExclusion != null ||
                  widget.onClearAllExclusionsExceptImage != null) ...<Widget>[
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: <Widget>[
                    if (widget.onExcludeAll != null)
                      _ActionButton(
                        label: AppLocalizations.of(context)!.exclusionPanelExcludeAll,
                        loading: _excludeAllLoading,
                        onPressed: () async {
                          if (_excludeAllLoading) return;
                          setState(() => _excludeAllLoading = true);
                          try {
                            await widget.onExcludeAll!();
                          } finally {
                            if (mounted) setState(() => _excludeAllLoading = false);
                          }
                        },
                      ),
                    if (widget.onCancelUserExclusion != null)
                      _ActionButton(
                        label: AppLocalizations.of(context)!.exclusionPanelCancelUserExclusion,
                        loading: _cancelUserExclusionLoading,
                        onPressed: () async {
                          if (_cancelUserExclusionLoading) return;
                          setState(() => _cancelUserExclusionLoading = true);
                          try {
                            await widget.onCancelUserExclusion!();
                          } finally {
                            if (mounted) setState(() => _cancelUserExclusionLoading = false);
                          }
                        },
                      ),
                    if (widget.onClearAllExclusionsExceptImage != null)
                      _ActionButton(
                        label: AppLocalizations.of(context)!.exclusionPanelClearAllExclusions,
                        loading: _clearAllExclusionsLoading,
                        onPressed: () async {
                          if (_clearAllExclusionsLoading) return;
                          setState(() => _clearAllExclusionsLoading = true);
                          try {
                            await widget.onClearAllExclusionsExceptImage!();
                          } finally {
                            if (mounted) setState(() => _clearAllExclusionsLoading = false);
                          }
                        },
                      ),
                  ],
                ),
                const SizedBox(height: 12),
              ],
              const Divider(height: 16),
            ],
            // Filter section
            ExclusionFilterSection(
              selectedFilters: widget.selectedFilters,
              onFiltersChanged: widget.onFiltersChanged,
              exclusionCounts: widget.exclusionCounts,
              totalSegments: widget.totalSegments,
              excludedCount: widget.excludedCount,
              failedCount: widget.failedCount,
              filterMode: widget.filterMode,
              onFilterModeChanged: widget.onFilterModeChanged,
              // In Translate phase, categoryExclusionStates is null, so use compact layout
              isTranslatePhase: _isTranslatePhase,
              // Add collapse callback for both Translate and Extract phases
              onCollapse: _toggleCollapse,
            ),
          ],
        ),
      ),
    );
  }
}

/// Small button for Exclude All / Cancel User Exclusion with optional loading state
class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.loading,
    required this.onPressed,
  });

  final String label;
  final bool loading;
  final Future<void> Function() onPressed;

  @override
  Widget build(BuildContext context) => SizedBox(
      height: 32,
      child: OutlinedButton(
        onPressed: loading ? null : onPressed,
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          minimumSize: const Size(0, 32),
        ),
        child: loading
            ? SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Theme.of(context).colorScheme.primary,
                ),
              )
            : Text(label, style: const TextStyle(fontSize: 12)),
      ),
    );
}
