// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';

import '../../../../l10n/app_localizations.dart';
import '../../utils/segment_type_utils.dart';

/// Shared border-style + stroke-width menu used by task toolbar and segment chip.
List<Widget> buildPdfTableBorderStrokeMenuChildren({
  required BuildContext context,
  required AppLocalizations l10n,
  required String borderStyle,
  required double strokePt,
  bool showFollowTask = false,
  bool hasBorderStyleOverride = false,
  VoidCallback? onFollowTask,
  ValueChanged<String>? onBorderStyleChanged,
  ValueChanged<double>? onStrokePtChanged,
}) {
  final ColorScheme colors = Theme.of(context).colorScheme;
  final bool canEditStyle = onBorderStyleChanged != null || onFollowTask != null;
  final bool showWeightMenu =
      borderStyle != 'none' && onStrokePtChanged != null;
  final List<Widget> children = <Widget>[];

  if (onBorderStyleChanged != null || showFollowTask) {
    children.add(
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
        child: Text(
          l10n.segmentTableBorderMenuTitle,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: colors.onSurfaceVariant,
          ),
        ),
      ),
    );
    if (showFollowTask) {
      children.add(
        MenuItemButton(
          onPressed: canEditStyle ? onFollowTask : null,
          child: PdfTableBorderStyleMenuRow(
            style: 'follow_task',
            label: l10n.segmentTableBorderFollowGlobal,
            checked: !hasBorderStyleOverride,
          ),
        ),
      );
    }
    children.addAll(
      kPdfTableBorderStyleOptions.map((String optionStyle) {
        final bool selected = showFollowTask
            ? hasBorderStyleOverride &&
                isPdfTableBorderStyleSelected(borderStyle, optionStyle)
            : isPdfTableBorderStyleSelected(borderStyle, optionStyle);
        return MenuItemButton(
          onPressed: onBorderStyleChanged == null
              ? null
              : () => onBorderStyleChanged(optionStyle),
          child: PdfTableBorderStyleMenuRow(
            style: optionStyle,
            label: pdfTableBorderStyleLabel(l10n, optionStyle),
            checked: selected,
          ),
        );
      }),
    );
  }

  if (showWeightMenu) {
    children.add(
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
        child: Text(
          l10n.segmentTableStrokeMenuTitle,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: colors.onSurfaceVariant,
          ),
        ),
      ),
    );
    children.addAll(
      kPdfTableStrokeOptionsPt.map((double optionPt) {
        final bool selected =
            isPdfTableStrokeOptionSelected(strokePt, optionPt);
        final String optionLabel = optionPt <= 0
            ? l10n.segmentTableStrokeNone
            : l10n.segmentTableStrokeLabel(
                formatPdfTableStrokePtLabel(optionPt),
              );
        return MenuItemButton(
          onPressed: () => onStrokePtChanged!(optionPt),
          child: PdfTableStrokeMenuRow(
            strokePt: optionPt,
            label: optionLabel,
            checked: selected,
          ),
        );
      }),
    );
  }

  return children;
}

IconData pdfTableBorderStyleIcon(String style) {
  switch (style) {
    case 'booktabs':
    case 'booktabs_2':
    case 'booktabs_3':
      return Icons.table_rows_outlined;
    case 'horizontal':
      return Icons.horizontal_rule;
    case 'outer':
      return Icons.crop_square_outlined;
    case 'none':
      return Icons.border_clear_outlined;
    case 'grid':
    default:
      return Icons.grid_on_outlined;
  }
}

class PdfTableBorderStyleMenuRow extends StatelessWidget {
  const PdfTableBorderStyleMenuRow({
    super.key,
    required this.style,
    required this.label,
    required this.checked,
  });

  final String style;
  final String label;
  final bool checked;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final Widget styleIcon = style == 'follow_task'
        ? Icon(Icons.assignment_outlined, size: 14, color: colors.onSurface)
        : _TableBorderStylePreviewIcon(
            style: style,
            color: colors.onSurface,
          );
    return Row(
      children: <Widget>[
        SizedBox(
          width: 18,
          child: checked
              ? Icon(Icons.check, size: 14, color: colors.primary)
              : const SizedBox.shrink(),
        ),
        styleIcon,
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 12),
          ),
        ),
      ],
    );
  }
}

class PdfTableStrokeMenuRow extends StatelessWidget {
  const PdfTableStrokeMenuRow({
    super.key,
    required this.strokePt,
    required this.label,
    required this.checked,
  });

  final double strokePt;
  final String label;
  final bool checked;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Row(
      children: <Widget>[
        SizedBox(
          width: 18,
          child: checked
              ? Icon(Icons.check, size: 14, color: colors.primary)
              : const SizedBox.shrink(),
        ),
        _TableGridPreviewIcon(
          strokePt: strokePt,
          color: colors.onSurface,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 12),
          ),
        ),
      ],
    );
  }
}

class _TableBorderStylePreviewIcon extends StatelessWidget {
  const _TableBorderStylePreviewIcon({
    required this.style,
    required this.color,
  });

  final String style;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 22,
      height: 16,
      child: CustomPaint(
        painter: _TableBorderStylePreviewPainter(
          style: style,
          color: color,
        ),
      ),
    );
  }
}

class _TableBorderStylePreviewPainter extends CustomPainter {
  _TableBorderStylePreviewPainter({
    required this.style,
    required this.color,
  });

  final String style;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final Rect bounds = Rect.fromLTWH(1, 1, size.width - 2, size.height - 2);
    final Paint linePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    switch (style) {
      case 'booktabs':
      case 'booktabs_2':
      case 'booktabs_3':
        canvas.drawLine(
          Offset(bounds.left, bounds.top),
          Offset(bounds.right, bounds.top),
          linePaint,
        );
        final int headerRows = style == 'booktabs_3'
            ? 3
            : style == 'booktabs_2'
                ? 2
                : 1;
        final double headerBand = bounds.height * 0.28 / headerRows;
        for (int row = 1; row <= headerRows; row++) {
          final double y = bounds.top + headerBand * row;
          canvas.drawLine(
            Offset(bounds.left, y),
            Offset(bounds.right, y),
            linePaint,
          );
        }
        canvas.drawLine(
          Offset(bounds.left, bounds.bottom),
          Offset(bounds.right, bounds.bottom),
          linePaint,
        );
        break;
      case 'horizontal':
        for (final double y in <double>[0.0, 0.28, 0.56, 0.84, 1.0]) {
          final double py = bounds.top + bounds.height * y;
          canvas.drawLine(
            Offset(bounds.left, py),
            Offset(bounds.right, py),
            linePaint,
          );
        }
        break;
      case 'outer':
        canvas.drawRect(bounds, linePaint);
        break;
      case 'none':
        final Paint dashed = Paint()
          ..color = color.withValues(alpha: 0.35)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1;
        canvas.drawRect(bounds, dashed);
        break;
      case 'grid':
      default:
        canvas.drawRect(bounds, linePaint);
        canvas.drawLine(
          Offset(bounds.left, bounds.center.dy),
          Offset(bounds.right, bounds.center.dy),
          linePaint,
        );
        canvas.drawLine(
          Offset(bounds.center.dx, bounds.top),
          Offset(bounds.center.dx, bounds.bottom),
          linePaint,
        );
    }
  }

  @override
  bool shouldRepaint(covariant _TableBorderStylePreviewPainter oldDelegate) {
    return oldDelegate.style != style || oldDelegate.color != color;
  }
}

class _TableGridPreviewIcon extends StatelessWidget {
  const _TableGridPreviewIcon({
    required this.strokePt,
    required this.color,
  });

  final double strokePt;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 22,
      height: 16,
      child: CustomPaint(
        painter: _TableGridPreviewPainter(
          strokePt: strokePt,
          color: color,
        ),
      ),
    );
  }
}

class _TableGridPreviewPainter extends CustomPainter {
  _TableGridPreviewPainter({
    required this.strokePt,
    required this.color,
  });

  final double strokePt;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final Rect bounds = Rect.fromLTWH(1, 1, size.width - 2, size.height - 2);
    if (strokePt <= 0) {
      final Paint dashed = Paint()
        ..color = color.withValues(alpha: 0.35)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1;
      canvas.drawRect(bounds, dashed);
      return;
    }

    final double previewStroke = switch (strokePt) {
      <= 0.5 => 0.8,
      <= 1.0 => 1.1,
      _ => 1.4,
    };
    final Paint linePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = previewStroke;

    canvas.drawRect(bounds, linePaint);
    canvas.drawLine(
      Offset(bounds.left, bounds.center.dy),
      Offset(bounds.right, bounds.center.dy),
      linePaint,
    );
    canvas.drawLine(
      Offset(bounds.center.dx, bounds.top),
      Offset(bounds.center.dx, bounds.bottom),
      linePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _TableGridPreviewPainter oldDelegate) {
    return oldDelegate.strokePt != strokePt || oldDelegate.color != color;
  }
}
