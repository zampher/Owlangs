// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'config_service.dart';
import '../../app/app_config.dart';

/// 术语表条目模型
class GlossaryEntry {
  const GlossaryEntry({
    required this.id,
    required this.source,
    required this.target,
    required this.category,
    required this.glossaryId,
    required this.glossaryName,
    required this.isSystem,
  });

  factory GlossaryEntry.fromJson(Map<String, dynamic> json) => GlossaryEntry(
        id: json['id'] ?? '',
        source: json['source'] ?? '',
        target: json['target'] ?? '',
        category: json['category'] ?? '',
        glossaryId: json['glossary_id'] ?? '',
        glossaryName: json['glossary_name'] ?? '',
        isSystem: json['is_system'] ?? false,
      );
  final String id;
  final String source;
  final String target;
  final String category;
  final String glossaryId;
  final String glossaryName;
  final bool isSystem;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'source': source,
        'target': target,
        'category': category,
        'glossary_id': glossaryId,
        'glossary_name': glossaryName,
        'is_system': isSystem,
      };
}

/// 术语表模型
class Glossary {
  const Glossary({
    required this.id,
    required this.name,
    required this.description,
    required this.isSystem,
    required this.entries,
    required this.entryCount,
  });

  factory Glossary.fromJson(Map<String, dynamic> json) {
    final entries = (json['entries'] as List<dynamic>?)
            ?.map((e) => GlossaryEntry.fromJson(e as Map<String, dynamic>))
            .toList() ??
        <GlossaryEntry>[];

    return Glossary(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      description: json['description'] ?? '',
      isSystem: json['is_system'] ?? false,
      entries: entries,
      entryCount: json['entry_count'] ?? 0,
    );
  }
  final String id;
  final String name;
  final String description;
  final bool isSystem;
  final List<GlossaryEntry> entries;
  final int entryCount;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'name': name,
        'description': description,
        'is_system': isSystem,
        'entries': entries.map((e) => e.toJson()).toList(),
        'entry_count': entryCount,
      };
}

/// 术语表管理服务
class GlossaryManagementService {
  static final String _baseUrl = AppConfig.baseUrl;
  static const String _apiPrefix = '/glossary-management';

  /// 获取所有术语表
  static Future<List<Glossary>> getAllGlossaries() async {
    try {
      final String token = _getAuthToken();
      final http.Response response = await http.get(
        Uri.parse('$_baseUrl$_apiPrefix/list'),
        headers: <String, String>{
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final List<Glossary> glossaries = (data['glossaries'] as List<dynamic>)
            .map((g) => Glossary.fromJson(g as Map<String, dynamic>))
            .toList();
        return glossaries;
      } else {
        print('❌ Failed to get glossaries: ${response.statusCode}');
        return <Glossary>[];
      }
    } catch (e) {
      print('❌ Error getting glossaries: $e');
      return <Glossary>[];
    }
  }

  /// 添加术语表条目
  static Future<bool> addGlossaryEntry({
    required String glossaryId,
    required String source,
    required String target,
    required String category,
  }) async {
    try {
      final String token = _getAuthToken();
      final http.Response response = await http.post(
        Uri.parse('$_baseUrl$_apiPrefix/entry'),
        headers: <String, String>{
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: json.encode(<String, String>{
          'glossary_id': glossaryId,
          'source': source,
          'target': target,
          'category': category,
        }),
      );

      if (response.statusCode == 200) {
        print('✅ Glossary entry added successfully');
        return true;
      } else {
        print('❌ Failed to add glossary entry: ${response.statusCode}');
        return false;
      }
    } catch (e) {
      print('❌ Error adding glossary entry: $e');
      return false;
    }
  }

  /// 更新术语表条目
  static Future<bool> updateGlossaryEntry({
    required String glossaryId,
    required String entryId,
    required String source,
    required String target,
    required String category,
  }) async {
    try {
      final String token = _getAuthToken();
      final http.Response response = await http.put(
        Uri.parse('$_baseUrl$_apiPrefix/entry/$glossaryId/$entryId'),
        headers: <String, String>{
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: json.encode(<String, String>{
          'source': source,
          'target': target,
          'category': category,
        }),
      );

      if (response.statusCode == 200) {
        print('✅ Glossary entry updated successfully');
        return true;
      } else {
        print('❌ Failed to update glossary entry: ${response.statusCode}');
        return false;
      }
    } catch (e) {
      print('❌ Error updating glossary entry: $e');
      return false;
    }
  }

  /// 删除术语表条目
  static Future<bool> deleteGlossaryEntry({
    required String glossaryId,
    required String entryId,
  }) async {
    try {
      final String token = _getAuthToken();
      final http.Response response = await http.delete(
        Uri.parse('$_baseUrl$_apiPrefix/entry/$glossaryId/$entryId'),
        headers: <String, String>{
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        print('✅ Glossary entry deleted successfully');
        return true;
      } else {
        print('❌ Failed to delete glossary entry: ${response.statusCode}');
        return false;
      }
    } catch (e) {
      print('❌ Error deleting glossary entry: $e');
      return false;
    }
  }

  /// 获取认证令牌
  static String _getAuthToken() {
    try {
      final ConfigService configService = ConfigService();
      final String? authHeader = configService.authorizationHeader;
      if (authHeader != null && authHeader.isNotEmpty) {
        // 从 "Bearer token" 格式中提取令牌
        if (authHeader.startsWith('Bearer ')) {
          return authHeader.substring(7);
        }
        return authHeader;
      }

      // 如果没有令牌，返回空字符串
      return '';
    } catch (e) {
      print('❌ Error getting auth token: $e');
      return '';
    }
  }
}
