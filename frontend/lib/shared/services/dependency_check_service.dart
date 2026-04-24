import 'package:flutter/foundation.dart' show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:dio/dio.dart';
import '../../app/app_config.dart';

/// Model for a single dependency check result
class DependencyItem {
  final String name;
  final String displayName;
  final bool installed;
  final String requiredFor;
  final bool optional;
  final String macosInstall;
  final String linuxInstall;

  DependencyItem({
    required this.name,
    required this.displayName,
    required this.installed,
    required this.requiredFor,
    required this.optional,
    required this.macosInstall,
    required this.linuxInstall,
  });

  factory DependencyItem.fromJson(Map<String, dynamic> json) {
    return DependencyItem(
      name: json['name'] as String,
      displayName: json['display_name'] as String,
      installed: json['installed'] as bool,
      requiredFor: json['required_for'] as String,
      optional: json['optional'] as bool,
      macosInstall: json['macos_install'] as String,
      linuxInstall: json['linux_install'] as String,
    );
  }
}

/// Model for macOS installation guidance
class MacosGuidance {
  final String message;
  final List<String> steps;
  final String? latexNote;

  MacosGuidance({
    required this.message,
    required this.steps,
    this.latexNote,
  });

  factory MacosGuidance.fromJson(Map<String, dynamic> json) {
    return MacosGuidance(
      message: json['message'] as String,
      steps: (json['steps'] as List<dynamic>).cast<String>(),
      latexNote: json['latex_note'] as String?,
    );
  }
}

/// Model for dependency check response
class DependencyCheckResult {
  final String platform;
  final bool isMacos;
  final bool allOk;
  final List<DependencyItem> dependencies;
  final int missingCount;
  final int missingRequiredCount;
  final int missingOptionalCount;
  final MacosGuidance? macosGuidance;

  DependencyCheckResult({
    required this.platform,
    required this.isMacos,
    required this.allOk,
    required this.dependencies,
    required this.missingCount,
    required this.missingRequiredCount,
    required this.missingOptionalCount,
    this.macosGuidance,
  });

  factory DependencyCheckResult.fromJson(Map<String, dynamic> json) {
    return DependencyCheckResult(
      platform: json['platform'] as String,
      isMacos: json['is_macos'] as bool,
      allOk: json['all_ok'] as bool,
      dependencies: (json['dependencies'] as List<dynamic>)
          .map((e) => DependencyItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      missingCount: json['missing_count'] as int,
      missingRequiredCount: json['missing_required_count'] as int,
      missingOptionalCount: json['missing_optional_count'] as int,
      macosGuidance: json['macos_guidance'] != null
          ? MacosGuidance.fromJson(json['macos_guidance'] as Map<String, dynamic>)
          : null,
    );
  }

  /// Get list of missing dependencies
  List<DependencyItem> get missingDependencies =>
      dependencies.where((d) => !d.installed).toList();

  /// Get list of missing required dependencies
  List<DependencyItem> get missingRequiredDependencies =>
      dependencies.where((d) => !d.installed && !d.optional).toList();
}

/// Service for checking system dependencies
class DependencyCheckService {
  static final DependencyCheckService _instance = DependencyCheckService._internal();
  factory DependencyCheckService() => _instance;
  DependencyCheckService._internal();

  DependencyCheckResult? _lastResult;
  DateTime? _lastCheckTime;
  static const Duration _cacheDuration = Duration(minutes: 5);

  /// Check if we should skip dependency check on this platform
  bool get shouldSkipCheck {
    // Skip on web
    if (kIsWeb) return true;
    // Skip on Windows and Linux (only macOS needs this check for now)
    if (defaultTargetPlatform != TargetPlatform.macOS) return true;
    return false;
  }

  /// Check system dependencies (with caching)
  Future<DependencyCheckResult?> checkDependencies({bool force = false}) async {
    if (shouldSkipCheck) return null;

    // Use cached result if available and not forced
    if (!force && _lastResult != null && _lastCheckTime != null) {
      final age = DateTime.now().difference(_lastCheckTime!);
      if (age < _cacheDuration) {
        return _lastResult;
      }
    }

    try {
      final dio = Dio(BaseOptions(
        baseUrl: AppConfig.baseUrl,
        connectTimeout: const Duration(seconds: 5),
        receiveTimeout: const Duration(seconds: 5),
      ));

      final response = await dio.get('/api/system/dependencies');
      final result = DependencyCheckResult.fromJson(response.data as Map<String, dynamic>);

      _lastResult = result;
      _lastCheckTime = DateTime.now();
      return result;
    } catch (e) {
      // If backend is not ready, return null (will retry later)
      return null;
    }
  }

  /// Check if there are missing required dependencies
  Future<bool> hasMissingRequiredDependencies() async {
    final result = await checkDependencies();
    if (result == null) return false;
    return result.missingRequiredCount > 0;
  }

  /// Clear cached result
  void clearCache() {
    _lastResult = null;
    _lastCheckTime = null;
  }
}
