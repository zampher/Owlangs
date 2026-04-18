"""
Simple GUI keygen tool built on top of backend.tools.keygen.

Features:
- Generate license code using Ed25519 private key
- Support machine_id / user_id / license_key / features / expiry
- Support custom JSON payload
- Verify license code with public key
- Decode license code without verification

This GUI is intended for internal use by maintainers to generate and inspect
licenses. It uses the same key discovery logic as backend.tools.keygen
(LICENSE_PRIVATE_KEY_FILE / LICENSE_PUBLIC_KEY_FILE, fallback to donor keys).
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox

# Ensure project root is on sys.path so we can import backend.tools.keygen.keygen
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.tools.keygen import keygen as core_keygen  # type: ignore

# License key (product edition) options: display label -> payload value (None = omit from payload)
LICENSE_KEY_OPTIONS: List[Tuple[str, Optional[str]]] = [
    ("(None - legacy / Pro desktop)", None),
    ("PRO (Desktop)", "PRO"),
    ("PRO-WEB (Web)", "PRO-WEB"),
]
LICENSE_KEY_DISPLAYS = [t[0] for t in LICENSE_KEY_OPTIONS]


def _license_key_display_to_value(display: str) -> Optional[str]:
    """Map combo display text to payload value; empty or unknown -> None."""
    for d, v in LICENSE_KEY_OPTIONS:
        if d == display:
            return v
    return None


def _license_key_value_to_display(value: Optional[str]) -> str:
    """Map payload value to combo display text."""
    if not value:
        return LICENSE_KEY_OPTIONS[0][0]
    for d, v in LICENSE_KEY_OPTIONS:
        if v == value:
            return d
    return LICENSE_KEY_OPTIONS[0][0]


class KeygenGuiApp:
    """Tkinter-based GUI keygen application."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.master.title("Owlangs License Keygen")
        self.master.geometry("900x600")

        # Main notebook with two tabs: Generate / Verify
        self.notebook = ttk.Notebook(self.master)
        self.frame_generate = ttk.Frame(self.notebook)
        self.frame_verify = ttk.Frame(self.notebook)
        self.notebook.add(self.frame_generate, text="Generate")
        self.notebook.add(self.frame_verify, text="Verify / Decode")
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_generate_tab()
        self._build_verify_tab()
        self._build_status_bar()

        # Initialize status bar with detected key paths
        self._refresh_key_status()

    # ------------------------------------------------------------------
    # UI building helpers
    # ------------------------------------------------------------------
    def _build_generate_tab(self) -> None:
        """Build controls for license generation."""
        container = self.frame_generate

        # Left side: structured fields
        left = ttk.Frame(container)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        row = 0

        ttk.Label(left, text="Machine ID (optional)").grid(
            row=row, column=0, sticky=tk.W
        )
        self.entry_machine_id = ttk.Entry(left, width=40)
        self.entry_machine_id.grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(left, text="User ID (optional)").grid(
            row=row, column=0, sticky=tk.W
        )
        self.entry_user_id = ttk.Entry(left, width=40)
        self.entry_user_id.grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(left, text="Product / License Key").grid(
            row=row, column=0, sticky=tk.W
        )
        self.combo_license_key = ttk.Combobox(
            left, width=36, values=LICENSE_KEY_DISPLAYS, state="readonly"
        )
        self.combo_license_key.set(LICENSE_KEY_OPTIONS[0][0])
        self.combo_license_key.grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(left, text="Features (comma-separated, optional)").grid(
            row=row, column=0, sticky=tk.W
        )
        self.entry_features = ttk.Entry(left, width=40)
        self.entry_features.grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(left, text="Expiry (YYYY-MM-DD, optional)").grid(
            row=row, column=0, sticky=tk.W
        )
        self.entry_expiry = ttk.Entry(left, width=40)
        self.entry_expiry.grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        # Custom payload toggle
        self.var_use_custom_payload = tk.BooleanVar(value=False)
        chk_custom = ttk.Checkbutton(
            left,
            text="Use custom JSON payload (override above fields)",
            variable=self.var_use_custom_payload,
        )
        chk_custom.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        # Right side: JSON payload editor and output
        right = ttk.Frame(container)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        payload_label = ttk.Label(right, text="Payload JSON")
        payload_label.pack(anchor=tk.W)

        self.text_payload = tk.Text(right, height=10)
        self.text_payload.pack(fill=tk.X, padx=0, pady=2)

        # Buttons
        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill=tk.X, pady=4)

        btn_build = ttk.Button(
            btn_frame, text="Build JSON from fields", command=self._on_build_payload
        )
        btn_build.pack(side=tk.LEFT, padx=4)

        btn_generate = ttk.Button(
            btn_frame, text="Generate Code", command=self._on_generate_code
        )
        btn_generate.pack(side=tk.LEFT, padx=4)

        btn_copy = ttk.Button(
            btn_frame, text="Copy Code", command=self._on_copy_code
        )
        btn_copy.pack(side=tk.LEFT, padx=4)

        # Result code
        ttk.Label(right, text="License Code").pack(anchor=tk.W, pady=(8, 0))
        self.text_code = tk.Text(right, height=4)
        self.text_code.pack(fill=tk.X, pady=2)

        ttk.Label(right, text="Formatted Code (groups of 4)").pack(
            anchor=tk.W, pady=(8, 0)
        )
        self.text_code_formatted = tk.Text(right, height=2)
        self.text_code_formatted.pack(fill=tk.X, pady=2)

    def _build_verify_tab(self) -> None:
        """Build controls for license verification and decoding."""
        container = self.frame_verify

        top = ttk.Frame(container)
        top.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(top, text="License Code").grid(row=0, column=0, sticky=tk.W)
        self.text_verify_code = tk.Text(top, height=4, width=80)
        self.text_verify_code.grid(row=1, column=0, columnspan=4, sticky=tk.W)

        row = 2
        ttk.Label(top, text="Expected Machine ID (optional)").grid(
            row=row, column=0, sticky=tk.W
        )
        self.entry_verify_machine_id = ttk.Entry(top, width=30)
        self.entry_verify_machine_id.grid(row=row, column=1, sticky=tk.W, pady=2)

        ttk.Label(top, text="Expected User ID (optional)").grid(
            row=row, column=2, sticky=tk.W
        )
        self.entry_verify_user_id = ttk.Entry(top, width=30)
        self.entry_verify_user_id.grid(row=row, column=3, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(top, text="Expected License Key").grid(
            row=row, column=0, sticky=tk.W
        )
        self.combo_verify_license_key = ttk.Combobox(
            top, width=28, values=LICENSE_KEY_DISPLAYS, state="readonly"
        )
        self.combo_verify_license_key.set(LICENSE_KEY_OPTIONS[0][0])
        self.combo_verify_license_key.grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        btn_frame = ttk.Frame(top)
        btn_frame.grid(row=row, column=0, columnspan=4, sticky=tk.W, pady=4)

        btn_verify = ttk.Button(
            btn_frame, text="Verify Code", command=self._on_verify_code
        )
        btn_verify.pack(side=tk.LEFT, padx=4)

        btn_decode = ttk.Button(
            btn_frame, text="Decode Only", command=self._on_decode_code
        )
        btn_decode.pack(side=tk.LEFT, padx=4)

        # Result area
        ttk.Label(container, text="Result / Payload").pack(
            anchor=tk.W, padx=10, pady=(8, 0)
        )
        self.text_verify_result = tk.Text(container, height=16)
        self.text_verify_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

    def _build_status_bar(self) -> None:
        """Build simple status bar at bottom."""
        self.status_var = tk.StringVar(value="Ready")
        frame = ttk.Frame(self.master)
        frame.pack(fill=tk.X, side=tk.BOTTOM)
        label = ttk.Label(frame, textvariable=self.status_var, anchor=tk.W)
        label.pack(fill=tk.X, padx=4, pady=2)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _set_status(self, msg: str) -> None:
        """Update status bar text."""
        self.status_var.set(msg)

    def _refresh_key_status(self) -> None:
        """Detect key paths and show in status bar."""
        try:
            priv_path = core_keygen._find_private_key()  # type: ignore[attr-defined]
            pub_path = core_keygen._find_public_key()  # type: ignore[attr-defined]
            self._set_status(
                f"Using private key: {priv_path} | public key: {pub_path}"
            )
        except Exception as e:  # noqa: BLE001
            self._set_status(f"Key load warning: {e}")

    def _build_payload_from_fields(self) -> Dict[str, Any]:
        """Build payload dict from structured fields."""
        payload: Dict[str, Any] = {}
        machine_id = self.entry_machine_id.get().strip().upper()
        user_id = self.entry_user_id.get().strip()
        license_key = _license_key_display_to_value(
            self.combo_license_key.get().strip()
        )
        features = self.entry_features.get().strip()
        expiry = self.entry_expiry.get().strip()

        if machine_id:
            payload["machine_id"] = machine_id
        if user_id:
            payload["user_id"] = user_id
        if license_key:
            payload["license_key"] = license_key
        if features:
            lst = [f.strip() for f in features.split(",") if f.strip()]
            if lst:
                payload["features"] = lst
        if expiry:
            payload["expiry"] = expiry

        return payload

    def _get_payload(self) -> Optional[Dict[str, Any]]:
        """Get payload from either custom JSON or fields."""
        if self.var_use_custom_payload.get():
            text = self.text_payload.get("1.0", tk.END).strip()
            if not text:
                messagebox.showerror("Error", "Custom JSON payload is empty.")
                return None
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as e:
                messagebox.showerror(
                    "Error", f"Invalid JSON payload:\n{e}"
                )
                return None
            if not isinstance(payload, dict):
                messagebox.showerror(
                    "Error", "JSON payload must be a JSON object (dictionary)."
                )
                return None
            return payload
        # Build from structured fields
        payload = self._build_payload_from_fields()
        if not payload:
            messagebox.showerror(
                "Error",
                "No payload data. Fill one of the fields or enable custom JSON payload.",
            )
            return None
        return payload

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_build_payload(self) -> None:
        """Populate JSON payload text from structured fields."""
        payload = self._build_payload_from_fields()
        if not payload:
            messagebox.showinfo(
                "Info",
                "No data in fields. Please fill at least one field.",
            )
            return
        self.text_payload.delete("1.0", tk.END)
        self.text_payload.insert(
            tk.END, json.dumps(payload, indent=2, ensure_ascii=False)
        )
        self._set_status("Payload JSON built from fields.")

    def _on_generate_code(self) -> None:
        """Generate license code from payload."""
        try:
            payload = self._get_payload()
            if payload is None:
                return

            try:
                key_path = core_keygen._find_private_key()  # type: ignore[attr-defined]
                private_pem = core_keygen._load_private_key(key_path)  # type: ignore[attr-defined]
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Error", f"Failed to load private key:\n{e}")
                self._set_status(f"Failed to load private key: {e}")
                return

            code = core_keygen.sign_license(private_pem, payload)

            # Show raw code
            self.text_code.delete("1.0", tk.END)
            self.text_code.insert(tk.END, code)

            # Show formatted code
            formatted = self._format_code(code)
            self.text_code_formatted.delete("1.0", tk.END)
            self.text_code_formatted.insert(tk.END, formatted)

            self._set_status("License code generated successfully.")
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            messagebox.showerror("Error", f"Unexpected error:\n{e}")
            self._set_status(f"Error generating code: {e}")

    def _on_copy_code(self) -> None:
        """Copy current formatted code to clipboard."""
        # Prefer copying raw license code (backend expects raw base64url string).
        code = self.text_code.get("1.0", tk.END).strip()
        if not code:
            # Fallback to formatted view if raw is empty
            code = self.text_code_formatted.get("1.0", tk.END).strip()
        if not code:
            messagebox.showinfo("Info", "No code to copy.")
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(code)
        self._set_status("Code copied to clipboard.")

    def _on_verify_code(self) -> None:
        """Verify license code using public key and optional expected data."""
        code = self.text_verify_code.get("1.0", tk.END).strip()
        if not code:
            messagebox.showerror("Error", "Please paste a license code to verify.")
            return

        try:
            key_path = core_keygen._find_public_key()  # type: ignore[attr-defined]
            public_pem = core_keygen._load_public_key(key_path)  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to load public key:\n{e}")
            self._set_status(f"Failed to load public key: {e}")
            return

        expected: Dict[str, Any] = {}
        machine_id = self.entry_verify_machine_id.get().strip().upper()
        user_id = self.entry_verify_user_id.get().strip()
        license_key = _license_key_display_to_value(
            self.combo_verify_license_key.get().strip()
        )
        if machine_id:
            expected["machine_id"] = machine_id
        if user_id:
            expected["user_id"] = user_id
        if license_key:
            expected["license_key"] = license_key

        is_valid, error_msg, payload = core_keygen.verify_license(
            public_pem, code, expected if expected else None
        )

        self.text_verify_result.delete("1.0", tk.END)
        if is_valid:
            self.text_verify_result.insert(
                tk.END,
                "✓ License is VALID\n\n"
                + json.dumps(payload or {}, indent=2, ensure_ascii=False),
            )
            self._set_status("License is valid.")
        else:
            self.text_verify_result.insert(
                tk.END,
                f"✗ License is INVALID: {error_msg}\n\n"
                + (
                    json.dumps(payload or {}, indent=2, ensure_ascii=False)
                    if payload
                    else ""
                ),
            )
            self._set_status("License is invalid.")

    def _on_decode_code(self) -> None:
        """Decode license code without verifying signature."""
        code = self.text_verify_code.get("1.0", tk.END).strip()
        if not code:
            messagebox.showerror("Error", "Please paste a license code to decode.")
            return
        payload, error = core_keygen.decode_license(code)
        self.text_verify_result.delete("1.0", tk.END)
        if error:
            self.text_verify_result.insert(tk.END, f"✗ Error decoding license: {error}")
            self._set_status("Failed to decode license.")
        else:
            self.text_verify_result.insert(
                tk.END,
                "✓ License decoded (not verified):\n\n"
                + json.dumps(payload or {}, indent=2, ensure_ascii=False),
            )
            self._set_status("License decoded (not verified).")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @staticmethod
    def _format_code(code: str, group_size: int = 4) -> str:
        """Format code with dashes every group_size characters."""
        formatted = ""
        for i, ch in enumerate(code):
            if i > 0 and i % group_size == 0:
                formatted += "-"
            formatted += ch
        return formatted


def main() -> None:
    root = tk.Tk()
    app = KeygenGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

