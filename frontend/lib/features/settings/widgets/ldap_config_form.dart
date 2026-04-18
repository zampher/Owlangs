// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import '../../../l10n/app_localizations.dart';

/// LDAP config form (admin group only; no glossary group).
/// Notifies [onChanged] with full payload on any edit.
class LdapConfigForm extends StatefulWidget {
  const LdapConfigForm({
    required this.initialData, required this.onChanged, super.key,
    this.ldapTestValidated = false,
  });

  final Map<String, dynamic> initialData;
  final void Function(Map<String, dynamic> payload) onChanged;
  final bool ldapTestValidated;

  @override
  State<LdapConfigForm> createState() => _LdapConfigFormState();
}

class _LdapConfigFormState extends State<LdapConfigForm> {
  late final TextEditingController _hostController;
  late final TextEditingController _portController;
  late final TextEditingController _baseDnController;
  late final TextEditingController _bindDnController;
  late final TextEditingController _userFilterController;
  late final TextEditingController _adminGroupController;
  late final TextEditingController _groupBaseDnController;
  late final TextEditingController _tlsCacertfileController;

  bool _ldapEnabled = false;
  String _protocol = 'ldap';
  bool _adminGroupEnabled = false;
  bool _tlsVerify = true;

  static int _parsePort(v) {
    if (v == null) return 389;
    if (v is int) return v;
    final n = int.tryParse(v.toString());
    return n ?? 389;
  }

  static bool _parseBool(v) {
    if (v == null) return false;
    if (v is bool) return v;
    final s = v.toString().toLowerCase();
    return s == 'true' || s == '1' || s == 'yes' || s == 'on';
  }

  @override
  void initState() {
    super.initState();
    final d = widget.initialData;
    _ldapEnabled = _parseBool(d['ldap_enabled']);
    _protocol = (d['ldap_protocol']?.toString() ?? 'ldap').toLowerCase();
    if (_protocol != 'ldaps') _protocol = 'ldap';
    _adminGroupEnabled = _parseBool(d['ldap_admin_group_enabled']);
    _tlsVerify = _parseBool(d['ldap_tls_verify']);
    _hostController = TextEditingController(text: d['ldap_host']?.toString() ?? '');
    _portController = TextEditingController(text: (d['ldap_port'] ?? 389).toString());
    _baseDnController = TextEditingController(text: d['ldap_base_dn']?.toString() ?? '');
    _bindDnController = TextEditingController(text: d['ldap_bind_dn_template']?.toString() ?? '');
    _userFilterController = TextEditingController(text: d['ldap_user_filter']?.toString() ?? '');
    _adminGroupController = TextEditingController(text: d['ldap_admin_group']?.toString() ?? '');
    _groupBaseDnController = TextEditingController(text: d['ldap_group_base_dn']?.toString() ?? '');
    _tlsCacertfileController = TextEditingController(text: d['ldap_tls_cacertfile']?.toString() ?? '');
    // Defer notify to after build; avoid setState() in parent during build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _notify();
    });
  }

  @override
  void didUpdateWidget(covariant LdapConfigForm oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialData != widget.initialData) {
      final d = widget.initialData;
      _ldapEnabled = _parseBool(d['ldap_enabled']);
      _protocol = (d['ldap_protocol']?.toString() ?? 'ldap').toLowerCase();
      if (_protocol != 'ldaps') _protocol = 'ldap';
      _adminGroupEnabled = _parseBool(d['ldap_admin_group_enabled']);
      _tlsVerify = _parseBool(d['ldap_tls_verify']);
      _hostController.text = d['ldap_host']?.toString() ?? '';
      _portController.text = (d['ldap_port'] ?? 389).toString();
      _baseDnController.text = d['ldap_base_dn']?.toString() ?? '';
      _bindDnController.text = d['ldap_bind_dn_template']?.toString() ?? '';
      _userFilterController.text = d['ldap_user_filter']?.toString() ?? '';
      _adminGroupController.text = d['ldap_admin_group']?.toString() ?? '';
      _groupBaseDnController.text = d['ldap_group_base_dn']?.toString() ?? '';
      _tlsCacertfileController.text = d['ldap_tls_cacertfile']?.toString() ?? '';
    }
  }

  @override
  void dispose() {
    _hostController.dispose();
    _portController.dispose();
    _baseDnController.dispose();
    _bindDnController.dispose();
    _userFilterController.dispose();
    _adminGroupController.dispose();
    _groupBaseDnController.dispose();
    _tlsCacertfileController.dispose();
    super.dispose();
  }

  Map<String, dynamic> _buildPayload() {
    final port = _parsePort(int.tryParse(_portController.text.trim()));
    return <String, dynamic>{
      'ldap_enabled': _ldapEnabled,
      'ldap_protocol': _protocol,
      'ldap_host': _hostController.text.trim(),
      'ldap_port': port,
      'ldap_base_dn': _baseDnController.text.trim(),
      'ldap_bind_dn_template': _bindDnController.text.trim(),
      'ldap_user_filter': _userFilterController.text.trim(),
      'ldap_admin_group_enabled': _adminGroupEnabled,
      'ldap_admin_group': _adminGroupController.text.trim(),
      'ldap_group_base_dn': _groupBaseDnController.text.trim(),
      'ldap_tls_verify': _tlsVerify,
      'ldap_tls_cacertfile': _tlsCacertfileController.text.trim(),
    };
  }

  void _notify() {
    widget.onChanged(_buildPayload());
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final isLdaps = _protocol == 'ldaps';
    final canEnableLdap = widget.ldapTestValidated || _ldapEnabled;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        SwitchListTile(
          value: _ldapEnabled,
          onChanged: canEnableLdap
              ? (bool v) {
                  setState(() {
                    _ldapEnabled = v;
                    _notify();
                  });
                }
              : null,
          title: Text(l10n.settingsLdapEnabled),
          subtitle: canEnableLdap
              ? Text(
                  l10n.settingsLdapEnableHint,
                  style: Theme.of(context).textTheme.bodySmall,
                )
              : Text(
                  l10n.settingsLdapEnableRequireTest,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.error,
                      ),
                ),
        ),
        DropdownButtonFormField<String>(
          initialValue: _protocol,
          decoration: InputDecoration(
            labelText: l10n.settingsLdapProtocol,
          ),
          items: <DropdownMenuItem<String>>[
            DropdownMenuItem<String>(value: 'ldap', child: Text(l10n.settingsLdapProtocolLdap)),
            DropdownMenuItem<String>(value: 'ldaps', child: Text(l10n.settingsLdapProtocolLdaps)),
          ],
          onChanged: (String? v) {
            if (v == null) return;
            setState(() {
              _protocol = v;
              if (v == 'ldap' && _portController.text.trim().isEmpty) {
                _portController.text = '389';
              } else if (v == 'ldaps' && _portController.text == '389') {
                _portController.text = '636';
              }
              _notify();
            });
          },
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _hostController,
          decoration: InputDecoration(
            labelText: l10n.settingsLdapHost,
            hintText: l10n.settingsLdapHostPlaceholder,
          ),
          onChanged: (_) => _notify(),
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _portController,
          decoration: InputDecoration(
            labelText: l10n.settingsLdapPort,
            hintText: l10n.settingsLdapPortPlaceholder,
          ),
          keyboardType: TextInputType.number,
          onChanged: (_) => _notify(),
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _baseDnController,
          decoration: InputDecoration(
            labelText: l10n.settingsLdapBaseDn,
            hintText: l10n.settingsLdapBaseDnPlaceholder,
          ),
          onChanged: (_) => _notify(),
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _bindDnController,
          decoration: InputDecoration(
            labelText: l10n.settingsLdapBindDnTemplate,
            hintText: l10n.settingsLdapBindDnPlaceholder('{username}'),
          ),
          onChanged: (_) => _notify(),
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _userFilterController,
          decoration: InputDecoration(
            labelText: l10n.settingsLdapUserFilter,
            hintText: l10n.settingsLdapUserFilterPlaceholder('{username}'),
          ),
          onChanged: (_) => _notify(),
        ),
        const SizedBox(height: 16),
        SwitchListTile(
          value: _adminGroupEnabled,
          onChanged: (bool v) {
            setState(() {
              _adminGroupEnabled = v;
              _notify();
            });
          },
          title: Text(l10n.settingsLdapAdminGroupEnabled),
        ),
        TextFormField(
          controller: _adminGroupController,
          decoration: InputDecoration(
            labelText: l10n.settingsLdapAdminGroup,
            hintText: l10n.settingsLdapAdminGroupPlaceholder,
          ),
          onChanged: (_) => _notify(),
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _groupBaseDnController,
          decoration: InputDecoration(
            labelText: l10n.settingsLdapGroupBaseDn,
            hintText: l10n.settingsLdapGroupBaseDnPlaceholder,
          ),
          onChanged: (_) => _notify(),
        ),
        if (isLdaps) ...<Widget>[
          const SizedBox(height: 16),
          SwitchListTile(
            value: _tlsVerify,
            onChanged: (bool v) {
              setState(() {
                _tlsVerify = v;
                _notify();
              });
            },
            title: Text(l10n.settingsLdapTlsVerify),
          ),
          TextFormField(
            controller: _tlsCacertfileController,
            decoration: InputDecoration(
              labelText: l10n.settingsLdapTlsCacertfile,
              hintText: l10n.settingsLdapTlsCacertfilePlaceholder,
            ),
            onChanged: (_) => _notify(),
          ),
        ],
      ],
    );
  }
}
