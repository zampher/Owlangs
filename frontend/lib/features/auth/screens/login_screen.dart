import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/models/user_model.dart';
import '../../../shared/providers/auth_provider.dart';
import '../../../shared/services/config_service.dart';
import '../../../app/app_router.dart';
import '../../../l10n/app_localizations.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final bool _rememberMe = false;
  bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    // Clear any previous auth error when entering the login screen
    // so old error messages do not keep popping up.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      ref.read(authProvider.notifier).clearError();
      final messenger = ScaffoldMessenger.maybeOf(context);
      messenger?.hideCurrentSnackBar();
    });
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (_formKey.currentState?.validate() ?? false) {
      // Clear previous error and hide any visible snackbar before a new attempt
      ref.read(authProvider.notifier).clearError();
      final messenger = ScaffoldMessenger.maybeOf(context);
      messenger?.hideCurrentSnackBar();

      await ref.read(authProvider.notifier).login(
            _usernameController.text.trim(),
            _passwordController.text,
            rememberMe: _rememberMe,
          );
    }
  }

  void _togglePasswordVisibility() {
    setState(() {
      _obscurePassword = !_obscurePassword;
    });
  }

  @override
  Widget build(BuildContext context) {
    print('🔍 [DEBUG] LoginScreen build() called');
    final authState = ref.watch(authProvider);
    print(
      '🔍 [DEBUG] LoginScreen current auth state: ${authState.runtimeType}',
    );
    final l10n = AppLocalizations.of(context)!;
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    // Handle authentication state changes
    ref.listen<AuthState>(authProvider, (previous, next) {
      print(
        '🔍 [DEBUG] LoginScreen auth state changed from ${previous?.runtimeType} to ${next.runtimeType}',
      );
      next.when(
        initial: () {
          print('🔍 [DEBUG] LoginScreen: Auth state is initial');
        },
        loading: () {
          print('🔍 [DEBUG] LoginScreen: Auth state is loading');
        },
        authenticated: (user) {
          print('🔍 [DEBUG] LoginScreen: User authenticated: ${user.username}');
          // Finish autofill context so browser can show "Save password?" with username + password
          TextInput.finishAutofillContext();
          // Navigate to home immediately after successful login
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              context.go(AppRouter.homeRoute);
            }
          });
        },
        unauthenticated: () {
          print('🔍 [DEBUG] LoginScreen: Auth state is unauthenticated');
        },
        error: (message) {
          print('🔍 [DEBUG] LoginScreen: Auth state has error: $message');
          if (!mounted) return;
          final messenger = ScaffoldMessenger.maybeOf(context);
          if (messenger == null) return;
          messenger.showSnackBar(
            SnackBar(
              content: SelectableText(
                message,
                style: const TextStyle(color: Colors.white),
              ),
              backgroundColor: Colors.red,
              duration: const Duration(seconds: 8),
              action: SnackBarAction(
                label: l10n.loginCopyErrorLabel,
                textColor: Colors.white,
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: message));
                  // Use maybeOf to avoid using deactivated context (e.g. after redirect to home)
                  final m = ScaffoldMessenger.maybeOf(context);
                  m?.showSnackBar(
                    SnackBar(
                      content: Text(l10n.loginErrorCopiedMessage),
                      duration: const Duration(seconds: 2),
                    ),
                  );
                },
              ),
            ),
          );
        },
      );
    });

    return Scaffold(
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth >= 720;

          if (isWide) {
            return Row(
              children: <Widget>[
                // Left: Brand Panel
                Expanded(
                  flex: 35,
                  child: _BrandPanel(cs: cs, l10n: l10n),
                ),
                // Right: Login Form Panel
                Expanded(
                  flex: 65,
                  child: _LoginFormPanel(
                    authState: authState,
                    l10n: l10n,
                    formKey: _formKey,
                    usernameController: _usernameController,
                    passwordController: _passwordController,
                    obscurePassword: _obscurePassword,
                    togglePasswordVisibility: _togglePasswordVisibility,
                    handleLogin: _handleLogin,
                  ),
                ),
              ],
            );
          } else {
            // Narrow screen: stack vertically
            return SingleChildScrollView(
              child: Column(
                children: <Widget>[
                  _BrandPanel(cs: cs, compact: true, l10n: l10n),
                  Padding(
                    padding: const EdgeInsets.all(24),
                    child: _LoginFormPanel(
                      authState: authState,
                      l10n: l10n,
                      formKey: _formKey,
                      usernameController: _usernameController,
                      passwordController: _passwordController,
                      obscurePassword: _obscurePassword,
                      togglePasswordVisibility: _togglePasswordVisibility,
                      handleLogin: _handleLogin,
                    ),
                  ),
                ],
              ),
            );
          }
        },
      ),
    );
  }
}

// ─── Brand Panel (left side) ────────────────────────────────────────────────

class _BrandPanel extends StatelessWidget {
  final ColorScheme cs;
  final bool compact;
  final AppLocalizations l10n;

  const _BrandPanel({
    required this.cs,
    this.compact = false,
    required this.l10n,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[
            cs.primary,
            cs.primary.withValues(alpha: 0.85),
            cs.secondary,
          ],
        ),
      ),
      child: Center(
        child: Padding(
          padding: EdgeInsets.all(compact ? 32 : 48),
          child: Column(
            mainAxisSize: compact ? MainAxisSize.min : MainAxisSize.max,
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              // Logo
              Image.asset(
                'images/logo_96.png',
                width: compact ? 72 : 100,
                height: compact ? 72 : 100,
                errorBuilder: (_, __, ___) => Icon(
                  Icons.language,
                  size: compact ? 72 : 100,
                  color: Colors.white,
                ),
              ),
              SizedBox(height: compact ? 20 : 28),

              // App name
              Text(
                'Owlangs',
                style: TextStyle(
                  fontSize: compact ? 28 : 36,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                  letterSpacing: 1.2,
                ),
              ),
              const SizedBox(height: 8),

              // Tagline
              Text(
                l10n.loginSubtitleFeatures,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: compact ? 14 : 16,
                  color: Colors.white.withValues(alpha: 0.85),
                  fontWeight: FontWeight.w300,
                ),
              ),
              SizedBox(height: compact ? 24 : 36),

              // Accent line
              Container(
                width: 48,
                height: 3,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.6),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              SizedBox(height: compact ? 24 : 36),

              // Feature points
              _FeatureItem(
                icon: Icons.description_outlined,
                text: l10n.loginFeatureFormats,
                compact: compact,
              ),
              SizedBox(height: compact ? 16 : 20),
              _FeatureItem(
                icon: Icons.design_services_outlined,
                text: l10n.loginFeatureLayout,
                compact: compact,
              ),
              SizedBox(height: compact ? 16 : 20),
              _FeatureItem(
                icon: Icons.smart_toy_outlined,
                text: l10n.loginFeaturePlatforms,
                compact: compact,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FeatureItem extends StatelessWidget {
  final IconData icon;
  final String text;
  final bool compact;

  const _FeatureItem({
    required this.icon,
    required this.text,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Icon(icon, color: Colors.white.withValues(alpha: 0.9), size: compact ? 20 : 24),
        const SizedBox(width: 14),
        Flexible(
          child: Text(
            text,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.85),
              fontSize: compact ? 13 : 14,
              height: 1.5,
            ),
          ),
        ),
      ],
    );
  }
}

// ─── Login Form Panel (right side) ──────────────────────────────────────────

class _LoginFormPanel extends StatelessWidget {
  final AuthState authState;
  final AppLocalizations l10n;
  final GlobalKey<FormState> formKey;
  final TextEditingController usernameController;
  final TextEditingController passwordController;
  final bool obscurePassword;
  final VoidCallback togglePasswordVisibility;
  final VoidCallback handleLogin;

  const _LoginFormPanel({
    required this.authState,
    required this.l10n,
    required this.formKey,
    required this.usernameController,
    required this.passwordController,
    required this.obscurePassword,
    required this.togglePasswordVisibility,
    required this.handleLogin,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 32),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              // Title
              Text(
                l10n.loginWelcomeBack,
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: cs.onSurface,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                l10n.loginSubtitleTagline,
                style: TextStyle(
                  fontSize: 15,
                  color: cs.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 40),

              // Login Form
              Form(
                key: formKey,
                child: AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      // Username
                      TextFormField(
                        controller: usernameController,
                        autofillHints: const <String>[AutofillHints.username],
                        decoration: InputDecoration(
                          labelText: l10n.loginUsernameLabel,
                          hintText: l10n.loginUsernameHint,
                          prefixIcon: const Icon(Icons.person_outline),
                          filled: true,
                          fillColor: cs.surfaceContainerHighest.withValues(alpha: 0.4),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(color: cs.outlineVariant),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(color: cs.outlineVariant),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(color: cs.primary, width: 2),
                          ),
                        ),
                        validator: (value) {
                          if (value == null || value.isEmpty) {
                            return l10n.loginUsernameRequiredError;
                          }
                          if (value.length < 3) {
                            return l10n.loginUsernameMinLengthError;
                          }
                          return null;
                        },
                      ),

                      const SizedBox(height: 20),

                      // Password
                      TextFormField(
                        controller: passwordController,
                        obscureText: obscurePassword,
                        autofillHints: const <String>[AutofillHints.password],
                        decoration: InputDecoration(
                          labelText: l10n.loginPasswordLabel,
                          hintText: l10n.loginPasswordHint,
                          prefixIcon: const Icon(Icons.lock_outline),
                          suffixIcon: IconButton(
                            icon: Icon(
                              obscurePassword
                                  ? Icons.visibility_off_outlined
                                  : Icons.visibility_outlined,
                            ),
                            onPressed: togglePasswordVisibility,
                          ),
                          filled: true,
                          fillColor: cs.surfaceContainerHighest.withValues(alpha: 0.4),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(color: cs.outlineVariant),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(color: cs.outlineVariant),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(color: cs.primary, width: 2),
                          ),
                        ),
                        validator: (value) {
                          if (value == null || value.isEmpty) {
                            return l10n.loginPasswordRequiredError;
                          }
                          return null;
                        },
                        onFieldSubmitted: (_) => handleLogin(),
                      ),

                      const SizedBox(height: 32),

                      // Login Button
                      FilledButton(
                        onPressed: authState.maybeWhen(
                          loading: () => null,
                          orElse: () => handleLogin,
                        ),
                        style: FilledButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          textStyle: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        child: authState.maybeWhen(
                          loading: () => true,
                          orElse: () => false,
                        )
                            ? const SizedBox(
                                height: 22,
                                width: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2.5,
                                  valueColor:
                                      AlwaysStoppedAnimation<Color>(
                                    Colors.white,
                                  ),
                                ),
                              )
                            : Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: <Widget>[
                                  const Icon(Icons.login, size: 20),
                                  const SizedBox(width: 10),
                                  Text(l10n.commonLogin),
                                ],
                              ),
                      ),

                      const SizedBox(height: 16),

                      // Forgot Password
                      Center(
                        child: TextButton(
                          onPressed: () => showDialog(
                            context: context,
                            builder: (context) => AlertDialog(
                              title: Text(l10n.loginPasswordRecoveryTitle),
                              content: Column(
                                mainAxisSize: MainAxisSize.min,
                                crossAxisAlignment:
                                    CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    l10n.loginPasswordRecoveryContactAdmin,
                                  ),
                                  const SizedBox(height: 16),
                                  Text(
                                    l10n.loginPasswordRecoveryAdminHint,
                                    style: TextStyle(
                                      fontSize: 13,
                                      color: cs.onSurfaceVariant,
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  Text(
                                    l10n.loginPasswordRecoveryAdminGuide,
                                    style: TextStyle(
                                      fontSize: 13,
                                      color: cs.onSurfaceVariant,
                                    ),
                                  ),
                                ],
                              ),
                              actions: [
                                TextButton(
                                  onPressed: () =>
                                      Navigator.of(context).pop(),
                                  child: Text(l10n.commonOk),
                                ),
                              ],
                            ),
                          ),
                          child: Text(
                            l10n.loginForgotPassword,
                            style: TextStyle(
                              color: cs.primary,
                              fontSize: 14,
                            ),
                          ),
                        ),
                      ),

                      const SizedBox(height: 12),

                      // Auth Method Info
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 10),
                        decoration: BoxDecoration(
                          color: cs.tertiaryContainer.withValues(alpha: 0.5),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: <Widget>[
                            Icon(
                              Icons.info_outline,
                              color: cs.onTertiaryContainer,
                              size: 15,
                            ),
                            const SizedBox(width: 8),
                            Flexible(
                              child: Text(
                                l10n.loginAuthMethodDefault,
                                style: TextStyle(
                                  color: cs.onTertiaryContainer,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 16),
                      if (ConfigService().authRequired == false)
                        Center(
                          child: TextButton.icon(
                            onPressed: () {
                              context.go(AppRouter.homeRoute);
                            },
                            icon: const Icon(Icons.arrow_back, size: 18),
                            label: Text(l10n.backToHome),
                            style: TextButton.styleFrom(
                              foregroundColor: cs.primary,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
