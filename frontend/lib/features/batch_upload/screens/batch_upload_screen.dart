// SPDX-FileCopyrightText: 2026 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../l10n/app_localizations.dart';
import '../widgets/batch_upload_dialog.dart'
    show BatchUploadPageBody;

/// Full-screen batch upload page, replacing the old dialog overlay.
///
/// Preserves the same horizontal layout (toolbar top, settings left, file list
/// right) but shown as a standalone route instead of a dialog overlay.
class BatchUploadScreen extends StatelessWidget {
  const BatchUploadScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.batchUploadTitle),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: const SafeArea(
        child: BatchUploadPageBody(showAppBar: true),
      ),
    );
  }
}
