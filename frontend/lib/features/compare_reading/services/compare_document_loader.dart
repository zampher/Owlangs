// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../../../app/app_config.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../models/compare_document_model.dart';

/// Resolves local file bytes into a [CompareDocumentModel] for compare reading.
///
/// Does not start translation or format-conversion tasks. Uses local decode for
/// text/PDF/images and lightweight `/preview/docx|xlsx|pptx|epub|mobi` for
/// Office / ebook formats.
class CompareDocumentLoader {
  CompareDocumentLoader({Dio? dio}) : _dio = dio;

  Dio? _dio;

  static const Set<String> _pdfExt = <String>{'pdf'};
  static const Set<String> _imageExt = <String>{'png', 'jpg', 'jpeg'};
  static const Set<String> _htmlExt = <String>{'html', 'htm'};
  static const Set<String> _mdExt = <String>{'md', 'markdown'};
  static const Set<String> _plainExt = <String>{
    'txt',
    'srt',
    'csv',
    'json',
    'arb',
    'ts',
  };
  static const Set<String> _docxExt = <String>{'docx'};
  static const Set<String> _xlsxExt = <String>{'xlsx'};
  static const Set<String> _pptxExt = <String>{'pptx'};
  static const Set<String> _epubExt = <String>{'epub'};
  static const Set<String> _mobiExt = <String>{'mobi', 'azw', 'azw3'};

  /// Extensions that compare reading can load without a convert/translate task.
  static List<String> get supportedExtensions => <String>[
        ..._pdfExt,
        ..._imageExt,
        ..._htmlExt,
        ..._mdExt,
        ..._plainExt,
        ..._docxExt,
        ..._xlsxExt,
        ..._pptxExt,
        ..._epubExt,
        ..._mobiExt,
      ]..sort();

  /// Classify extension into a pane kind (null = unsupported).
  static ComparePaneKind? classifyKind(String extension) {
    final String ext = _normalizeExt(extension);
    if (_pdfExt.contains(ext)) {
      return ComparePaneKind.pdf;
    }
    if (_imageExt.contains(ext)) {
      return ComparePaneKind.image;
    }
    if (_htmlExt.contains(ext) ||
        _mdExt.contains(ext) ||
        _plainExt.contains(ext) ||
        _docxExt.contains(ext) ||
        _xlsxExt.contains(ext) ||
        _pptxExt.contains(ext) ||
        _epubExt.contains(ext) ||
        _mobiExt.contains(ext)) {
      return ComparePaneKind.scrollable;
    }
    return null;
  }

  static String _normalizeExt(String extension) {
    return extension.toLowerCase().replaceAll('.', '').trim();
  }

  static String extensionOf(String fileName) {
    final int dot = fileName.lastIndexOf('.');
    if (dot < 0 || dot == fileName.length - 1) {
      return '';
    }
    return fileName.substring(dot + 1);
  }

  Future<CompareDocumentModel> load({
    required String fileName,
    required Uint8List bytes,
  }) async {
    final String ext = _normalizeExt(extensionOf(fileName));
    final ComparePaneKind? kind = classifyKind(ext);
    AppLogger.log(
      'CompareDocumentLoader',
      'Loading fileName=$fileName ext=$ext kind=$kind bytes=${bytes.length}',
      level: LogLevel.info,
    );
    if (kind == null) {
      throw UnsupportedError(
        'Unsupported compare-reading format: .$ext '
        '(supported: ${supportedExtensions.join(', ')})',
      );
    }
    if (bytes.isEmpty) {
      throw StateError('Empty file: $fileName');
    }

    if (_pdfExt.contains(ext)) {
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.pdf,
        contentType: 'pdf',
        pdfBytes: bytes,
      );
    }
    if (_imageExt.contains(ext)) {
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.image,
        contentType: 'image',
        imageBytes: bytes,
      );
    }
    if (_docxExt.contains(ext)) {
      final String html = await _previewOfficeHtml(
        path: '/preview/docx',
        fileName: fileName,
        bytes: bytes,
      );
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.scrollable,
        contentType: 'html',
        textContent: html,
      );
    }
    if (_xlsxExt.contains(ext)) {
      final String html = await _previewOfficeHtml(
        path: '/preview/xlsx',
        fileName: fileName,
        bytes: bytes,
      );
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.scrollable,
        contentType: 'html',
        textContent: html,
      );
    }
    if (_pptxExt.contains(ext)) {
      final String html = await _previewOfficeHtml(
        path: '/preview/pptx',
        fileName: fileName,
        bytes: bytes,
      );
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.scrollable,
        contentType: 'html',
        textContent: html,
      );
    }
    if (_epubExt.contains(ext)) {
      final String html = await _previewOfficeHtml(
        path: '/preview/epub',
        fileName: fileName,
        bytes: bytes,
      );
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.scrollable,
        contentType: 'html',
        textContent: html,
      );
    }
    if (_mobiExt.contains(ext)) {
      final String html = await _previewOfficeHtml(
        path: '/preview/mobi',
        fileName: fileName,
        bytes: bytes,
      );
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.scrollable,
        contentType: 'html',
        textContent: html,
      );
    }
    if (_htmlExt.contains(ext)) {
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.scrollable,
        contentType: 'html',
        textContent: _decodeText(bytes, fileName),
      );
    }
    if (_mdExt.contains(ext)) {
      return CompareDocumentModel(
        fileName: fileName,
        kind: ComparePaneKind.scrollable,
        contentType: 'md',
        textContent: _decodeText(bytes, fileName),
      );
    }
    return CompareDocumentModel(
      fileName: fileName,
      kind: ComparePaneKind.scrollable,
      contentType: 'plain',
      textContent: _decodeText(bytes, fileName),
    );
  }

  String _decodeText(Uint8List bytes, String fileName) {
    try {
      return utf8.decode(bytes);
    } on FormatException catch (e) {
      AppLogger.log(
        'CompareDocumentLoader',
        'UTF-8 decode failed for $fileName: $e; trying latin1',
        level: LogLevel.warn,
      );
      return latin1.decode(bytes);
    }
  }

  Future<String> _previewOfficeHtml({
    required String path,
    required String fileName,
    required Uint8List bytes,
  }) async {
    final Dio dio = _dio ?? _buildDio();
    final FormData form = FormData.fromMap(<String, dynamic>{
      'file': MultipartFile.fromBytes(bytes, filename: fileName),
    });
    final Map<String, dynamic> headers = Map<String, dynamic>.from(
      dio.options.headers,
    );
    headers.remove(Headers.contentTypeHeader);
    headers.remove('Content-Type');
    AppLogger.log(
      'CompareDocumentLoader',
      'POST $path fileName=$fileName size=${bytes.length}',
      level: LogLevel.info,
    );
    try {
      final Response<dynamic> resp = await dio.post<dynamic>(
        path,
        data: form,
        options: Options(
          headers: headers,
          responseType: ResponseType.plain,
        ),
      );
      final Object? data = resp.data;
      if (data is! String || data.isEmpty) {
        AppLogger.log(
          'CompareDocumentLoader',
          'Empty preview response for $fileName path=$path '
          'status=${resp.statusCode} type=${data.runtimeType}',
          level: LogLevel.error,
        );
        throw StateError('Empty preview response for $fileName');
      }
      return data;
    } on DioException catch (e) {
      final int? status = e.response?.statusCode;
      final String detail = previewErrorDetail(e.response?.data, fallback: e.message);
      AppLogger.log(
        'CompareDocumentLoader',
        'Preview failed path=$path fileName=$fileName '
        'status=$status detail=$detail error=$e',
        level: LogLevel.error,
      );
      if (status == 404) {
        throw StateError(
          'Preview API missing ($path). Restart the Owlangs backend '
          'so /preview routes are loaded, then import again.',
        );
      }
      if (detail.isNotEmpty) {
        throw StateError('Preview failed for $fileName: $detail');
      }
      rethrow;
    }
  }

  /// Extract a human-readable detail from a preview API error body.
  static String previewErrorDetail(Object? data, {String? fallback}) {
    if (data is Map && data['detail'] != null) {
      return data['detail'].toString();
    }
    if (data is String && data.trim().isNotEmpty) {
      final String trimmed = data.trim();
      // FastAPI JSON body often arrives as plain text with ResponseType.plain.
      final RegExpMatch? match = RegExp(
        r'"detail"\s*:\s*"((?:\\.|[^"\\])*)"',
      ).firstMatch(trimmed);
      if (match != null) {
        return match
            .group(1)!
            .replaceAll(r'\"', '"')
            .replaceAll(r'\\', r'\');
      }
      return trimmed.length > 400 ? '${trimmed.substring(0, 400)}…' : trimmed;
    }
    return fallback ?? '';
  }

  Dio _buildDio() {
    final ConfigService cfg = ConfigService();
    final String? authHeader = cfg.authorizationHeader;
    return Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        headers: <String, dynamic>{
          if (authHeader != null) 'Authorization': authHeader,
          ...ConfigService.desktopBackendHeaders,
        },
        connectTimeout: AppConfig.requestTimeout,
        receiveTimeout: AppConfig.longRequestTimeout,
        sendTimeout: AppConfig.longRequestTimeout,
      ),
    );
  }
}
