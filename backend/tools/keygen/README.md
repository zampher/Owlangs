# Keygen Tool Package

License code generation and verification tool using Ed25519 private key.

## Structure

- `keygen.py` - CLI tool for generating and verifying license codes
- `keygen_gui.py` - GUI tool (Tkinter) for interactive license generation
- `test_keygen_core.py` - Unit tests for core crypto functions
- `__init__.py` - Package initialization with exported functions

## Quick Start

### Generate Key Pair (First Time)

```bash
python -m backend.tools.keygen.keygen --generate-keys
```

This creates:
- `configs/license_private.pem` (keep secret!)
- `configs/license_public.pem` (can be deployed)

### Generate License Code (CLI)

```bash
# Machine-bound license
python -m backend.tools.keygen.keygen --machine-id A1B2C3D4E5F6 --expiry 2026-12-31

# User license with features
python -m backend.tools.keygen.keygen --user-id user123 --features premium,advanced --expiry 2026-12-31

# Custom JSON payload
python -m backend.tools.keygen.keygen --payload '{"user_id":"12345","type":"premium"}'
```

### Launch GUI

```bash
python -m backend.tools.keygen.keygen_gui
```

### Verify License Code

```bash
python -m backend.tools.keygen.keygen --verify CODE --machine-id A1B2C3D4E5F6
```

## Documentation

See `docs/tools/keygen_usage.md` for detailed usage instructions.

## Security Notes

- **Private key** (`license_private.pem`) must be kept secret
- Never commit private key to Git (add to `.gitignore`)
- GUI tool is for internal use only
- Public key can be safely deployed for verification
