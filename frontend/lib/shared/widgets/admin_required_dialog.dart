// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../l10n/app_localizations.dart';

/// Shows a dialog that only administrators can access settings/setup wizard,
/// with a button to navigate to the login page. Used on Web when guest clicks
/// Settings, Setup Wizard, or quick settings buttons.
void showAdminRequiredDialog(BuildContext context) {
  final l10n = AppLocalizations.of(context)!;
  showDialog<void>(
    context: context,
    builder: (BuildContext dialogContext) => AlertDialog(
      title: Text(l10n.settingsAdminOnlyDialogTitle),
      content: Text(l10n.settingsAdminOnlyDialogMessage),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(dialogContext).pop(),
          child: Text(l10n.settingsAdminOnlyDialogClose),
        ),
        FilledButton(
          onPressed: () {
            Navigator.of(dialogContext).pop();
            context.go('/login');
          },
          child: Text(l10n.settingsAdminOnlyDialogGoToLogin),
        ),
      ],
    ),
  );
}
