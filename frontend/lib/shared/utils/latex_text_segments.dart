// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

/// Split plain text and LaTeX math delimiters for segment preview rendering.

enum LatexSegmentKind { plain, inline, display }

class LatexTextSegment {
  const LatexTextSegment(this.kind, this.text);
  final LatexSegmentKind kind;
  final String text;
}

final RegExp _latexDisplayBlockPattern =
    RegExp(r'\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]');
final RegExp _latexInlinePattern =
    RegExp(r'(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)|\\\(([^\\]*?)\\\)');

bool textContainsLatexMath(String text) {
  if (text.isEmpty) {
    return false;
  }
  return _latexDisplayBlockPattern.hasMatch(text) ||
      _latexInlinePattern.hasMatch(text);
}

class _LatexMatch {
  const _LatexMatch({
    required this.start,
    required this.end,
    required this.kind,
    required this.content,
  });

  final int start;
  final int end;
  final LatexSegmentKind kind;
  final String content;
}

List<LatexTextSegment> splitLatexTextSegments(String text) {
  if (text.isEmpty) {
    return const <LatexTextSegment>[];
  }

  final List<_LatexMatch> matches = <_LatexMatch>[];

  for (final RegExpMatch match in _latexDisplayBlockPattern.allMatches(text)) {
    final String? content = match.group(1) ?? match.group(2);
    if (content == null) {
      continue;
    }
    matches.add(
      _LatexMatch(
        start: match.start,
        end: match.end,
        kind: LatexSegmentKind.display,
        content: content.trim(),
      ),
    );
  }

  for (final RegExpMatch match in _latexInlinePattern.allMatches(text)) {
    final String? content = match.group(1) ?? match.group(2);
    if (content == null) {
      continue;
    }
    matches.add(
      _LatexMatch(
        start: match.start,
        end: match.end,
        kind: LatexSegmentKind.inline,
        content: content.trim(),
      ),
    );
  }

  if (matches.isEmpty) {
    return <LatexTextSegment>[LatexTextSegment(LatexSegmentKind.plain, text)];
  }

  matches.sort((a, b) => a.start.compareTo(b.start));

  final List<_LatexMatch> nonOverlapping = <_LatexMatch>[];
  for (final _LatexMatch match in matches) {
    if (nonOverlapping.isEmpty || match.start >= nonOverlapping.last.end) {
      nonOverlapping.add(match);
    }
  }

  final List<LatexTextSegment> segments = <LatexTextSegment>[];
  int pos = 0;
  for (final _LatexMatch match in nonOverlapping) {
    if (match.start > pos) {
      segments.add(
        LatexTextSegment(
          LatexSegmentKind.plain,
          text.substring(pos, match.start),
        ),
      );
    }
    if (match.content.isNotEmpty) {
      segments.add(LatexTextSegment(match.kind, match.content));
    }
    pos = match.end;
  }
  if (pos < text.length) {
    segments.add(
      LatexTextSegment(LatexSegmentKind.plain, text.substring(pos)),
    );
  }
  return segments;
}
