import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../app/app_config.dart';
import 'config_service.dart';
import '../config/pagination_config.dart';
import '../utils/app_logger.dart';

/// TranslationService: 前端最小闭环 - 提交任务/查询状态/轮询/取消/释放/下载链接
class TranslationService {
  factory TranslationService() => _instance;
  TranslationService._internal();
  static final TranslationService _instance = TranslationService._internal();

  // Cache for translation-segments per task to avoid duplicate polling chains.
  final Map<String, Future<Map<String, dynamic>>> _segmentsRequests =
      <String, Future<Map<String, dynamic>>>{};
  final Map<String, Map<String, dynamic>> _segmentsCache =
      <String, Map<String, dynamic>>{};

  Dio _buildAuthedDio({bool useLongTimeout = false}) {
    final cfg = ConfigService();
    final authHeader = cfg.authorizationHeader;
    final timeout = useLongTimeout
        ? AppConfig.longRequestTimeout
        : AppConfig.requestTimeout;
    
    final baseUrl = AppConfig.baseUrl;
    
    return Dio(
      BaseOptions(
        baseUrl: baseUrl,
        headers: <String, dynamic>{
          'Content-Type': 'application/json',
          if (authHeader != null) 'Authorization': authHeader,
          ...ConfigService.desktopBackendHeaders,
        },
        connectTimeout: timeout,
        receiveTimeout: timeout,
      ),
    );
  }

  /// 提交翻译任务
  /// fileBytes: 原文件字节；fileName: 原文件名；payload: 工作流及参数
  /// execution_mode: `immediate` (default) or `queued` (FIFO worker pool).
  Future<Map<String, dynamic>> submitTask({
    required List<int> fileBytes,
    required String fileName,
    required Map<String, dynamic> payload,
    String executionMode = 'immediate',
    String? relativePath,
  }) async {
    // Use long timeout for file upload and translation task submission
    final dio = _buildAuthedDio(useLongTimeout: true);
    final body = <String, Object>{
      'file_content': base64Encode(fileBytes),
      'file_name': fileName,
      'payload': payload,
      'execution_mode': executionMode,
      if (relativePath != null && relativePath.isNotEmpty)
        'relative_path': relativePath,
    };
    final resp = await dio.post(
      '/service/translate',
      data: body,
      options: Options(
        receiveTimeout: AppConfig.longRequestTimeout,
        sendTimeout: AppConfig.longRequestTimeout,
      ),
    );
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// List translation tasks for the current session (in-memory + stashed outputs).
  Future<Map<String, dynamic>> listTranslationTasks({int limit = 50}) async {
    final dio = _buildAuthedDio();
    final resp = await dio.get<Map<String, dynamic>>(
      '/service/tasks',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final data = resp.data;
    if (data == null) {
      return <String, dynamic>{'tasks': <dynamic>[], 'limit': limit};
    }
    return data;
  }

  /// Admin-only: cancel queued/in-flight work, drop memory tasks, wipe result stash.
  Future<Map<String, dynamic>> adminClearTranslationQueue() async {
    final Dio dio = _buildAuthedDio(useLongTimeout: true);
    final Response<dynamic> resp = await dio.post<dynamic>(
      '/service/admin/clear-translation-queue',
      options: Options(
        receiveTimeout: AppConfig.longRequestTimeout,
        sendTimeout: AppConfig.longRequestTimeout,
      ),
    );
    final dynamic body = resp.data;
    if (body is Map<String, dynamic>) {
      return body;
    }
    if (body is Map) {
      return body.cast<String, dynamic>();
    }
    return <String, dynamic>{};
  }

  /// 查询任务状态
  Future<Map<String, dynamic>> getStatus(String taskId) async {
    final dio = _buildAuthedDio();
    final resp = await dio.get('/service/status/$taskId');
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// 查询任务日志
  Future<Map<String, dynamic>> getLogs(String taskId) async {
    final dio = _buildAuthedDio();
    final resp = await dio.get('/service/logs/$taskId');
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// 检查任务中的 LaTeX 公式完整性（仅在后端支持时可用）
  Future<Map<String, dynamic>> checkLatexFormulas(String taskId) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post('/service/latex-formula-check/$taskId');
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// 使用后端 LLM 对单个片段做 LaTeX/公式修复（不直接写回任务状态）
  Future<Map<String, dynamic>> repairLatexForSegment(
    String taskId,
    int segmentIndex,
    String text, {
    String? sourceText,
    String? userPrompt,
  }) async {
    final dio = _buildAuthedDio();
    final body = <String, dynamic>{
      'segment_index': segmentIndex,
      'text': text,
      if (sourceText != null) 'source_text': sourceText,
      if (userPrompt != null && userPrompt.isNotEmpty) 'user_prompt': userPrompt,
    };
    final resp = await dio.post(
      '/service/latex-formula-repair-segment/$taskId',
      data: body,
    );
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// 获取格式设置
  Future<Map<String, dynamic>> getFormatSettings(String taskId) async {
    final dio = _buildAuthedDio();
    final resp = await dio.get('/service/format-settings/$taskId');
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// 更新格式设置
  Future<Map<String, dynamic>> updateFormatSettings(
    String taskId, {
    String? tableBodyFormat,
    String? equationFormat,
    bool? bilingualExport,
    String? bilingualOrder,
    bool? sourceTextItalic,
    String? sourceTextColor,
    bool? targetTextItalic,
    String? targetTextColor,
  }) async {
    final dio = _buildAuthedDio();
    final queryParams = <String, dynamic>{};
    if (tableBodyFormat != null) {
      queryParams['table_body_format'] = tableBodyFormat;
    }
    if (equationFormat != null) {
      queryParams['equation_format'] = equationFormat;
    }
    if (bilingualExport != null) {
      queryParams['bilingual_export'] = bilingualExport;
    }
    if (bilingualOrder != null) {
      queryParams['bilingual_order'] = bilingualOrder;
    }
    if (sourceTextItalic != null) {
      queryParams['source_text_italic'] = sourceTextItalic;
    }
    if (sourceTextColor != null) {
      queryParams['source_text_color'] = sourceTextColor;
    }
    if (targetTextItalic != null) {
      queryParams['target_text_italic'] = targetTextItalic;
    }
    if (targetTextColor != null) {
      queryParams['target_text_color'] = targetTextColor;
    }
    final resp = await dio.put(
      '/service/format-settings/$taskId',
      queryParameters: queryParams,
    );
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// 取消任务
  Future<Map<String, dynamic>> cancelTask(String taskId) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post('/service/cancel/$taskId');
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// 释放任务资源
  Future<Map<String, dynamic>> releaseTask(String taskId) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post('/service/release/$taskId');
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Writes rebuilt exports to server-side stash so [listTranslationTasks] / queue downloads match current segments.
  Future<Map<String, dynamic>> persistQueueSnapshot(String taskId) async {
    final dio = _buildAuthedDio(useLongTimeout: true);
    final resp = await dio.post<Map<String, dynamic>>(
      '/service/persist-result/$taskId',
      options: Options(
        receiveTimeout: AppConfig.longRequestTimeout,
        sendTimeout: AppConfig.longRequestTimeout,
      ),
    );
    final data = resp.data;
    if (data == null) {
      return <String, dynamic>{'ok': false};
    }
    return Map<String, dynamic>.from(data);
  }

  /// Check if Pandoc and Calibre are available for EPUB/MOBI export.
  /// When both are true, the UI can offer a choice (Pandoc vs Calibre).
  Future<Map<String, bool>> getEbookConvertersAvailability() async {
    final dio = _buildAuthedDio();
    final resp = await dio.get<Map<String, dynamic>>('/service/ebook-converters');
    final data = resp.data;
    if (data == null) return <String, bool>{'pandoc': false, 'calibre': false};
    return <String, bool>{
      'pandoc': data['pandoc'] as bool? ?? false,
      'calibre': data['calibre'] as bool? ?? false,
    };
  }

  /// 拼接下载链接（前端直接跳转）
  String buildDownloadUrl(String taskId, String fileType) {
    // 与后端保持相对路径，复用当前域名与端口
    return '/service/download/$taskId/$fileType';
  }

  /// 拼接debug文件链接（前端直接跳转）
  String buildDebugUrl(String taskId, String fileType) {
    // 与后端保持相对路径，复用当前域名与端口
    return '/service/debug/$taskId/$fileType';
  }

  /// 下载文件
  /// 返回文件字节数组
  Future<List<int>> downloadFile(String url) async {
    // Use long timeout for file downloads because backend may need to
    // generate the file on demand (especially for large documents).
    final Dio dio = _buildAuthedDio(useLongTimeout: true);
    // 如果 URL 是相对路径，需要确保以 / 开头
    String fullUrl;
    if (url.startsWith('http://') || url.startsWith('https://')) {
      fullUrl = url;
    } else {
      // 确保相对路径以 / 开头
      final normalizedPath = url.startsWith('/') ? url : '/$url';
      fullUrl = '${AppConfig.baseUrl}$normalizedPath';
    }
    try {
      final Response<List<int>> resp = await dio.get<List<int>>(
        fullUrl,
        options: Options(
          responseType: ResponseType.bytes,
          followRedirects: true,
          // Explicitly use long timeout to avoid premature failures for large files.
          receiveTimeout: AppConfig.longRequestTimeout,
        ),
      );
      return resp.data ?? <int>[];
    } on DioException catch (e) {
      // For download endpoints we request bytes, so even JSON errors (e.g. HTTP 500 with {"detail": "..."} )
      // come back as raw bytes. Decode them to surface actionable messages to the UI.
      final dynamic data = e.response?.data;
      if (data is List<int> && data.isNotEmpty) {
        try {
          final String text = utf8.decode(data, allowMalformed: true).trim();
          if (text.isNotEmpty) {
            final dynamic parsed = jsonDecode(text);
            if (parsed is Map && parsed['detail'] is String) {
              throw Exception(parsed['detail'] as String);
            }
          }
        } catch (_) {
          // Fall through to rethrow original DioException
        }
      } else if (data is Map && data['detail'] is String) {
        throw Exception(data['detail'] as String);
      }
      rethrow;
    }
  }

  /// 批量下载：提交多个 task_id，返回 ZIP 文件字节
  Future<List<int>> batchDownload(
    List<String> taskIds,
    String fileType,
  ) async {
    final Dio dio = _buildAuthedDio(useLongTimeout: true);
    final Response<List<int>> resp = await dio.post<List<int>>(
      '/service/batch-download',
      data: <String, dynamic>{
        'task_ids': taskIds,
        'file_type': fileType,
      },
      options: Options(
        responseType: ResponseType.bytes,
        receiveTimeout: AppConfig.longRequestTimeout,
      ),
    );
    return resp.data ?? <int>[];
  }

  /// 轮询任务状态，直到完成或失败或超时
  /// onUpdate: 每次拉取到状态时回调；intervalSec: 轮询间隔；timeoutSec: 超时时间
  Future<Map<String, dynamic>> pollUntilDone(
    String taskId, {
    void Function(Map<String, dynamic> status)? onUpdate,
    int intervalSec = 2,
    int timeoutSec = 600,
  }) async {
    final started = DateTime.now();
    while (true) {
      final status = await getStatus(taskId);
      if (onUpdate != null) onUpdate(status);

      final s = (status['status'] ?? '').toString().toLowerCase();
      final done = s == 'completed' || s == 'failed' || s == 'cancelled';
      if (done) return status;

      if (DateTime.now().difference(started).inSeconds >= timeoutSec) {
        return <String, dynamic>{
          'task_id': taskId,
          'status': 'timeout',
          'message': 'Polling timeout',
        };
      }
      await Future.delayed(Duration(seconds: intervalSec));
    }
  }

  /// Get translation segments for a task.
  /// Backend returns 404 while translation is still processing (segments not written yet).
  /// Retries with backoff so that segments load once the task completes.
  Future<Map<String, dynamic>> getTranslationSegments(
    String taskId, {
    int maxRetries = 50,
    Duration retryDelay = const Duration(seconds: 1),
    bool forceRefresh = false,
  }) async {
    // If not forcing refresh, try cache or in-flight request first.
    if (!forceRefresh) {
      final Map<String, dynamic>? cached = _segmentsCache[taskId];
      if (cached != null) {
        return cached;
      }
      final Future<Map<String, dynamic>>? inFlight = _segmentsRequests[taskId];
      if (inFlight != null) {
        return inFlight;
      }
    } else {
      _segmentsCache.remove(taskId);
      _segmentsRequests.remove(taskId);
    }

    final Future<Map<String, dynamic>> future =
        _loadTranslationSegments(taskId, maxRetries, retryDelay);
    _segmentsRequests[taskId] = future;

    return future.then((Map<String, dynamic> data) {
      _segmentsCache[taskId] = data;
      _segmentsRequests.remove(taskId);
      return data;
    }).catchError((Object error, StackTrace stackTrace) {
      _segmentsRequests.remove(taskId);
      throw error;
    });
  }

  Future<Map<String, dynamic>> _loadTranslationSegments(
    String taskId,
    int maxRetries,
    Duration retryDelay,
  ) async {
    final Dio dio = _buildAuthedDio();

    int attempt = 0;
    while (true) {
      attempt += 1;
      try {
        final Response<dynamic> resp =
            await dio.get('/service/translation-segments/$taskId');
        return (resp.data as Map).cast<String, dynamic>();
      } on DioException catch (e, stackTrace) {
        final int? statusCode = e.response?.statusCode;
        final bool is404 = statusCode == 404;
        final bool retryableStatus =
            is404 || statusCode == 500 || statusCode == 503;

        // Special handling for 404: this is often "segments not ready yet" while task is still processing.
        // In that case we keep retrying without treating it as a hard error, even if attempt >= maxRetries.
        if (is404) {
          String taskStatus = '';
          try {
            final Map<String, dynamic> status = await getStatus(taskId);
            taskStatus = (status['status'] ?? '').toString().toLowerCase();
          } catch (_) {
            // Status check failed, fall through to generic handling below.
          }

          final bool done =
              taskStatus == 'completed' || taskStatus == 'failed' || taskStatus == 'cancelled';

          if (!done && taskStatus.isNotEmpty) {
            // Task is still processing, keep retrying.
            AppLogger.log(
              'TranslationService',
              '[SEGMENTS] getTranslationSegments 404 (segments not ready yet) for '
              'taskId=$taskId, attempt=$attempt, taskStatus=$taskStatus',
              level: LogLevel.warn,
            );
            await Future.delayed(retryDelay);
            continue;
          }

          if (done) {
            // Task is in a terminal state but segments still 404: this means
            // the task either has no segments (e.g. convert-phase task) or the
            // segments have been released. Stop retrying immediately.
            AppLogger.log(
              'TranslationService',
              '[SEGMENTS] getTranslationSegments 404 (task terminal, no segments) for '
              'taskId=$taskId, attempt=$attempt, taskStatus=$taskStatus',
              level: LogLevel.error,
            );
            throw Exception(
              'Task $taskId is in terminal state ($taskStatus) and has no segments',
            );
          }
        }

        // Only retry for temporary states and while attempts remain
        if (!retryableStatus || attempt >= maxRetries) {
          AppLogger.log(
            'TranslationService',
            '[SEGMENTS] getTranslationSegments failed after $attempt attempt(s) '
            'for taskId=$taskId, statusCode=$statusCode, error=$e\nStack trace: $stackTrace',
            level: LogLevel.error,
          );
          rethrow;
        }

        AppLogger.log(
          'TranslationService',
          '[SEGMENTS] getTranslationSegments retry $attempt/$maxRetries for '
          'taskId=$taskId, statusCode=$statusCode',
          level: LogLevel.warn,
        );
        await Future.delayed(retryDelay);
      }
    }
  }

  /// Update a translation segment
  Future<Map<String, dynamic>> updateTranslationSegment(
    String taskId,
    int segmentIndex, {
    String? targetText,
    bool? reviewed,
    String? reviewNotes,
    String? modifiedBy,
  }) async {
    final dio = _buildAuthedDio();
    final body = <String, dynamic>{};
    if (targetText != null) body['target_text'] = targetText;
    if (reviewed != null) body['reviewed'] = reviewed;
    if (reviewNotes != null) body['review_notes'] = reviewNotes;
    if (modifiedBy != null) body['modified_by'] = modifiedBy;

    final resp = await dio.post(
      '/service/translation-segments/$taskId/$segmentIndex/update',
      data: body,
    );
    // Invalidate cached segments for this task so next read gets fresh data.
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Download attachment file (e.g., glossary)
  Future<List<int>> downloadAttachment(String taskId, String identifier) async {
    final dio = _buildAuthedDio();
    final resp = await dio.get<List<int>>(
      '/service/attachment/$taskId/$identifier',
      options: Options(
        responseType: ResponseType.bytes,
        followRedirects: true,
      ),
    );
    return resp.data ?? <int>[];
  }

  /// Get source preview segments with pagination support
  /// [targetLang] Optional target language code for language match detection (e.g., 'zh', 'en'). If provided, will be used for language match exclusion detection.
  Future<Map<String, dynamic>> getSourcePreview(
    String taskId, {
    int offset = 0,
    int? limit,
    String? targetLang,
  }) async {
    // Use pagination config for default limit
    final int limitValue = limit ?? defaultPaginationLimit;
    final Dio dio = _buildAuthedDio();
    final Map<String, dynamic> queryParams = <String, dynamic>{
      'offset': offset,
      'limit': limitValue,
    };
    // CRITICAL: Pass target_lang for language match detection
    if (targetLang != null && targetLang.isNotEmpty) {
      queryParams['target_lang'] = targetLang;
    }

    // Dynamically extend receive timeout for large documents to avoid premature
    // preview failures on very big EPUB/PDF/HTML files.
    //
    // Strategy:
    // - Inspect task status to estimate document size (total_segments / file_size).
    // - Scale the timeout between requestTimeout and longRequestTimeout.
    Duration receiveTimeout = AppConfig.requestTimeout;
    try {
      final Map<String, dynamic> status = await getStatus(taskId);
      final Map<String, dynamic>? sourcePreview =
          status['source_preview'] as Map<String, dynamic>?;
      final Map<String, dynamic>? chunksCache =
          status['source_chunks_cache'] as Map<String, dynamic>?;

      final int? totalSegments = (chunksCache?['total_segments'] as int?) ??
          (sourcePreview?['total_segments'] as int?);
      final int? fileSizeBytes = status['file_size_bytes'] as int?;

      int weight = 1;
      if (totalSegments != null && totalSegments > 0) {
        // Scale based primarily on total segment count
        if (totalSegments > 200000) {
          weight = 5;
        } else if (totalSegments > 50000) {
          weight = 3;
        } else if (totalSegments > 10000) {
          weight = 2;
        }
      } else if (fileSizeBytes != null && fileSizeBytes > 0) {
        // Fallback: very rough scaling using file size
        if (fileSizeBytes > 200 * 1024 * 1024) {
          // > 200MB
          weight = 5;
        } else if (fileSizeBytes > 50 * 1024 * 1024) {
          // > 50MB
          weight = 3;
        } else if (fileSizeBytes > 10 * 1024 * 1024) {
          // > 10MB
          weight = 2;
        }
      }

      final int baseMs = AppConfig.requestTimeout.inMilliseconds;
      final int maxMs = AppConfig.longRequestTimeout.inMilliseconds;
      final int scaledMs = (baseMs * weight).clamp(baseMs, maxMs);
      receiveTimeout = Duration(milliseconds: scaledMs);
    } catch (_) {
      // If status inspection fails, keep default timeout.
    }

    final Response<dynamic> resp = await dio.get(
      '/service/source-preview/$taskId',
      queryParameters: queryParams,
      options: Options(
        receiveTimeout: receiveTimeout,
      ),
    );
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Get layout-based extract data for PDF files
  /// [chunkSize] Optional chunk size to use for regenerating chunks. If provided, chunks will be regenerated with this chunk size.
  /// [excludedSegmentIndices] List of segment indices to exclude. If empty list is passed, it will clear user-selected exclusions.
  /// [targetLang] Optional target language code for language match detection (e.g., 'zh', 'en'). If provided, will be used for language match exclusion detection.
  Future<Map<String, dynamic>> getLayoutExtract(
    String taskId, {
    int? chunkSize,
    List<int>? excludedSegmentIndices,
    String? targetLang,
  }) async {
    // CRITICAL: Log the targetLang parameter being passed to this method
    print(
        '[TranslationService] getLayoutExtract called: taskId=$taskId, targetLang=$targetLang (type: ${targetLang.runtimeType})',);

    final dio = _buildAuthedDio();
    final queryParams = <String, dynamic>{};
    if (chunkSize != null) {
      queryParams['chunk_size'] = chunkSize;
    }
    // CRITICAL: Always pass excluded_segment_indices parameter, even if empty
    // Empty list means "clear user-selected exclusions", None means "use existing exclusions"
    if (excludedSegmentIndices != null) {
      queryParams['excluded_segment_indices'] = excludedSegmentIndices.isEmpty
          ? ''
          : excludedSegmentIndices.join(',');
    }
    // CRITICAL: Pass target_lang for language match detection
    if (targetLang != null && targetLang.isNotEmpty) {
      queryParams['target_lang'] = targetLang;
      print(
          '[TranslationService] Adding target_lang=$targetLang to queryParams',);
    } else {
      print(
          '[TranslationService] targetLang is null or empty, not adding to queryParams',);
    }

    print(
        '[TranslationService] Final queryParams before API call: $queryParams',);

    final resp = await dio.get(
      '/service/layout-extract/$taskId',
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Re-split source
  Future<Map<String, dynamic>> resplitSource(
    String taskId, {
    int? chunkSize,
    List<int>? excludedSegmentIndices,
    String? sourceLang,
  }) async {
    final dio = _buildAuthedDio();
    final queryParams = <String, dynamic>{};
    if (chunkSize != null) {
      queryParams['chunk_size'] = chunkSize;
    }
    if (excludedSegmentIndices != null && excludedSegmentIndices.isNotEmpty) {
      queryParams['excluded_segment_indices'] =
          excludedSegmentIndices.join(',');
    }
    // Pass source language as OCR hint for MinerU markdown_based workflows.
    if (sourceLang != null &&
        sourceLang.isNotEmpty &&
        sourceLang != 'auto') {
      queryParams['ocr_language'] = sourceLang;
    }
    final resp = await dio.post(
      '/service/source-resplit/$taskId',
      queryParameters: queryParams.isNotEmpty ? queryParams : null,
    );
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Retranslate a single segment
  /// taskId: Task ID
  /// segmentIndex: Segment index to retranslate
  /// platformKey: AI platform key to use (optional, will use rotation if not provided)
  /// toLang: Target language code (optional, will use translation phase target_lang if not provided)
  Future<Map<String, dynamic>> retranslateSegment(
    String taskId,
    int segmentIndex, {
    String? platformKey,
    String? toLang,
    String? userPrompt,
  }) async {
    final dio = _buildAuthedDio();
    final body = <String, dynamic>{};
    if (platformKey != null) body['platform_key'] = platformKey;
    if (toLang != null && toLang.isNotEmpty) body['to_lang'] = toLang;
    if (userPrompt != null && userPrompt.isNotEmpty) body['user_prompt'] = userPrompt;

    final resp = await dio.post(
      '/service/translation-segments/$taskId/$segmentIndex/retranslate',
      data: body,
    );
    // Retranslation updates translation_segments; invalidate cache.
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Batch retranslate multiple segments together (enables chunk merging)
  /// taskId: Task ID
  /// segmentIndices: List of segment indices to retranslate
  /// platformKey: AI platform key to use (optional)
  /// toLang: Target language code (optional, will use translation phase target_lang if not provided)
  /// Returns a map with 'success', 'segments' (map of segment_index -> segment), and 'errors'
  Future<Map<String, dynamic>> retranslateSegmentsBatch(
    String taskId,
    List<int> segmentIndices, {
    String? platformKey,
    String? toLang,
    String? userPrompt,
  }) async {
    final dio = _buildAuthedDio(useLongTimeout: true);
    final body = <String, dynamic>{
      'segment_indices': segmentIndices,
    };
    if (platformKey != null) body['platform_key'] = platformKey;
    if (toLang != null && toLang.isNotEmpty) body['to_lang'] = toLang;
    if (userPrompt != null && userPrompt.isNotEmpty) body['user_prompt'] = userPrompt;

    final resp = await dio.post(
      '/service/translation-segments/$taskId/batch-retranslate',
      data: body,
    );
    // Batch retranslations also change translation_segments; invalidate cache.
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Mark a segment for retry
  Future<Map<String, dynamic>> markSegmentForRetry(
    String taskId,
    int segmentIndex,
  ) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post(
      '/service/translation-segments/$taskId/$segmentIndex/mark-retry',
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Unmark a segment for retry (clear retry flag)
  Future<Map<String, dynamic>> unmarkSegmentForRetry(
    String taskId,
    int segmentIndex,
  ) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post(
      '/service/translation-segments/$taskId/$segmentIndex/unmark-retry',
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Exclude a segment from translation (restore target_text to source_text)
  Future<Map<String, dynamic>> excludeSegment(
    String taskId,
    int segmentIndex,
  ) async {
    debugPrint(
        '[TranslationService] excludeSegment called: taskId=$taskId, segmentIndex=$segmentIndex',);
    final dio = _buildAuthedDio();
    try {
      final resp = await dio.post(
        '/service/translation-segments/$taskId/$segmentIndex/exclude',
      );
      debugPrint(
          '[TranslationService] excludeSegment success: taskId=$taskId, segmentIndex=$segmentIndex',);
      _segmentsCache.remove(taskId);
      _segmentsRequests.remove(taskId);
      return (resp.data as Map).cast<String, dynamic>();
    } catch (e) {
      debugPrint(
          '[TranslationService] excludeSegment failed: taskId=$taskId, segmentIndex=$segmentIndex, error=$e',);
      rethrow;
    }
  }

  /// Unexclude a segment from translation (clear exclusion flag)
  Future<Map<String, dynamic>> unexcludeSegment(
    String taskId,
    int segmentIndex,
  ) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post(
      '/service/translation-segments/$taskId/$segmentIndex/unexclude',
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Update exclusion reason for a segment
  Future<Map<String, dynamic>> updateExclusionReason(
    String taskId,
    int segmentIndex,
    String? newReason,
  ) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post(
      '/service/translation-segments/$taskId/$segmentIndex/exclusion_reason',
      data: <String, dynamic>{'new_reason': newReason},
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Update excluded segments for target language
  /// Re-detects language for all segments and updates excluded status
  /// This operation may take a long time for documents with many segments,
  /// so we use long timeout to prevent premature failures
  Future<Map<String, dynamic>> updateExcludedSegmentsForLanguage(
    String taskId,
    String targetLang, {
    bool autoExclude = false,
  }) async {
    // CRITICAL: Use long timeout for this operation as it may process many segments
    // This prevents network errors when processing large documents
    final dio = _buildAuthedDio(useLongTimeout: true);
    final resp = await dio.post(
      '/service/update-excluded-segments/$taskId',
      queryParameters: <String, dynamic>{
        'target_lang': targetLang,
        'auto_exclude': autoExclude,
      },
      options: Options(
        receiveTimeout: AppConfig.longRequestTimeout,
        sendTimeout: AppConfig.longRequestTimeout,
      ),
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Exclude all segments for the task (mark non-excluded as user exclusion).
  Future<Map<String, dynamic>> excludeAllSegments(String taskId) async {
    final dio = _buildAuthedDio(useLongTimeout: true);
    final resp = await dio.post(
      '/service/translation-segments/$taskId/exclude-all',
      options: Options(
        receiveTimeout: AppConfig.longRequestTimeout,
        sendTimeout: AppConfig.longRequestTimeout,
      ),
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Cancel only user/manual exclusions; other exclusion types are unchanged.
  Future<Map<String, dynamic>> cancelUserExclusion(String taskId) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post(
      '/service/translation-segments/$taskId/cancel-user-exclusion',
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Clear all exclusions except image segments. Only image segments remain excluded.
  Future<Map<String, dynamic>> clearAllExclusionsExceptImage(String taskId) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post(
      '/service/translation-segments/$taskId/clear-all-exclusions-except-image',
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// Clear a segment translation (set target text to empty string)
  Future<Map<String, dynamic>> clearSegment(
    String taskId,
    int segmentIndex,
  ) async {
    final dio = _buildAuthedDio();
    final resp = await dio.post(
      '/service/translation-segments/$taskId/$segmentIndex/clear',
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }

  /// LLM repair for segments that fail Pandoc DOCX fragment math (texmath / OMML path).
  Future<Map<String, dynamic>> repairDocxMathFragments(
    String taskId, {
    bool refreshCheckFirst = true,
    bool recheckAfter = true,
    int? maxSegments,
  }) async {
    final dio = _buildAuthedDio(useLongTimeout: true);
    final Map<String, dynamic> body = <String, dynamic>{
      'refresh_check_first': refreshCheckFirst,
      'recheck_after': recheckAfter,
    };
    if (maxSegments != null) {
      body['max_segments'] = maxSegments;
    }
    final resp = await dio.post(
      '/service/translation-segments/$taskId/repair-docx-math-fragments',
      data: body,
    );
    _segmentsCache.remove(taskId);
    _segmentsRequests.remove(taskId);
    return (resp.data as Map).cast<String, dynamic>();
  }
}
