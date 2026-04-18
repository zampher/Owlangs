import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../shared/models/user_model.dart';
import '../../../shared/providers/auth_provider.dart';
import '../../../shared/services/config_service.dart';
import '../../../app/app_router.dart';

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
                label: 'Copy',
                textColor: Colors.white,
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: message));
                  // Use maybeOf to avoid using deactivated context (e.g. after redirect to home)
                  final m = ScaffoldMessenger.maybeOf(context);
                  m?.showSnackBar(
                    const SnackBar(
                      content: Text('Error message copied to clipboard'),
                      duration: Duration(seconds: 2),
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
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              Color(0xFF1e3c72),
              Color(0xFF2a5298),
            ],
          ),
        ),
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Card(
              elevation: 8,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(15),
              ),
              child: Container(
                width: 400,
                padding: const EdgeInsets.all(32),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(15),
                  // Use a near-white background so dark text has good contrast
                  color: Colors.white.withOpacity(0.96),
                  border: Border.all(
                    color: Colors.black.withOpacity(0.06),
                  ),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    // Logo and Title
                    Column(
                      children: <Widget>[
                        Image.asset(
                          'images/favicon.ico',
                          width: 48,
                          height: 48,
                          errorBuilder: (
                            context,
                            error,
                            stackTrace,
                          ) =>
                              const Icon(
                            Icons.translate,
                            size: 48,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 16),
                        const Text(
                          'Owlangs Translation\n File Format Conversion',
                          style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                            // Use brand-like deep blue for strong contrast on light card
                            color: Color(0xFF1e3c72),
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Document Translation System',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.black87,
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
                                labelText: 'Username',
                                hintText: 'Please enter username',
                                prefixIcon: const Icon(
                                  Icons.person,
                                  color: Colors.black54,
                                ),
                                filled: true,
                                fillColor: Colors.white.withOpacity(0.9),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide(
                                    color: Colors.grey.withOpacity(0.3),
                                  ),
                                ),
                                enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide(
                                    color: Colors.grey.withOpacity(0.3),
                                  ),
                                ),
                                focusedBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: const BorderSide(
                                    color: Color(0xFF0d6efd),
                                    width: 2,
                                  ),
                                ),
                                labelStyle:
                                    const TextStyle(color: Colors.black87),
                                hintStyle: TextStyle(
                                  color: Colors.black.withOpacity(0.6),
                                ),
                              ),
                              style: const TextStyle(color: Colors.black87),
                              validator: (value) {
                                if (value == null || value.isEmpty) {
                                  return 'Please enter your username';
                                }
                                if (value.length < 3) {
                                  return 'Username must be at least 3 characters';
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
                                labelText: 'Password',
                                hintText: 'Please enter password',
                                prefixIcon: const Icon(
                                  Icons.lock,
                                  color: Colors.black54,
                                ),
                                suffixIcon: IconButton(
                                  icon: Icon(
                                    _obscurePassword
                                        ? Icons.visibility_off
                                        : Icons.visibility,
                                    color: Colors.black54,
                                  ),
                                  onPressed: _togglePasswordVisibility,
                                ),
                                filled: true,
                                fillColor: Colors.white.withOpacity(0.9),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide(
                                    color: Colors.grey.withOpacity(0.3),
                                  ),
                                ),
                                enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide(
                                    color: Colors.grey.withOpacity(0.3),
                                  ),
                                ),
                                focusedBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: const BorderSide(
                                    color: Color(0xFF0d6efd),
                                    width: 2,
                                  ),
                                ),
                                labelStyle:
                                    const TextStyle(color: Colors.black87),
                                hintStyle: TextStyle(
                                  color: Colors.black.withOpacity(0.6),
                                ),
                              ),
                              style: const TextStyle(color: Colors.black87),
                              validator: (value) {
                                if (value == null || value.isEmpty) {
                                  return 'Please enter your password';
                                }
                                return null;
                              },
                              onFieldSubmitted: (_) => _handleLogin(),
                            ),

                            const SizedBox(height: 24),

                            // Login Button
                            ElevatedButton(
                              onPressed: authState.maybeWhen(
                                loading: () => null,
                                orElse: () => _handleLogin,
                              ),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF0d6efd),
                                foregroundColor: Colors.white,
                                padding:
                                    const EdgeInsets.symmetric(vertical: 16),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                elevation: 2,
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
                                  : const Row(
                                      mainAxisAlignment:
                                          MainAxisAlignment.center,
                                      children: <Widget>[
                                        Icon(Icons.login, size: 20),
                                        SizedBox(width: 8),
                                        Text(
                                          'Login',
                                          style: TextStyle(fontSize: 16),
                                        ),
                                      ],
                                    ),
                            ),

                            const SizedBox(height: 16),

                            // Forgot Password Link
                            Center(
                              child: TextButton(
                                onPressed: () {
                                  // TODO: Implement forgot password
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text(
                                        'Password recovery feature coming soon!',
                                      ),
                                    ),
                                  );
                                },
                                child: Text(
                                  'Forgot Password?',
                                  style: TextStyle(
                                    color: Colors.black.withOpacity(0.8),
                                    fontSize: 14,
                                  ),
                                ),
                              ),
                            ),

                            const SizedBox(height: 16),

                            // Authentication Method Info
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: Colors.white.withOpacity(0.9),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: <Widget>[
                                  Icon(
                                    Icons.info_outline,
                                    color: Colors.black.withOpacity(0.7),
                                    size: 16,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'Using Default Authentication',
                                    style: TextStyle(
                                      color: Colors.black.withOpacity(0.7),
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
                          label: const Text('Back to Home'),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
