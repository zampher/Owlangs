// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

import '../../../../l10n/app_localizations.dart';

const double kPdfFontSizeMin = 5.0;
const double kPdfFontSizeMax = 72.0;
const double kPdfFontSizeStep = 0.1;

double snapPdfFontSize(double value) {
  final double clamped = value.clamp(kPdfFontSizeMin, kPdfFontSizeMax);
  final int steps = (clamped / kPdfFontSizeStep).round();
  return double.parse((steps * kPdfFontSizeStep).toStringAsFixed(1));
}

/// Result from the PDF typography settings dialog.
class SegmentPdfTypographyResult {
  const SegmentPdfTypographyResult({
    required this.reset,
    this.fontSizePt,
    this.fontWeight,
    this.fontStyle,
  });

  final bool reset;
  final double? fontSizePt;
  final String? fontWeight;
  final String? fontStyle;
}

/// Show dialog to adjust PDF font size, weight, and style with live preview.
Future<SegmentPdfTypographyResult?> showSegmentPdfTypographyDialog({
  required BuildContext context,
  required String previewText,
  required bool hasUserOverride,
  required double initialFontSizePt,
  required String initialFontWeight,
  required String initialFontStyle,
}) {
  return showDialog<SegmentPdfTypographyResult>(
    context: context,
    builder: (BuildContext dialogContext) {
      return _SegmentPdfTypographyDialog(
        previewText: previewText,
        hasUserOverride: hasUserOverride,
        initialFontSizePt: initialFontSizePt,
        initialFontWeight: initialFontWeight,
        initialFontStyle: initialFontStyle,
      );
    },
  );
}

class _SegmentPdfTypographyDialog extends StatefulWidget {
  const _SegmentPdfTypographyDialog({
    required this.previewText,
    required this.hasUserOverride,
    required this.initialFontSizePt,
    required this.initialFontWeight,
    required this.initialFontStyle,
  });

  final String previewText;
  final bool hasUserOverride;
  final double initialFontSizePt;
  final String initialFontWeight;
  final String initialFontStyle;

  @override
  State<_SegmentPdfTypographyDialog> createState() =>
      _SegmentPdfTypographyDialogState();
}

class _SegmentPdfTypographyDialogState extends State<_SegmentPdfTypographyDialog> {
  late double _fontSizePt;
  late bool _isBold;
  late bool _isItalic;

  @override
  void initState() {
    super.initState();
    _fontSizePt = snapPdfFontSize(widget.initialFontSizePt);
    _isBold = widget.initialFontWeight == 'bold';
    _isItalic = widget.initialFontStyle == 'italic';
  }

  String _previewSample() {
    final String trimmed = widget.previewText.trim();
    if (trimmed.isEmpty) {
      return 'Aa 字体预览 Font preview 123';
    }
    const int maxLen = 160;
    if (trimmed.length <= maxLen) {
      return trimmed;
    }
    return '${trimmed.substring(0, maxLen)}…';
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = AppLocalizations.of(context)!;
    final ThemeData theme = Theme.of(context);
    final ColorScheme colors = theme.colorScheme;
    final double previewScale = (_fontSizePt / 12.0).clamp(0.45, 2.4);

    return AlertDialog(
      title: Text(l10n.segmentPdfTypographyTitle),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(
              l10n.segmentPdfTypographyPreviewLabel,
              style: theme.textTheme.labelMedium?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Container(
              constraints: const BoxConstraints(minHeight: 88, maxHeight: 160),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colors.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: colors.outlineVariant),
              ),
              child: SingleChildScrollView(
                child: Text(
                  _previewSample(),
                  style: TextStyle(
                    fontSize: 12.0 * previewScale,
                    fontWeight: _isBold ? FontWeight.bold : FontWeight.normal,
                    fontStyle:
                        _isItalic ? FontStyle.italic : FontStyle.normal,
                    height: 1.25,
                    color: colors.onSurface,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              _fontSizePt.toStringAsFixed(1),
              textAlign: TextAlign.center,
              style: theme.textTheme.titleLarge,
            ),
            Slider(
              value: _fontSizePt,
              min: kPdfFontSizeMin,
              max: kPdfFontSizeMax,
              divisions:
                  ((kPdfFontSizeMax - kPdfFontSizeMin) / kPdfFontSizeStep)
                      .round(),
              label: _fontSizePt.toStringAsFixed(1),
              onChanged: (double value) {
                setState(() {
                  _fontSizePt = snapPdfFontSize(value);
                });
              },
            ),
            const SizedBox(height: 4),
            ToggleButtons(
              isSelected: <bool>[_isBold, _isItalic],
              onPressed: (int index) {
                setState(() {
                  if (index == 0) {
                    _isBold = !_isBold;
                  } else {
                    _isItalic = !_isItalic;
                  }
                });
              },
              borderRadius: BorderRadius.circular(8),
              children: <Widget>[
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    l10n.segmentPdfTypographyBold,
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: _isBold ? colors.onPrimary : colors.onSurface,
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    l10n.segmentPdfTypographyItalic,
                    style: TextStyle(
                      fontStyle: FontStyle.italic,
                      color: _isItalic ? colors.onPrimary : colors.onSurface,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
      actions: <Widget>[
        if (widget.hasUserOverride)
          TextButton(
            onPressed: () {
              Navigator.of(context).pop(
                const SegmentPdfTypographyResult(reset: true),
              );
            },
            child: Text(l10n.segmentPdfFontSizeReset),
          ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(MaterialLocalizations.of(context).cancelButtonLabel),
        ),
        FilledButton(
          onPressed: () {
            Navigator.of(context).pop(
              SegmentPdfTypographyResult(
                reset: false,
                fontSizePt: _fontSizePt,
                fontWeight: _isBold ? 'bold' : 'regular',
                fontStyle: _isItalic ? 'italic' : 'normal',
              ),
            );
          },
          child: Text(l10n.segmentPdfFontSizeApply),
        ),
      ],
    );
  }
}
