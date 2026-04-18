// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/version_stack_provider.dart';

class TextImportPanel extends ConsumerStatefulWidget {
  const TextImportPanel({required this.taskId, super.key});
  final String taskId;

  @override
  ConsumerState<TextImportPanel> createState() => _TextImportPanelState();
}

class _TextImportPanelState extends ConsumerState<TextImportPanel> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    // Initialize version stack with empty string
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(textVersionStackProvider(widget.taskId).notifier).initialize('');
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final VersionStackState<String> stack =
        ref.watch(textVersionStackProvider(widget.taskId));
    final VersionStackNotifier<String> notifier =
        ref.read(textVersionStackProvider(widget.taskId).notifier);

    // Sync controller with present snapshot
    final String text = stack.present?.data ?? '';
    if (_controller.text != text) {
      _controller.text = text;
      _controller.selection =
          TextSelection.collapsed(offset: _controller.text.length);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            OutlinedButton.icon(
              onPressed: stack.canUndo ? notifier.undo : null,
              icon: const Icon(Icons.undo, size: 16),
              label: const Text('Undo'),
            ),
            const SizedBox(width: 8),
            OutlinedButton.icon(
              onPressed: stack.canRedo ? notifier.redo : null,
              icon: const Icon(Icons.redo, size: 16),
              label: const Text('Redo'),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Expanded(
          child: TextField(
            controller: _controller,
            maxLines: null,
            expands: true,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: 'Paste or type text (Markdown supported)...',
            ),
            onChanged: notifier.push,
          ),
        ),
      ],
    );
  }
}
