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
import '../../../shared/widgets/preview_panel.dart';
import '../../../shared/widgets/file_upload_area.dart';
import '../../../shared/widgets/document_card.dart';
import '../../../shared/utils/message_service.dart';
import '../../tasks/models/flow.dart';
import '../../translation/providers/preview_tabs_provider.dart';
import '../../translation/models/preview_tab.dart';
import '../../translation/providers/translation_state_provider.dart';
import '../../translation/providers/translation_state_provider_family.dart';
import '../../tasks/providers/flow_provider.dart';
import '../widgets/de_anonymize_view.dart';
import '../widgets/anonymization_quick_settings.dart';

/// De-anonymize screen - similar layout to AnonymizeScreen
/// Left: Settings panel
/// Right: Preview Panel with De-anonymize tab
class DeAnonymizeScreen extends ConsumerStatefulWidget {
  const DeAnonymizeScreen({super.key, this.flowId});
  final String? flowId;

  @override
  ConsumerState<DeAnonymizeScreen> createState() => _DeAnonymizeScreenState();
}

class _DeAnonymizeScreenState extends ConsumerState<DeAnonymizeScreen> {
  @override
  void initState() {
    super.initState();
    // Add De-anonymize tab if it doesn't exist
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _ensureDeAnonymizeTab();
    });
  }

  void _ensureDeAnonymizeTab() {
    if (widget.flowId == null) return;

    final PreviewTabsNotifier tabsNotifier =
        ref.read(previewTabsProviderFamily(widget.flowId!).notifier);
    final PreviewTabsState tabsState =
        ref.read(previewTabsProviderFamily(widget.flowId!));

    // Check if De-anonymize tab already exists
    final bool hasDeAnonymizeTab =
        tabsState.tabs.any((PreviewTab tab) => tab.id == 'de_anonymize');

    if (!hasDeAnonymizeTab) {
      // Get data from current active tab or any Anonymized Result tab
      String? originalText;
      String? anonymizedText;
      List<dynamic>? entities;

      // Try to get data from current active tab if it's an Anonymized Result tab
      if (tabsState.tabs.isNotEmpty &&
          tabsState.activeTabIndex < tabsState.tabs.length) {
        final PreviewTab activeTab = tabsState.tabs[tabsState.activeTabIndex];
        if (activeTab.title == 'Anonymized Result' &&
            activeTab.dataRef != null) {
          originalText = activeTab.dataRef!['originalText']?.toString();
          anonymizedText = activeTab.dataRef!['anonymizedText']?.toString();
          entities = activeTab.dataRef!['entities'] as List<dynamic>?;
        }
      }

      // If no data from active tab, try to get from any Anonymized Result tab
      if (originalText == null || anonymizedText == null || entities == null) {
        for (final PreviewTab tab in tabsState.tabs) {
          if (tab.title == 'Anonymized Result' && tab.dataRef != null) {
            originalText = tab.dataRef!['originalText']?.toString();
            anonymizedText = tab.dataRef!['anonymizedText']?.toString();
            entities = tab.dataRef!['entities'] as List<dynamic>?;
            break;
          }
        }
      }

      // Create De-anonymize view with entities data
      final DeAnonymizeView deAnonymizeView = DeAnonymizeView(
        flowId: widget.flowId,
        originalText: originalText,
        anonymizedText: anonymizedText,
        entities: entities,
      );

      final PreviewTab tab = PreviewTab(
        id: 'de_anonymize',
        type: PreviewTabType.translationResult, // Reuse type for tab behavior
        title: 'De-anonymize',
        icon: Icons.visibility,
        content: deAnonymizeView,
        dataRef: <String, dynamic>{
          'flowId': widget.flowId,
          'originalText': originalText,
          'anonymizedText': anonymizedText,
          'entities': entities,
        },
      );

      tabsNotifier.addTab(tab);
      // Switch to the new tab
      tabsNotifier.switchToTab(tabsState.tabs.length);
    }
  }

  @override
  Widget build(BuildContext context) {
    final dynamic translationState = widget.flowId != null
        ? ref.watch(translationStateProviderFamily(widget.flowId!))
        : ref.watch(translationStateProvider);
    final PreviewTabsState tabsState = widget.flowId != null
        ? ref.watch(previewTabsProviderFamily(widget.flowId!))
        : ref.watch(previewTabsProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        // Toolbar at the top
        _buildToolbar(),
        // Content area
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Left Panel (1/4 width)
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      // Document Card
                      DocumentCard(pickedFile: translationState.pickedFile),
                      const SizedBox(height: 24),
                      // Anonymization Quick Settings
                      AnonymizationQuickSettingsWidget(flowId: widget.flowId),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 16),
              // Right Panel - Preview Area (3/4 width)
              Expanded(
                flex: 3,
                child: _buildPreviewPanel(translationState, tabsState),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildToolbar() {
    final FlowStateModel? flow = widget.flowId != null
        ? ref.watch(flowProviderFamily(widget.flowId!))
        : null;

    return Container(
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
          Icon(Icons.visibility, size: 20, color: Colors.purple.shade700),
          const SizedBox(width: 8),
          Text(
            'De-anonymize',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: Colors.purple.shade700,
            ),
          ),
          const Spacer(),
          // Download Restored Text button
          if (flow?.context.deAnonymize.restoredText != null &&
              flow!.context.deAnonymize.restoredText!.isNotEmpty)
            OutlinedButton.icon(
              onPressed: () => _downloadRestored(flow),
              icon: const Icon(Icons.download, size: 16),
              label: const Text('Download Restored'),
              style: OutlinedButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                foregroundColor: Colors.green.shade700,
              ),
            ),
          if (flow?.context.deAnonymize.restoredText != null &&
              flow!.context.deAnonymize.restoredText!.isNotEmpty)
            const SizedBox(width: 12),
          // Copy Restored Text button
          if (flow?.context.deAnonymize.restoredText != null &&
              flow!.context.deAnonymize.restoredText!.isNotEmpty)
            OutlinedButton.icon(
              onPressed: () => _copyRestored(flow),
              icon: const Icon(Icons.copy, size: 16),
              label: const Text('Copy Restored'),
              style: OutlinedButton.styleFrom(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                foregroundColor: Colors.blue.shade700,
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _downloadRestored(flow) async {
    final restoredText = flow.context.deAnonymize.restoredText;
    if (restoredText == null || restoredText.isEmpty) {
      if (mounted) {
        MessageService.showWarning(context, 'No restored text to download');
      }
      return;
    }

    try {
      // Get original file name from flow context if available
      var originalFileName = 'restored_document';
      final sourceFileName = flow.context.source.fileName;
      if (sourceFileName != null && sourceFileName.isNotEmpty) {
        originalFileName = sourceFileName;
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

  Future<void> _copyRestored(flow) async {
    final restoredText = flow.context.deAnonymize.restoredText;
    if (restoredText == null || restoredText.isEmpty) {
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

  Widget _buildPreviewPanel(state, tabsState) {
    // Build empty state widget
    Widget? emptyStateWidget;
    if (tabsState.tabs.isEmpty) {
      emptyStateWidget = FileUploadArea(
        isDisabled: false,
        onTap: () {
          // File upload not needed in De-anonymize phase
        },
      );
    }

    return PreviewPanel(
      flowId: widget.flowId,
      emptyState: emptyStateWidget,
    );
  }
}
