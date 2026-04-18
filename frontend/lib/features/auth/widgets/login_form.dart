import 'package:flutter/material.dart';
import 'password_field.dart';

class LoginForm extends StatelessWidget {
  const LoginForm({
    required this.usernameController,
    required this.passwordController,
    required this.rememberMe,
    super.key,
    this.onRememberMeChanged,
    this.onLogin,
    this.isLoading = false,
  });
  final TextEditingController usernameController;
  final TextEditingController passwordController;
  final bool rememberMe;
  final ValueChanged<bool>? onRememberMeChanged;
  final VoidCallback? onLogin;
  final bool isLoading;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          // Username Field
          TextFormField(
            controller: usernameController,
            decoration: const InputDecoration(
              labelText: 'Username',
              hintText: 'Enter your username',
              prefixIcon: Icon(Icons.person),
              border: OutlineInputBorder(),
            ),
            textInputAction: TextInputAction.next,
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
          PasswordField(
            controller: passwordController,
            onFieldSubmitted: () {
              // Trigger login when Enter is pressed
              onLogin?.call();
            },
          ),

          const SizedBox(height: 16),

          // Remember Me Checkbox
          Row(
            children: <Widget>[
              Checkbox(
                value: rememberMe,
                onChanged: (value) => onRememberMeChanged?.call(value ?? false),
              ),
              const Text('Remember me'),
            ],
          ),

          const SizedBox(height: 24),

          // Login Button
          ElevatedButton(
            onPressed: isLoading ? null : onLogin,
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            child: isLoading
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: <Widget>[
                      Icon(Icons.login, size: 20),
                      SizedBox(width: 8),
                      Text('Login', style: TextStyle(fontSize: 16)),
                    ],
                  ),
          ),

          const SizedBox(height: 16),

          // Forgot Password Link
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: () {
                // TODO: Implement forgot password
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Password recovery feature coming soon!'),
                  ),
                );
              },
              child: const Text('Forgot Password?'),
            ),
          ),
        ],
      );
}
