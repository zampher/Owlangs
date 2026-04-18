// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/entity_group.dart';
import '../utils/entity_group_helper.dart';
import 'entity_group_widget.dart';
import 'missing_placeholders_widget.dart';

/// Widget for displaying the list of detected entities with grouped view support
class EntityListWidget extends StatefulWidget {
  // Notifier for view mode changes

  const EntityListWidget({
    required this.entities,
    required this.highlightedEntityIndex,
    required this.currentNavigationIndex,
    required this.originalSegments,
    required this.segmentBoundaries,
    required this.anonymizedText,
    required this.onNavigateToNext,
    required this.onEntityTap,
    required this.onEditEntity,
    required this.onShowEntityDetails,
    required this.onDeleteEntity,
    super.key,
    this.onAddEntity,
    this.onAddMissingPlaceholder,
    this.onScanMissing,
    this.entitiesExpanded,
    this.onFillAllMissing,
    this.viewModeNotifier,
  });
  final List<dynamic> entities;
  final int? highlightedEntityIndex;
  final int currentNavigationIndex;
  final List<String> originalSegments;
  final List<int> segmentBoundaries;
  final String anonymizedText;
  final VoidCallback onNavigateToNext;
  final void Function(int) onEntityTap;
  final void Function(int) onEditEntity;
  final void Function(Map<String, dynamic>) onShowEntityDetails;
  final void Function(int) onDeleteEntity;
  final void Function({String? prefillText, String? prefillType})? onAddEntity;
  final void Function(String placeholder)? onAddMissingPlaceholder;
  final VoidCallback? onScanMissing;
  final List<dynamic>?
      entitiesExpanded; // Backend-expanded entities for missing detection
  final VoidCallback? onFillAllMissing; // One-click fill all missing entities
  final ValueNotifier<bool>? viewModeNotifier;

  @override
  State<EntityListWidget> createState() => _EntityListWidgetState();
}

class _EntityListWidgetState extends State<EntityListWidget> {
  bool _isGroupedView = true; // Default to grouped view
  final Set<String> _expandedGroupKeys = <String>{};
  Set<String> _missingPlaceholders = <String>{};
  List<Map<String, String>> _missingEntitySeeds =
      <Map<String, String>>[]; // Missing entities from entitiesExpanded
  final Map<String, GlobalKey> _groupKeys = <String,
      GlobalKey<State<StatefulWidget>>>{}; // Keys for scrolling to groups
  final ScrollController _listScrollController =
      ScrollController(); // Controller for entity list scrolling

  // Checkbox selection state
  final Set<String> _selectedGroupKeys = <String>{}; // Selected group keys
  final Set<int> _selectedOccurrenceIndices =
      <int>{}; // Selected occurrence indices
  bool _skipDeleteConfirmation = false; // Whether to skip delete confirmation

  // Search state
  OverlayEntry? _searchOverlayEntry;
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';
  List<int> _searchResults = <int>[];
  int _currentSearchIndex = -1;

  @override
  void initState() {
    super.initState();
    // Notify parent about initial view mode
    widget.viewModeNotifier?.value = _isGroupedView;
    // Load skip delete confirmation preference
    _loadSkipDeleteConfirmation();
    // Use postFrameCallback to ensure data is fully ready before scanning
    // This is especially important for first-time detection results
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _scanMissingPlaceholders();
        _scanMissingEntities();
      }
    });
  }

  @override
  void dispose() {
    // Close search dialog first (before disposing controller)
    _closeSearchDialog();
    // Then dispose the controller
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadSkipDeleteConfirmation() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _skipDeleteConfirmation =
          prefs.getBool('entity_delete_skip_confirmation') ?? false;
    } catch (e) {
      // Ignore errors
    }
  }

  Future<void> _saveSkipDeleteConfirmation(bool value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('entity_delete_skip_confirmation', value);
      setState(() {
        _skipDeleteConfirmation = value;
      });
    } catch (e) {
      // Ignore errors
    }
  }

  void _toggleGroupSelection(String groupKey) {
    setState(() {
      if (_selectedGroupKeys.contains(groupKey)) {
        _selectedGroupKeys.remove(groupKey);
        // Also remove all occurrences in this group
        final groups = EntityGroupHelper.groupEntities(widget.entities);
        final group = groups.firstWhere((g) => g.groupKey == groupKey);
        for (final occurrence in group.occurrences) {
          _selectedOccurrenceIndices.remove(occurrence.index);
        }
      } else {
        _selectedGroupKeys.add(groupKey);
        // Also select all occurrences in this group
        final groups = EntityGroupHelper.groupEntities(widget.entities);
        final group = groups.firstWhere((g) => g.groupKey == groupKey);
        for (final occurrence in group.occurrences) {
          _selectedOccurrenceIndices.add(occurrence.index);
        }
      }
    });
  }

  void _toggleOccurrenceSelection(int occurrenceIndex) {
    setState(() {
      if (_selectedOccurrenceIndices.contains(occurrenceIndex)) {
        _selectedOccurrenceIndices.remove(occurrenceIndex);
        // Check if group should be deselected
        final groups = EntityGroupHelper.groupEntities(widget.entities);
        for (final group in groups) {
          if (group.occurrences.any((o) => o.index == occurrenceIndex)) {
            final allSelected = group.occurrences.every(
              (o) => _selectedOccurrenceIndices.contains(o.index),
            );
            if (!allSelected && _selectedGroupKeys.contains(group.groupKey)) {
              _selectedGroupKeys.remove(group.groupKey);
            }
          }
        }
      } else {
        _selectedOccurrenceIndices.add(occurrenceIndex);
        // Check if all occurrences in group are selected
        final groups = EntityGroupHelper.groupEntities(widget.entities);
        for (final group in groups) {
          if (group.occurrences.any((o) => o.index == occurrenceIndex)) {
            final allSelected = group.occurrences.every(
              (o) => _selectedOccurrenceIndices.contains(o.index),
            );
            if (allSelected && !_selectedGroupKeys.contains(group.groupKey)) {
              _selectedGroupKeys.add(group.groupKey);
            }
          }
        }
      }
    });
  }

  void _clearSelection() {
    setState(() {
      _selectedGroupKeys.clear();
      _selectedOccurrenceIndices.clear();
    });
  }

  void _toggleSearchDialog() {
    if (_searchOverlayEntry != null) {
      _closeSearchDialog();
    } else {
      _showSearchDialog();
    }
  }

  void _showSearchDialog() {
    _searchController.addListener(_onSearchChanged);

    _searchOverlayEntry = OverlayEntry(
      builder: (context) => Positioned(
        top: 100,
        left: 20,
        right: 20,
        child: Material(
          elevation: 8,
          borderRadius: BorderRadius.circular(8),
          color: Theme.of(context).colorScheme.surface,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: Theme.of(context).dividerColor,
              ),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Icon(
                      Icons.search,
                      size: 20,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextField(
                        controller: _searchController,
                        autofocus: true,
                        decoration: const InputDecoration(
                          hintText: 'Search entities (text, type, placeholder)',
                          border: InputBorder.none,
                          isDense: true,
                          contentPadding: EdgeInsets.symmetric(vertical: 8),
                        ),
                        onSubmitted: (_) {
                          if (_searchResults.isNotEmpty) {
                            _navigateToSearchResult(0);
                          }
                        },
                      ),
                    ),
                    if (_searchQuery.isNotEmpty) ...<Widget>[
                      Text(
                        '${_currentSearchIndex >= 0 ? _currentSearchIndex + 1 : 0}/${_searchResults.length}',
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        icon: const Icon(Icons.arrow_upward, size: 18),
                        onPressed: _searchResults.isNotEmpty
                            ? () =>
                                _navigateToSearchResult(_currentSearchIndex - 1)
                            : null,
                        tooltip: 'Previous',
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                      ),
                      IconButton(
                        icon: const Icon(Icons.arrow_downward, size: 18),
                        onPressed: _searchResults.isNotEmpty
                            ? () =>
                                _navigateToSearchResult(_currentSearchIndex + 1)
                            : null,
                        tooltip: 'Next',
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                      ),
                      const SizedBox(width: 4),
                    ],
                    IconButton(
                      icon: const Icon(Icons.close, size: 18),
                      onPressed: _closeSearchDialog,
                      tooltip: 'Close',
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
                if (_searchQuery.isNotEmpty &&
                    _searchResults.isEmpty) ...<Widget>[
                  const SizedBox(height: 8),
                  Text(
                    'No results found',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ] else if (_searchQuery.isNotEmpty &&
                    _searchResults.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 8),
                  Text(
                    'Found ${_searchResults.length} result${_searchResults.length > 1 ? 's' : ''}',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );

    Overlay.of(context).insert(_searchOverlayEntry!);
  }

  void _closeSearchDialog() {
    // Remove listener if controller is still valid
    try {
      _searchController.removeListener(_onSearchChanged);
    } catch (e) {
      // Controller may already be disposed, ignore
    }
    _searchOverlayEntry?.remove();
    _searchOverlayEntry = null;
    // Clear controller only if it's still valid
    try {
      _searchController.clear();
    } catch (e) {
      // Controller may already be disposed, ignore
    }
    // Only call setState if widget is still mounted and not being disposed
    // Check mounted first, then verify we can safely call setState
    if (mounted) {
      try {
        setState(() {
          _searchQuery = '';
          _searchResults = <int>[];
          _currentSearchIndex = -1;
        });
      } catch (e) {
        // Widget may be in defunct state, ignore setState error
        debugPrint(
          '[EntityListWidget] setState failed in _closeSearchDialog: $e',
        );
      }
    }
  }

  void _onSearchChanged() {
    final query = _searchController.text.trim().toLowerCase();
    setState(() {
      _searchQuery = query;
      if (query.isEmpty) {
        _searchResults = <int>[];
        _currentSearchIndex = -1;
      } else {
        _searchResults = _performSearch(query);
        _currentSearchIndex = _searchResults.isNotEmpty ? 0 : -1;
      }
    });

    // Update overlay if it exists
    if (_searchOverlayEntry != null) {
      _searchOverlayEntry!.markNeedsBuild();
    }
  }

  List<int> _performSearch(String query) {
    final results = <int>[];
    final lowerQuery = query.toLowerCase();

    for (int i = 0; i < widget.entities.length; i++) {
      final entity =
          widget.entities[i] as Map<String, dynamic>? ?? <String, dynamic>{};
      final text = (entity['text']?.toString() ?? '').toLowerCase();
      final type = (entity['type']?.toString() ?? '').toLowerCase();
      final placeholder =
          (entity['placeholder']?.toString() ?? '').toLowerCase();

      if (text.contains(lowerQuery) ||
          type.contains(lowerQuery) ||
          placeholder.contains(lowerQuery)) {
        results.add(i);
      }
    }

    return results;
  }

  void _navigateToSearchResult(int targetIndex) {
    if (_searchResults.isEmpty) return;

    // Clamp index to valid range
    final clampedIndex = targetIndex.clamp(0, _searchResults.length - 1);
    setState(() {
      _currentSearchIndex = clampedIndex;
    });

    final entityIndex = _searchResults[clampedIndex];

    // Navigate to the entity
    widget.onEntityTap(entityIndex);

    // If in grouped view, expand the group and scroll to it
    if (_isGroupedView) {
      final groups = EntityGroupHelper.groupEntities(widget.entities);
      for (final group in groups) {
        if (group.occurrences.any((o) => o.index == entityIndex)) {
          _expandAndScrollToGroup(group.groupKey);
          break;
        }
      }
    } else {
      // Scroll to the entity in flat view
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _listScrollController.hasClients) {
          // Calculate approximate scroll position
          const int itemHeight = 80; // Approximate height of each item
          final int targetOffset = entityIndex * itemHeight;
          _listScrollController.animateTo(
            targetOffset.toDouble().clamp(
                  0.0,
                  _listScrollController.position.maxScrollExtent,
                ),
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeInOut,
          );
        }
      });
    }

    // Update overlay
    if (_searchOverlayEntry != null) {
      _searchOverlayEntry!.markNeedsBuild();
    }
  }

  @override
  void didUpdateWidget(EntityListWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Re-scan if entities, anonymized text, or entitiesExpanded changed
    if (oldWidget.entities != widget.entities ||
        oldWidget.anonymizedText != widget.anonymizedText ||
        oldWidget.entitiesExpanded != widget.entitiesExpanded) {
      _scanMissingPlaceholders();
      _scanMissingEntities();
    }

    // If highlighted entity index changed and in grouped view, expand and scroll to the group
    if (_isGroupedView &&
        oldWidget.highlightedEntityIndex != widget.highlightedEntityIndex &&
        widget.highlightedEntityIndex != null) {
      final groups = EntityGroupHelper.groupEntities(widget.entities);
      for (final group in groups) {
        for (final occurrence in group.occurrences) {
          if (occurrence.index == widget.highlightedEntityIndex) {
            // Found the group containing the highlighted entity
            _expandAndScrollToGroup(group.groupKey);
            break;
          }
        }
      }
    }
  }

  void _scanMissingPlaceholders() {
    setState(() {
      _missingPlaceholders = EntityGroupHelper.scanMissingPlaceholders(
        widget.anonymizedText,
        widget.entities,
      );
    });
  }

  void _scanMissingEntities() {
    setState(() {
      _missingEntitySeeds = EntityGroupHelper.scanMissingEntitiesFromExpanded(
        widget.entities,
        widget.entitiesExpanded,
      );
    });
  }

  void _toggleGroup(String groupKey) {
    setState(() {
      if (_expandedGroupKeys.contains(groupKey)) {
        _expandedGroupKeys.remove(groupKey);
      } else {
        _expandedGroupKeys.add(groupKey);
      }
    });
  }

  /// Expand a group and scroll to make it visible
  void _expandAndScrollToGroup(String groupKey) {
    if (!_expandedGroupKeys.contains(groupKey)) {
      setState(() {
        _expandedGroupKeys.add(groupKey);
      });
    }

    // Scroll to group after expansion
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        final groupkeyObj = _groupKeys[groupKey];
        if (groupkeyObj?.currentContext != null) {
          Scrollable.ensureVisible(
            groupkeyObj!.currentContext!,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeInOut,
            alignment: 0.1,
          );
        }
      }
    });
  }

  bool _isGroupExpanded(EntityGroup group) {
    // Expand if has selected occurrence or manually expanded
    if (widget.highlightedEntityIndex != null) {
      for (final occurrence in group.occurrences) {
        if (occurrence.index == widget.highlightedEntityIndex) {
          return true;
        }
      }
    }
    return _expandedGroupKeys.contains(group.groupKey);
  }

  bool _hasSelectedOccurrence(EntityGroup group) {
    if (widget.highlightedEntityIndex == null) return false;
    return group.occurrences
        .any((o) => o.index == widget.highlightedEntityIndex);
  }

  @override
  Widget build(BuildContext context) {
    final groups = EntityGroupHelper.groupEntities(widget.entities);
    final uniqueCount = groups.length;
    final totalCount = widget.entities.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).dividerColor,
              ),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // First row: Title
              Row(
                children: <Widget>[
                  Icon(
                    Icons.label,
                    size: 18,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Detected Entities ($uniqueCount groups, $totalCount occurrences)',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              // Second row: Buttons (wrap to avoid overflow)
              Wrap(
                spacing: 8,
                runSpacing: 4,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: <Widget>[
                  ToggleButtons(
                    isSelected: <bool>[_isGroupedView, !_isGroupedView],
                    onPressed: (index) {
                      setState(() {
                        _isGroupedView = index == 0;
                        widget.viewModeNotifier?.value = _isGroupedView;
                      });
                    },
                    borderRadius: BorderRadius.circular(4),
                    constraints: const BoxConstraints(
                      minHeight: 28,
                      minWidth: 60,
                    ),
                    children: const <Widget>[
                      Padding(
                        padding: EdgeInsets.symmetric(horizontal: 8),
                        child: Text('Grouped', style: TextStyle(fontSize: 11)),
                      ),
                      Padding(
                        padding: EdgeInsets.symmetric(horizontal: 8),
                        child: Text('Flat', style: TextStyle(fontSize: 11)),
                      ),
                    ],
                  ),
                  if (widget.onFillAllMissing != null &&
                      _missingEntitySeeds.isNotEmpty)
                    Tooltip(
                      message:
                          'Fill all ${_missingEntitySeeds.length} missing entities',
                      child: IconButton(
                        icon: const Icon(Icons.auto_fix_high, size: 18),
                        color: Theme.of(context).colorScheme.error,
                        onPressed: widget.onFillAllMissing,
                        tooltip: 'Fill all missing entities',
                      ),
                    ),
                  IconButton(
                    icon: const Icon(Icons.search, size: 18),
                    onPressed: _toggleSearchDialog,
                    tooltip: 'Search entities',
                  ),
                  if (widget.onScanMissing != null)
                    IconButton(
                      icon: const Icon(Icons.find_replace, size: 18),
                      onPressed: () {
                        _scanMissingPlaceholders();
                        _scanMissingEntities();
                        widget.onScanMissing?.call();
                      },
                      tooltip: 'Scan missing placeholders',
                    ),
                  if (_selectedGroupKeys.isNotEmpty ||
                      _selectedOccurrenceIndices.isNotEmpty)
                    IconButton(
                      icon: Icon(
                        Icons.delete_outline,
                        size: 18,
                        color: Theme.of(context).colorScheme.error,
                      ),
                      tooltip:
                          'Delete selected (${_selectedGroupKeys.length + _selectedOccurrenceIndices.length} items)',
                      onPressed: _handleDeleteSelected,
                    ),
                  if (widget.onAddEntity != null)
                    IconButton(
                      icon: Icon(
                        Icons.add,
                        size: 18,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      tooltip: 'Add entity',
                      onPressed: widget.onAddEntity,
                    ),
                  if (widget.entities.isNotEmpty)
                    IconButton(
                      icon: Icon(
                        Icons.arrow_forward,
                        size: 18,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      tooltip:
                          'Next entity${widget.currentNavigationIndex >= 0 ? ' (${widget.currentNavigationIndex + 1}/${widget.entities.length})' : ''}',
                      onPressed: widget.onNavigateToNext,
                    ),
                ],
              ),
            ],
          ),
        ),
        Expanded(
          child: widget.entities.isEmpty
              ? Center(
                  child: Text(
                    'No entities detected',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                )
              : _isGroupedView
                  ? _buildGroupedView(groups)
                  : _buildFlatView(),
        ),
      ],
    );
  }

  Widget _buildGroupedView(List<EntityGroup> groups) {
    final hasMissingPlaceholders = _missingPlaceholders.isNotEmpty;
    final hasMissingEntities = _missingEntitySeeds.isNotEmpty;
    final itemCount = groups.length +
        (hasMissingPlaceholders ? 1 : 0) +
        (hasMissingEntities ? 1 : 0);

    // Ensure all groups have keys
    for (final group in groups) {
      if (!_groupKeys.containsKey(group.groupKey)) {
        _groupKeys[group.groupKey] = GlobalKey();
      }
    }

    return ListView.builder(
      controller: _listScrollController,
      padding: const EdgeInsets.all(8),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        // Groups come first (index 0 to groups.length - 1)
        if (index < groups.length) {
          final group = groups[index];
          final isExpanded = _isGroupExpanded(group);
          final hasSelected = _hasSelectedOccurrence(group);

          // Auto-expand if has selected occurrence
          if (hasSelected && !_expandedGroupKeys.contains(group.groupKey)) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted) {
                _toggleGroup(group.groupKey);
              }
            });
          }

          return Container(
            key: _groupKeys[group.groupKey],
            child: EntityGroupWidget(
              group: group,
              isExpanded: isExpanded,
              hasSelectedOccurrence: hasSelected,
              highlightedEntityIndex: widget.highlightedEntityIndex,
              isGroupSelected: _selectedGroupKeys.contains(group.groupKey),
              selectedOccurrenceIndices: _selectedOccurrenceIndices,
              onToggle: () => _toggleGroup(group.groupKey),
              onGroupCheckboxChanged: (checked) =>
                  _toggleGroupSelection(group.groupKey),
              onOccurrenceTap: widget.onEntityTap,
              onOccurrenceEdit: widget.onEditEntity,
              onOccurrenceDelete: _handleDeleteOccurrence,
              onOccurrenceCheckboxChanged: _toggleOccurrenceSelection,
              onAdd: widget.onAddEntity != null
                  ? () {
                      // Add occurrence with same text/type as the group
                      widget.onAddEntity?.call(
                        prefillText: group.text,
                        prefillType: group.type,
                      );
                    }
                  : null,
              onDeleteAll: group.occurrences.isNotEmpty
                  ? () {
                      _handleDeleteGroup(group);
                    }
                  : null,
            ),
          );
        }

        // Missing entities widget (backend-driven, shown after groups)
        if (hasMissingEntities && index == groups.length) {
          return _buildMissingEntitiesWidget();
        }

        // Missing placeholders widget (legacy, shown after missing entities)
        if (hasMissingPlaceholders &&
            index == groups.length + (hasMissingEntities ? 1 : 0)) {
          return MissingPlaceholdersWidget(
            missingPlaceholders: _missingPlaceholders,
            anonymizedText: widget.anonymizedText,
            isExpanded: _expandedGroupKeys.contains('__missing_placeholders__'),
            onToggle: () => _toggleGroup('__missing_placeholders__'),
            onAddAll: (placeholder) {
              widget.onAddMissingPlaceholder?.call(placeholder);
            },
          );
        }

        // Should not reach here, but return empty widget as fallback
        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildFlatView() => ListView.builder(
        padding: const EdgeInsets.all(8),
        itemCount: widget.entities.length,
        itemBuilder: (BuildContext context, int index) {
          final Map<String, dynamic> entity =
              widget.entities[index] as Map<String, dynamic>? ??
                  <String, dynamic>{};
          final bool isSelected = widget.highlightedEntityIndex == index;
          final bool isChecked = _selectedOccurrenceIndices.contains(index);
          final String originalText = entity['text']?.toString() ?? '';
          final String placeholder = entity['placeholder']?.toString() ?? '';
          final int? segmentIndex = entity['segmentIndex'] as int?;

          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            elevation: isSelected ? 4 : 1,
            color: isSelected
                ? Theme.of(context)
                    .colorScheme
                    .primaryContainer
                    .withOpacity(0.3)
                : Theme.of(context).colorScheme.surface,
            child: ListTile(
              dense: true,
              selected: isSelected,
              leading: Checkbox(
                value: isChecked,
                onChanged: (bool? checked) => _toggleOccurrenceSelection(index),
              ),
              onTap: () => widget.onEntityTap(index),
              title: Text(
                originalText,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Icon(
                      Icons.arrow_forward,
                      size: 12,
                      color: Colors.orange.shade700,
                    ),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(
                        placeholder,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 12,
                          fontFamily: 'monospace',
                          color: Colors.orange.shade700,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    if (segmentIndex != null) ...<Widget>[
                      const SizedBox(width: 8),
                      Chip(
                        label: Text(
                          '#${segmentIndex + 1}', // 1-based display (consistent with preview)
                          style: const TextStyle(fontSize: 9),
                        ),
                        padding: EdgeInsets.zero,
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        visualDensity: VisualDensity.compact,
                        backgroundColor: Colors.blue.shade50,
                      ),
                    ],
                  ],
                ),
              ),
              trailing: SizedBox(
                width: 108,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: <Widget>[
                    IconButton(
                      icon: const Icon(Icons.edit_outlined, size: 18),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 32,
                        minHeight: 32,
                      ),
                      onPressed: () => widget.onEditEntity(index),
                      tooltip: 'Edit entity',
                    ),
                    IconButton(
                      icon: const Icon(Icons.info_outline, size: 18),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 32,
                        minHeight: 32,
                      ),
                      onPressed: () => widget.onShowEntityDetails(entity),
                      tooltip: 'Entity details',
                    ),
                    IconButton(
                      icon: const Icon(Icons.delete_outline, size: 18),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(
                        minWidth: 32,
                        minHeight: 32,
                      ),
                      onPressed: () => _handleDeleteOccurrence(index),
                      tooltip: 'Delete entity',
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      );

  Widget _buildMissingEntitiesWidget() {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 1,
      color: theme.colorScheme.errorContainer.withOpacity(0.2),
      child: ExpansionTile(
        initiallyExpanded: _expandedGroupKeys.contains('__missing_entities__'),
        onExpansionChanged: (_) => _toggleGroup('__missing_entities__'),
        leading: Icon(
          Icons.warning_amber_rounded,
          size: 20,
          color: theme.colorScheme.error,
        ),
        title: Row(
          children: <Widget>[
            Text(
              'Missing Entities',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: theme.colorScheme.onSurface,
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: theme.colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                '${_missingEntitySeeds.length}',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: theme.colorScheme.onErrorContainer,
                ),
              ),
            ),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Entities from backend expansion not in current list',
                  style: TextStyle(
                    fontSize: 11,
                    color: theme.colorScheme.onSurfaceVariant,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
              if (widget.onFillAllMissing != null)
                ElevatedButton.icon(
                  onPressed: widget.onFillAllMissing,
                  icon: const Icon(Icons.auto_fix_high, size: 16),
                  label: const Text('Fill All'),
                  style: ElevatedButton.styleFrom(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    backgroundColor: theme.colorScheme.errorContainer,
                    foregroundColor: theme.colorScheme.onErrorContainer,
                  ),
                ),
            ],
          ),
        ),
        children: _missingEntitySeeds.map((seed) {
          final text = seed['text'] ?? '';
          final type = seed['type'] ?? 'UNKNOWN';

          return Card(
            margin: const EdgeInsets.only(left: 16, right: 8, bottom: 4),
            elevation: 0,
            color: theme.colorScheme.surface,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: <Widget>[
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          text,
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: theme.colorScheme.onSurface,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Type: $type',
                          style: TextStyle(
                            fontSize: 11,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  if (widget.onAddEntity != null)
                    ElevatedButton.icon(
                      onPressed: () {
                        widget.onAddEntity
                            ?.call(prefillText: text, prefillType: type);
                      },
                      icon: const Icon(Icons.add, size: 16),
                      label: const Text('Add'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                    ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  void _handleDeleteGroup(EntityGroup group) {
    // Check if there are selected items
    final hasSelected =
        _selectedGroupKeys.isNotEmpty || _selectedOccurrenceIndices.isNotEmpty;

    if (hasSelected) {
      // Delete selected items
      _handleDeleteSelected();
    } else {
      // Delete current group
      if (_skipDeleteConfirmation) {
        _performDeleteGroup(group);
      } else {
        _showDeleteGroupDialog(group);
      }
    }
  }

  void _handleDeleteOccurrence(int index) {
    // Check if there are selected items
    final hasSelected =
        _selectedGroupKeys.isNotEmpty || _selectedOccurrenceIndices.isNotEmpty;

    if (hasSelected) {
      // Delete selected items
      _handleDeleteSelected();
    } else {
      // Delete current occurrence
      if (_skipDeleteConfirmation) {
        widget.onDeleteEntity(index);
      } else {
        _showDeleteOccurrenceDialog(index);
      }
    }
  }

  void _handleDeleteSelected() {
    if (_selectedOccurrenceIndices.isEmpty && _selectedGroupKeys.isEmpty) {
      return;
    }

    final selectedIndices = <int>{};

    // Add selected occurrence indices
    selectedIndices.addAll(_selectedOccurrenceIndices);

    // Add all occurrences from selected groups
    final groups = EntityGroupHelper.groupEntities(widget.entities);
    for (final groupKey in _selectedGroupKeys) {
      final group = groups.firstWhere((g) => g.groupKey == groupKey);
      for (final occurrence in group.occurrences) {
        selectedIndices.add(occurrence.index);
      }
    }

    if (selectedIndices.isEmpty) {
      return;
    }

    if (_skipDeleteConfirmation) {
      _performDeleteIndices(selectedIndices.toList());
    } else {
      _showDeleteSelectedDialog(selectedIndices.toList());
    }
  }

  void _performDeleteGroup(EntityGroup group) {
    // Delete all occurrences in reverse order
    final indices = EntityGroupHelper.findOccurrenceIndices(
      widget.entities,
      group.groupKey,
    );
    indices.sort((a, b) => b.compareTo(a));
    for (final index in indices) {
      widget.onDeleteEntity(index);
    }
    _clearSelection();
  }

  void _performDeleteIndices(List<int> indices) {
    // Sort in reverse order to avoid index shifting issues
    indices.sort((a, b) => b.compareTo(a));
    for (final index in indices) {
      widget.onDeleteEntity(index);
    }
    _clearSelection();
  }

  void _showDeleteGroupDialog(EntityGroup group) {
    bool dontShowAgain = false;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Delete Group?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'This will remove all ${group.occurrenceCount} occurrences:\n'
                '- ${group.displayName} (${group.type})\n\n'
                'This action cannot be undone.',
              ),
              const SizedBox(height: 16),
              CheckboxListTile(
                value: dontShowAgain,
                onChanged: (value) {
                  setDialogState(() {
                    dontShowAgain = value ?? false;
                  });
                },
                title: const Text('不再提醒'),
                contentPadding: EdgeInsets.zero,
                dense: true,
                controlAffinity: ListTileControlAffinity.leading,
              ),
            ],
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                if (dontShowAgain) {
                  _saveSkipDeleteConfirmation(true);
                }
                Navigator.of(context).pop();
                _performDeleteGroup(group);
              },
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
              ),
              child: const Text('Delete All'),
            ),
          ],
        ),
      ),
    );
  }

  void _showDeleteOccurrenceDialog(int index) {
    final entity =
        widget.entities[index] as Map<String, dynamic>? ?? <String, dynamic>{};
    final text = entity['text']?.toString() ?? '';
    bool dontShowAgain = false;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Delete Occurrence?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'This will remove the occurrence:\n'
                '- $text\n\n'
                'This action cannot be undone.',
              ),
              const SizedBox(height: 16),
              CheckboxListTile(
                value: dontShowAgain,
                onChanged: (value) {
                  setDialogState(() {
                    dontShowAgain = value ?? false;
                  });
                },
                title: const Text('不再提醒'),
                contentPadding: EdgeInsets.zero,
                dense: true,
                controlAffinity: ListTileControlAffinity.leading,
              ),
            ],
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                if (dontShowAgain) {
                  _saveSkipDeleteConfirmation(true);
                }
                Navigator.of(context).pop();
                widget.onDeleteEntity(index);
              },
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
              ),
              child: const Text('Delete'),
            ),
          ],
        ),
      ),
    );
  }

  void _showDeleteSelectedDialog(List<int> indices) {
    bool dontShowAgain = false;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Delete Selected?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'This will remove ${indices.length} selected item${indices.length > 1 ? 's' : ''}.\n\n'
                'This action cannot be undone.',
              ),
              const SizedBox(height: 16),
              CheckboxListTile(
                value: dontShowAgain,
                onChanged: (value) {
                  setDialogState(() {
                    dontShowAgain = value ?? false;
                  });
                },
                title: const Text('不再提醒'),
                contentPadding: EdgeInsets.zero,
                dense: true,
                controlAffinity: ListTileControlAffinity.leading,
              ),
            ],
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                if (dontShowAgain) {
                  _saveSkipDeleteConfirmation(true);
                }
                Navigator.of(context).pop();
                _performDeleteIndices(indices);
              },
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
              ),
              child: const Text('Delete'),
            ),
          ],
        ),
      ),
    );
  }
}
