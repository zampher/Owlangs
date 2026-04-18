// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/widgets/unified_preview_widget.dart';

/// Widget to display Translation Preview in a tab with toolbar
/// (Settings and Download buttons)
/// Uses UnifiedPreviewWidget for consistent rendering with Convert
class TranslationPreviewTabWidget extends ConsumerStatefulWidget {
  const TranslationPreviewTabWidget({
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
  ConsumerState<TranslationPreviewTabWidget> createState() =>
      _TranslationPreviewTabWidgetState();
}

class _TranslationPreviewTabWidgetState
    extends ConsumerState<TranslationPreviewTabWidget> {
  @override
  Widget build(BuildContext context) {
    // Use UnifiedPreviewWidget for consistent rendering with Convert
    return UnifiedPreviewWidget(
      taskId: widget.taskId,
      flowId: widget.flowId,
      downloads: widget.downloads,
      onDownload: widget.onDownload,
      title: 'Translation Preview',
      icon: Icons.preview,
      previewType: 'md', // Use markdown preview for translation
    );
  }
}
