// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Service for migrating global persistence data to per-flow buckets
class PersistenceMigrationService {
  static const String _migrationFlagKey = 'persistence_migration_v1_completed';

  /// Check if migration has already been completed
  static Future<bool> isMigrationCompleted() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getBool(_migrationFlagKey) ?? false;
    } catch (e) {
      print('Error checking migration status: $e');
      return false;
    }
  }

  /// Mark migration as completed
  static Future<void> markMigrationCompleted() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_migrationFlagKey, true);
    } catch (e) {
      print('Error marking migration as completed: $e');
    }
  }

  /// Migrate global persistence data to per-flow buckets
  /// This should be called once at app startup
  static Future<void> migratePersistenceData() async {
    try {
      // Check if migration already completed
      if (await isMigrationCompleted()) {
        print('Persistence migration already completed, skipping...');
        return;
      }

      print('Starting persistence data migration...');
      final prefs = await SharedPreferences.getInstance();

      // 1. Migrate Preview Tabs
      await _migratePreviewTabs(prefs);

      // 2. Migrate Closed Tabs
      await _migrateClosedTabs(prefs);

      // 3. Mark migration as completed
      await markMigrationCompleted();
      print('Persistence data migration completed successfully');
    } catch (e) {
      print('Error during persistence migration: $e');
      // Don't throw - migration failure shouldn't break app startup
    }
  }

  /// Migrate preview tabs from global key to flowId buckets
  static Future<void> _migratePreviewTabs(SharedPreferences prefs) async {
    final globalTabsJson = prefs.getString('preview_tabs');
    if (globalTabsJson == null || globalTabsJson.isEmpty) {
      print('No global preview tabs to migrate');
      return;
    }

    try {
      final tabs = jsonDecode(globalTabsJson) as List;
      if (tabs.isEmpty) {
        print('Global preview tabs list is empty');
        return;
      }

      final tabsByFlow = <String, List<dynamic>>{};
      int migratedCount = 0;
      int skippedCount = 0;

      for (final tab in tabs) {
        if (tab is! Map<String, dynamic>) continue;

        final dataRef = tab['dataRef'] as Map<String, dynamic>?;
        final flowId = dataRef?['flowId'] as String?;

        if (flowId != null && flowId.isNotEmpty) {
          // Migrate to flowId bucket
          tabsByFlow.putIfAbsent(flowId, () => <dynamic>[]).add(tab);
          migratedCount++;
        } else {
          // Tab without flowId - skip migration (keep in global key for backward compatibility)
          skippedCount++;
        }
      }

      // Save migrated tabs to flowId buckets
      for (final entry in tabsByFlow.entries) {
        final flowKey = 'preview_tabs_${entry.key}';
        final existingFlowTabsJson = prefs.getString(flowKey);
        List<dynamic> existingFlowTabs = <dynamic>[];

        if (existingFlowTabsJson != null) {
          try {
            existingFlowTabs = jsonDecode(existingFlowTabsJson) as List;
          } catch (e) {
            print('Error parsing existing tabs for flow ${entry.key}: $e');
          }
        }

        // Merge with existing tabs (avoid duplicates by id)
        final existingIds = existingFlowTabs
            .map((t) => t['id']?.toString())
            .whereType<String>()
            .toSet();
        final newTabs = entry.value.where((t) {
          final id = t['id']?.toString();
          return id != null && !existingIds.contains(id);
        }).toList();

        if (newTabs.isNotEmpty) {
          final mergedTabs = <dynamic>[
            ...existingFlowTabs,
            ...newTabs,
          ];
          await prefs.setString(flowKey, jsonEncode(mergedTabs));
          print('Migrated ${newTabs.length} tabs to flow bucket: ${entry.key}');
        }
      }

      print(
        'Preview tabs migration: $migratedCount migrated, $skippedCount skipped (no flowId)',
      );
    } catch (e) {
      print('Error migrating preview tabs: $e');
      // Continue with other migrations
    }
  }

  /// Migrate closed tabs from global key to flowId buckets
  static Future<void> _migrateClosedTabs(SharedPreferences prefs) async {
    final globalClosedTabsJson = prefs.getString('preview_closed_tabs');
    if (globalClosedTabsJson == null || globalClosedTabsJson.isEmpty) {
      print('No global closed tabs to migrate');
      return;
    }

    try {
      final closedTabs = jsonDecode(globalClosedTabsJson) as List;
      if (closedTabs.isEmpty) {
        print('Global closed tabs list is empty');
        return;
      }

      final closedTabsByFlow = <String, List<dynamic>>{};
      int migratedCount = 0;
      int skippedCount = 0;

      for (final tab in closedTabs) {
        if (tab is! Map<String, dynamic>) continue;

        final dataRef = tab['dataRef'] as Map<String, dynamic>?;
        final flowId = dataRef?['flowId'] as String?;

        if (flowId != null && flowId.isNotEmpty) {
          // Migrate to flowId bucket
          closedTabsByFlow.putIfAbsent(flowId, () => <dynamic>[]).add(tab);
          migratedCount++;
        } else {
          // Tab without flowId - skip migration
          skippedCount++;
        }
      }

      // Save migrated closed tabs to flowId buckets
      for (final entry in closedTabsByFlow.entries) {
        final flowKey = 'preview_closed_tabs_${entry.key}';
        final existingFlowClosedTabsJson = prefs.getString(flowKey);
        List<dynamic> existingFlowClosedTabs = <dynamic>[];

        if (existingFlowClosedTabsJson != null) {
          try {
            existingFlowClosedTabs =
                jsonDecode(existingFlowClosedTabsJson) as List;
          } catch (e) {
            print(
              'Error parsing existing closed tabs for flow ${entry.key}: $e',
            );
          }
        }

        // Merge with existing closed tabs (avoid duplicates by id)
        final existingIds = existingFlowClosedTabs
            .map((t) => t['id']?.toString())
            .whereType<String>()
            .toSet();
        final newTabs = entry.value.where((t) {
          final id = t['id']?.toString();
          return id != null && !existingIds.contains(id);
        }).toList();

        if (newTabs.isNotEmpty) {
          // Limit to max 10 closed tabs per flow
          final mergedTabs = <dynamic>[
            ...existingFlowClosedTabs,
            ...newTabs,
          ];
          final limitedTabs =
              mergedTabs.length > 10 ? mergedTabs.sublist(0, 10) : mergedTabs;
          await prefs.setString(flowKey, jsonEncode(limitedTabs));
          print(
            'Migrated ${newTabs.length} closed tabs to flow bucket: ${entry.key}',
          );
        }
      }

      print(
        'Closed tabs migration: $migratedCount migrated, $skippedCount skipped (no flowId)',
      );
    } catch (e) {
      print('Error migrating closed tabs: $e');
      // Continue - migration failure shouldn't break app
    }
  }

  /// Optional: Clean up global keys after migration (call this after verifying migration success)
  /// WARNING: This will delete global data. Only call after confirming all flows are working correctly.
  static Future<void> cleanupGlobalKeys({bool force = false}) async {
    if (!force) {
      print('Cleanup skipped (use force=true to execute)');
      return;
    }

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('preview_tabs');
      await prefs.remove('preview_closed_tabs');
      print('Global persistence keys cleaned up');
    } catch (e) {
      print('Error cleaning up global keys: $e');
    }
  }
}
