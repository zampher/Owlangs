// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import 'translation_quick_settings.dart';

/// Prompt settings tab — mode, style, and long custom instruction.
class PromptPreview extends ConsumerWidget {
  const PromptPreview({this.flowId, super.key});

  final String? flowId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final TranslationQuickSettings settings = flowId != null
        ? ref.watch(translationQuickSettingsProviderFamily(flowId!))
        : ref.watch(translationQuickSettingsProvider);
    final TranslationQuickSettingsNotifier notifier = flowId != null
        ? ref.read(translationQuickSettingsProviderFamily(flowId!).notifier)
        : ref.read(translationQuickSettingsProvider.notifier);

    final List<Map<String, String>> modes = <Map<String, String>>[
      <String, String>{'code': 'off', 'name': l10n.quickSettingsPromptModeOff},
      <String, String>{
        'code': 'simple',
        'name': l10n.quickSettingsPromptModeSimple,
      },
      <String, String>{
        'code': 'advanced',
        'name': l10n.quickSettingsPromptModeAdvanced,
      },
    ];
    final List<Map<String, String>> styles = <Map<String, String>>[
      <String, String>{
        'code': 'literal',
        'name': l10n.quickSettingsStyleLiteral,
      },
      <String, String>{
        'code': 'fluent',
        'name': l10n.quickSettingsStyleFluent,
      },
      <String, String>{
        'code': 'academic',
        'name': l10n.quickSettingsStyleAcademic,
      },
      <String, String>{
        'code': 'business',
        'name': l10n.quickSettingsStyleBusiness,
      },
      <String, String>{
        'code': 'technical',
        'name': l10n.quickSettingsStyleTechnical,
      },
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Row(
            children: <Widget>[
              Icon(
                Icons.edit_note,
                size: 20,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(width: 8),
              Text(
                l10n.homePhasePrompt,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            l10n.promptTabDescription,
            style: TextStyle(
              fontSize: 12,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        const SizedBox(height: 12),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: DropdownButtonFormField<String>(
            initialValue: settings.promptMode,
            isExpanded: true,
            decoration: InputDecoration(
              labelText: l10n.quickSettingsPromptMode,
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            ),
            items: modes
                .map(
                  (Map<String, String> m) => DropdownMenuItem<String>(
                    value: m['code'],
                    child: Text(m['name']!),
                  ),
                )
                .toList(),
            onChanged: (String? v) => notifier.updatePromptMode(v ?? 'off'),
          ),
        ),
        if (settings.promptMode != 'off') ...<Widget>[
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: DropdownButtonFormField<String>(
              initialValue: settings.promptStyle,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: l10n.quickSettingsStyle,
                border: const OutlineInputBorder(),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              ),
              items: styles
                  .map(
                    (Map<String, String> s) => DropdownMenuItem<String>(
                      value: s['code'],
                      child: Text(s['name']!),
                    ),
                  )
                  .toList(),
              onChanged: notifier.updatePromptStyle,
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: PromptNoteTextField(
                initialValue: settings.taskNote ?? '',
                onChanged: notifier.updateTaskNote,
              ),
            ),
          ),
        ] else
          const Spacer(),
      ],
    );
  }
}

/// Large multiline field for custom translation instructions.
class PromptNoteTextField extends StatefulWidget {
  const PromptNoteTextField({
    required this.initialValue,
    required this.onChanged,
    super.key,
  });

  final String initialValue;
  final ValueChanged<String> onChanged;

  @override
  State<PromptNoteTextField> createState() => _PromptNoteTextFieldState();
}

class _PromptNoteTextFieldState extends State<PromptNoteTextField> {
  late TextEditingController _controller;
  late ScrollController _scrollController;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialValue);
    _scrollController = ScrollController();
  }

  @override
  void didUpdateWidget(PromptNoteTextField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialValue != widget.initialValue &&
        _controller.text != widget.initialValue) {
      final TextSelection selection = _controller.selection;
      _controller.text = widget.initialValue;
      if (selection.isValid &&
          selection.end <= widget.initialValue.length) {
        _controller.selection = selection;
      } else {
        _controller.selection = TextSelection.collapsed(
          offset: widget.initialValue.length,
        );
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    return Scrollbar(
      controller: _scrollController,
      thumbVisibility: true,
      child: TextField(
        controller: _controller,
        scrollController: _scrollController,
        onChanged: widget.onChanged,
        maxLines: null,
        expands: true,
        textAlignVertical: TextAlignVertical.top,
        style: const TextStyle(fontSize: 14),
        decoration: InputDecoration(
          labelText: l10n.promptTabLongInstructionLabel,
          hintText: l10n.promptTabLongInstructionHint,
          border: const OutlineInputBorder(),
          contentPadding: const EdgeInsets.all(12),
          alignLabelWithHint: true,
        ),
      ),
    );
  }
}
