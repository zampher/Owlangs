// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/app_localizations.dart';
import 'dart:typed_data';
import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:file_saver/file_saver.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io' as io;
import '../../../core/utils/file_picker_helper.dart';
import 'package:desktop_drop/desktop_drop.dart'
    if (dart.library.html) 'package:owlangs/shared/widgets/desktop_drop_stub.dart';
import '../../../shared/utils/html_stub.dart' if (dart.library.html) 'dart:html'
    as html;
import '../../../shared/services/glossary_api_service.dart';
import '../../../shared/utils/app_logger.dart';
import '../../../shared/utils/message_service.dart';
import '../../tasks/models/flow.dart';
import '../../tasks/providers/flow_provider.dart';
import '../providers/translation_state_provider.dart';
import '../providers/translation_state_provider_family.dart';

/// Glossary entry model
class GlossaryEntry {
  GlossaryEntry({
    required this.source,
    required this.target,
    this.category = '',
    this.targetLang = '',
  });
  String source;
  String target;
  String category;
  String targetLang;
}

/// Glossary preview with editing capability
class GlossaryPreview extends ConsumerStatefulWidget {
  // Callback when editing state changes

  const GlossaryPreview({
    required this.glossaryId,
    required this.glossaryData,
    super.key,
    this.onSave,
    this.flowId,
    this.targetLang,
    this.onGenerateGlossary,
    this.onCancelGlossary,
    this.onEditingStateChanged,
  });
  final String glossaryId;
  final Map<String, dynamic>
      glossaryData; // Original glossary data (key-value pairs)
  final Function(Map<String, dynamic>)? onSave;
  final String? flowId; // Optional flowId for applying glossary to FlowContext
  final String? targetLang; // Optional target language for glossary entries
  final VoidCallback?
      onGenerateGlossary; // Callback to trigger AI glossary generation
  final VoidCallback?
      onCancelGlossary; // Callback to cancel glossary generation
  final Function(bool)? onEditingStateChanged;

  @override
  ConsumerState<GlossaryPreview> createState() => _GlossaryPreviewState();
}

class _GlossaryPreviewState extends ConsumerState<GlossaryPreview> {
  bool isEditing = false;
  late List<GlossaryEntry> entries;
  List<GlossaryEntry> originalEntries = <GlossaryEntry>[];
  bool _busy = false;
  List<Map<String, dynamic>> _globalGlossaries = <Map<String, dynamic>>[];
  final TextEditingController _glossaryNameCtrl = TextEditingController();
  String? _selectedGlossaryId; // Selected glossary ID (null means new glossary)
  final Set<int> _selectedEntryIndices =
      <int>{}; // Selected entry indices for batch deletion
  // Cache TextEditingControllers for editing mode to avoid recreation on every rebuild
  final Map<int, TextEditingController> _sourceControllers =
      <int, TextEditingController>{};
  final Map<int, TextEditingController> _targetControllers =
      <int, TextEditingController>{};
  // Use ValueNotifier for each checkbox to enable granular updates without full rebuild
  final Map<int, ValueNotifier<bool>> _selectionNotifiers =
      <int, ValueNotifier<bool>>{};

  void _log(String message, {LogLevel level = LogLevel.debug}) {
    AppLogger.log('GlossaryPreview', message, level: level);
  }

  /// Create a copy of a GlossaryEntry
  GlossaryEntry _copyEntry(GlossaryEntry entry) => GlossaryEntry(
        source: entry.source,
        target: entry.target,
        category: entry.category,
        targetLang: entry.targetLang,
      );

  /// Create a list of copied entries
  List<GlossaryEntry> _copyEntries(List<GlossaryEntry> entries) =>
      entries.map(_copyEntry).toList();

  /// Rebuild controllers and notifiers for all entries
  void _rebuildControllersAndNotifiers() {
    // Dispose old controllers and notifiers
    _disposeTextControllers();
    for (final notifier in _selectionNotifiers.values) {
      notifier.dispose();
    }
    _selectionNotifiers.clear();

    // Rebuild from scratch
    _initializeTextControllers();
    for (int i = 0; i < entries.length; i++) {
      _selectionNotifiers[i] = ValueNotifier<bool>(false);
    }
  }

  /// Get status color based on status text (matching translation progress bar style)
  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
        return Colors.green;
      case 'failed':
      case 'error':
        return Colors.red;
      case 'cancelled':
        return Colors.orange;
      default:
        return Colors.blue;
    }
  }

  @override
  void initState() {
    super.initState();
    _loadEntries();
  }

  @override
  void didUpdateWidget(GlossaryPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Reload entries if glossaryData changed
    final wasEmpty = oldWidget.glossaryData.isEmpty;
    final isEmpty = widget.glossaryData.isEmpty;
    final dataChanged =
        oldWidget.glossaryData.length != widget.glossaryData.length ||
            !_mapsEqual(oldWidget.glossaryData, widget.glossaryData);

    if (dataChanged) {
      _log('GlossaryData changed, reloading entries');
      _loadEntries();

      // Auto-enter edit mode when glossary generation completes (data changes from empty to non-empty)
      if (wasEmpty && !isEmpty && !isEditing) {
        _log('Glossary generation completed, auto-entering edit mode');
        // Defer setState and callback to after build completes to avoid "setState during build" error
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            setState(() {
              isEditing = true;
            });
            // Notify parent about editing state change
            if (widget.onEditingStateChanged != null) {
              widget.onEditingStateChanged!(true);
            }
            // Initialize TextEditingControllers for edit mode
            _initializeTextControllers();
          }
        });
      } else if (isEditing && entries.isNotEmpty) {
        // If already in edit mode and entries changed, reinitialize controllers
        _disposeTextControllers();
        _initializeTextControllers();
      }
    }
  }

  bool _mapsEqual(Map<String, dynamic> map1, Map<String, dynamic> map2) {
    if (map1.length != map2.length) return false;
    for (final key in map1.keys) {
      if (map1[key] != map2[key]) return false;
    }
    return true;
  }

  void _loadEntries() {
    // Dispose old selection notifiers
    for (final notifier in _selectionNotifiers.values) {
      notifier.dispose();
    }
    _selectionNotifiers.clear();

    // Convert glossaryData to a regular Map to handle IdentityMap or other map types
    final glossaryDataMap = Map<String, dynamic>.from(widget.glossaryData);

    _log(
      'Loading entries from glossaryData: ${glossaryDataMap.length} entries',
    );
    _log('GlossaryData keys: ${glossaryDataMap.keys.take(5).toList()}...');

    entries = glossaryDataMap.entries.map((entry) {
      // Check if entry value is a string (simple format) or a map (with language info)
      final targetValue = entry.value;
      if (targetValue is Map) {
        // Entry has detailed format with target_lang
        return GlossaryEntry(
          source: entry.key.toString(),
          target: targetValue['dst']?.toString() ??
              targetValue['target']?.toString() ??
              '',
          category: targetValue['category']?.toString() ?? '',
          targetLang:
              targetValue['target_lang']?.toString() ?? widget.targetLang ?? '',
        );
      } else {
        // Simple format: just src -> dst string
        return GlossaryEntry(
          source: entry.key.toString(),
          target: targetValue.toString(),
          targetLang: widget.targetLang ?? '',
        );
      }
    }).toList();

    _log('Loaded ${entries.length} entries from glossaryData');
    if (entries.isEmpty) {
      _log(
        'WARNING: No entries loaded! glossaryData type: ${widget.glossaryData.runtimeType}, original length: ${widget.glossaryData.length}, converted length: ${glossaryDataMap.length}, keys: ${glossaryDataMap.keys.take(10).toList()}',
        level: LogLevel.error,
      );
    } else {
      _log('First entry: ${entries.first.source} -> ${entries.first.target}');
    }

    originalEntries = _copyEntries(entries);

    // Trigger UI update
    if (mounted) {
      setState(() {});
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _loadGlobalGlossaries();
  }

  Future<void> _loadGlobalGlossaries() async {
    try {
      final list = await GlossaryApiService.getSimpleGlossaryList();
      setState(() {
        _globalGlossaries = list;
      });
    } catch (_) {}
  }

  void _startEditing() {
    setState(() {
      _selectedEntryIndices.clear(); // Clear selection when entering edit mode
      isEditing = true;
    });
    // Notify parent about editing state change
    if (widget.onEditingStateChanged != null) {
      widget.onEditingStateChanged!(true);
    }
    // Initialize TextEditingControllers for all entries
    _initializeTextControllers();
  }

  /// Create a new empty glossary and enter edit mode
  void _createNewGlossary() {
    setState(() {
      entries = <GlossaryEntry>[];
      originalEntries = <GlossaryEntry>[];
      _selectedEntryIndices.clear();
      isEditing = true;
    });
    // Notify parent about editing state change
    if (widget.onEditingStateChanged != null) {
      widget.onEditingStateChanged!(true);
    }
    // Clear controllers and notifiers
    _disposeTextControllers();
    for (final notifier in _selectionNotifiers.values) {
      notifier.dispose();
    }
    _selectionNotifiers.clear();
    // Initialize empty controllers (will be created when user adds entries)
    _log('Created new empty glossary, entered edit mode');
  }

  void _cancelEditing() {
    // Dispose all TextEditingControllers
    _disposeTextControllers();
    setState(() {
      isEditing = false;
      entries = _copyEntries(originalEntries);
      _selectedEntryIndices.clear(); // Clear selection when canceling edit
    });
    // Notify parent about editing state change
    if (widget.onEditingStateChanged != null) {
      widget.onEditingStateChanged!(false);
    }
  }

  void _initializeTextControllers() {
    // Create controllers for all entries if not already created
    for (int i = 0; i < entries.length; i++) {
      if (!_sourceControllers.containsKey(i)) {
        _sourceControllers[i] = TextEditingController(text: entries[i].source);
      } else {
        _sourceControllers[i]!.text = entries[i].source;
      }
      if (!_targetControllers.containsKey(i)) {
        _targetControllers[i] = TextEditingController(text: entries[i].target);
      } else {
        _targetControllers[i]!.text = entries[i].target;
      }
    }
  }

  void _disposeTextControllers() {
    // Dispose all controllers
    for (final controller in _sourceControllers.values) {
      controller.dispose();
    }
    for (final controller in _targetControllers.values) {
      controller.dispose();
    }
    _sourceControllers.clear();
    _targetControllers.clear();
  }

  @override
  void dispose() {
    _disposeTextControllers();
    _glossaryNameCtrl.dispose();
    // Dispose all selection notifiers
    for (final notifier in _selectionNotifiers.values) {
      notifier.dispose();
    }
    _selectionNotifiers.clear();
    super.dispose();
  }

  void _saveChanges() {
    final updatedGlossary = <String, dynamic>{};
    for (final entry in entries) {
      if (entry.source.isNotEmpty && entry.target.isNotEmpty) {
        updatedGlossary[entry.source] = entry.target;
      }
    }

    _log(
        '_saveChanges: Processing ${entries.length} entries, ${updatedGlossary.length} valid entries',);
    if (updatedGlossary.isNotEmpty) {
      final sample = updatedGlossary.entries
          .take(3)
          .map((e) => '${e.key}->${e.value}')
          .join(', ');
      _log('_saveChanges: Sample entries: $sample');
    }

    // Call onSave callback if provided
    if (widget.onSave != null) {
      widget.onSave!(updatedGlossary);
    }

    // Automatically apply to FlowContext if flowId is available
    if (widget.flowId != null) {
      if (updatedGlossary.isNotEmpty) {
        try {
          final flowNotifier =
              ref.read(flowProviderFamily(widget.flowId!).notifier);
          final terms = updatedGlossary.entries
              .map((e) => <String, String>{
                    'src': e.key.toString(),
                    'dst': e.value.toString(),
                  },)
              .toList();
          _log(
              '_saveChanges: Applying ${terms.length} terms to FlowContext (flowId: ${widget.flowId})',);
          flowNotifier.setGlossaryArtifacts(
            GlossaryArtifacts(terms: terms, confirmedTerms: terms),
          );
          _log('_saveChanges: Successfully applied glossary to FlowContext');
        } catch (e) {
          // Log error but don't fail the save operation
          _log(
            'Failed to apply glossary to FlowContext: $e',
            level: LogLevel.error,
          );
        }
      } else {
        _log(
            '_saveChanges: updatedGlossary is empty, skipping FlowContext update',);
      }
    } else {
      _log('_saveChanges: No flowId, skipping FlowContext update');
    }

    setState(() {
      isEditing = false;
      originalEntries = _copyEntries(entries);
    });

    // Notify parent about editing state change (editing finished, saved)
    if (widget.onEditingStateChanged != null) {
      widget.onEditingStateChanged!(false);
    }

    final l10n = AppLocalizations.of(context)!;
    MessageService.showSuccess(
      context,
      l10n.translationSnackGlossarySavedAndApplied,
    );
  }

  void _addEntry() {
    setState(() {
      final newIndex = entries.length;
      entries.add(GlossaryEntry(source: '', target: ''));
      // Initialize controllers for the new entry
      if (isEditing) {
        _sourceControllers[newIndex] = TextEditingController(text: '');
        _targetControllers[newIndex] = TextEditingController(text: '');
      }
      // Initialize selection notifier for the new entry
      _selectionNotifiers[newIndex] = ValueNotifier<bool>(false);
    });
  }

  void _deleteEntry(int index) {
    setState(() {
      entries.removeAt(index);
      _selectedEntryIndices.remove(index);
      // Dispose controllers for deleted entry
      _sourceControllers[index]?.dispose();
      _targetControllers[index]?.dispose();
      _sourceControllers.remove(index);
      _targetControllers.remove(index);
      // Dispose selection notifier for deleted entry
      _selectionNotifiers[index]?.dispose();
      _selectionNotifiers.remove(index);
      // Update indices after deletion - rebuild controller and notifier maps
      final newSourceControllers = <int, TextEditingController>{};
      final newTargetControllers = <int, TextEditingController>{};
      final newSelectionNotifiers = <int, ValueNotifier<bool>>{};
      final newSelectedIndices = <int>{};
      for (int i = 0; i < entries.length; i++) {
        final oldIndex = i < index ? i : i + 1;
        if (_sourceControllers.containsKey(oldIndex)) {
          newSourceControllers[i] = _sourceControllers[oldIndex]!;
        } else {
          newSourceControllers[i] =
              TextEditingController(text: entries[i].source);
        }
        if (_targetControllers.containsKey(oldIndex)) {
          newTargetControllers[i] = _targetControllers[oldIndex]!;
        } else {
          newTargetControllers[i] =
              TextEditingController(text: entries[i].target);
        }
        // Update selection notifiers
        if (_selectionNotifiers.containsKey(oldIndex)) {
          newSelectionNotifiers[i] = _selectionNotifiers[oldIndex]!;
        } else {
          newSelectionNotifiers[i] = ValueNotifier<bool>(false);
        }
        // Update selected indices
        if (_selectedEntryIndices.contains(oldIndex)) {
          if (oldIndex > index) {
            newSelectedIndices.add(oldIndex - 1);
          } else if (oldIndex < index) {
            newSelectedIndices.add(oldIndex);
          }
        }
      }
      _sourceControllers.clear();
      _targetControllers.clear();
      _sourceControllers.addAll(newSourceControllers);
      _targetControllers.addAll(newTargetControllers);
      _selectionNotifiers.clear();
      _selectionNotifiers.addAll(newSelectionNotifiers);
      _selectedEntryIndices.clear();
      _selectedEntryIndices.addAll(newSelectedIndices);
    });
  }

  void _deleteSelectedEntries() {
    if (_selectedEntryIndices.isEmpty) return;

    _log('Deleting ${_selectedEntryIndices.length} selected entries');
    _log('Selected indices: ${_selectedEntryIndices.toList()}');
    _log('Current entries count: ${entries.length}');

    setState(() {
      // Sort indices in descending order to delete from end to start
      final sortedIndices = _selectedEntryIndices.toList()
        ..sort((a, b) => b.compareTo(a));

      _log('Sorted indices for deletion: $sortedIndices');

      // Dispose all controllers and notifiers for deleted entries BEFORE removing from maps
      for (final index in sortedIndices) {
        _sourceControllers[index]?.dispose();
        _targetControllers[index]?.dispose();
        _selectionNotifiers[index]?.dispose();
        // Remove from maps immediately after dispose
        _sourceControllers.remove(index);
        _targetControllers.remove(index);
        _selectionNotifiers.remove(index);
      }

      // Delete entries from list (from end to start to avoid index shifting)
      for (final index in sortedIndices) {
        if (index >= 0 && index < entries.length) {
          entries.removeAt(index);
        } else {
          _log(
            'WARNING: Invalid index $index for deletion (entries.length=${entries.length})',
            level: LogLevel.warn,
          );
        }
      }

      _log('After deletion, entries count: ${entries.length}');

      // Dispose all remaining controllers and notifiers
      // We'll rebuild them from scratch to ensure correct indices
      for (final controller in _sourceControllers.values) {
        controller.dispose();
      }
      for (final controller in _targetControllers.values) {
        controller.dispose();
      }
      for (final notifier in _selectionNotifiers.values) {
        notifier.dispose();
      }

      // Rebuild all maps from scratch with correct indices
      _sourceControllers.clear();
      _targetControllers.clear();
      _selectionNotifiers.clear();

      for (int i = 0; i < entries.length; i++) {
        _sourceControllers[i] = TextEditingController(text: entries[i].source);
        _targetControllers[i] = TextEditingController(text: entries[i].target);
        _selectionNotifiers[i] = ValueNotifier<bool>(false);
      }

      _log(
        'Rebuilt ${_sourceControllers.length} controllers and ${_selectionNotifiers.length} notifiers',
      );

      // Update originalEntries to match
      originalEntries = _copyEntries(entries);

      // Clear selection
      _selectedEntryIndices.clear();
    });

    _log(
      'Delete operation completed. Current entries count: ${entries.length}',
    );
  }

  void _clearAllEntries() {
    if (entries.isEmpty) return;

    _log('Clearing all ${entries.length} entries');

    setState(() {
      // Dispose all controllers and notifiers
      for (final controller in _sourceControllers.values) {
        controller.dispose();
      }
      for (final controller in _targetControllers.values) {
        controller.dispose();
      }
      for (final notifier in _selectionNotifiers.values) {
        notifier.dispose();
      }

      // Clear all maps and lists
      _sourceControllers.clear();
      _targetControllers.clear();
      _selectionNotifiers.clear();
      entries.clear();
      originalEntries.clear();
      _selectedEntryIndices.clear();
    });

    _log('Clear operation completed. All entries removed');
  }

  void _toggleEntrySelection(int index) {
    // Update selection state immediately
    final wasSelected = _selectedEntryIndices.contains(index);
    if (wasSelected) {
      _selectedEntryIndices.remove(index);
    } else {
      _selectedEntryIndices.add(index);
    }

    // Update the ValueNotifier for this specific checkbox - this triggers only the checkbox rebuild
    final notifier = _selectionNotifiers[index];
    if (notifier != null) {
      notifier.value = !wasSelected;
    }

    // Use scheduleMicrotask to batch the setState call for DataRow.selected update
    // This allows the checkbox to update immediately via ValueNotifier while deferring the full rebuild
    scheduleMicrotask(() {
      if (mounted) {
        setState(() {
          // State already updated above, just trigger rebuild for DataRow.selected
        });
      }
    });
  }

  void _toggleSelectAll() {
    final selectAll = _selectedEntryIndices.length != entries.length;

    if (selectAll) {
      _selectedEntryIndices.clear();
      _selectedEntryIndices.addAll(List.generate(entries.length, (i) => i));
      // Update all notifiers
      for (int i = 0; i < entries.length; i++) {
        _selectionNotifiers[i]?.value = true;
      }
    } else {
      _selectedEntryIndices.clear();
      // Update all notifiers
      for (int i = 0; i < entries.length; i++) {
        _selectionNotifiers[i]?.value = false;
      }
    }

    // Use scheduleMicrotask to batch the setState call
    scheduleMicrotask(() {
      if (mounted) {
        setState(() {
          // State already updated above
        });
      }
    });
  }

  void _invertSelection() {
    final allIndices = Set<int>.from(List.generate(entries.length, (i) => i));
    if (_selectedEntryIndices.length == entries.length) {
      // If all are selected, clear selection
      _selectedEntryIndices.clear();
      // Update all notifiers
      for (int i = 0; i < entries.length; i++) {
        _selectionNotifiers[i]?.value = false;
      }
    } else {
      // Invert: selected becomes unselected, unselected becomes selected
      final newSelection = allIndices.difference(_selectedEntryIndices);
      _selectedEntryIndices.clear();
      _selectedEntryIndices.addAll(newSelection);
      // Update all notifiers
      for (int i = 0; i < entries.length; i++) {
        _selectionNotifiers[i]?.value = newSelection.contains(i);
      }
    }

    // Use scheduleMicrotask to batch the setState call
    scheduleMicrotask(() {
      if (mounted) {
        setState(() {
          // State already updated above
        });
      }
    });
  }

  Future<void> _exportGlossary() async {
    try {
      // Build CSV content
      final csvLines = <String>['src,dst,category,target_lang'];
      for (final entry in entries) {
        final src = '"${entry.source.replaceAll('"', '""')}"';
        final dst = '"${entry.target.replaceAll('"', '""')}"';
        final cat = '"${entry.category.replaceAll('"', '""')}"';
        final tgtLang = '"${entry.targetLang.replaceAll('"', '""')}"';
        csvLines.add('$src,$dst,$cat,$tgtLang');
      }
      final csvContent = csvLines.join('\r\n');

      // Convert to bytes with UTF-8 BOM for better compatibility
      final csvBytes = utf8.encode('\uFEFF$csvContent');

      // Generate filename with timestamp
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final filename = 'glossary_$timestamp.csv';

      // Save file (Web or Desktop)
      if (kIsWeb) {
        // Web: use FileSaver
        await FileSaver.instance.saveFile(
          name: 'glossary_$timestamp',
          bytes: Uint8List.fromList(csvBytes),
          ext: 'csv',
          mimeType: MimeType.csv,
        );
      } else {
        // Desktop: use FilePicker to save
        final path = await FilePicker.platform.saveFile(
          dialogTitle:
              AppLocalizations.of(context)!.glossaryExportDialogTitle,
          fileName: filename,
          type: FileType.custom,
          allowedExtensions: <String>['csv'],
        );
        if (path != null) {
          final file = io.File(path);
          await file.writeAsBytes(csvBytes, flush: true);
        } else {
          // User cancelled
          return;
        }
      }

      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        MessageService.showSuccess(
          context,
          l10n.glossaryExportSuccess(filename),
        );
      }
    } catch (e) {
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        MessageService.showError(
          context,
          l10n.glossaryExportFailed(e.toString()),
        );
      }
    }
  }

  /// Process imported CSV file bytes (shared logic for file picker and drag-drop)
  Future<void> _processImportedFileBytes(Uint8List fileBytes) async {
    try {
      setState(() {
        _busy = true;
      });

      // Validate and parse CSV
      final validationResult = _validateAndParseCsv(fileBytes);
      if (!(validationResult['valid'] as bool)) {
        final errors = validationResult['errors'] as List<String>;
        final l10n = AppLocalizations.of(context)!;
        final errorMessage =
            l10n.glossaryCsvValidationFailed(errors.join('\n'));
        MessageService.showError(context, errorMessage);
        return;
      }

      final importedEntries =
          validationResult['entries'] as List<GlossaryEntry>;
      if (importedEntries.isEmpty) {
        final l10n = AppLocalizations.of(context)!;
        MessageService.showWarning(
          context,
          l10n.glossaryCsvNoValidEntries,
        );
        return;
      }

      // Show dialog to choose replace or merge
      // If glossary is empty, only show Replace option
      final isEmpty = entries.isEmpty;
      final l10n = AppLocalizations.of(context)!;
      final action = await showDialog<String>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(l10n.glossaryImportDialogTitle),
          content: Text(
            isEmpty
                ? l10n.glossaryImportDialogBodyEmpty(
                    importedEntries.length.toString(),
                  )
                : l10n.glossaryImportDialogBody(
                    importedEntries.length.toString(),
                  ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop('cancel'),
              child: Text(l10n.glossaryDialogCancel),
            ),
            if (isEmpty)
              ElevatedButton(
                onPressed: () => Navigator.of(dialogContext).pop('replace'),
                child: Text(l10n.glossaryImportButtonImport),
              )
            else ...<Widget>[
              OutlinedButton(
                onPressed: () => Navigator.of(dialogContext).pop('replace'),
                child: Text(l10n.glossaryImportButtonReplace),
              ),
              ElevatedButton(
                onPressed: () => Navigator.of(dialogContext).pop('merge'),
                child: Text(l10n.glossaryImportButtonMerge),
              ),
            ],
          ],
        ),
      );

      if (action == null || action == 'cancel') {
        return;
      }

      // Import entries
      setState(() {
        if (action == 'replace') {
          entries = importedEntries;
        } else {
          // Merge: add new entries, update existing ones
          final existingMap = <String, GlossaryEntry>{};
          for (final entry in entries) {
            if (entry.source.isNotEmpty) {
              existingMap[entry.source] = entry;
            }
          }
          for (final entry in importedEntries) {
            if (entry.source.isNotEmpty) {
              existingMap[entry.source] = entry;
            }
          }
          entries = existingMap.values.toList();
        }
        originalEntries = _copyEntries(entries);
      });

      // Rebuild controllers and notifiers
      _rebuildControllersAndNotifiers();

      // Auto-enter edit mode after import
      setState(() {
        isEditing = true;
      });

      // Notify parent about editing state change
      if (widget.onEditingStateChanged != null) {
        widget.onEditingStateChanged!(true);
      }

      final mode = action == 'replace' ? 'replaced' : 'merged';
      MessageService.showSuccess(
        context,
        l10n.glossaryImportResult(
          importedEntries.length.toString(),
          mode,
        ),
      );
    } catch (e) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showError(
        context,
        l10n.glossaryErrorImport(e.toString()),
      );
    } finally {
      setState(() {
        _busy = false;
      });
    }
  }

  /// Import glossary from CSV file
  Future<void> _importGlossaryFromFile() async {
    try {
      setState(() {
        _busy = true;
      });

      // Pick CSV file
      FilePickerResult? result;
      result = await FilePickerHelper.pickFiles(
        type: FileType.custom,
        allowedExtensions: <String>['csv'],
        withData: true,
      );

      if (result == null || result.files.isEmpty) {
        // User cancelled
        setState(() {
          _busy = false;
        });
        return;
      }

      final file = result.files.first;
      Uint8List fileBytes;
      if (kIsWeb) {
        if (file.bytes == null) {
          final l10n = AppLocalizations.of(context)!;
          MessageService.showError(
            context,
            l10n.glossaryErrorFileData,
          );
          setState(() {
            _busy = false;
          });
          return;
        }
        fileBytes = file.bytes!;
      } else {
        if (file.path == null) {
          final l10n = AppLocalizations.of(context)!;
          MessageService.showError(
            context,
            l10n.glossaryErrorFilePath,
          );
          setState(() {
            _busy = false;
          });
          return;
        }
        fileBytes = await io.File(file.path!).readAsBytes();
      }

      // Process the file
      await _processImportedFileBytes(fileBytes);
    } catch (e) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showError(
        context,
        l10n.glossaryErrorImport(e.toString()),
      );
      setState(() {
        _busy = false;
      });
    }
  }

  /// Handle dropped file (for drag and drop)
  Future<void> _handleDroppedFile(PlatformFile file) async {
    if (_busy) return;

    // Check file extension
    final fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.csv')) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showError(
        context,
        l10n.glossaryErrorOnlyCsv,
      );
      return;
    }

    Uint8List fileBytes;
    if (kIsWeb) {
      if (file.bytes == null) {
        final l10n = AppLocalizations.of(context)!;
        MessageService.showError(
          context,
          l10n.glossaryErrorFileData,
        );
        return;
      }
      fileBytes = file.bytes!;
    } else {
      if (file.path == null) {
        final l10n = AppLocalizations.of(context)!;
        MessageService.showError(
          context,
          l10n.glossaryErrorFilePath,
        );
        return;
      }
      fileBytes = await io.File(file.path!).readAsBytes();
    }

    // Process the file
    await _processImportedFileBytes(fileBytes);
  }

  /// Validate and parse CSV file
  Map<String, dynamic> _validateAndParseCsv(Uint8List bytes) {
    final errors = <String>[];
    final entries = <GlossaryEntry>[];

    try {
      // Try to decode as UTF-8 (with or without BOM)
      String content;
      if (bytes.length >= 3 &&
          bytes[0] == 0xEF &&
          bytes[1] == 0xBB &&
          bytes[2] == 0xBF) {
        // UTF-8 BOM detected, skip first 3 bytes
        content = utf8.decode(bytes.sublist(3));
      } else {
        content = utf8.decode(bytes);
      }

      if (content.trim().isEmpty) {
        errors.add('File is empty');
        return <String, dynamic>{
          'valid': false,
          'errors': errors,
          'entries': entries,
        };
      }

      // Split into lines
      final lines = content.split('\n');
      if (lines.isEmpty) {
        errors.add('File contains no lines');
        return <String, dynamic>{
          'valid': false,
          'errors': errors,
          'entries': entries,
        };
      }

      // Parse header
      final headerLine = lines[0].trim();
      if (headerLine.isEmpty) {
        errors.add('Header line is empty');
        return <String, dynamic>{
          'valid': false,
          'errors': errors,
          'entries': entries,
        };
      }

      // Remove quotes and split by comma
      final headerFields = _parseCsvLine(headerLine);
      if (headerFields.length < 2) {
        errors.add(
          'Header must have at least 2 columns (src, dst). Found: ${headerFields.length}',
        );
        return <String, dynamic>{
          'valid': false,
          'errors': errors,
          'entries': entries,
        };
      }

      // Find column indices
      int srcIndex = -1;
      int dstIndex = -1;
      int categoryIndex = -1;
      int targetLangIndex = -1;

      for (int i = 0; i < headerFields.length; i++) {
        final field = headerFields[i].toLowerCase().trim();
        if (field == 'src' || field == 'source') {
          srcIndex = i;
        } else if (field == 'dst' ||
            field == 'target' ||
            field == 'destination') {
          dstIndex = i;
        } else if (field == 'category') {
          categoryIndex = i;
        } else if (field == 'target_lang' ||
            field == 'targetlang' ||
            field == 'target lang') {
          targetLangIndex = i;
        }
      }

      if (srcIndex == -1) {
        errors.add('Required column "src" or "source" not found in header');
      }
      if (dstIndex == -1) {
        errors.add('Required column "dst" or "target" not found in header');
      }

      if (srcIndex == -1 || dstIndex == -1) {
        errors.add('Available columns: ${headerFields.join(", ")}');
        return <String, dynamic>{
          'valid': false,
          'errors': errors,
          'entries': entries,
        };
      }

      // Parse data rows
      int lineNumber = 1; // Header is line 1
      for (int i = 1; i < lines.length; i++) {
        lineNumber++;
        final line = lines[i].trim();
        if (line.isEmpty) {
          continue; // Skip empty lines
        }

        try {
          final fields = _parseCsvLine(line);
          if (fields.length < 2) {
            errors.add(
              'Line $lineNumber: Insufficient columns (expected at least 2, found ${fields.length})',
            );
            continue;
          }

          final src = fields[srcIndex].trim();
          final dst = fields[dstIndex].trim();

          if (src.isEmpty) {
            errors.add('Line $lineNumber: Source term is empty');
            continue;
          }
          if (dst.isEmpty) {
            errors.add('Line $lineNumber: Target term is empty');
            continue;
          }

          final category = categoryIndex >= 0 && categoryIndex < fields.length
              ? fields[categoryIndex].trim()
              : '';
          final targetLang =
              targetLangIndex >= 0 && targetLangIndex < fields.length
                  ? fields[targetLangIndex].trim()
                  : widget.targetLang ?? '';

          entries.add(
            GlossaryEntry(
              source: src,
              target: dst,
              category: category,
              targetLang: targetLang,
            ),
          );
        } catch (e) {
          errors.add('Line $lineNumber: Parse error - ${e.toString()}');
        }
      }

      if (errors.isNotEmpty && entries.isEmpty) {
        return <String, dynamic>{
          'valid': false,
          'errors': errors,
          'entries': entries,
        };
      }

      // If we have some entries but also some errors, show warnings but allow import
      if (errors.isNotEmpty) {
        // Still return valid=true but include errors as warnings
        return <String, dynamic>{
          'valid': true,
          'errors': errors,
          'entries': entries,
          'warnings': true,
        };
      }

      return <String, dynamic>{
        'valid': true,
        'errors': <dynamic>[],
        'entries': entries,
      };
    } catch (e) {
      errors.add('Failed to parse CSV file: ${e.toString()}');
      return <String, dynamic>{
        'valid': false,
        'errors': errors,
        'entries': entries,
      };
    }
  }

  /// Parse a CSV line, handling quoted fields
  List<String> _parseCsvLine(String line) {
    final fields = <String>[];
    String currentField = '';
    bool inQuotes = false;

    for (int i = 0; i < line.length; i++) {
      final char = line[i];

      if (char == '"') {
        if (inQuotes && i + 1 < line.length && line[i + 1] == '"') {
          // Escaped quote
          currentField += '"';
          i++; // Skip next quote
        } else {
          // Toggle quote state
          inQuotes = !inQuotes;
        }
      } else if (char == ',' && !inQuotes) {
        // Field separator
        fields.add(currentField);
        currentField = '';
      } else {
        currentField += char;
      }
    }

    // Add last field
    fields.add(currentField);

    return fields;
  }

  Uint8List _buildCsvBytes(Map<String, String> map, {String? targetLang}) {
    final lines = <String>['src,dst,category,target_lang'];
    map.forEach((k, v) {
      String q(String s) => '"${s.replaceAll('"', '""')}"';
      lines.add('${q(k)},${q(v)},${q('')},${q(targetLang ?? '')}');
    });
    // Use UTF-8 encoding with BOM (utf-8-sig) for better compatibility
    // This matches backend's expected encoding priority
    final csvContent = lines.join('\r\n');
    final utf8Bytes = utf8.encode(csvContent);
    // Add UTF-8 BOM (0xEF, 0xBB, 0xBF) for utf-8-sig compatibility
    return Uint8List.fromList(<int>[0xEF, 0xBB, 0xBF, ...utf8Bytes]);
  }

  /// Show select glossary dialog
  Future<void> _showSelectGlossaryDialog() async {
    if (_globalGlossaries.isEmpty) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showWarning(context, l10n.glossaryPanelNoGlobalGlossaries);
      return;
    }

    String? selectedGlossaryId;
    String? selectedGlossaryName;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (BuildContext context, setDialogState) => AlertDialog(
          title: Text(AppLocalizations.of(context)!.glossaryPanelSelectTitle),
          content: SizedBox(
            width: 400,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Text(
                  'Select a glossary to work with:',
                  style: TextStyle(fontSize: 14),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: selectedGlossaryId,
                  decoration: InputDecoration(
                    border: const OutlineInputBorder(),
                    hintText:
                        AppLocalizations.of(context)!.glossaryPanelSelectHint,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                  ),
                  items: _globalGlossaries.map((g) {
                    final id = (g['id'] ?? g['glossary_id'] ?? '').toString();
                    final name = (g['name'] ?? id).toString();
                    return DropdownMenuItem(
                      value: id,
                      child: Text(name, overflow: TextOverflow.ellipsis),
                    );
                  }).toList(),
                  onChanged: (id) {
                    if (id != null) {
                      setDialogState(() {
                        selectedGlossaryId = id;
                        final glossary = _globalGlossaries.firstWhere(
                          (g) =>
                              (g['id'] ?? g['glossary_id'] ?? '').toString() ==
                              id,
                          orElse: () => <String, dynamic>{},
                        );
                        selectedGlossaryName =
                            (glossary['name'] ?? id).toString();
                      });
                    }
                  },
                ),
                if (selectedGlossaryId != null &&
                    selectedGlossaryName != null) ...<Widget>[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color:
                          Theme.of(context).colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: <Widget>[
                        Icon(
                          Icons.info_outline,
                          size: 20,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            AppLocalizations.of(context)!.glossaryPanelSelected(
                              selectedGlossaryName!,
                            ),
                            style: TextStyle(
                              fontSize: 12,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
              },
              child: Text(AppLocalizations.of(context)!.translationDialogCancelButton),
            ),
            TextButton(
              onPressed: selectedGlossaryId == null
                  ? null
                  : () {
                      Navigator.of(dialogContext).pop(<String, String?>{
                        'action': 'select',
                        'glossaryId': selectedGlossaryId,
                        'glossaryName': selectedGlossaryName,
                      });
                    },
              child: Text(AppLocalizations.of(context)!.glossaryPanelSelectConfirm),
            ),
            // Only show Merge button if current glossary is not empty
            if (entries.isNotEmpty)
              ElevatedButton(
                onPressed: selectedGlossaryId == null
                    ? null
                    : () {
                        Navigator.of(dialogContext).pop(<String, String?>{
                          'action': 'merge',
                          'glossaryId': selectedGlossaryId,
                          'glossaryName': selectedGlossaryName,
                        });
                      },
                child: Text(AppLocalizations.of(context)!.glossaryPanelMergeToCurrent),
              ),
          ],
        ),
      ),
    );

    // Handle dialog result
    if (result != null) {
      final action = result['action'] as String;
      final glossaryId = result['glossaryId'] as String;
      final glossaryName = result['glossaryName'] as String? ?? 'Unknown';

      if (action == 'select') {
        // Load selected glossary entries into current glossary
        await _loadGlossaryEntries(glossaryId);
        final l10n = AppLocalizations.of(context)!;
        MessageService.showSuccess(
          context,
          l10n.glossaryPanelLoadedGlossary(glossaryName),
        );
      } else if (action == 'merge') {
        // Merge selected glossary into current glossary
        await _mergeGlossaryIntoCurrent(glossaryId, glossaryName);
      }
    }
  }

  /// Load entries from a glossary (replace current entries)
  Future<void> _loadGlossaryEntries(String glossaryId) async {
    setState(() {
      _busy = true;
    });
    try {
      final resp = await GlossaryApiService.listEntries(glossaryId);
      final List<dynamic> entriesList = resp['entries'] as List? ?? <dynamic>[];

      setState(() {
        entries = entriesList
            .map((entry) {
              final src = (entry['src'] ?? '').toString();
              final dst = (entry['dst'] ?? '').toString();
              final category = (entry['category'] ?? '').toString();
              final targetLang =
                  (entry['target_lang'] ?? widget.targetLang ?? '').toString();
              return GlossaryEntry(
                source: src,
                target: dst,
                category: category,
                targetLang: targetLang,
              );
            })
            .where((e) => e.source.isNotEmpty && e.target.isNotEmpty)
            .toList();

        originalEntries = _copyEntries(entries);
      });

      // Rebuild controllers and notifiers for new entries
      _rebuildControllersAndNotifiers();

      // Auto-save loaded glossary
      _saveChanges();
    } catch (e) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showError(
        context,
        l10n.glossaryPanelLoadFailed(e.toString()),
      );
    } finally {
      setState(() {
        _busy = false;
      });
    }
  }

  /// Merge a glossary into current glossary
  Future<void> _mergeGlossaryIntoCurrent(
    String glossaryId,
    String glossaryName,
  ) async {
    setState(() {
      _busy = true;
    });
    try {
      // Load entries from selected glossary and merge into current
      final mergedEntries = <String, String>{};

      // First, add current entries
      for (final e in entries) {
        if (e.source.isNotEmpty && e.target.isNotEmpty) {
          mergedEntries[e.source] = e.target;
        }
      }

      // Then, load and merge from selected glossary
      try {
        final resp = await GlossaryApiService.listEntries(glossaryId);
        final List<dynamic> entriesList =
            resp['entries'] as List? ?? <dynamic>[];
        for (final entry in entriesList) {
          final src = (entry['src'] ?? '').toString();
          final dst = (entry['dst'] ?? '').toString();
          if (src.isNotEmpty && dst.isNotEmpty) {
            // Merge mode: update existing, add new
            mergedEntries[src] = dst;
          }
        }
      } catch (e) {
        _log('Failed to load glossary $glossaryId: $e', level: LogLevel.error);
        rethrow;
      }

      // Update current entries
      setState(() {
        entries = mergedEntries.entries
            .map(
              (e) => GlossaryEntry(
                source: e.key,
                target: e.value,
                targetLang: widget.targetLang ?? '',
              ),
            )
            .toList();
        originalEntries = _copyEntries(entries);
      });

      // Rebuild controllers and notifiers for merged entries
      _rebuildControllersAndNotifiers();

      // Auto-save merged glossary
      _saveChanges();

      final l10n = AppLocalizations.of(context)!;
      MessageService.showSuccess(
        context,
        l10n.glossaryPanelMergedIntoCurrent(glossaryName),
      );
    } catch (e) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showError(
        context,
        l10n.glossaryPanelMergeFailed(e.toString()),
      );
    } finally {
      setState(() {
        _busy = false;
      });
    }
  }

  /// Show save glossary dialog
  Future<void> _showSaveGlossaryDialog() async {
    // Reset dialog state
    final dialogNameCtrl = TextEditingController(text: _glossaryNameCtrl.text);
    String? dialogSelectedGlossaryId = _selectedGlossaryId;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (BuildContext context, setDialogState) => AlertDialog(
          title: Text(
            dialogSelectedGlossaryId != null
                ? 'Replace Glossary'
                : 'Save Glossary',
          ),
          content: SizedBox(
            width: 400,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  AppLocalizations.of(context)!.glossaryPanelSaveDialogHint,
                  style: const TextStyle(fontSize: 14),
                ),
                const SizedBox(height: 16),
                Autocomplete<String>(
                  displayStringForOption: (option) => option,
                  optionsBuilder: (textEditingValue) {
                    if (textEditingValue.text.isEmpty) {
                      return _globalGlossaries.map(
                        (g) => (g['name'] ??
                                (g['id'] ?? g['glossary_id'] ?? '').toString())
                            .toString(),
                      );
                    }
                    final query = textEditingValue.text.toLowerCase();
                    return _globalGlossaries
                        .map(
                          (g) => (g['name'] ??
                                  (g['id'] ?? g['glossary_id'] ?? '')
                                      .toString())
                              .toString(),
                        )
                        .where(
                          (name) => name.toLowerCase().contains(query),
                        );
                  },
                  onSelected: (selectedName) {
                    final glossary = _globalGlossaries.firstWhere(
                      (g) =>
                          (g['name'] ??
                                  (g['id'] ?? g['glossary_id'] ?? '')
                                      .toString())
                              .toString() ==
                          selectedName,
                      orElse: () => <String, dynamic>{},
                    );
                    if (glossary.isNotEmpty) {
                      setDialogState(() {
                        dialogSelectedGlossaryId =
                            (glossary['id'] ?? glossary['glossary_id'] ?? '')
                                .toString();
                        dialogNameCtrl.text = selectedName;
                      });
                    } else {
                      setDialogState(() {
                        dialogSelectedGlossaryId = null;
                      });
                    }
                  },
                  fieldViewBuilder: (
                    context,
                    textEditingController,
                    focusNode,
                    onFieldSubmitted,
                  ) {
                    if (textEditingController.text != dialogNameCtrl.text) {
                      textEditingController.text = dialogNameCtrl.text;
                    }
                    return TextField(
                      controller: textEditingController,
                      focusNode: focusNode,
                      autofocus: true,
                      onChanged: (value) {
                        dialogNameCtrl.text = value;
                        final matchingGlossary = _globalGlossaries.firstWhere(
                          (g) =>
                              (g['name'] ??
                                      (g['id'] ?? g['glossary_id'] ?? '')
                                          .toString())
                                  .toString()
                                  .toLowerCase() ==
                              value.toLowerCase(),
                          orElse: () => <String, dynamic>{},
                        );
                        if (matchingGlossary.isEmpty) {
                          setDialogState(() {
                            dialogSelectedGlossaryId = null;
                          });
                        } else {
                          setDialogState(() {
                            dialogSelectedGlossaryId =
                                (matchingGlossary['id'] ??
                                        matchingGlossary['glossary_id'] ??
                                        '')
                                    .toString();
                          });
                        }
                      },
                      decoration: InputDecoration(
                        border: const OutlineInputBorder(),
                        hintText: AppLocalizations.of(context)!
                            .glossaryPanelSaveNameHint,
                        suffixIcon: dialogSelectedGlossaryId != null
                            ? IconButton(
                                icon: const Icon(Icons.close, size: 20),
                                tooltip: AppLocalizations.of(context)!
                                    .glossaryPanelClearSelection,
                                onPressed: () {
                                  setDialogState(() {
                                    dialogSelectedGlossaryId = null;
                                    dialogNameCtrl.clear();
                                    textEditingController.clear();
                                  });
                                },
                              )
                            : null,
                      ),
                    );
                  },
                ),
                if (dialogSelectedGlossaryId != null) ...<Widget>[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color:
                          Theme.of(context).colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: <Widget>[
                        Icon(
                          Icons.info_outline,
                          size: 20,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'This will replace the existing glossary "${_globalGlossaries.firstWhere((g) => (g['id'] ?? g['glossary_id'] ?? '').toString() == dialogSelectedGlossaryId, orElse: () => <String, dynamic>{})['name'] ?? 'Unknown'}"',
                            style: TextStyle(
                              fontSize: 12,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
              },
              child: Text(AppLocalizations.of(context)!.translationDialogCancelButton),
            ),
            ElevatedButton(
              onPressed: dialogNameCtrl.text.trim().isEmpty
                  ? null
                  : () {
                      Navigator.of(dialogContext).pop(<String, String?>{
                        'name': dialogNameCtrl.text.trim(),
                        'selectedGlossaryId': dialogSelectedGlossaryId,
                      });
                    },
              child: Text(
                dialogSelectedGlossaryId != null ? 'Replace' : 'Save As',
              ),
            ),
          ],
        ),
      ),
    );

    // Clean up dialog controller
    dialogNameCtrl.dispose();

    // Handle dialog result
    if (result != null) {
      // Update main controllers with dialog values
      _glossaryNameCtrl.text = result['name'] as String;
      _selectedGlossaryId = result['selectedGlossaryId'] as String?;
      // Call save method
      await _saveGlossary();
    }
  }

  /// Unified save method: Save as new or replace existing based on selection
  Future<void> _saveGlossary() async {
    final name = _glossaryNameCtrl.text.trim();
    if (name.isEmpty) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showWarning(context, l10n.glossaryPanelEnterName);
      return;
    }

    final current = <String, String>{};
    for (final e in entries) {
      if (e.source.isNotEmpty && e.target.isNotEmpty) {
        current[e.source] = e.target;
      }
    }

    // Check if it's replacing an existing glossary
    if (_selectedGlossaryId != null) {
      final glossaryName = _globalGlossaries.firstWhere(
            (g) =>
                (g['id'] ?? g['glossary_id'] ?? '').toString() ==
                _selectedGlossaryId,
            orElse: () => <String, dynamic>{'name': name},
          )['name'] ??
          name;

      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(AppLocalizations.of(context)!.glossaryPanelReplaceTitle),
          content: Text(
            AppLocalizations.of(context)!.glossaryPanelReplaceBody(glossaryName),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(AppLocalizations.of(context)!.translationDialogCancelButton),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(AppLocalizations.of(context)!.glossaryPanelReplaceConfirm),
            ),
          ],
        ),
      );

      if (confirmed != true) return;
    }

    setState(() {
      _busy = true;
    });
    try {
      final targetLang =
          entries.isNotEmpty && entries.first.targetLang.isNotEmpty
              ? entries.first.targetLang
              : widget.targetLang;
      final bytes = _buildCsvBytes(current, targetLang: targetLang);

      if (_selectedGlossaryId != null) {
        // Replace existing glossary
        await GlossaryApiService.importCsv(
          _selectedGlossaryId!,
          bytes,
          mergeMode: 'replace',
        );
        final glossaryName = _globalGlossaries.firstWhere(
              (g) =>
                  (g['id'] ?? g['glossary_id'] ?? '').toString() ==
                  _selectedGlossaryId,
              orElse: () => <String, dynamic>{'name': name},
            )['name'] ??
            name;
        final l10n = AppLocalizations.of(context)!;
        MessageService.showSuccess(
          context,
          l10n.glossaryPanelReplacedGlobal(glossaryName),
        );
        setState(() {
          _selectedGlossaryId = null;
          _glossaryNameCtrl.clear();
        });
      } else {
        // Save as new glossary
        final created = await GlossaryApiService.createEmptyGlossary(
          name: name,
        );
        final newId =
            (created['id'] ?? created['glossary_id'] ?? '').toString();
        if (newId.isEmpty) throw Exception('Invalid new glossary id');
        await GlossaryApiService.importCsv(newId, bytes);
        final l10n = AppLocalizations.of(context)!;
        MessageService.showSuccess(
          context,
          l10n.glossaryPanelSavedAsNewGlobal(name),
        );
        setState(_glossaryNameCtrl.clear);
      }
      await _loadGlobalGlossaries();
    } catch (e) {
      final l10n = AppLocalizations.of(context)!;
      MessageService.showError(
        context,
        l10n.glossaryPanelSaveFailed(e.toString()),
      );
    } finally {
      setState(() {
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    _log(
      'Building GlossaryPreview: ${entries.length} entries, isEditing=$isEditing',
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        // Top toolbar - Main actions only
        Container(
          constraints: const BoxConstraints(
            minHeight: 36,
            maxHeight: 36,
          ), // Fixed height at 36px
          padding: const EdgeInsets.symmetric(
              horizontal: 12,
              vertical: 4,), // Reduced padding to match other toolbars
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            border: Border(
              bottom: BorderSide(color: Theme.of(context).dividerColor),
            ),
          ),
          child: Builder(
            builder: (context) {
              // Get translation state to check if glossary generation is in progress
              final dynamic translationState = widget.flowId != null
                  ? ref.watch(translationStateProviderFamily(widget.flowId!))
                  : ref.watch(translationStateProvider);
              final currentOperation = translationState?.currentOperation ??
                  TranslationOperation.none;
              final isGenerating =
                  currentOperation == TranslationOperation.generatingGlossary;
              final progress = translationState?.progress ?? 0;
              final statusText = translationState?.statusText?.toString() ?? '';

              return Row(
                children: <Widget>[
                  Icon(
                    Icons.book,
                    size: 18,
                    color: Theme.of(context).colorScheme.primary,
                  ), // Reduced from 20 to 18
                  const SizedBox(width: 6), // Reduced spacing
                  // Glossary title and entries count in the same row
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        AppLocalizations.of(context)!.glossaryPanelListTitle,
                        style: TextStyle(
                          fontSize: 15, // Reduced from 16 to 15
                          fontWeight: FontWeight.bold,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                      const SizedBox(
                          width: 8,), // Spacing between title and count
                      Text(
                        entries.isEmpty
                            ? AppLocalizations.of(context)!.glossaryPanelNoEntries
                            : entries.length == 1
                                ? AppLocalizations.of(context)!.glossaryPanelOneEntry
                                : AppLocalizations.of(context)!
                                    .glossaryPanelEntriesCount(
                                        entries.length.toString(),),
                        style: TextStyle(
                          fontSize: 10, // Reduced from 11 to 10
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                  const Spacer(), // Push buttons to the right
                  // Detect Glossary button (moved to the right)
                  if (widget.onGenerateGlossary != null &&
                      !isGenerating) ...<Widget>[
                    const SizedBox(width: 8), // Reduced spacing
                    OutlinedButton.icon(
                      onPressed: widget.onGenerateGlossary,
                      icon: const Icon(Icons.auto_awesome,
                          size: 14,), // Reduced from 16 to 14
                      label: Text(
                        AppLocalizations.of(context)!.glossaryPanelDetect,
                        style: const TextStyle(fontSize: 12),
                      ), // Reduced font size
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 6,
                        ), // Reduced padding
                        minimumSize:
                            const Size(0, 32), // Increased button height
                      ),
                    ),
                  ],
                  // Progress bar for glossary generation (right-aligned, matching translation progress bar style)
                  if (isGenerating) ...<Widget>[
                    const SizedBox(width: 8), // Reduced spacing
                    SizedBox(
                      width: 100,
                      height: 6,
                      child: LinearProgressIndicator(
                        value: progress / 100.0,
                        backgroundColor: Colors.grey.shade300,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          _getStatusColor(statusText),
                        ),
                        minHeight: 6,
                      ),
                    ),
                    const SizedBox(width: 6), // Reduced spacing
                    Text(
                      '$progress%',
                      style: TextStyle(
                        fontSize: 10, // Reduced from 11 to 10
                        fontWeight: FontWeight.w600,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(width: 6), // Reduced spacing
                    Text(
                      statusText.isNotEmpty
                          ? statusText
                          : 'Generating glossary...',
                      style: TextStyle(
                        fontSize: 10, // Reduced from 11 to 10
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(width: 6), // Reduced spacing
                    // Cancel button
                    if (widget.onCancelGlossary != null)
                      TextButton.icon(
                        onPressed: widget.onCancelGlossary,
                        icon: const Icon(Icons.cancel,
                            size: 14,), // Reduced from 16 to 14
                        label: Text(
                          AppLocalizations.of(context)!.translationDialogCancelButton,
                          style: const TextStyle(fontSize: 12),
                        ), // Reduced font size
                        style: TextButton.styleFrom(
                          foregroundColor: Colors.red,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 4,
                          ), // Reduced padding
                          minimumSize:
                              const Size(0, 32), // Increased button height
                        ),
                      ),
                  ],
                  if (_busy)
                    const Padding(
                      padding: EdgeInsets.only(right: 8),
                      child: SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  // Edit button (only show when not editing)
                  if (!isEditing && entries.isNotEmpty)
                    ElevatedButton.icon(
                      onPressed: _startEditing,
                      icon: const Icon(Icons.edit, size: 16),
                      label: Text(AppLocalizations.of(context)!.glossaryPanelEdit),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 12,
                        ),
                      ),
                    ),
                  const SizedBox(width: 8),
                  // Create Glossary button (only show when entries are empty)
                  if (entries.isEmpty)
                    OutlinedButton.icon(
                      onPressed: _busy ? null : _createNewGlossary,
                      icon: const Icon(Icons.add_circle_outline, size: 16),
                      label: Text(AppLocalizations.of(context)!.glossaryPanelCreate),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 12,
                        ),
                      ),
                    ),
                  if (entries.isEmpty && _globalGlossaries.isNotEmpty)
                    const SizedBox(width: 8),
                  // Select Glossary button (opens dialog for selecting/merging)
                  // Available immediately when tab is created, even if entries are empty
                  if (_globalGlossaries.isNotEmpty)
                    OutlinedButton.icon(
                      onPressed: _busy ? null : _showSelectGlossaryDialog,
                      icon: const Icon(Icons.select_all, size: 16),
                      label: Text(AppLocalizations.of(context)!.glossaryPanelSelect),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 12,
                        ),
                      ),
                    ),
                  const SizedBox(width: 8),
                  // Upload button
                  OutlinedButton.icon(
                    onPressed: _busy ? null : _importGlossaryFromFile,
                    icon: const Icon(Icons.upload_file, size: 16),
                    label: Text(AppLocalizations.of(context)!.glossaryPanelImport),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Export button
                  OutlinedButton.icon(
                    onPressed: entries.isEmpty ? null : _exportGlossary,
                    icon: const Icon(Icons.download, size: 16),
                    label: Text(AppLocalizations.of(context)!.glossaryPanelExport),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                    ),
                  ),
                  // Save button (opens dialog)
                  if (entries.isNotEmpty) ...<Widget>[
                    const SizedBox(width: 8),
                    ElevatedButton.icon(
                      onPressed: _busy ? null : _showSaveGlossaryDialog,
                      icon: const Icon(Icons.save, size: 16),
                      label: Text(AppLocalizations.of(context)!.glossaryPanelSave),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 12,
                        ),
                      ),
                    ),
                  ],
                ],
              );
            },
          ),
        ),
        // Table toolbar - Actions directly related to the table (nearby principle)
        // Show toolbar when entries exist OR when in editing mode (to allow adding entries)
        if (entries.isNotEmpty || isEditing)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerLow,
              border: Border(
                bottom: BorderSide(color: Theme.of(context).dividerColor),
              ),
            ),
            child: Row(
              children: <Widget>[
                if (isEditing) ...<Widget>[
                  // Add Entry button
                  OutlinedButton.icon(
                    onPressed: _addEntry,
                    icon: const Icon(Icons.add, size: 18),
                    label: Text(AppLocalizations.of(context)!.glossaryPanelAddEntry),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Delete selected entries button
                  OutlinedButton.icon(
                    onPressed: _selectedEntryIndices.isEmpty
                        ? null
                        : _deleteSelectedEntries,
                    icon: const Icon(Icons.delete, size: 18),
                    label: Text(
                      _selectedEntryIndices.isEmpty
                          ? 'Delete'
                          : 'Delete (${_selectedEntryIndices.length})',
                    ),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      foregroundColor: Colors.red.shade700,
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Clear all entries button
                  OutlinedButton.icon(
                    onPressed: entries.isEmpty ? null : _clearAllEntries,
                    icon: const Icon(Icons.clear_all, size: 18),
                    label: Text(AppLocalizations.of(context)!.glossaryPanelClear),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      foregroundColor: Colors.red.shade700,
                    ),
                  ),
                ],
                const Spacer(),
                if (isEditing) ...<Widget>[
                  // Cancel button
                  OutlinedButton.icon(
                    onPressed: _cancelEditing,
                    icon: const Icon(Icons.cancel, size: 18),
                    label: Text(
                      AppLocalizations.of(context)!.translationDialogCancelButton,
                    ),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Apply button
                  ElevatedButton.icon(
                    onPressed: _saveChanges,
                    icon: const Icon(Icons.check, size: 18),
                    label: Text(AppLocalizations.of(context)!.glossaryPanelApply),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        // Glossary table
        Expanded(
          child: entries.isEmpty && !isEditing
              ? _GlossaryDropZone(
                  onFileDropped: _handleDroppedFile,
                  isBusy: _busy,
                )
              : Column(
                  children: <Widget>[
                    // Table with scroll
                    Expanded(
                      child: SingleChildScrollView(
                        child: SingleChildScrollView(
                          // Horizontal scrolling for columns
                          scrollDirection: Axis.horizontal,
                          child: DataTable(
                            columns: <DataColumn>[
                              // Checkbox column for selection (only in editing mode)
                              if (isEditing)
                                DataColumn(
                                  label: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: <Widget>[
                                      Checkbox(
                                        value: entries.isNotEmpty &&
                                            _selectedEntryIndices.length ==
                                                entries.length,
                                        tristate: true,
                                        onChanged: entries.isEmpty
                                            ? null
                                            : (_) => _toggleSelectAll(),
                                      ),
                                      if (entries.isNotEmpty)
                                        IconButton(
                                          icon: const Icon(
                                            Icons.swap_horiz,
                                            size: 18,
                                          ),
                                          tooltip: 'Invert selection',
                                          padding: EdgeInsets.zero,
                                          constraints: const BoxConstraints(
                                            minWidth: 32,
                                            minHeight: 32,
                                          ),
                                          onPressed: _invertSelection,
                                        ),
                                    ],
                                  ),
                                ),
                              DataColumn(
                                label: Text(
                                  AppLocalizations.of(context)!
                                      .glossaryPanelColumnSource,
                                ),
                              ),
                              DataColumn(
                                label: Text(
                                  AppLocalizations.of(context)!
                                      .glossaryPanelColumnTarget,
                                ),
                              ),
                              if (isEditing)
                                DataColumn(
                                  label: Text(
                                    AppLocalizations.of(context)!
                                        .glossaryPanelColumnActions,
                                  ),
                                ),
                            ],
                            rows: List.generate(entries.length, (index) {
                              final entry = entries[index];
                              // Ensure notifier exists for this index
                              if (!_selectionNotifiers.containsKey(index)) {
                                _selectionNotifiers[index] =
                                    ValueNotifier<bool>(
                                  _selectedEntryIndices.contains(index),
                                );
                              }
                              final notifier = _selectionNotifiers[index]!;
                              return DataRow(
                                key: ValueKey('glossary_row_$index'),
                                selected: _selectedEntryIndices.contains(index),
                                cells: <DataCell>[
                                  // Checkbox cell - only in editing mode
                                  if (isEditing)
                                    DataCell(
                                      ValueListenableBuilder<bool>(
                                        valueListenable: notifier,
                                        builder: (context, value, child) =>
                                            Checkbox(
                                          value: value,
                                          onChanged: (_) =>
                                              _toggleEntrySelection(index),
                                        ),
                                      ),
                                    ),
                                  DataCell(
                                    isEditing
                                        ? SizedBox(
                                            width: 200,
                                            child: TextField(
                                              key: ValueKey(
                                                'source_field_$index',
                                              ),
                                              controller:
                                                  _sourceControllers[index],
                                              onChanged: (value) {
                                                entry.source = value;
                                              },
                                              decoration: const InputDecoration(
                                                border: OutlineInputBorder(),
                                                isDense: true,
                                              ),
                                            ),
                                          )
                                        : SelectableText(
                                            entry.source,
                                            key: ValueKey('source_text_$index'),
                                          ),
                                  ),
                                  DataCell(
                                    isEditing
                                        ? SizedBox(
                                            width: 200,
                                            child: TextField(
                                              key: ValueKey(
                                                'target_field_$index',
                                              ),
                                              controller:
                                                  _targetControllers[index],
                                              onChanged: (value) {
                                                entry.target = value;
                                              },
                                              decoration: const InputDecoration(
                                                border: OutlineInputBorder(),
                                                isDense: true,
                                              ),
                                            ),
                                          )
                                        : SelectableText(
                                            entry.target,
                                            key: ValueKey('target_text_$index'),
                                          ),
                                  ),
                                  if (isEditing)
                                    DataCell(
                                      IconButton(
                                        icon:
                                            const Icon(Icons.delete, size: 20),
                                        color: Colors.red.shade700,
                                        onPressed: () => _deleteEntry(index),
                                        tooltip: 'Delete entry',
                                      ),
                                    ),
                                ],
                              );
                            }),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
        ),
      ],
    );
  }
}

/// Drop zone widget for glossary file drag and drop
class _GlossaryDropZone extends StatefulWidget {
  const _GlossaryDropZone({
    required this.onFileDropped,
    required this.isBusy,
  });
  final Function(PlatformFile) onFileDropped;
  final bool isBusy;

  @override
  State<_GlossaryDropZone> createState() => _GlossaryDropZoneState();
}

class _GlossaryDropZoneState extends State<_GlossaryDropZone> {
  bool _isDragging = false;

  @override
  void initState() {
    super.initState();
    if (kIsWeb) {
      _setupDragAndDrop();
    }
  }

  @override
  void dispose() {
    if (kIsWeb) {
      _cleanupDragAndDrop();
    }
    super.dispose();
  }

  void _setupDragAndDrop() {
    if (!kIsWeb) return;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _attachWindowListeners();
    });
  }

  void _attachWindowListeners() {
    if (!kIsWeb) return;

    html.window.addEventListener('dragover', _handleDragOver);
    html.window.addEventListener('dragleave', _handleDragLeave);
    html.window.addEventListener('drop', _handleDrop);
  }

  void _cleanupDragAndDrop() {
    if (!kIsWeb) return;

    html.window.removeEventListener('dragover', _handleDragOver);
    html.window.removeEventListener('dragleave', _handleDragLeave);
    html.window.removeEventListener('drop', _handleDrop);
  }

  void _handleDragOver(html.Event e) {
    if (widget.isBusy) return;
    e.preventDefault();
    e.stopPropagation();
    if (mounted) {
      setState(() {
        _isDragging = true;
      });
    }
  }

  void _handleDragLeave(html.Event e) {
    e.preventDefault();
    try {
      final relatedTarget = (e as dynamic).relatedTarget;
      if (relatedTarget == null && mounted) {
        setState(() {
          _isDragging = false;
        });
      }
    } catch (_) {
      // Not a drag event, ignore
    }
  }

  Future<void> _handleDrop(html.Event e) async {
    if (widget.isBusy) return;

    e.preventDefault();
    e.stopPropagation();

    if (mounted) {
      setState(() {
        _isDragging = false;
      });
    }

    try {
      final dataTransfer = (e as dynamic).dataTransfer;
      if (dataTransfer != null) {
        final files = dataTransfer.files;
        if (files != null && files.isNotEmpty) {
          _processDroppedFile(files[0]);
        }
      }
    } catch (_) {
      // Not a drag event, ignore
    }
  }

  Future<void> _processDroppedFile(file) async {
    // Check file extension
    final fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.csv')) {
      if (mounted) {
        final l10n = AppLocalizations.of(context)!;
        MessageService.showError(context, l10n.glossaryErrorOnlyCsv);
      }
      return;
    }

    // Read file as bytes
    final reader = html.FileReader();
    final completer = Completer<Uint8List?>();

    reader.onLoadEnd.listen((_) {
      if (reader.readyState == html.FileReader.DONE) {
        completer.complete(reader.result as Uint8List?);
      }
    });

    reader.onError.listen((e) {
      completer.completeError('Failed to read file: ${file.name}');
    });

    reader.readAsArrayBuffer(file);

    try {
      final bytes = await completer.future;
      if (bytes != null && mounted) {
        final platformFile = PlatformFile(
          name: file.name,
          size: file.size,
          bytes: bytes,
        );
        widget.onFileDropped(platformFile);
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(
          context,
          'Failed to read file: ${e.toString()}',
        );
      }
    }
  }

  Widget _buildInnerDropContent(BuildContext context) => Center(
        child: Container(
          decoration: BoxDecoration(
            border: _isDragging && !widget.isBusy
                ? Border.all(
                    color: Theme.of(context).colorScheme.primary,
                    width: 2,
                  )
                : null,
            borderRadius: BorderRadius.circular(8),
            color: _isDragging && !widget.isBusy
                ? Theme.of(context)
                    .colorScheme
                    .primaryContainer
                    .withOpacity(0.3)
                : null,
          ),
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Icon(
                _isDragging && !widget.isBusy
                    ? Icons.file_download
                    : Icons.book_outlined,
                size: 64,
                color: widget.isBusy
                    ? Colors.grey.shade400
                    : _isDragging
                        ? Theme.of(context).colorScheme.primary
                        : Colors.grey.shade400,
              ),
              const SizedBox(height: 16),
              Text(
                widget.isBusy
                    ? AppLocalizations.of(context)!.glossaryPanelProcessing
                    : _isDragging
                        ? AppLocalizations.of(context)!.glossaryPanelDropCsvHere
                        : AppLocalizations.of(context)!.glossaryPanelNoEntriesHint,
                textAlign: TextAlign.left,
                style: TextStyle(
                  fontSize: 16,
                  color: widget.isBusy
                      ? Colors.grey.shade400
                      : _isDragging
                          ? Theme.of(context).colorScheme.primary
                          : Colors.grey.shade600,
                  fontWeight: _isDragging && !widget.isBusy
                      ? FontWeight.w600
                      : FontWeight.normal,
                ),
              ),
            ],
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final inner = _buildInnerDropContent(context);

    // Web: use global HTML drag-and-drop listeners for OS-level drops
    if (kIsWeb) {
      return inner;
    }

    // Desktop / other platforms: use DropTarget for OS-level file drops
    return DropTarget(
      onDragEntered: (detail) {
        if (widget.isBusy) return;
        if (mounted) {
          setState(() {
            _isDragging = true;
          });
        }
      },
      onDragExited: (detail) {
        if (mounted) {
          setState(() {
            _isDragging = false;
          });
        }
      },
      onDragDone: (detail) {
        if (widget.isBusy) return;
        if (mounted) {
          setState(() {
            _isDragging = false;
          });
        }
        if (detail.files.isEmpty) {
          return;
        }

        final file = detail.files.first;
        final platformFile = PlatformFile(
          name: file.name,
          size: 0,
          path: file.path,
        );
        widget.onFileDropped(platformFile);
      },
      child: inner,
    );
  }
}
