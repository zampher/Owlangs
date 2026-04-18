// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../l10n/app_localizations.dart';
import '../../../shared/services/config_service.dart';
import '../widgets/ldap_config_form.dart';
import '../widgets/ldap_test_dialog.dart';

/// User management mode: no login, LDAP, or local users (local = in development).
enum UserManagementMode {
  noLogin,
  ldap,
  local,
}

class UserManagementSettingsScreen extends ConsumerStatefulWidget {
  const UserManagementSettingsScreen({super.key});

  @override
  ConsumerState<UserManagementSettingsScreen> createState() =>
      _UserManagementSettingsScreenState();
}

class _UserManagementSettingsScreenState
    extends ConsumerState<UserManagementSettingsScreen> {
  bool _loading = true;
  bool _saving = false;
  UserManagementMode _selectedMode = UserManagementMode.noLogin;
  Map<String, dynamic> _ldapFormData = <String, dynamic>{};
  bool _ldapTestValidated = false;

  // Local users state (only used when in local user mode)
  bool _loadingLocalUsers = false;
  String? _localUsersError;
  List<Map<String, dynamic>> _localUsers = <Map<String, dynamic>>[];

  @override
  void initState() {
    super.initState();
    _loadMode();
  }

  Future<void> _loadMode() async {
    setState(() => _loading = true);
    final config = ConfigService();
    await config.loadAuthConfigOnce();
    final authRequired = config.authRequired ?? false;
    Map<String, dynamic> ldapData = <String, dynamic>{};
    bool ldapEnabled = false;
    try {
      final data = await config.getLdapConfig();
      if (data != null) {
        ldapData = Map<String, dynamic>.from(data);
        ldapEnabled = (data['ldap_enabled'] as bool?) ?? false;
      }
    } catch (_) {
      ldapEnabled = false;
    }
    UserManagementMode mode = UserManagementMode.noLogin;
    if (authRequired && ldapEnabled) {
      mode = UserManagementMode.ldap;
    } else if (authRequired && !ldapEnabled) {
      mode = UserManagementMode.local;
    }
    if (mounted) {
      setState(() {
        _selectedMode = mode;
        _ldapFormData = ldapData;
        _ldapTestValidated = mode == UserManagementMode.ldap && ldapEnabled;
        _loading = false;
      });
      if (mode == UserManagementMode.local) {
        _loadLocalUsers();
      }
    }
  }

  Future<void> _saveMode(UserManagementMode mode) async {
    final config = ConfigService();
    final l10n = AppLocalizations.of(context)!;
    // LDAP 模式由下方 LDAP 配置表单控制，这里只切换 UI 选中状态
    if (mode == UserManagementMode.ldap) {
      setState(() => _selectedMode = mode);
      return;
    }
    setState(() => _saving = true);
    try {
      if (mode == UserManagementMode.noLogin) {
        // 免登录：关闭 auth_required
        final ok = await config.updateSettingsBatch(
          'global',
          <String, dynamic>{'auth_required': false},
        );
        if (!ok) throw Exception('Batch update failed');
        await config.loadAuthConfigOnce();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(l10n.settingsUserManagementSaveSuccess)),
          );
          setState(() => _selectedMode = mode);
        }
      } else if (mode == UserManagementMode.local) {
        // 本地用户登录：开启 auth_required，且关闭 LDAP
        final ok = await config.updateSettingsBatch(
          'global',
          <String, dynamic>{'auth_required': true},
        );
        if (!ok) throw Exception('Batch update failed');

        final ldapOk = await config.saveLdapConfig(<String, dynamic>{
          'ldap_enabled': false,
        });
        if (!ldapOk) throw Exception('Failed to disable LDAP');

        await config.loadAuthConfigOnce();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(l10n.settingsUserManagementSaveSuccess)),
          );
          setState(() => _selectedMode = mode);
        }
        // 切到本地用户模式后，加载本地用户列表
        await _loadLocalUsers();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              l10n.settingsUserManagementSaveFailed(e.toString()),
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _loadLocalUsers() async {
    setState(() {
      _loadingLocalUsers = true;
      _localUsersError = null;
    });
    final config = ConfigService();
    try {
      final users = await config.listLocalUsers();
      if (!mounted) return;
      setState(() {
        _localUsers = users;
        _loadingLocalUsers = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _localUsersError = e.toString();
        _localUsers = <Map<String, dynamic>>[];
        _loadingLocalUsers = false;
      });
    }
  }

  Future<void> _showCreateOrEditLocalUserDialog({Map<String, dynamic>? user}) async {
    final bool isEdit = user != null;
    final TextEditingController usernameController =
        TextEditingController(text: user?['username']?.toString() ?? '');
    final TextEditingController displayNameController =
        TextEditingController(text: user?['display_name']?.toString() ?? '');
    final TextEditingController emailController =
        TextEditingController(text: user?['email']?.toString() ?? '');
    final TextEditingController passwordController = TextEditingController();
    String role = user?['role']?.toString() ?? 'user';

    final result = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        String? errorMessage;
        String? usernameError;
        String? passwordError;
        bool saving = false;

        return StatefulBuilder(
          builder: (BuildContext context, void Function(void Function()) setDialogState) {
            final Color errorBorderColor = Colors.orange.shade700;

            Future<void> onSave() async {
              final username = usernameController.text.trim();
              final displayName = displayNameController.text.trim();
              final email = emailController.text.trim();

              setDialogState(() {
                errorMessage = null;
                usernameError = null;
                passwordError = null;
              });

              if (username.isEmpty) {
                setDialogState(() {
                  usernameError = 'Username is required';
                  errorMessage = usernameError;
                });
                return;
              }

              if (!isEdit) {
                if (passwordController.text.isEmpty) {
                  setDialogState(() {
                    passwordError = 'Password is required';
                    errorMessage = passwordError;
                  });
                  return;
                }
              }

              setDialogState(() => saving = true);

              final config = ConfigService();
              try {
                bool ok = false;
                if (isEdit) {
                  ok = await config.updateLocalUser(
                    username: username,
                    role: role,
                    displayName: displayName.isEmpty ? null : displayName,
                    email: email.isEmpty ? null : email,
                  );
                } else {
                  ok = await config.createLocalUser(
                    username: username,
                    password: passwordController.text,
                    role: role,
                    displayName: displayName.isEmpty ? null : displayName,
                    email: email.isEmpty ? null : email,
                  );
                }
                if (!dialogContext.mounted) return;
                if (ok) {
                  Navigator.of(dialogContext).pop(true);
                  return;
                }
                setDialogState(() {
                  errorMessage = 'Operation failed (unknown error)';
                  saving = false;
                });
              } catch (e) {
                final String msg = e.toString();
                if (!dialogContext.mounted) return;
                final bool isPasswordError = msg.toLowerCase().contains('password') ||
                    msg.contains('8 character') ||
                    msg.contains('at least');
                setDialogState(() {
                  errorMessage = msg;
                  if (isPasswordError) passwordError = msg;
                  saving = false;
                });
              }
            }

            return AlertDialog(
              title: Text(isEdit ? 'Edit local user' : 'Add local user'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    if (errorMessage != null && errorMessage!.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(
                          errorMessage!,
                          style: TextStyle(
                            color: errorBorderColor,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    TextField(
                      controller: usernameController,
                      enabled: !isEdit,
                      decoration: InputDecoration(
                        labelText: 'Username',
                        errorText: usernameError,
                        errorBorder: usernameError != null
                            ? OutlineInputBorder(
                                borderSide: BorderSide(color: errorBorderColor),
                              )
                            : null,
                        focusedErrorBorder: usernameError != null
                            ? OutlineInputBorder(
                                borderSide: BorderSide(color: errorBorderColor, width: 2),
                              )
                            : null,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: displayNameController,
                      decoration: const InputDecoration(
                        labelText: 'Display name (optional)',
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: emailController,
                      decoration: const InputDecoration(
                        labelText: 'Email (optional)',
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: role,
                      items: const <DropdownMenuItem<String>>[
                        DropdownMenuItem<String>(
                          value: 'user',
                          child: Text('User'),
                        ),
                        DropdownMenuItem<String>(
                          value: 'admin',
                          child: Text('Admin'),
                        ),
                      ],
                      onChanged: (String? v) {
                        if (v != null) {
                          setDialogState(() => role = v);
                        }
                      },
                      decoration: const InputDecoration(
                        labelText: 'Role',
                      ),
                    ),
                    if (!isEdit) ...<Widget>[
                      const SizedBox(height: 12),
                      TextField(
                        controller: passwordController,
                        obscureText: true,
                        decoration: InputDecoration(
                          labelText: 'Password',
                          errorText: passwordError,
                          errorBorder: passwordError != null
                              ? OutlineInputBorder(
                                  borderSide: BorderSide(color: errorBorderColor),
                                )
                              : null,
                          focusedErrorBorder: passwordError != null
                              ? OutlineInputBorder(
                                  borderSide: BorderSide(color: errorBorderColor, width: 2),
                                )
                              : null,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: saving
                      ? null
                      : () => Navigator.of(dialogContext).pop(false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: saving ? null : onSave,
                  child: saving
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Save'),
                ),
              ],
            );
          },
        );
      },
    );

    if (result != true || !mounted) return;

    final l10n = AppLocalizations.of(context)!;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(l10n.settingsUserManagementSaveSuccess)),
    );
    await _loadLocalUsers();
  }

  Future<void> _resetLocalUserPassword(String username) async {
    final TextEditingController passwordController = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
          title: Text('Reset password: $username'),
          content: TextField(
            controller: passwordController,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'New password',
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Confirm'),
            ),
          ],
        ),
    );
    if (confirmed != true || passwordController.text.isEmpty) return;

    final config = ConfigService();
    final ok = await config.resetLocalUserPassword(
      username: username,
      newPassword: passwordController.text,
    );
    if (!mounted) return;
    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Password reset successfully')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to reset password')),
      );
    }
  }

  Future<void> _deleteLocalUser(String username) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
          title: Text('Delete user: $username'),
          content: const Text(
            'This action will permanently delete the user from local user store. This cannot be undone.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Delete'),
            ),
          ],
        ),
    );
    if (confirmed != true) return;

    final config = ConfigService();
    final ok = await config.deleteLocalUser(username);
    if (!mounted) return;
    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('User deleted')),
      );
      await _loadLocalUsers();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to delete user')),
      );
    }
  }

  Future<void> _testLdap() async {
    final config = ConfigService();
    final l10n = AppLocalizations.of(context)!;
    await showLdapTestDialog(context, onTest: (String username, String password) async {
      final payload = Map<String, dynamic>.from(_ldapFormData)
        ..['username'] = username
        ..['password'] = password;
      final result = await config.testLdap(payload);
      if (result['ok'] == true && result['test_validated'] == true) {
        if (mounted) setState(() => _ldapTestValidated = true);
        return null;
      }
      return result['message']?.toString() ?? l10n.settingsLdapTestFailed;
    },);
  }

  Future<void> _saveLdapConfig() async {
    final payload = Map<String, dynamic>.from(_ldapFormData);
    if (payload['ldap_enabled'] == true && !_ldapTestValidated) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.settingsLdapEnableRequireTest),
        ),
      );
      return;
    }
    if (payload['ldap_enabled'] == true) {
      payload['ldap_test_validated'] = true;
    }
    setState(() => _saving = true);
    final config = ConfigService();
    final l10n = AppLocalizations.of(context)!;
    try {
      await config.saveLdapConfig(payload);
      await config.updateSettingsBatch(
        'global',
        <String, dynamic>{'auth_required': true},
      );
      await config.loadAuthConfigOnce();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.settingsLdapConfigSaved)),
        );
      }
    } catch (e) {
      if (mounted) {
        String message = e.toString();
        if (e is DioException &&
            e.response?.data is Map<String, dynamic> &&
            (e.response!.data as Map<String, dynamic>)['message'] != null) {
          message = (e.response!.data as Map<String, dynamic>)['message'] as String;
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(l10n.settingsUserManagementSaveFailed(message)),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            l10n.settingsUserManagementTitle,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            l10n.settingsUserManagementSubtitle,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 24),
          RadioListTile<UserManagementMode>(
            value: UserManagementMode.noLogin,
            groupValue: _selectedMode,
            onChanged: _saving
                ? null
                : (UserManagementMode? v) {
                    if (v != null) {
                      setState(() => _selectedMode = v);
                      _saveMode(v);
                    }
                  },
            title: Text(l10n.settingsUserManagementModeNoLogin),
            subtitle: Text(l10n.settingsUserManagementModeNoLoginDesc),
          ),
          RadioListTile<UserManagementMode>(
            value: UserManagementMode.ldap,
            groupValue: _selectedMode,
            onChanged: _saving
                ? null
                : (UserManagementMode? v) {
                    if (v != null) _saveMode(v);
                  },
            title: Text(l10n.settingsUserManagementModeLdap),
            subtitle: Text(l10n.settingsUserManagementModeLdapDesc),
          ),
          if (_selectedMode == UserManagementMode.ldap) ...<Widget>[
            const SizedBox(height: 24),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: LdapConfigForm(
                  initialData: _ldapFormData,
                  onChanged: (Map<String, dynamic> payload) {
                    setState(() => _ldapFormData = payload);
                  },
                  ldapTestValidated: _ldapTestValidated,
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: <Widget>[
                FilledButton.tonal(
                  onPressed: _saving ? null : _testLdap,
                  child: Text(l10n.settingsLdapTestConnection),
                ),
                const SizedBox(width: 12),
                FilledButton(
                  onPressed: _saving ? null : _saveLdapConfig,
                  child: Text(l10n.settingsLdapSaveConfig),
                ),
              ],
            ),
          ],
          RadioListTile<UserManagementMode>(
            value: UserManagementMode.local,
            groupValue: _selectedMode,
            onChanged: _saving
                ? null
                : (UserManagementMode? v) {
                    if (v != null) _saveMode(v);
                  },
            title: Row(
              children: <Widget>[
                Text(l10n.settingsUserManagementModeLocal),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    l10n.settingsUserManagementInDevelopment,
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ),
              ],
            ),
            subtitle: Text(l10n.settingsUserManagementModeLocalDesc),
          ),
          if (_selectedMode == UserManagementMode.local) ...<Widget>[
            const SizedBox(height: 24),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: <Widget>[
                        Text(
                          'Local users',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        FilledButton.icon(
                          onPressed: _loadingLocalUsers
                              ? null
                              : _showCreateOrEditLocalUserDialog,
                          icon: const Icon(Icons.person_add),
                          label: const Text('Add user'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (_loadingLocalUsers)
                      const Center(child: CircularProgressIndicator())
                    else if (_localUsersError != null)
                      Text(
                        _localUsersError!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      )
                    else if (_localUsers.isEmpty)
                      Text(
                        'No local users found.',
                        style: Theme.of(context).textTheme.bodyMedium,
                      )
                    else
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: DataTable(
                          columns: const <DataColumn>[
                            DataColumn(
                              label: Text('Username'),
                            ),
                            DataColumn(
                              label: Text('Display name'),
                            ),
                            DataColumn(
                              label: Text('Email'),
                            ),
                            DataColumn(
                              label: Text('Role'),
                            ),
                            DataColumn(
                              label: Text(''),
                            ),
                          ],
                          rows: _localUsers.map((Map<String, dynamic> u) {
                            final username = u['username']?.toString() ?? '';
                            final displayName =
                                u['display_name']?.toString() ?? '';
                            final email = u['email']?.toString() ?? '';
                            final role = u['role']?.toString() ?? 'user';
                            final bool isSuperAdmin = username == 'admin';
                            return DataRow(
                              cells: <DataCell>[
                                DataCell(Text(username)),
                                DataCell(Text(displayName)),
                                DataCell(Text(email)),
                                DataCell(Text(role)),
                                DataCell(
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: <Widget>[
                                      if (!isSuperAdmin)
                                        IconButton(
                                          tooltip: 'Edit',
                                          icon: const Icon(Icons.edit),
                                          onPressed: () =>
                                              _showCreateOrEditLocalUserDialog(
                                            user: u,
                                          ),
                                        ),
                                      if (!isSuperAdmin)
                                        IconButton(
                                          tooltip: 'Reset password',
                                          icon: const Icon(Icons.lock_reset),
                                          onPressed: () =>
                                              _resetLocalUserPassword(username),
                                        ),
                                      if (!isSuperAdmin)
                                        IconButton(
                                          tooltip: 'Delete',
                                          icon: const Icon(Icons.delete),
                                          onPressed: () =>
                                              _deleteLocalUser(username),
                                        ),
                                    ],
                                  ),
                                ),
                              ],
                            );
                          }).toList(),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
