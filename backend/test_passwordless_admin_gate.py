# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Guards for passwordless web: config still requires admin session."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.auth.models import UserRole


class PasswordlessAdminGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_passwordless_web_without_session_is_non_admin(self) -> None:
        from backend.auth.routes import get_current_user

        request = MagicMock()
        request.url.path = "/api/v1/auth/user/permissions"
        request.client = ("203.0.113.10", 443)
        request.headers = {}

        unified = MagicMock()
        unified.auth_required = False
        session_manager = MagicMock()
        session_manager.get_user = AsyncMock(return_value=None)

        with patch("backend.auth.routes.get_unified_config", return_value=unified), patch(
            "backend.auth.routes.get_session_manager", return_value=session_manager
        ), patch("backend.auth.routes._is_desktop_localhost", return_value=False):
            user = await get_current_user(request)

        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.username, "local")
        self.assertFalse(user.is_admin())
        self.assertFalse(user.can_access_admin_settings())
        self.assertEqual(user.role, UserRole.LDAP_USER)

    async def test_passwordless_desktop_localhost_is_admin(self) -> None:
        from backend.auth.routes import get_current_user

        request = MagicMock()
        request.url.path = "/api/v1/auth/settings/batch"
        request.client = ("127.0.0.1", 12345)
        request.headers = {"x-client": "desktop"}

        unified = MagicMock()
        unified.auth_required = False
        session_manager = MagicMock()
        session_manager.get_user = AsyncMock(return_value=None)

        with patch("backend.auth.routes.get_unified_config", return_value=unified), patch(
            "backend.auth.routes.get_session_manager", return_value=session_manager
        ):
            user = await get_current_user(request)

        self.assertIsNotNone(user)
        assert user is not None
        self.assertTrue(user.is_admin())
        self.assertTrue(user.can_access_admin_settings())
        self.assertEqual(user.role, UserRole.ADMIN)


if __name__ == "__main__":
    unittest.main()
