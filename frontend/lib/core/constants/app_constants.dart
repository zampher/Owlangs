import '../../app/app_config.dart';

class AppConstants {
  // App Info
  static const String appName = 'Owlangs';
  static const String appVersion = '1.5.4.0';

  // Planned version for feature messages (e.g. "Will be available in vX.X.X.X")
  static const String plannedVersionAnonymize = '2.0.0.0';
  static const String plannedVersionLayoutFeature = '1.1.0.0';

  // API Configuration: use AppConfig.baseUrl for consistency
  static String get baseUrl => AppConfig.baseUrl;
  static const String apiVersion = 'v1';

  // API Endpoints
  static const String loginEndpoint = '/api/v1/auth/login';
  static const String logoutEndpoint = '/api/v1/auth/logout';
  static const String userEndpoint = '/api/v1/auth/user';
  static const String permissionsEndpoint = '/api/v1/auth/user/permissions';
  static const String configEndpoint = '/api/v1/config/app';
  static const String translationEndpoint = '/api/v1/service/translate';
  static const String statusEndpoint = '/api/v1/service/status';
  static const String downloadEndpoint = '/api/v1/service/download';

  // Storage Keys
  static const String userTokenKey = 'user_token';
  static const String userInfoKey = 'user_info';
  static const String settingsKey = 'app_settings';
  static const String themeKey = 'theme_mode';

  // UI Constants
  static const double defaultPadding = 16;
  static const double defaultRadius = 8;
  static const double defaultElevation = 2;

  // Animation Durations
  static const Duration shortAnimation = Duration(milliseconds: 200);
  static const Duration mediumAnimation = Duration(milliseconds: 300);
  static const Duration longAnimation = Duration(milliseconds: 500);

  // File Upload
  static const List<String> supportedFileTypes = <String>[
    'pdf',
    'docx',
    'doc',
    'txt',
    'md',
    'html',
    'epub',
    'mobi',
    'azw',
    'ts',
  ];
  static const int maxFileSize = 50 * 1024 * 1024; // 50MB

  // Translation Settings
  static const List<String> supportedLanguages = <String>[
    'en',
    'zh',
    'ja',
    'ko',
    'fr',
    'de',
    'es',
    'it',
    'pt',
    'ru',
  ];

  static const Map<String, String> languageNames = <String, String>{
    'en': 'English',
    'zh': '中文',
    'ja': '日本語',
    'ko': '한국어',
    'fr': 'Français',
    'de': 'Deutsch',
    'es': 'Español',
    'it': 'Italiano',
    'pt': 'Português',
    'ru': 'Русский',
  };
}
