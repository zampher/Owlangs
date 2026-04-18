"""
Basic tests for backend.tools.keygen core functions.

This verifies that generate_key_pair, sign_license and verify_license work
end-to-end. It does not cover the GUI itself but ensures the crypto logic is
sound for both CLI and GUI keygen tools.
"""

from typing import Any, Dict

from backend.tools.keygen import keygen as core_keygen


def _build_sample_payload() -> Dict[str, Any]:
    """Build a simple sample payload for testing."""
    return {
        "machine_id": "ABCDEF123456",
        "user_id": "tester",
        "license_key": "TEST-KEY",
        "features": ["feature1", "feature2"],
        "expiry": "2099-12-31",
    }


def test_sign_and_verify_roundtrip() -> None:
    """Sign a payload and verify it with the corresponding public key."""
    private_pem, public_pem = core_keygen.generate_key_pair()
    payload = _build_sample_payload()

    code = core_keygen.sign_license(private_pem, payload)

    is_valid, error_msg, decoded = core_keygen.verify_license(
        public_pem, code, expected_data={"machine_id": payload["machine_id"]}
    )

    assert is_valid, f"Expected license to be valid, got error: {error_msg}"
    assert decoded is not None
    assert decoded.get("machine_id") == payload["machine_id"]
    assert decoded.get("user_id") == payload["user_id"]
    assert decoded.get("license_key") == payload["license_key"]


def test_decode_without_verification() -> None:
    """Decode a license without verification and ensure payload is present."""
    private_pem, _ = core_keygen.generate_key_pair()
    payload = _build_sample_payload()

    code = core_keygen.sign_license(private_pem, payload)

    decoded, error = core_keygen.decode_license(code)
    assert error is None
    assert decoded is not None
    assert decoded.get("machine_id") == payload["machine_id"]

