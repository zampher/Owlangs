// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../l10n/app_localizations.dart';

/// Dialog to test LDAP connection: username and password input.
/// [onTest] is called with credentials; return null on success, error message on failure.
/// Dialog closes on success; on failure shows the returned message.
Future<bool?> showLdapTestDialog(
  BuildContext context, {
  required Future<String?> Function(String username, String password) onTest,
}) => showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (context) => _LdapTestDialogBody(onTest: onTest),
  );

class _LdapTestDialogBody extends StatefulWidget {
  const _LdapTestDialogBody({required this.onTest});

  final Future<String?> Function(String username, String password) onTest;

  @override
  State<_LdapTestDialogBody> createState() => _LdapTestDialogBodyState();
}

class _LdapTestDialogBodyState extends State<_LdapTestDialogBody> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _loading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    if (username.isEmpty || password.isEmpty) {
      setState(() {
        _errorMessage = AppLocalizations.of(context)!.settingsLdapTestFailed;
      });
      return;
    }
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    final error = await widget.onTest(username, password);
    if (!mounted) return;
    setState(() => _loading = false);
    if (error != null) {
      setState(() => _errorMessage = error);
    } else {
      Navigator.of(context).pop(true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return AlertDialog(
      title: Text(l10n.settingsLdapTestDialogTitle),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            TextFormField(
              controller: _usernameController,
              decoration: InputDecoration(
                labelText: l10n.settingsLdapTestUsername,
                hintText: l10n.settingsLdapTestUsernamePlaceholder,
              ),
              enabled: !_loading,
              onFieldSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _passwordController,
              decoration: InputDecoration(
                labelText: l10n.settingsLdapTestPassword,
                hintText: l10n.settingsLdapTestPasswordPlaceholder,
              ),
              obscureText: true,
              enabled: !_loading,
              onFieldSubmitted: (_) => _submit(),
            ),
            if (_errorMessage != null) ...<Widget>[
              const SizedBox(height: 12),
              Text(
                _errorMessage!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
          ],
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: _loading ? null : () => Navigator.of(context).pop(false),
          child: Text(MaterialLocalizations.of(context).cancelButtonLabel),
        ),
        FilledButton(
          onPressed: _loading ? null : _submit,
          child: _loading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(l10n.settingsLdapTestStart),
        ),
      ],
    );
  }
}
