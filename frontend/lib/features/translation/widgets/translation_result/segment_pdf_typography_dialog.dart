// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

import '../../../../l10n/app_localizations.dart';

const double kPdfFontSizeMin = 0.5;
const double kPdfFontSizeMax = 72.0;
const double kPdfFontSizeStep = 0.1;

const double kPdfLeadingEmMin = 0.35;
const double kPdfLeadingEmMax = 3.0;
const double kPdfLeadingEmStep = 0.05;
const double kPdfLeadingEmDefault = 1.25;

/// Gate PDF line-spacing UI until Typst overlay leading overrides are reliable.
const bool kPdfLeadingTypographyUiEnabled = false;

double snapPdfFontSize(double value) {
  final double clamped = value.clamp(kPdfFontSizeMin, kPdfFontSizeMax);
  final int steps = (clamped / kPdfFontSizeStep).round();
  return double.parse((steps * kPdfFontSizeStep).toStringAsFixed(1));
}

/// Resolved segment font size for UI labels and batch ± steps (single source of truth).
double? effectivePdfSegmentFontSizePtOrNull({
  String? fontSizeSource,
  double? fontSizePt,
  double? computedFontSizePt,
}) {
  // User override: show persisted pt (strict render target). Auto: use computed dry-run.
  if (fontSizeSource == 'user' && fontSizePt != null) {
    return snapPdfFontSize(fontSizePt);
  }
  if (computedFontSizePt != null) {
    return snapPdfFontSize(computedFontSizePt);
  }
  if (fontSizePt != null) {
    return snapPdfFontSize(fontSizePt);
  }
  return null;
}

double effectivePdfSegmentFontSizePt({
  String? fontSizeSource,
  double? fontSizePt,
  double? computedFontSizePt,
}) {
  return effectivePdfSegmentFontSizePtOrNull(
        fontSizeSource: fontSizeSource,
        fontSizePt: fontSizePt,
        computedFontSizePt: computedFontSizePt,
      ) ??
      kPdfFontSizeMin;
}

double effectivePdfSegmentFontSizePtFromMetadata(
  Map<String, dynamic> metadata,
) {
  double? readDouble(dynamic raw) {
    if (raw is num) {
      return raw.toDouble();
    }
    if (raw is String) {
      return double.tryParse(raw);
    }
    return null;
  }

  return effectivePdfSegmentFontSizePt(
    fontSizeSource: metadata['font_size_source'] as String?,
    fontSizePt: readDouble(metadata['font_size_pt']),
    computedFontSizePt: readDouble(metadata['computed_font_size_pt']),
  );
}

double snapPdfLeadingEm(double value) {
  final double clamped = value.clamp(kPdfLeadingEmMin, kPdfLeadingEmMax);
  final int steps = (clamped / kPdfLeadingEmStep).round();
  return double.parse((steps * kPdfLeadingEmStep).toStringAsFixed(2));
}

/// Which fields the typography dialog edits.
enum SegmentPdfTypographyDialogMode {
  all,
  fontOnly,
  leadingOnly,
}

/// Result from the PDF typography settings dialog.
class SegmentPdfTypographyResult {
  const SegmentPdfTypographyResult({
    required this.reset,
    required this.mode,
    this.fontSizePt,
    this.fontWeight,
    this.fontStyle,
    this.leadingEm,
  });

  final bool reset;
  final SegmentPdfTypographyDialogMode mode;
  final double? fontSizePt;
  final String? fontWeight;
  final String? fontStyle;
  final double? leadingEm;
}

/// Show dialog to adjust PDF font size, weight, style, and/or leading with preview.
Future<SegmentPdfTypographyResult?> showSegmentPdfTypographyDialog({
  required BuildContext context,
  required String previewText,
  required bool hasUserOverride,
  required double initialFontSizePt,
  required String initialFontWeight,
  required String initialFontStyle,
  required double initialLeadingEm,
  SegmentPdfTypographyDialogMode mode = SegmentPdfTypographyDialogMode.all,
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
        initialLeadingEm: initialLeadingEm,
        mode: mode,
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
    required this.initialLeadingEm,
    required this.mode,
  });

  final String previewText;
  final bool hasUserOverride;
  final double initialFontSizePt;
  final String initialFontWeight;
  final String initialFontStyle;
  final double initialLeadingEm;
  final SegmentPdfTypographyDialogMode mode;

  @override
  State<_SegmentPdfTypographyDialog> createState() =>
      _SegmentPdfTypographyDialogState();
}

class _SegmentPdfTypographyDialogState extends State<_SegmentPdfTypographyDialog> {
  late double _fontSizePt;
  late double _leadingEm;
  late bool _isBold;
  late bool _isItalic;

  @override
  void initState() {
    super.initState();
    _fontSizePt = snapPdfFontSize(widget.initialFontSizePt);
    _leadingEm = snapPdfLeadingEm(widget.initialLeadingEm);
    _isBold = widget.initialFontWeight == 'bold';
    _isItalic = widget.initialFontStyle == 'italic';
  }

  String _previewSample() {
    final String trimmed = widget.previewText.trim();
    if (trimmed.isEmpty) {
      return 'Aa 字体预览 Font preview 123\n第二行预览 Second line preview';
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
    final bool showFontControls =
        widget.mode != SegmentPdfTypographyDialogMode.leadingOnly;
    final bool showLeadingControls = kPdfLeadingTypographyUiEnabled &&
        widget.mode != SegmentPdfTypographyDialogMode.fontOnly;
    final double previewScale = showFontControls
        ? (_fontSizePt / 12.0).clamp(0.45, 2.4)
        : 1.0;

    final String title;
    switch (widget.mode) {
      case SegmentPdfTypographyDialogMode.fontOnly:
        title = l10n.segmentPdfTypographyFontTitle;
      case SegmentPdfTypographyDialogMode.leadingOnly:
        title = l10n.segmentPdfTypographyLeadingTitle;
      case SegmentPdfTypographyDialogMode.all:
        title = l10n.segmentPdfTypographyTitle;
    }

    return AlertDialog(
      title: Text(title),
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
                    fontWeight: showFontControls && _isBold
                        ? FontWeight.bold
                        : FontWeight.normal,
                    fontStyle: showFontControls && _isItalic
                        ? FontStyle.italic
                        : FontStyle.normal,
                    height: showLeadingControls
                        ? _leadingEm
                        : widget.initialLeadingEm,
                    color: colors.onSurface,
                  ),
                ),
              ),
            ),
            if (showFontControls) ...<Widget>[
              const SizedBox(height: 16),
              Text(
                l10n.segmentPdfTypographyFontSizeLabel(
                  _fontSizePt.toStringAsFixed(1),
                ),
                style: theme.textTheme.labelMedium,
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
            if (showLeadingControls) ...<Widget>[
              SizedBox(height: showFontControls ? 16 : 16),
              Text(
                l10n.segmentPdfTypographyLeadingLabel(
                  _leadingEm.toStringAsFixed(2),
                ),
                style: theme.textTheme.labelMedium,
              ),
              Slider(
                value: _leadingEm,
                min: kPdfLeadingEmMin,
                max: kPdfLeadingEmMax,
                divisions:
                    ((kPdfLeadingEmMax - kPdfLeadingEmMin) / kPdfLeadingEmStep)
                        .round(),
                label: _leadingEm.toStringAsFixed(2),
                onChanged: (double value) {
                  setState(() {
                    _leadingEm = snapPdfLeadingEm(value);
                  });
                },
              ),
            ],
          ],
        ),
      ),
      actions: <Widget>[
        if (widget.hasUserOverride)
          TextButton(
            onPressed: () {
              Navigator.of(context).pop(
                SegmentPdfTypographyResult(
                  reset: true,
                  mode: widget.mode,
                ),
              );
            },
            child: Text(
              widget.mode == SegmentPdfTypographyDialogMode.leadingOnly
                  ? l10n.segmentPdfTypographyResetLeading
                  : widget.mode == SegmentPdfTypographyDialogMode.fontOnly
                      ? l10n.segmentPdfTypographyResetFont
                      : l10n.segmentPdfFontSizeReset,
            ),
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
                mode: widget.mode,
                fontSizePt: showFontControls ? _fontSizePt : null,
                fontWeight: showFontControls
                    ? (_isBold ? 'bold' : 'regular')
                    : null,
                fontStyle: showFontControls
                    ? (_isItalic ? 'italic' : 'normal')
                    : null,
                leadingEm: showLeadingControls ? _leadingEm : null,
              ),
            );
          },
          child: Text(l10n.segmentPdfFontSizeApply),
        ),
      ],
    );
  }
}
