# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

try:
    from .config import AuthConfig
except Exception as e:
    print(f"❌ AUTH __init__.py: AuthConfig import failed: {e}")

try:
    from .ldap_client import LDAPClient
except Exception as e:
    print(f"❌ AUTH __init__.py: LDAPClient import failed: {e}")

try:
    from .session_manager import AuthSessionManager
except Exception as e:
    print(f"❌ AUTH __init__.py: AuthSessionManager import failed: {e}")

try:
    from .middleware import AuthMiddleware
except Exception as e:
    print(f"❌ AUTH __init__.py: AuthMiddleware import failed: {e}")

try:
    from .routes import auth_router, auth_compat_router, init_auth, get_session_manager, get_auth_config
except Exception as e:
    print(f"❌ AUTH __init__.py: routes import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    from .models import LoginRequest, User
except Exception as e:
    print(f"❌ AUTH __init__.py: models import failed: {e}")

try:
    from .user_profile import UserProfile, UserProfileManager, get_user_profile_manager
except Exception as e:
    print(f"❌ AUTH __init__.py: user_profile import failed: {e}")

__all__ = [
    "AuthConfig",
    "LDAPClient", 
    "AuthSessionManager",
    "AuthMiddleware",
    "auth_router",
    "auth_compat_router",
    "init_auth",
    "get_session_manager",
    "get_auth_config",
    "LoginRequest",
    "User",
    "UserProfile",
    "UserProfileManager",
    "get_user_profile_manager"
]

# Optional helpers
try:
    from .mineru_service import test_mineru_connectivity  # type: ignore
    __all__.append("test_mineru_connectivity")
except Exception:
    pass