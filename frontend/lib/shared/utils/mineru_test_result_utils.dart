import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';

/// Whether [platformKey] refers to a MinerU parsing platform.
bool isMinerUPlatform(String platformKey) {
  final String key = platformKey.toLowerCase();
  return key == 'mineru' || key == 'mineru_local';
}

/// Whether [platformKey] refers to a PaddleOCR parsing platform.
bool isPaddlePlatform(String platformKey) {
  final String key = platformKey.toLowerCase();
  return key == 'paddle' || key == 'paddle_local';
}

/// True when PaddleOCR is reachable but lacks VL document parsing.
bool paddleTestHasCapabilityWarning(Map<String, dynamic>? result) {
  if (result == null) {
    return false;
  }
  final bool success = result['success'] == true ||
      result['success'] == 'true' ||
      result['success'] == 1;
  if (!success) {
    return false;
  }
  final dynamic capable = result['document_parsing_capable'];
  return capable == false || capable == 'false' || capable == 0;
}

/// True when a platform connectivity test satisfies Owlangs requirements.
bool platformTestMeetsRequirements(Map<String, dynamic>? result) {
  if (result == null) {
    return false;
  }
  final bool success = result['success'] == true ||
      result['success'] == 'true' ||
      result['success'] == 1;
  if (!success) {
    return false;
  }
  if (result.containsKey('document_parsing_capable')) {
    final dynamic capable = result['document_parsing_capable'];
    return capable != false && capable != 'false' && capable != 0;
  }
  if (result.containsKey('meets_requirements')) {
    final dynamic meets = result['meets_requirements'];
    return meets != false && meets != 'false' && meets != 0;
  }
  return true;
}

/// SnackBar background for platform test results (green / orange / red).
Color platformTestSnackBarColor(Map<String, dynamic>? result) {
  if (result == null || !platformTestMeetsRequirements(result)) {
    final bool reachable = result?['success'] == true ||
        result?['success'] == 'true' ||
        result?['success'] == 1;
    if (reachable && paddleTestHasCapabilityWarning(result)) {
      return Colors.orange.shade700;
    }
    return Colors.red.shade700;
  }
  return Colors.green.shade700;
}

/// Localized detail message for platform test snackbars / banners.
String platformTestDetailMessage(
  AppLocalizations l10n,
  String platformKey,
  Map<String, dynamic>? result,
) {
  if (result == null) {
    return l10n.quickSettingsTestFailed;
  }
  if (platformTestMeetsRequirements(result)) {
    return buildPlatformTestSuccessMessage(l10n, platformKey, result);
  }
  final bool reachable = result['success'] == true ||
      result['success'] == 'true' ||
      result['success'] == 1;
  if (reachable && isPaddlePlatform(platformKey)) {
    return buildPaddleTestSuccessMessage(l10n, result);
  }
  return buildPlatformTestFailureMessage(l10n, platformKey, result);
}

/// Inline banner for platform connectivity test feedback.
Widget buildPlatformTestResultBanner({
  required String message,
  required bool? lastTestSuccess,
  required Map<String, dynamic>? rawResult,
}) {
  final PlatformTestVisualState visualState = resolvePlatformTestVisualState(
    lastTestSuccess: lastTestSuccess,
    rawResult: rawResult,
  );
  final style = platformTestResultStyle(visualState);
  return Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
    decoration: BoxDecoration(
      color: style.backgroundColor,
      borderRadius: BorderRadius.circular(4),
      border: Border.all(color: style.borderColor),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Icon(style.icon, color: style.contentColor, size: 18),
        const SizedBox(width: 8),
        Expanded(
          child: SelectableText(
            message,
            style: TextStyle(color: style.contentColor, fontSize: 12),
          ),
        ),
      ],
    ),
  );
}

/// Build localized success message for PaddleOCR connectivity tests.
String buildPaddleTestSuccessMessage(
  AppLocalizations l10n,
  Map<String, dynamic>? result,
) {
  final String? warningCode = result?['warning_code']?.toString();
  if (warningCode == 'paddle_text_ocr_only') {
    return l10n.paddleOcrTestWarningTextOnly;
  }
  if (warningCode == 'paddle_capability_unknown') {
    return l10n.paddleOcrTestWarningUnverified;
  }

  final String? backendMessage = result?['message']?.toString();
  if (backendMessage != null && backendMessage.isNotEmpty) {
    return backendMessage;
  }

  return l10n.aiPlatformConnectionTestSucceeded;
}

/// Localized failure message for PaddleOCR connectivity tests.
String buildPaddleTestFailureMessage(
  AppLocalizations l10n,
  Map<String, dynamic>? result,
) {
  final String? warningCode = result?['warning_code']?.toString();
  if (warningCode == 'paddle_unreachable') {
    return l10n.paddleOcrTestUnreachable;
  }
  final String? backendMessage =
      result?['message']?.toString() ?? result?['error']?.toString();
  if (backendMessage != null && backendMessage.isNotEmpty) {
    return l10n.aiPlatformConnectionTestFailed(backendMessage);
  }
  return l10n.aiPlatformConnectionTestFailed(l10n.quickSettingsTestFailed);
}

/// Resolve platform test failure message.
String buildPlatformTestFailureMessage(
  AppLocalizations l10n,
  String platformKey,
  Map<String, dynamic>? result,
) {
  if (isPaddlePlatform(platformKey)) {
    return buildPaddleTestFailureMessage(l10n, result);
  }
  final String? backendMessage =
      result?['message']?.toString() ?? result?['error']?.toString();
  if (backendMessage != null && backendMessage.isNotEmpty) {
    return l10n.aiPlatformConnectionTestFailed(backendMessage);
  }
  return l10n.aiPlatformConnectionTestFailed(l10n.quickSettingsTestFailed);
}

/// Build localized success message for MinerU connectivity tests, including version when available.
String buildMinerUTestSuccessMessage(
  AppLocalizations l10n,
  Map<String, dynamic>? result,
) {
  final String? mineruVersion = result?['mineru_version']?.toString();
  if (mineruVersion != null && mineruVersion.isNotEmpty) {
    return l10n.mineruConnectionSuccessWithVersion(mineruVersion);
  }

  final String? modelVersion = result?['model_version']?.toString();
  if (modelVersion != null && modelVersion.isNotEmpty) {
    return l10n.mineruConnectionSuccessWithModelVersion(modelVersion);
  }

  final String? backendMessage = result?['message']?.toString();
  if (backendMessage != null &&
      backendMessage.isNotEmpty &&
      _messageLikelyContainsVersion(backendMessage)) {
    return backendMessage;
  }

  final String? apiVersion = result?['api_version']?.toString();
  if (apiVersion != null && apiVersion.isNotEmpty) {
    return l10n.mineruConnectionSuccessCloudWithApi(apiVersion);
  }

  if (backendMessage != null && backendMessage.isNotEmpty) {
    return backendMessage;
  }

  return l10n.aiPlatformConnectionTestSucceeded;
}

bool _messageLikelyContainsVersion(String message) {
  final lower = message.toLowerCase();
  return lower.contains('version:') || lower.contains('version ');
}

/// Resolve platform test success message; MinerU platforms include version info.
String buildPlatformTestSuccessMessage(
  AppLocalizations l10n,
  String platformKey,
  Map<String, dynamic>? result,
) {
  if (isMinerUPlatform(platformKey)) {
    return buildMinerUTestSuccessMessage(l10n, result);
  }
  if (isPaddlePlatform(platformKey)) {
    return buildPaddleTestSuccessMessage(l10n, result);
  }
  return l10n.aiPlatformConnectionTestSucceeded;
}

enum PlatformTestVisualState { failure, success, warning }

/// Resolve how to render a platform connectivity test banner.
PlatformTestVisualState resolvePlatformTestVisualState({
  required bool? lastTestSuccess,
  required Map<String, dynamic>? rawResult,
}) {
  final bool reachable = lastTestSuccess == true ||
      rawResult?['success'] == true ||
      rawResult?['success'] == 'true' ||
      rawResult?['success'] == 1;
  if (!reachable) {
    return PlatformTestVisualState.failure;
  }
  if (paddleTestHasCapabilityWarning(rawResult)) {
    return PlatformTestVisualState.warning;
  }
  return PlatformTestVisualState.success;
}

/// Colors and icon for platform test result banners.
({
  Color backgroundColor,
  Color borderColor,
  Color contentColor,
  IconData icon,
}) platformTestResultStyle(PlatformTestVisualState state) {
  switch (state) {
    case PlatformTestVisualState.warning:
      return (
        backgroundColor: Colors.orange.shade50,
        borderColor: Colors.orange.shade300,
        contentColor: Colors.orange.shade800,
        icon: Icons.warning_amber_rounded,
      );
    case PlatformTestVisualState.success:
      return (
        backgroundColor: Colors.green.shade50,
        borderColor: Colors.green.shade300,
        contentColor: Colors.green.shade700,
        icon: Icons.check_circle,
      );
    case PlatformTestVisualState.failure:
      return (
        backgroundColor: Colors.red.shade50,
        borderColor: Colors.red.shade300,
        contentColor: Colors.red.shade700,
        icon: Icons.error,
      );
  }
}
