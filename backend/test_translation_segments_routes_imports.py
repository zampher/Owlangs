"""
Basic import test for translation segments routes.

Goal:
- Ensure that importing the service routes package and the translation
  segments routes no longer raises circular import errors related to
  utils.translation_segments.get_translation_segments.

NOTE:
- This test assumes the full backend runtime environment is available
  (including config.config_loader used by the logger).
  If that dependency is missing, the test will be skipped instead of failing.
"""

import pytest


def test_import_service_router_and_translation_segments_router() -> None:
    # Ensure logger/config dependencies are available; otherwise skip.
    pytest.importorskip("config.config_loader")

    # Import the top-level service router, which will in turn import
    # app_routes_translation_segments and its dependencies.
    from backend.app.routes.service import router as service_router  # noqa: F401

    # Import the translation segments routes module directly and ensure
    # that its router object is available.
    from backend.app.routes.service import app_routes_translation_segments

    assert hasattr(app_routes_translation_segments, "router")

