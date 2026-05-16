import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../app/app_config.dart';
import 'config_service.dart';

/// Service for converting document formats without translation
class FormatConversionService {
  factory FormatConversionService() => _instance;
  FormatConversionService._internal();
  static final FormatConversionService _instance =
      FormatConversionService._internal();

  final ConfigService _configService = ConfigService();

  /// Convert document format (parse + convert, no translation)
  Future<Map<String, dynamic>> convertFormat({
    required List<int> fileBytes,
    required String fileName,
    String? workflowType,
    String? convertEngine,
    bool? formulaOcr,
    bool? tableOcr,
    String? modelVersion,
    String? mineruToken,
    bool? deepSplit,
    String? tableBodyFormat,
    bool? skipCache,
    String? toLang,
    String? sourceLang,
  }) async {
    try {
      // Get base URL from config
      final appConfig = await _configService.getAppConfig();
      final baseUrl = appConfig?['base_url'] ?? AppConfig.baseUrl;

      // Auto-detect workflow type from file extension if not provided
      final detectedWorkflowType =
          workflowType ?? _getWorkflowTypeFromExtension(fileName);

      // Prepare request payload
      final payload = <String, Object>{
        'file_name': fileName,
        'file_content': base64Encode(fileBytes),
        if (detectedWorkflowType.isNotEmpty)
          'workflow_type': detectedWorkflowType,
        if (convertEngine != null) 'convert_engine': convertEngine,
        if (formulaOcr != null) 'formula_ocr': formulaOcr,
        if (tableOcr != null) 'table_ocr': tableOcr,
        if (modelVersion != null) 'model_version': modelVersion,
        if (mineruToken != null && mineruToken.isNotEmpty)
          'mineru_token': mineruToken,
        // deep_split: Only include if explicitly provided, otherwise let backend use default from translation_config.json
        if (deepSplit != null) 'deep_split': deepSplit,
        if (tableBodyFormat != null && tableBodyFormat.isNotEmpty)
          'table_body_format': tableBodyFormat,
        // skip_cache: When true, skip using cached conversion results (Extract phase).
        // When false, use cached results if available (Convert phase).
        // Always pass this parameter explicitly to ensure backend receives the correct value.
        if (skipCache != null) 'skip_cache': skipCache,
        // CRITICAL: Pass to_lang for exclusion detection during extraction
        if (toLang != null && toLang.isNotEmpty) 'to_lang': toLang,
        // OCR source language hint for MinerU (markdown_based workflow).
        // When null or "auto", backend will default to auto-detection.
        if (sourceLang != null &&
            sourceLang.isNotEmpty &&
            sourceLang != 'auto')
          'ocr_language': sourceLang,
      };

      // Debug: Log skip_cache parameter
      if (skipCache != null) {
        print(
          '[FormatConversionService] skipCache parameter: $skipCache (type: ${skipCache.runtimeType})',
        );
      } else {
        print(
          '[FormatConversionService] skipCache parameter is null, will not be included in payload',
        );
      }

      // Get authentication token
      final authHeader = _getAuthToken();

      // Make API request
      final response = await http.post(
        Uri.parse('$baseUrl/service/convert-format'),
        headers: <String, String>{
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
          ...ConfigService.desktopBackendHeaders,
        },
        body: jsonEncode(payload),
      );

      final result = jsonDecode(response.body) as Map<String, dynamic>? ?? <String, dynamic>{};
      if (response.statusCode == 200) {
        // Backend may return 200 with success: false (e.g. PDF too large)
        final bool bodySuccess = result['success'] == true;
        if (!bodySuccess) {
          return <String, dynamic>{
            'success': false,
            'error': result['message'] ??
                result['detail'] ??
                'Request failed',
          };
        }
        return <String, dynamic>{
          'success': true,
          'data': result,
        };
      } else {
        return <String, dynamic>{
          'success': false,
          'error': result['detail'] ??
              result['message'] ??
              'Unknown error occurred',
        };
      }
    } catch (e) {
      return <String, dynamic>{
        'success': false,
        'error': 'Failed to convert format: $e',
      };
    }
  }

  /// Get workflow type from file extension
  String _getWorkflowTypeFromExtension(String fileName) {
    final ext = fileName.toLowerCase().split('.').last;
    switch (ext) {
      case 'txt':
        return 'txt';
      case 'md':
      case 'pdf':
      case 'png':
      case 'jpg':
      case 'jpeg':
        return 'markdown_based';
      case 'json':
      case 'arb':
        return 'json';
      case 'xlsx':
      case 'xls':
      case 'csv':
        return 'xlsx';
      case 'srt':
        return 'srt';
      case 'epub':
        return 'epub';
      case 'mobi':
      case 'azw':
        return 'mobi';
      case 'html':
      case 'htm':
        return 'html';
      case 'ts':
        return 'qt_ts';
      case 'docx':
        return 'docx';
      case 'pptx':
        return 'pptx';
      default:
        return 'markdown_based'; // Default fallback
    }
  }

  /// Fetch a URL and start format conversion (parse + convert, no translation).
  Future<Map<String, dynamic>> fetchUrl({
    required String url,
    String extractMode = 'content',
    String? workflowType,
    bool? deepSplit,
    bool? skipCache,
    String? toLang,
  }) async {
    try {
      final appConfig = await _configService.getAppConfig();
      final baseUrl = appConfig?['base_url'] ?? AppConfig.baseUrl;

      final payload = <String, Object>{
        'url': url,
        'extract_mode': extractMode,
        if (workflowType != null && workflowType.isNotEmpty)
          'workflow_type': workflowType,
        if (deepSplit != null) 'deep_split': deepSplit,
        if (skipCache != null) 'skip_cache': skipCache,
        if (toLang != null && toLang.isNotEmpty) 'to_lang': toLang,
      };

      final authHeader = _getAuthToken();

      final response = await http.post(
        Uri.parse('$baseUrl/service/fetch-url'),
        headers: <String, String>{
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
          ...ConfigService.desktopBackendHeaders,
        },
        body: jsonEncode(payload),
      );

      final result = jsonDecode(response.body) as Map<String, dynamic>? ?? <String, dynamic>{};
      if (response.statusCode == 200) {
        final bool bodySuccess = result['success'] == true;
        if (!bodySuccess) {
          return <String, dynamic>{
            'success': false,
            'error': result['message'] ?? result['detail'] ?? 'Request failed',
          };
        }
        return <String, dynamic>{
          'success': true,
          'data': result,
        };
      } else {
        return <String, dynamic>{
          'success': false,
          'error': result['detail'] ?? result['message'] ?? 'Unknown error occurred',
        };
      }
    } catch (e) {
      return <String, dynamic>{
        'success': false,
        'error': 'Failed to fetch URL: $e',
      };
    }
  }

  /// Get authentication token from ConfigService
  String? _getAuthToken() => _configService.authorizationHeader;

  /// Parser options aligned with global settings (cloud vs local MinerU, OCR flags).
  Future<FormatConvertParserOptions> resolveParserOptions({
    required String parsingEngine,
    required bool formulaOcr,
    required bool tableOcr,
    String modelVersion = 'vlm',
  }) async {
    String? mineruToken;
    if (parsingEngine == 'mineru') {
      final Map<String, dynamic>? secretsConfig =
          await _configService.getSecretsConfig();
      final Map<String, dynamic>? mineruTokenData =
          secretsConfig?['translator_mineru_token_meta']
              as Map<String, dynamic>?;
      mineruToken = mineruTokenData?['key'] as String? ?? '';
    }
    return FormatConvertParserOptions(
      convertEngine: parsingEngine,
      formulaOcr: formulaOcr,
      tableOcr: tableOcr,
      modelVersion: modelVersion,
      mineruToken: mineruToken?.isNotEmpty ?? false ? mineruToken : null,
    );
  }
}

/// MinerU / parsing options for [FormatConversionService.convertFormat].
class FormatConvertParserOptions {
  const FormatConvertParserOptions({
    required this.convertEngine,
    required this.formulaOcr,
    required this.tableOcr,
    this.modelVersion = 'vlm',
    this.mineruToken,
  });

  final String convertEngine;
  final bool formulaOcr;
  final bool tableOcr;
  final String modelVersion;
  final String? mineruToken;
}
