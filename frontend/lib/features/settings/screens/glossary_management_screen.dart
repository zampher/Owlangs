// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/services/glossary_management_service.dart';

/// 术语表管理页面
class GlossaryManagementScreen extends ConsumerStatefulWidget {
  const GlossaryManagementScreen({super.key});

  @override
  ConsumerState<GlossaryManagementScreen> createState() =>
      _GlossaryManagementScreenState();
}

class _GlossaryManagementScreenState
    extends ConsumerState<GlossaryManagementScreen> {
  List<Glossary> _glossaries = <Glossary>[];
  bool _isLoading = false;
  String _selectedGlossaryId = '';
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _loadGlossaries();
  }

  /// 加载术语表列表
  Future<void> _loadGlossaries() async {
    setState(() {
      _isLoading = true;
    });

    try {
      final glossaries = await GlossaryManagementService.getAllGlossaries();
      setState(() {
        _glossaries = glossaries;
        if (glossaries.isNotEmpty && _selectedGlossaryId.isEmpty) {
          _selectedGlossaryId = glossaries.first.id;
        }
      });
    } catch (e) {
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.glossaryErrorRefresh(e.toString()))),
        );
      }
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  /// 获取当前选中的术语表
  Glossary? get _selectedGlossary {
    if (_selectedGlossaryId.isEmpty) return null;
    return _glossaries.firstWhere(
      (g) => g.id == _selectedGlossaryId,
      orElse: () =>
          _glossaries.isNotEmpty ? _glossaries.first : _glossaries.first,
    );
  }

  /// 获取过滤后的条目
  List<GlossaryEntry> get _filteredEntries {
    final glossary = _selectedGlossary;
    if (glossary == null) return <GlossaryEntry>[];

    if (_searchQuery.isEmpty) {
      return glossary.entries;
    }

    return glossary.entries
        .where(
          (entry) =>
              entry.source.toLowerCase().contains(_searchQuery.toLowerCase()) ||
              entry.target.toLowerCase().contains(_searchQuery.toLowerCase()) ||
              entry.category.toLowerCase().contains(_searchQuery.toLowerCase()),
        )
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
        appBar: AppBar(
          title: Text(l10n.settingsGlossaryManagementTitle),
          actions: <Widget>[
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _loadGlossaries,
            ),
          ],
        ),
        body: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : Column(
                children: <Widget>[
                  // Glossary selector
                  Container(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: <Widget>[
                        Text('${l10n.settingsGlossarySelectGlossary}: '),
                        Expanded(
                          child: DropdownButton<String>(
                            value: _selectedGlossaryId.isEmpty
                                ? null
                                : _selectedGlossaryId,
                            hint: Text(l10n.settingsGlossarySelectGlossary),
                            items: _glossaries
                                .map(
                                  (Glossary glossary) =>
                                      DropdownMenuItem<String>(
                                    value: glossary.id,
                                    child: Row(
                                      children: <Widget>[
                                        Icon(
                                          glossary.isSystem
                                              ? Icons.public
                                              : Icons.person,
                                          size: 16,
                                          color: glossary.isSystem
                                              ? Colors.blue
                                              : Colors.green,
                                        ),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: Text(
                                            '${glossary.name} (${glossary.entryCount}条)',
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                )
                                .toList(),
                            onChanged: (String? value) {
                              setState(() {
                                _selectedGlossaryId = value ?? '';
                                _searchQuery = '';
                              });
                            },
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Search box
                  if (_selectedGlossary != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: TextField(
                        decoration: InputDecoration(
                          hintText: l10n.settingsGlossaryFilterLabel,
                          prefixIcon: const Icon(Icons.search),
                          border: const OutlineInputBorder(),
                        ),
                        onChanged: (String value) {
                          setState(() {
                            _searchQuery = value;
                          });
                        },
                      ),
                    ),

                  // Glossary info
                  if (_selectedGlossary != null)
                    Container(
                      padding: const EdgeInsets.all(16),
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Row(
                                children: <Widget>[
                                  Icon(
                                    _selectedGlossary!.isSystem
                                        ? Icons.public
                                        : Icons.person,
                                    color: _selectedGlossary!.isSystem
                                        ? Colors.blue
                                        : Colors.green,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    _selectedGlossary!.name,
                                    style: const TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                              if (_selectedGlossary!
                                  .description.isNotEmpty) ...<Widget>[
                                const SizedBox(height: 8),
                                Text(
                                  _selectedGlossary!.description,
                                  style: TextStyle(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                                ),
                              ],
                              const SizedBox(height: 8),
                              Text(
                                l10n.settingsGlossaryEntryCount(
                                    _selectedGlossary!.entryCount.toString(),),
                                style: TextStyle(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),

                  // Glossary entries list
                  Expanded(
                    child: _selectedGlossary == null
                        ? Center(
                            child: Text(l10n.settingsGlossarySelectGlossary),
                          )
                        : _filteredEntries.isEmpty
                            ? Center(
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: <Widget>[
                                    Icon(
                                      Icons.list_alt,
                                      size: 64,
                                      color: Theme.of(context)
                                          .colorScheme
                                          .onSurfaceVariant,
                                    ),
                                    const SizedBox(height: 16),
                                    Text(
                                      _searchQuery.isEmpty
                                          ? l10n.settingsGlossaryNoEntriesYet
                                          : l10n.glossaryCsvNoValidEntries,
                                      style: TextStyle(
                                        color: Theme.of(context)
                                            .colorScheme
                                            .onSurfaceVariant,
                                        fontSize: 16,
                                      ),
                                    ),
                                  ],
                                ),
                              )
                            : ListView.builder(
                                itemCount: _filteredEntries.length,
                                itemBuilder: (BuildContext context, int index) {
                                  final GlossaryEntry entry =
                                      _filteredEntries[index];
                                  return Card(
                                    margin: const EdgeInsets.symmetric(
                                      horizontal: 16,
                                      vertical: 4,
                                    ),
                                    child: ListTile(
                                      title: Text(entry.source),
                                      subtitle: Text(entry.target),
                                      trailing: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: <Widget>[
                                          if (entry.category.isNotEmpty)
                                            Chip(
                                              label: Text(entry.category),
                                              backgroundColor: Theme.of(context)
                                                  .colorScheme
                                                  .primaryContainer,
                                              labelStyle: TextStyle(
                                                color: Theme.of(context)
                                                    .colorScheme
                                                    .onPrimaryContainer,
                                                fontSize: 12,
                                              ),
                                            ),
                                          const SizedBox(width: 8),
                                          PopupMenuButton<String>(
                                            onSelected: (String value) {
                                              if (value == 'edit') {
                                                _onEditEntry(entry);
                                              } else if (value == 'delete') {
                                                _onDeleteEntry(entry);
                                              }
                                            },
                                            itemBuilder:
                                                (BuildContext context) =>
                                                    <PopupMenuEntry<String>>[
                                              PopupMenuItem<String>(
                                                value: 'edit',
                                                child: Row(
                                                  children: <Widget>[
                                                    const Icon(Icons.edit),
                                                    const SizedBox(width: 8),
                                                    Text(l10n.settingsGlossaryEdit),
                                                  ],
                                                ),
                                              ),
                                              PopupMenuItem<String>(
                                                value: 'delete',
                                                child: Row(
                                                  children: <Widget>[
                                                    const Icon(Icons.delete),
                                                    const SizedBox(width: 8),
                                                    Text(l10n.settingsGlossaryDelete),
                                                  ],
                                                ),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ),
                                    ),
                                  );
                                },
                              ),
                  ),
                ],
              ),
        floatingActionButton:
            _selectedGlossary != null && !_selectedGlossary!.isSystem
                ? FloatingActionButton(
                    onPressed: _addEntry,
                    child: const Icon(Icons.add),
                  )
                : null,
      );
  }

  /// 添加条目
  void _addEntry() {
    _showEntryDialog();
  }

  /// 编辑条目
  void _onEditEntry(GlossaryEntry entry) {
    _showEntryDialog(entry: entry);
  }

  /// Delete glossary entry
  void _onDeleteEntry(GlossaryEntry entry) {
    final l10n = AppLocalizations.of(context)!;
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.settingsGlossaryConfirmDeleteEntryTitle),
        content: Text(
            l10n.settingsGlossaryConfirmDeleteEntryMessage(entry.source),),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l10n.settingsGlossaryCancel),
          ),
          TextButton(
            onPressed: () async {
              Navigator.of(context).pop();
              final success =
                  await GlossaryManagementService.deleteGlossaryEntry(
                glossaryId: entry.glossaryId,
                entryId: entry.id,
              );
              if (success) {
                _loadGlossaries();
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                        content: Text(l10n.settingsGlossaryEntryDeletedSnack),),
                  );
                }
              } else {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                        content: Text(
                            l10n.settingsGlossaryEntryDeleteFailedSnack,),),
                  );
                }
              }
            },
            child: Text(l10n.settingsGlossaryDelete),
          ),
        ],
      ),
    );
  }

  /// Show add/edit entry dialog
  void _showEntryDialog({GlossaryEntry? entry}) {
    final l10n = AppLocalizations.of(context)!;
    final sourceController = TextEditingController(text: entry?.source ?? '');
    final targetController = TextEditingController(text: entry?.target ?? '');
    final categoryController =
        TextEditingController(text: entry?.category ?? '');

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(entry == null
            ? l10n.settingsGlossaryAddEntryDialogTitle
            : l10n.settingsGlossaryEditEntryDialogTitle,),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            TextField(
              controller: sourceController,
              decoration: InputDecoration(
                labelText: l10n.settingsGlossarySourceTextLabel,
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: targetController,
              decoration: InputDecoration(
                labelText: l10n.settingsGlossaryTargetTextLabel,
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: categoryController,
              decoration: InputDecoration(
                labelText: l10n.settingsGlossaryCategoryOptionalLabel,
                border: const OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(l10n.settingsGlossaryCancel),
          ),
          TextButton(
            onPressed: () async {
              if (sourceController.text.isEmpty ||
                  targetController.text.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                      content: Text(l10n.settingsGlossarySourceTargetRequired),),
                );
                return;
              }

              Navigator.of(context).pop();

              final success = entry == null
                  ? await GlossaryManagementService.addGlossaryEntry(
                      glossaryId: _selectedGlossaryId,
                      source: sourceController.text,
                      target: targetController.text,
                      category: categoryController.text,
                    )
                  : await GlossaryManagementService.updateGlossaryEntry(
                      glossaryId: entry.glossaryId,
                      entryId: entry.id,
                      source: sourceController.text,
                      target: targetController.text,
                      category: categoryController.text,
                    );

              if (success) {
                _loadGlossaries();
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(entry == null
                          ? l10n.settingsGlossaryEntryAddedSnack
                          : l10n.settingsGlossaryEntryUpdatedSnack,),
                    ),
                  );
                }
              } else {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(entry == null
                          ? l10n.settingsGlossaryAddFailedSnack('')
                          : l10n.settingsGlossaryUpdateFailedSnack(''),),
                    ),
                  );
                }
              }
            },
            child: Text(entry == null
                ? l10n.settingsGlossaryAdd
                : l10n.settingsGlossaryUpdate,),
          ),
        ],
      ),
    );
  }
}
