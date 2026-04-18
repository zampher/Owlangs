import 'package:dio/dio.dart';
import 'package:logger/logger.dart';

import '../../app/app_config.dart';
import '../models/api_response.dart';
import '../models/error_model.dart';

class ApiService {
  factory ApiService() => _instance;
  ApiService._internal();
  static final ApiService _instance = ApiService._internal();

  late Dio _dio;
  final Logger _logger = Logger();

  void initialize() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.baseUrl,
        connectTimeout: AppConfig.requestTimeout,
        // Use normal timeout by default; long-running operations should explicitly set longRequestTimeout
        receiveTimeout: AppConfig
            .requestTimeout, // Changed from longRequestTimeout to requestTimeout
        headers: <String, dynamic>{
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    // Add interceptors
    // Remove noisy LogInterceptor; rely on concise custom logs below

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (RequestOptions options, RequestInterceptorHandler handler) {
          // Intentionally silent to reduce noise
          handler.next(options);
        },
        onResponse:
            (Response<dynamic> response, ResponseInterceptorHandler handler) {
          // Intentionally silent to reduce noise
          handler.next(response);
        },
        onError: (DioException error, ErrorInterceptorHandler handler) {
          // Log errors concisely
          _logger.e('Error: ${error.message}');
          handler.next(error);
        },
      ),
    );
  }

  // GET request
  Future<ApiResponse<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      final Response<dynamic> response = await _dio.get(
        path,
        queryParameters: queryParameters,
        options: options,
      );
      return ApiResponse<T>.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // POST request
  Future<ApiResponse<T>> post<T>(
    String path, {
    data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      final Response<dynamic> response = await _dio.post(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
      return ApiResponse<T>.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // PUT request
  Future<ApiResponse<T>> put<T>(
    String path, {
    data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      final Response<dynamic> response = await _dio.put(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
      return ApiResponse<T>.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // DELETE request
  Future<ApiResponse<T>> delete<T>(
    String path, {
    data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      final Response<dynamic> response = await _dio.delete(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
      return ApiResponse<T>.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // File upload
  Future<ApiResponse<T>> uploadFile<T>(
    String path,
    String filePath, {
    String fieldName = 'file',
    Map<String, dynamic>? additionalData,
    ProgressCallback? onSendProgress,
  }) async {
    try {
      final FormData formData = FormData.fromMap(<String, dynamic>{
        fieldName: await MultipartFile.fromFile(filePath),
        ...?additionalData,
      });

      final Response<dynamic> response = await _dio.post(
        path,
        data: formData,
        onSendProgress: onSendProgress,
        options: Options(
          headers: <String, dynamic>{
            'Content-Type': 'multipart/form-data',
          },
          receiveTimeout: AppConfig.longRequestTimeout,
          sendTimeout: AppConfig.longRequestTimeout,
        ),
      );
      return ApiResponse<T>.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // Error handling
  ApiError _handleDioError(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return ApiError(
          code: 'TIMEOUT',
          message: 'Connection timeout. Please check your network connection.',
        );
      case DioExceptionType.badResponse:
        return ApiError(
          code: error.response?.statusCode.toString() ?? 'UNKNOWN',
          message: error.response?.data?['message'] ?? 'Server error occurred.',
        );
      case DioExceptionType.cancel:
        return ApiError(
          code: 'CANCELLED',
          message: 'Request was cancelled.',
        );
      default:
        return ApiError(
          code: 'NETWORK_ERROR',
          message: 'Network error occurred. Please try again.',
        );
    }
  }
}
