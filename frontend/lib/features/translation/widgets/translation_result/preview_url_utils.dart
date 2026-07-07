// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

import '../../providers/format_settings_provider.dart';
import '../../utils/segment_type_utils.dart';

/// Build export query parameters for preview download URLs.
Map<String, String> buildPreviewExportQueryParams(
  FormatSettings formatSettings, {
  required bool isPdfWorkflow,
  bool isImageWorkflow = false,
  String? rendererType,
}) {
  final Map<String, String> params = <String, String>{
    'table_body_format':
        formatSettings.getTableFormat(isPdfWorkflow: isPdfWorkflow),
    'equation_format':
        formatSettings.getEquationFormat(isPdfWorkflow: isPdfWorkflow),
    'chart_body_format':
        formatSettings.getChartFormat(isPdfWorkflow: isPdfWorkflow),
  };
  if (isImageWorkflow) {
    params['cover_color_mode'] = formatSettings.getCoverColorMode();
  }
  if (rendererType != null && rendererType.isNotEmpty) {
    params['renderer_type'] = rendererType;
  }
  final bool allowBilingual = rendererType != 'typst_overlay';
  if (allowBilingual && formatSettings.bilingualExport == true) {
    params['bilingual_export'] = 'true';
    params['bilingual_order'] =
        formatSettings.bilingualOrder ?? 'target_after_source';
    if (formatSettings.sourceTextItalic != null) {
      params['source_text_italic'] =
          formatSettings.sourceTextItalic.toString();
    }
    if (formatSettings.sourceTextColor != null &&
        formatSettings.sourceTextColor!.isNotEmpty) {
      params['source_text_color'] = formatSettings.sourceTextColor!;
    }
    if (formatSettings.targetTextItalic != null) {
      params['target_text_italic'] =
          formatSettings.targetTextItalic.toString();
    }
    if (formatSettings.targetTextColor != null &&
        formatSettings.targetTextColor!.isNotEmpty) {
      params['target_text_color'] = formatSettings.targetTextColor!;
    }
    if (formatSettings.sourceTextFontSizeDelta != null &&
        formatSettings.sourceTextFontSizeDelta != 0.0) {
      params['source_text_font_size_delta'] =
          formatSettings.sourceTextFontSizeDelta.toString();
    }
    if (formatSettings.targetTextFontSizeDelta != null &&
        formatSettings.targetTextFontSizeDelta != 0.0) {
      params['target_text_font_size_delta'] =
          formatSettings.targetTextFontSizeDelta.toString();
    }
  }
  return params;
}

/// Append a revision token so PDF preview re-fetches after segment edits.
Map<String, String> previewCacheBustParams(int revision, {int manualNonce = 0}) {
  final Map<String, String> params = <String, String>{};
  if (revision > 0) {
    params['_rev'] = revision.toString();
  }
  if (manualNonce > 0) {
    params['_pdf_refresh'] = manualNonce.toString();
  }
  return params;
}

/// Pass dirty segment indices for incremental PDF preview refresh.
Map<String, String> pdfPreviewDirtySegmentParams(Set<int> segmentIndices) {
  if (segmentIndices.isEmpty) {
    return const <String, String>{};
  }
  final List<int> sorted = segmentIndices.toList()..sort();
  return <String, String>{'dirty_segments': sorted.join(',')};
}

/// Optional auto-rotation query params for PDF typst_overlay preview/export.
Map<String, String> autoRotationPreviewParams({
  required bool enabled,
  double aspectRatio = kDefaultAutoRotationAspectRatio,
  int degrees = kDefaultAutoRotationDegrees,
}) {
  if (!enabled) {
    return const <String, String>{};
  }
  final double ratio = aspectRatio > 0
      ? aspectRatio
      : kDefaultAutoRotationAspectRatio;
  final int rotationDegrees = kPdfRotationOptionsDegrees.contains(degrees) &&
          degrees != 0
      ? degrees
      : kDefaultAutoRotationDegrees;
  return <String, String>{
    'auto_rotation_enabled': 'true',
    'auto_rotation_aspect_ratio': ratio.toString(),
    'auto_rotation_degrees': rotationDegrees.toString(),
  };
}

String mergePreviewUrl(String baseUrl, Map<String, String> params) {
  final Uri uri = Uri.parse(baseUrl);
  return uri
      .replace(
        queryParameters: <String, String>{
          ...uri.queryParameters,
          ...params,
        },
      )
      .toString();
}

/// Compare preview/download URLs ignoring parameter order.
bool previewUrlsEquivalent(String a, String b) {
  if (a == b) {
    return true;
  }
  try {
    final Uri uriA = Uri.parse(a);
    final Uri uriB = Uri.parse(b);
    if (uriA.scheme != uriB.scheme ||
        uriA.host != uriB.host ||
        uriA.path != uriB.path) {
      return false;
    }
    final Map<String, String> paramsA = uriA.queryParameters;
    final Map<String, String> paramsB = uriB.queryParameters;
    if (paramsA.length != paramsB.length) {
      return false;
    }
    for (final MapEntry<String, String> entry in paramsA.entries) {
      if (paramsB[entry.key] != entry.value) {
        return false;
      }
    }
    return true;
  } on FormatException {
    return false;
  }
}

/// Append preview=1 so backend serves HTML inline (not attachment download).
String appendPreviewInlineParam(String url) {
  final Uri uri = Uri.parse(url);
  return uri
      .replace(
        queryParameters: <String, String>{
          ...uri.queryParameters,
          'preview': '1',
        },
      )
      .toString();
}

/// Absolute URL for preview/download endpoints.
String toAbsolutePreviewUrl(String baseUrl, String relativeOrAbsolute) {
  if (relativeOrAbsolute.startsWith('http')) {
    return relativeOrAbsolute;
  }
  final String normalizedBase =
      baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
  if (relativeOrAbsolute.startsWith('/')) {
    return '$normalizedBase$relativeOrAbsolute';
  }
  return '$normalizedBase/$relativeOrAbsolute';
}

/// Backend compare reader shell URL (single linked scroll container).
String buildHtmlCompareReaderUrl({
  required String apiBaseUrl,
  required String sourceHtmlUrl,
  required String targetHtmlUrl,
  String sourceLabel = 'Source',
  String targetLabel = 'Target',
  bool linkedScroll = false,
}) {
  final String normalizedBase =
      apiBaseUrl.endsWith('/') ? apiBaseUrl.substring(0, apiBaseUrl.length - 1) : apiBaseUrl;
  final Uri readerUri = Uri.parse('$normalizedBase/static/compare_reader.html');
  final String absoluteSource = appendPreviewInlineParam(
    toAbsolutePreviewUrl(normalizedBase, sourceHtmlUrl),
  );
  final String absoluteTarget = appendPreviewInlineParam(
    toAbsolutePreviewUrl(normalizedBase, targetHtmlUrl),
  );
  return readerUri
      .replace(
        queryParameters: <String, String>{
          'source': absoluteSource,
          'target': absoluteTarget,
          'sourceLabel': sourceLabel,
          'targetLabel': targetLabel,
          'linkedScroll': linkedScroll ? '1' : '0',
        },
      )
      .toString();
}
