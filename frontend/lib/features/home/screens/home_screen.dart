import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../app/app_router.dart';
import 'package:dio/dio.dart';
import '../../../l10n/app_localizations.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../app/app_config.dart';
import '../../../shared/models/user_model.dart';
import '../../../shared/providers/auth_provider.dart';
import '../../../shared/providers/admin_permissions_provider.dart';
import '../../../shared/providers/backend_status_provider.dart';
import '../../../shared/services/config_service.dart';
import '../../../shared/services/settings_service.dart';
import '../../settings/screens/ai_platform_settings.dart';
import '../widgets/release_notes_widget.dart';
import '../widgets/translation_stats_widget.dart';
import '../../../shared/services/donor_activation_service.dart';
import '../../../shared/services/dependency_check_service.dart';
import 'package:flutter/foundation.dart'
    show kIsWeb, kDebugMode, defaultTargetPlatform;
import 'package:flutter/foundation.dart' show TargetPlatform;

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  String? _appVersion; // Cached app version from backend
  String? _appVersionType; // Version type from backend, e.g. Alpha/Beta
  String? _latestVersion; // Latest version from update-check API
  bool? _updateAvailable; // Whether a newer version is available
  String? _releaseUrl; // URL to latest release on GitHub
  String? _releaseNotesZh; // Release notes in Chinese (when update available)
  String? _releaseNotesEn; // Release notes in English (when update available)

  // Cache to prevent repeated version checks (once per day)
  static DateTime? _lastVersionCheck;
  static const Duration _versionCheckInterval = Duration(days: 1);
  static Map<String, dynamic>? _cachedVersionData;
  bool?
      _isDonor; // User type: true for Pro, false for Basic, null for unknown/loading
  int? _trialDaysRemaining; // Remaining trial days (null if not in trial)
  DonorStatus? _donorStatus; // Full donor/license status cache

  // GlobalKey for home screen Scaffold to get its size
  final GlobalKey _homeScaffoldKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    // Load app version from backend
    _loadAppVersion();
    // Load user type for desktop users
    _loadUserType();
    // Check system dependencies on macOS
    _checkDependencies();
    // Initialize notification listener after first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        final settingsService = SettingsService();
        settingsService.initNotificationListener(context);
      }
    });
  }

  /// Check system dependencies and show warning dialog if any are missing
  Future<void> _checkDependencies() async {
    // Only run on macOS desktop
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.macOS) return;

    final service = DependencyCheckService();
    final result = await service.checkDependencies();
    if (result == null || result.allOk || !mounted) return;

    // Delay slightly to let the UI settle
    await Future.delayed(const Duration(seconds: 2));
    if (!mounted) return;

    _showDependencyDialog(result);
  }

  /// Show dependency warning dialog
  void _showDependencyDialog(DependencyCheckResult result) {
    final missing = result.missingDependencies;
    final missingRequired = result.missingRequiredDependencies;
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    showDialog(
      context: context,
      barrierDismissible: missingRequired.isEmpty, // Require action if required deps missing
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: Row(
            children: <Widget>[
              Icon(
                Icons.warning_amber_rounded,
                color: missingRequired.isNotEmpty ? Colors.orange : Colors.blue,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  missingRequired.isNotEmpty
                      ? 'Dependencies Missing'
                      : 'Optional Dependencies',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                if (missingRequired.isNotEmpty) ...<Widget>[
                  Text(
                    'The following required dependencies are missing:',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                ...missing.map((dep) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isDark
                            ? Colors.orange.withOpacity(0.1)
                            : Colors.orange.withOpacity(0.05),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: Colors.orange.withOpacity(0.3),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Row(
                            children: <Widget>[
                              Icon(
                                dep.installed ? Icons.check_circle : Icons.cancel,
                                color: dep.installed ? Colors.green : Colors.red,
                                size: 18,
                              ),
                              const SizedBox(width: 8),
                              Text(
                                dep.displayName,
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              if (dep.optional) ...<Widget>[
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 6,
                                    vertical: 2,
                                  ),
                                  decoration: BoxDecoration(
                                    color: isDark
                                        ? Colors.blue.withOpacity(0.2)
                                        : Colors.blue.withOpacity(0.1),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    'Optional',
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: Colors.blue,
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Required for: ${dep.requiredFor}',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.textTheme.bodySmall?.color?.withOpacity(0.8),
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Install: ${dep.macosInstall}',
                            style: theme.textTheme.bodySmall?.copyWith(
                              fontFamily: 'monospace',
                              color: theme.colorScheme.primary,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
                if (result.macosGuidance != null) ...<Widget>[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: isDark
                          ? Colors.blue.withOpacity(0.1)
                          : Colors.blue.withOpacity(0.05),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: Colors.blue.withOpacity(0.3),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          'Quick Install (Recommended)',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: Colors.blue,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          result.macosGuidance!.message,
                          style: theme.textTheme.bodySmall,
                        ),
                        const SizedBox(height: 8),
                        ...result.macosGuidance!.steps.map((step) {
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 4),
                            child: Text(
                              step,
                              style: theme.textTheme.bodySmall?.copyWith(
                                fontFamily: step.startsWith('   ') ? 'monospace' : null,
                                color: step.startsWith('   ')
                                    ? theme.colorScheme.primary
                                    : null,
                              ),
                            ),
                          );
                        }).toList(),
                        if (result.macosGuidance!.latexNote != null) ...<Widget>[
                          const SizedBox(height: 8),
                          Text(
                            result.macosGuidance!.latexNote!,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: Colors.orange,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
          actions: <Widget>[
            if (missingRequired.isEmpty)
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(),
                child: const Text('Dismiss'),
              ),
            if (result.macosGuidance != null)
              ElevatedButton(
                onPressed: () => Navigator.of(dialogContext).pop(),
                child: const Text('Got it'),
              ),
          ],
        );
      },
    );
  }

  /// Load license / trial status. If license expired, show prompt once on desktop.
  Future<void> _loadUserType() async {
    // OpenSource edition: no donor/pro/enterprise distinction and no trial control.
    if (!mounted) return;
    setState(() {
      _donorStatus = null;
      _isDonor = null;
      _trialDaysRemaining = null;
    });
  }

  /// Load app version from backend API (with cache)
  Future<void> _loadAppVersion() async {
    // Check cache first
    if (_cachedVersionData != null && _lastVersionCheck != null) {
      final timeSinceLastCheck = DateTime.now().difference(_lastVersionCheck!);
      if (timeSinceLastCheck < _versionCheckInterval) {
        if (kDebugMode) {
          print(
              '[HomeScreen] Using cached version data (${timeSinceLastCheck.inMinutes}m ago)');
        }
        _applyVersionData(_cachedVersionData!);
        return;
      }
    }

    // Load from backend asynchronously (don't block UI)
    _loadVersionFromBackend();
  }

  /// Apply version data to state
  void _applyVersionData(Map<String, dynamic> data) {
    // New API shape: { ok, current_version, current_version_type?, latest_version, update_available, release_url, release_notes_zh?, release_notes_en? }
    if (data['ok'] == true && data['current_version'] != null) {
      final String current = data['current_version'] as String;
      final String? currentType = data['current_version_type'] is String &&
              (data['current_version_type'] as String).isNotEmpty
          ? data['current_version_type'] as String
          : null;
      final String? latest = data['latest_version'] as String?;
      final bool? updateAvailable = data['update_available'] as bool?;
      final String? releaseUrl = data['release_url'] as String?;
      final String? notesZh = data['release_notes_zh'] as String?;
      final String? notesEn = data['release_notes_en'] as String?;

      if (mounted) {
        setState(() {
          _appVersion = current;
          _appVersionType = currentType;
          _latestVersion = latest;
          _updateAvailable = updateAvailable;
          _releaseUrl = releaseUrl;
          _releaseNotesZh = notesZh;
          _releaseNotesEn = notesEn;
        });
      }
    }
    // Legacy API shape: { ok, version, version_type? }
    else if (data['ok'] == true && data['version'] != null) {
      final String version = data['version'] as String;
      final String? versionType = data['version_type'] is String &&
              (data['version_type'] as String).isNotEmpty
          ? data['version_type'] as String
          : null;

      if (mounted) {
        setState(() {
          _appVersion = version;
          _appVersionType = versionType;
          _latestVersion = null;
          _updateAvailable = null;
          _releaseUrl = null;
          _releaseNotesZh = null;
          _releaseNotesEn = null;
        });
      }
    }
  }

  /// Load version from backend in background
  Future<void> _loadVersionFromBackend() async {
    try {
      if (kDebugMode) {
        print('[HomeScreen] Fetching version from backend...');
      }

      // Use shorter timeouts - don't wait too long for GitHub check
      final dio = Dio(
        BaseOptions(
          baseUrl: AppConfig.baseUrl,
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 10),
          headers: <String, dynamic>{
            'Content-Type': 'application/json',
          },
        ),
      );

      // Add auth header if available
      final configService = ConfigService();
      final authHeader = configService.authorizationHeader;
      if (authHeader != null) {
        dio.options.headers['Authorization'] = authHeader;
      }

      // Prefer /api/settings/update-check for version + update info.
      Response<dynamic> response;
      try {
        response = await dio.get('/api/settings/update-check');
      } on DioException catch (e) {
        // Fallback for older backends without update-check endpoint
        if (e.response?.statusCode == 404) {
          response = await dio.get('/api/settings/version');
        } else {
          rethrow;
        }
      }

      if (response.statusCode == 200 && response.data is Map<String, dynamic>) {
        final data = response.data as Map<String, dynamic>;

        // Cache the data
        _cachedVersionData = data;
        _lastVersionCheck = DateTime.now();

        _applyVersionData(data);

        if (kDebugMode) {
          print('[HomeScreen] Version data cached at $_lastVersionCheck');
        }
      }
    } catch (e) {
      // Silently fail - version is optional, don't show error to user
      if (kDebugMode) {
        debugPrint('[HomeScreen] Failed to load app version: $e');
      }
    }
  }

  @override
  void dispose() {
    // Clear notification context when widget is disposed
    SettingsService().clearNotificationContext();
    super.dispose();
  }

  // Static to persist across widget rebuilds when navigating back from Settings
  static bool _hasInitializedTests = false;

  @override
  Widget build(BuildContext context) {
    final AuthState authState = ref.watch(authProvider);
    final cfg = ConfigService();
    final authRequired = cfg.authRequired;

    // Initialize platform status on first build (read from backend cache, no connection test)
    if (!_hasInitializedTests) {
      _hasInitializedTests = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final aiPlatformNotifier =
            ref.read(aiPlatformSettingsProvider.notifier);
        aiPlatformNotifier.initializePlatformTests();
        _logHomeScreenSize();
      });
    }

    // If auth is disabled or not configured (null), show content directly
    // This allows the app to work even if auth config is not loaded yet
    if (authRequired == false || authRequired == null) {
      return Scaffold(
        key: _homeScaffoldKey,
        body: _buildHomeContent(authState),
      );
    }

    // Auth is required, check auth state
    return authState.when(
      initial: () =>
          _buildResult(const Center(child: CircularProgressIndicator())),
      loading: () =>
          _buildResult(const Center(child: CircularProgressIndicator())),
      authenticated: (UserModel user) =>
          _buildResult(_buildHomeContent(authState)),
      unauthenticated: () =>
          _buildResult(const Center(child: CircularProgressIndicator())),
      error: (String message) => _buildResult(
        Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              const Icon(Icons.error_outline, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(AppLocalizations.of(context)!.homeAuthErrorTitle,
                  style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8),
              Text(message,
                  style: Theme.of(context).textTheme.bodyMedium,
                  textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  ref.read(authProvider.notifier).clearError();
                  context.go('/login');
                },
                child: Text(AppLocalizations.of(context)!.homeAuthRetryLogin),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Helper to build Scaffold
  Widget _buildResult(Widget body) => Scaffold(
        key: _homeScaffoldKey,
        body: body,
      );

  Widget _buildHomeContent(AuthState authState) {
    final showReleaseNotes = _updateAvailable ?? false;
    final locale = Localizations.localeOf(context);
    final useZh = locale.languageCode == 'zh';
    final releaseNotesText = useZh
        ? (_releaseNotesZh ?? _releaseNotesEn)
        : (_releaseNotesEn ?? _releaseNotesZh);

    // Adaptive height: support scrolling when window height is small
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) =>
          SingleChildScrollView(
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Padding(
                padding: const EdgeInsets.all(24),
                child: _buildWelcomeSection(authState),
              ),
              if (showReleaseNotes) ...<Widget>[
                const SizedBox(height: 24),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: ReleaseNotesWidget(
                    releaseNotes: releaseNotesText,
                    releaseUrl: _releaseUrl,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWelcomeSection(AuthState authState) {
    final l10n = AppLocalizations.of(context)!;
    final aiPlatformSettings = ref.watch(aiPlatformSettingsProvider);

    final availablePlatforms = aiPlatformSettings.platforms.values
        .where((p) => p.isApiAvailable ?? false)
        .map((p) => p.name)
        .toList();

    final result = Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Row(
                        children: <Widget>[
                          Icon(
                            Icons.dashboard,
                            color: Theme.of(context).colorScheme.primary,
                            size: 32,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: <Widget>[
                                Flexible(
                                  child: Text(
                                    'Owlangs Translation\nFile Format Conversion',
                                    style: TextStyle(
                                      fontSize: 24,
                                      fontWeight: FontWeight.bold,
                                      color:
                                          Theme.of(context).colorScheme.primary,
                                    ),
                                    maxLines: 2,
                                    softWrap: true,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                if (_appVersion != null) ...<Widget>[
                                  const SizedBox(width: 8),
                                  Text(
                                    'v$_appVersion',
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.normal,
                                      color: Theme.of(context)
                                          .colorScheme
                                          .onSurfaceVariant,
                                    ),
                                  ),
                                  if (_appVersionType != null &&
                                      _appVersionType!.isNotEmpty) ...<Widget>[
                                    const SizedBox(width: 6),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 6,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: Theme.of(context)
                                            .colorScheme
                                            .secondaryContainer,
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        _appVersionType!,
                                        style: TextStyle(
                                          fontSize: 11,
                                          fontWeight: FontWeight.w600,
                                          color: Theme.of(context)
                                              .colorScheme
                                              .onSecondaryContainer,
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                                const SizedBox(width: 8),
                                Flexible(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: <Widget>[
                                      _buildEditionStatusSection(context),
                                      if (_latestVersion != null &&
                                          _updateAvailable != null)
                                        Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: <Widget>[
                                            if (_updateAvailable ?? false)
                                              GestureDetector(
                                                onTap: () async {
                                                  final uri = Uri.parse(
                                                    'https://www.owlangs.org',
                                                  );
                                                  if (await canLaunchUrl(uri)) {
                                                    await launchUrl(
                                                      uri,
                                                      mode: LaunchMode
                                                          .externalApplication,
                                                    );
                                                  }
                                                },
                                                child: Container(
                                                  padding: const EdgeInsets
                                                      .symmetric(
                                                    horizontal: 8,
                                                    vertical: 2,
                                                  ),
                                                  decoration: BoxDecoration(
                                                    color: Theme.of(context)
                                                        .colorScheme
                                                        .primaryContainer,
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                      6,
                                                    ),
                                                  ),
                                                  child: Text(
                                                    'v$_latestVersion available',
                                                    style: TextStyle(
                                                      fontSize: 11,
                                                      color: Theme.of(context)
                                                          .colorScheme
                                                          .onPrimaryContainer,
                                                    ),
                                                  ),
                                                ),
                                              )
                                            else
                                              Text(
                                                'Latest version',
                                                style: TextStyle(
                                                  fontSize: 11,
                                                  color: Theme.of(context)
                                                      .colorScheme
                                                      .onSurfaceVariant,
                                                ),
                                              ),
                                          ],
                                        ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        l10n.homeTagline,
                        style: TextStyle(
                          fontSize: 14,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _buildWelcomeMessage(),
                        style: TextStyle(
                          fontSize: 16,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        l10n.homeIntro,
                        style: TextStyle(
                          fontSize: 14,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                // Translation and document stats aligned to the right (animation hidden for now)
                const Expanded(
                  child: Align(
                    alignment: Alignment.centerRight,
                    child: SizedBox(
                      width: 280,
                      child: TranslationStatsWidget(),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Workflow explanation
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Theme.of(context).brightness == Brightness.dark
                    ? Colors.blue.shade900.withOpacity(0.2)
                    : Colors.blue.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: Theme.of(context).brightness == Brightness.dark
                      ? Colors.blue.shade700
                      : Colors.blue.shade200,
                ),
              ),
              child: Row(
                children: <Widget>[
                  Icon(
                    Icons.info_outline,
                    color: Theme.of(context).brightness == Brightness.dark
                        ? Colors.blue.shade300
                        : Colors.blue.shade700,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      l10n.homeHowItWorks,
                      style: TextStyle(
                        fontSize: 13,
                        color: Theme.of(context).brightness == Brightness.dark
                            ? Colors.blue.shade300
                            : Colors.blue.shade700,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            if (availablePlatforms.isNotEmpty) ...<Widget>[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Theme.of(context).brightness == Brightness.dark
                      ? Colors.green.shade900.withOpacity(0.3)
                      : Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: Theme.of(context).brightness == Brightness.dark
                        ? Colors.green.shade700
                        : Colors.green.shade200,
                  ),
                ),
                child: Row(
                  children: <Widget>[
                    Icon(
                      Icons.check_circle,
                      color: Theme.of(context).brightness == Brightness.dark
                          ? Colors.green.shade300
                          : Colors.green.shade700,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        l10n.homeAiPlatformsAvailable(
                          availablePlatforms.join(', '),
                        ),
                        style: TextStyle(
                          fontSize: 14,
                          color: Theme.of(context).brightness == Brightness.dark
                              ? Colors.green.shade300
                              : Colors.green.shade700,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            if (availablePlatforms.isEmpty &&
                (!kIsWeb ||
                    (ref.watch(canAccessAdminSettingsProvider).valueOrNull ??
                        false))) ...<Widget>[
              const SizedBox(height: 16),
              InkWell(
                onTap: () => context.push('${AppRouter.settingsRoute}?tab=1'),
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Theme.of(context).brightness == Brightness.dark
                        ? Colors.orange.shade900.withOpacity(0.3)
                        : Colors.orange.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: Theme.of(context).brightness == Brightness.dark
                          ? Colors.orange.shade700
                          : Colors.orange.shade200,
                    ),
                  ),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        Icons.settings_suggest,
                        color: Theme.of(context).brightness == Brightness.dark
                            ? Colors.orange.shade300
                            : Colors.orange.shade700,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          l10n.homeAiPlatformsConfigureNotice,
                          style: TextStyle(
                            fontSize: 14,
                            color:
                                Theme.of(context).brightness == Brightness.dark
                                    ? Colors.orange.shade300
                                    : Colors.orange.shade700,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      Icon(
                        Icons.arrow_forward_ios,
                        size: 14,
                        color: Theme.of(context).brightness == Brightness.dark
                            ? Colors.orange.shade300
                            : Colors.orange.shade700,
                      ),
                    ],
                  ),
                ),
              ),
            ],
            // Backend status indicator (Windows desktop only)
            if (!kIsWeb &&
                defaultTargetPlatform == TargetPlatform.windows) ...<Widget>[
              const SizedBox(height: 16),
              _buildBackendStatusIndicator(context),
            ],
          ],
        ),
      ),
    );
    return result;
  }

  /// Compute remaining trial days from ISO date string (YYYY-MM-DD).
  /// Returns null when date is invalid or missing; returns 0 when trial has ended.
  int? _computeTrialDaysRemaining(String? trialEndsAtIso) {
    if (trialEndsAtIso == null || trialEndsAtIso.isEmpty) return null;
    try {
      final endDate = DateTime.parse(trialEndsAtIso);
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final endDay = DateTime(endDate.year, endDate.month, endDate.day);
      final diff = endDay.difference(today).inDays;
      // When diff <= 0, treat as expired (0 days remaining)
      return diff > 0 ? diff : 0;
    } catch (_) {
      return null;
    }
  }

  /// Pro edition status text: trial remaining / not activated / activated.
  String _proStatusLabel() {
    final l10n = AppLocalizations.of(context)!;
    if (_donorStatus?.activated ?? false)
      return l10n.homeEditionProStatusActivated;
    if (_trialDaysRemaining != null && _trialDaysRemaining! > 0) {
      return l10n.homeEditionProStatusTrialRemaining(_trialDaysRemaining!);
    }
    return l10n.homeEditionProStatusNotActivated;
  }

  /// Edition status block (OpenSource edition): Desktop + Web are always available.
  Widget _buildEditionStatusSection(BuildContext context) {
    final theme = Theme.of(context);
    final surfaceColor = theme.colorScheme.surfaceContainerHighest;
    final borderColor = theme.colorScheme.outlineVariant.withOpacity(0.5);
    final textStyle = TextStyle(
      fontSize: 12,
      fontWeight: FontWeight.w500,
      color: theme.colorScheme.onSurfaceVariant,
    );
    const smallPadding = EdgeInsets.symmetric(horizontal: 8, vertical: 4);
    const String platformLabel = kIsWeb ? 'Web' : 'Desktop';
    const String availabilityLabel = 'Available';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Container(
          padding: smallPadding,
          decoration: BoxDecoration(
            color: surfaceColor,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: borderColor),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(platformLabel, style: textStyle),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  availabilityLabel,
                  style: textStyle.copyWith(
                    fontWeight: FontWeight.normal,
                    fontSize: 11,
                  ),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 1,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  /// Build welcome message based on user type (desktop Pro/Standard) or default intro.
  String _buildWelcomeMessage() {
    final l10n = AppLocalizations.of(context)!;
    final isDesktop = !kIsWeb &&
        (defaultTargetPlatform == TargetPlatform.windows ||
            defaultTargetPlatform == TargetPlatform.linux ||
            defaultTargetPlatform == TargetPlatform.macOS);

    if (isDesktop && _isDonor != null) {
      return _isDonor!
          ? l10n.homeWelcomeDearPro
          : l10n.homeWelcomeDearStandard;
    }

    return l10n.homeWelcomeHello;
  }

  /// Build backend status indicator widget
  Widget _buildBackendStatusIndicator(BuildContext context) {
    final backendStatus = ref.watch(backendStatusProvider);
    final l10n = AppLocalizations.of(context)!;

    Color statusColor;
    IconData statusIcon;
    String statusText;

    switch (backendStatus) {
      case BackendStatus.starting:
        statusColor = Theme.of(context).brightness == Brightness.dark
            ? Colors.orange.shade300
            : Colors.orange.shade700;
        statusIcon = Icons.hourglass_empty;
        statusText = l10n.homeBackendStatusStarting;
        break;
      case BackendStatus.connecting:
        statusColor = Theme.of(context).brightness == Brightness.dark
            ? Colors.blue.shade300
            : Colors.blue.shade700;
        statusIcon = Icons.sync;
        statusText = l10n.homeBackendStatusConnecting;
        break;
      case BackendStatus.connected:
        statusColor = Theme.of(context).brightness == Brightness.dark
            ? Colors.green.shade300
            : Colors.green.shade700;
        statusIcon = Icons.check_circle;
        statusText = l10n.homeBackendStatusConnected;
        break;
      case BackendStatus.disconnected:
        statusColor = Theme.of(context).brightness == Brightness.dark
            ? Colors.red.shade300
            : Colors.red.shade700;
        statusIcon = Icons.error_outline;
        statusText = l10n.homeBackendStatusDisconnected;
        break;
      case BackendStatus.unknown:
        statusColor = Theme.of(context).brightness == Brightness.dark
            ? Colors.grey.shade400
            : Colors.grey.shade600;
        statusIcon = Icons.help_outline;
        statusText = l10n.homeBackendStatusUnknown;
        break;
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).brightness == Brightness.dark
            ? statusColor.withOpacity(0.2)
            : statusColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: statusColor.withOpacity(0.5),
        ),
      ),
      child: Row(
        children: <Widget>[
          Icon(
            statusIcon,
            color: statusColor,
            size: 20,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              statusText,
              style: TextStyle(
                fontSize: 14,
                color: statusColor,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          if (backendStatus == BackendStatus.disconnected) ...<Widget>[
            const SizedBox(width: 8),
            TextButton(
              onPressed: () {
                ref.read(backendStatusProvider.notifier).refresh();
              },
              child: Text(
                l10n.homeBackendRetry,
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// Log home screen size for debugging
  void _logHomeScreenSize() {
    final context = _homeScaffoldKey.currentContext;
    if (context != null) {
      final RenderBox? renderBox = context.findRenderObject() as RenderBox?;
      if (renderBox != null && renderBox.hasSize) {
        final size = renderBox.size;
        debugPrint(
          '[Home Screen] Size: (${size.width.toStringAsFixed(2)}, ${size.height.toStringAsFixed(2)})',
        );
      }
    }
  }
}
