// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/utils/message_service.dart';
import '../../../shared/services/anonymize_service.dart';
import '../../tasks/providers/flow_provider.dart';
import '../../tasks/models/flow.dart';
import '../../anonymize/widgets/anonymization_quick_settings.dart';

class AnonymizePanel extends ConsumerWidget {
  const AnonymizePanel({required this.taskId, super.key});
  final String taskId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final FlowStateModel flow = ref.watch(flowProviderFamily(taskId));
    final FlowStateNotifier flowNotifier =
        ref.read(flowProviderFamily(taskId).notifier);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          // Anonymization Quick Settings
          AnonymizationQuickSettingsWidget(flowId: taskId),
          const SizedBox(height: 24),

          // Action buttons
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              ElevatedButton.icon(
                onPressed: () async {
                  try {
                    // Get Quick Settings configuration
                    final AnonymizationQuickSettings anonymizeQs = ref
                        .read(anonymizationQuickSettingsProviderFamily(taskId));

                    // Get workflow ID from flow context
                    final String? workflowId =
                        flow.context.anonymize.workflowId;

                    if (workflowId == null || workflowId.isEmpty) {
                      if (context.mounted) {
                        MessageService.showError(
                          context,
                          'No workflow ID found. Please upload a file first.',
                        );
                      }
                      return;
                    }

                    // Run anonymize with Quick Settings configuration
                    final AnonymizeService anonymizeService =
                        AnonymizeService();
                    await anonymizeService.runAnonymizeWithConfig(
                      workflowId,
                      enabledEntities:
                          anonymizeQs.selectedEntityTypes.isNotEmpty
                              ? anonymizeQs.selectedEntityTypes
                              : null,
                      mode: anonymizeQs.anonymizeMode,
                      confidenceThreshold: anonymizeQs.anonymizeConfidence,
                      detectionLanguage: anonymizeQs.detectionLanguage != 'auto'
                          ? anonymizeQs.detectionLanguage
                          : anonymizeQs.detectedLanguage,
                    );

                    if (context.mounted) {
                      MessageService.showSuccess(context, 'Anonymize started');
                    }
                    // demo: update flow context with placeholder anonymized text
                    flowNotifier.setAnonymizeArtifacts(
                      const AnonymizeArtifacts(
                        anonymizedText: '[ANONYMIZED] ...',
                        mappings: <String, dynamic>{'demo': true},
                      ),
                    );
                  } catch (e) {
                    if (context.mounted) {
                      MessageService.showError(context, 'Failed: $e');
                    }
                  }
                },
                icon: const Icon(Icons.visibility_off),
                label: const Text('Run Anonymize'),
              ),
              OutlinedButton.icon(
                onPressed: () async {
                  try {
                    await AnonymizeService().runDeAnonymize(taskId);
                    if (context.mounted) {
                      MessageService.showSuccess(
                        context,
                        'De-anonymize started',
                      );
                    }
                    // demo: clear anonymize artifacts
                    flowNotifier.setDeAnonymizeArtifacts(
                      const DeAnonymizeArtifacts(
                        restoredText: '...restored',
                      ),
                    );
                  } catch (e) {
                    if (context.mounted) {
                      MessageService.showError(context, 'Failed: $e');
                    }
                  }
                },
                icon: const Icon(Icons.visibility),
                label: const Text('Run De-anonymize'),
              ),
            ],
          ),

          // Debug info (if source text exists)
          if (flow.context.source.text != null) ...<Widget>[
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      'Source Information',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Source length: ${flow.context.source.text!.length} characters',
                      style:
                          TextStyle(color: Colors.grey.shade600, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
