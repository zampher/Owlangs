class UserModel {
  const UserModel({
    required this.id,
    required this.username,
    required this.email,
    required this.roles,
    required this.permissions,
    this.fullName,
    this.avatar,
    this.lastLogin,
    this.isActive = true,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    try {
      final id = json['id']?.toString() ?? '';
      final username = json['username']?.toString() ?? '';
      final email = json['email']?.toString() ?? '';
      final fullName = json['full_name']?.toString();
      final avatar = json['avatar']?.toString();
      final roles = List<String>.from(json['roles'] ?? <dynamic>[]);
      final permissions = List<String>.from(json['permissions'] ?? <dynamic>[]);
      final lastLogin = json['last_login'] != null
          ? DateTime.parse(json['last_login'].toString())
          : null;
      final isActive = json['is_active'] ?? true;

      return UserModel(
        id: id,
        username: username,
        email: email,
        fullName: fullName,
        avatar: avatar,
        roles: roles,
        permissions: permissions,
        lastLogin: lastLogin,
        isActive: isActive,
      );
    } catch (e) {
      throw FormatException('Failed to parse UserModel: $e');
    }
  }
  final String id;
  final String username;
  final String email;
  final String? fullName;
  final String? avatar;
  final List<String> roles;
  final List<String> permissions;
  final DateTime? lastLogin;
  final bool isActive;

  /// 获取主要角色（第一个角色）
  String get role => roles.isNotEmpty ? roles.first : 'user';

  Map<String, dynamic> toJson() => <String, dynamic>{
        'id': id,
        'username': username,
        'email': email,
        'full_name': fullName,
        'avatar': avatar,
        'roles': roles,
        'permissions': permissions,
        'last_login': lastLogin?.toIso8601String(),
        'is_active': isActive,
      };

  UserModel copyWith({
    String? id,
    String? username,
    String? email,
    String? fullName,
    String? avatar,
    List<String>? roles,
    List<String>? permissions,
    DateTime? lastLogin,
    bool? isActive,
  }) =>
      UserModel(
        id: id ?? this.id,
        username: username ?? this.username,
        email: email ?? this.email,
        fullName: fullName ?? this.fullName,
        avatar: avatar ?? this.avatar,
        roles: roles ?? this.roles,
        permissions: permissions ?? this.permissions,
        lastLogin: lastLogin ?? this.lastLogin,
        isActive: isActive ?? this.isActive,
      );

  @override
  String toString() =>
      'UserModel(id: $id, username: $username, email: $email, fullName: $fullName, roles: $roles)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is UserModel && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;
}
