class ApiError {
  ApiError({
    required this.code,
    required this.message,
    this.details,
    this.statusCode,
  });

  factory ApiError.fromJson(Map<String, dynamic> json) => ApiError(
        code: json['code'] ?? 'UNKNOWN_ERROR',
        message: json['message'] ?? 'An error occurred',
        details: json['details'],
        statusCode: json['statusCode'],
      );
  final String code;
  final String message;
  final String? details;
  final int? statusCode;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'code': code,
        'message': message,
        'details': details,
        'statusCode': statusCode,
      };

  @override
  String toString() =>
      'ApiError(code: $code, message: $message, details: $details, statusCode: $statusCode)';
}

class ValidationError {
  ValidationError({
    required this.field,
    required this.message,
  });

  factory ValidationError.fromJson(Map<String, dynamic> json) =>
      ValidationError(
        field: json['field'] ?? '',
        message: json['message'] ?? '',
      );
  final String field;
  final String message;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'field': field,
        'message': message,
      };

  @override
  String toString() => 'ValidationError(field: $field, message: $message)';
}
