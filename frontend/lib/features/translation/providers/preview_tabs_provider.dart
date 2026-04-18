// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/preview_tab.dart';
import '../services/preview_tabs_persistence.dart';

/// Preview tabs state
class PreviewTabsState {
  // Recently closed tabs for recovery

  PreviewTabsState({
    List<PreviewTab>? tabs,
    int? activeTabIndex,
    List<PreviewTab>? closedTabs,
  })  : tabs = tabs ?? <PreviewTab>[],
        activeTabIndex = activeTabIndex ?? 0,
        closedTabs = closedTabs ?? <PreviewTab>[];
  final List<PreviewTab> tabs;
  final int activeTabIndex;
  final List<PreviewTab> closedTabs;

  PreviewTabsState copyWith({
    List<PreviewTab>? tabs,
    int? activeTabIndex,
    List<PreviewTab>? closedTabs,
  }) =>
      PreviewTabsState(
        tabs: tabs ?? this.tabs,
        activeTabIndex: activeTabIndex ?? this.activeTabIndex,
        closedTabs: closedTabs ?? this.closedTabs,
      );
}

/// Preview tabs notifier
class PreviewTabsNotifier extends StateNotifier<PreviewTabsState> {
  PreviewTabsNotifier({this.flowId}) : super(PreviewTabsState());
  final String? flowId;

  /// Add a new tab
  void addTab(PreviewTab tab) {
    // Check if tab with same id already exists
    final existingIndex = state.tabs.indexWhere((t) => t.id == tab.id);
    if (existingIndex >= 0) {
      // Switch to existing tab
      switchToTab(existingIndex);
      return;
    }

    final newTabs = <PreviewTab>[...state.tabs, tab];
    state = state.copyWith(
      tabs: newTabs,
      activeTabIndex: newTabs.length - 1,
    );

    // Persist tabs
    _saveTabsAsync(newTabs);
  }

  /// Update an existing tab by id, or add it if it doesn't exist
  void updateOrAddTab(PreviewTab tab) {
    final existingIndex = state.tabs.indexWhere((t) => t.id == tab.id);
    if (existingIndex >= 0) {
      // Update existing tab
      final newTabs = List<PreviewTab>.from(state.tabs);
      newTabs[existingIndex] = tab;
      state = state.copyWith(
        tabs: newTabs,
        activeTabIndex: existingIndex, // Switch to updated tab
      );
      _saveTabsAsync(newTabs);
    } else {
      // Add new tab
      addTab(tab);
    }
  }

  /// Save tabs asynchronously (don't await to avoid blocking UI)
  void _saveTabsAsync(List<PreviewTab> tabs) {
    PreviewTabsPersistence.saveTabs(tabs, flowId: flowId);
    if (state.closedTabs.isNotEmpty) {
      PreviewTabsPersistence.saveClosedTabs(state.closedTabs, flowId: flowId);
    }
  }

  /// Close a tab by index
  void closeTab(int index) {
    if (index < 0 || index >= state.tabs.length) return;

    final closedTab = state.tabs[index];
    final newTabs = List<PreviewTab>.from(state.tabs);
    newTabs.removeAt(index);

    // Add to closed tabs list (max 10)
    final newClosedTabs = <PreviewTab>[
      closedTab,
      ...state.closedTabs,
    ];
    if (newClosedTabs.length > 10) {
      newClosedTabs.removeRange(10, newClosedTabs.length);
    }

    // Adjust active tab index
    int newActiveIndex = state.activeTabIndex;
    if (index < state.activeTabIndex) {
      newActiveIndex = state.activeTabIndex - 1;
    } else if (index == state.activeTabIndex) {
      if (newTabs.isEmpty) {
        newActiveIndex = 0;
      } else if (newActiveIndex >= newTabs.length) {
        newActiveIndex = newTabs.length - 1;
      }
    }

    state = state.copyWith(
      tabs: newTabs,
      activeTabIndex:
          newActiveIndex.clamp(0, newTabs.isNotEmpty ? newTabs.length - 1 : 0),
      closedTabs: newClosedTabs,
    );

    // Persist tabs
    _saveTabsAsync(newTabs);
    if (newClosedTabs.isNotEmpty) {
      PreviewTabsPersistence.saveClosedTabs(newClosedTabs, flowId: flowId);
    }
  }

  /// Switch to a tab
  void switchToTab(int index) {
    if (index >= 0 && index < state.tabs.length) {
      state = state.copyWith(activeTabIndex: index);
    }
  }

  /// Reopen a closed tab
  void reopenTab(PreviewTab tab) {
    // Remove from closed tabs
    final newClosedTabs = List<PreviewTab>.from(state.closedTabs);
    newClosedTabs.removeWhere((t) => t.id == tab.id);

    // Add to active tabs
    addTab(tab);

    state = state.copyWith(closedTabs: newClosedTabs);

    // Persist tabs
    PreviewTabsPersistence.saveClosedTabs(newClosedTabs, flowId: flowId);
  }

  /// Replace the content (and optional dataRef) of an existing tab
  void replaceTabContent(
    String tabId,
    Widget newContent, {
    Map<String, dynamic>? dataRef,
  }) {
    final index = state.tabs.indexWhere((t) => t.id == tabId);
    if (index < 0) return;

    final oldTab = state.tabs[index];
    final updatedTab = PreviewTab(
      id: oldTab.id,
      type: oldTab.type,
      title: oldTab.title,
      content: newContent,
      icon: oldTab.icon,
      createdAt: oldTab.createdAt,
      dataRef: dataRef ?? oldTab.dataRef,
    );

    final newTabs = List<PreviewTab>.from(state.tabs);
    newTabs[index] = updatedTab;
    state = state.copyWith(tabs: newTabs);
    _saveTabsAsync(newTabs);
  }

  /// Clear all tabs
  void clearAllTabs() {
    state = PreviewTabsState();
    PreviewTabsPersistence.clearTabs(flowId: flowId);
  }

  /// Update closed tabs (for persistence recovery)
  void setClosedTabs(List<PreviewTab> closedTabs) {
    state = state.copyWith(closedTabs: closedTabs);
  }

  /// Close a tab by id
  void closeTabById(String tabId) {
    final index = state.tabs.indexWhere((t) => t.id == tabId);
    if (index >= 0) {
      closeTab(index);
    }
  }

  /// Close a tab by id without adding to closed tabs list
  /// This is used when programmatically closing tabs (e.g., when starting a new translation)
  /// to avoid triggering onTabClose callbacks that might release resources
  void closeTabByIdSilently(String tabId) {
    final index = state.tabs.indexWhere((t) => t.id == tabId);
    if (index < 0 || index >= state.tabs.length) return;

    final newTabs = List<PreviewTab>.from(state.tabs);
    newTabs.removeAt(index);

    // Adjust active tab index
    int newActiveIndex = state.activeTabIndex;
    if (index < state.activeTabIndex) {
      newActiveIndex = state.activeTabIndex - 1;
    } else if (index == state.activeTabIndex) {
      if (newTabs.isEmpty) {
        newActiveIndex = 0;
      } else if (newActiveIndex >= newTabs.length) {
        newActiveIndex = newTabs.length - 1;
      }
    }

    state = state.copyWith(
      tabs: newTabs,
      activeTabIndex:
          newActiveIndex.clamp(0, newTabs.isNotEmpty ? newTabs.length - 1 : 0),
      // Note: Do not add to closedTabs to avoid triggering onTabClose callbacks
    );

    // Persist tabs
    _saveTabsAsync(newTabs);
  }

  /// Close tabs by type
  void closeTabsByType(PreviewTabType type) {
    final indicesToClose = <int>[];
    for (int i = 0; i < state.tabs.length; i++) {
      if (state.tabs[i].type == type) {
        indicesToClose.add(i);
      }
    }
    // Close from highest index to lowest to avoid index shifting issues
    indicesToClose.sort((a, b) => b.compareTo(a));
    for (final index in indicesToClose) {
      closeTab(index);
    }
  }
}

/// Preview tabs provider
///
/// @deprecated Use [previewTabsProviderFamily] instead for per-flow isolation.
/// This global provider is kept for backward compatibility with legacy routes
/// (e.g., /translation route, MainLayout). New code should always use family provider.
@Deprecated('Use previewTabsProviderFamily instead for per-flow isolation')
final StateNotifierProvider<PreviewTabsNotifier, PreviewTabsState>
    previewTabsProvider =
    StateNotifierProvider<PreviewTabsNotifier, PreviewTabsState>(
  (ref) => PreviewTabsNotifier(),
);

final StateNotifierProviderFamily<PreviewTabsNotifier, PreviewTabsState, String>
    previewTabsProviderFamily =
    StateNotifierProvider.family<PreviewTabsNotifier, PreviewTabsState, String>(
  (
    ref,
    flowId,
  ) {
    // Keep provider alive to avoid reloading when switching flows
    ref.keepAlive();
    return PreviewTabsNotifier(flowId: flowId);
  },
);
