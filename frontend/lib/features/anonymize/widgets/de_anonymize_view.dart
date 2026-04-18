// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'dart:io';
import '../../../shared/utils/message_service.dart';
import '../../tasks/providers/flow_provider.dart';
import '../../tasks/models/flow.dart';
import '../../tasks/models/persisted_flow_state.dart';
import '../../tasks/services/flow_state_persistence.dart';

/// De-anonymize view widget - three column layout
/// Column 1: Anonymized Text (editable)
/// Column 2: De-anonymized Text (restored text, read-only)
/// Column 3: Detected Entities
class DeAnonymizeView extends ConsumerStatefulWidget {
  const DeAnonymizeView({
    super.key,
    this.flowId,
    this.originalText,
    this.anonymizedText,
    this.entities,
  });
  final String? flowId;
  final String? originalText;
  final String? anonymizedText;
  final List<dynamic>? entities;

  @override
  ConsumerState<DeAnonymizeView> createState() => _DeAnonymizeViewState();
}

class _DeAnonymizeViewState extends ConsumerState<DeAnonymizeView> {
  late final TextEditingController _anonymizedTextController;
  late final TextEditingController _restoredTextController;
  bool _isRecovering = false;
  List<dynamic>? _entities;

  @override
  void initState() {
    super.initState();
    _anonymizedTextController = TextEditingController();
    _restoredTextController = TextEditingController();

    // Initialize with provided data or load from flow context
    _entities = widget.entities;

    if (widget.anonymizedText != null && widget.anonymizedText!.isNotEmpty) {
      _anonymizedTextController.text = widget.anonymizedText!;
    }

    // Load data from flow context if not provided
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadData();
    });
  }

  @override
  void dispose() {
    _anonymizedTextController.dispose();
    _restoredTextController.dispose();
    super.dispose();
  }

  void _loadData() {
    if (widget.flowId == null) return;

    try {
      final FlowStateModel flow = ref.read(flowProviderFamily(widget.flowId!));

      // Load anonymized text if not provided
      if (_anonymizedTextController.text.isEmpty) {
        final String? anonymizedText = flow.context.anonymize.anonymizedText;
        if (anonymizedText != null && anonymizedText.isNotEmpty) {
          _anonymizedTextController.text = anonymizedText;
        }
      }
    } catch (e) {
      // Ignore errors
    }
  }

  Future<void> _recoverText() async {
    final String anonymizedText = _anonymizedTextController.text.trim();

    if (anonymizedText.isEmpty) {
      if (mounted) {
        MessageService.showError(context, 'Please enter anonymized text first');
      }
      return;
    }

    if (widget.flowId == null) {
      if (mounted) {
        MessageService.showError(context, 'No flow ID found');
      }
      return;
    }

    setState(() {
      _isRecovering = true;
    });

    try {
      // Get entity mappings from flow context
      final FlowStateModel flow = ref.read(flowProviderFamily(widget.flowId!));
      var mappings = flow.context.anonymize.mappings;

      // If mappings are empty, generate from entities
      if (mappings == null || mappings.isEmpty) {
        final List<dynamic> entities = _entities ?? <dynamic>[];
        if (entities.isEmpty) {
          if (mounted) {
            MessageService.showError(
              context,
              'No entity mappings found. Please run anonymization first.',
            );
          }
          setState(() {
            _isRecovering = false;
          });
          return;
        }

        // Generate mappings from entities: placeholder -> original text
        mappings = <String, dynamic>{};
        for (final entity in entities) {
          final Map<String, dynamic> entityMap =
              entity as Map<String, dynamic>? ?? <String, dynamic>{};
          final String placeholder = entityMap['placeholder']?.toString() ?? '';
          final String originalText = entityMap['text']?.toString() ?? '';

          if (placeholder.isNotEmpty && originalText.isNotEmpty) {
            mappings[placeholder] = originalText;
          }
        }

        // Update flow context with generated mappings
        if (mappings.isNotEmpty && widget.flowId != null) {
          final FlowStateNotifier flowNotifier =
              ref.read(flowProviderFamily(widget.flowId!).notifier);
          flowNotifier.setAnonymizeArtifacts(
            AnonymizeArtifacts(
              anonymizedText: flow.context.anonymize.anonymizedText,
              mappings: mappings,
              workflowId: flow.context.anonymize.workflowId,
            ),
          );
        }
      }

      // Restore text by replacing placeholders with original values
      var restoredText = anonymizedText;

      // Replace placeholders in reverse order of length to avoid partial matches
      // Sort by placeholder length (longest first) to handle nested placeholders correctly
      final List<MapEntry<String, dynamic>> sortedMappings =
          mappings.entries.toList()
            ..sort(
              (MapEntry<String, dynamic> a, MapEntry<String, dynamic> b) =>
                  b.key.length.compareTo(a.key.length),
            );

      for (final MapEntry<String, dynamic> entry in sortedMappings) {
        final String placeholder = entry.key;
        // Handle dynamic value type - convert to string
        final String originalText = entry.value?.toString() ?? '';
        if (originalText.isNotEmpty) {
          restoredText = restoredText.replaceAll(placeholder, originalText);
        }
      }

      // Update restored text controller
      _restoredTextController.text = restoredText;

      // Save restored text to flow context
      final FlowStateNotifier flowNotifier =
          ref.read(flowProviderFamily(widget.flowId!).notifier);
      flowNotifier.setDeAnonymizeArtifacts(
        DeAnonymizeArtifacts(
          restoredText: restoredText,
        ),
      );

      // Save steps state: de-anonymize completed
      await _saveStepsState(deAnonymizeCompleted: true);

      if (mounted) {
        MessageService.showSuccess(context, 'Text recovered successfully');
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to recover text: $e');
      }
    } finally {
      if (mounted) {
        setState(() {
          _isRecovering = false;
        });
      }
    }
  }

  Future<void> _copyRestoredText() async {
    final String restoredText = _restoredTextController.text;
    if (restoredText.isEmpty) {
      if (mounted) {
        MessageService.showWarning(context, 'No restored text to copy');
      }
      return;
    }

    try {
      await Clipboard.setData(ClipboardData(text: restoredText));
      if (mounted) {
        MessageService.showSuccess(
          context,
          'Restored text copied to clipboard',
        );
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to copy: $e');
      }
    }
  }

  Future<void> _downloadRestoredText() async {
    final String restoredText = _restoredTextController.text;
    if (restoredText.isEmpty) {
      if (mounted) {
        MessageService.showWarning(context, 'No restored text to download');
      }
      return;
    }

    try {
      // Get original file name from flow context if available
      var originalFileName = 'restored_document';
      if (widget.flowId != null) {
        try {
          final FlowStateModel flow =
              ref.read(flowProviderFamily(widget.flowId!));
          final String? sourceFileName = flow.context.source.fileName;
          if (sourceFileName != null && sourceFileName.isNotEmpty) {
            originalFileName = sourceFileName;
          }
        } catch (e) {
          // Ignore errors, use default filename
        }
      }

      // Determine file extension
      final String fileExtension = originalFileName.contains('.')
          ? originalFileName.split('.').last.toLowerCase()
          : 'txt';

      final List<String> textBasedFormats = <String>[
        'txt',
        'md',
        'json',
        'csv',
        'html',
        'htm',
        'xml',
      ];
      var finalExtension = fileExtension;
      var fileName =
          'restored_${originalFileName.replaceAll(RegExp(r'\.[^.]+$'), '')}';

      if (textBasedFormats.contains(fileExtension)) {
        finalExtension = fileExtension;
      } else {
        finalExtension = 'txt';
        fileName = '${fileName}_as_text';
      }

      final Uint8List bytes = utf8.encode(restoredText);
      final String finalFileName = '$fileName.$finalExtension';

      if (kIsWeb) {
        await FileSaver.instance.saveFile(
          name: fileName,
          bytes: bytes,
          ext: finalExtension,
        );
      } else {
        final String? path = await FilePicker.platform.saveFile(
          dialogTitle: 'Save Restored Document',
          fileName: finalFileName,
          type: FileType.custom,
          allowedExtensions: <String>[finalExtension],
        );
        if (path != null) {
          final File file = File(path);
          await file.writeAsBytes(bytes, flush: true);
        }
      }

      if (mounted) {
        if (finalExtension != fileExtension) {
          MessageService.showInfo(
            context,
            'Document saved as .txt (format conversion not available). Content matches panel display.',
          );
        } else {
          MessageService.showSuccess(
            context,
            'Restored document downloaded successfully',
          );
        }
      }
    } catch (e) {
      if (mounted) {
        MessageService.showError(context, 'Failed to download: $e');
      }
    }
  }

  void _deleteEntity(int index) {
    if (_entities == null || index < 0 || index >= _entities!.length) {
      return;
    }

    final Map<String, dynamic> entityToDelete =
        _entities![index] as Map<String, dynamic>? ?? <String, dynamic>{};
    final String placeholder = entityToDelete['placeholder']?.toString() ?? '';

    setState(() {
      // Remove entity from list
      _entities = List<dynamic>.from(_entities!)..removeAt(index);
    });

    // Update mappings in flow context if placeholder exists
    if (widget.flowId != null && placeholder.isNotEmpty) {
      try {
        final FlowStateModel flow =
            ref.read(flowProviderFamily(widget.flowId!));
        final Map<String, dynamic>? mappings = flow.context.anonymize.mappings;

        if (mappings != null && mappings.containsKey(placeholder)) {
          // Remove placeholder from mappings
          final Map<String, dynamic> updatedMappings =
              Map<String, dynamic>.from(mappings)..remove(placeholder);

          // Update anonymized text by removing the placeholder
          var anonymizedText = flow.context.anonymize.anonymizedText;
          if (anonymizedText != null && anonymizedText.contains(placeholder)) {
            // Remove placeholder from anonymized text
            anonymizedText = anonymizedText.replaceAll(placeholder, '');

            // Update flow context
            final FlowStateNotifier flowNotifier =
                ref.read(flowProviderFamily(widget.flowId!).notifier);
            flowNotifier.setAnonymizeArtifacts(
              AnonymizeArtifacts(
                anonymizedText: anonymizedText,
                mappings: updatedMappings,
                workflowId: flow.context.anonymize.workflowId,
              ),
            );

            // Update anonymized text controller
            _anonymizedTextController.text = anonymizedText;
          }
        }
      } catch (e) {
        // Ignore errors
      }
    }

    if (mounted) {
      MessageService.showSuccess(context, 'Entity deleted');
    }
  }

  /// Save steps state to persistence
  Future<void> _saveStepsState({
    bool? deAnonymizeCompleted,
  }) async {
    if (widget.flowId == null) return;
    try {
      final FlowStateNotifier flowNotifier =
          ref.read(flowProviderFamily(widget.flowId!).notifier);

      // Load existing steps state or create new one
      final PersistedStepsState? existingStepsState =
          await FlowStatePersistence.getPersistedStepsState(widget.flowId!);
      final PersistedStepsState stepsState = PersistedStepsState(
        uploadCompleted: existingStepsState?.uploadCompleted ?? false,
        extractCompleted: existingStepsState?.extractCompleted ?? false,
        glossaryCompleted: existingStepsState?.glossaryCompleted ?? false,
        glossarySkipped: existingStepsState?.glossarySkipped ?? false,
        translateCompleted: existingStepsState?.translateCompleted ?? false,
        anonymizeCompleted: existingStepsState?.anonymizeCompleted ?? false,
        deAnonymizeCompleted: deAnonymizeCompleted ??
            existingStepsState?.deAnonymizeCompleted ??
            false,
      );

      await flowNotifier.saveStateWithGlossaryIds(
        <String>[], // No glossary IDs for anonymize flow
        stepsState: stepsState,
      );
    } catch (e) {
      // Ignore errors
    }
  }

  @override
  Widget build(BuildContext context) {
    final List<dynamic> entities = _entities ?? <dynamic>[];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        // Toolbar
        Container(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            border: Border(
              bottom: BorderSide(
                color: Theme.of(context).dividerColor,
              ),
            ),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: <Widget>[
              Icon(Icons.visibility, size: 18, color: Colors.purple.shade700),
              const SizedBox(width: 8),
              Text(
                'De-anonymize',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: Colors.purple.shade700,
                ),
              ),
              const Spacer(),
              // Recover Text button
              ElevatedButton.icon(
                onPressed: _isRecovering ? null : _recoverText,
                icon: _isRecovering
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor:
                              AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Icon(Icons.restore, size: 16),
                label: Text(_isRecovering ? 'Recovering...' : 'Recover Text'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.purple.shade700,
                  foregroundColor: Colors.white,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(6),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Download Restored Text button
              if (_restoredTextController.text.isNotEmpty)
                OutlinedButton.icon(
                  onPressed: _downloadRestoredText,
                  icon: const Icon(Icons.download, size: 14),
                  label: const Text('Download'),
                  style: OutlinedButton.styleFrom(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    foregroundColor: Colors.green.shade700,
                  ),
                ),
              const SizedBox(width: 8),
              // Copy Restored Text button
              if (_restoredTextController.text.isNotEmpty)
                OutlinedButton.icon(
                  onPressed: _copyRestoredText,
                  icon: const Icon(Icons.copy, size: 14),
                  label: const Text('Copy'),
                  style: OutlinedButton.styleFrom(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    foregroundColor: Colors.green.shade700,
                  ),
                ),
            ],
          ),
        ),
        // Three-column layout: Anonymized Text | De-anonymized Text | Detected Entities
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Column 1: Anonymized Text (editable)
              Expanded(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    border: Border(
                      right: BorderSide(
                        color: Theme.of(context).dividerColor,
                      ),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Theme.of(context)
                              .colorScheme
                              .surfaceContainerHighest,
                          border: Border(
                            bottom: BorderSide(
                              color: Theme.of(context).dividerColor,
                            ),
                          ),
                        ),
                        child: Row(
                          children: <Widget>[
                            Icon(
                              Icons.visibility_off,
                              size: 18,
                              color: Colors.orange.shade700,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Anonymized Text (Editable)',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                                color: Theme.of(context).colorScheme.onSurface,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: TextField(
                            controller: _anonymizedTextController,
                            maxLines: null,
                            expands: true,
                            textAlignVertical: TextAlignVertical.top,
                            style: const TextStyle(fontSize: 14),
                            decoration: const InputDecoration(
                              hintText: 'Paste anonymized text here...',
                              border: InputBorder.none,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              // Column 2: De-anonymized Text (read-only)
              Expanded(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    border: Border(
                      right: BorderSide(
                        color: Theme.of(context).dividerColor,
                      ),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Theme.of(context)
                              .colorScheme
                              .surfaceContainerHighest,
                          border: Border(
                            bottom: BorderSide(
                              color: Theme.of(context).dividerColor,
                            ),
                          ),
                        ),
                        child: Row(
                          children: <Widget>[
                            Icon(
                              Icons.visibility,
                              size: 18,
                              color: Colors.green.shade700,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'De-anonymized Text',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.bold,
                                color: Theme.of(context).colorScheme.onSurface,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: TextField(
                            controller: _restoredTextController,
                            maxLines: null,
                            expands: true,
                            textAlignVertical: TextAlignVertical.top,
                            readOnly: true,
                            style: const TextStyle(fontSize: 14),
                            decoration: const InputDecoration(
                              hintText:
                                  'De-anonymized text will appear here after clicking "Recover Text"...',
                              border: InputBorder.none,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              // Column 3: Detected Entities
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Theme.of(context)
                            .colorScheme
                            .surfaceContainerHighest,
                        border: Border(
                          bottom: BorderSide(
                            color: Theme.of(context).dividerColor,
                          ),
                        ),
                      ),
                      child: Row(
                        children: <Widget>[
                          Icon(
                            Icons.label,
                            size: 18,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Entities (${entities.length})',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: Theme.of(context).colorScheme.onSurface,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Expanded(
                      child: entities.isNotEmpty
                          ? ListView.builder(
                              padding: const EdgeInsets.all(8),
                              itemCount: entities.length,
                              itemBuilder: (BuildContext context, int index) {
                                final Map<String, dynamic> entity =
                                    entities[index] as Map<String, dynamic>? ??
                                        <String, dynamic>{};
                                final String originalText =
                                    entity['text']?.toString() ?? '';
                                final String placeholder =
                                    entity['placeholder']?.toString() ?? '';
                                final String entityType =
                                    entity['type']?.toString() ?? 'Unknown';
                                final String confidence =
                                    entity['score']?.toString() ?? 'N/A';

                                return Card(
                                  margin: const EdgeInsets.symmetric(
                                    vertical: 4,
                                    horizontal: 4,
                                  ),
                                  child: ListTile(
                                    dense: true,
                                    title: Text(
                                      originalText,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                    subtitle: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: <Widget>[
                                        if (placeholder.isNotEmpty) ...<Widget>[
                                          const SizedBox(height: 4),
                                          Row(
                                            children: <Widget>[
                                              Icon(
                                                Icons.arrow_forward,
                                                size: 14,
                                                color: Colors.orange.shade700,
                                              ),
                                              const SizedBox(width: 4),
                                              Text(
                                                placeholder,
                                                style: TextStyle(
                                                  fontSize: 12,
                                                  fontFamily: 'monospace',
                                                  color: Colors.orange.shade700,
                                                  fontWeight: FontWeight.bold,
                                                ),
                                              ),
                                            ],
                                          ),
                                        ],
                                        const SizedBox(height: 4),
                                        Row(
                                          children: <Widget>[
                                            Container(
                                              padding:
                                                  const EdgeInsets.symmetric(
                                                horizontal: 6,
                                                vertical: 2,
                                              ),
                                              decoration: BoxDecoration(
                                                color: Theme.of(context)
                                                    .colorScheme
                                                    .primaryContainer,
                                                borderRadius:
                                                    BorderRadius.circular(4),
                                              ),
                                              child: Text(
                                                entityType,
                                                style: TextStyle(
                                                  fontSize: 11,
                                                  color: Theme.of(context)
                                                      .colorScheme
                                                      .onPrimaryContainer,
                                                  fontWeight: FontWeight.w500,
                                                ),
                                              ),
                                            ),
                                            const SizedBox(width: 8),
                                            Text(
                                              'Confidence: $confidence',
                                              style: TextStyle(
                                                fontSize: 11,
                                                color: Theme.of(context)
                                                    .colorScheme
                                                    .onSurfaceVariant,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                    trailing: IconButton(
                                      icon: const Icon(
                                        Icons.delete_outline,
                                        size: 18,
                                      ),
                                      color: Colors.red.shade700,
                                      tooltip: 'Delete entity',
                                      onPressed: () => _deleteEntity(index),
                                    ),
                                  ),
                                );
                              },
                            )
                          : Center(
                              child: Text(
                                'No entities detected',
                                style: TextStyle(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                              ),
                            ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
