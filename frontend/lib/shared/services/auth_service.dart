import 'package:dio/dio.dart';
import '../models/user_model.dart';
import '../../features/auth/models/login_request.dart';
import 'config_service.dart';
import '../../app/app_config.dart';

class AuthService {
  AuthService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: _baseUrl,
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
        headers: <String, dynamic>{
          'Content-Type': 'application/json',
        },
      ),
    );

    // Add interceptors for error handling
    _dio.interceptors.add(
      InterceptorsWrapper(
        onError: (error, handler) {
          if (error.response?.statusCode == 401) {
            // Handle authentication errors
            throw AuthException('Invalid username or password');
          } else if (error.response?.statusCode == 429) {
            // Handle too many attempts
            throw AuthException(
              'Too many login attempts. Please try again later.',
            );
          } else if (error.response?.statusCode == 500) {
            // Handle server errors
            throw AuthException('Server error. Please try again later.');
          }
          handler.next(error);
        },
      ),
    );
  }
  static final String _baseUrl = AppConfig.baseUrl;
  late final Dio _dio;

  /// Login with username and password
  Future<LoginResponse> login(
    String username,
    String password, {
    bool rememberMe = false,
  }) async {
    try {
      // Send form data instead of JSON
      final formData = FormData.fromMap(<String, dynamic>{
        'username': username,
        'password': password,
        'remember_me': rememberMe.toString(),
      });

      final Response<dynamic> response =
          await _dio.post('/api/v1/auth/login', data: formData);

      if (response.statusCode == 200) {
        final data = response.data;
        if (data is! Map<String, dynamic>) {
          throw AuthException(
            'Invalid login response from server (expected JSON object)',
          );
        }
        final loginResponse = LoginResponse.fromJson(data);

        // Save token to Dio headers for future requests
        if (loginResponse.token != null && loginResponse.token!.isNotEmpty) {
          _dio.options.headers['Authorization'] =
              'Bearer ${loginResponse.token}';
          // Also set token for ConfigService
          ConfigService().setAuthToken(loginResponse.token);
        }

        return loginResponse;
      } else {
        throw AuthException('Login failed');
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        throw AuthException('Invalid username or password');
      } else if (e.response?.statusCode == 429) {
        throw AuthException('Too many login attempts. Please try again later.');
      } else {
        throw AuthException('Login failed: ${e.message}');
      }
    } on FormatException catch (e) {
      throw AuthException('Invalid login response: ${e.message}');
    } catch (e) {
      if (e is AuthException) rethrow;
      throw AuthException('Network error: ${e.toString()}');
    }
  }

  /// Logout current user
  Future<void> logout() async {
    try {
      await _dio.get('/logout');
    } catch (e) {
      // Ignore logout errors
      print('Logout error: $e');
    } finally {
      // Clear authorization header
      _dio.options.headers.remove('Authorization');
      // Also clear token for ConfigService
      ConfigService().setAuthToken(null);
    }
  }

  /// Get current user information
  Future<UserModel?> getCurrentUser() async {
    try {
      final Response<dynamic> response = await _dio.get('/api/v1/auth/user');

      if (response.statusCode == 200) {
        return UserModel.fromJson(response.data);
      }
    } catch (e) {
      // Silent error handling
    }
    return null;
  }

  /// Get user permissions
  Future<Map<String, dynamic>?> getUserPermissions() async {
    try {
      final Response<dynamic> response =
          await _dio.get('/api/v1/auth/user/permissions');
      if (response.statusCode == 200) {
        return response.data;
      }
    } catch (e) {
      // Silent error handling
    }
    return null;
  }

  /// Check if user is authenticated
  Future<bool> isAuthenticated() async {
    try {
      // 先检查本地是否有token，避免不必要的API请求
      if (_dio.options.headers['Authorization'] == null ||
          _dio.options.headers['Authorization']!.isEmpty) {
        return false;
      }

      final UserModel? user = await getCurrentUser();
      return user != null;
    } catch (e) {
      return false;
    }
  }
}

class AuthException implements Exception {
  AuthException(this.message);
  final String message;

  @override
  String toString() => message;
}
