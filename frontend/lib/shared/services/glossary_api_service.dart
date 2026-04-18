// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'config_service.dart';
import '../../app/app_config.dart';

class GlossaryApiService {
  static final String _baseUrl = AppConfig.baseUrl;

  static Map<String, String> _headers() {
    final String? auth = ConfigService().authorizationHeader;
    return <String, String>{
      'Content-Type': 'application/json',
      if (auth != null && auth.isNotEmpty) 'Authorization': auth,
      ...ConfigService.desktopBackendHeaders,
    };
  }

  // Entries
  static Future<Map<String, dynamic>> listEntries(
    String glossaryId, {
    String? search,
  }) async {
    final Uri uri =
        Uri.parse('$_baseUrl/auth/glossaries/$glossaryId/entries').replace(
      queryParameters: <String, dynamic>{
        if (search != null && search.isNotEmpty) 'search': search,
      },
    );
    final http.Response res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      return json.decode(res.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to list entries: ${res.statusCode}');
  }

  static Future<void> createEntry(
    String glossaryId, {
    required String src,
    required String dst,
    String category = '',
    String? targetLang,
  }) async {
    final Uri uri = Uri.parse('$_baseUrl/auth/glossaries/$glossaryId/entries');
    final Map<String, String> body = <String, String>{
      'src': src,
      'dst': dst,
      'category': category,
      if (targetLang != null) 'target_lang': targetLang,
    };
    final http.Response res =
        await http.post(uri, headers: _headers(), body: json.encode(body));
    if (res.statusCode != 200) {
      throw Exception('Failed to create entry: ${res.statusCode}');
    }
  }

  static Future<void> updateEntry(
    String glossaryId,
    String entryId, {
    required String src,
    required String dst,
    String category = '',
  }) async {
    final Uri uri =
        Uri.parse('$_baseUrl/auth/glossaries/$glossaryId/entries/$entryId');
    final http.Response res = await http.put(
      uri,
      headers: _headers(),
      body: json.encode(<String, String>{
        'src': src,
        'dst': dst,
        'category': category,
      }),
    );
    if (res.statusCode != 200) {
      throw Exception('Failed to update entry: ${res.statusCode}');
    }
  }

  static Future<void> deleteEntry(String glossaryId, String entryId) async {
    final Uri uri =
        Uri.parse('$_baseUrl/auth/glossaries/$glossaryId/entries/$entryId');
    final http.Response res = await http.delete(uri, headers: _headers());
    if (res.statusCode != 200) {
      throw Exception('Failed to delete entry: ${res.statusCode}');
    }
  }

  // Import CSV to glossary (merge)
  static Future<Map<String, dynamic>> importCsv(
    String glossaryId,
    Uint8List bytes, {
    String mergeMode = 'update',
  }) async {
    final Uri uri = Uri.parse('$_baseUrl/auth/glossaries/$glossaryId/import');
    final http.MultipartRequest request = http.MultipartRequest('POST', uri);
    final String? auth = ConfigService().authorizationHeader;
    if (auth != null && auth.isNotEmpty) {
      request.headers['Authorization'] = auth;
    }
    request.headers.addAll(ConfigService.desktopBackendHeaders);
    request.fields['merge_mode'] = mergeMode;
    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: 'glossary.csv'),
    );
    final http.StreamedResponse streamed = await request.send();
    final http.Response res = await http.Response.fromStream(streamed);
    if (res.statusCode == 200) {
      return json.decode(res.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to import CSV: ${res.statusCode}');
  }

  // Download CSV
  static Future<Uint8List> downloadCsv(String glossaryId) async {
    final Uri uri = Uri.parse('$_baseUrl/auth/glossaries/$glossaryId/download');
    final http.Response res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      return res.bodyBytes;
    }
    throw Exception('Failed to download CSV: ${res.statusCode}');
  }

  // Delete a glossary by id
  static Future<void> deleteGlossary(String glossaryId) async {
    final Uri uri = Uri.parse('$_baseUrl/auth/glossaries/$glossaryId');
    final http.Response res = await http.delete(uri, headers: _headers());
    if (res.statusCode != 200) {
      throw Exception('Failed to delete glossary: ${res.statusCode}');
    }
  }

  // Get simplified glossary list for UI selection
  static Future<List<Map<String, dynamic>>> getSimpleGlossaryList() async {
    final Uri uri = Uri.parse('$_baseUrl/auth/glossaries/simple-list');
    final http.Response res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      final Map<String, dynamic> data =
          json.decode(res.body) as Map<String, dynamic>;
      return List<Map<String, dynamic>>.from(data['glossaries'] ?? <dynamic>[]);
    }
    throw Exception('Failed to get glossary list: ${res.statusCode}');
  }

  // Export all glossaries. format: 'csvzip' or 'xlsx'
  static Future<Uint8List> exportAll({
    String? targetLanguage,
    String? category,
    String? search,
    String format = 'csvzip',
  }) async {
    final Map<String, String> qp = <String, String>{'format': format};
    if (targetLanguage != null && targetLanguage.isNotEmpty) {
      qp['target_language'] = targetLanguage;
    }
    if (category != null) qp['category'] = category;
    if (search != null && search.isNotEmpty) qp['search'] = search;
    final Uri uri = Uri.parse('$_baseUrl/auth/glossaries/export-all')
        .replace(queryParameters: qp.isEmpty ? null : qp);
    final http.Response res = await http.get(uri, headers: _headers());
    if (res.statusCode == 200) {
      return res.bodyBytes;
    }
    throw Exception('Failed to export all: ${res.statusCode}');
  }

  // Create an empty glossary (CSV with only header) by upload API
  static Future<Map<String, dynamic>> createEmptyGlossary({
    required String name,
    bool isGlobal = true,
    String description = '',
  }) async {
    final Uri uri = Uri.parse('$_baseUrl/auth/glossaries/upload');
    final http.MultipartRequest request = http.MultipartRequest('POST', uri);
    final String? auth = ConfigService().authorizationHeader;
    if (auth != null && auth.isNotEmpty) {
      request.headers['Authorization'] = auth;
    }
    request.headers.addAll(ConfigService.desktopBackendHeaders);
    request.fields['name'] = name;
    request.fields['description'] = description;
    request.fields['is_global'] = isGlobal ? 'true' : 'false';

    // CSV header: src,dst,category,target_lang
    const String csv = 'src,dst,category,target_lang\n';
    final Uint8List bytes = Uint8List.fromList(utf8.encode(csv));
    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: 'glossary.csv'),
    );

    final http.StreamedResponse streamed = await request.send();
    final http.Response res = await http.Response.fromStream(streamed);
    if (res.statusCode == 200) {
      return json.decode(res.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to create glossary: ${res.statusCode}');
  }

  // Apply glossary to a translation task
  static Future<Map<String, dynamic>> applyGlossaryToTask(
    String glossaryId,
    String taskId,
  ) async {
    final Uri uri = Uri.parse(
      '$_baseUrl/auth/glossaries/$glossaryId/apply-to-task/$taskId',
    );
    final http.Response res = await http.post(uri, headers: _headers());
    if (res.statusCode == 200) {
      return json.decode(res.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to apply glossary to task: ${res.statusCode}');
  }

  // Add terms to personal glossary (merge mode: update = upsert, append = add new only, replace = replace all)
  // Note: The backend will determine the personal glossary ID from the authenticated user
  // If personal glossary doesn't exist, it will be automatically created
  static Future<Map<String, dynamic>> addToPersonalGlossary(
    Map<String, dynamic> glossaryData, {
    String mergeMode = 'update',
  }) async {
    // Convert glossary data to CSV format
    // Format: src,dst,category,target_lang
    final List<String> lines = <String>['src,dst,category,target_lang'];
    glossaryData.forEach((String src, dst) {
      final String srcEscaped = '"${src.toString().replaceAll('"', '""')}"';
      final dstValue =
          dst is Map ? dst['dst'] ?? dst.toString() : dst.toString();
      final String dstEscaped = '"${dstValue.replaceAll('"', '""')}"';
      final String category =
          dst is Map ? (dst['category'] ?? '').toString() : '';
      final String targetLang =
          dst is Map ? (dst['target_lang'] ?? '').toString() : '';
      final String categoryEscaped = '"${category.replaceAll('"', '""')}"';
      final String targetLangEscaped = '"${targetLang.replaceAll('"', '""')}"';
      lines.add('$srcEscaped,$dstEscaped,$categoryEscaped,$targetLangEscaped');
    });
    final String csvContent = lines.join('\n');
    final Uint8List csvBytes = Uint8List.fromList(utf8.encode(csvContent));

    // Get personal glossary ID from the glossary list
    // The backend will determine the personal glossary ID from the authenticated user
    final List<Map<String, dynamic>> listRes = await getSimpleGlossaryList();
    final Map<String, dynamic> personalGlossary = listRes.firstWhere(
      (Map<String, dynamic> g) => g['type'] == 'personal',
      orElse: () => <String, dynamic>{},
    );

    // If personal glossary doesn't exist, create it automatically
    String personalId;
    if (personalGlossary.isEmpty || personalGlossary['id'] == null) {
      // Auto-create personal glossary using create-and-import endpoint
      final Uri uri = Uri.parse('$_baseUrl/auth/glossaries/create-and-import');
      final http.MultipartRequest request = http.MultipartRequest('POST', uri);
      final String? auth = ConfigService().authorizationHeader;
      if (auth != null && auth.isNotEmpty) {
        request.headers['Authorization'] = auth;
      }
      request.headers.addAll(ConfigService.desktopBackendHeaders);
      request.fields['name'] = 'Personal Glossary';
      request.fields['description'] = 'Auto-created personal glossary';
      request.fields['is_global'] = 'false';
      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          csvBytes,
          filename: 'glossary.csv',
        ),
      );

      final http.StreamedResponse streamed = await request.send();
      final http.Response res = await http.Response.fromStream(streamed);
      if (res.statusCode == 200) {
        final Map<String, dynamic> result =
            json.decode(res.body) as Map<String, dynamic>;
        personalId = result['glossary_id'] as String;
        // Return result with detailed stats
        return <String, dynamic>{
          'success': true,
          'message': 'Personal glossary created and terms added',
          'imported_count': glossaryData.length,
          'total': glossaryData.length,
          'new_terms': glossaryData.length,
          'updated_terms': 0,
          'glossary_created': true,
        };
      } else {
        throw Exception(
          'Failed to create personal glossary: ${res.statusCode}',
        );
      }
    } else {
      personalId = personalGlossary['id'] as String;
      // Import to existing personal glossary
      return importCsv(personalId, csvBytes, mergeMode: mergeMode);
    }
  }
}
