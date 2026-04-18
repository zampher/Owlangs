class ApiResponse<T> {
  ApiResponse({
    required this.code,
    required this.message,
    this.data,
    this.success = true,
  });

  factory ApiResponse.fromJson(Map<String, dynamic> json) => ApiResponse<T>(
        code: json['code'] ?? 0,
        message: json['message'] ?? '',
        data: json['data'],
        success: json['success'] ?? (json['code'] == 200),
      );
  final int code;
  final String message;
  final T? data;
  final bool success;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'code': code,
        'message': message,
        'data': data,
        'success': success,
      };

  bool get isSuccess => success && code == 200;
  bool get isError => !success || code != 200;
}
