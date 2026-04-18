# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Unified password management system for Owlangs
Provides secure password hashing and verification for all user types
"""

import hashlib
import hmac
import secrets
import logging
from typing import Optional

from logger.logger import LogModule

logger = logging.getLogger(__name__)


class PasswordManager:
    """Unified password management system"""
    
    # PBKDF2 parameters
    DEFAULT_ITERATIONS = 210_000
    SALT_LENGTH = 16  # 128 bits
    
    @staticmethod
    def hash_password(password: str, iterations: int = None, skip_validation: bool = False) -> str:
        """
        Hash a password using PBKDF2-SHA256
        
        Args:
            password: Plain text password
            iterations: Number of iterations (default: 210,000)
            skip_validation: Skip password strength validation (for default passwords)
            
        Returns:
            Hashed password in format: pbkdf2_sha256$iterations$salt$hash
            
        Raises:
            ValueError: If password is empty or invalid
        """
        if not isinstance(password, str) or not password:
            raise ValueError("Password must be non-empty string")
        
        # Validate password strength unless explicitly skipped
        if not skip_validation:
            is_valid, error_msg = PasswordManager.validate_password_strength(password)
            if not is_valid:
                raise ValueError(error_msg)
        
        if iterations is None:
            iterations = PasswordManager.DEFAULT_ITERATIONS
            
        # Generate random salt
        salt = secrets.token_bytes(PasswordManager.SALT_LENGTH)
        
        # Hash password using PBKDF2-SHA256
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        
        # Return in format: algorithm$iterations$salt$hash
        return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash
        
        Args:
            password: Plain text password to verify
            hashed_password: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            # Parse hash format: algorithm$iterations$salt$hash
            parts = hashed_password.split('$', 3)
            if len(parts) != 4:
                logger.warning(LogModule.AUTH, "Invalid password hash format")
                return False
                
            algorithm, iter_str, salt_hex, hash_hex = parts
            
            # Check algorithm
            if algorithm != 'pbkdf2_sha256':
                logger.warning(LogModule.AUTH, f"Unsupported password hash algorithm: {algorithm}")
                return False
            
            # Parse parameters
            iterations = int(iter_str)
            salt = bytes.fromhex(salt_hex)
            expected_hash = bytes.fromhex(hash_hex)
            
            # Compute hash
            computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            
            # Constant time comparison to prevent timing attacks
            return hmac.compare_digest(computed_hash, expected_hash)
            
        except (ValueError, TypeError) as e:
            logger.warning(LogModule.AUTH, f"Password verification failed: {e}")
            return False
        except Exception as e:
            logger.error(LogModule.AUTH, f"Unexpected error during password verification: {e}")
            return False
    
    @staticmethod
    def is_hashed(password: str) -> bool:
        """
        Check if a password is already hashed
        
        Args:
            password: Password string to check
            
        Returns:
            True if password appears to be hashed, False otherwise
        """
        if not isinstance(password, str):
            return False
            
        # Check if it matches our hash format
        parts = password.split('$', 3)
        return (len(parts) == 4 and 
                parts[0] == 'pbkdf2_sha256' and 
                parts[1].isdigit() and 
                len(parts[2]) == PasswordManager.SALT_LENGTH * 2 and  # hex encoded salt
                len(parts[3]) == 64)  # SHA256 hash is 32 bytes = 64 hex chars
    
    @staticmethod
    def migrate_plaintext_password(plaintext_password: str) -> str:
        """
        Migrate a plaintext password to hashed format
        
        Args:
            plaintext_password: Plain text password to migrate
            
        Returns:
            Hashed password
        """
        if PasswordManager.is_hashed(plaintext_password):
            logger.debug(LogModule.AUTH, "Password is already hashed, returning as-is")
            return plaintext_password
            
        logger.info(LogModule.AUTH, "Migrating plaintext password to secure hash")
        return PasswordManager.hash_password(plaintext_password)
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        Validate password strength
        
        Args:
            password: Password to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        from .i18n_utils import get_password_message
        
        if not isinstance(password, str):
            return False, get_password_message("changePasswordTooWeakString")
            
        if len(password) < 8:
            return False, get_password_message("changePasswordTooWeakLength")
            
        if len(password) > 128:
            return False, get_password_message("changePasswordTooWeakMaxLength")
            
        # Check for at least one character from each category
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if not (has_lower and has_upper and has_digit):
            return False, get_password_message("changePasswordTooWeakComplexity")
            
        return True, "Password is valid"


# Global instance for easy access
password_manager = PasswordManager()
