import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart'
    show kDebugMode, kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:go_router/src/router.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:window_manager/window_manager.dart'
    if (dart.library.html) 'app/window_manager_stub.dart';

// Conditional import for dart:io (not available on web)
import 'dart:io' if (dart.library.html) 'shared/utils/io_stub.dart' as io;

import 'app/theme.dart';
import 'app/app_config.dart';
import 'app/app_router.dart';
import 'app/windows_close_interceptor.dart';
import 'core/services/api_service.dart';
import 'shared/services/config_service.dart';
import 'shared/services/translation_stats_service.dart';
import 'shared/services/donor_activation_service.dart';

import 'shared/providers/settings_provider.dart';
import 'shared/providers/auth_provider.dart';
import 'shared/providers/edition_title_provider.dart';
import 'l10n/app_localizations.dart';
import 'shared/utils/set_page_title_stub.dart'
    if (dart.library.html) 'shared/utils/set_page_title_web.dart'
    as page_title_util;
import 'features/translation/services/persistence_migration_service.dart';
import 'features/tasks/services/flow_state_persistence.dart';
import 'features/translation/services/tab_background_update_service.dart';
import 'features/settings/screens/ai_platform_settings.dart'
    show aiPlatformSettingsProvider;
import 'shared/utils/app_logger.dart';
import 'shared/utils/desktop_drop_utils_stub.dart'
    if (dart.library.html) 'shared/utils/desktop_drop_utils_web.dart'
    as drop_utils;
import 'shared/utils/webview_platform_bootstrap_stub.dart'
    if (dart.library.io) 'shared/utils/webview_platform_bootstrap.dart';

// Global variable to track runApp call time for diagnostics
DateTime? _runAppCallTime;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  ensureWebViewPlatformRegistered();

  // On web, override desktop_drop's window property drag handlers so that
  // their (unimplemented) method channel is never called during drag.
  if (kIsWeb) {
    drop_utils.disableDesktopDropWebPlugin();
    // Re-apply after first frame in case plugin registers after main().
    WidgetsBinding.instance.addPostFrameCallback((_) {
      drop_utils.disableDesktopDropWebPlugin();
    });
  }

  final isDesktop = !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.windows ||
          defaultTargetPlatform == TargetPlatform.linux ||
          defaultTargetPlatform == TargetPlatform.macOS);

  // Initialize Hive for local storage (can be slow on first run, but required for app)
  // On desktop, initialize asynchronously to avoid blocking startup
  if (isDesktop) {
    // Desktop: initialize asynchronously in background, don't block startup
    Future.microtask(() async {
      try {
        await Hive.initFlutter();
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [STARTUP] Background Hive initialization failed: $e');
        }
      }
    });
  } else {
    // Web/Mobile: wait for Hive initialization (required for IndexedDB)
    try {
      await Hive.initFlutter().timeout(
        const Duration(seconds: 10),
        onTimeout: () {
          if (kDebugMode) {
            print('⚠️ [STARTUP] Hive initialization timeout after 10s');
          }
        },
      );
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [STARTUP] Hive initialization failed: $e');
      }
    }
  }

  // Initialize AppConfig (load custom server URL if set)
  await AppConfig.initialize();
  if (kDebugMode) {
    print('🚀 [STARTUP] AppConfig initialized, baseUrl: ${AppConfig.baseUrl}');
  }
  
  // Initialize API service
  ApiService().initialize();

  // Log current log level at startup (only in debug mode)
  if (kDebugMode) {
    final currentLogLevel =
        AppLogger.currentLevel.toString().split('.').last.toUpperCase();
    print('🚀 [STARTUP] Log level: $currentLogLevel');
  }

  // Preload auth config BEFORE starting app so router can decide login/home immediately
  // Desktop: skip network request entirely (already handled in ConfigService)
  // Web: need to check with timeout
  if (isDesktop) {
    ConfigService().setDefaultAuthRequired(false);
  } else {
    try {
      await ConfigService().loadAuthConfigOnce().timeout(
        const Duration(seconds: 3),
        onTimeout: () {
          ConfigService().setDefaultAuthRequired(false);
        },
      );
    } catch (e) {
      ConfigService().setDefaultAuthRequired(false);
    }
  }

  // Set preferred orientations (non-blocking, can be done in parallel)
  // On desktop, delay to background since orientation doesn't matter
  if (isDesktop) {
    Future.microtask(() {
      SystemChrome.setPreferredOrientations(<DeviceOrientation>[
        DeviceOrientation.portraitUp,
        DeviceOrientation.portraitDown,
        DeviceOrientation.landscapeLeft,
        DeviceOrientation.landscapeRight,
      ]).catchError((e) {
        // Ignore orientation setting errors
      });
    });
  } else {
    // Mobile/Web: set immediately
    SystemChrome.setPreferredOrientations(<DeviceOrientation>[
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]).catchError((e) {
      // Ignore orientation setting errors
    });
  }

  // Run non-critical initialization in background (non-blocking)
  Future.microtask(() async {
    // Initialize donor activation service
    DonorActivationService().initialize().catchError((e) {
      // Donor activation initialization error (non-fatal)
    });

    // Initialize translation statistics service
    TranslationStatsService().ensureInitialized().catchError((e) {
      // Stats initialization error (non-fatal)
    });

    // Run persistence migration in background (non-blocking)
    PersistenceMigrationService.migratePersistenceData().catchError((e) {
      // Migration error (non-fatal)
    });

    // Clean up expired Flows - run in a separate isolate to avoid blocking
    // This is important for Windows desktop where SharedPreferences can block the platform thread
    Future(() async {
      try {
        await FlowStatePersistence.cleanupExpiredFlows();
      } catch (e) {
        // Failed to cleanup expired Flows (non-fatal)
      }
    });
    
    // One-time cleanup of flows older than 14 days (to clean up accumulated old flows)
    // This helps users who have many old flows from before the 7-day limit
    // Run after a longer delay to avoid interfering with app startup
    Future.delayed(const Duration(seconds: 30), () async {
      try {
        final cleaned = await FlowStatePersistence.cleanupFlowsOlderThan(14);
        if (cleaned > 0 && kDebugMode) {
          print('🧹 One-time cleanup: removed $cleaned flows older than 14 days');
        }
      } catch (e) {
        // Silent fail - cleanup is not critical
      }
    });
  });

  // Windows desktop only: prevent window close until user confirms; show dialog and notify Launcher to exit
  if (isDesktop && defaultTargetPlatform == TargetPlatform.windows) {
    try {
      await windowManager.ensureInitialized();
      await windowManager.setPreventClose(true);
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ [STARTUP] window_manager init failed: $e');
      }
    }
  }

  // Handle app exit on desktop platforms (skip on web) - delay to background to not block startup
  if (isDesktop) {
    // Delay process signal registration to background to avoid blocking startup
    Future.microtask(() async {
      try {
        // Register exit handler to ensure clean shutdown
        // Note: SIGINT is supported on all platforms, SIGTERM is not available on Windows
        try {
          io.ProcessSignal.sigint.watch().listen((signal) {
            print('Application received SIGINT, exiting...');
            // REMOVED: BackendManager().stopBackend() - backend runs independently
            io.exit(0);
          });
        } catch (e) {
          // SIGINT not available on this platform, ignore
        }

        // SIGTERM is not supported on Windows
        if (defaultTargetPlatform != TargetPlatform.windows) {
          try {
            io.ProcessSignal.sigterm.watch().listen((signal) {
              print('Application received SIGTERM, exiting...');
              // REMOVED: BackendManager().stopBackend() - backend runs independently
              io.exit(0);
            });
          } catch (e) {
            // SIGTERM not available on this platform, ignore
          }
        }
      } catch (e) {
        // Platform API not available, ignore
      }
    });
  }

  final container = ProviderContainer();

  // Initialize TabBackgroundUpdateService with container - delay to background on desktop
  if (isDesktop) {
    Future.microtask(() {
      try {
        final tabUpdateService =
            container.read(tabBackgroundUpdateServiceProvider);
        tabUpdateService.setContainer(container);
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ [STARTUP] TabBackgroundUpdateService init failed: $e');
        }
      }
    });
  } else {
    final tabUpdateService = container.read(tabBackgroundUpdateServiceProvider);
    tabUpdateService.setContainer(container);
  }

  // Ensure auth provider (and its delayed check) starts immediately
  container.read(authProvider);

  _runAppCallTime = DateTime.now();
  runApp(
    UncontrolledProviderScope(
      container: container,
      child: isWindowsDesktopCloseInterceptorEnabled
          ? const WindowsCloseInterceptor(child: OwlangsApp())
          : const OwlangsApp(),
    ),
  );
}

class OwlangsApp extends ConsumerWidget {
  const OwlangsApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Ensure auth state is evaluated immediately on startup
    final buildStartTime = DateTime.now();
    AppLogger.log(
      'Startup',
      'OwlangsApp.build() called at ${buildStartTime.toIso8601String()}',
    );

    // Calculate time since runApp was called
    if (_runAppCallTime != null) {
      final timeSinceRunApp = buildStartTime.difference(_runAppCallTime!);
      AppLogger.log(
        'Startup',
        '⚠️ DELAY DETECTED: ${timeSinceRunApp.inSeconds}s ${timeSinceRunApp.inMilliseconds % 1000}ms since runApp was called',
      );
    } else {
      print(
        '🚀 [APP] Warning: _runAppCallTime not set, cannot calculate delay',
      );
    }

    print('🚀 [APP] Watching authProvider...');
    final authWatchStart = DateTime.now();
    ref.watch(authProvider);
    final authWatchDuration = DateTime.now().difference(authWatchStart);
    print(
      '🚀 [APP] AuthProvider watched in ${authWatchDuration.inMilliseconds}ms, watching globalSettingsProvider...',
    );

    // When user logs in, reload global settings and AI platforms from backend
    // so that configuration (which is gated by auth) is fetched with the valid token.
    ref.listen<AuthState>(authProvider, (previous, next) {
      next.whenOrNull(
        authenticated: (_) {
          try {
            ref.read(globalSettingsProvider.notifier).reloadSettings();
          } catch (e) {
            if (kDebugMode) {
              print('⚠️ [AUTH] Failed to reload settings after login: $e');
            }
          }
          try {
            ref
                .read(aiPlatformSettingsProvider.notifier)
                .loadPlatforms(force: true);
          } catch (e) {
            if (kDebugMode) {
              print('⚠️ [AUTH] Failed to reload AI platforms after login: $e');
            }
          }
        },
      );
    });

    // Watch global settings to respond to dark mode changes
    // Use try-catch to handle potential initialization delays gracefully
    GlobalSettings globalSettings;
    try {
      globalSettings = ref.watch(globalSettingsProvider);
      print('🚀 [APP] GlobalSettingsProvider watched, building UI...');
    } catch (e) {
      // Fallback to default settings if provider not ready yet
      print('🚀 [APP] GlobalSettingsProvider not ready, using defaults: $e');
      globalSettings = const GlobalSettings();
    }

    // Determine theme mode based on user setting
    final themeMode =
        globalSettings.darkMode ? ThemeMode.dark : ThemeMode.light;

    // App title with edition (Basic / Pro / Enterprise) for window and document title
    final editionTitleAsync = ref.watch(editionTitleProvider);
    final appTitle = editionTitleAsync.valueOrNull ?? AppConfig.appName;
    ref.listen<AsyncValue<String>>(editionTitleProvider, (prev, next) {
      next.whenOrNull(
        data: (String title) {
          if (kIsWeb) {
            page_title_util.setPageTitle(title);
          } else if (defaultTargetPlatform == TargetPlatform.windows) {
            windowManager.setTitle(title);
          }
        },
      );
    });

    return ScreenUtilInit(
      designSize: const Size(375, 812), // iPhone X design size
      minTextAdapt: true,
      splitScreenMode: true,
      builder: (context, child) {
        final router = AppRouter.router;
        final locale = mapLanguageCodeToLocale(globalSettings.language);
        return MaterialApp.router(
          title: appTitle,
          debugShowCheckedModeBanner: false,
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: themeMode, // Use user's dark mode setting
          locale: locale,
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: const <LocalizationsDelegate<dynamic>>[
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          routerConfig: router,
          builder: (context, widget) {
            // Set system UI overlay style based on current theme
            final brightness = Theme.of(context).brightness;
            SystemChrome.setSystemUIOverlayStyle(
              SystemUiOverlayStyle(
                statusBarColor: Colors.transparent,
                statusBarIconBrightness: brightness == Brightness.dark
                    ? Brightness.light
                    : Brightness.dark,
                systemNavigationBarColor: brightness == Brightness.dark
                    ? const Color(0xFF121212)
                    : Colors.white,
                systemNavigationBarIconBrightness: brightness == Brightness.dark
                    ? Brightness.light
                    : Brightness.dark,
              ),
            );
            // Debug: log viewport / physical size on every build
            if (kDebugMode) {
              final mq = MediaQuery.of(context);
              final double physicalW = mq.size.width * mq.devicePixelRatio;
              final double physicalH = mq.size.height * mq.devicePixelRatio;
              debugPrint(
                '[VIEWPORT] logical=${mq.size.width.toStringAsFixed(0)}x${mq.size.height.toStringAsFixed(0)}, '
                'physical=${physicalW.toStringAsFixed(0)}x${physicalH.toStringAsFixed(0)}, '
                'devicePixelRatio=${mq.devicePixelRatio.toStringAsFixed(2)}',
              );
            }
            return LayoutBuilder(
              builder: (context, constraints) {
                final appChild = MediaQuery(
                  // Set text scale factor to prevent system font scaling
                  data: MediaQuery.of(context)
                      .copyWith(textScaler: const TextScaler.linear(1)),
                  child: widget!,
                );
                // Enforce minimum 800px width for web; if viewport is narrower,
                // wrap with horizontal scroll so content never clips.
                if (constraints.maxWidth < 800) {
                  return SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: SizedBox(
                      width: 800,
                      height: constraints.maxHeight,
                      child: appChild,
                    ),
                  );
                }
                return appChild;
              },
            );
          },
        );
      },
    );
  }
}

Locale mapLanguageCodeToLocale(String code) {
  // Normalize language code to lower case and use '-' as separator
  final String normalized = code.toLowerCase().replaceAll('_', '-');

  if (kDebugMode) {
    // This log helps trace unexpected language codes from backend/user profile.
    print(
      '🌐 [LOCALE] mapLanguageCodeToLocale input="$code", normalized="$normalized"',
    );
  }

  switch (normalized) {
    // Simplified Chinese aliases
    case 'zh':
    case 'zh-cn':
    case 'zh-hans':
      return const Locale('zh');

    // Traditional Chinese aliases (currently mapped to zh locale;
    // if a dedicated Traditional Chinese ARB is added, adjust here)
    case 'zh-tw':
    case 'zh-hk':
    case 'zh-mo':
    case 'zh-hant':
      return const Locale('zh');

    // Japanese (with common region alias)
    case 'ja':
    case 'ja-jp':
      return const Locale('ja');

    // Korean (with common region alias)
    case 'ko':
    case 'ko-kr':
      return const Locale('ko');

    // Spanish (with common region alias)
    case 'es':
    case 'es-es':
      return const Locale('es');

    // Fallback to English for unknown codes
    default:
      return const Locale('en');
  }
}
