// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../l10n/app_localizations.dart';
import '../../../../shared/services/translation_service.dart';
import '../../../../shared/utils/dialog_helper.dart';
import '../../providers/format_settings_provider.dart';
import 'preview_selection.dart';

/// Describes one selectable preview mode in the dialog.
class PreviewModeOption {
  const PreviewModeOption({
    required this.mode,
    required this.label,
    required this.description,
  });

  final TranslationPreviewMode mode;
  final String label;
  final String description;
}

List<PreviewModeOption> buildPreviewModeOptions({
  required AppLocalizations l10n,
  required bool isPdfFile,
  required bool hasPdfDownload,
  bool isImageFile = false,
  bool hasImageDownload = false,
}) {
  final List<PreviewModeOption> options = <PreviewModeOption>[
    PreviewModeOption(
      mode: TranslationPreviewMode.html,
      label: l10n.translationPreviewModeHtml,
      description: l10n.translationPreviewModeHtmlDesc,
    ),
  ];
  if (isImageFile && hasImageDownload) {
    options.add(
      PreviewModeOption(
        mode: TranslationPreviewMode.imageOriginalLayout,
        label: l10n.translationExportImageOriginalLayout,
        description: l10n.translationExportImageOriginalLayoutDesc,
      ),
    );
  }
  if (isPdfFile && hasPdfDownload) {
    options.add(
      PreviewModeOption(
        mode: TranslationPreviewMode.pdfPreserve,
        label: l10n.translationExportPdfPreserveLayout,
        description: l10n.translationExportPdfPreserveLayoutDesc,
      ),
    );
    options.add(
      PreviewModeOption(
        mode: TranslationPreviewMode.pdfReflow,
        label: l10n.translationExportPdfReflow,
        description: l10n.translationExportPdfReflowDesc,
      ),
    );
  }
  return options;
}

/// Show unified preview settings dialog (mode + format options).
Future<PreviewSelection?> showTranslationPreviewDialog({
  required BuildContext context,
  required WidgetRef ref,
  required String taskId,
  required bool isPdfFile,
  required bool hasPdfDownload,
  required String resolvedWorkflowType,
  bool isImageFile = false,
  bool hasImageDownload = false,
  TranslationPreviewMode initialMode = TranslationPreviewMode.html,
  bool initialFullDocumentCompare = false,
  bool initialSyncScroll = false,
}) async {
  final AppLocalizations l10n = AppLocalizations.of(context)!;
  final List<PreviewModeOption> modeOptions = buildPreviewModeOptions(
    l10n: l10n,
    isPdfFile: isPdfFile,
    hasPdfDownload: hasPdfDownload,
    isImageFile: isImageFile,
    hasImageDownload: hasImageDownload,
  );
  if (modeOptions.isEmpty) {
    return null;
  }

  TranslationPreviewMode selectedMode = initialMode;
  if (!modeOptions.any((PreviewModeOption o) => o.mode == selectedMode)) {
    selectedMode = modeOptions.first.mode;
  }
  int selectedModeIndex =
      modeOptions.indexWhere((PreviewModeOption o) => o.mode == selectedMode);
  if (selectedModeIndex < 0) {
    selectedModeIndex = 0;
    selectedMode = modeOptions.first.mode;
  }
  bool fullDocumentCompareSelected = initialFullDocumentCompare;
  bool syncScrollSelected = fullDocumentCompareSelected &&
      (initialFullDocumentCompare && initialMode == selectedMode
          ? initialSyncScroll
          : selectedMode.defaultFullCompareSyncScroll);

  Map<String, dynamic>? status;
  try {
    status = await TranslationService().getStatus(taskId);
  } catch (_) {
    status = null;
  }
  final bool hasTables = status?['has_tables'] as bool? ?? false;
  final bool hasInterlineEquations =
      status?['has_interline_equations'] as bool? ?? false;
  final bool hasCharts = status?['has_charts'] as bool? ?? false;

  final bool isPdfWorkflow =
      resolvedWorkflowType == 'markdown_based' || isPdfFile;
  final bool isImageWorkflow =
      isImageFile && resolvedWorkflowType == 'markdown_based';
  final bool showFormatOptions = (isPdfWorkflow || isImageWorkflow) &&
      (hasTables || hasInterlineEquations || hasCharts);
  final bool supportsBilingual = <String>{
    'markdown_based',
    'txt',
    'html',
    'srt',
    'epub',
    'mobi',
    'docx',
    'pptx',
    'xlsx',
  }.contains(resolvedWorkflowType);

  final List<Map<String, dynamic>> colorOptions = <Map<String, dynamic>>[
    {
      'value': '',
      'color': Colors.transparent,
      'label': l10n.translationExportColorDefault,
    },
    {
      'value': 'gray',
      'color': Colors.grey,
      'label': l10n.translationExportColorGray,
    },
    {
      'value': 'blue',
      'color': Colors.blue,
      'label': l10n.translationExportColorBlue,
    },
    {
      'value': 'red',
      'color': Colors.red,
      'label': l10n.translationExportColorRed,
    },
    {
      'value': 'green',
      'color': Colors.green,
      'label': l10n.translationExportColorGreen,
    },
    {
      'value': 'orange',
      'color': Colors.orange,
      'label': l10n.translationExportColorOrange,
    },
    {
      'value': 'black',
      'color': Colors.black,
      'label': l10n.translationExportColorBlack,
    },
  ];

  return DialogHelper.showGeneralDialog<PreviewSelection>(
    context: context,
    barrierColor: Colors.black54,
    barrierLabel: l10n.translationPreviewDialogTitle,
    useRootNavigator: true,
    pageBuilder: (
      BuildContext dialogContext,
      Animation<double> animation,
      Animation<double> secondaryAnimation,
    ) =>
        Consumer(
      builder: (BuildContext context, WidgetRef ref, Widget? child) {
        final FormatSettings formatSettings =
            ref.watch(formatSettingsProviderFamily(taskId));
        String tableFormat =
            formatSettings.getTableFormat(isPdfWorkflow: isPdfWorkflow);
        String equationFormat =
            formatSettings.getEquationFormat(isPdfWorkflow: isPdfWorkflow);
        String chartFormat =
            formatSettings.getChartFormat(isPdfWorkflow: isPdfWorkflow);
        String coverColorMode = formatSettings.getCoverColorMode();
        String bilingualOrder =
            formatSettings.bilingualOrder ?? 'target_after_source';
        bool sourceTextItalic = formatSettings.sourceTextItalic ?? false;
        String sourceTextColor = formatSettings.sourceTextColor ?? '';
        bool targetTextItalic = formatSettings.targetTextItalic ?? true;
        String targetTextColor = formatSettings.targetTextColor ?? 'gray';

        return StatefulBuilder(
          builder: (BuildContext context, StateSetter setDialogState) {
            selectedMode = modeOptions[selectedModeIndex].mode;
            final bool bilingualAvailable = supportsBilingual &&
                selectedMode.supportsBilingualExportOptions;
            final bool bilingualExport = bilingualAvailable &&
                (formatSettings.bilingualExport ?? false);

            return Material(
              type: MaterialType.transparency,
              child: AlertDialog(
                title: Text(l10n.translationPreviewDialogTitle),
                content: SizedBox(
                  width: 720,
                  height: 420,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Expanded(
                        flex: 2,
                        child: SingleChildScrollView(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(
                                l10n.translationPreviewModeSectionTitle,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 16,
                                ),
                              ),
                              const SizedBox(height: 8),
                              for (int i = 0; i < modeOptions.length; i++)
                                RadioListTile<int>(
                                  value: i,
                                  groupValue: selectedModeIndex,
                                  onChanged: (int? value) {
                                    if (value == null) {
                                      return;
                                    }
                                    setDialogState(() {
                                      selectedModeIndex = value;
                                      selectedMode = modeOptions[value].mode;
                                      if (selectedMode.defaultFullDocumentCompare) {
                                        fullDocumentCompareSelected = true;
                                        syncScrollSelected =
                                            selectedMode.defaultFullCompareSyncScroll;
                                      } else {
                                        syncScrollSelected = false;
                                      }
                                    });
                                  },
                                  title: Text(modeOptions[i].label),
                                  subtitle: Text(modeOptions[i].description),
                                  dense: true,
                                  contentPadding: EdgeInsets.zero,
                                ),
                              const Divider(height: 24),
                              CheckboxListTile(
                                value: fullDocumentCompareSelected,
                                onChanged: (bool? value) {
                                  setDialogState(() {
                                    fullDocumentCompareSelected = value ?? false;
                                    if (fullDocumentCompareSelected) {
                                      syncScrollSelected =
                                          selectedMode.defaultFullCompareSyncScroll;
                                    } else {
                                      syncScrollSelected = false;
                                    }
                                  });
                                },
                                title: Text(
                                  l10n.translationPreviewFullDocumentCompare,
                                ),
                                subtitle: Text(
                                  l10n.translationPreviewFullDocumentCompareDesc,
                                ),
                                controlAffinity: ListTileControlAffinity.leading,
                                contentPadding: EdgeInsets.zero,
                                dense: true,
                              ),
                              if (fullDocumentCompareSelected)
                                Padding(
                                  padding: const EdgeInsets.only(left: 16),
                                  child: CheckboxListTile(
                                    value: syncScrollSelected,
                                    onChanged: (bool? value) {
                                      setDialogState(() {
                                        syncScrollSelected = value ?? false;
                                      });
                                    },
                                    title: Text(
                                      l10n.translationPreviewSyncScroll,
                                    ),
                                    subtitle: Text(
                                      l10n.translationPreviewSyncScrollDesc,
                                    ),
                                    controlAffinity:
                                        ListTileControlAffinity.leading,
                                    contentPadding: EdgeInsets.zero,
                                    dense: true,
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
                      const VerticalDivider(width: 1),
                      Expanded(
                        flex: 3,
                        child: SingleChildScrollView(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              if (showFormatOptions &&
                                  selectedMode.usesHtmlPreview) ...<Widget>[
                                Text(
                                  l10n.translationExportFormatOptionsTitle,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 16,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                if (hasTables)
                                  _FormatRadioRow(
                                    label: l10n.translationExportTableFormatLabel,
                                    value: tableFormat,
                                    options: <String, String>{
                                      'image': l10n.translationExportChartFormatImage,
                                      'html': l10n.translationExportChartFormatHtml,
                                    },
                                    onChanged: (String value) {
                                      setDialogState(() => tableFormat = value);
                                      ref
                                          .read(formatSettingsProviderFamily(
                                                  taskId)
                                              .notifier)
                                          .setTableFormat(value);
                                    },
                                  ),
                                if (hasInterlineEquations)
                                  _FormatRadioRow(
                                    label:
                                        l10n.translationExportEquationFormatLabel,
                                    value: equationFormat,
                                    options: <String, String>{
                                      'image':
                                          l10n.translationExportEquationFormatImage,
                                      'text':
                                          l10n.translationExportEquationFormatLatex,
                                    },
                                    onChanged: (String value) {
                                      setDialogState(
                                          () => equationFormat = value);
                                      ref
                                          .read(formatSettingsProviderFamily(
                                                  taskId)
                                              .notifier)
                                          .setEquationFormat(value);
                                    },
                                  ),
                                if (hasCharts)
                                  _FormatRadioRow(
                                    label: l10n.translationExportChartFormatLabel,
                                    value: chartFormat,
                                    options: <String, String>{
                                      'image': l10n.translationExportChartFormatImage,
                                      'html': l10n.translationExportChartFormatHtml,
                                    },
                                    onChanged: (String value) {
                                      setDialogState(() => chartFormat = value);
                                      ref
                                          .read(formatSettingsProviderFamily(
                                                  taskId)
                                              .notifier)
                                          .setChartFormat(value);
                                    },
                                  ),
                                const Divider(height: 24),
                              ],
                              if (showFormatOptions &&
                                  selectedMode.usesPdfPreview) ...<Widget>[
                                Text(
                                  l10n.translationExportFormatOptionsTitle,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 16,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                if (hasTables)
                                  _FormatRadioRow(
                                    label: l10n.translationExportTableFormatLabel,
                                    value: tableFormat,
                                    options: <String, String>{
                                      'image': l10n.translationExportChartFormatImage,
                                      'html': l10n.translationExportChartFormatHtml,
                                    },
                                    onChanged: (String value) {
                                      setDialogState(() => tableFormat = value);
                                      ref
                                          .read(formatSettingsProviderFamily(
                                                  taskId)
                                              .notifier)
                                          .setTableFormat(value);
                                    },
                                  ),
                                if (hasInterlineEquations)
                                  _FormatRadioRow(
                                    label:
                                        l10n.translationExportEquationFormatLabel,
                                    value: equationFormat,
                                    options: <String, String>{
                                      'image':
                                          l10n.translationExportEquationFormatImage,
                                      'text':
                                          l10n.translationExportEquationFormatLatex,
                                    },
                                    onChanged: (String value) {
                                      setDialogState(
                                          () => equationFormat = value);
                                      ref
                                          .read(formatSettingsProviderFamily(
                                                  taskId)
                                              .notifier)
                                          .setEquationFormat(value);
                                    },
                                  ),
                                if (hasCharts)
                                  _FormatRadioRow(
                                    label: l10n.translationExportChartFormatLabel,
                                    value: chartFormat,
                                    options: <String, String>{
                                      'image': l10n.translationExportChartFormatImage,
                                      'html': l10n.translationExportChartFormatHtml,
                                    },
                                    onChanged: (String value) {
                                      setDialogState(() => chartFormat = value);
                                      ref
                                          .read(formatSettingsProviderFamily(
                                                  taskId)
                                              .notifier)
                                          .setChartFormat(value);
                                    },
                                  ),
                                const Divider(height: 24),
                              ],
                              if (isImageWorkflow) ...<Widget>[
                                Text(
                                  l10n.translationExportFormatOptionsTitle,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 16,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                _FormatRadioRow(
                                  label: l10n.translationImageCoverColorModeLabel,
                                  value: coverColorMode,
                                  options: <String, String>{
                                    'max': l10n.translationImageCoverColorModeMax,
                                    'min': l10n.translationImageCoverColorModeMin,
                                    'avg': l10n.translationImageCoverColorModeAvg,
                                  },
                                  onChanged: (String value) {
                                    setDialogState(() => coverColorMode = value);
                                    ref
                                        .read(formatSettingsProviderFamily(
                                                taskId)
                                            .notifier)
                                        .setCoverColorMode(value);
                                  },
                                ),
                                const Divider(height: 24),
                              ],
                              if (supportsBilingual) ...<Widget>[
                                Opacity(
                                  opacity: bilingualAvailable ? 1.0 : 0.4,
                                  child: Row(
                                    children: <Widget>[
                                      Checkbox(
                                        value: bilingualExport,
                                        onChanged: bilingualAvailable
                                            ? (bool? value) {
                                                if (value == null) {
                                                  return;
                                                }
                                                ref
                                                    .read(
                                                      formatSettingsProviderFamily(
                                                              taskId)
                                                          .notifier,
                                                    )
                                                    .setBilingualExport(value);
                                              }
                                            : null,
                                      ),
                                      Expanded(
                                        child: Text(
                                          l10n.translationExportBilingualExport,
                                          style: const TextStyle(
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                Opacity(
                                  opacity: bilingualAvailable && bilingualExport
                                      ? 1.0
                                      : 0.4,
                                  child: AbsorbPointer(
                                    absorbing:
                                        !bilingualAvailable || !bilingualExport,
                                    child: Padding(
                                      padding:
                                          const EdgeInsets.only(left: 32),
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: <Widget>[
                                          Row(
                                            children: <Widget>[
                                              Radio<String>(
                                                value: 'target_after_source',
                                                groupValue: bilingualOrder,
                                                onChanged: (String? value) {
                                                  if (value == null) {
                                                    return;
                                                  }
                                                  setDialogState(() {
                                                    bilingualOrder = value;
                                                  });
                                                  ref
                                                      .read(
                                                        formatSettingsProviderFamily(
                                                                taskId)
                                                            .notifier,
                                                      )
                                                      .setBilingualOrder(value);
                                                },
                                              ),
                                              Text(l10n
                                                  .translationExportBilingualOrderTargetAfter),
                                              const SizedBox(width: 16),
                                              Radio<String>(
                                                value: 'target_before_source',
                                                groupValue: bilingualOrder,
                                                onChanged: (String? value) {
                                                  if (value == null) {
                                                    return;
                                                  }
                                                  setDialogState(() {
                                                    bilingualOrder = value;
                                                  });
                                                  ref
                                                      .read(
                                                        formatSettingsProviderFamily(
                                                                taskId)
                                                            .notifier,
                                                      )
                                                      .setBilingualOrder(value);
                                                },
                                              ),
                                              Text(l10n
                                                  .translationExportBilingualOrderTargetBefore),
                                            ],
                                          ),
                                          Row(
                                            children: <Widget>[
                                              Checkbox(
                                                value: sourceTextItalic,
                                                onChanged: (bool? value) {
                                                  if (value == null) {
                                                    return;
                                                  }
                                                  setDialogState(() {
                                                    sourceTextItalic = value;
                                                  });
                                                  ref
                                                      .read(
                                                        formatSettingsProviderFamily(
                                                                taskId)
                                                            .notifier,
                                                      )
                                                      .setSourceTextItalic(
                                                          value);
                                                },
                                              ),
                                              Text(l10n
                                                  .translationExportSourceTextItalic),
                                              const SizedBox(width: 24),
                                              Checkbox(
                                                value: targetTextItalic,
                                                onChanged: (bool? value) {
                                                  if (value == null) {
                                                    return;
                                                  }
                                                  setDialogState(() {
                                                    targetTextItalic = value;
                                                  });
                                                  ref
                                                      .read(
                                                        formatSettingsProviderFamily(
                                                                taskId)
                                                            .notifier,
                                                      )
                                                      .setTargetTextItalic(
                                                          value);
                                                },
                                              ),
                                              Text(l10n
                                                  .translationExportTargetTextItalic),
                                            ],
                                          ),
                                          _ColorRow(
                                            label: l10n
                                                .translationExportSourceTextColor,
                                            selected: sourceTextColor,
                                            options: colorOptions,
                                            onSelected: (String value) {
                                              setDialogState(() {
                                                sourceTextColor = value;
                                              });
                                              ref
                                                  .read(
                                                    formatSettingsProviderFamily(
                                                            taskId)
                                                        .notifier,
                                                  )
                                                  .setSourceTextColor(value);
                                            },
                                          ),
                                          _ColorRow(
                                            label: l10n
                                                .translationExportTargetTextColor,
                                            selected: targetTextColor,
                                            options: colorOptions,
                                            onSelected: (String value) {
                                              setDialogState(() {
                                                targetTextColor = value;
                                              });
                                              ref
                                                  .read(
                                                    formatSettingsProviderFamily(
                                                            taskId)
                                                        .notifier,
                                                  )
                                                  .setTargetTextColor(value);
                                            },
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                              if (!showFormatOptions && !supportsBilingual)
                                Text(
                                  l10n.translationPreviewNoExtraOptions,
                                  style: TextStyle(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                actions: <Widget>[
                  TextButton(
                    onPressed: () =>
                        Navigator.of(context, rootNavigator: true).pop(),
                    child: Text(l10n.commonCancel),
                  ),
                  FilledButton(
                    onPressed: () {
                      Navigator.of(context, rootNavigator: true).pop(
                        PreviewSelection(
                          mode: selectedMode,
                          fullDocumentCompare: fullDocumentCompareSelected,
                          syncScroll: fullDocumentCompareSelected &&
                              syncScrollSelected,
                        ),
                      );
                    },
                    child: Text(l10n.translationPreviewStart),
                  ),
                ],
              ),
            );
          },
        );
      },
    ),
  );
}

class _FormatRadioRow extends StatelessWidget {
  const _FormatRadioRow({
    required this.label,
    required this.value,
    required this.options,
    required this.onChanged,
  });

  final String label;
  final String value;
  final Map<String, String> options;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(
            child: Wrap(
              spacing: 8,
              children: options.entries.map((MapEntry<String, String> e) {
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Radio<String>(
                      value: e.key,
                      groupValue: value,
                      onChanged: (String? v) {
                        if (v != null) {
                          onChanged(v);
                        }
                      },
                    ),
                    Text(e.value),
                  ],
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }
}

class _ColorRow extends StatelessWidget {
  const _ColorRow({
    required this.label,
    required this.selected,
    required this.options,
    required this.onSelected,
  });

  final String label;
  final String selected;
  final List<Map<String, dynamic>> options;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: <Widget>[
          Text(label),
          const SizedBox(width: 8),
          ...options.map((Map<String, dynamic> option) {
            final String value = option['value'] as String;
            final Color color = option['color'] as Color;
            final String? tooltip = option['label'] as String?;
            final bool isSelected = selected == value;
            final Widget circle = GestureDetector(
              onTap: () => onSelected(value),
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 4),
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isSelected
                        ? Theme.of(context).colorScheme.primary
                        : (color == Colors.transparent
                            ? Colors.grey.shade300
                            : Colors.transparent),
                    width: 2,
                  ),
                ),
              ),
            );
            return tooltip != null
                ? Tooltip(message: tooltip, child: circle)
                : circle;
          }),
        ],
      ),
    );
  }
}
