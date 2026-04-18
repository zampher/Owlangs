// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import '../../app/app_config.dart';
import 'config_service.dart';

/// Result of donor status from backend (activated, expired, trial, license edition/expiry).
class DonorStatus {
  const DonorStatus({
    required this.activated,
    required this.expired,
    this.machineId,
    this.licenseEdition,
    this.licenseExpiry,
    this.trialEndsAt,
    this.trialExpired = false,
    this.effectiveActivated = false,
    this.canCreateTranslationTask = true,
    this.deploymentEdition,
  });
  final bool activated;
  final bool expired;
  final String? machineId;
  /// Product type from decoded token: "PRO", "PRO-WEB", or null (legacy / year-only).
  final String? licenseEdition;
  /// Expiry date "YYYY-MM-DD" or null (no expiry).
  final String? licenseExpiry;
  /// Trial end date "YYYY-MM-DD" when not activated (15-day trial from first run).
  final String? trialEndsAt;
  /// True when trial period ended and not activated.
  final bool trialExpired;
  /// True when activated or within trial (effective Pro state).
  final bool effectiveActivated;
    /// False only for Web when trial expired and not activated (cannot create new translation tasks).
  final bool canCreateTranslationTask;
  /// Deployment type: "PRO" (desktop) or "PRO-WEB" (web). Used to show product name during trial.
  final String? deploymentEdition;
}

/// Service for managing donor activation status (machine-bound registration code).
/// Uses backend API; no plaintext activation codes stored.
class DonorActivationService {
  factory DonorActivationService() => _instance;
  DonorActivationService._internal();
  static final DonorActivationService _instance =
      DonorActivationService._internal();

  final ConfigService _configService = ConfigService();
  bool? _cachedActivatedStatus;
  String? _cachedMachineId;

  /// True when the last status fetch reported license expired (year-only code past validity).
  bool _cachedExpired = false;
  String? _cachedLicenseEdition;
  String? _cachedLicenseExpiry;
  String? _cachedTrialEndsAt;
  bool _cachedTrialExpired = false;
  bool _cachedEffectiveActivated = false;
  bool _cachedCanCreateTranslationTask = true;
  String? _cachedDeploymentEdition;
  final StreamController<bool> _activationStatusController =
      StreamController<bool>.broadcast();

  /// Stream of activation status changes
  Stream<bool> get activationStatusStream => _activationStatusController.stream;

  Dio _buildDio() {
    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        headers: <String, dynamic>{
          'Content-Type': 'application/json',
          if (_configService.authorizationHeader != null)
            'Authorization': _configService.authorizationHeader,
          ...ConfigService.desktopBackendHeaders,
        },
      ),
    );
    return dio;
  }

  /// Initialize the service and load status from backend
  Future<void> initialize() async {
    try {
      await _loadStatus();
    } catch (e) {
      if (kDebugMode) {
        print('DonorActivationService: Failed to initialize: $e');
      }
      _cachedActivatedStatus = false;
      _cachedMachineId = null;
    }
  }

  /// Load activation status from backend
  Future<void> _loadStatus() async {
    try {
      final dio = _buildDio();
      final response = await dio.get('/auth/donor/status');

      if (response.statusCode == 200 && response.data is Map<String, dynamic>) {
        final data = response.data as Map<String, dynamic>;
        _cachedActivatedStatus = data['activated'] as bool? ?? false;
        _cachedMachineId = data['machine_id'] as String?;
        _cachedExpired = data['expired'] as bool? ?? false;
        _cachedLicenseEdition = data['license_edition'] as String?;
        _cachedLicenseExpiry = data['license_expiry'] as String?;
        _cachedTrialEndsAt = data['trial_ends_at'] as String?;
        _cachedTrialExpired = data['trial_expired'] as bool? ?? false;
        _cachedEffectiveActivated = data['effective_activated'] as bool? ?? _cachedActivatedStatus ?? false;
        _cachedCanCreateTranslationTask = data['can_create_translation_task'] as bool? ?? true;
        _cachedDeploymentEdition = data['deployment_edition'] as String?;
      } else {
        _cachedActivatedStatus = false;
        _cachedMachineId = null;
        _cachedExpired = false;
        _cachedLicenseEdition = null;
        _cachedLicenseExpiry = null;
        _cachedTrialEndsAt = null;
        _cachedTrialExpired = false;
        _cachedEffectiveActivated = false;
        _cachedCanCreateTranslationTask = true;
        _cachedDeploymentEdition = null;
      }
    } catch (e) {
      if (kDebugMode) {
        print('DonorActivationService: Failed to load status: $e');
      }
      _cachedActivatedStatus = false;
      _cachedMachineId = null;
      _cachedExpired = false;
      _cachedLicenseEdition = null;
      _cachedLicenseExpiry = null;
      _cachedTrialEndsAt = null;
      _cachedTrialExpired = false;
      _cachedEffectiveActivated = false;
      _cachedCanCreateTranslationTask = true;
      _cachedDeploymentEdition = null;
    }
  }

  /// Whether the last status reported license expired (year-only code). Call after isActivated()/getStatus().
  bool get lastStatusExpired => _cachedExpired;

  /// Clear the expired flag so the expiry prompt is not shown again this session.
  void clearExpiredFlag() {
    _cachedExpired = false;
  }

  /// Get full donor status (activated, expired, trial, machineId). Prefer this when you need to show expiry message.
  Future<DonorStatus> getStatus() async {
    if (_cachedActivatedStatus == null || _cachedMachineId == null) {
      await _loadStatus();
    }
    return DonorStatus(
      activated: _cachedActivatedStatus ?? false,
      expired: _cachedExpired,
      machineId: _cachedMachineId,
      licenseEdition: _cachedLicenseEdition,
      licenseExpiry: _cachedLicenseExpiry,
      trialEndsAt: _cachedTrialEndsAt,
      trialExpired: _cachedTrialExpired,
      effectiveActivated: _cachedEffectiveActivated,
      canCreateTranslationTask: _cachedCanCreateTranslationTask,
      deploymentEdition: _cachedDeploymentEdition,
    );
  }

  /// Whether the deployment can create new translation tasks (false only for Web when trial expired and not activated).
  bool get canCreateTranslationTask => _cachedCanCreateTranslationTask;

  /// Check if donor is activated (license/code activated).
  Future<bool> isActivated() async {
    if (_cachedActivatedStatus == null) {
      await _loadStatus();
    }
    return _cachedActivatedStatus ?? false;
  }

  /// Whether Pro features (e.g. all file formats) are allowed: activated or within trial.
  /// Use this for format availability; use [isActivated] only when meaning license activation.
  Future<bool> isEffectiveActivated() async {
    if (_cachedActivatedStatus == null) {
      await _loadStatus();
    }
    return _cachedEffectiveActivated;
  }

  /// Get machine ID for this device (user sends this to author to receive registration code)
  Future<String?> getMachineId() async {
    if (_cachedMachineId == null) {
      await _loadStatus();
    }
    return _cachedMachineId;
  }

  /// Activate with registration code (machine-bound; no plaintext codes)
  Future<bool> activateWithCode(String code) async {
    if (code.trim().isEmpty) return false;
    try {
      final dio = _buildDio();
      final response = await dio.post(
        '/auth/donor/activate',
        data: <String, String>{'registration_code': code.trim()},
      );

      if (response.statusCode == 200) {
        await _loadStatus();
        _activationStatusController.add(true);
        return true;
      }
      return false;
    } catch (e) {
      if (kDebugMode) {
        print('DonorActivationService: Failed to activate: $e');
      }
      return false;
    }
  }

  /// Deactivate donor status (for testing or revocation)
  Future<void> deactivate() async {
    try {
      // Note: Backend doesn't have a deactivate endpoint yet
      // For now, just update local cache
      _cachedActivatedStatus = false;

      // Notify listeners
      _activationStatusController.add(false);
    } catch (e) {
      if (kDebugMode) {
        print('DonorActivationService: Failed to deactivate: $e');
      }
    }
  }

  /// Dispose resources
  void dispose() {
    _activationStatusController.close();
  }
}
