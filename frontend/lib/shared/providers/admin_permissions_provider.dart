// SPDX-FileCopyrightText: 2025 Owlangs
// SPDX-License-Identifier: MPL-2.0

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/app_config.dart';
import '../services/config_service.dart';
import 'auth_provider.dart';

/// Whether the current user can access admin-only UI (Settings, Setup Wizard, etc.).
/// Desktop: always true (no user management).
/// Web: requires a real login token and backend can_access_admin_settings.
/// (Passwordless mode still needs admin login for configuration.)
final FutureProvider<bool> canAccessAdminSettingsProvider =
    FutureProvider<bool>((FutureProviderRef<bool> ref) async {
  ref.watch(authProvider);
  if (!kIsWeb) return true;
  final config = ConfigService();
  final String? authHeader = config.authorizationHeader;
  // Without a session token, treat as non-admin even when auth_required=false
  // (backend may return a passwordless "local" user that is not admin).
  if (authHeader == null || authHeader.isEmpty) {
    return false;
  }
  final baseUrl = AppConfig.baseUrl;
  final dio = Dio(BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 10),
    headers: <String, dynamic>{
      'Content-Type': 'application/json',
      'Authorization': authHeader,
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

/// Backend reports ``is_admin`` or ``is_super_admin`` (queue purge, audit UI, etc.).
/// Unlike [canAccessAdminSettingsProvider], desktop does **not** default to true.
final FutureProvider<bool> isAppAdminUserProvider =
    FutureProvider<bool>((FutureProviderRef<bool> ref) async {
  ref.watch(authProvider);
  final ConfigService config = ConfigService();
  final String? authHeader = config.authorizationHeader;
  if (authHeader == null || authHeader.isEmpty) {
    return false;
  }
  final String baseUrl = AppConfig.baseUrl;
  final Dio dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      headers: <String, dynamic>{
        'Content-Type': 'application/json',
        'Authorization': authHeader,
        ...ConfigService.desktopBackendHeaders,
      },
    ),
  );
  try {
    final Response<Map<String, dynamic>> response =
        await dio.get<Map<String, dynamic>>(
      '/api/v1/auth/user/permissions',
    );
    if (response.statusCode == 200 &&
        response.data != null &&
        (response.data!['is_admin'] == true ||
            response.data!['is_super_admin'] == true)) {
      return true;
    }
  } catch (_) {
    // network / 401
  }
  return false;
});
