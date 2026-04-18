import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart'
    show kIsWeb, defaultTargetPlatform, TargetPlatform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import '../../features/auth/models/login_request.dart';
import '../models/user_model.dart';
import '../services/auth_service.dart';

part 'auth_provider.freezed.dart';

@freezed
class AuthState with _$AuthState {
  const factory AuthState.initial() = _Initial;
  const factory AuthState.loading() = _Loading;
  const factory AuthState.authenticated(UserModel user) = _Authenticated;
  const factory AuthState.unauthenticated() = _Unauthenticated;
  const factory AuthState.error(String message) = _Error;
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._authService) : super(const AuthState.initial()) {
    print('🔍 [DEBUG] AuthNotifier initialized with initial state');
    // On desktop platforms, check auth immediately; on web, delay to avoid blocking startup
    if (!kIsWeb) {
      // Check if running on desktop platform using Flutter's defaultTargetPlatform
      final bool isDesktop = defaultTargetPlatform == TargetPlatform.windows ||
          defaultTargetPlatform == TargetPlatform.linux ||
          defaultTargetPlatform == TargetPlatform.macOS;

      if (isDesktop) {
        // Desktop: check immediately - start async check without waiting
        print(
          '🔍 [DEBUG] Desktop platform detected, checking auth immediately...',
        );
        // Use unawaited to start the check without blocking constructor
        _checkAuthStatus();
      } else {
        // Mobile: delay to avoid blocking startup
        _delayedAuthCheck();
      }
    } else {
      // Web: delay to avoid blocking startup
      _delayedAuthCheck();
    }
  }
  final AuthService _authService;

  void _delayedAuthCheck() {
    print('🔍 [DEBUG] Starting delayed auth check in 500ms...');
    // 延迟500ms后检查认证状态，给应用足够时间初始化
    Future.delayed(const Duration(milliseconds: 500), () {
      print(
        '🔍 [DEBUG] Delayed auth check triggered, current state: ${state.runtimeType}',
      );
      if (state is _Initial) {
        print('🔍 [DEBUG] State is still initial, proceeding with auth check');
        _checkAuthStatus();
      } else {
        print('🔍 [DEBUG] State is no longer initial, skipping auth check');
      }
    });
  }

  Future<void> _checkAuthStatus() async {
    print('🔍 [DEBUG] Starting auth status check...');
    try {
      final isAuthenticated = await _authService.isAuthenticated();
      print('🔍 [DEBUG] Auth check result: isAuthenticated = $isAuthenticated');
      if (isAuthenticated) {
        final user = await _authService.getCurrentUser();
        print('🔍 [DEBUG] Current user: ${user?.username ?? 'null'}');
        if (user != null) {
          state = AuthState.authenticated(user);
          print('🔍 [DEBUG] State updated to authenticated');
        } else {
          state = const AuthState.unauthenticated();
          print('🔍 [DEBUG] State updated to unauthenticated (no user)');
        }
      } else {
        state = const AuthState.unauthenticated();
        print(
          '🔍 [DEBUG] State updated to unauthenticated (not authenticated)',
        );
      }
    } catch (e) {
      // 静默失败，不显示错误信息
      print('🔍 [DEBUG] Auth check failed silently: $e');
      state = const AuthState.unauthenticated();
    }
  }

  Future<void> login(
    String username,
    String password, {
    bool rememberMe = false,
  }) async {
    String normalizeLoginError(String raw) {
      final trimmed = raw.trim();
      if (trimmed.isEmpty) {
        return 'Login failed. Please check your username or password.';
      }
      final lower = trimmed.toLowerCase();
      if (lower == 'null' || lower == 'login failed: null') {
        return 'Login failed. Please check your username or password.';
      }
      if (trimmed.contains('Instance of')) {
        return 'Login failed due to an unexpected error. Please try again later.';
      }
      return trimmed;
    }

    state = const AuthState.loading();

    try {
      final response =
          await _authService.login(username, password, rememberMe: rememberMe);

      if (response.success) {
        // If we have user info in response, use it directly
        if (response.user != null) {
          state = AuthState.authenticated(response.user!);
        } else if (response.token != null && response.token!.isNotEmpty) {
          // If we have a token but no user info, try to get current user info
          final user = await _authService.getCurrentUser();
          if (user != null) {
            state = AuthState.authenticated(user);
          } else {
            state = const AuthState.error(
              'Failed to get user information after login',
            );
          }
        } else {
          state = const AuthState.error(
            'Login successful but no user information available',
          );
        }
      } else {
        const fallbackMessage =
            'Login failed. Please check your username or password.';
        final raw = response.message;
        final normalized = raw == null || raw.trim().isEmpty
            ? fallbackMessage
            : normalizeLoginError(raw);
        state = AuthState.error(normalized);
      }
    } on AuthException catch (e) {
      final normalized = normalizeLoginError(e.message);
      state = AuthState.error(normalized);
    } catch (e) {
      final raw = e.toString();
      final hasUsefulDetail =
          raw.isNotEmpty && raw.toLowerCase() != 'null' && !raw.contains('Instance of');
      final base = hasUsefulDetail
          ? 'Login failed: $raw'
          : 'Login failed due to an unexpected error. Please try again later.';
      state = AuthState.error(normalizeLoginError(base));
    }
  }

  Future<void> logout() async {
    try {
      await _authService.logout();
    } catch (e) {
      // Ignore logout errors
    } finally {
      state = const AuthState.unauthenticated();
    }
  }

  void clearError() {
    if (state is _Error) {
      state = const AuthState.unauthenticated();
    }
  }
}

final Provider<AuthService> authServiceProvider =
    Provider<AuthService>((ref) => AuthService());

final StateNotifierProvider<AuthNotifier, AuthState> authProvider =
    StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final authService = ref.watch(authServiceProvider);
  return AuthNotifier(authService);
});
