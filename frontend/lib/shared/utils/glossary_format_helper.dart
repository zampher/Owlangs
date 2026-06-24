// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import '../../core/utils/file_picker_helper.dart';
import '../../l10n/app_localizations.dart';
import '../models/language_model.dart';

/// Shared glossary CSV template export and format help for settings & translation UI.
class GlossaryFormatHelper {
  GlossaryFormatHelper._();

  static Uint8List templateCsvBytes() {
    const String content =
        'src,dst,category,target_lang\nHello,你好,Example,zh\n';
    return Uint8List.fromList(
      <int>[0xEF, 0xBB, 0xBF, ...utf8.encode(content)],
    );
  }

  static String buildFormatHelpText(AppLocalizations l10n) {
    final String targetLangList = LanguageService.supportedLanguages
        .map(
          (Language lang) =>
              '• ${lang.code} — ${lang.nativeName} (${lang.name})',
        )
        .join('\n');
    return '${l10n.settingsGlossaryFormatHelpContent}\n\n'
        '${l10n.settingsGlossaryFormatHelpTargetLangListTitle}\n'
        '$targetLangList';
  }

  static void showFormatHelpDialog(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    showDialog<void>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: Text(l10n.settingsGlossaryFormatHelpTitle),
        content: SingleChildScrollView(
          child: SelectableText(
            buildFormatHelpText(l10n),
            style: TextStyle(
              fontSize: 14,
              color: Theme.of(dialogContext).colorScheme.onSurface,
            ),
          ),
        ),
        actions: <Widget>[
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: Text(l10n.commonOk),
          ),
        ],
      ),
    );
  }

  static Future<void> exportTemplate(BuildContext context) async {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final Uint8List bytes = templateCsvBytes();
    const String baseName = 'glossary_template';
    try {
      if (kIsWeb) {
        await FileSaver.instance.saveFile(
          name: baseName,
          bytes: bytes,
          ext: 'csv',
        );
      } else {
        final String? savePath = await FilePickerHelper.saveFile(
          fileName: '$baseName.csv',
          dialogTitle: l10n.settingsGlossarySaveTemplateCsv,
          type: FileType.custom,
          allowedExtensions: <String>['csv'],
        );
        if (savePath == null) {
          return;
        }
        final File f = File(savePath);
        await f.writeAsBytes(bytes, flush: true);
      }
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.settingsGlossaryTemplateExportedSnack)),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              l10n.settingsGlossaryExportFailedSnack(e.toString()),
            ),
          ),
        );
      }
    }
  }
}
