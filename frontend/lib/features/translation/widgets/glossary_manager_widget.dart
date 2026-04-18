// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/services/glossary_api_service.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/utils/dialog_helper.dart';
import 'translation_quick_settings.dart'
    show
        TranslationQuickSettings,
        TranslationQuickSettingsNotifier,
        translationQuickSettingsProvider,
        translationQuickSettingsProviderFamily;
import '../providers/preview_tabs_provider.dart';
import '../models/preview_tab.dart';
import 'glossary_preview.dart';

/// Unified Glossary Manager Widget
/// Integrates glossary selection and generated glossary viewing
class GlossaryManagerWidget extends ConsumerStatefulWidget {
  // For checking generated glossary

  const GlossaryManagerWidget({
    super.key,
    this.flowId,
    this.taskId,
    this.attachments,
  });
  final String? flowId;
  final String? taskId; // For viewing generated glossary
  final Map<String, String>? attachments;

  @override
  ConsumerState<GlossaryManagerWidget> createState() =>
      _GlossaryManagerWidgetState();
}

class _GlossaryManagerWidgetState extends ConsumerState<GlossaryManagerWidget> {
  late Future<List<Map<String, dynamic>>> _glossariesFuture;
  bool _expanded = false;
  bool _isRefreshing = false;
  bool _hasAutoRefreshed = false; // Track if auto-refresh has been done
  bool _loadingGeneratedGlossary = false;
  Map<String, dynamic>? _generatedGlossaryData;

  @override
  void initState() {
    super.initState();
    _glossariesFuture = GlossaryApiService.getSimpleGlossaryList();
    // Check for generated glossary on init
    _checkGeneratedGlossary();
  }

  /// Check if generated glossary exists and load it
  Future<void> _checkGeneratedGlossary() async {
    if (widget.taskId == null || widget.taskId!.isEmpty) return;

    // If attachments are provided, use them directly
    if (widget.attachments != null &&
        widget.attachments!.containsKey('glossary')) {
      await _loadGeneratedGlossary();
      return;
    }

    // Otherwise, fetch task status to check for attachments
    try {
      final TranslationService svc = TranslationService();
      final Map<String, dynamic> status = await svc.getStatus(widget.taskId!);
      final Map<String, dynamic>? attachments =
          status['attachments'] as Map<String, dynamic>?;

      if (attachments != null && attachments.containsKey('glossary')) {
        await _loadGeneratedGlossary();
      }
    } catch (e) {
      // Ignore errors - glossary may not exist yet
    }
  }

  /// Load generated glossary from attachment
  Future<void> _loadGeneratedGlossary() async {
    if (widget.taskId == null) return;

    setState(() {
      _loadingGeneratedGlossary = true;
    });

    try {
      final TranslationService svc = TranslationService();
      final List<int> bytes =
          await svc.downloadAttachment(widget.taskId!, 'glossary');

      // Try to parse as JSON first
      var glossaryData = <String, dynamic>{};
      try {
        final String jsonStr = utf8.decode(bytes);
        final Map<String, dynamic> parsed =
            jsonDecode(jsonStr) as Map<String, dynamic>;
        glossaryData = parsed;
      } catch (e) {
        // If not JSON, try CSV
        try {
          final String csvStr = utf8.decode(bytes);
          final List<String> lines = csvStr.split('\n');
          for (final String line in lines) {
            if (line.trim().isEmpty) continue;
            final List<String> parts = line.split(',');
            if (parts.length >= 2) {
              glossaryData[parts[0].trim()] = parts[1].trim();
            }
          }
        } catch (e2) {
          // Failed to parse, ignore
        }
      }

      if (mounted) {
        setState(() {
          _generatedGlossaryData = glossaryData;
          _loadingGeneratedGlossary = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loadingGeneratedGlossary = false;
        });
      }
    }
  }

  /// Refresh glossary list (smart sync: auto-refresh on first expansion)
  Future<void> _refreshGlossaries() async {
    setState(() {
      _isRefreshing = true;
    });

    try {
      final List<Map<String, dynamic>> refreshed =
          await GlossaryApiService.getSimpleGlossaryList();
      if (mounted) {
        setState(() {
          _glossariesFuture = Future.value(refreshed);
          _isRefreshing = false;
          _hasAutoRefreshed = true;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isRefreshing = false;
        });
        final l10n = AppLocalizations.of(context)!;
        MessageService.showError(
          context,
          l10n.glossaryErrorRefresh(e.toString()),
        );
      }
    }
  }

  /// Handle expansion change (smart sync)
  void _onExpansionChanged(bool expanded) {
    setState(() {
      _expanded = expanded;
    });

    // Auto-refresh on first expansion (smart sync)
    if (expanded && !_hasAutoRefreshed) {
      _refreshGlossaries();
    }
  }

  /// Toggle glossary selection
  void _toggleGlossary(String glossaryId) {
    final TranslationQuickSettingsNotifier notifier = widget.flowId != null
        ? ref.read(
            translationQuickSettingsProviderFamily(widget.flowId!).notifier,)
        : ref.read(translationQuickSettingsProvider.notifier);
    notifier.toggleGlossary(glossaryId);
  }

  /// View generated glossary in preview tab
  Future<void> _viewGeneratedGlossary() async {
    if (_generatedGlossaryData == null) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showWarning(
        context,
        l10n.glossaryWarningNoGenerated,
      );
      return;
    }

    final PreviewTabsNotifier tabsNotifier = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!).notifier)
        : ref.read(previewTabsProvider.notifier);

    final l10n = AppLocalizations.of(context)!;

    final PreviewTab glossaryTab = PreviewTab(
      id: 'glossary_${widget.taskId}_${DateTime.now().millisecondsSinceEpoch}',
      type: PreviewTabType.glossary,
      title: l10n.glossaryGeneratedTabTitle,
      icon: Icons.book,
      content: GlossaryPreview(
        glossaryId: 'generated_${widget.taskId}',
        glossaryData: _generatedGlossaryData!,
        onSave: (Map<String, dynamic> updatedGlossary) {
          // TODO: Save to backend if needed
        },
      ),
      dataRef: <String, dynamic>{
        'glossaryData': _generatedGlossaryData,
        'flowId': widget.flowId,
        'taskId': widget.taskId,
      },
    );

    tabsNotifier.addTab(glossaryTab);
    final List<PreviewTab> currentTabs = widget.flowId != null
        ? ref.read(previewTabsProviderFamily(widget.flowId!)).tabs
        : ref.read(previewTabsProvider).tabs;
    final int tabIndex =
        currentTabs.indexWhere((PreviewTab t) => t.id == glossaryTab.id);
    if (tabIndex >= 0) {
      tabsNotifier.switchToTab(tabIndex);
    }
  }

  /// Add generated glossary to personal glossary
  Future<void> _addToPersonalGlossary() async {
    if (_generatedGlossaryData == null) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showWarning(
        context,
        l10n.glossaryWarningNoGenerated,
      );
      return;
    }

    // Show confirmation dialog with preview and merge mode selection
    final int termCount = _generatedGlossaryData!.length;
    final List<MapEntry<String, dynamic>> previewTerms =
        _generatedGlossaryData!.entries.take(5).toList();

    var selectedMergeMode = 'update'; // Default: update (upsert)

    final l10n = AppLocalizations.of(context)!;

    final Map<String, dynamic>? confirmed =
        await DialogHelper.showDialog<Map<String, dynamic>>(
      context: context,
      builder: (BuildContext context) => StatefulBuilder(
        builder: (BuildContext context, setState) => AlertDialog(
          title: Text(l10n.glossaryDialogAddTitle),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  l10n.glossaryDialogAddBody(termCount.toString()),
                  style: const TextStyle(fontWeight: FontWeight.w500),
                ),
                const SizedBox(height: 16),
                Text(
                  l10n.glossaryDialogAddPreviewTitle,
                  style: const TextStyle(
                    fontWeight: FontWeight.w500,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 8),
                ...previewTerms.map(
                  (MapEntry<String, dynamic> entry) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Text(
                      '• ${entry.key} => ${entry.value}',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ),
                if (termCount > 5)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      l10n.glossaryDialogAddMoreTerms(
                        (termCount - 5).toString(),
                      ),
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.grey.shade600,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                const Divider(),
                const SizedBox(height: 8),
                Text(
                  l10n.glossaryDialogMergeStrategyTitle,
                  style: const TextStyle(
                    fontWeight: FontWeight.w500,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 8),
                RadioListTile<String>(
                  title: Text(l10n.glossaryDialogMergeUpdateTitle),
                  subtitle: Text(
                    l10n.glossaryDialogMergeUpdateSubtitle,
                    style: const TextStyle(fontSize: 11),
                  ),
                  value: 'update',
                  groupValue: selectedMergeMode,
                  onChanged: (String? value) {
                    if (value != null) {
                      setState(() {
                        selectedMergeMode = value;
                      });
                    }
                  },
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                ),
                RadioListTile<String>(
                  title: Text(l10n.glossaryDialogMergeAppendTitle),
                  subtitle: Text(
                    l10n.glossaryDialogMergeAppendSubtitle,
                    style: const TextStyle(fontSize: 11),
                  ),
                  value: 'append',
                  groupValue: selectedMergeMode,
                  onChanged: (String? value) {
                    if (value != null) {
                      setState(() {
                        selectedMergeMode = value;
                      });
                    }
                  },
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                ),
                RadioListTile<String>(
                  title: Text(l10n.glossaryDialogMergeReplaceTitle),
                  subtitle: Text(
                    l10n.glossaryDialogMergeReplaceSubtitle,
                    style: const TextStyle(fontSize: 11),
                  ),
                  value: 'replace',
                  groupValue: selectedMergeMode,
                  onChanged: (String? value) {
                    if (value != null) {
                      setState(() {
                        selectedMergeMode = value;
                      });
                    }
                  },
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10n.glossaryDialogCancel),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(<String, Object>{
                'confirmed': true,
                'mergeMode': selectedMergeMode,
              }),
              child: Text(l10n.glossaryDialogReviewAndAdd),
            ),
          ],
        ),
      ),
    );

    if (confirmed == null || confirmed['confirmed'] != true) return;
    final String mergeMode = confirmed['mergeMode'] as String? ?? 'update';

    // Open glossary preview tab for review first
    await _viewGeneratedGlossary();

    // Show final confirmation dialog
    final bool? addConfirmed = await DialogHelper.showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: Text(l10n.glossaryConfirmAddTitle),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              l10n.glossaryConfirmAddBody(termCount.toString()),
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 8),
            Text(
              mergeMode == 'update'
                  ? l10n.glossaryConfirmAddStrategyUpdate
                  : mergeMode == 'append'
                      ? l10n.glossaryConfirmAddStrategyAppend
                      : l10n.glossaryConfirmAddStrategyReplace,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              l10n.glossaryConfirmAddAutoCreateHint,
              style: TextStyle(
                fontSize: 11,
                color: Colors.blue.shade700,
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(l10n.glossaryDialogCancel),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(l10n.glossaryConfirmAddButton),
          ),
        ],
      ),
    );

    if (addConfirmed != true) return;

    // Actually add to personal glossary
    setState(() {
      _loadingGeneratedGlossary = true;
    });

    try {
      final Map<String, dynamic> result =
          await GlossaryApiService.addToPersonalGlossary(
        _generatedGlossaryData!,
        mergeMode: mergeMode,
      );

      if (mounted) {
        // Show detailed feedback
        final int importedCount = result['imported_count'] as int? ?? termCount;
        final int newTerms = result['new_terms'] as int? ?? 0;
        final int updatedTerms = result['updated_terms'] as int? ?? 0;
        final bool glossaryCreated =
            result['glossary_created'] as bool? ?? false;
        final int total = result['total'] as int? ?? importedCount;

        final l10n = AppLocalizations.of(context)!;
        String message;
        if (glossaryCreated) {
          message = l10n.glossaryWidgetPersonalCreated(importedCount.toString());
        } else {
          if (mergeMode == 'replace') {
            message =
                l10n.glossaryWidgetPersonalReplaced(total.toString());
          } else if (mergeMode == 'append') {
            message = l10n.glossaryWidgetPersonalAppended(
              newTerms.toString(),
              (termCount - newTerms).toString(),
              total.toString(),
            );
          } else {
            message = l10n.glossaryWidgetPersonalUpdated(
              newTerms.toString(),
              updatedTerms.toString(),
              total.toString(),
            );
          }
        }

        MessageService.showSuccess(context, message);
        // Refresh glossary list to show updated personal glossary
        _refreshGlossaries();
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(
          context,
          AppLocalizations.of(context)!.glossaryWidgetAddToPersonalFailed(e.toString()),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _loadingGeneratedGlossary = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final TranslationQuickSettings settings = widget.flowId != null
        ? ref.watch(translationQuickSettingsProviderFamily(widget.flowId!))
        : ref.watch(translationQuickSettingsProvider);

    final int selectedCount = settings.selectedGlossaries.length;
    final bool hasGeneratedGlossary = _generatedGlossaryData != null;

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            // Header
            Row(
              children: <Widget>[
                Icon(Icons.book, color: Colors.blue.shade700, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    l10n.glossaryWidgetTitle,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Colors.blue.shade700,
                    ),
                  ),
                ),
                // Refresh button
                IconButton(
                  icon: _isRefreshing
                      ? SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              Colors.blue.shade700,
                            ),
                          ),
                        )
                      : Icon(Icons.refresh,
                          size: 18, color: Colors.blue.shade700,),
                  onPressed: _isRefreshing ? null : _refreshGlossaries,
                  tooltip: l10n.glossaryWidgetRefreshTooltip,
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Selected glossaries summary
            if (selectedCount > 0)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blue.shade200),
                ),
                child: Row(
                  children: <Widget>[
                    Icon(Icons.check_circle,
                        size: 16, color: Colors.blue.shade700,),
                    const SizedBox(width: 8),
                    Text(
                      selectedCount > 1
                          ? l10n.glossaryWidgetGlossariesSelectedPlural(
                              selectedCount.toString(),)
                          : l10n.glossaryWidgetGlossariesSelected(
                              selectedCount.toString(),),
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.blue.shade700,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),

            const SizedBox(height: 12),

            // Glossary selector (expandable)
            InkWell(
              onTap: () => _onExpansionChanged(!_expanded),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: <Widget>[
                    AnimatedRotation(
                      duration: const Duration(milliseconds: 150),
                      turns: _expanded ? 0.25 : 0.0,
                      child: const Icon(Icons.chevron_right, size: 20),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      l10n.glossaryWidgetSelectGlossaries,
                      style: const TextStyle(fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
              ),
            ),

            // Glossary list (expandable)
            AnimatedSize(
              duration: const Duration(milliseconds: 150),
              curve: Curves.easeInOut,
              child: _expanded
                  ? FutureBuilder<List<Map<String, dynamic>>>(
                      future: _glossariesFuture,
                      builder: (BuildContext context,
                          AsyncSnapshot<List<Map<String, dynamic>>> snapshot,) {
                        if (snapshot.connectionState ==
                            ConnectionState.waiting) {
                          return const SizedBox(
                            height: 48,
                            child: Center(
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          );
                        }
                        if (snapshot.hasError) {
                          return Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.red.shade50,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.red.shade200),
                            ),
                            child: Row(
                              children: <Widget>[
                                Icon(
                                  Icons.error_outline,
                                  color: Colors.red.shade700,
                                  size: 20,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    l10n.glossaryWidgetLoadFailed(
                                        snapshot.error.toString(),),
                                    style: TextStyle(
                                      color: Colors.red.shade700,
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }

                        final List<Map<String, dynamic>> glossaries =
                            snapshot.data ?? <Map<String, dynamic>>[];
                        if (glossaries.isEmpty) {
                          return Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.grey.shade100,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.grey.shade300),
                            ),
                            child: Row(
                              children: <Widget>[
                                const Icon(
                                  Icons.info_outline,
                                  color: Colors.grey,
                                  size: 20,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    l10n.glossaryWidgetNoGlossariesHint,
                                    style: const TextStyle(
                                        color: Colors.grey, fontSize: 12,),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }

                        return Container(
                          constraints: const BoxConstraints(maxHeight: 200),
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.grey.shade300),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: ListView.builder(
                            shrinkWrap: true,
                            physics: const ClampingScrollPhysics(),
                            itemCount: glossaries.length,
                            itemBuilder: (BuildContext context, int index) {
                              final Map<String, dynamic> g = glossaries[index];
                              final String glossaryId = g['id'] as String;
                              final name = g['name'] ?? glossaryId;
                              final type = g['type'] ?? 'unknown';
                              final itemCount = g['item_count'] ?? 0;
                              final bool isSelected = settings
                                  .selectedGlossaries
                                  .contains(glossaryId);
                              return Container(
                                margin: const EdgeInsets.symmetric(vertical: 2),
                                decoration: BoxDecoration(
                                  color:
                                      isSelected ? Colors.blue.shade50 : null,
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(
                                    color: isSelected
                                        ? Colors.blue.shade200
                                        : Colors.transparent,
                                  ),
                                ),
                                child: CheckboxListTile(
                                  value: isSelected,
                                  onChanged: (_) => _toggleGlossary(glossaryId),
                                  controlAffinity:
                                      ListTileControlAffinity.leading,
                                  title: Text(
                                    name,
                                    style: const TextStyle(fontSize: 14),
                                    overflow: TextOverflow.ellipsis,
                                    maxLines: 1,
                                  ),
                                  subtitle: Text(
                                    l10n.glossaryWidgetTypeCountItems(
                                        type.toString(),
                                        itemCount.toString(),),
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey.shade600,
                                    ),
                                    overflow: TextOverflow.ellipsis,
                                    maxLines: 1,
                                  ),
                                  contentPadding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 4,
                                  ),
                                  dense: true,
                                  visualDensity: VisualDensity.compact,
                                  activeColor: Colors.blue.shade600,
                                  checkboxShape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                ),
                              );
                            },
                          ),
                        );
                      },
                    )
                  : const SizedBox.shrink(),
            ),

            // Generated glossary section (if available)
            if (hasGeneratedGlossary) ...<Widget>[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Row(
                      children: <Widget>[
                        Icon(
                          Icons.auto_awesome,
                          size: 18,
                          color: Colors.green.shade700,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            l10n.glossaryGeneratedTabTitle,
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: Colors.green.shade700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      l10n.glossaryWidgetTermsExtracted(
                          _generatedGlossaryData!.length.toString(),),
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.green.shade700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: <Widget>[
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _loadingGeneratedGlossary
                                ? null
                                : _viewGeneratedGlossary,
                            icon: _loadingGeneratedGlossary
                                ? const SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(Icons.visibility, size: 16),
                            label: Text(
                              AppLocalizations.of(context)!.glossaryPanelView,
                            ),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.green.shade700,
                              side: BorderSide(color: Colors.green.shade300),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _loadingGeneratedGlossary
                                ? null
                                : _addToPersonalGlossary,
                            icon: const Icon(Icons.add, size: 16),
                            label: Text(
                              AppLocalizations.of(context)!
                                  .glossaryPanelAddToPersonal,
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.green.shade700,
                              foregroundColor: Colors.white,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
