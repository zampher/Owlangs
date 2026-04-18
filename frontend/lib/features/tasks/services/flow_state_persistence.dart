// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/persisted_flow_state.dart';
import '../../translation/services/preview_tabs_persistence.dart';

/// Service for persisting Flow state to local storage
class FlowStatePersistence {
  static const String _keyPrefix = 'flow_state_';
  static const String _flowListKey = 'flow_list'; // List of all Flow IDs
  static const String _flowSeqKey =
      'flow_seq_counter'; // Monotonic flow sequence

  /// Get next flow sequence (monotonic) and persist it
  static Future<int> _nextFlowSequence() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    final int current = prefs.getInt(_flowSeqKey) ?? 0;
    final int next = current + 1;
    await prefs.setInt(_flowSeqKey, next);
    return next;
  }

  /// Build default flow title like "Flow-001"
  static String _buildDefaultTitleFromSeq(int seq) {
    final String padded = seq.toString().padLeft(3, '0');
    return 'Flow-$padded';
  }

  /// Public helper: get next default flow title (increments sequence)
  static Future<String> getNextDefaultTitle() async {
    final int seq = await _nextFlowSequence();
    return _buildDefaultTitleFromSeq(seq);
  }

  /// Maximum number of flows to keep (to prevent unlimited growth)
  static const int _maxFlowsToKeep = 50;

  /// Save Flow state
  static Future<void> saveFlowState(PersistedFlowState state) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();

      // Save Flow state
      final String stateJson = jsonEncode(state.toJson());
      await prefs.setString('$_keyPrefix${state.flowId}', stateJson);

      // Update Flow list
      final List<String> flowList = await getAllFlowIds();
      if (!flowList.contains(state.flowId)) {
        flowList.add(state.flowId);
        await prefs.setStringList(_flowListKey, flowList);
      }

      // Update lastAccessedAt
      final PersistedFlowState updatedState = state.updateLastAccessed();
      final String updatedStateJson = jsonEncode(updatedState.toJson());
      await prefs.setString('$_keyPrefix${state.flowId}', updatedStateJson);
      
      // Cleanup old flows if exceeding limit (keep only most recent _maxFlowsToKeep)
      // Run in background to not block the save operation
      Future.microtask(_cleanupOldFlowsIfNeeded);
    } catch (e) {
      print('Error saving Flow state: $e');
      // Fail silently - persistence is optional
    }
  }
  
  /// Cleanup old flows if total count exceeds limit
  static Future<void> _cleanupOldFlowsIfNeeded() async {
    try {
      final List<String> flowIds = await getAllFlowIds();
      if (flowIds.length <= _maxFlowsToKeep) return;
      
      // Sort by flowId (which is timestamp-based, newer = larger number)
      final sortedIds = List<String>.from(flowIds)..sort();
      
      // Delete oldest flows (keep the most recent _maxFlowsToKeep)
      final toDelete = sortedIds.sublist(0, sortedIds.length - _maxFlowsToKeep);
      for (final flowId in toDelete) {
        await deleteFlowState(flowId);
      }
      
      print('Cleaned up ${toDelete.length} old flows, kept $_maxFlowsToKeep most recent');
    } catch (e) {
      print('Error cleaning up old flows: $e');
    }
  }
  
  /// Update lastAccessedAt in background without triggering cleanup
  static void _saveAccessTimeInBackground(String flowId, PersistedFlowState state) {
    Future.microtask(() async {
      try {
        final SharedPreferences prefs = await SharedPreferences.getInstance();
        final String stateJson = jsonEncode(state.toJson());
        await prefs.setString('$_keyPrefix$flowId', stateJson);
      } catch (e) {
        // Silent fail - access time update is not critical
      }
    });
  }

  /// Load Flow state
  static Future<PersistedFlowState?> loadFlowState(String flowId) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String? stateJsonStr = prefs.getString('$_keyPrefix$flowId');
      if (stateJsonStr == null) return null;

      final Map<String, dynamic> stateJson =
          jsonDecode(stateJsonStr) as Map<String, dynamic>;
      final PersistedFlowState state = PersistedFlowState.fromJson(stateJson);

      // Update lastAccessedAt in background (don't block load)
      final PersistedFlowState updatedState = state.updateLastAccessed();
      _saveAccessTimeInBackground(flowId, updatedState);

      return state;
    } catch (e) {
      print('Error loading Flow state: $e');
      return null;
    }
  }

  /// Get persisted steps state for a Flow
  static Future<PersistedStepsState?> getPersistedStepsState(
    String flowId,
  ) async {
    try {
      final PersistedFlowState? persisted = await loadFlowState(flowId);
      return persisted?.uiState.stepsState;
    } catch (e) {
      print('Error loading steps state: $e');
      return null;
    }
  }

  /// Get all Flow ID list
  static Future<List<String>> getAllFlowIds() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      return prefs.getStringList(_flowListKey) ?? <String>[];
    } catch (e) {
      print('Error loading Flow list: $e');
      return <String>[];
    }
  }

  /// Delete Flow state
  static Future<void> deleteFlowState(String flowId) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();

      // Delete state data
      await prefs.remove('$_keyPrefix$flowId');

      // Remove from Flow list
      final List<String> flowList = await getAllFlowIds();
      flowList.remove(flowId);
      await prefs.setStringList(_flowListKey, flowList);

      // Clean up related Preview Tabs
      await PreviewTabsPersistence.clearTabs(flowId: flowId);
    } catch (e) {
      print('Error deleting Flow state: $e');
    }
  }

  /// Clean up expired Flows (7 days not accessed)
  /// Optimized to avoid loading full state objects
  static Future<void> cleanupExpiredFlows() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final List<String> flowIds = await getAllFlowIds();
      if (flowIds.isEmpty) return;
      
      final List<String> expiredFlows = <String>[];
      final now = DateTime.now();
      const expiryDays = 7;

      // Batch read - check raw JSON without full deserialization
      for (final String flowId in flowIds) {
        try {
          final String? stateJsonStr = prefs.getString('$_keyPrefix$flowId');
          if (stateJsonStr == null) {
            expiredFlows.add(flowId); // Orphaned entry
            continue;
          }
          
          // Quick JSON parse to check dates without full object creation
          final Map<String, dynamic> json = jsonDecode(stateJsonStr) as Map<String, dynamic>;
          
          // Check lastAccessedAt first, then createdAt
          DateTime? checkDate;
          if (json['lastAccessedAt'] != null) {
            checkDate = DateTime.tryParse(json['lastAccessedAt'] as String);
          }
          if (checkDate == null && json['createdAt'] != null) {
            checkDate = DateTime.tryParse(json['createdAt'] as String);
          }
          
          if (checkDate != null && now.difference(checkDate).inDays > expiryDays) {
            expiredFlows.add(flowId);
          }
        } catch (e) {
          // If we can't parse it, consider it expired
          expiredFlows.add(flowId);
        }
      }

      // Batch delete
      for (final String flowId in expiredFlows) {
        await deleteFlowState(flowId);
      }

      if (expiredFlows.isNotEmpty) {
        print('Cleaned up ${expiredFlows.length} expired Flows');
      }
    } catch (e) {
      print('Error cleaning up expired Flows: $e');
    }
  }

  /// Clear all Flow data
  static Future<void> clearAllFlowData() async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final List<String> flowIds = await getAllFlowIds();

      // Delete all Flow states
      for (final String flowId in flowIds) {
        await prefs.remove('$_keyPrefix$flowId');
        await PreviewTabsPersistence.clearTabs(flowId: flowId);
      }

      // Clear Flow list
      await prefs.remove(_flowListKey);
      print('Cleared all Flow data');
    } catch (e) {
      print('Error clearing all Flow data: $e');
    }
  }
  
  /// Cleanup flows older than specified days (regardless of access time)
  /// This is useful for one-time cleanup of accumulated old flows
  static Future<int> cleanupFlowsOlderThan(int days) async {
    try {
      final List<String> flowIds = await getAllFlowIds();
      final List<String> toDelete = <String>[];
      final cutoffDate = DateTime.now().subtract(Duration(days: days));
      
      for (final String flowId in flowIds) {
        final PersistedFlowState? state = await loadFlowState(flowId);
        if (state == null) {
          toDelete.add(flowId);
          continue;
        }
        // Check both createdAt and lastAccessedAt
        final isOld = state.createdAt.isBefore(cutoffDate) &&
            (state.lastAccessedAt == null || state.lastAccessedAt!.isBefore(cutoffDate));
        if (isOld) {
          toDelete.add(flowId);
        }
      }
      
      for (final String flowId in toDelete) {
        await deleteFlowState(flowId);
      }
      
      if (toDelete.isNotEmpty) {
        print('Cleaned up ${toDelete.length} flows older than $days days');
      }
      return toDelete.length;
    } catch (e) {
      print('Error cleaning up old flows: $e');
      return 0;
    }
  }

  /// Get Flow state summary (for listing)
  static Future<List<Map<String, dynamic>>> getAllFlowSummaries() async {
    try {
      final List<String> flowIds = await getAllFlowIds();
      final List<Map<String, dynamic>> summaries = <Map<String, dynamic>>[];

      for (final String flowId in flowIds) {
        final PersistedFlowState? state = await loadFlowState(flowId);
        if (state != null && !state.isExpired) {
          summaries.add(<String, dynamic>{
            'flowId': state.flowId,
            'title': state.title,
            'flowType': state.flowType.toString(),
            'activePhase': state.activePhase.toString(),
            'createdAt': state.createdAt.toIso8601String(),
            'lastAccessedAt': state.lastAccessedAt?.toIso8601String(),
            'hasTranslateTask': state.context.translateTaskId != null,
          });
        }
      }

      // Sort by lastAccessedAt (most recent first)
      summaries.sort((Map<String, dynamic> a, Map<String, dynamic> b) {
        final String? aTime = a['lastAccessedAt'] as String?;
        final String? bTime = b['lastAccessedAt'] as String?;
        if (aTime == null && bTime == null) return 0;
        if (aTime == null) return 1;
        if (bTime == null) return -1;
        return bTime.compareTo(aTime);
      });

      return summaries;
    } catch (e) {
      print('Error getting Flow summaries: $e');
      return <Map<String, dynamic>>[];
    }
  }
}
