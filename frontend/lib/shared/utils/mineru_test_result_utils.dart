import '../../l10n/app_localizations.dart';

/// Whether [platformKey] refers to a MinerU parsing platform.
bool isMinerUPlatform(String platformKey) {
  final String key = platformKey.toLowerCase();
  return key == 'mineru' || key == 'mineru_local';
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
  return l10n.aiPlatformConnectionTestSucceeded;
}
