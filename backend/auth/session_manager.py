# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import json
import os
import time
import uuid
from typing import Optional, Dict, Any
import redis
from fastapi import Request, Response

# In-memory session storage as fallback
_memory_sessions = {}

from .config import AuthConfig
from .models import User
from backend.utils.redis_manager import get_redis_client
from logger import unified_logger, LogModule


class AuthSessionManager:
    """Session manager"""
    
    _log_once_cache = set()
    
    def __init__(self, config: AuthConfig):
        self.config = config
        self.redis_client = None
        self._last_created_session_id = None
        self._init_redis_client()
    
    @classmethod
    def _log_once(cls, key: str, level: str, message: str):
        if key in cls._log_once_cache:
            return
        cls._log_once_cache.add(key)
        getattr(unified_logger, level)(LogModule.SYSTEM, message)
    
    @staticmethod
    def _log(level: str, message: str):
        getattr(unified_logger, level)(LogModule.SYSTEM, message)
    
    def _init_redis_client(self):
        """Initialize Redis client"""
        # Check if Redis is disabled via environment variable
        redis_enabled = os.getenv("REDIS_ENABLED", "true").lower()
        if redis_enabled in ["false", "0", "no", "off"]:
            self._log_once(
                "redis_disabled_warn",
                "warning",
                "Redis is disabled via REDIS_ENABLED environment variable",
            )
            self._log_once(
                "redis_disabled_info",
                "info",
                "Session management will be unavailable (Redis disabled)",
            )
            return
        
        try:
            # First try to use local Redis manager
            self.redis_client = get_redis_client()
            if self.redis_client:
                self._log_once(
                    "redis_local_session",
                    "info",
                    "Using local Redis service for session management",
                )
                return
        except Exception as e:
            self._log(
                "warning",
                f"Local Redis startup failed: {e}",
            )
        
        # If local Redis is unavailable, try connecting to external Redis
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # Test connection
            self.redis_client.ping()
            self._log_once(
                "redis_external_session",
                "info",
                "Using external Redis service for session management",
            )
        except Exception as e:
            self._log("error", f"Redis connection failed: {e}")
            self._log_once(
                "redis_unavailable",
                "warning",
                "Session management will be unavailable, please check Redis service",
            )
            self.redis_client = None
    
    def create_session_id(self) -> str:
        """Create session ID"""
        return str(uuid.uuid4())
    
    def set_session_cookie(self, response: Response, session_id: str):
        """Set session cookie"""
        response.set_cookie(
            key=self.config.session_cookie_name,
            value=session_id,
            max_age=self.config.session_max_age,
            httponly=True,
            samesite="lax",
            secure=False  # Set to False for development, should be True for production
        )
    
    def get_session_id(self, request: Request) -> Optional[str]:
        """Get session ID from request"""
        return request.cookies.get(self.config.session_cookie_name)
    
    def clear_session_cookie(self, response: Response):
        """Clear session cookie"""
        response.delete_cookie(
            key=self.config.session_cookie_name,
            httponly=True,
            samesite="lax"
        )
    
    async def create_session(self, request: Request, response: Response, user: User) -> str:
        """Create user session"""
        session_id = self.create_session_id()
        
        # Store user information
        user_data = {
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "is_authenticated": user.is_authenticated,
            "role": user.role.value,  # Save user role
            "created_at": time.time()
        }
        
        # Try Redis first
        if self.redis_client:
            try:
                self.redis_client.setex(
                    f"session:{session_id}",
                    self.config.session_max_age,
                    json.dumps(user_data)
                )
                self._log(
                    "debug",
                    f"Session stored to Redis: {session_id}",
                )
            except Exception as e:
                self._log(
                    "warning",
                    f"Failed to store session to Redis: {e}",
                )
                # Fallback to in-memory storage
                _memory_sessions[session_id] = user_data
                self._log(
                    "debug",
                    f"Using in-memory session storage: {session_id}",
                )
        else:
            # Redis not available, use in-memory storage
            _memory_sessions[session_id] = user_data
            self._log(
                "debug",
                f"Using in-memory session storage: {session_id}",
            )
        
        # Set Cookie
        self.set_session_cookie(response, session_id)
        
        # Store the session ID for API access
        self._last_created_session_id = session_id
        
        return session_id
    
    
    async def destroy_session(self, request: Request, response: Response) -> bool:
        """Destroy user session"""
        session_id = self.get_session_id(request)
        if not session_id:
            return False
        
        # Delete session data from Redis
        if self.redis_client:
            try:
                self.redis_client.delete(f"session:{session_id}")
            except Exception as e:
                self._log(
                    "warning",
                    f"Failed to delete session from Redis: {e}",
                )
        
        # Delete from in-memory storage
        if session_id in _memory_sessions:
            del _memory_sessions[session_id]
            self._log(
                "debug",
                f"Removed in-memory session: {session_id}",
            )
        
        # Clear Cookie
        self.clear_session_cookie(response)
        
        return True
    
    async def get_user(self, request: Request) -> Optional[User]:
        """Get current user from session with in-memory fallback"""
        # Try to get session ID from cookies first
        session_id = self.get_session_id(request)
        
        # If no session ID from cookies, try Authorization header
        if not session_id:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                session_id = auth_header[7:]  # Remove "Bearer " prefix
                unified_logger.debug(LogModule.AUTH, f"Using session ID from Authorization header: {session_id[:20]}...")
        
        if not session_id:
            return None
        
        user_data = None
        
        # Try Redis first
        if self.redis_client:
            try:
                session_data = self.redis_client.get(f"session:{session_id}")
                if session_data:
                    user_data = json.loads(session_data)
                    unified_logger.debug(LogModule.AUTH, f"Found user data in Redis for session: {session_id[:20]}...")
            except Exception as e:
                unified_logger.warning(LogModule.AUTH, f"Failed to get session from Redis: {e}")
        
        # Fallback to in-memory storage
        if not user_data and session_id in _memory_sessions:
            user_data = _memory_sessions[session_id]
            unified_logger.info(LogModule.AUTH, f"Using in-memory session data: {session_id[:20]}...")
        
        if not user_data:
            unified_logger.debug(LogModule.AUTH, f"No user data found for session: {session_id[:20]}...")
            return None
        
        # Check if session is expired
        created_at = user_data.get("created_at", 0)
        if time.time() - created_at > self.config.session_max_age:
            # Remove expired session
            if session_id in _memory_sessions:
                del _memory_sessions[session_id]
            unified_logger.debug(LogModule.AUTH, f"Session expired: {session_id[:20]}...")
            return None
        
        # Create User object
        from auth.models import User, UserRole
        unified_logger.debug(LogModule.AUTH, f"Successfully authenticated user: {user_data['username']}")
        return User(
            username=user_data["username"],
            display_name=user_data["display_name"],
            email=user_data["email"],
            is_authenticated=user_data["is_authenticated"],
            role=UserRole(user_data["role"])
        )

    async def is_authenticated(self, request: Request) -> bool:
        """Check if user is authenticated"""
        user = await self.get_user(request)
        return user is not None and user.is_authenticated
    
    def get_login_attempts(self, ip_address: str) -> int:
        """Get login attempt count for IP address"""
        if not self.redis_client:
            return 0
        
        try:
            key = f"login_attempts:{ip_address}"
            attempts = self.redis_client.get(key)
            return int(attempts) if attempts else 0
        except Exception as e:
            unified_logger.warning(LogModule.AUTH, f"Failed to get login attempt count: {e}")
            return 0
    
    def increment_login_attempts(self, ip_address: str) -> int:
        """Increment login attempt count for IP address"""
        if not self.redis_client:
            return 1
        
        try:
            key = f"login_attempts:{ip_address}"
            attempts = self.redis_client.incr(key)
            self.redis_client.expire(key, self.config.login_attempt_window)
            return attempts
        except Exception as e:
            unified_logger.warning(LogModule.AUTH, f"Failed to increment login attempt count: {e}")
            return 1
    
    def reset_login_attempts(self, ip_address: str):
        """Reset login attempt count for IP address"""
        if not self.redis_client:
            return
        
        try:
            key = f"login_attempts:{ip_address}"
            self.redis_client.delete(key)
        except Exception as e:
            unified_logger.warning(LogModule.AUTH, f"Failed to reset login attempt count: {e}")
