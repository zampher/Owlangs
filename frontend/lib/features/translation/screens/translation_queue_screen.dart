// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../app/app_router.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/providers/admin_permissions_provider.dart';
import '../../../shared/providers/settings_provider.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/utils/download_filename_builder.dart';

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
  List<Map<String, dynamic>> _batches = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _ungroupedTasks = <Map<String, dynamic>>[];
  final Set<String> _collapsedBatchIds = <String>{};
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

  Future<Map<String, dynamic>> _enrichTaskRow(Map<String, dynamic> row) async {
        _mergeDownloadsFromStashMeta(row);
        final String id = row['task_id']?.toString() ?? '';
    if (id.isEmpty) {
      return row;
    }
        try {
          final Map<String, dynamic> st = await _svc.getStatus(id);
          row['status'] = st['status'] ?? row['status'];
          row['progress'] = st['progress'] ?? row['progress'];
          if (row['status']?.toString().toLowerCase() == 'completed') {
            row['progress'] = 100;
          }
          row['message'] = st['message'] ?? row['message'];
          row['message_level'] = st['message_level'] ?? row['message_level'];
          row['error'] = st['error'] ?? row['error'];
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
          _mergeDownloadsFromStashMeta(row);
        }
        return row;
  }

  Future<List<Map<String, dynamic>>> _enrichTasks(
    Iterable<Map<String, dynamic>> raw,
  ) async {
    return Future.wait(raw.map(_enrichTaskRow));
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
      final Map<String, dynamic> batchResp =
          await _svc.listUploadBatches();
      final List<dynamic> batchesRaw =
          (batchResp['batches'] as List<dynamic>?) ?? <dynamic>[];
      final List<dynamic> ungroupedRaw =
          (batchResp['ungrouped_tasks'] as List<dynamic>?) ?? <dynamic>[];

      final List<Map<String, dynamic>> allRaw = <Map<String, dynamic>>[];
      for (final dynamic batch in batchesRaw) {
        if (batch is! Map) {
          continue;
        }
        final List<dynamic> nested =
            (batch['tasks'] as List<dynamic>?) ?? <dynamic>[];
        for (final dynamic task in nested) {
          if (task is Map) {
            allRaw.add(Map<String, dynamic>.from(task));
          }
        }
      }
      for (final dynamic task in ungroupedRaw) {
        if (task is Map) {
          allRaw.add(Map<String, dynamic>.from(task));
        }
      }

      final Set<String> seenIds = <String>{};
      final List<Map<String, dynamic>> uniqueRaw = <Map<String, dynamic>>[];
      for (final Map<String, dynamic> row in allRaw) {
        final String id = row['task_id']?.toString() ?? '';
        if (id.isEmpty || seenIds.contains(id)) {
          continue;
        }
        seenIds.add(id);
        uniqueRaw.add(row);
      }

      final List<Map<String, dynamic>> enriched =
          await _enrichTasks(uniqueRaw);
      final Map<String, Map<String, dynamic>> enrichedById =
          <String, Map<String, dynamic>>{
        for (final Map<String, dynamic> row in enriched)
          row['task_id']?.toString() ?? '': row,
      };

      final List<Map<String, dynamic>> batches = batchesRaw
          .whereType<Map<dynamic, dynamic>>()
          .map((Map<dynamic, dynamic> batch) {
        final Map<String, dynamic> copy =
            Map<String, dynamic>.from(batch);
        final List<dynamic> taskIds =
            (copy['task_ids'] as List<dynamic>?) ?? <dynamic>[];
        final List<Map<String, dynamic>> tasks = taskIds
            .map((dynamic tid) => enrichedById[tid.toString()])
            .whereType<Map<String, dynamic>>()
            .toList();
        copy['tasks'] = tasks;
        int completed = 0;
        int failed = 0;
        for (final Map<String, dynamic> row in tasks) {
          final String status =
              row['status']?.toString().toLowerCase() ?? '';
          if (status == 'completed') {
            completed++;
          } else if (status == 'failed' || status == 'cancelled') {
            failed++;
          }
        }
        copy['task_count'] = tasks.length;
        copy['completed_count'] = completed;
        copy['failed_count'] = failed;
        return copy;
      }).toList();

      final List<Map<String, dynamic>> ungrouped = ungroupedRaw
          .whereType<Map<dynamic, dynamic>>()
          .map((Map<dynamic, dynamic> row) =>
              enrichedById[row['task_id']?.toString() ?? ''] ??
              Map<String, dynamic>.from(row),)
          .where((Map<String, dynamic> row) =>
              (row['task_id']?.toString() ?? '').isNotEmpty,)
          .toList();

      if (!mounted) return;
      setState(() {
        _batches = batches;
        _ungroupedTasks = ungrouped;
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

  void _toggleBatchExpanded(String batchId) {
    setState(() {
      if (_collapsedBatchIds.contains(batchId)) {
        _collapsedBatchIds.remove(batchId);
      } else {
        _collapsedBatchIds.add(batchId);
      }
    });
  }

  void _toggleBatchSelection(Set<String> taskIds) {
    setState(() {
      final bool allSelected =
          taskIds.every(_selectedTaskIds.contains);
      if (allSelected) {
        _selectedTaskIds.removeAll(taskIds);
      } else {
        _selectedTaskIds.addAll(taskIds);
      }
    });
  }

  Future<void> _confirmDeleteBatch(String batchId, String label) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final bool? ok = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text(l10n.translationQueueBatchDeleteTitle),
        content: Text(
          '${l10n.translationQueueBatchDeleteMessage}\n\n$label',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(l10n.commonCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(l10n.translationQueueBatchDelete),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) {
      return;
    }
    try {
      await _svc.deleteUploadBatch(batchId);
      if (!mounted) {
        return;
      }
      setState(() {
        for (final Map<String, dynamic> batch in _batches) {
          if (batch['batch_id']?.toString() != batchId) {
            continue;
          }
          final List<dynamic> tasks =
              (batch['tasks'] as List<dynamic>?) ?? <dynamic>[];
          for (final dynamic task in tasks) {
            if (task is Map) {
              _selectedTaskIds.remove(task['task_id']?.toString());
            }
          }
          break;
        }
        _collapsedBatchIds.remove(batchId);
      });
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

  Future<void> _downloadBatch(String batchId, String fileType) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    try {
      final List<int> bytes =
          await _svc.batchDownloadByBatch(batchId, fileType);
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
      final String filename =
          'batch_${batchId}_${fileType}_$timestamp.$ext';
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

  Future<void> _showBatchDownloadMenu(
    String batchId,
    List<Map<String, dynamic>> tasks,
  ) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final List<Map<String, dynamic>> completedTasks = tasks
        .where(
          (Map<String, dynamic> row) =>
              row['status']?.toString().toLowerCase() == 'completed',
        )
        .toList();
    final Map<String, int> formatCounts = _computeFormatCounts(
      completedTasks
          .map((Map<String, dynamic> row) => row['task_id']?.toString() ?? '')
          .where((String id) => id.isNotEmpty)
          .toSet(),
      completedTasks,
    );
    if (formatCounts.isEmpty) {
      MessageService.showWarning(
        context,
        l10n.translationQueueBatchDownloadFailed('no completed downloads'),
      );
      return;
    }

    const List<(String, IconData)> formats = <(String, IconData)>[
      ('docx', Icons.description),
      ('html', Icons.language),
      ('md', Icons.article),
      ('md_zip', Icons.folder_zip_outlined),
      ('pdf', Icons.picture_as_pdf),
      ('pdf_reflow', Icons.picture_as_pdf_outlined),
      ('txt', Icons.text_snippet),
    ];

    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (BuildContext ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Text(
                  l10n.translationQueueBatchDownload,
                  style: Theme.of(ctx).textTheme.titleSmall,
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: formats
                      .where((f) => (formatCounts[f.$1] ?? 0) > 0)
                      .map(
                        (f) => ActionChip(
                          avatar: Icon(f.$2, size: 16),
                          label: Text(
                            '${_downloadFormatButtonLabel(f.$1, l10n)} '
                            '(${formatCounts[f.$1]})',
                          ),
                          onPressed: () {
                            Navigator.of(ctx).pop();
                            _downloadBatch(batchId, f.$1);
                          },
                        ),
                      )
                      .toList(),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildGroupedTaskList(
    AppLocalizations l10n,
    ThemeData theme,
    ColorScheme cs,
  ) {
    if (_tasks.isEmpty && _loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_tasks.isEmpty) {
      return Center(child: Text(l10n.translationQueueEmpty));
    }

    final List<Widget> children = <Widget>[];
    for (final Map<String, dynamic> batch in _batches) {
      children.add(_buildBatchSection(batch, l10n, theme, cs));
    }
    if (_ungroupedTasks.isNotEmpty) {
      children.add(
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Text(
            l10n.translationQueueUngroupedSection,
            style: theme.textTheme.titleSmall?.copyWith(
              color: cs.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      );
      for (final Map<String, dynamic> row in _ungroupedTasks) {
        children.add(_buildTaskCard(row, l10n, theme, cs));
      }
    }

    // Tooltip + OverlayPortal hit-tests fail while the list scrolls; keep
    // list rows free of Tooltip widgets (show status text inline instead).
    return ListView(
      padding: const EdgeInsets.only(bottom: 8),
      children: children,
    );
  }

  /// Progress/status line for in-flight tasks (replaces hover Tooltip on filename).
  String? _inlineTaskStatusMessage(Map<String, dynamic> row) {
    final String status = (row['status']?.toString() ?? '').toLowerCase();
    if (status == 'failed' ||
        status == 'completed' ||
        status == 'cancelled') {
      return null;
    }
    final String message = row['message']?.toString().trim() ?? '';
    if (message.isEmpty) {
      return null;
    }
    final String name = row['original_filename']?.toString() ?? '';
    if (message == name) {
      return null;
    }
    return message;
  }

  Widget _buildBatchSection(
    Map<String, dynamic> batch,
    AppLocalizations l10n,
    ThemeData theme,
    ColorScheme cs,
  ) {
    final String batchId = batch['batch_id']?.toString() ?? '';
    final String label = batch['label']?.toString() ?? batchId;
    final List<Map<String, dynamic>> tasks =
        (batch['tasks'] as List<dynamic>?)
                ?.whereType<Map<dynamic, dynamic>>()
                .map(Map<String, dynamic>.from)
                .toList() ??
            <Map<String, dynamic>>[];
    final int completed =
        (batch['completed_count'] as num?)?.toInt() ?? 0;
    final int total = (batch['task_count'] as num?)?.toInt() ?? tasks.length;
    final bool expanded = !_collapsedBatchIds.contains(batchId);
    final Set<String> taskIds = tasks
        .map((Map<String, dynamic> row) => row['task_id']?.toString() ?? '')
        .where((String id) => id.isNotEmpty)
        .toSet();
    final bool allSelected = taskIds.isNotEmpty &&
        taskIds.every(_selectedTaskIds.contains);
    final bool someSelected =
        taskIds.any(_selectedTaskIds.contains) && !allSelected;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Material(
            color: cs.surfaceContainerHighest.withValues(alpha: 0.35),
            child: InkWell(
              onTap: () => _toggleBatchExpanded(batchId),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(4, 6, 8, 6),
                child: Row(
                  children: <Widget>[
                    Checkbox(
                      value: allSelected
                          ? true
                          : (someSelected ? null : false),
                      tristate: true,
                      onChanged: (_) => _toggleBatchSelection(taskIds),
                      visualDensity: VisualDensity.compact,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            label,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          Text(
                            l10n.translationQueueBatchProgress(
                              completed,
                              total,
                            ),
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: cs.onSurfaceVariant,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                    _QueueListIconButton(
                      icon: Icons.download_outlined,
                      semanticLabel: l10n.translationQueueBatchDownload,
                      minSize: 32,
                      onPressed: completed == 0
                          ? null
                          : () => _showBatchDownloadMenu(batchId, tasks),
                    ),
                    _QueueListIconButton(
                      icon: Icons.delete_outline,
                      semanticLabel: l10n.translationQueueBatchDelete,
                      iconColor: cs.error,
                      minSize: 32,
                      onPressed: () => _confirmDeleteBatch(batchId, label),
                    ),
                    Icon(
                      expanded ? Icons.expand_less : Icons.expand_more,
                      color: cs.onSurfaceVariant,
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (expanded)
            ...tasks.map(
              (Map<String, dynamic> row) =>
                  _buildTaskCard(row, l10n, theme, cs, nested: true),
            ),
        ],
      ),
    );
  }

  Widget _buildTaskCard(
    Map<String, dynamic> row,
    AppLocalizations l10n,
    ThemeData theme,
    ColorScheme cs, {
    bool nested = false,
  }) {
    final String taskId = row['task_id']?.toString() ?? '';
    final String name =
        row['original_filename']?.toString() ?? taskId;
    final String relativePath =
        row['original_relative_path']?.toString() ?? '';
    final String status = row['status']?.toString() ?? '';
    final dynamic progressRaw = row['progress'];
    final int progress = progressRaw is num
        ? progressRaw.toInt().clamp(0, 100)
        : 0;
    final String? mode = row['execution_mode']?.toString();
    final dynamic qp = row['queue_position'];
    final Map<String, dynamic>? downloads = row['downloads'] is Map
        ? Map<String, dynamic>.from(
            row['downloads'] as Map<dynamic, dynamic>,
          )
        : null;
    final List<MapEntry<String, dynamic>> downloadEntries =
        downloads == null || downloads.isEmpty
            ? <MapEntry<String, dynamic>>[]
            : (downloads.entries.toList()
              ..sort(
                (MapEntry<String, dynamic> a, MapEntry<String, dynamic> b) =>
                    _downloadFormatSortOrder(a.key)
                        .compareTo(_downloadFormatSortOrder(b.key)),
              ));

    final bool inMemory = row['in_memory'] != false;
    final String? ownerRaw = row['owner_username']?.toString();
    final String ownerShow = (ownerRaw != null && ownerRaw.isNotEmpty)
        ? ownerRaw
        : l10n.translationQueueGuestUser;
    final double? startedSec = _coerceUnix(row['started_at']) ??
        _coerceUnix(row['queued_at']) ??
        _coerceUnix(row['task_start_time']);

    return Card(
      margin: EdgeInsets.fromLTRB(nested ? 20 : 12, nested ? 2 : 3, 12, nested ? 2 : 3),
      elevation: nested ? 0 : null,
      color: nested ? cs.surfaceContainerLowest : null,
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
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
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
                  Icon(_fileIcon(name), size: 18, color: cs.onSurfaceVariant),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        if (relativePath.isNotEmpty)
                          Text(
                            relativePath,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 10,
                              color: cs.onSurfaceVariant,
                              height: 1.2,
                            ),
                          ),
                        Text(
                          name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            height: 1.3,
                          ),
                        ),
                        if (_inlineTaskStatusMessage(row) case final String statusMsg)
                          Text(
                            statusMsg,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: cs.primary,
                              fontSize: 11,
                              height: 1.2,
                            ),
                          ),
                      ],
                    ),
                  ),
                  if (status == 'completed') _buildInlineStats(row, cs),
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
              if (status.toLowerCase() == 'failed')
                _buildFailedMessage(row, cs, theme),
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
                  if (downloadEntries.isNotEmpty)
                    ...downloadEntries.map(
                      (MapEntry<String, dynamic> e) => _DownloadFormatButton(
                        taskId: taskId,
                        name: name,
                        ft: e.key,
                        url: e.value.toString(),
                        isFormatConversion:
                            row['is_format_conversion'] == true,
                        onDownload: _download,
                      ),
                    ),
                  const SizedBox(width: 28),
                  SizedBox(
                    width: 84,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: <Widget>[
                        if (_canCancel(status) && inMemory)
                          _QueueListIconButton(
                            icon: Icons.cancel_outlined,
                            semanticLabel: l10n.translationQueueCancel,
                            onPressed: () => _cancel(taskId),
                          ),
                        if (status == 'completed' &&
                            row['is_format_conversion'] != true &&
                            inMemory)
                          _QueueListIconButton(
                            icon: Icons.label_outlined,
                            semanticLabel: l10n.translationQueueEdit,
                            onPressed: () {
                              final String? wf =
                                  row['workflow_type']?.toString();
                              final String reeditUri =
                                  '${AppRouter.translationRoute}'
                                  '?execution_mode=queued'
                                  '&reedit_task_id=$taskId'
                                  '&reedit_workflow_type=${Uri.encodeComponent(wf ?? '')}'
                                  '&reedit_file_name=${Uri.encodeComponent(name)}';
                              context.push(reeditUri);
                            },
                          ),
                        if (status == 'completed' && inMemory)
                          _QueueListIconButton(
                            icon: Icons.chrome_reader_mode,
                            semanticLabel: l10n.translationQueueView,
                            onPressed: () {
                              final String? wf =
                                  row['workflow_type']?.toString();
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
                        _QueueListIconButton(
                          icon: Icons.remove_circle_outline,
                          semanticLabel: l10n.translationQueueRelease,
                          onPressed: () => _release(taskId),
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
  }

  /// Backend exposes two Markdown downloads: `md` (default embed_images) and `md_zip` (?embed_images=false).
  static int _downloadFormatSortOrder(String formatKey) {
    if (_isOriginalImageDownloadFormat(formatKey)) {
      return -1;
    }
    const List<String> preferred = <String>[
      'docx',
      'html',
      'md',
      'md_zip',
      'pdf',
      'pdf_reflow',
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
    if (formatKey == 'pdf_reflow') {
      return 'pdf';
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
      final String suffix = isFormatConversion
          ? ref.read(globalSettingsProvider).convertOutputSuffix
          : ref.read(globalSettingsProvider).translateOutputSuffix;
      final String ext = _fileExtensionForDownloadFormat(fileType);
      final String filename = buildDownloadFilename(
        originalName: baseName,
        extension: ext,
        suffix: suffix,
      );
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
          // Import button
          TextButton.icon(
            onPressed: _showNewTaskDialog,
            icon: const Icon(Icons.add, size: 18),
            label: Text(l10n.translationQueueImport,
              style: const TextStyle(fontSize: 13),
            ),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              visualDensity: VisualDensity.compact,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
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
              Container(
                margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: theme.colorScheme.errorContainer.withOpacity(0.35),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: theme.colorScheme.error.withOpacity(0.3),
                  ),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.error_outline,
                        color: theme.colorScheme.error, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        l10n.translationQueueLoadFailed(_loadError!),
                        style: TextStyle(
                          color: theme.colorScheme.error,
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ),
                    GestureDetector(
                      onTap: () => setState(() => _loadError = null),
                      child: Icon(Icons.close,
                          color: theme.colorScheme.error.withOpacity(0.6),
                          size: 16),
                    ),
                  ],
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
                onDownloadAll: _batchDownloadAll,
                onClear: () => _batchClear(_selectedTaskIds.toList(growable: false)),
                onSelectFormats: () => _showSelectFormatsDialog(
                  _selectedTaskIds.toList(growable: false),
                ),
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
              child: _buildGroupedTaskList(l10n, theme, cs),
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

  Future<void> _batchDownloadAll(List<String> taskIds) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    try {
      // Collect all download entries from selected tasks
      final List<_TaskDownloadEntry> entries = <_TaskDownloadEntry>[];
      for (final Map<String, dynamic> row in _tasks) {
        final String? tid = row['task_id']?.toString();
        if (tid == null || !taskIds.contains(tid)) continue;
        final String name =
            row['original_filename']?.toString() ?? tid;
        final String baseName = name.contains('.')
            ? name.substring(0, name.lastIndexOf('.'))
            : name;
        final dynamic d = row['downloads'];
        if (d is! Map) continue;
        for (final MapEntry<dynamic, dynamic> e in d.entries) {
          final String ft = e.key.toString();
          // Skip non-file entries
          if (ft.isEmpty || e.value == null) continue;
          entries.add(_TaskDownloadEntry(
            taskId: tid,
            baseName: baseName,
            format: ft,
            url: e.value.toString(),
          ));
        }
      }

      if (entries.isEmpty) {
        if (mounted) {
          MessageService.showWarning(context, 'No downloads available');
        }
        return;
      }

      // Download each file and pack into a single ZIP, preserving relative paths
      final Archive archive = Archive();
      // Track per-directory name conflicts
      final Map<String, int> dirCounters = <String, int>{};

      for (final _TaskDownloadEntry dl in entries) {
        try {
          final List<int> fileBytes = await _svc.downloadFile(dl.url);
          final String ext = _extensionForFormat(dl.format);

          // Look up relative path for this task
          String relativePath = '';
          for (final Map<String, dynamic> row in _tasks) {
            if (row['task_id']?.toString() == dl.taskId) {
              relativePath =
                  row['original_relative_path']?.toString() ?? '';
              break;
            }
          }

          String entryName;
          if (relativePath.isNotEmpty) {
            String name = '${dl.baseName}_${dl.format}.$ext';
            // Windows-style conflict resolution
            final String key = '$relativePath/$name';
            final int count = (dirCounters[key] ?? 0) + 1;
            dirCounters[key] = count;
            if (count > 1) {
              final String baseNameNoExt =
                  name.substring(0, name.lastIndexOf('.'));
              name = '$baseNameNoExt ($count).$ext';
            }
            entryName = '$relativePath/$name';
          } else {
            entryName = '${dl.taskId}/${dl.baseName}_${dl.format}.$ext';
          }

          archive.addFile(ArchiveFile(entryName, fileBytes.length, fileBytes));
        } catch (_) {
          // Skip failed individual downloads
        }
      }

      if (archive.files.isEmpty) {
        if (mounted) {
          MessageService.showWarning(context, 'No files could be downloaded');
        }
        return;
      }

      final List<int>? encoded = ZipEncoder().encode(archive);
      if (encoded == null) {
        if (mounted) {
          MessageService.showWarning(context, 'Failed to create ZIP archive');
        }
        return;
      }
      final List<int> zipBytes = Uint8List.fromList(encoded);
      final String timestamp =
          DateTime.now().millisecondsSinceEpoch.toString();
      await _saveDownloadedBytes(
        bytes: zipBytes,
        filename: 'batch_all_$timestamp.zip',
        ext: 'zip',
      );
      if (mounted) {
        MessageService.showInfo(
          context,
          '${entries.length} files from ${taskIds.length} tasks packaged into ZIP',
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

  Future<void> _showSelectFormatsDialog(List<String> taskIds) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;

    // Group selected tasks by source file extension.
    // Each group shares one target-format dropdown.
    final Map<String, _SourceFormatGroup> groups = <String, _SourceFormatGroup>{};
    for (final Map<String, dynamic> row in _tasks) {
      final String? tid = row['task_id']?.toString();
      if (tid == null || !taskIds.contains(tid)) continue;
      final String name = row['original_filename']?.toString() ?? tid;
      final String sourceExt = name.contains('.')
          ? name.substring(name.lastIndexOf('.') + 1).toLowerCase()
          : '';
      if (sourceExt.isEmpty) continue;
      final dynamic d = row['downloads'];
      if (d is! Map || d.isEmpty) continue;

      _SourceFormatGroup group = groups.putIfAbsent(
        sourceExt,
        () {
          final List<String> fmts = d.keys.map((k) => k.toString()).toList()
            ..sort(
              (String a, String b) =>
                  _downloadFormatSortOrder(a).compareTo(
                    _downloadFormatSortOrder(b),
                  ),
            );
          // Default: PDF → docx, others → same as source
          final String defaultFormat = sourceExt == 'pdf'
              ? 'docx'
              : (fmts.contains(sourceExt) ? sourceExt : fmts.first);
          return _SourceFormatGroup(
            sourceFormat: sourceExt,
            availableTargetFormats: fmts,
            selectedTargetFormat: defaultFormat,
          );
        },
      );
      group.taskIds.add(tid);
    }

    if (groups.isEmpty) {
      if (mounted) {
        MessageService.showWarning(
          context,
          'No downloads available for selected tasks',
        );
      }
      return;
    }

    // Sort groups for stable display
    final List<_SourceFormatGroup> groupList = groups.values.toList()
      ..sort((a, b) => a.sourceFormat.compareTo(b.sourceFormat));

    final bool? result = await showDialog<bool>(
      context: context,
      builder: (BuildContext ctx) => _SelectFormatsDialog(
        groups: groupList,
        l10n: l10n,
      ),
    );

    if (result != true) return;

    // Map taskId → selected target format via its source-format group
    final Map<String, String> selections = <String, String>{};
    for (final _SourceFormatGroup group in groupList) {
      for (final String tid in group.taskIds) {
        selections[tid] = group.selectedTargetFormat;
      }
    }
    await _batchDownloadSelectedFormats(selections);
  }

  Future<void> _batchDownloadSelectedFormats(
    Map<String, String> selections,
  ) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    try {
      // Collect download entries from user selections
      final List<_TaskDownloadEntry> entries = <_TaskDownloadEntry>[];
      for (final Map<String, dynamic> row in _tasks) {
        final String? tid = row['task_id']?.toString();
        if (tid == null || !selections.containsKey(tid)) continue;
        final String name = row['original_filename']?.toString() ?? tid;
        final String baseName = name.contains('.')
            ? name.substring(0, name.lastIndexOf('.'))
            : name;
        final dynamic d = row['downloads'];
        if (d is! Map) continue;
        final String format = selections[tid]!;
        final dynamic url = d[format];
        if (url == null) continue;
        entries.add(_TaskDownloadEntry(
          taskId: tid,
          baseName: baseName,
          format: format,
          url: url.toString(),
        ));
      }

      if (entries.isEmpty) {
        if (mounted) {
          MessageService.showWarning(context, 'No downloads available');
        }
        return;
      }

      // Download each file and pack into a single ZIP, preserving relative paths
      final Archive archive = Archive();
      // Track per-directory name conflicts
      final Map<String, int> dirCounters = <String, int>{};

      for (final _TaskDownloadEntry dl in entries) {
        try {
          final List<int> fileBytes = await _svc.downloadFile(dl.url);
          final String ext = _extensionForFormat(dl.format);

          // Look up relative path for this task
          String relativePath = '';
          for (final Map<String, dynamic> row in _tasks) {
            if (row['task_id']?.toString() == dl.taskId) {
              relativePath =
                  row['original_relative_path']?.toString() ?? '';
              break;
            }
          }

          String entryName;
          if (relativePath.isNotEmpty) {
            final suffix = ref.read(globalSettingsProvider).translateOutputSuffix;
            String name = buildDownloadFilename(
              originalName: dl.baseName,
              extension: ext,
              suffix: suffix,
            );
            // Windows-style conflict resolution
            final String key = '$relativePath/$name';
            final int count = (dirCounters[key] ?? 0) + 1;
            dirCounters[key] = count;
            if (count > 1) {
              final String baseNameNoExt =
                  name.substring(0, name.lastIndexOf('.'));
              name = '$baseNameNoExt ($count).$ext';
            }
            entryName = '$relativePath/$name';
          } else {
            entryName = '${dl.taskId}/${dl.baseName}_${dl.format}.$ext';
          }

          archive.addFile(ArchiveFile(entryName, fileBytes.length, fileBytes));
        } catch (_) {
          // Skip failed individual downloads
        }
      }

      if (archive.files.isEmpty) {
        if (mounted) {
          MessageService.showWarning(context, 'No files could be downloaded');
        }
        return;
      }

      final List<int>? encoded = ZipEncoder().encode(archive);
      if (encoded == null) {
        if (mounted) {
          MessageService.showWarning(
            context,
            'Failed to create ZIP archive',
          );
        }
        return;
      }
      final List<int> zipBytes = Uint8List.fromList(encoded);
      final String timestamp =
          DateTime.now().millisecondsSinceEpoch.toString();
      await _saveDownloadedBytes(
        bytes: zipBytes,
        filename: 'batch_selected_$timestamp.zip',
        ext: 'zip',
      );
      if (mounted) {
        MessageService.showInfo(
          context,
          '${entries.length} files from ${selections.length} tasks packaged into ZIP',
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


  /// Build inline error message for failed tasks, shown between Line 1 and Line 2.
  Widget _buildFailedMessage(
    Map<String, dynamic> row,
    ColorScheme cs,
    ThemeData theme,
  ) {
    // For failed tasks, prefer 'error' (root cause) over 'message' (step progress).
    // message_level: 0=info, 1=warning, 2=error.
    final int level = (row['message_level'] ?? 0) as int;
    final String msg = (level >= 2
            ? ((row['error'] ?? row['message']) ?? '')
            : (row['message'] ?? row['error'] ?? ''))
        .toString();
    if (msg.isEmpty) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: cs.errorContainer.withOpacity(0.3),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: cs.error.withOpacity(0.2)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.error_outline, color: cs.error, size: 15),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                msg,
                maxLines: 4,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: cs.error,
                  fontSize: 12,
                  height: 1.35,
                ),
              ),
            ),
            const SizedBox(width: 4),
            InkWell(
              borderRadius: BorderRadius.circular(4),
              onTap: () {
                Clipboard.setData(ClipboardData(text: msg));
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(AppLocalizations.of(context)!.translationQueueErrorMessageCopied),
                      duration: const Duration(seconds: 1),
                    ),
                  );
                }
              },
              child: Padding(
                padding: const EdgeInsets.all(2),
                child: Icon(Icons.copy, color: cs.error.withOpacity(0.6), size: 14),
              ),
            ),
          ],
        ),
      ),
    );
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

    return RichText(
        text: TextSpan(children: spans),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
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
  final Future<void> Function(List<String>) onDownloadAll;
  final VoidCallback? onClear;
  final VoidCallback? onSelectFormats;

  const _BatchDownloadBottomBar({
    required this.taskIds,
    required this.formatCounts,
    required this.onDownloadFormat,
    required this.onDownloadAll,
    this.onClear,
    this.onSelectFormats,
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
          // Format chips (includes "Select" chip at the end)
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
    final List<Widget> chips = <Widget>[
      // "All" button — download all formats in one ZIP
      Padding(
        padding: const EdgeInsets.only(right: 6),
        child: ActionChip(
          avatar: const Icon(Icons.all_inclusive, size: 16),
          label: Text(
            'All (${formatCounts.values.fold(0, (a, b) => a + b)})',
            style: const TextStyle(fontSize: 12),
          ),
          onPressed: () => onDownloadAll(taskIds),
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          padding: const EdgeInsets.symmetric(horizontal: 4),
        ),
      ),
    ];

    const List<(String, IconData)> formats = <(String, IconData)>[
      ('docx', Icons.description),
      ('html', Icons.language),
      ('md', Icons.article),
      ('md_zip', Icons.folder_zip_outlined),
      ('pdf', Icons.picture_as_pdf),
      ('pdf_reflow', Icons.picture_as_pdf_outlined),
      ('txt', Icons.text_snippet),
    ];
    for (final f in formats) {
      final String ft = f.$1;
      final int count = formatCounts[ft] ?? 0;
      if (count == 0) continue;
      chips.add(Padding(
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
      ));
    }
    // "Select" chip — choose per-source-format target
    if (onSelectFormats != null) {
      chips.add(Padding(
        padding: const EdgeInsets.only(right: 6),
        child: ActionChip(
          avatar: const Icon(Icons.tune, size: 16),
          label: Text(
            '${l10n.translationQueueSelectFormats} (${taskIds.length})',
            style: const TextStyle(fontSize: 12),
          ),
          onPressed: onSelectFormats,
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          padding: const EdgeInsets.symmetric(horizontal: 4),
        ),
      ));
    }
    return chips;
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

bool _isOriginalImageDownloadFormat(String formatKey) {
  const Set<String> imageFormats = <String>{
    'png',
    'jpg',
    'jpeg',
    'webp',
    'bmp',
    'gif',
    'tif',
    'tiff',
  };
  return imageFormats.contains(formatKey.toLowerCase());
}

/// Map download format key to a localized button label.
String _extensionForFormat(String formatKey) {
  switch (formatKey) {
    case 'docx': return 'docx';
    case 'html': return 'html';
    case 'md': return 'md';
    case 'md_zip': return 'zip';
    case 'pdf':
    case 'pdf_reflow': return 'pdf';
    case 'txt': return 'txt';
    default: return formatKey;
  }
}

String _downloadFormatButtonLabel(String formatKey, AppLocalizations l10n) {
  switch (formatKey) {
    case 'md':
      return l10n.translationQueueDownloadMdEmbedded;
    case 'md_zip':
      return l10n.translationQueueDownloadMdZip;
    case 'pdf':
      return l10n.translationExportPdfPreserveLayout;
    case 'pdf_reflow':
      return l10n.translationExportPdfReflow;
    default:
      if (_isOriginalImageDownloadFormat(formatKey)) {
        return l10n.translationExportImageOriginalLayout;
      }
      return formatKey.toUpperCase();
  }
}

/// Map download format key to a Material icon.
IconData _downloadFormatIcon(String ft) {
  switch (ft) {
    case 'pdf':
    case 'pdf_reflow':
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
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'webp':
    case 'bmp':
    case 'gif':
    case 'tif':
    case 'tiff':
      return Icons.image_outlined;
    default:
      return Icons.download;
  }
}

/// Icon button for scrollable queue rows — avoids Tooltip OverlayPortal hit-test
/// crashes while the task list is scrolling.
class _QueueListIconButton extends StatelessWidget {
  const _QueueListIconButton({
    required this.icon,
    required this.semanticLabel,
    required this.onPressed,
    this.iconColor,
    this.minSize = 28,
  });

  final IconData icon;
  final String semanticLabel;
  final VoidCallback? onPressed;
  final Color? iconColor;
  final double minSize;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: semanticLabel,
      button: true,
      child: Tooltip(
        message: semanticLabel,
        triggerMode: TooltipTriggerMode.longPress,
        child: IconButton(
          icon: Icon(icon, size: 20, color: iconColor),
          tooltip: semanticLabel,
          visualDensity: VisualDensity.compact,
          padding: const EdgeInsets.all(4),
          constraints: BoxConstraints(minWidth: minSize, minHeight: minSize),
          onPressed: onPressed,
        ),
      ),
    );
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
    final String label = _downloadFormatButtonLabel(ft, l10n);
    return Semantics(
      label: label,
      button: true,
      child: Tooltip(
        message: label,
        triggerMode: TooltipTriggerMode.longPress,
        child: IconButton(
        icon: Icon(_downloadFormatIcon(ft), size: 20),
        tooltip: label,
        visualDensity: VisualDensity.compact,
        padding: const EdgeInsets.all(4),
        constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
        onPressed: url.isNotEmpty
            ? () => onDownload(taskId, ft, url, name, isFormatConversion)
            : null,
        ),
      ),
    );
  }
}

class _TaskDownloadEntry {
  final String taskId;
  final String baseName;
  final String format;
  final String url;
  const _TaskDownloadEntry({
    required this.taskId,
    required this.baseName,
    required this.format,
    required this.url,
  });
}

// ─── Select formats dialog ───────────────────────────────────────────────────

/// Groups tasks by their source file extension so the user picks one target
/// format per source type, not per individual task.
class _SourceFormatGroup {
  final String sourceFormat;
  final List<String> availableTargetFormats;
  final List<String> taskIds = <String>[];
  String selectedTargetFormat;

  _SourceFormatGroup({
    required this.sourceFormat,
    required this.availableTargetFormats,
    required this.selectedTargetFormat,
  });
}

class _SelectFormatsDialog extends StatefulWidget {
  final List<_SourceFormatGroup> groups;
  final AppLocalizations l10n;

  const _SelectFormatsDialog({
    required this.groups,
    required this.l10n,
  });

  @override
  State<_SelectFormatsDialog> createState() => _SelectFormatsDialogState();
}

class _SelectFormatsDialogState extends State<_SelectFormatsDialog> {
  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return AlertDialog(
      title: Text(widget.l10n.translationQueueSelectFormatsTitle),
      content: SizedBox(
        width: 480,
        child: ListView.builder(
          shrinkWrap: true,
          itemCount: widget.groups.length,
          itemBuilder: (BuildContext context, int index) {
            final _SourceFormatGroup group = widget.groups[index];
            final IconData icon = _downloadFormatIcon(group.sourceFormat);
            return Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Row(
                children: <Widget>[
                  Icon(icon, size: 20, color: theme.colorScheme.onSurfaceVariant),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${group.sourceFormat.toUpperCase()} '
                      '(${group.taskIds.length})',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  DropdownButton<String>(
                    value: group.selectedTargetFormat,
                    isDense: true,
                    underline: const SizedBox(),
                    style: theme.textTheme.bodySmall,
                    items: group.availableTargetFormats.map((String ft) {
                      return DropdownMenuItem<String>(
                        value: ft,
                        child: Text(
                          _downloadFormatButtonLabel(ft, widget.l10n),
                        ),
                      );
                    }).toList(),
                    onChanged: (String? value) {
                      if (value != null) {
                        setState(() {
                          group.selectedTargetFormat = value;
                        });
                      }
                    },
                  ),
                ],
              ),
            );
          },
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(widget.l10n.translationQueueClearAllCancel),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(widget.l10n.translationQueueSelectFormatsDownload),
        ),
      ],
    );
  }
}
