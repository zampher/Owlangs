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
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Card(
            elevation: 4,
            child: Container(
              width: 400,
              padding: const EdgeInsets.all(32),
              child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    // Logo and Title
                    Column(
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
                            size: 48,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Column(
                          children: [
                            Text(
                              'Owlangs',
                              style: TextStyle(
                                fontSize: 28,
                                fontWeight: FontWeight.bold,
                                color: Theme.of(context).colorScheme.primary,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              l10n.loginSubtitleFeatures,
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 15,
                                color: Theme.of(context).colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          l10n.loginSubtitleTagline,
                          style: TextStyle(
                            fontSize: 16,
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),

                    const SizedBox(height: 32),

                    // Login Form — AutofillGroup so browser can save/restore username + password together
                    Form(
                      key: _formKey,
                      child: AutofillGroup(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: <Widget>[
                            // Username Field
                            TextFormField(
                              controller: _usernameController,
                              autofillHints: const <String>[
                                AutofillHints.username,
                              ],
                              decoration: InputDecoration(
                                labelText: l10n.loginUsernameLabel,
                                hintText: l10n.loginUsernameHint,
                                prefixIcon: const Icon(Icons.person),
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

                            const SizedBox(height: 16),

                            // Password Field
                            TextFormField(
                              controller: _passwordController,
                              obscureText: _obscurePassword,
                              autofillHints: const <String>[
                                AutofillHints.password,
                              ],
                              decoration: InputDecoration(
                                labelText: l10n.loginPasswordLabel,
                                hintText: l10n.loginPasswordHint,
                                prefixIcon: const Icon(Icons.lock),
                                suffixIcon: IconButton(
                                  icon: Icon(
                                    _obscurePassword
                                        ? Icons.visibility_off
                                        : Icons.visibility,
                                  ),
                                  onPressed: _togglePasswordVisibility,
                                ),
                                labelStyle:
                                    const TextStyle(color: Colors.black87),
                                hintStyle: TextStyle(
                                  color: Colors.black.withOpacity(0.6),
                                ),
                              ),
                              validator: (value) {
                                if (value == null || value.isEmpty) {
                                  return l10n.loginPasswordRequiredError;
                                }
                                return null;
                              },
                              onFieldSubmitted: (_) => _handleLogin(),
                            ),

                            const SizedBox(height: 24),

                            // Login Button
                            FilledButton(
                              onPressed: authState.maybeWhen(
                                loading: () => null,
                                orElse: () => _handleLogin,
                              ),
                              child: authState.maybeWhen(
                                loading: () => true,
                                orElse: () => false,
                              )
                                  ? const SizedBox(
                                      height: 20,
                                      width: 20,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        valueColor:
                                            AlwaysStoppedAnimation<Color>(
                                          Colors.white,
                                        ),
                                      ),
                                    )
                                  : Row(
                                      mainAxisAlignment:
                                          MainAxisAlignment.center,
                                      children: <Widget>[
                                        const Icon(Icons.login, size: 20),
                                        const SizedBox(width: 8),
                                        Text(
                                          l10n.commonLogin,
                                          style: const TextStyle(fontSize: 16),
                                        ),
                                      ],
                                    ),
                            ),

                            const SizedBox(height: 16),

                            // Forgot Password Link
                            Center(
                              child: TextButton(
                                onPressed: () => showDialog(
                                  context: context,
                                  builder: (context) => AlertDialog(
                                    title: Text(l10n.loginPasswordRecoveryTitle),
                                    content: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          l10n.loginPasswordRecoveryContactAdmin,
                                        ),
                                        const SizedBox(height: 16),
                                        Text(
                                          l10n.loginPasswordRecoveryAdminHint,
                                          style: TextStyle(
                                            fontSize: 13,
                                            color: Colors.grey,
                                          ),
                                        ),
                                      ],
                                    ),
                                    actions: [
                                      TextButton(
                                        onPressed: () => Navigator.of(context).pop(),
                                        child: Text(l10n.commonOk),
                                      ),
                                    ],
                                  ),
                                ),
                                child: Text(
                                  l10n.loginForgotPassword,
                                ),
                              ),
                            ),

                            const SizedBox(height: 16),

                            // Authentication Method Info
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: Theme.of(context)
                                    .colorScheme
                                    .primaryContainer,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: <Widget>[
                                  Icon(
                                    Icons.info_outline,
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onPrimaryContainer,
                                    size: 16,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                  l10n.loginAuthMethodDefault,
                                    style: TextStyle(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .onPrimaryContainer,
                                      fontSize: 12,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    if (ConfigService().authRequired == false)
                      Center(
                        child: TextButton.icon(
                          onPressed: () {
                            context.go(AppRouter.homeRoute);
                          },
                          icon: const Icon(Icons.arrow_back),
                          label: Text(l10n.backToHome),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
    );
  }
}
