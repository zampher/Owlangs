// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../../l10n/app_localizations.dart';
import '../../models/exclusion_reason.dart';

/// Dialog for editing exclusion reason
class ExclusionReasonEditor extends StatefulWidget {
  const ExclusionReasonEditor({
    required this.currentReason,
    super.key,
  });

  final String? currentReason;

  @override
  State<ExclusionReasonEditor> createState() => _ExclusionReasonEditorState();
}

class _ExclusionReasonEditorState extends State<ExclusionReasonEditor> {
  String? _selectedReason;

  @override
  void initState() {
    super.initState();
    _selectedReason = widget.currentReason;
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    return AlertDialog(
      title: Text(l10n.exclusionPanelChangeReasonTitle),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            if (widget.currentReason != null) ...<Widget>[
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Row(
                  children: <Widget>[
                    Text(l10n.exclusionPanelCurrentLabel),
                    _buildReasonChip(
                      context,
                      ExclusionReason.fromString(widget.currentReason),
                    ),
                  ],
                ),
              ),
            ],
            Text(l10n.exclusionPanelSelectNewReason),
            const SizedBox(height: 12),
            ...ExclusionReason.values.map(
              (reason) => RadioListTile<String?>(
                title: Row(
                  children: <Widget>[
                    Icon(reason.icon, size: 16, color: reason.color),
                    const SizedBox(width: 8),
                    Text(reason.displayNameLocalized(l10n)),
                  ],
                ),
                value: reason.value,
                groupValue: _selectedReason,
                onChanged: (String? value) {
                  setState(() {
                    _selectedReason = value;
                  });
                },
              ),
            ),
            const Divider(),
            RadioListTile<String?>(
              title: Row(
                children: <Widget>[
                  const Icon(Icons.cancel, size: 16, color: Colors.red),
                  const SizedBox(width: 8),
                  Text(
                    l10n.exclusionPanelNoneRemoveExclusion,
                    style: const TextStyle(color: Colors.red),
                  ),
                ],
              ),
              value: null,
              groupValue: _selectedReason,
              onChanged: (value) {
                setState(() {
                  _selectedReason = value;
                });
              },
            ),
          ],
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l10n.translationToolbarCancelButton),
        ),
        ElevatedButton(
          onPressed: () {
            Navigator.of(context).pop(_selectedReason);
          },
          child: Text(l10n.exclusionPanelApply),
        ),
      ],
    );
  }

  Widget _buildReasonChip(BuildContext context, ExclusionReason reason) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: reason.color.withOpacity(0.2),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: reason.color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(reason.icon, size: 12, color: reason.color),
          const SizedBox(width: 4),
          Text(
            reason.displayNameLocalized(l10n),
            style: TextStyle(fontSize: 10, color: reason.color),
          ),
        ],
      ),
    );
  }
}
