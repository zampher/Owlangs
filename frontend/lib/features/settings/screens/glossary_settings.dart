import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import '../../../core/utils/file_picker_helper.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;
import 'package:file_saver/file_saver.dart';
import 'dart:io';
import '../../../l10n/app_localizations.dart';
import '../../../shared/services/glossary_api_service.dart';
import '../../../shared/models/language_model.dart';

// 术语表设置状态管理
final StateNotifierProvider<GlossarySettingsNotifier, GlossarySettings>
    glossarySettingsProvider =
    StateNotifierProvider<GlossarySettingsNotifier, GlossarySettings>(
  (
    ref,
  ) =>
      GlossarySettingsNotifier(),
);

class GlossarySettings {
  const GlossarySettings({
    this.useGlobalGlossary = false,
    this.globalGlossaryFile = '',
    this.glossaryGenerateEnable = true,
    this.glossaryEntries = const <GlossaryEntry>[],
    this.isUploading = false,
    this.selectedCategoryFilter,
    this.targetLanguage = 'en',
    this.selectedGlossaryId,
  });
  final bool useGlobalGlossary;
  final String globalGlossaryFile;
  final bool glossaryGenerateEnable;
  final List<GlossaryEntry> glossaryEntries;
  final bool isUploading;
  final String? selectedCategoryFilter;
  final String targetLanguage; // Only target_lang is kept, source_lang removed
  final String? selectedGlossaryId;

  GlossarySettings copyWith({
    bool? useGlobalGlossary,
    String? globalGlossaryFile,
    bool? glossaryGenerateEnable,
    List<GlossaryEntry>? glossaryEntries,
    bool? isUploading,
    String? selectedCategoryFilter,
    String? targetLanguage,
    String? selectedGlossaryId,
  }) =>
      GlossarySettings(
        useGlobalGlossary: useGlobalGlossary ?? this.useGlobalGlossary,
        globalGlossaryFile: globalGlossaryFile ?? this.globalGlossaryFile,
        glossaryGenerateEnable:
            glossaryGenerateEnable ?? this.glossaryGenerateEnable,
        glossaryEntries: glossaryEntries ?? this.glossaryEntries,
        isUploading: isUploading ?? this.isUploading,
        selectedCategoryFilter:
            selectedCategoryFilter ?? this.selectedCategoryFilter,
        targetLanguage: targetLanguage ?? this.targetLanguage,
        selectedGlossaryId: selectedGlossaryId ?? this.selectedGlossaryId,
      );
}

class GlossaryEntry {
  const GlossaryEntry({
    required this.id,
    required this.sourceText,
    required this.targetText,
    required this.targetLanguage,
    this.category = '',
    this.isActive = true,
  });
  final String id;
  final String sourceText;
  final String targetText;
  final String targetLanguage; // Only target_lang is kept, source_lang removed
  final String category;
  final bool isActive;

  // Backward compatibility getters
  String get source => sourceText;
  String get target => targetText;

  GlossaryEntry copyWith({
    String? id,
    String? sourceText,
    String? targetText,
    String? targetLanguage,
    String? category,
    bool? isActive,
  }) =>
      GlossaryEntry(
        id: id ?? this.id,
        sourceText: sourceText ?? this.sourceText,
        targetText: targetText ?? this.targetText,
        targetLanguage: targetLanguage ?? this.targetLanguage,
        category: category ?? this.category,
        isActive: isActive ?? this.isActive,
      );
}

class GlossarySettingsNotifier extends StateNotifier<GlossarySettings> {
  GlossarySettingsNotifier() : super(const GlossarySettings());

  void updateUseGlobalGlossary(bool useGlobalGlossary) {
    state = state.copyWith(useGlobalGlossary: useGlobalGlossary);
  }

  void updateGlobalGlossaryFile(String globalGlossaryFile) {
    state = state.copyWith(globalGlossaryFile: globalGlossaryFile);
  }

  void updateGlossaryGenerateEnable(bool glossaryGenerateEnable) {
    state = state.copyWith(glossaryGenerateEnable: glossaryGenerateEnable);
  }

  void addGlossaryEntry(GlossaryEntry entry) {
    final updatedEntries = List<GlossaryEntry>.from(state.glossaryEntries);
    updatedEntries.add(entry);
    state = state.copyWith(glossaryEntries: updatedEntries);
  }

  void updateGlossaryEntry(GlossaryEntry entry) {
    final updatedEntries =
        state.glossaryEntries.map((e) => e.id == entry.id ? entry : e).toList();
    state = state.copyWith(glossaryEntries: updatedEntries);
  }

  void removeGlossaryEntry(String id) {
    final updatedEntries =
        state.glossaryEntries.where((e) => e.id != id).toList();
    state = state.copyWith(glossaryEntries: updatedEntries);
  }

  void setGlossaryEntries(List<GlossaryEntry> entries) {
    state = state.copyWith(glossaryEntries: entries);
  }

  Future<void> uploadGlossaryFile() async {
    state = state.copyWith(isUploading: true);

    try {
      // Use FilePickerHelper to ensure Web uses browser-native file picker
      final result = await FilePickerHelper.pickFiles(
        type: FileType.custom,
        allowedExtensions: <String>['txt', 'csv', 'json'],
      );

      if (result != null) {
        final file = result.files.single;
        final fileName =
            kIsWeb ? file.name : file.path?.split('/').last ?? 'unknown';
        state = state.copyWith(globalGlossaryFile: fileName);
      }
    } catch (e) {
      // Handle error
    } finally {
      state = state.copyWith(isUploading: false);
    }
  }

  void setCategoryFilter(String? filter) {
    state = state.copyWith(selectedCategoryFilter: filter);
  }

  void updateTargetLanguage(String languageCode) {
    state = state.copyWith(targetLanguage: languageCode);
  }

  void reset() {
    state = const GlossarySettings();
  }

  void setSelectedGlossaryId(String id) {
    state = state.copyWith(selectedGlossaryId: id);
  }

  void clearSelectedGlossaryId() {
    state = state.copyWith();
  }
}

class GlossarySettingsScreen extends ConsumerWidget {
  const GlossarySettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(glossarySettingsProvider);
    final notifier = ref.read(glossarySettingsProvider.notifier);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          // Glossary Management (kept)
          _buildGlossaryManagementSection(context, settings, notifier),
          const SizedBox(height: 24),

          // Glossary Entries (kept)
          _buildGlossaryEntriesSection(context, settings, notifier),
        ],
      ),
    );
  }

  // Removed Global Glossary section with switches and upload file option
  // Widget _buildGlobalGlossarySection(BuildContext context, GlossarySettings settings, GlossarySettingsNotifier notifier) { ... }

  Widget _buildGlossaryManagementSection(
    BuildContext context,
    GlossarySettings settings,
    GlossarySettingsNotifier notifier,
  ) =>
      Card(
        elevation: 4,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(Icons.manage_accounts,
                      color: Theme.of(context).colorScheme.primary,),
                  const SizedBox(width: 8),
                  Text(
                    AppLocalizations.of(context)!.settingsGlossaryManagementTitle,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                AppLocalizations.of(context)!.settingsGlossaryManagementSubtitle,
                style: TextStyle(
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 16),
              // Toolbar: Glossary selector + actions
              FutureBuilder<List<Map<String, dynamic>>>(
                future: GlossaryApiService.getSimpleGlossaryList(),
                builder: (
                  BuildContext context,
                  AsyncSnapshot<List<Map<String, dynamic>>> snapshot,
                ) {
                  final bool loading =
                      snapshot.connectionState == ConnectionState.waiting;
                  final List<Map<String, dynamic>> glossaries =
                      snapshot.data ?? <Map<String, dynamic>>[];
                  var selectedId = settings.selectedGlossaryId;
                  if (!loading && selectedId == null && glossaries.isNotEmpty) {
                    // initialize selection on first load (defer state changes after build)
                    final String firstId = glossaries.first['id'] as String;
                    WidgetsBinding.instance.addPostFrameCallback((_) async {
                      notifier.setSelectedGlossaryId(firstId);
                      await _loadEntriesForGlossary(
                        context,
                        notifier,
                        firstId,
                        settings,
                      );
                    });
                    selectedId = firstId;
                  }

                  return Row(
                    children: <Widget>[
                      // Glossary dropdown
                      Expanded(
                        flex: 2,
                        child: loading
                            ? const LinearProgressIndicator(minHeight: 44)
                            : DropdownButtonFormField<String>(
                                isExpanded: true,
                                initialValue: selectedId,
                                items: glossaries.map((Map<String, dynamic> g) {
                                  final name = g['name'] ?? g['id'];
                                  final type = g['type'] ?? '';
                                  final count = g['item_count'] ?? 0;
                                  return DropdownMenuItem<String>(
                                    value: g['id'] as String,
                                    child: Text(
                                      AppLocalizations.of(context)!
                                          .settingsGlossaryGlossaryDropdownItem(
                                        name.toString(),
                                        type.toString(),
                                        count.toString(),
                                      ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  );
                                }).toList(),
                                onChanged: (String? v) async {
                                  if (v == null) return;
                                  notifier.setSelectedGlossaryId(v);
                                  await _loadEntriesForGlossary(
                                    context,
                                    notifier,
                                    v,
                                    settings,
                                  );
                                },
                                decoration: InputDecoration(
                                  labelText: AppLocalizations.of(context)!
                                      .settingsGlossarySelectGlossary,
                                ),
                              ),
                      ),
                      const SizedBox(width: 12),
                      // Create glossary
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: () => _showCreateGlossaryDialog(context),
                          icon: const Icon(Icons.create_new_folder),
                          label: Text(AppLocalizations.of(context)!
                              .settingsGlossaryCreateGlossary,),

                        ),
                      ),
                      const SizedBox(width: 12),
                      // Import current
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: () =>
                              _showImportDialog(context, settings, notifier),
                          icon: const Icon(Icons.upload),
                          label: Text(AppLocalizations.of(context)!
                              .settingsGlossaryImportCsv,),

                        ),
                      ),
                      const SizedBox(width: 12),
                      // Export current
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: () => _showExportDialog(context, settings),
                          icon: const Icon(Icons.download),
                          label: Text(AppLocalizations.of(context)!
                              .settingsGlossaryExport,),

                        ),
                      ),
                      const SizedBox(width: 12),
                      // Export all
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: () async {
                            try {
                              final Uint8List bytes =
                                  await GlossaryApiService.exportAll(
                                targetLanguage: settings.targetLanguage,
                              );
                              final String baseName =
                                  'glossaries_${DateTime.now().millisecondsSinceEpoch}';
                              if (kIsWeb) {
                                await FileSaver.instance.saveFile(
                                  name: baseName,
                                  bytes: bytes,
                                  ext: 'zip',
                                );
                              } else {
                                // Use FilePickerHelper to ensure Web uses browser download
                                final String? savePath =
                                    await FilePickerHelper.saveFile(
                                  fileName: '$baseName.zip',
                                  dialogTitle: AppLocalizations.of(context)!
                                      .settingsGlossarySaveZip,
                                  type: FileType.custom,
                                  allowedExtensions: <String>['zip'],
                                );
                                if (savePath != null) {
                                  // Log saved path
                                  // ignore: avoid_print
                                  print('[ExportAll] Saved to: $savePath');
                                  final File f = File(savePath);
                                  await f.writeAsBytes(bytes, flush: true);
                                }
                              }
                              if (context.mounted) {
                                _showCopyableSnackBar(
                                  context,
                                  AppLocalizations.of(context)!
                                      .settingsGlossaryExportedAllSnack(
                                    '${kIsWeb ? baseName : 'ZIP file'} (${bytes.lengthInBytes} bytes)',
                                  ),
                                );
                              }
                            } catch (e) {
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text(
                                      AppLocalizations.of(context)!
                                          .settingsGlossaryExportAllFailedSnack(
                                        e.toString(),
                                      ),
                                    ),
                                  ),
                                );
                              }
                            }
                          },
                          icon: const Icon(Icons.file_download),
                          label: Text(AppLocalizations.of(context)!
                              .settingsGlossaryExportAll,),

                        ),
                      ),
                      const SizedBox(width: 12),
                      // Delete selected glossary
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: (selectedId == null)
                              ? null
                              : () async {
                                  final l10n = AppLocalizations.of(context)!;
                                  final bool? confirm = await showDialog<bool>(
                                    context: context,
                                    builder: (_) => AlertDialog(
                                      title: Text(l10n.settingsGlossaryDeleteDialogTitle),
                                      content: Text(
                                        l10n.settingsGlossaryDeleteDialogMessage(
                                          selectedId ?? '',
                                        ),
                                      ),
                                      actions: <Widget>[
                                        TextButton(
                                          onPressed: () =>
                                              Navigator.of(context).pop(false),
                                          child: Text(l10n.settingsGlossaryCancel),
                                        ),
                                        FilledButton(
                                          onPressed: () =>
                                              Navigator.of(context).pop(true),
                                          style: FilledButton.styleFrom(
                                            backgroundColor: Theme.of(context)
                                                .colorScheme
                                                .error,
                                            foregroundColor: Theme.of(context)
                                                .colorScheme
                                                .onError,
                                          ),
                                          child: Text(l10n.settingsGlossaryDelete),
                                        ),
                                      ],
                                    ),
                                  );
                                  if (confirm != true) return;
                                  try {
                                    await GlossaryApiService.deleteGlossary(
                                      selectedId!,
                                    );
                                    // refresh list and selection
                                    final List<Map<String, dynamic>> list =
                                        await GlossaryApiService
                                            .getSimpleGlossaryList();
                                    if (list.isNotEmpty) {
                                      final String firstId =
                                          list.first['id'] as String;
                                      notifier.setSelectedGlossaryId(firstId);
                                      await _loadEntriesForGlossary(
                                        context,
                                        notifier,
                                        firstId,
                                        settings,
                                      );
                                    } else {
                                      notifier.clearSelectedGlossaryId();
                                      notifier.setGlossaryEntries(
                                        const <GlossaryEntry>[],
                                      );
                                    }
                                    if (context.mounted) {
                                      _showCopyableSnackBar(
                                        context,
                                        AppLocalizations.of(context)!
                                            .settingsGlossaryDeletedSnack(selectedId),
                                      );
                                    }
                                  } catch (e) {
                                    if (context.mounted) {
                                      _showCopyableSnackBar(
                                        context,
                                        AppLocalizations.of(context)!
                                            .settingsGlossaryDeleteFailedSnack(
                                          e.toString(),
                                        ),
                                      );
                                    }
                                  }
                                },
                          icon: Icon(Icons.delete_forever,
                              color: Theme.of(context).colorScheme.error,),
                          label: Text(AppLocalizations.of(context)!
                              .settingsGlossaryDeleteGlossary,),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Theme.of(context).colorScheme.error,
                            side: BorderSide(
                              color: Theme.of(context).colorScheme.error,
                            ),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 16, vertical: 12,),
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ],
          ),
        ),
      );

  Widget _buildGlossaryEntriesSection(
    BuildContext context,
    GlossarySettings settings,
    GlossarySettingsNotifier notifier,
  ) =>
      Card(
        elevation: 4,
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(Icons.table_chart,
                      color: Theme.of(context).colorScheme.primary,),
                  const SizedBox(width: 8),
                  Text(
                    AppLocalizations.of(context)!
                        .settingsGlossaryEntriesTitle(
                      settings.glossaryEntries.length,
                    ),
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                  const Spacer(),
                  FilledButton.icon(
                    onPressed: () =>
                        _showAddEntryDialog(context, settings, notifier),
                    icon: const Icon(Icons.add),
                    label: Text(AppLocalizations.of(context)!
                        .settingsGlossaryAddEntry,),

                  ),
                ],
              ),
              const SizedBox(height: 16),
              // Category filter (optional)
              if (settings.glossaryEntries.isNotEmpty) ...<Widget>[
                _buildCategoryFilter(context, settings, notifier),
                const SizedBox(height: 16),
              ],
              if (settings.glossaryEntries.isEmpty)
                Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(
                      AppLocalizations.of(context)!
                          .settingsGlossaryNoEntriesYet,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 16,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                )
              else
                _buildEditableTable(context, settings, notifier),
            ],
          ),
        ),
      );

  // Language selector removed - entries have their own language information

  String _formatTargetLanguage(String targetLang) {
    if (targetLang.isEmpty) {
      return '—';
    }
    final target = LanguageService.getLanguageByCode(targetLang);
    final targetName = target?.nativeName ?? targetLang.toUpperCase();
    return targetName;
  }

  Future<void> _loadEntriesForGlossary(
    BuildContext context,
    GlossarySettingsNotifier notifier,
    String glossaryId,
    GlossarySettings settings,
  ) async {
    try {
      final resp = await GlossaryApiService.listEntries(
        glossaryId,
      );
      final List<dynamic> entries = resp['entries'] as List? ?? <dynamic>[];
      final mapped = entries
          .map(
            (e) => GlossaryEntry(
              id: e['id']?.toString() ?? '${e['src']}_${e['category'] ?? ''}',
              sourceText: e['src'] ?? '',
              targetText: e['dst'] ?? '',
              targetLanguage: e['target_lang'] ?? settings.targetLanguage,
              category: (e['category'] ?? '').toString(),
            ),
          )
          .toList();
      notifier.setGlossaryEntries(List<GlossaryEntry>.from(mapped));
      if (context.mounted) {
      _showCopyableSnackBar(
        context,
        AppLocalizations.of(context)!.settingsGlossaryLoadedSnack(mapped.length),
      );
    }
    } catch (e) {
      if (context.mounted) {
        _showCopyableSnackBar(
          context,
          AppLocalizations.of(context)!.settingsGlossaryLoadFailedSnack(e.toString()),
        );
      }
    }
  }

  void _showCreateGlossaryDialog(BuildContext context) {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    bool isGlobal = true;
    final l10n = AppLocalizations.of(context)!;
    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: Text(l10n.settingsGlossaryCreateDialogTitle),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              TextField(
                controller: nameController,
                decoration: InputDecoration(
                    labelText: l10n.settingsGlossaryNameLabel,),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: descController,
                decoration: InputDecoration(
                    labelText: l10n.settingsGlossaryDescriptionLabel,),
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                value: isGlobal,
                onChanged: (bool v) => setState(() => isGlobal = v),
                title: Text(l10n.settingsGlossaryGlobalGlossary),
                subtitle: Text(l10n.settingsGlossaryGlobalGlossarySubtitle),
              ),
            ],
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10n.settingsGlossaryCancel),
            ),
            FilledButton(
              onPressed: () async {
                final String name = nameController.text.trim();
                if (name.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                        content: Text(l10n.settingsGlossaryNameRequired),),
                  );
                  return;
                }
                try {
                  final Map<String, dynamic> resp =
                      await GlossaryApiService.createEmptyGlossary(
                    name: name,
                    isGlobal: isGlobal,
                    description: descController.text.trim(),
                  );
                  if (context.mounted) {
                    Navigator.of(context).pop();
                    _showCopyableSnackBar(
                      context,
                      l10n.settingsGlossaryCreatedSnack(
                        resp['glossary_name']?.toString() ?? name,
                      ),
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    _showCopyableSnackBar(
                      context,
                      l10n.settingsGlossaryCreateFailedSnack(e.toString()),
                    );
                  }
                }
              },
              child: Text(l10n.settingsGlossaryCreate),
            ),
          ],
        ),
      ),
    );
  }

  void _showCopyableSnackBar(BuildContext context, String message) {
    final l10n = AppLocalizations.of(context)!;
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      SnackBar(
        content: Text(message),
        action: SnackBarAction(
          label: l10n.settingsGlossaryCopyAction,
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: message));
            messenger.showSnackBar(
              SnackBar(content: Text(l10n.settingsGlossaryCopiedToClipboard)),
            );
          },
        ),
      ),
    );
  }

  static const String _kFilterAll = '__all__';
  static const String _kFilterUncategorized = '__uncategorized__';

  Widget _buildCategoryFilter(
    BuildContext context,
    GlossarySettings settings,
    GlossarySettingsNotifier notifier,
  ) {
    final l10n = AppLocalizations.of(context)!;
    final categorySet = <String>{};
    for (final entry in settings.glossaryEntries) {
      if (entry.category.isNotEmpty) {
        categorySet.add(entry.category);
      }
    }
    final categories = categorySet.toList()..sort();

    final filterOptions = <String>[_kFilterAll, _kFilterUncategorized, ...categories];

    String? validValue = settings.selectedCategoryFilter;
    if (validValue != null && !filterOptions.contains(validValue)) {
      validValue = _kFilterAll;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        notifier.setCategoryFilter(_kFilterAll);
      });
    }

    final colorScheme = Theme.of(context).colorScheme;
    return Row(
      children: <Widget>[
        Icon(Icons.filter_list, color: colorScheme.onSurfaceVariant),
        const SizedBox(width: 8),
        Text(l10n.settingsGlossaryFilterLabel,
            style: const TextStyle(fontWeight: FontWeight.w500),),
        const SizedBox(width: 12),
        Expanded(
          child: DropdownButtonFormField<String>(
            initialValue: validValue,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            ),
            items: filterOptions
                .map(
                  (category) => DropdownMenuItem<String>(
                    value: category,
                    child: Text(
                      category == _kFilterAll
                          ? l10n.settingsGlossaryFilterAll
                          : (category == _kFilterUncategorized
                              ? l10n.settingsGlossaryFilterUncategorized
                              : category),
                    ),
                  ),
                )
                .toList(),
            onChanged: (value) {
              notifier.setCategoryFilter(value ?? _kFilterAll);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildEditableTable(
    BuildContext context,
    GlossarySettings settings,
    GlossarySettingsNotifier notifier,
  ) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    // Filter entries based on selected category only (language filter removed)
    final filteredEntries = _filterEntriesByCategory(
      settings.glossaryEntries,
      settings.selectedCategoryFilter,
    );

    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: <Widget>[
          // Table header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(8),
                topRight: Radius.circular(8),
              ),
            ),
            child: Row(
              children: <Widget>[
                Expanded(
                  flex: 2,
                  child: Text(
                    AppLocalizations.of(context)!.settingsGlossaryTableSource,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onSurface,
                    ),
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: Text(
                    AppLocalizations.of(context)!.settingsGlossaryTableTarget,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onSurface,
                    ),
                  ),
                ),
                Expanded(
                  child: Text(
                    AppLocalizations.of(context)!.settingsGlossaryTableCategory,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onSurface,
                    ),
                  ),
                ),
                Expanded(
                  child: Text(
                    AppLocalizations.of(context)!.settingsGlossaryTableTargetLang,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onSurface,
                      fontSize: 12,
                    ),
                  ),
                ),
                const SizedBox(width: 60), // Space for active toggle
                const SizedBox(width: 100), // Space for actions
              ],
            ),
          ),
          // Table rows
          ...filteredEntries.asMap().entries.map((entry) {
            final index = entry.key;
            final glossaryEntry = entry.value;
            return _buildTableRow(
              context,
              index,
              glossaryEntry,
              settings,
              notifier,
            );
          }),
        ],
      ),
    );
  }

  List<GlossaryEntry> _filterEntriesByCategory(
    List<GlossaryEntry> entries,
    String? categoryFilter,
  ) {
    if (categoryFilter == null || categoryFilter == _kFilterAll) {
      return entries;
    }
    if (categoryFilter == _kFilterUncategorized) {
      return entries.where((e) => e.category.isEmpty).toList();
    }
    return entries.where((e) => e.category == categoryFilter).toList();
  }

  Widget _buildTableRow(
    BuildContext context,
    int index,
    GlossaryEntry entry,
    GlossarySettings settings,
    GlossarySettingsNotifier notifier,
  ) {
    final sourceController = TextEditingController(text: entry.source);
    final targetController = TextEditingController(text: entry.target);
    final categoryController = TextEditingController(text: entry.category);
    bool isEditing = false;

    final colorScheme = Theme.of(context).colorScheme;
    return StatefulBuilder(
      builder: (context, setState) => DecoratedBox(
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: colorScheme.outlineVariant),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: <Widget>[
              Expanded(
                flex: 2,
                child: isEditing
                    ? TextField(
                        controller: sourceController,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          contentPadding:
                              EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        ),
                      )
                    : Text(
                        entry.source,
                        style: const TextStyle(fontSize: 14),
                      ),
              ),
              const SizedBox(width: 16),
              Expanded(
                flex: 2,
                child: isEditing
                    ? TextField(
                        controller: targetController,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          contentPadding:
                              EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        ),
                      )
                    : Text(
                        entry.target,
                        style: const TextStyle(fontSize: 14),
                      ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: isEditing
                    ? TextField(
                        controller: categoryController,
                        decoration: InputDecoration(
                          border: const OutlineInputBorder(),
                          contentPadding:
                              const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          hintText: AppLocalizations.of(context)!
                              .settingsGlossaryCategoryHint,
                        ),
                      )
                    : Text(
                        entry.category.isEmpty
                            ? AppLocalizations.of(context)!
                                .settingsGlossaryUncategorizedDisplay
                            : entry.category,
                        style: TextStyle(
                          fontSize: 14,
                          color: entry.category.isEmpty
                              ? colorScheme.onSurfaceVariant
                              : colorScheme.onSurface,
                          fontStyle: entry.category.isEmpty
                              ? FontStyle.italic
                              : FontStyle.normal,
                        ),
                      ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Text(
                  _formatTargetLanguage(entry.targetLanguage),
                  style: TextStyle(
                    fontSize: 11,
                    color: colorScheme.onSurfaceVariant,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              SizedBox(
                width: 60,
                child: Switch(
                  value: entry.isActive,
                  onChanged: (bool value) {
                    notifier
                        .updateGlossaryEntry(entry.copyWith(isActive: value));
                  },
                ),
              ),
              const SizedBox(width: 16),
              SizedBox(
                width: 100,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    if (isEditing) ...<Widget>[
                      IconButton(
                        icon: Icon(Icons.check,
                            color: Theme.of(context).colorScheme.primary,),
                        onPressed: () async {
                          try {
                            await GlossaryApiService.updateEntry(
                              settings.selectedGlossaryId ?? '',
                              entry.id,
                              src: sourceController.text.trim(),
                              dst: targetController.text.trim(),
                              category: categoryController.text.trim(),
                            );
                            notifier.updateGlossaryEntry(
                              entry.copyWith(
                                sourceText: sourceController.text.trim(),
                                targetText: targetController.text.trim(),
                                category: categoryController.text.trim(),
                              ),
                            );
                            setState(() => isEditing = false);
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(AppLocalizations.of(context)!
                                    .settingsGlossaryEntryUpdatedSnack,),
                              ),
                            );
                          } catch (e) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(AppLocalizations.of(context)!
                                    .settingsGlossaryUpdateFailedSnack(e.toString()),),
                              ),
                            );
                          }
                        },
                      ),
                      IconButton(
                        icon: Icon(Icons.close,
                            color: Theme.of(context).colorScheme.error,),
                        onPressed: () {
                          sourceController.text = entry.source;
                          targetController.text = entry.target;
                          categoryController.text = entry.category;
                          setState(() => isEditing = false);
                        },
                      ),
                    ] else ...<Widget>[
                      IconButton(
                        icon: Icon(Icons.edit,
                            color: Theme.of(context).colorScheme.primary,),
                        onPressed: () => setState(() => isEditing = true),
                      ),
                      IconButton(
                        icon: Icon(Icons.delete,
                            color: Theme.of(context).colorScheme.error,),
                        onPressed: () async {
                          try {
                            await GlossaryApiService.deleteEntry(
                              settings.selectedGlossaryId ?? '',
                              entry.id,
                            );
                            notifier.removeGlossaryEntry(entry.id);
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(AppLocalizations.of(context)!
                                    .settingsGlossaryEntryDeletedSnack,),
                              ),
                            );
                          } catch (e) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(AppLocalizations.of(context)!
                                    .settingsGlossaryDeleteEntryFailedSnack(e.toString()),),
                              ),
                            );
                          }
                        },
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showAddEntryDialog(
    BuildContext context,
    GlossarySettings settings,
    GlossarySettingsNotifier notifier,
  ) {
    final srcController = TextEditingController();
    final dstController = TextEditingController();
    final categoryController = TextEditingController();
    // Language removed - entries will have empty language info (can be inferred from context)

    // Create future outside dialog to avoid recreation on each rebuild
    final glossariesFuture = GlossaryApiService.getSimpleGlossaryList();
    // State variables outside builder to persist across rebuilds
    String? selectedGlossaryId = settings.selectedGlossaryId;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (BuildContext context, setState) {
          final l10n = AppLocalizations.of(context)!;
          return AlertDialog(
          title: Text(l10n.settingsGlossaryAddEntryDialogTitle),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                FutureBuilder<List<Map<String, dynamic>>>(
                  future: glossariesFuture,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState == ConnectionState.waiting) {
                      return const CircularProgressIndicator();
                    }
                    if (snapshot.hasError) {
                      return Text(l10n.settingsGlossaryErrorPrefix(
                        snapshot.error.toString(),
                      ),);
                    }
                    final glossaries =
                        snapshot.data ?? <Map<String, dynamic>>[];
                    // Use currently selected glossary if it exists in the list, otherwise use first one
                    if (selectedGlossaryId == null && glossaries.isNotEmpty) {
                      selectedGlossaryId = glossaries.first['id'] as String;
                    } else if (selectedGlossaryId != null) {
                      // Verify selected glossary still exists in the list
                      final exists =
                          glossaries.any((g) => g['id'] == selectedGlossaryId);
                      if (!exists && glossaries.isNotEmpty) {
                        selectedGlossaryId = glossaries.first['id'] as String;
                      }
                    }
                    return DropdownButtonFormField<String>(
                      initialValue: selectedGlossaryId,
                      decoration: InputDecoration(
                          labelText: l10n.settingsGlossarySelectGlossary,),
                      items: glossaries
                          .map(
                            (glossary) => DropdownMenuItem<String>(
                              value: glossary['id'] as String,
                              child: Text(
                                '${glossary['name']} (${glossary['type']})',
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (value) {
                        setState(() {
                          selectedGlossaryId = value;
                        });
                      },
                    );
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: srcController,
                  decoration: InputDecoration(
                      labelText: l10n.settingsGlossarySourceTextLabel,),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: dstController,
                  decoration: InputDecoration(
                      labelText: l10n.settingsGlossaryTargetTextLabel,),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: categoryController,
                  decoration: InputDecoration(
                    labelText: l10n.settingsGlossaryCategoryOptionalLabel,
                    hintText: l10n.settingsGlossaryCategoryOptionalHint,
                  ),
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10n.settingsGlossaryCancel),
            ),
            Builder(
              builder: (ctx) {
                final l10nCtx = AppLocalizations.of(ctx)!;
                return FilledButton(
                onPressed: selectedGlossaryId == null
                    ? null
                    : () async {
                        if (srcController.text.trim().isEmpty ||
                            dstController.text.trim().isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                l10nCtx.settingsGlossarySourceTargetRequired,
                              ),
                            ),
                          );
                          return;
                        }
                        try {
                          await GlossaryApiService.createEntry(
                            selectedGlossaryId!,
                            src: srcController.text.trim(),
                            dst: dstController.text.trim(),
                            category: categoryController.text.trim(),
                            targetLang: settings
                                .targetLanguage, // Use settings target language
                          );
                          // reload entries so that new category appears in filter
                          await _loadEntriesForGlossary(
                            context,
                            notifier,
                            selectedGlossaryId!,
                            settings,
                          );
                          if (context.mounted) {
                            Navigator.of(context).pop();
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                    l10nCtx.settingsGlossaryEntryAddedSnack,),
                              ),
                            );
                          }
                        } catch (e) {
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                  l10nCtx.settingsGlossaryAddFailedSnack(
                                    e.toString(),
                                  ),
                                ),
                              ),
                            );
                          }
                        }
                      },
                child: Text(l10nCtx.settingsGlossaryAdd),
              );
              },
            ),
          ],
        );
        },
      ),
    );
  }

  void _showImportDialog(
    BuildContext context,
    GlossarySettings settings,
    GlossarySettingsNotifier notifier,
  ) {
    // Create future outside dialog to avoid recreation on each rebuild
    final glossariesFuture = GlossaryApiService.getSimpleGlossaryList();
    // State variables outside builder to persist across rebuilds
    String? selectedGlossaryId = settings.selectedGlossaryId;
    String mergeMode = 'update';

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (BuildContext context, setState) {
          final l10nImport = AppLocalizations.of(context)!;
          return AlertDialog(
          title: Text(l10nImport.settingsGlossaryImportDialogTitle),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              FutureBuilder<List<Map<String, dynamic>>>(
                future: glossariesFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const CircularProgressIndicator();
                  }
                  if (snapshot.hasError) {
                    return Text(l10nImport.settingsGlossaryErrorPrefix(
                      snapshot.error.toString(),
                    ),);
                  }
                  final glossaries = snapshot.data ?? <Map<String, dynamic>>[];
                  // Use currently selected glossary if it exists in the list, otherwise use first one
                  if (selectedGlossaryId == null && glossaries.isNotEmpty) {
                    selectedGlossaryId = glossaries.first['id'] as String;
                  } else if (selectedGlossaryId != null) {
                    // Verify selected glossary still exists in the list
                    final exists =
                        glossaries.any((g) => g['id'] == selectedGlossaryId);
                    if (!exists && glossaries.isNotEmpty) {
                      selectedGlossaryId = glossaries.first['id'] as String;
                    }
                  }
                  return DropdownButtonFormField<String>(
                    initialValue: selectedGlossaryId,
                    decoration: InputDecoration(
                        labelText: l10nImport.settingsGlossarySelectGlossary,),
                    items: glossaries
                        .map(
                          (glossary) => DropdownMenuItem<String>(
                            value: glossary['id'] as String,
                            child: Text(
                              '${glossary['name']} (${glossary['type']})',
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      setState(() {
                        selectedGlossaryId = value;
                      });
                    },
                  );
                },
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: mergeMode,
                items: <DropdownMenuItem<String>>[
                  DropdownMenuItem(
                    value: 'update',
                    child: Text(l10nImport.settingsGlossaryMergeUpdate),
                  ),
                  DropdownMenuItem(
                    value: 'append',
                    child: Text(l10nImport.settingsGlossaryMergeAppend),
                  ),
                  DropdownMenuItem(
                    value: 'replace',
                    child: Text(l10nImport.settingsGlossaryMergeReplace),
                  ),
                ],
                onChanged: (v) {
                  setState(() {
                    mergeMode = v ?? 'update';
                  });
                },
                decoration: InputDecoration(
                    labelText: l10nImport.settingsGlossaryMergeModeLabel,),
              ),
            ],
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10nImport.settingsGlossaryCancel),
            ),
            Builder(
              builder: (btnContext) {
                final l10nBtn = AppLocalizations.of(btnContext)!;
                return FilledButton(
                onPressed: selectedGlossaryId == null
                    ? null
                    : () async {
                        try {
                          final result = await FilePickerHelper.pickFiles(
                            type: FileType.custom,
                            allowedExtensions: <String>['csv'],
                          );
                          if (result == null) return;
                          final bytes = result.files.single.bytes;
                          if (bytes == null) {
                            ScaffoldMessenger.of(btnContext).showSnackBar(
                              SnackBar(
                                content: Text(
                                    l10nBtn.settingsGlossaryUnableToReadFile,),
                              ),
                            );
                            return;
                          }
                          final resp = await GlossaryApiService.importCsv(
                            selectedGlossaryId!,
                            bytes,
                            mergeMode: mergeMode,
                          );
                          await _loadEntriesForGlossary(
                            btnContext,
                            notifier,
                            selectedGlossaryId!,
                            settings,
                          );
                          if (btnContext.mounted) {
                            Navigator.of(btnContext).pop();
                            ScaffoldMessenger.of(btnContext).showSnackBar(
                              SnackBar(
                                content: Text(
                                  l10nBtn.settingsGlossaryImportedSnack(
                                    (resp['imported_count'] ?? 0).toString(),
                                  ),
                                ),
                              ),
                            );
                          }
                        } catch (e) {
                          if (btnContext.mounted) {
                            ScaffoldMessenger.of(btnContext).showSnackBar(
                              SnackBar(
                                content: Text(
                                  l10nBtn.settingsGlossaryImportFailedSnack(
                                    e.toString(),
                                  ),
                                ),
                              ),
                            );
                          }
                        }
                      },
                child: Text(l10nBtn.settingsGlossaryImport),
              );
              },
            ),
          ],
        );
        },
      ),
    );
  }

  void _showExportDialog(BuildContext context, GlossarySettings settings) {
    // Create future outside dialog to avoid recreation on each rebuild
    final glossariesFuture = GlossaryApiService.getSimpleGlossaryList();
    // State variables outside builder to persist across rebuilds
    String? selectedGlossaryId = settings.selectedGlossaryId;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (BuildContext context, setState) {
          final l10nExport = AppLocalizations.of(context)!;
          return AlertDialog(
          title: Text(l10nExport.settingsGlossaryExportDialogTitle),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              FutureBuilder<List<Map<String, dynamic>>>(
                future: glossariesFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const CircularProgressIndicator();
                  }
                  if (snapshot.hasError) {
                    return Text(l10nExport.settingsGlossaryErrorPrefix(
                      snapshot.error.toString(),
                    ),);
                  }
                  final glossaries = snapshot.data ?? <Map<String, dynamic>>[];
                  if (selectedGlossaryId == null && glossaries.isNotEmpty) {
                    selectedGlossaryId = glossaries.first['id'] as String;
                  } else if (selectedGlossaryId != null) {
                    final exists =
                        glossaries.any((g) => g['id'] == selectedGlossaryId);
                    if (!exists && glossaries.isNotEmpty) {
                      selectedGlossaryId = glossaries.first['id'] as String;
                    }
                  }
                  return DropdownButtonFormField<String>(
                    initialValue: selectedGlossaryId,
                    decoration: InputDecoration(
                        labelText: l10nExport.settingsGlossarySelectGlossary,),
                    items: glossaries
                        .map(
                          (glossary) => DropdownMenuItem<String>(
                            value: glossary['id'] as String,
                            child: Text(
                              '${glossary['name']} (${glossary['type']}) - ${glossary['item_count']} items',
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      setState(() {
                        selectedGlossaryId = value;
                      });
                    },
                  );
                },
              ),
            ],
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l10nExport.settingsGlossaryCancel),
            ),
            Builder(
              builder: (btnContext) {
                final l10nBtn = AppLocalizations.of(btnContext)!;
                return FilledButton(
                onPressed: selectedGlossaryId == null
                    ? null
                    : () async {
                        try {
                          final data = await GlossaryApiService.downloadCsv(
                            selectedGlossaryId!,
                          );
                          final baseName =
                              'glossary_${DateTime.now().millisecondsSinceEpoch}';
                          if (kIsWeb) {
                            await FileSaver.instance.saveFile(
                              name: baseName,
                              bytes: data,
                              ext: 'csv',
                            );
                          } else {
                            final savePath = await FilePickerHelper.saveFile(
                              fileName: '$baseName.csv',
                              dialogTitle: l10nBtn.settingsGlossarySaveCsv,
                              type: FileType.custom,
                              allowedExtensions: <String>['csv'],
                            );
                            if (savePath != null) {
                              // ignore: avoid_print
                              print('[ExportCurrent] Saved to: $savePath');
                              final f = File(savePath);
                              await f.writeAsBytes(data, flush: true);
                            }
                          }
                          if (btnContext.mounted) {
                            Navigator.of(btnContext).pop();
                            _showCopyableSnackBar(
                              btnContext,
                              l10nBtn.settingsGlossaryDownloadedSnack(
                                '${kIsWeb ? baseName : 'CSV file'} (${data.lengthInBytes} bytes)',
                              ),
                            );
                          }
                        } catch (e) {
                          if (btnContext.mounted) {
                            ScaffoldMessenger.of(btnContext).showSnackBar(
                              SnackBar(
                                content: Text(
                                  l10nBtn.settingsGlossaryExportFailedSnack(
                                    e.toString(),
                                  ),
                                ),
                              ),
                            );
                          }
                        }
                      },
                child: Text(l10nBtn.settingsGlossaryDownload),
              );
              },
            ),
          ],
        );
        },
      ),
    );
  }
}
