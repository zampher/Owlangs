// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import '../models/persisted_flow_state.dart';
import 'flow_state_persistence.dart';
import '../../translation/services/preview_tabs_persistence.dart';

/// Cache for flow data to improve switching performance
///
/// This cache stores loaded flow data in memory to avoid repeated
/// SharedPreferences reads when switching between flows.
class FlowDataCache {
  factory FlowDataCache() => _instance;
  FlowDataCache._internal();
  static final FlowDataCache _instance = FlowDataCache._internal();

  // Cache for persisted steps state
  final Map<String, PersistedStepsState?> _stepsStateCache =
      <String, PersistedStepsState?>{};

  // Cache for persisted tabs data
  final Map<String, List<Map<String, dynamic>>> _tabsDataCache =
      <String, List<Map<String, dynamic>>>{};
  final Map<String, List<Map<String, dynamic>>> _closedTabsDataCache =
      <String, List<Map<String, dynamic>>>{};

  // Cache timestamps to track when data was loaded
  final Map<String, DateTime> _cacheTimestamps = <String, DateTime>{};

  // Cache expiration time (5 minutes)
  static const Duration _cacheExpiration = Duration(minutes: 5);

  /// Get cached steps state, or load from persistence if not cached
  Future<PersistedStepsState?> getStepsState(
    String flowId, {
    bool forceReload = false,
  }) async {
    // Check cache first
    if (!forceReload && _stepsStateCache.containsKey(flowId)) {
      final DateTime? timestamp = _cacheTimestamps[flowId];
      if (timestamp != null &&
          DateTime.now().difference(timestamp) < _cacheExpiration) {
        return _stepsStateCache[flowId];
      }
    }

    // Load from persistence
    try {
      final PersistedStepsState? stepsState =
          await FlowStatePersistence.getPersistedStepsState(flowId);
      _stepsStateCache[flowId] = stepsState;
      _cacheTimestamps[flowId] = DateTime.now();
      return stepsState;
    } catch (e) {
      print('Error loading steps state for $flowId: $e');
      return null;
    }
  }

  /// Get cached tabs data, or load from persistence if not cached
  Future<List<Map<String, dynamic>>> getTabsData(
    String? flowId, {
    bool forceReload = false,
  }) async {
    if (flowId == null) return <Map<String, dynamic>>[];

    final String cacheKey = flowId;

    // Check cache first
    if (!forceReload && _tabsDataCache.containsKey(cacheKey)) {
      final DateTime? timestamp = _cacheTimestamps[cacheKey];
      if (timestamp != null &&
          DateTime.now().difference(timestamp) < _cacheExpiration) {
        return _tabsDataCache[cacheKey]!;
      }
    }

    // Load from persistence
    try {
      final List<Map<String, dynamic>> tabsData =
          await PreviewTabsPersistence.loadTabsData(flowId: flowId);
      _tabsDataCache[cacheKey] = tabsData;
      _cacheTimestamps[cacheKey] = DateTime.now();
      return tabsData;
    } catch (e) {
      print('Error loading tabs data for $flowId: $e');
      return <Map<String, dynamic>>[];
    }
  }

  /// Get cached closed tabs data, or load from persistence if not cached
  Future<List<Map<String, dynamic>>> getClosedTabsData(
    String? flowId, {
    bool forceReload = false,
  }) async {
    if (flowId == null) return <Map<String, dynamic>>[];

    final String cacheKey = '${flowId}_closed';

    // Check cache first
    if (!forceReload && _closedTabsDataCache.containsKey(cacheKey)) {
      final DateTime? timestamp = _cacheTimestamps[cacheKey];
      if (timestamp != null &&
          DateTime.now().difference(timestamp) < _cacheExpiration) {
        return _closedTabsDataCache[cacheKey]!;
      }
    }

    // Load from persistence
    try {
      final List<Map<String, dynamic>> closedTabsData =
          await PreviewTabsPersistence.loadClosedTabsData(flowId: flowId);
      _closedTabsDataCache[cacheKey] = closedTabsData;
      _cacheTimestamps[cacheKey] = DateTime.now();
      return closedTabsData;
    } catch (e) {
      print('Error loading closed tabs data for $flowId: $e');
      return <Map<String, dynamic>>[];
    }
  }

  /// Invalidate cache for a specific flow
  void invalidateFlow(String flowId) {
    _stepsStateCache.remove(flowId);
    _tabsDataCache.remove(flowId);
    _closedTabsDataCache.remove('${flowId}_closed');
    _cacheTimestamps.remove(flowId);
    _cacheTimestamps.remove('${flowId}_closed');
  }

  /// Update cached steps state
  void updateStepsState(String flowId, PersistedStepsState? stepsState) {
    _stepsStateCache[flowId] = stepsState;
    _cacheTimestamps[flowId] = DateTime.now();
  }

  /// Update cached tabs data
  void updateTabsData(String? flowId, List<Map<String, dynamic>> tabsData) {
    if (flowId == null) return;
    _tabsDataCache[flowId] = tabsData;
    _cacheTimestamps[flowId] = DateTime.now();
  }

  /// Update cached closed tabs data
  void updateClosedTabsData(
    String? flowId,
    List<Map<String, dynamic>> closedTabsData,
  ) {
    if (flowId == null) return;
    final String cacheKey = '${flowId}_closed';
    _closedTabsDataCache[cacheKey] = closedTabsData;
    _cacheTimestamps[cacheKey] = DateTime.now();
  }

  /// Clear all cache
  void clear() {
    _stepsStateCache.clear();
    _tabsDataCache.clear();
    _closedTabsDataCache.clear();
    _cacheTimestamps.clear();
  }

  /// Preload data for a flow (for smooth switching)
  Future<void> preloadFlowData(String flowId) async {
    // Load all data in parallel
    await Future.wait(<Future<Object?>>[
      getStepsState(flowId),
      getTabsData(flowId),
      getClosedTabsData(flowId),
    ]);
  }
}
