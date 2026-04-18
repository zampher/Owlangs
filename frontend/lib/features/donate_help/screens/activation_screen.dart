// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../shared/utils/message_service.dart';
import '../../../shared/services/donor_activation_service.dart';

const String _kDocUrl = 'https://www.owlangs.org';

/// Dedicated activation screen for Pro / Team licenses.
/// Separated from donation channels to better serve purchased users.
@Deprecated(
  'OpenSource branch hides activation entry. Keep this screen only for potential future migration.',
)
class ActivationScreen extends StatefulWidget {
  const ActivationScreen({super.key});

  @override
  State<ActivationScreen> createState() => _ActivationScreenState();
}

class _ActivationScreenState extends State<ActivationScreen> {
  final TextEditingController _activationCodeController =
      TextEditingController();

  @override
  void dispose() {
    _activationCodeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Text(
                'Activation',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: colorScheme.primary,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                'Enter your registration code here to activate Pro / Team edition. '
                'If you purchased a license, you can ignore donation channels and use this page directly.',
                style: TextStyle(
                  fontSize: 13,
                  color: colorScheme.onSurfaceVariant,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 24),
              _buildCurrentLicenseCard(context),
              const SizedBox(height: 16),
              _buildMachineIdCard(context),
              const SizedBox(height: 16),
              _buildActivationForm(context),
            ],
          ),
        ),
      ),
    );
  }

  /// Label for license edition: Standard / Professional / Enterprise.
  static String _editionLabel(String? edition) {
    // OpenSource edition: do not distinguish Web Enterprise / Pro-Web.
    return kIsWeb ? 'Web' : 'Desktop';
  }

  /// Compute remaining trial days from ISO date string (YYYY-MM-DD).
  /// Returns null when date is invalid or missing; returns 0 when trial has ended.
  static int? _trialDaysRemaining(String? trialEndsAtIso) {
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

  Widget _buildCurrentLicenseCard(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  Icons.verified_user,
                  color: colorScheme.primary,
                  size: 24,
                ),
                const SizedBox(width: 8),
                Text(
                  'Current License',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            FutureBuilder<DonorStatus>(
              future: DonorActivationService().getStatus(),
              builder:
                  (BuildContext context, AsyncSnapshot<DonorStatus> snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return Text(
                    'Loading...',
                    style: TextStyle(
                      fontSize: 13,
                      color: colorScheme.onSurfaceVariant,
                    ),
                  );
                }
                final status = snapshot.data;
                if (status == null || !status.effectiveActivated) {
                  final bool trialExpired = status?.trialExpired ?? false;
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        trialExpired
                            ? 'Trial expired. Web features now run in standard mode. '
                                'If you have an Enterprise license code, please enter it in the desktop application.'
                            : 'No active license. Enter a registration code below to activate.',
                        style: TextStyle(
                          fontSize: 13,
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                      if (trialExpired)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Text(
                            'Professional trial has expired. The current effective edition is Standard (desktop), and desktop standard features remain available.',
                            style: TextStyle(
                              fontSize: 13,
                              color: colorScheme.onSurfaceVariant,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                    ],
                  );
                }
                final List<String> lines = <String>[
                  if (status.expired) 'Status: Expired' else 'Status: Active',
                  'Product: ${_editionLabel(status.licenseEdition ?? status.deploymentEdition)}',
                  if (!status.activated &&
                      status.trialEndsAt != null &&
                      status.trialEndsAt!.isNotEmpty)
                    'Trial ends: ${status.trialEndsAt}'
                  else if (status.licenseExpiry != null &&
                      status.licenseExpiry!.isNotEmpty)
                    'Expires: ${status.licenseExpiry}'
                  else
                    'Expires: No expiry',
                ];
                final int? daysRemaining =
                    _trialDaysRemaining(status.trialEndsAt);
                if (!status.activated &&
                    !status.trialExpired &&
                    daysRemaining != null &&
                    daysRemaining > 0) {
                  lines.add(
                    'Professional Trial remaining: $daysRemaining day${daysRemaining > 1 ? 's' : ''}',
                  );
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: lines
                      .map<Widget>(
                        (String line) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: SelectableText(
                            line,
                            style: TextStyle(
                              fontSize: 13,
                              color: colorScheme.onSurfaceVariant,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ),
                      )
                      .toList(),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMachineIdCard(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  Icons.computer,
                  color: colorScheme.primary,
                  size: 24,
                ),
                const SizedBox(width: 8),
                Text(
                  'Machine ID',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Send this Machine ID to Zampher or the sales channel after purchasing to receive a registration code.',
              style: TextStyle(
                fontSize: 13,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            FutureBuilder<String?>(
              future: DonorActivationService().getMachineId(),
              builder: (BuildContext context, AsyncSnapshot<String?> snapshot) {
                final String? machineId = snapshot.data;
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Expanded(
                      child: SelectableText(
                        machineId ??
                            (snapshot.connectionState == ConnectionState.waiting
                                ? 'Loading...'
                                : '—'),
                        style: TextStyle(
                          fontSize: 14,
                          fontFamily: 'monospace',
                          color: colorScheme.primary,
                        ),
                      ),
                    ),
                    if (machineId != null && machineId.isNotEmpty)
                      IconButton(
                        icon: const Icon(Icons.copy),
                        tooltip: 'Copy Machine ID',
                        onPressed: () async {
                          await Clipboard.setData(
                            ClipboardData(text: machineId),
                          );
                          if (!mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Machine ID copied to clipboard'),
                              duration: Duration(seconds: 2),
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        },
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActivationForm(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  Icons.vpn_key,
                  color: colorScheme.primary,
                  size: 24,
                ),
                const SizedBox(width: 8),
                Text(
                  'Registration Code',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Already have a registration code? Enter it below to activate.',
              style: TextStyle(
                fontSize: 13,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              children: <Widget>[
                Text(
                  'Need help? Visit ',
                  style: TextStyle(
                    fontSize: 12,
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
                MouseRegion(
                  cursor: SystemMouseCursors.click,
                  child: GestureDetector(
                    onTap: () async {
                      final Uri uri = Uri.parse(_kDocUrl);
                      if (await canLaunchUrl(uri)) {
                        await launchUrl(
                          uri,
                          mode: LaunchMode.externalApplication,
                        );
                      }
                    },
                    child: Text(
                      'www.owlangs.org',
                      style: TextStyle(
                        fontSize: 12,
                        color: colorScheme.primary,
                        decoration: TextDecoration.underline,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ),
                Text(
                  ' for documentation and contact information.',
                  style: TextStyle(
                    fontSize: 12,
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _activationCodeController,
              decoration: const InputDecoration(
                hintText: 'Enter registration code',
                border: OutlineInputBorder(),
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                isDense: true,
              ),
              autocorrect: false,
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton.icon(
                onPressed: _submitActivationCode,
                icon: const Icon(Icons.check_circle_outline, size: 18),
                label: const Text('Activate'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submitActivationCode() async {
    final String code = _activationCodeController.text.trim();
    if (code.isEmpty) {
      MessageService.showWarning(
        context,
        'Please enter a registration code.',
      );
      return;
    }
    try {
      final DonorActivationService donorService = DonorActivationService();
      final bool success = await donorService.activateWithCode(code);
      if (!mounted) return;
      if (success) {
        MessageService.showSuccess(
          context,
          'Pro benefits activated. Thank you for your support!',
        );
        _activationCodeController.clear();
        setState(() {});
      } else {
        MessageService.showWarning(
          context,
          'Invalid registration code or wrong machine. Please check and try again.',
        );
      }
    } catch (e) {
      if (!mounted) return;
      MessageService.showError(
        context,
        'Failed to save activation. Please try again.',
      );
    }
  }
}
