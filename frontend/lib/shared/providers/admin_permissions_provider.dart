// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';

import '../services/config_service.dart';
import 'auth_provider.dart';
import '../../app/app_config.dart';

/// Whether the current user can access admin-only UI (Settings, Setup Wizard, etc.).
/// Desktop: always true (no user management). Web: from backend can_access_admin_settings.
final FutureProvider<bool> canAccessAdminSettingsProvider =
    FutureProvider<bool>((FutureProviderRef<bool> ref) async {
  ref.watch(authProvider);
  if (!kIsWeb) return true;
  final config = ConfigService();
  final baseUrl = AppConfig.baseUrl;
  final dio = Dio(BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 10),
    headers: <String, dynamic>{
      'Content-Type': 'application/json',
      if (config.authorizationHeader != null)
        'Authorization': config.authorizationHeader,
    },
  ),);
  try {
    final response = await dio.get<Map<String, dynamic>>(
      '/api/v1/auth/user/permissions',
    );
    if (response.statusCode == 200 &&
        response.data != null &&
        response.data!['can_access_admin_settings'] == true) {
      return true;
    }
  } catch (_) {
    // 401, network error, etc. -> treat as non-admin
  }
  return false;
});
