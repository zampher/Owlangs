// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../app/app_router.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/providers/admin_permissions_provider.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/message_service.dart';

/// Lists backend translation tasks (immediate + queued + stashed) with polling.
class TranslationQueueScreen extends ConsumerStatefulWidget {
  const TranslationQueueScreen({super.key});

  @override
  ConsumerState<TranslationQueueScreen> createState() =>
      _TranslationQueueScreenState();
}

class _TranslationQueueScreenState extends ConsumerState<TranslationQueueScreen>
    with WidgetsBindingObserver {
  final TranslationService _svc = TranslationService();
  Timer? _pollTimer;
  List<Map<String, dynamic>> _tasks = <Map<String, dynamic>>[];
  bool _loading = false;
  String? _loadError;
  final Set<String> _selectedTaskIds = <String>{};
  bool _appInForeground = true;
  bool _wasActiveRoute = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Defer initial refresh to avoid calling ModalRoute.of(context) before build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _refresh();
    });
    _pollTimer = Timer.periodic(const Duration(seconds: 4), (_) => _refresh());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final bool nowForeground = state == AppLifecycleState.resumed;
    if (nowForeground && !_appInForeground) {
      // App came back to foreground — refresh immediately
      _refresh();
    }
    _appInForeground = nowForeground;
  }

  /// When task was evicted from memory, list API still exposes [stashed_file_types].
  /// Build relative download URLs so buttons appear even before GET /status returns stash payload.
  static void _mergeDownloadsFromStashMeta(Map<String, dynamic> row) {
    final dynamic existing = row['downloads'];
    final bool hasDownloads = existing is Map && existing.isNotEmpty;
    if (hasDownloads) {
      return;
    }
    final dynamic fts = row['stashed_file_types'];
    if (fts is! List<dynamic> || fts.isEmpty) {
      return;
    }
    final String tid = row['task_id']?.toString() ?? '';
    if (tid.isEmpty) {
      return;
    }
    final Map<String, dynamic> built = <String, dynamic>{};
    for (final dynamic ft in fts) {
      final String k = ft.toString();
      if (k.isEmpty) {
        continue;
      }
      built[k] = '/service/download/$tid/$k';
    }
    if (built.isNotEmpty) {
      row['downloads'] = built;
    }
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    // Skip refresh when app is in background or this screen is not the current route
    if (!_appInForeground) return;
    final route = ModalRoute.of(context);
    if (route != null && !route.isCurrent) return;
    setState(() {
      _loading = true;
      _loadError = null;
    });
    try {
      final Map<String, dynamic> listResp =
          await _svc.listTranslationTasks();
      final List<dynamic> raw =
          (listResp['tasks'] as List<dynamic>?) ?? <dynamic>[];
      final List<Map<String, dynamic>> enriched =
          await Future.wait(raw.map((t) async {
        final Map<String, dynamic> row =
            Map<String, dynamic>.from(t as Map<dynamic, dynamic>);
        _mergeDownloadsFromStashMeta(row);
        final String id = row['task_id']?.toString() ?? '';
        if (id.isEmpty) return row;
        try {
          final Map<String, dynamic> st = await _svc.getStatus(id);
          row['status'] = st['status'] ?? row['status'];
          row['progress'] = st['progress'] ?? row['progress'];
          // Ensure completed tasks always show 100% progress
          if (row['status']?.toString().toLowerCase() == 'completed') {
            row['progress'] = 100;
          }
          row['message'] = st['message'] ?? row['message'];
          // Merge translation stats and token usage for completed tasks
          if (st['translation_stats'] is Map) {
            row['translation_stats'] = Map<String, dynamic>.from(
              st['translation_stats'] as Map<dynamic, dynamic>,
            );
          }
          if (st['token_usage'] is Map) {
            row['token_usage'] = Map<String, dynamic>.from(
              st['token_usage'] as Map<dynamic, dynamic>,
            );
          }
          final dynamic sd = st['downloads'];
          if (sd is Map && sd.isNotEmpty) {
            row['downloads'] = Map<String, dynamic>.from(sd);
          } else {
            _mergeDownloadsFromStashMeta(row);
          }
        } catch (_) {
          // Keep list row; retain stash-derived download URLs when GET /status fails
          _mergeDownloadsFromStashMeta(row);
        }
        return row;
      }),);
      if (!mounted) return;
      setState(() {
        _tasks = enriched;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _loadError = e.toString();
      });
    }
  }

  /// Show "New queue task" dialog with three upload options (Single File / Folder / ZIP),
  /// same as the workspace screen's queued translation entry.
  void _showNewTaskDialog() {
    final l10n = AppLocalizations.of(context)!;
    showDialog<void>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text(l10n.translationQueueNewQueuedTask),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            ListTile(
              leading: const Icon(Icons.upload_file),
              title: Text(l10n.batchUploadSelectSingleFile),
              onTap: () {
                Navigator.of(ctx).pop();
                context.push(
                  '${AppRouter.batchUploadRoute}?source=single',
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.folder_open),
              title: Text(l10n.batchUploadSelectFolder),
              subtitle: Text(l10n.batchUploadFolderDescription),
              onTap: () {
                Navigator.of(ctx).pop();
                context.push('${AppRouter.batchUploadRoute}?source=folder');
              },
            ),
            ListTile(
              leading: const Icon(Icons.folder_zip_outlined),
              title: Text(l10n.batchUploadSelectZip),
              subtitle: Text(l10n.batchUploadZipDescription),
              onTap: () {
                Navigator.of(ctx).pop();
                context.push('${AppRouter.batchUploadRoute}?source=zip');
              },
            ),
          ],
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(l10n.commonCancel),
          ),
        ],
      ),
    );
  }

  Future<void> _cancel(String taskId) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final bool? confirm = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text(l10n.translationQueueCancelDialogTitle),
        content: Text(l10n.translationQueueCancelDialogMessage),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.translationQueueCancelDialogKeep),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.translationQueueCancelDialogConfirm),
          ),
        ],
      ),
    );
    if (confirm != true || !mounted) {
      return;
    }
    try {
      await _svc.cancelTask(taskId);
      if (!mounted) {
        return;
      }
      await _refresh();
    } catch (e) {
      if (mounted) {
        MessageService.showWarning(
          context,
          l10n.translationQueueActionFailed(e),
        );
      }
    }
  }

  Future<void> _release(String taskId) async {
    try {
      await _svc.releaseTask(taskId);
      await _refresh();
    } catch (e) {
      if (mounted) {
        MessageService.showWarning(
          context,
          AppLocalizations.of(context)!.translationQueueActionFailed(e),
        );
      }
    }
  }

  /// Backend exposes two Markdown downloads: `md` (default embed_images) and `md_zip` (?embed_images=false).
  static int _downloadFormatSortOrder(String formatKey) {
    const List<String> preferred = <String>[
      'docx',
      'html',
      'md',
      'md_zip',
      'pdf',
      'epub',
      'mobi',
      'txt',
      'json',
    ];
    final int idx = preferred.indexOf(formatKey);
    return idx >= 0 ? idx : 100 + formatKey.hashCode.abs() % 9000;
  }

  static String _fileExtensionForDownloadFormat(String formatKey) {
    if (formatKey == 'md_zip') {
      return 'zip';
    }
    return formatKey;
  }

  MimeType _mimeForExtension(String ext) {
    switch (ext.toLowerCase()) {
      case 'docx':
        return MimeType.microsoftWord;
      case 'pdf':
        return MimeType.pdf;
      case 'html':
      case 'htm':
      case 'md':
      case 'txt':
      case 'json':
      case 'zip':
      case 'xlsx':
      case 'xls':
      default:
        return MimeType.other;
    }
  }

  Future<void> _saveDownloadedBytes({
    required List<int> bytes,
    required String filename,
    required String ext,
  }) async {
    if (kIsWeb) {
      await FileSaver.instance.saveFile(
        name: filename.replaceAll(RegExp(r'\.[^.]+$'), ''),
        bytes: bytes is Uint8List ? bytes : Uint8List.fromList(bytes),
        ext: ext,
        mimeType: _mimeForExtension(ext),
      );
    } else {
      final String? path = await FilePicker.platform.saveFile(
        dialogTitle: 'Save file',
        fileName: filename,
        type: FileType.custom,
        allowedExtensions: <String>[ext],
      );
      if (path != null) {
        await File(path).writeAsBytes(bytes, flush: true);
      }
    }
  }

  Future<void> _download(
    String taskId,
    String fileType,
    String relativeUrl,
    String? originalFilename,
    bool isFormatConversion,
  ) async {
    try {
      final List<int> bytes = await _svc.downloadFile(relativeUrl);
      final String baseName = (originalFilename != null &&
              originalFilename.trim().isNotEmpty)
          ? _stripExtension(originalFilename.trim())
          : 'download';
      final String suffix = isFormatConversion ? 'converted' : 'translated';
      final String ext = _fileExtensionForDownloadFormat(fileType);
      final String filename = '${baseName}_$suffix.$ext';
      await _saveDownloadedBytes(
        bytes: bytes,
        filename: filename,
        ext: ext,
      );
      if (mounted) {
        final AppLocalizations l10n = AppLocalizations.of(context)!;
        MessageService.showInfo(
          context,
          '${l10n.translationQueueDownloads}: ${_downloadFormatButtonLabel(fileType, l10n)}',
        );
      }
    } catch (e) {
      if (mounted) {
        MessageService.showWarning(
          context,
          AppLocalizations.of(context)!.translationQueueActionFailed(e),
        );
      }
    }
  }

  String _stripExtension(String name) {
    final int dot = name.lastIndexOf('.');
    if (dot <= 0) return name;
    return name.substring(0, dot);
  }

  bool _canCancel(String? status) {
    final String s = (status ?? '').toLowerCase();
    return s == 'queued' ||
        s == 'processing' ||
        s == 'pending' ||
        s == 'running';
  }

  static double? _coerceUnix(v) {
    if (v == null) {
      return null;
    }
    final double? n =
        v is num ? v.toDouble() : double.tryParse(v.toString());
    if (n == null || n <= 0) {
      return null;
    }
    return n;
  }

  String _formatUnixOrDash(
    AppLocalizations l10n,
    BuildContext context,
    double? seconds,
  ) {
    if (seconds == null) {
      return l10n.translationQueueTimeUnknown;
    }
    final DateTime dt =
        DateTime.fromMillisecondsSinceEpoch((seconds * 1000).round());
    final Locale loc = Localizations.localeOf(context);
    return DateFormat.yMMMd(loc.toLanguageTag()).add_Hm().format(dt);
  }

  /// Compact time display: "05-22 14:00" or dash.
  String _formatCompactTime(BuildContext context, double? seconds) {
    if (seconds == null) return '-';
    final DateTime dt =
        DateTime.fromMillisecondsSinceEpoch((seconds * 1000).round());
    final Locale loc = Localizations.localeOf(context);
    return DateFormat.yMMMd(loc.toLanguageTag()).add_Hm().format(dt);
  }

  /// Map filename to a Material icon.
  static IconData _fileIcon(String name) {
    final ext = name.split('.').last.toLowerCase();
    switch (ext) {
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'docx':
      case 'doc':
        return Icons.description;
      case 'xlsx':
      case 'xls':
        return Icons.table_chart;
      case 'pptx':
      case 'ppt':
        return Icons.slideshow;
      case 'html':
      case 'htm':
        return Icons.language;
      case 'md':
        return Icons.article;
      case 'epub':
        return Icons.book;
      case 'mobi':
        return Icons.book_online;
      case 'txt':
        return Icons.text_snippet;
      case 'json':
        return Icons.data_object;
      case 'srt':
        return Icons.subtitles;
      default:
        return Icons.insert_drive_file;
    }
  }

  Future<void> _confirmClearQueue(
    BuildContext context,
    AppLocalizations l10n,
  ) async {
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text(l10n.translationQueueClearAllTitle),
        content: Text(l10n.translationQueueClearAllMessage),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.translationQueueClearAllCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.translationQueueClearAllConfirm),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) {
      return;
    }
    try {
      await _svc.adminClearTranslationQueue();
      if (!mounted) {
        return;
      }
      MessageService.showInfo(context, l10n.translationQueueClearAllSuccess);
      await _refresh();
    } catch (e) {
      if (!mounted) {
        return;
      }
      MessageService.showWarning(
        context,
        l10n.translationQueueClearAllFailed(e.toString()),
      );
    }
  }

  Future<void> _confirmClearMyQueue(
    BuildContext context,
    AppLocalizations l10n,
  ) async {
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text(l10n.translationQueueClearMyQueueTitle),
        content: Text(l10n.translationQueueClearMyQueueMessage),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.translationQueueClearMyQueueCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.translationQueueClearMyQueueConfirm),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) {
      return;
    }
    int success = 0;
    int fail = 0;
    for (final Map<String, dynamic> row in _tasks) {
      final String taskId = row['task_id']?.toString() ?? '';
      if (taskId.isEmpty) continue;
      try {
        await _svc.releaseTask(taskId);
        success++;
      } catch (_) {
        fail++;
      }
    }
    if (!mounted) {
      return;
    }
    if (fail == 0) {
      MessageService.showInfo(context, l10n.translationQueueClearMyQueueSuccess);
    } else {
      MessageService.showWarning(
        context,
        l10n.translationQueueClearMyQueueFailed('$fail/$success'),
      );
    }
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    // Detect transition from inactive → active route (e.g. popped back from a task)
    // and trigger an immediate refresh when the screen becomes visible again.
    final ModalRoute<dynamic>? currentRoute = ModalRoute.of(context);
    final bool isActive = currentRoute?.isCurrent ?? true;
    if (isActive && !_wasActiveRoute && mounted) {
      _wasActiveRoute = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _refresh();
      });
    } else if (!isActive) {
      _wasActiveRoute = false;
    }

    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final ThemeData theme = Theme.of(context);
    final ColorScheme cs = theme.colorScheme;
    final AsyncValue<bool> adminGate = ref.watch(isAppAdminUserProvider);

    return Scaffold(
      appBar: AppBar(
        title: _selectedTaskIds.isNotEmpty
            ? Text('${l10n.translationQueueTitle} · ${_selectedTaskIds.length} ${l10n.translationQueueSelected}')
            : Text(l10n.translationQueueTitle),
        leadingWidth: 220,
        leading: Row(
          children: <Widget>[
            IconButton(
              tooltip: l10n.homeNavHome,
              icon: const Icon(Icons.arrow_back),
              onPressed: () => context.go(AppRouter.homeRoute),
            ),
          ],
        ),
        actions: <Widget>[
          // New task first
          IconButton(
            tooltip: l10n.translationQueueNewQueuedTask,
            icon: const Icon(Icons.add, size: 20),
            onPressed: _showNewTaskDialog,
          ),
          adminGate.maybeWhen(
            data: (bool isAdmin) => isAdmin
                ? IconButton(
                    tooltip: l10n.translationQueueClearAllTooltip,
                    icon: const Icon(Icons.delete_sweep_outlined),
                    onPressed:
                        _loading ? null : () => _confirmClearQueue(context, l10n),
                  )
                : const SizedBox.shrink(),
            orElse: () => const SizedBox.shrink(),
          ),
          IconButton(
            tooltip: l10n.translationQueueClearMyQueueTooltip,
            icon: const Icon(Icons.cleaning_services_outlined),
            onPressed: _tasks.isEmpty || _loading
                ? null
                : () => _confirmClearMyQueue(context, l10n),
          ),
          IconButton(
            tooltip: l10n.translationQueueRefresh,
            icon: _loading
                ? SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: theme.colorScheme.onSurface,
                    ),
                  )
                : const Icon(Icons.refresh),
            onPressed: _loading ? null : _refresh,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 4),
              child: Text(
                '${l10n.translationQueueHint}\n'
                '${l10n.translationQueueCancelExitHint}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  height: 1.25,
                  fontSize: (theme.textTheme.bodySmall?.fontSize ?? 12) - 0.5,
                ),
              ),
            ),
            if (_loadError != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  l10n.translationQueueLoadFailed(_loadError!),
                  style: TextStyle(color: theme.colorScheme.error),
                ),
              ),
            // Multi-select toolbar
            if (_selectedTaskIds.isNotEmpty)
              _BatchDownloadBottomBar(
                taskIds: _selectedTaskIds.toList(growable: false),
                formatCounts: _computeFormatCounts(
                  _selectedTaskIds,
                  _tasks,
                ),
                onDownloadFormat: _batchDownload,
                onClear: () => _batchClear(_selectedTaskIds.toList(growable: false)),
              ),
            // Select-all row
            if (_tasks.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                child: Row(
                  children: <Widget>[
                    Checkbox(
                      value: _tasks.every((Map<String, dynamic> r) =>
                        _selectedTaskIds.contains(r['task_id']?.toString()))
                          ? true
                          : _selectedTaskIds.any((String id) =>
                              _tasks.any((Map<String, dynamic> r) =>
                                r['task_id']?.toString() == id))
                            ? null
                            : false,
                      tristate: true,
                      onChanged: (_) {
                        setState(() {
                          final bool allSelected = _tasks.every(
                            (Map<String, dynamic> r) =>
                              _selectedTaskIds.contains(r['task_id']?.toString()),
                          );
                          if (allSelected) {
                            _selectedTaskIds.clear();
                          } else {
                            _selectedTaskIds.addAll(
                              _tasks
                                .map((Map<String, dynamic> r) => r['task_id']?.toString() ?? '')
                                .where((String id) => id.isNotEmpty),
                            );
                          }
                        });
                      },
                      visualDensity: VisualDensity.compact,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    GestureDetector(
                      onTap: () {
                        setState(() {
                          final bool allSelected = _tasks.every(
                            (Map<String, dynamic> r) =>
                              _selectedTaskIds.contains(r['task_id']?.toString()),
                          );
                          if (allSelected) {
                            _selectedTaskIds.clear();
                          } else {
                            _selectedTaskIds.addAll(
                              _tasks
                                .map((Map<String, dynamic> r) => r['task_id']?.toString() ?? '')
                                .where((String id) => id.isNotEmpty),
                            );
                          }
                        });
                      },
                      child: Text(
                        _tasks.every((Map<String, dynamic> r) =>
                          _selectedTaskIds.contains(r['task_id']?.toString()))
                              ? l10n.translationQueueClearSelection
                              : l10n.translationQueueSelectMode,
                        style: theme.textTheme.labelMedium?.copyWith(
                          color: cs.onSurfaceVariant,
                        ),
                      ),
                    ),
                    const Spacer(),
                    Text(
                      '${_selectedTaskIds.length}/${_tasks.length}',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: cs.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            Expanded(
              child: _tasks.isEmpty && _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _tasks.isEmpty
                      ? Center(child: Text(l10n.translationQueueEmpty))
                      : ListView.builder(
                      padding: const EdgeInsets.only(bottom: 8),
                      itemCount: _tasks.length,
                      itemBuilder: (BuildContext context, int index) {
                        final Map<String, dynamic> row = _tasks[index];
                        final String taskId =
                            row['task_id']?.toString() ?? '';
                        final String name =
                            row['original_filename']?.toString() ??
                                taskId;
                        final String status =
                            row['status']?.toString() ?? '';
                        final dynamic progressRaw = row['progress'];
                        final int progress = progressRaw is num
                            ? progressRaw.toInt().clamp(0, 100)
                            : 0;
                        final String? mode =
                            row['execution_mode']?.toString();
                        final dynamic qp = row['queue_position'];
                        final Map<String, dynamic>? downloads = row['downloads']
                                is Map
                            ? Map<String, dynamic>.from(
                                row['downloads'] as Map<dynamic, dynamic>,
                              )
                            : null;
                        final List<MapEntry<String, dynamic>> downloadEntries =
                            downloads == null || downloads.isEmpty
                                ? <MapEntry<String, dynamic>>[]
                                : (downloads.entries.toList()
                                  ..sort(
                                    (MapEntry<String, dynamic> a,
                                            MapEntry<String, dynamic> b,) =>
                                        _downloadFormatSortOrder(a.key).compareTo(
                                          _downloadFormatSortOrder(b.key),
                                        ),
                                  ));

                        final bool inMemory = row['in_memory'] != false;

                        final String? ownerRaw =
                            row['owner_username']?.toString();
                        final String ownerShow =
                            (ownerRaw != null && ownerRaw.isNotEmpty)
                                ? ownerRaw
                                : l10n.translationQueueGuestUser;
                        final double? startedSec = _coerceUnix(
                              row['started_at'],
                            ) ??
                            _coerceUnix(row['queued_at']) ??
                            _coerceUnix(row['task_start_time']);
                        final double? completedSec = _coerceUnix(
                              row['completed_at'],
                            ) ??
                            _coerceUnix(row['task_end_time']);

                        return Card(
                          margin: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 3,
                          ),
                          child: InkWell(
                            onTap: () {
                              setState(() {
                                if (_selectedTaskIds.contains(taskId)) {
                                  _selectedTaskIds.remove(taskId);
                                } else {
                                  _selectedTaskIds.add(taskId);
                                }
                              });
                            },
                            borderRadius: BorderRadius.circular(12),
                            child: Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 10,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: <Widget>[
                                // ── Line 1: Filename + Status ──
                                Row(
                                  children: <Widget>[
                                    Checkbox(
                                        value: _selectedTaskIds.contains(taskId),
                                        onChanged: (_) {
                                          setState(() {
                                            if (_selectedTaskIds.contains(taskId)) {
                                              _selectedTaskIds.remove(taskId);
                                            } else {
                                              _selectedTaskIds.add(taskId);
                                            }
                                          });
                                        },
                                        visualDensity: VisualDensity.compact,
                                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                      ),
                                    Icon(
                                      _fileIcon(name),
                                      size: 18,
                                      color: cs.onSurfaceVariant,
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Tooltip(
                                        message: row['message']?.toString() ?? name,
                                        child: Text(
                                          name,
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: theme.textTheme.titleSmall?.copyWith(
                                            fontWeight: FontWeight.w600,
                                            height: 1.3,
                                          ),
                                        ),
                                      ),
                                    ),
                                    if (status == 'completed')
                                      _buildInlineStats(row, cs),
                                    const SizedBox(width: 8),
                                    _StatusBadge(status, progress, cs),
                                    if (row['is_format_conversion'] == true)
                                      Padding(
                                        padding: const EdgeInsets.only(left: 4),
                                        child: _TinyBadge(
                                          label: l10n.translationQueueTaskTypeConversion,
                                          cs: cs,
                                        ),
                                      )
                                    else
                                      Padding(
                                        padding: const EdgeInsets.only(left: 4),
                                        child: _TinyBadge(
                                          label: l10n.translationQueueTaskTypeTranslation,
                                          cs: cs,
                                        ),
                                      ),
                                    if (mode == 'queued')
                                      Padding(
                                        padding: const EdgeInsets.only(left: 4),
                                        child: _TinyBadge(
                                          label: l10n.translationQueueExecutionModeQueued,
                                          cs: cs,
                                        ),
                                      ),
                                    if (qp != null && qp is num && qp > 0)
                                      Padding(
                                        padding: const EdgeInsets.only(left: 4),
                                        child: _TinyBadge(
                                          label: '#${qp.toInt()}',
                                          cs: cs,
                                        ),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                // ── Line 2: Meta + Actions ──
                                Row(
                                  children: <Widget>[
                                    Expanded(
                                      child: Text(
                                        '$ownerShow · ${_formatCompactTime(context, startedSec)}',
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: theme.textTheme.bodySmall?.copyWith(
                                          color: cs.onSurfaceVariant,
                                          fontSize: 12,
                                        ),
                                      ),
                                    ),
                                    // Download format icons
                                    if (downloadEntries.isNotEmpty)
                                      ...downloadEntries.map(
                                        (e) => _DownloadFormatButton(
                                          taskId: taskId,
                                          name: name,
                                          ft: e.key,
                                          url: e.value.toString(),
                                          isFormatConversion: row['is_format_conversion'] == true,
                                          onDownload: _download,
                                        ),
                                      ),
                                    const SizedBox(width: 28),
                                    // Action buttons (fixed width: up to 3 buttons)
                                    SizedBox(
                                      width: 84,
                                      child: Row(
                                        mainAxisAlignment:
                                            MainAxisAlignment.end,
                                        children: <Widget>[
                                          // Cancel
                                          if (_canCancel(status) && inMemory)
                                            IconButton(
                                              icon: const Icon(
                                                  Icons.cancel_outlined,
                                                  size: 20),
                                              tooltip:
                                                  l10n.translationQueueCancel,
                                              visualDensity:
                                                  VisualDensity.compact,
                                              padding: const EdgeInsets.all(4),
                                              constraints: const BoxConstraints(
                                                  minWidth: 28, minHeight: 28),
                                              onPressed:
                                                  () => _cancel(taskId),
                                            ),
                                          // Edit
                                          if (status == 'completed' &&
                                              row['is_format_conversion'] !=
                                                  true &&
                                              inMemory)
                                            IconButton(
                                              icon: const Icon(
                                                  Icons.label_outlined,
                                                  size: 20),
                                              tooltip:
                                                  l10n.translationQueueEdit,
                                              visualDensity:
                                                  VisualDensity.compact,
                                              padding: const EdgeInsets.all(4),
                                              constraints: const BoxConstraints(
                                                  minWidth: 28, minHeight: 28),
                                              onPressed: () {
                                                final String? wf = row[
                                                        'workflow_type']
                                                    ?.toString();
                                                final String reeditUri =
                                                    '${AppRouter.translationRoute}'
                                                    '?execution_mode=queued'
                                                    '&reedit_task_id=$taskId'
                                                    '&reedit_workflow_type=${Uri.encodeComponent(wf ?? '')}'
                                                    '&reedit_file_name=${Uri.encodeComponent(name)}';
                                                context.push(reeditUri);
                                              },
                                            ),
                                          // View
                                          if (status == 'completed' && inMemory)
                                            IconButton(
                                              icon: const Icon(
                                                  Icons.chrome_reader_mode,
                                                  size: 20),
                                              tooltip:
                                                  l10n.translationQueueView,
                                              visualDensity:
                                                  VisualDensity.compact,
                                              padding: const EdgeInsets.all(4),
                                              constraints: const BoxConstraints(
                                                  minWidth: 28, minHeight: 28),
                                              onPressed: () {
                                                final String? wf = row[
                                                        'workflow_type']
                                                    ?.toString();
                                                final String viewUri =
                                                    '${AppRouter.translationRoute}'
                                                    '?execution_mode=queued'
                                                    '&reedit_task_id=$taskId'
                                                    '&reedit_workflow_type=${Uri.encodeComponent(wf ?? '')}'
                                                    '&reedit_file_name=${Uri.encodeComponent(name)}'
                                                    '&view_mode=clean';
                                                context.push(viewUri);
                                              },
                                            ),
                                          // Release
                                          IconButton(
                                            icon: const Icon(
                                                Icons.remove_circle_outline,
                                                size: 20),
                                            tooltip:
                                                l10n.translationQueueRelease,
                                            visualDensity:
                                                VisualDensity.compact,
                                            padding: const EdgeInsets.all(4),
                                            constraints: const BoxConstraints(
                                                minWidth: 28, minHeight: 28),
                                            onPressed:
                                                () => _release(taskId),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _batchDownload(List<String> taskIds, String fileType) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    try {
      final List<int> bytes = await _svc.batchDownload(taskIds, fileType);
      if (bytes.isEmpty) {
        if (mounted) {
          MessageService.showWarning(
            context,
            l10n.translationQueueBatchDownloadFailed('empty result'),
          );
        }
        return;
      }
      final String timestamp =
          DateTime.now().millisecondsSinceEpoch.toString();
      const String ext = 'zip';
      final String filename = 'batch_download_${fileType}_$timestamp.$ext';
      await _saveDownloadedBytes(
        bytes: bytes,
        filename: filename,
        ext: ext,
      );
      if (mounted) {
        MessageService.showInfo(
          context,
          l10n.translationQueueBatchDownloadSuccess(fileType),
        );
      }
    } catch (e) {
      if (mounted) {
        MessageService.showWarning(
          context,
          l10n.translationQueueBatchDownloadFailed(e.toString()),
        );
      }
    }
  }

  /// Count how many of the selected tasks support each download format.
  static Map<String, int> _computeFormatCounts(
    Set<String> selectedTaskIds,
    List<Map<String, dynamic>> tasks,
  ) {
    final Map<String, int> counts = <String, int>{};
    for (final Map<String, dynamic> row in tasks) {
      final String? tid = row['task_id']?.toString();
      if (tid == null || !selectedTaskIds.contains(tid)) continue;
      final dynamic d = row['downloads'];
      if (d is Map) {
        for (final String key in d.keys) {
          counts[key] = (counts[key] ?? 0) + 1;
        }
      }
    }
    return counts;
  }

  Future<void> _batchClear(List<String> taskIds) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final bool? confirm = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text(l10n.translationQueueClearAllTitle),
        content: Text(
          '${l10n.translationQueueClearAllMessage}\n\n'
          '${taskIds.length} ${l10n.translationQueueSelected}',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.translationQueueClearAllCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.translationQueueClearAllConfirm),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    int success = 0;
    for (final String taskId in taskIds) {
      try {
        await _svc.releaseTask(taskId);
        success++;
      } catch (_) {}
    }
    setState(() {
      _selectedTaskIds.clear();
    });
    if (mounted) {
      if (success == taskIds.length) {
        MessageService.showInfo(
          context,
          l10n.translationQueueClearAllSuccess,
        );
      } else {
        MessageService.showWarning(
          context,
          '$success/${taskIds.length} ${l10n.translationQueueClearAllFailed('')}',
        );
      }
    }
    await _refresh();
  }

  /// Build inline stats widget for Line 1 (filename row).
  Widget _buildInlineStats(
    Map<String, dynamic> row,
    ColorScheme cs,
  ) {
    final Map<String, dynamic>? stats =
        row['translation_stats'] as Map<String, dynamic>?;
    final Map<String, dynamic>? tokens =
        row['token_usage'] as Map<String, dynamic>?;

    final List<InlineSpan> spans = <InlineSpan>[];

    // Segments: success / failed / total with colors
    if (stats != null) {
      final int total = (stats['total_segments'] as num?)?.toInt() ?? 0;
      final int success = (stats['success_count'] as num?)?.toInt() ?? 0;
      final int failed = (stats['fail_count'] as num?)?.toInt() ?? 0;
      if (total > 0) {
        spans.add(const TextSpan(text: '  '));
        spans.add(WidgetSpan(
          child: Icon(Icons.segment, size: 12, color: cs.primary),
        ));
        spans.add(TextSpan(text: '$success', style: TextStyle(
          fontSize: 11, fontWeight: FontWeight.w600, color: cs.primary,
        )));
        if (failed > 0) {
          spans.add(TextSpan(text: '·$failed', style: TextStyle(
            fontSize: 11, fontWeight: FontWeight.w600, color: cs.error,
          )));
        }
        spans.add(TextSpan(text: '/$total', style: TextStyle(
          fontSize: 10, color: cs.onSurfaceVariant,
        )));
      }
    }

    // Token usage
    if (tokens != null) {
      final int input = (tokens['input_tokens'] as num?)?.toInt() ?? 0;
      final int output = (tokens['output_tokens'] as num?)?.toInt() ?? 0;
      if (input > 0 || output > 0) {
        spans.add(const TextSpan(text: '  '));
        spans.add(WidgetSpan(
          child: Icon(Icons.token, size: 12, color: cs.tertiary),
        ));
        spans.add(TextSpan(text: '${_fmtToken(input)}→${_fmtToken(output)}', style: TextStyle(
          fontSize: 10, color: cs.onSurfaceVariant,
        )));
      }
    }

    if (spans.isEmpty) return const SizedBox.shrink();

    // Build tooltip message with detailed labels
    final List<String> tooltipParts = <String>[];
    if (stats != null) {
      final int total = (stats['total_segments'] as num?)?.toInt() ?? 0;
      final int success = (stats['success_count'] as num?)?.toInt() ?? 0;
      final int failed = (stats['fail_count'] as num?)?.toInt() ?? 0;
      if (total > 0) {
        final String failedPart = failed > 0 ? ', $failed failed' : '';
        tooltipParts.add('Segments: $success succeeded${failedPart}, $total total');
      }
    }
    if (tokens != null) {
      final int input = (tokens['input_tokens'] as num?)?.toInt() ?? 0;
      final int output = (tokens['output_tokens'] as num?)?.toInt() ?? 0;
      if (input > 0) tooltipParts.add('Input tokens:  $input');
      if (output > 0) tooltipParts.add('Output tokens: $output');
    }

    return Tooltip(
      message: tooltipParts.join('\n'),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      textStyle: TextStyle(
        fontSize: 12,
        color: cs.onInverseSurface,
        height: 1.4,
      ),
      child: RichText(
        text: TextSpan(children: spans),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }

  String _fmtToken(int count) {
    if (count >= 1000000) return '${(count / 1000000).toStringAsFixed(1)}M';
    if (count >= 1000) return '${(count / 1000).toStringAsFixed(1)}K';
    return count.toString();
  }
}

// ─── Batch download bottom bar ───────────────────────────────────────────────

class _BatchDownloadBottomBar extends StatelessWidget {
  final List<String> taskIds;
  final Map<String, int> formatCounts;
  final Future<void> Function(List<String>, String) onDownloadFormat;
  final VoidCallback? onClear;

  const _BatchDownloadBottomBar({
    required this.taskIds,
    required this.formatCounts,
    required this.onDownloadFormat,
    this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final ThemeData theme = Theme.of(context);
    final ColorScheme cs = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        border: Border(top: BorderSide(color: cs.outlineVariant, width: 0.5)),
      ),
      child: Row(
        children: <Widget>[
          // Selection count
          Text(
            '${taskIds.length} ${l10n.translationQueueSelected}',
            style: theme.textTheme.labelMedium?.copyWith(
              color: cs.onSurfaceVariant,
            ),
          ),
          const SizedBox(width: 8),
          // "Download" label
          Text(
            l10n.translationQueueDownloads,
            style: theme.textTheme.labelSmall?.copyWith(
              color: cs.onSurfaceVariant,
            ),
          ),
          const SizedBox(width: 4),
          // Format chips
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: _buildFormatChips(l10n),
              ),
            ),
          ),
          // Clear / delete button
          if (onClear != null)
            IconButton(
              icon: Icon(Icons.delete_outline, size: 20, color: cs.error),
              tooltip: l10n.translationQueueClearSelection,
              visualDensity: VisualDensity.compact,
              constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              onPressed: onClear,
            ),
        ],
      ),
    );
  }

  List<Widget> _buildFormatChips(AppLocalizations l10n) {
    const List<(String, IconData)> formats = <(String, IconData)>[
      ('docx', Icons.description),
      ('html', Icons.language),
      ('md', Icons.article),
      ('md_zip', Icons.folder_zip_outlined),
      ('pdf', Icons.picture_as_pdf),
      ('txt', Icons.text_snippet),
    ];
    return formats.map((f) {
      final String ft = f.$1;
      final int count = formatCounts[ft] ?? 0;
      if (count == 0) return const SizedBox.shrink();
      return Padding(
        padding: const EdgeInsets.only(right: 6),
        child: ActionChip(
          avatar: Icon(f.$2, size: 16),
          label: Text(
            '${_downloadFormatButtonLabel(ft, l10n)} ($count)',
            style: const TextStyle(fontSize: 12),
          ),
          onPressed: () => onDownloadFormat(taskIds, ft),
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          padding: const EdgeInsets.symmetric(horizontal: 4),
        ),
      );
    }).toList();
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;
  final int progress;
  final ColorScheme cs;

  const _StatusBadge(this.status, this.progress, this.cs);

  Color get _dotColor {
    switch (status.toLowerCase()) {
      case 'completed':
        return Colors.green;
      case 'processing':
      case 'running':
        return Colors.orange;
      case 'queued':
      case 'pending':
        return cs.primary;
      case 'failed':
      case 'error':
        return Colors.red;
      default:
        return cs.onSurfaceVariant;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: _dotColor.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: _dotColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 5),
          Text(
            '$status · $progress%',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: _dotColor,
              height: 1.15,
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Ultra-compact badge (e.g. "Q", "#3") ───────────────────────────────────

class _TinyBadge extends StatelessWidget {
  final String label;
  final ColorScheme cs;

  const _TinyBadge({required this.label, required this.cs});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          color: cs.onSurfaceVariant,
          height: 1.15,
        ),
      ),
    );
  }
}

// ─── Download popup menu button ──────────────────────────────────────────────

/// Map download format key to a localized button label.
String _downloadFormatButtonLabel(String formatKey, AppLocalizations l10n) {
  switch (formatKey) {
    case 'md':
      return l10n.translationQueueDownloadMdEmbedded;
    case 'md_zip':
      return l10n.translationQueueDownloadMdZip;
    default:
      return formatKey.toUpperCase();
  }
}

/// Map download format key to a Material icon.
IconData _downloadFormatIcon(String ft) {
  switch (ft) {
    case 'pdf':
      return Icons.picture_as_pdf;
    case 'docx':
    case 'doc':
      return Icons.description;
    case 'xlsx':
    case 'xls':
      return Icons.table_chart;
    case 'pptx':
    case 'ppt':
      return Icons.slideshow;
    case 'html':
    case 'htm':
      return Icons.language;
    case 'md':
      return Icons.article;
    case 'md_zip':
      return Icons.folder_zip_outlined;
    case 'epub':
      return Icons.book;
    case 'mobi':
      return Icons.book_online;
    case 'txt':
      return Icons.text_snippet;
    case 'json':
      return Icons.data_object;
    case 'srt':
      return Icons.subtitles;
    default:
      return Icons.download;
  }
}

/// An icon button for a single download format.
class _DownloadFormatButton extends StatelessWidget {
  final String taskId;
  final String name;
  final String ft;
  final String url;
  final bool isFormatConversion;
  final Future<void> Function(String, String, String, String, bool) onDownload;

  const _DownloadFormatButton({
    required this.taskId,
    required this.name,
    required this.ft,
    required this.url,
    required this.isFormatConversion,
    required this.onDownload,
  });

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    return IconButton(
      icon: Icon(_downloadFormatIcon(ft), size: 20),
      tooltip: _downloadFormatButtonLabel(ft, l10n),
      visualDensity: VisualDensity.compact,
      padding: const EdgeInsets.all(4),
      constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
      onPressed: url.isNotEmpty
          ? () => onDownload(taskId, ft, url, name, isFormatConversion)
          : null,
    );
  }
}
