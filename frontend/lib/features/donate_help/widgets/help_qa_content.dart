// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

/// Help Q&A content: feature intro, edition comparison, quick guide.
/// All text is selectable for copy on desktop and web.
library;

import 'package:flutter/material.dart';

/// Section id for TOC navigation (must match keys in [HelpQaContent]).
/// Edition comparison has been moved to its own top-level tab, so Help
/// TOC now only shows the feature overview section.
const List<String> kHelpQaSectionIds = <String>[
  'section-features',
];

/// Section titles for TOC (same order as [kHelpQaSectionIds]).
const List<String> kHelpQaSectionTitles = <String>[
  'Software feature overview',
];

/// Help Q&A body: sections with selectable text. [sectionKeys] maps section id to GlobalKey for scroll-into-view.
class HelpQaContent extends StatelessWidget {
  const HelpQaContent({
    required this.sectionKeys,
    super.key,
  });

  final Map<String, GlobalKey> sectionKeys;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    return SelectableRegion(
      selectionControls: materialTextSelectionControls,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          _Section(
            key: sectionKeys[kHelpQaSectionIds[0]],
            title: kHelpQaSectionTitles[0],
            titleIcon: Icons.info_outline,
            colorScheme: colorScheme,
            textTheme: textTheme,
            child: const _FeaturesIntro(),
          ),
          const SizedBox(height: 32),
          SelectableText(
            'For getting started, see the Quick Start Guide tab.',
            style: TextStyle(
              fontStyle: FontStyle.italic,
              color: colorScheme.onSurfaceVariant,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.titleIcon,
    required this.colorScheme,
    required this.textTheme,
    required this.child,
    super.key,
  });

  final String title;
  final IconData titleIcon;
  final ColorScheme colorScheme;
  final TextTheme textTheme;
  final Widget child;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(titleIcon, color: colorScheme.primary, size: 24),
              const SizedBox(width: 8),
              Text(
                title,
                style: textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colorScheme.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          child,
        ],
      );
}

class _FeaturesIntro extends StatelessWidget {
  const _FeaturesIntro();

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        SelectableText.rich(
          TextSpan(
            style: textTheme.bodyMedium,
            children: const <InlineSpan>[
              TextSpan(
                text:
                    'Owlangs is a collaborative translation platform designed for teams working on multilingual documents. ',
              ),
              TextSpan(
                text: 'Key features include:\n\n',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              TextSpan(text: '• '),
              TextSpan(
                text: 'Multi-format support: ',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              TextSpan(
                text:
                    'PDF, DOCX, PPTX, XLSX, MD, TXT, HTML, EPUB, MOBI, and more.\n',
              ),
              TextSpan(text: '• '),
              TextSpan(
                text: 'Translation workflow: ',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              TextSpan(
                text:
                    'Extract glossary, translate segments, review, and export.\n',
              ),
              TextSpan(text: '• '),
              TextSpan(
                text: 'Quick error checking and revision: ',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              TextSpan(
                text:
                    'Edit translations in-context, fix errors per segment, and re-export with revisions applied.\n',
              ),
              TextSpan(text: '• '),
              TextSpan(
                text: 'Segment-type filtering: ',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              TextSpan(
                text:
                    'Quickly exclude segments that need no translation by type, reducing token usage.\n',
              ),
              TextSpan(text: '• '),
              TextSpan(
                text: 'Auto language and fonts: ',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              TextSpan(
                text:
                    'Automatic language detection and font selection matched to the target language.\n',
              ),
              TextSpan(text: '• '),
              TextSpan(
                text: 'High-fidelity layout: ',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              TextSpan(
                text:
                    'Preserve original document format and structure in the translated output.\n',
              ),
              TextSpan(text: '• '),
              TextSpan(
                text: 'Collaboration: ',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              TextSpan(
                text:
                    'Team edition supports shared projects and user management.\n',
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        const _ExportFormatTable(),
      ],
    );
  }
}

class _ExportFormatRow {
  const _ExportFormatRow({
    required this.source,
    required this.workflow,
    required this.outputs,
  });

  final String source;
  final String workflow;
  final String outputs;
}

class _ExportFormatTable extends StatelessWidget {
  const _ExportFormatTable();

  static const List<_ExportFormatRow> _rows = <_ExportFormatRow>[
    _ExportFormatRow(
      source: 'PDF / layout-based PDF',
      workflow: 'markdown_based',
      outputs: 'DOCX, HTML, MD, PDF',
    ),
    _ExportFormatRow(
      source: 'DOCX',
      workflow: 'docx',
      outputs: 'DOCX, HTML, MD',
    ),
    _ExportFormatRow(
      source: 'TXT, MD, HTML',
      workflow: 'txt / md / html',
      outputs: 'DOCX, HTML, MD',
    ),
    _ExportFormatRow(
      source: 'SRT (subtitles)',
      workflow: 'srt',
      outputs: 'SRT',
    ),
    _ExportFormatRow(
      source: 'PPTX',
      workflow: 'pptx',
      outputs: 'PPTX',
    ),
    _ExportFormatRow(
      source: 'XLSX / CSV',
      workflow: 'xlsx',
      outputs: 'XLSX, CSV',
    ),
    _ExportFormatRow(
      source: 'EPUB',
      workflow: 'epub',
      outputs: 'EPUB, MOBI, DOCX, HTML, MD',
    ),
    _ExportFormatRow(
      source: 'MOBI',
      workflow: 'mobi',
      outputs: 'MOBI, DOCX, HTML, MD',
    ),
    _ExportFormatRow(
      source: 'JSON / ARB',
      workflow: 'json',
      outputs: 'JSON, ARB',
    ),
    _ExportFormatRow(
      source: 'TS (Qt)',
      workflow: 'qt_ts',
      outputs: 'TS',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final style = Theme.of(context).textTheme.bodyMedium?.copyWith(
              fontSize: 13,
              height: 1.4,
            ) ??
        const TextStyle(fontSize: 13, height: 1.4);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: SelectableText(
            'Export formats by source type (after translation or format conversion):',
            style: style.copyWith(fontWeight: FontWeight.w600),
          ),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: IntrinsicWidth(
            child: Table(
              columnWidths: const <int, TableColumnWidth>{
                0: IntrinsicColumnWidth(),
                1: IntrinsicColumnWidth(),
                2: IntrinsicColumnWidth(),
              },
              defaultVerticalAlignment: TableCellVerticalAlignment.middle,
              border: TableBorder.all(
                color: Theme.of(context).dividerColor,
              ),
              children: <TableRow>[
                TableRow(
                  decoration: BoxDecoration(
                    color: colorScheme.surfaceContainerHighest.withOpacity(0.5),
                  ),
                  children: <Widget>[
                    _exportCell(
                      context,
                      'Source format',
                      style,
                      isHeader: true,
                    ),
                    _exportCell(
                      context,
                      'Workflow type',
                      style,
                      isHeader: true,
                    ),
                    _exportCell(
                      context,
                      'Available exports',
                      style,
                      isHeader: true,
                    ),
                  ],
                ),
                for (final _ExportFormatRow row in _rows)
                  TableRow(
                    children: <Widget>[
                      _exportCell(
                        context,
                        row.source,
                        style,
                        isHeader: false,
                      ),
                      _exportCell(
                        context,
                        row.workflow,
                        style,
                        isHeader: false,
                      ),
                      _exportCell(
                        context,
                        row.outputs,
                        style,
                        isHeader: false,
                      ),
                    ],
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _exportCell(
    BuildContext context,
    String text,
    TextStyle baseStyle, {
    required bool isHeader,
  }) {
    final style =
        isHeader ? baseStyle.copyWith(fontWeight: FontWeight.w600) : baseStyle;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: SelectableText(
        text,
        style: style,
      ),
    );
  }
}

/// Checkmark for "supported" in edition comparison table.
const String _kEditionCheck = '✓';

class _EditionRow {
  const _EditionRow({
    required this.dimension,
    required this.desktop,
    required this.web,
  });
  final String dimension;
  final String desktop;
  final String web;
}

class EditionComparisonTable extends StatelessWidget {
  const EditionComparisonTable({super.key});

  static const List<_EditionRow> _rows = <_EditionRow>[
    _EditionRow(
      dimension: 'Frontend',
      desktop: 'Windows desktop',
      web: 'Web',
    ),
    _EditionRow(
      dimension: 'PDF',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'DOCX',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'PNG / JPG / JPEG',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'TXT',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'MD',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'HTML',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'SRT',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'PPTX',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'XLSX / CSV',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'EPUB',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'MOBI',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'JSON / ARB',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'TS (Qt)',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'PDF workflow: Export DOCX with formulas',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'Translation usage',
      desktop: 'Not limited',
      web: 'Not limited',
    ),
    _EditionRow(
      dimension: 'Local deployment (OpenAI-compatible Local API)',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'Local deployment (Ollama)',
      desktop: _kEditionCheck,
      web: _kEditionCheck,
    ),
    _EditionRow(
      dimension: 'User / login',
      desktop: '',
      web: _kEditionCheck,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final style = TextStyle(
      fontSize: 14,
      height: 1.5,
      color: colorScheme.onSurface,
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: SelectableText(
            'Desktop and Web are available. Differences are summarized below. '
            'Both platforms have no usage caps (e.g. no page or request limits); '
            'technical differences are limited to platform (which frontend is used).',
            style: style,
          ),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: IntrinsicWidth(
            child: Table(
              columnWidths: const <int, TableColumnWidth>{
                0: IntrinsicColumnWidth(),
                1: IntrinsicColumnWidth(),
                2: IntrinsicColumnWidth(),
              },
              defaultVerticalAlignment: TableCellVerticalAlignment.middle,
              border: TableBorder.all(
                color: Theme.of(context).dividerColor,
              ),
              children: <TableRow>[
                TableRow(
                  decoration: BoxDecoration(
                    color: colorScheme.surfaceContainerHighest.withOpacity(0.5),
                  ),
                  children: <Widget>[
                    _tableCell(context, 'Dimension', style, isHeader: true),
                    _tableCell(context, 'Desktop', style,
                        isHeader: true,),
                    _tableCell(
                      context,
                      'Web',
                      style,
                      isHeader: true,
                    ),
                  ],
                ),
                for (final _EditionRow row in _rows)
                  TableRow(
                    children: <Widget>[
                      _tableCell(context, row.dimension, style, isHeader: true),
                      _tableCell(context, row.desktop, style, isHeader: false),
                      _tableCell(context, row.web, style, isHeader: false),
                    ],
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        SelectableText(
          'OpenSource edition provides the same core features on both Desktop and Web. '
          'There is no trial/activation gate for formats or translation workflow in the open-source build.',
          style: style,
        ),
      ],
    );
  }

  Widget _tableCell(
    BuildContext context,
    String text,
    TextStyle style, {
    required bool isHeader,
  }) =>
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: SelectableText(
          text,
          style: isHeader ? style.copyWith(fontWeight: FontWeight.w600) : style,
        ),
      );
}
