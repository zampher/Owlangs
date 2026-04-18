// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/anonymization_settings_state.dart';
import '../providers/anonymization_settings_provider.dart';

class AnonymizationStatusBar extends ConsumerWidget {
  const AnonymizationStatusBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AnonymizationSettingsState state =
        ref.watch(anonymizationSettingsProvider);
    final DownloadState downloadState = state.downloadState;
    final TestState testState = state.testState;

    // Show download state if downloading
    if (downloadState.isDownloading) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).brightness == Brightness.dark
              ? Colors.blue.shade900.withOpacity(0.3)
              : Colors.blue.shade50,
          border: Border(
            bottom: BorderSide(
              color: Theme.of(context).brightness == Brightness.dark
                  ? Colors.blue.shade700
                  : Colors.blue.shade200,
            ),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Downloading: ${downloadState.modelName ?? 'model'}',
                    style: TextStyle(
                      fontWeight: FontWeight.w500,
                      color: Theme.of(context).brightness == Brightness.dark
                          ? Colors.blue.shade200
                          : Colors.blue.shade900,
                    ),
                  ),
                ),
                Text(
                  '${downloadState.progress.toInt()}%',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Theme.of(context).brightness == Brightness.dark
                        ? Colors.blue.shade200
                        : Colors.blue.shade900,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: downloadState.progress / 100,
              backgroundColor: Theme.of(context).brightness == Brightness.dark
                  ? Colors.blue.shade800
                  : Colors.blue.shade200,
              valueColor: AlwaysStoppedAnimation<Color>(
                Theme.of(context).brightness == Brightness.dark
                    ? Colors.blue.shade400
                    : Colors.blue.shade700,
              ),
            ),
          ],
        ),
      );
    }

    // Show download error if any
    if (downloadState.errorMessage != null) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).brightness == Brightness.dark
              ? Colors.red.shade900.withOpacity(0.3)
              : Colors.red.shade50,
          border: Border(
            bottom: BorderSide(
              color: Theme.of(context).brightness == Brightness.dark
                  ? Colors.red.shade700
                  : Colors.red.shade200,
            ),
          ),
        ),
        child: Row(
          children: <Widget>[
            Icon(
              Icons.error,
              color: Colors.red.shade700,
              size: 20,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                downloadState.errorMessage!,
                style: TextStyle(
                  color: Theme.of(context).brightness == Brightness.dark
                      ? Colors.red.shade200
                      : Colors.red.shade900,
                ),
              ),
            ),
            IconButton(
              icon: const Icon(Icons.close, size: 18),
              onPressed: () {
                ref
                    .read(anonymizationSettingsProvider.notifier)
                    .clearDownloadState();
              },
              color: Theme.of(context).brightness == Brightness.dark
                  ? Colors.red.shade200
                  : Colors.red.shade700,
            ),
          ],
        ),
      );
    }

    // Show test state if testing
    if (testState.isTesting) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).brightness == Brightness.dark
              ? Colors.blue.shade900.withOpacity(0.3)
              : Colors.blue.shade50,
          border: Border(
            bottom: BorderSide(
              color: Theme.of(context).brightness == Brightness.dark
                  ? Colors.blue.shade700
                  : Colors.blue.shade200,
            ),
          ),
        ),
        child: Row(
          children: <Widget>[
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 8),
            Text(
              'Testing model...',
              style: TextStyle(
                fontWeight: FontWeight.w500,
                color: Theme.of(context).brightness == Brightness.dark
                    ? Colors.blue.shade200
                    : Colors.blue.shade900,
              ),
            ),
          ],
        ),
      );
    }

    // Show test result if available
    if (testState.result != null) {
      final TestResult result = testState.result!;
      final bool isSuccess = result.success;
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).brightness == Brightness.dark
              ? (isSuccess
                  ? Colors.green.shade900.withOpacity(0.3)
                  : Colors.red.shade900.withOpacity(0.3))
              : (isSuccess ? Colors.green.shade50 : Colors.red.shade50),
          border: Border(
            bottom: BorderSide(
              color: Theme.of(context).brightness == Brightness.dark
                  ? (isSuccess ? Colors.green.shade700 : Colors.red.shade700)
                  : (isSuccess ? Colors.green.shade200 : Colors.red.shade200),
            ),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  isSuccess ? Icons.check_circle : Icons.error,
                  color:
                      isSuccess ? Colors.green.shade700 : Colors.red.shade700,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    result.message,
                    style: TextStyle(
                      fontWeight: FontWeight.w500,
                      color: Theme.of(context).brightness == Brightness.dark
                          ? (isSuccess
                              ? Colors.green.shade200
                              : Colors.red.shade200)
                          : (isSuccess
                              ? Colors.green.shade900
                              : Colors.red.shade900),
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: () {
                    ref
                        .read(anonymizationSettingsProvider.notifier)
                        .clearTestState();
                  },
                  color: Theme.of(context).brightness == Brightness.dark
                      ? (isSuccess
                          ? Colors.green.shade200
                          : Colors.red.shade200)
                      : (isSuccess
                          ? Colors.green.shade700
                          : Colors.red.shade700),
                ),
              ],
            ),
            if (result.remediation != null &&
                result.remediation!.isNotEmpty) ...<Widget>[
              const SizedBox(height: 8),
              ...result.remediation!.map(
                (String item) => Padding(
                  padding: const EdgeInsets.only(left: 28, top: 4),
                  child: Text(
                    '• $item',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).brightness == Brightness.dark
                          ? Colors.grey.shade400
                          : Colors.grey.shade700,
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      );
    }

    // No status to show
    return const SizedBox.shrink();
  }
}
