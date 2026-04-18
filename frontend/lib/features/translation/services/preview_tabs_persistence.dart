// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/preview_tab.dart';

/// Service for persisting preview tabs to local storage
class PreviewTabsPersistence {
  static const String _key = 'preview_tabs';
  static const String _closedTabsKey = 'preview_closed_tabs';

  static String _withFlow(String base, String? flowId) =>
      flowId == null || flowId.isEmpty ? base : '${base}_$flowId';

  /// Save tabs to persistent storage
  static Future<void> saveTabs(List<PreviewTab> tabs, {String? flowId}) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final List<Map<String, dynamic>> tabsJson =
          tabs.map((PreviewTab tab) => tab.toJson()).toList();
      await prefs.setString(_withFlow(_key, flowId), jsonEncode(tabsJson));
    } catch (e) {
      print('Error saving tabs: $e');
      // Fail silently - persistence is optional
    }
  }

  /// Load tabs from persistent storage
  static Future<List<Map<String, dynamic>>> loadTabsData({
    String? flowId,
  }) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String? tabsJsonStr = prefs.getString(_withFlow(_key, flowId));
      if (tabsJsonStr == null) return <Map<String, dynamic>>[];

      final List<dynamic> tabsJson = jsonDecode(tabsJsonStr) as List;
      return tabsJson.cast<Map<String, dynamic>>();
    } catch (e) {
      print('Error loading tabs: $e');
      return <Map<String, dynamic>>[];
    }
  }

  /// Save closed tabs
  static Future<void> saveClosedTabs(
    List<PreviewTab> closedTabs, {
    String? flowId,
  }) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final List<Map<String, dynamic>> tabsJson =
          closedTabs.map((PreviewTab tab) => tab.toJson()).toList();
      await prefs.setString(
        _withFlow(_closedTabsKey, flowId),
        jsonEncode(tabsJson),
      );
    } catch (e) {
      print('Error saving closed tabs: $e');
    }
  }

  /// Load closed tabs
  static Future<List<Map<String, dynamic>>> loadClosedTabsData({
    String? flowId,
  }) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      final String? tabsJsonStr =
          prefs.getString(_withFlow(_closedTabsKey, flowId));
      if (tabsJsonStr == null) return <Map<String, dynamic>>[];

      final List<dynamic> tabsJson = jsonDecode(tabsJsonStr) as List;
      return tabsJson.cast<Map<String, dynamic>>();
    } catch (e) {
      print('Error loading closed tabs: $e');
      return <Map<String, dynamic>>[];
    }
  }

  /// Clear all persisted tabs
  static Future<void> clearTabs({String? flowId}) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      await prefs.remove(_withFlow(_key, flowId));
      await prefs.remove(_withFlow(_closedTabsKey, flowId));
    } catch (e) {
      print('Error clearing tabs: $e');
    }
  }
}
