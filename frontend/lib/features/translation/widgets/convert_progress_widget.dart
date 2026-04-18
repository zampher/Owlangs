// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/services/translation_service.dart';
import '../../../shared/utils/message_service.dart';
import '../providers/translation_state_provider_family.dart';
import '../../../shared/widgets/unified_preview_widget.dart';

/// Widget to display Convert operation progress, status, and cancel button
/// Uses UnifiedPreviewWidget for consistent rendering with Translation Preview
class ConvertProgressWidget extends ConsumerStatefulWidget {
  const ConvertProgressWidget({
    required this.taskId,
    required this.downloads,
    super.key,
    this.flowId,
    this.onDownload,
  });
  final String taskId;
  final String? flowId;
  final Map<String, String> downloads;
  final Function(String fileType, String url)? onDownload;

  @override
  ConsumerState<ConvertProgressWidget> createState() =>
      _ConvertProgressWidgetState();
}

class _ConvertProgressWidgetState extends ConsumerState<ConvertProgressWidget> {
  @override
  Widget build(BuildContext context) {
    // Use UnifiedPreviewWidget for consistent rendering with Translation Preview
    return UnifiedPreviewWidget(
      taskId: widget.taskId,
      flowId: widget.flowId,
      downloads: widget.downloads,
      onDownload: widget.onDownload,
      title: 'Convert',
      icon: Icons.transform,
      enableStatusPolling: true, // Convert needs status polling
      showProgressBar: true, // Convert shows progress bar
      onCancel: () async {
        // Cancel convert operation
        final svc = TranslationService();
        await svc.cancelTask(widget.taskId);

        if (!mounted) return;

        // Update translation state
        if (widget.flowId != null) {
          final notifier =
              ref.read(translationStateProviderFamily(widget.flowId!).notifier);
          notifier.setTranslating(false);
          notifier.setStatusText('cancelled');
          notifier.setCurrentOperation(TranslationOperation.none);
        }

        if (mounted) {
          MessageService.showInfo(context, 'Format conversion cancelled');
        }
      },
      onStatusUpdate: (status, downloads) {
        // Update translation state when status changes
        if (widget.flowId != null) {
          final notifier =
              ref.read(translationStateProviderFamily(widget.flowId!).notifier);
          final statusText = (status['status'] ?? '').toString().toLowerCase();
          notifier.setTranslating(false);
          notifier.setStatusText(statusText);
          // Safely extract progress, handling null and invalid types
          final dynamic progressValue = status['progress'];
          final int progress = (progressValue is num)
              ? progressValue.toInt().clamp(0, 100)
              : ((progressValue is String && progressValue.isNotEmpty)
                  ? (int.tryParse(progressValue) ?? 0).clamp(0, 100)
                  : 0);
          notifier.setProgress(progress);
          notifier.setCurrentOperation(TranslationOperation.none);
          // Update downloads in state
          if (downloads.isNotEmpty) {
            notifier.setDownloads(downloads);
          }
        }
      },
    );
  }
}
