// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../features/tasks/providers/version_stack_provider.dart';
import '../../../features/translation/providers/translation_state_provider.dart';
import '../../../features/translation/providers/translation_state_provider_family.dart';

/// Text input area widget with undo/redo support
class TextInputArea extends ConsumerStatefulWidget {
  const TextInputArea({
    required this.controller,
    super.key,
    this.flowId,
    this.onCancelTask,
  });
  final String? flowId;
  final TextEditingController controller;
  final VoidCallback? onCancelTask;

  @override
  ConsumerState<TextInputArea> createState() => _TextInputAreaState();
}

class _TextInputAreaState extends ConsumerState<TextInputArea> {
  @override
  Widget build(BuildContext context) {
    // Sync controller with version stack if flowId exists
    if (widget.flowId != null) {
      final VersionStackState<String> stack =
          ref.watch(textVersionStackProvider(widget.flowId!));
      final String text = stack.present?.data ?? '';
      if (widget.controller.text != text) {
        widget.controller.text = text;
        widget.controller.selection =
            TextSelection.collapsed(offset: widget.controller.text.length);
      }
    }

    final dynamic translationState = widget.flowId != null
        ? ref.read(translationStateProviderFamily(widget.flowId!))
        : ref.read(translationStateProvider);
    final bool hasTask = translationState.taskId != null &&
        (translationState.taskId as String).isNotEmpty;
    final isTranslating = translationState.isTranslating;
    final bool isTextInputDisabled = hasTask || isTranslating;

    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            // Undo/Redo buttons
            if (widget.flowId != null) ...<Widget>[
              Row(
                children: <Widget>[
                  Builder(
                    builder: (BuildContext context) {
                      final VersionStackState<String> stack =
                          ref.watch(textVersionStackProvider(widget.flowId!));
                      final VersionStackNotifier<String> stackNotifier =
                          ref.read(
                        textVersionStackProvider(widget.flowId!).notifier,
                      );
                      return Row(
                        children: <Widget>[
                          OutlinedButton.icon(
                            onPressed: isTextInputDisabled || !stack.canUndo
                                ? null
                                : stackNotifier.undo,
                            icon: const Icon(Icons.undo, size: 16),
                            label: const Text('Undo'),
                          ),
                          const SizedBox(width: 8),
                          OutlinedButton.icon(
                            onPressed: isTextInputDisabled || !stack.canRedo
                                ? null
                                : stackNotifier.redo,
                            icon: const Icon(Icons.redo, size: 16),
                            label: const Text('Redo'),
                          ),
                        ],
                      );
                    },
                  ),
                ],
              ),
              const SizedBox(height: 8),
            ],
            // Text input field
            Expanded(
              child: TextField(
                controller: widget.controller,
                enabled: !isTextInputDisabled,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                decoration: InputDecoration(
                  border: const OutlineInputBorder(),
                  hintText: 'Paste or type text (Markdown supported)...',
                  filled: isTextInputDisabled,
                  fillColor: isTextInputDisabled
                      ? Theme.of(context)
                          .colorScheme
                          .surfaceContainerHighest
                          .withOpacity(0.5)
                      : null,
                ),
                onChanged: (String value) {
                  if (widget.flowId != null && !isTextInputDisabled) {
                    ref
                        .read(textVersionStackProvider(widget.flowId!).notifier)
                        .push(value);
                  }
                },
              ),
            ),
            if (isTextInputDisabled && widget.onCancelTask != null) ...<Widget>[
              const SizedBox(height: 12),
              ElevatedButton.icon(
                onPressed: widget.onCancelTask,
                icon: const Icon(Icons.cancel, size: 18),
                label: const Text('Cancel Current Task'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Theme.of(context).colorScheme.errorContainer,
                  foregroundColor:
                      Theme.of(context).colorScheme.onErrorContainer,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
