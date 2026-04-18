import '../../../shared/models/user_model.dart';

class LoginRequest {
  LoginRequest({
    required this.username,
    required this.password,
    this.rememberMe = false,
  });
  final String username;
  final String password;
  final bool rememberMe;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'username': username,
        'password': password,
        'remember_me': rememberMe,
      };

  Map<String, dynamic> toFormData() => <String, dynamic>{
        'username': username,
        'password': password,
        'remember_me': rememberMe.toString(),
      };

  @override
  String toString() =>
      'LoginRequest(username: $username, rememberMe: $rememberMe)';
}

class LoginResponse {
  LoginResponse({
    this.token,
    this.user,
    this.message,
    this.success = false,
  });

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    try {
      final token = json['token'];
      final userJson = json['user'];

      UserModel? user;
      if (userJson != null) {
        user = UserModel.fromJson(userJson);
      }

      final message = json['message']?.toString() ?? '';
      final success = json['success'] ?? false;

      return LoginResponse(
        token: token,
        user: user,
        message: message,
        success: success,
      );
    } catch (e) {
      throw FormatException('Failed to parse LoginResponse: $e');
    }
  }
  final String? token;
  final UserModel? user;
  final String? message;
  final bool success;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'token': token,
        'user': user?.toJson(),
        'message': message,
        'success': success,
      };

  @override
  String toString() => 'LoginResponse(success: $success, message: $message)';
}
