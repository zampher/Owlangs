import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../l10n/app_localizations.dart';

import '../shared/models/user_model.dart';
import '../shared/services/config_service.dart';
import '../features/auth/screens/login_screen.dart';
// import '../features/home/screens/home_screen.dart';
import '../features/translation/screens/translation_screen.dart';
import '../features/translation/screens/translation_queue_screen.dart';
import '../features/tasks/screens/workspace_screen.dart';
import '../features/anonymization/screens/anonymize_screen.dart';
import '../features/settings/screens/settings_screen.dart';
import '../features/settings/screens/setup_wizard_screen.dart';
import '../features/profile/screens/profile_screen.dart';
import '../features/donate_help/screens/donate_help_contact_screen.dart';
import '../shared/providers/auth_provider.dart';

class GoRouterRefreshStream extends ChangeNotifier {
  GoRouterRefreshStream(Stream<dynamic> stream) {
    notifyListeners();
    _subscription = stream.listen((_) => notifyListeners());
  }

  late final StreamSubscription<dynamic> _subscription;

  @override
  void dispose() {
    _subscription.cancel();
    super.dispose();
  }
}

class AppRouter {
  static const String loginRoute = '/login';
  static const String homeRoute = '/';
  static const String translationRoute = '/translation';
  static const String translationQueueRoute = '/translation-queue';
  static const String anonymizeRoute = '/anonymize';
  static const String settingsRoute = '/settings';
  static const String donateRoute = '/donate';
  static const String profileRoute = '/profile';
  static const String setupWizardRoute = '/setup-wizard';

  // Lazy initialization to avoid blocking startup
  static GoRouter? _routerInstance;
  static GoRouter get router {
    _routerInstance ??= _createRouter();
    return _routerInstance!;
  }

  static GoRouter _createRouter() => GoRouter(
        // Dynamic initial location will be determined by redirect logic
        initialLocation: '/',
        // Use a less frequent refresh to reduce overhead during startup
        refreshListenable: GoRouterRefreshStream(
          Stream.periodic(const Duration(seconds: 5)).map((_) => null),
        ),
        redirect: (BuildContext context, GoRouterState state) {
          // Decide auth policy by backend config
          // Note: Config should already be loaded in main() before app starts
          final cfg = ConfigService();
          final authRequired = cfg.authRequired;
          // Get the auth state from the provider
          final container = ProviderScope.containerOf(context);
          final authState = container.read(authProvider);

          // If config not loaded yet, stay on current route (will redirect once loaded)
          if (authRequired == null) {
            // If we're on login page and config not loaded, wait a bit
            if (state.uri.path == loginRoute) return null;
            return null;
          }

          // Auth disabled: allow /login so guest can open it from "admin required" dialog; after login redirect to home
          if (authRequired == false) {
            final isAuth = authState.maybeWhen(
                authenticated: (_) => true, orElse: () => false,);
            if (isAuth && state.uri.path == loginRoute) return homeRoute;
            return null;
          }

          return authState.when(
            initial: () => null, // Stay on current route during initial state
            loading: () => null, // Stay on current route during loading
            authenticated: (user) {
              // If authenticated and on login page, redirect to home
              if (state.uri.path == loginRoute) {
                return homeRoute;
              }
              return null; // Allow navigation to any route
            },
            unauthenticated: () {
              // If not authenticated and not on login page, redirect to login
              if (state.uri.path != loginRoute) {
                return loginRoute;
              }
              return null; // Allow staying on login page
            },
            error: (message) {
              // Treat error state as unauthenticated for routing purposes
              if (state.uri.path != loginRoute) {
                return loginRoute;
              }
              return null; // Allow staying on login page to show error
            },
          );
        },
        routes: <RouteBase>[
          // Login Route
          GoRoute(
            path: loginRoute,
            name: 'login',
            builder: (BuildContext context, GoRouterState state) =>
                const LoginScreen(),
          ),

          // Home Route -> Workspace (multi-task)
          GoRoute(
            path: homeRoute,
            name: 'home',
            builder: (BuildContext context, GoRouterState state) =>
                const WorkspaceScreen(),
          ),

          // Translation Route (optional ?execution_mode=queued, ?reedit_task_id=...)
          GoRoute(
            path: translationRoute,
            name: 'translation',
            builder: (BuildContext context, GoRouterState state) {
              final String? q = state.uri.queryParameters['execution_mode'];
              final String mode =
                  (q == 'queued') ? 'queued' : 'immediate';

              // Re-edit parameters (optional)
              final String? reeditTaskId =
                  state.uri.queryParameters['reedit_task_id'];
              final String? reeditWorkflowType =
                  state.uri.queryParameters['reedit_workflow_type'];
              final String? reeditFileName =
                  state.uri.queryParameters['reedit_file_name'];
              final String? viewMode =
                  state.uri.queryParameters['view_mode'];

              return TranslationScreen(
                executionMode: mode,
                reeditTaskId: reeditTaskId,
                reeditWorkflowType: reeditWorkflowType,
                reeditFileName: reeditFileName,
                viewMode: viewMode,
              );
            },
          ),

          GoRoute(
            path: translationQueueRoute,
            name: 'translation_queue',
            builder: (BuildContext context, GoRouterState state) =>
                const TranslationQueueScreen(),
          ),

          // Anonymization Route
          GoRoute(
            path: anonymizeRoute,
            name: 'anonymize',
            builder: (BuildContext context, GoRouterState state) =>
                const AnonymizeScreen(),
          ),

          // Settings Route
          GoRoute(
            path: settingsRoute,
            name: 'settings',
            builder: (BuildContext context, GoRouterState state) {
              // Parse tab index from query parameter
              final tabParam = state.uri.queryParameters['tab'];
              int? initialTabIndex;
              if (tabParam != null) {
                initialTabIndex = int.tryParse(tabParam);
                // Validate tab index (0-5)
                if (initialTabIndex != null &&
                    (initialTabIndex < 0 || initialTabIndex >= 6)) {
                  initialTabIndex = null;
                }
              }
              return Scaffold(
                appBar: AppBar(
                  title: Text(AppLocalizations.of(context)!.homeNavSettings),
                  leadingWidth: 220,
                  leading: OwlangsAppBarLeading(
                    onTap: () => context.go(AppRouter.homeRoute),
                  ),
                  actions: <Widget>[
                    IconButton(
                      tooltip: 'Home',
                      onPressed: () => context.go(AppRouter.homeRoute),
                      icon: const Icon(Icons.home_outlined),
                    ),
                  ],
                ),
                body: SafeArea(
                  child: SettingsScreen(initialTabIndex: initialTabIndex),
                ),
              );
            },
          ),

          // Setup Wizard Route
          GoRoute(
            path: setupWizardRoute,
            name: 'setup_wizard',
            builder: (BuildContext context, GoRouterState state) =>
                const SetupWizardScreen(),
          ),

          // Donate & Help Route
          GoRoute(
            path: donateRoute,
            name: 'donate',
            builder: (BuildContext context, GoRouterState state) =>
                const DonateHelpContactScreen(),
          ),

          // Profile Route
          GoRoute(
            path: profileRoute,
            name: 'profile',
            builder: (BuildContext context, GoRouterState state) =>
                const ProfileScreen(),
          ),
        ],
        errorBuilder: (BuildContext context, GoRouterState state) {
          final l10n = AppLocalizations.of(context)!;
          return Scaffold(
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: <Widget>[
                  const Icon(
                    Icons.error_outline,
                    size: 64,
                    color: Colors.red,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    l10n.commonPageNotFound(state.uri.toString()),
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: () => context.go(homeRoute),
                    child: Text(l10n.commonGoHome),
                  ),
                ],
              ),
            ),
          );
        },
      );

  // Force initialization on first access (for testing)
  static void ensureInitialized() {
    router;
  }
}

/// Leading widget for app top AppBars: logo + title, tappable to go home.
class OwlangsAppBarLeading extends StatelessWidget {
  const OwlangsAppBarLeading({required this.onTap, super.key});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Image.asset(
                'images/logo_96.png',
                width: 48,
                height: 48,
                errorBuilder: (
                  context,
                  error,
                  stackTrace,
                ) =>
                    Icon(
                  Icons.language,
                  size: 32,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                'Owlangs',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
            ],
          ),
        ),
      );
}
