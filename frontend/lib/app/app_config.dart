import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  // SharedPreferences key for custom server URL
  static const String _kCustomServerUrlKey = 'custom_server_url';
  
  // Internal storage for custom URL
  static String? _customBaseUrl;
  
  /// Initialize AppConfig by loading saved preferences
  static Future<void> initialize() async {
    await _loadCustomServerUrl();
  }
  
  /// Load custom server URL from SharedPreferences
  static Future<void> _loadCustomServerUrl() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _customBaseUrl = prefs.getString(_kCustomServerUrlKey);
    } catch (e) {
      // Ignore errors, use default
      _customBaseUrl = null;
    }
  }
  
  /// Get custom server URL (if set)
  static String? get customServerUrl => _customBaseUrl;
  
  /// Set custom server URL (null to reset to default)
  static Future<bool> setCustomServerUrl(String? url) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _customBaseUrl = url;
      if (url == null || url.isEmpty) {
        return await prefs.remove(_kCustomServerUrlKey);
      } else {
        return await prefs.setString(_kCustomServerUrlKey, url);
      }
    } catch (e) {
      return false;
    }
  }
  
  /// Reset to default server URL
  static Future<bool> resetToDefaultServerUrl() async => setCustomServerUrl(null);
  // App Information
  static const String appName = 'Owlangs';
  static const String appVersion = '1.5.2.0';
  static const String appDescription =
      'Cross-platform document translation application';

  // Feature flags: enable features that are still in development
  /// When true, features under development (e.g. Anonymize) are enabled in the UI.
  /// Set to false for release; set to true for local testing of in-dev features.
  static const bool kEnableFeaturesInDevelopment = false;

  // Donation channel URLs (null = show "Coming soon" in UI)
  /// PayPal donation page URL (disabled for now; keep for future use).
  static const String? kDonatePayPalUrl = null;

  /// Credit card / Stripe donation page URL (disabled for now; keep for future use).
  static const String? kDonateCreditCardUrl = null;

  // Donor activation: whitelist of valid activation codes (fixed for now; confirm after donation)
  static const List<String> kDonorActivationCodeWhitelist = <String>['1037'];

  /// SharedPreferences key for donor activated state
  static const String kDonorActivatedStorageKey = 'donor_activated';

  // API Configuration: 
  // - Desktop: use localhost backend
  // - Web development (flutter run): use localhost:8800 directly to avoid dev server port mismatch
  // - Web production (PyInstaller): use relative path '' for multi-user deployment support
  // - Custom: user can override via settings
  static const String _defaultBaseUrl = 'http://localhost:8800';
  static String get baseUrl {
    // If user has set a custom server URL, use it
    if (_customBaseUrl != null && _customBaseUrl!.isNotEmpty) {
      return _customBaseUrl!;
    }
    
    if (!kIsWeb) {
      // Desktop: always use localhost backend
      return _defaultBaseUrl;
    }
    
    // Web: check if we're in development mode (flutter run)
    // In development, Uri.base will be something like http://localhost:8020
    // In production (PyInstaller), it will be http://localhost:8800 or user's domain
    final int currentPort = Uri.base.port;
    
    // If current port is not 8800, we're likely in dev mode (flutter run)
    // In this case, point directly to the backend
    if (currentPort != 8800) {
      return _defaultBaseUrl;
    }
    
    // Production mode: use relative path for multi-user deployment support
    // This allows reverse proxy configuration and custom domains
    return '';
  }
  
  /// Get the default base URL (for display in settings)
  static String get defaultBaseUrl => _defaultBaseUrl;
  static const String apiVersion = 'v1';
  static const Duration requestTimeout = Duration(
    seconds: 120,
  ); // Default timeout for normal requests (increased from 60s to handle slow backend)
  static const Duration longRequestTimeout = Duration(
    minutes: 30,
  ); // Timeout for long-running operations (file upload, translation, anonymization)

  // UI Configuration
  static const double defaultPadding = 16;
  static const double defaultRadius = 8;
  static const double defaultElevation = 2;

  // Animation Configuration
  static const Duration shortAnimation = Duration(milliseconds: 200);
  static const Duration mediumAnimation = Duration(milliseconds: 300);
  static const Duration longAnimation = Duration(milliseconds: 500);

  // File Upload Configuration
  static const List<String> supportedFileTypes = <String>[
    'pdf',
    'docx',
    'xlsx',
    'csv',
    'xls',
    'json',
    'srt',
    'txt',
    'md',
    'html',
    'epub',
    'mobi',
    'azw',
    'ts',
  ];
  static const int maxFileSize = 50 * 1024 * 1024; // 50MB

  // Desktop Specific Configuration
  static const Size minWindowSize = Size(800, 600);
  static const Size defaultWindowSize = Size(1200, 800);
  static const Size maxWindowSize = Size(1920, 1080);

  /// Launcher exit request URL (Windows desktop only). POST to request backend + Launcher shutdown.
  static const String kLauncherRequestExitUrl =
      'http://127.0.0.1:13131/request_exit';

  // Theme Configuration
  static const Color primaryColor = Color(0xFF1976D2);
  static const Color secondaryColor = Color(0xFF03DAC6);
  static const Color errorColor = Color(0xFFB00020);
  static const Color surfaceColor = Color(0xFFFFFFFF);
  static const Color backgroundColor = Color(0xFFF5F5F5);
}
