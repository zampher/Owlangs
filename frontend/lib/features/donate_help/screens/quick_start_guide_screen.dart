// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

/// Quick Start Guide: separate page with step-by-step instructions.
/// Step 1 is configuration (LLM platform + API Key); then upload, extract, translate, export.
library;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../app/app_router.dart';

/// Official documentation URL (same as in help_screen).
const String _kDocUrl = 'https://www.owlangs.org';

class QuickStartGuideScreen extends StatefulWidget {
  const QuickStartGuideScreen({super.key});

  @override
  State<QuickStartGuideScreen> createState() => _QuickStartGuideScreenState();
}

class _QuickStartGuideScreenState extends State<QuickStartGuideScreen> {
  late final FocusNode _selectionFocusNode = FocusNode();

  @override
  void dispose() {
    _selectionFocusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final TextTheme textTheme = theme.textTheme;
    final ColorScheme colorScheme = theme.colorScheme;

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 24),
      child: SelectableRegion(
        focusNode: _selectionFocusNode,
        selectionControls: materialTextSelectionControls,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  Icons.play_circle_outline,
                  color: colorScheme.primary,
                  size: 28,
                ),
                const SizedBox(width: 12),
                Text(
                  'Quick Start Guide',
                  style: textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colorScheme.primary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            SelectableText.rich(
              TextSpan(
                style: textTheme.bodyMedium,
                children: <TextSpan>[
                  const TextSpan(
                    text: '1. ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text: 'Configure LLM platform(s) and API Key\n',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text:
                        'Select one or more LLM platforms (e.g. DeepSeek, OpenAI) and configure the API Key for each. '
                        'Go to Settings → AI Platform to add platforms and keys. You need at least one configured LLM to translate.\n\n',
                  ),
                  const TextSpan(
                    text: '2. ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text: 'Configure MinerU for PDF extraction\n',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text:
                        'MinerU is used to extract content from PDFs (layout, tables, formulas). '
                        'If you need to translate PDFs, configure the MinerU API Key in Settings → AI Platform → MinerU.\n\n',
                  ),
                  const TextSpan(
                    text: '3. ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text: 'Upload a document ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(text: 'in the Workspace.\n\n'),
                  const TextSpan(
                    text: '4. ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text: 'Extract glossary ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(text: 'to identify terms and phrases.\n\n'),
                  const TextSpan(
                    text: '5. ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text: 'Translate segments ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text: 'using the built-in translation service.\n\n',
                  ),
                  const TextSpan(
                    text: '6. ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(
                    text: 'Review and export ',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const TextSpan(text: 'the translated document.\n\n'),
                  TextSpan(
                    text:
                        'For more details, see the Help tab and the documentation at ',
                    style: TextStyle(
                      fontStyle: FontStyle.italic,
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                  TextSpan(
                    text: 'www.owlangs.org',
                    style: TextStyle(
                      fontStyle: FontStyle.italic,
                      color: colorScheme.primary,
                      decoration: TextDecoration.underline,
                      fontWeight: FontWeight.w500,
                    ),
                    recognizer: TapGestureRecognizer()
                      ..onTap = () async {
                        final Uri uri = Uri.parse(_kDocUrl);
                        if (await canLaunchUrl(uri)) {
                          await launchUrl(
                            uri,
                            mode: LaunchMode.externalApplication,
                          );
                        }
                      },
                  ),
                  TextSpan(
                    text: '.',
                    style: TextStyle(
                      fontStyle: FontStyle.italic,
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: <Widget>[
                OutlinedButton.icon(
                  onPressed: () =>
                      context.push('${AppRouter.settingsRoute}?tab=1'),
                  icon: const Icon(Icons.settings, size: 20),
                  label: const Text('Open Settings → AI Platform'),
                ),
                OutlinedButton.icon(
                  onPressed: () =>
                      context.push('${AppRouter.settingsRoute}?tab=1'),
                  icon: const Icon(Icons.picture_as_pdf, size: 20),
                  label: const Text('Open Settings → MinerU'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
