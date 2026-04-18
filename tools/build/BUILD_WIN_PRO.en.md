# Building and packaging Owlangs Pro on Windows (`build_win_pro.ps1`)

> Chinese version: [BUILD_WIN_PRO.zh-CN.md](BUILD_WIN_PRO.zh-CN.md)

This guide explains how to use `tools/build/build_win_pro.ps1` on Windows to produce the **Pro** edition: **Windows desktop** frontend, **lite** package size, **Pandoc + pdflatex** bundled for PDF / DOCX workflows, and **no anonymize** components (as stated in the script comments).

---

## What the script does

| Step | Description |
|------|-------------|
| Working directory | Switches to the repository root (script lives under `tools/build`; two levels up is the project root). |
| Version sync | Runs `tools/setup/sync_version.ps1` (warnings only on failure; build usually continues). |
| Build | Delegates to `build_win.ps1` or `build_win_installer.ps1` with fixed flags: **Lite + Windows desktop + IncludePandoc + Edition Pro**. |
| Verification | Sources `verify_build.ps1` to assert the folder package or installer contains expected artifacts. |

---

## Prerequisites

Before running the script, ensure you have:

- **PowerShell** (normal user is usually fine; adjust execution policy if restricted).
- **Flutter SDK** (Windows desktop frontend build).
- **Python** and the project **virtual environment** (`.venv`) for backend packaging.
- **Inno Setup** only when you pass **`-Installer`**; the build looks for `ISCC.exe` in common install locations.

For the full dependency list and pipeline details, refer to `build_win.ps1` and `build_win_installer.ps1`.

---

## Usage

Run from the **repository root** (recommended):

```powershell
cd <path-to-Owlangs-repo-root>
.\tools\build\build_win_pro.ps1
```

### Mode 1: Folder package (default)

Without `-Installer`, the script invokes:

`build_win.ps1 --lite -Frontend windows -IncludePandoc -Edition Pro`

Verification expects under:

`build\win\Owlangs-<version>\`

at least one of:

- `bin\Owlangs-win.exe`, or  
- `launcher\OwlangsLauncher.exe`

(Version is typically taken from `backend.__version__` or `backend/__init__.py`.)

### Mode 2: Installer

Build an Inno Setup installer:

```powershell
.\tools\build\build_win_pro.ps1 -Installer
```

This calls `build_win_installer.ps1`. Verification expects under `build\installer\` an executable such as:

- `Owlangs-Installer-<version>.exe`, or  
- `Owlangs-Standard-<version>-x64.exe` (alternate naming for Pro; see `verify_build.ps1`)

---

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| Script exits immediately with an error | Read the first Flutter / Python / Inno error; confirm you run from the **repo root** with `.\tools\build\build_win_pro.ps1`. |
| `Verify: Package dir not found` | Confirm `build_win.ps1` completed successfully and `build\win\Owlangs-<version>` exists. |
| `Verify: Installer not found` | Inno Setup installed; no errors in `build_win_installer.ps1`; inspect `build\installer`. |
| Version sync warning | Often path or permissions; fix per log and retry. |

---

## Related scripts

- **`build_win_pro.ps1`**: Shortcut for **Pro + lite + Windows desktop + Pandoc** only; no extra switches.
- For **Enterprise**, **web + desktop** frontends, or a standalone **full** package, use **`build_win.ps1`**, **`build_win_enterprise.ps1`**, etc., and read their headers.

---

## Verify (checklist)

1. From the repo root, run `.\tools\build\build_win_pro.ps1` and confirm **Pro edition build finished and verified**.  
2. Under `build\win\Owlangs-<version>\`, confirm `bin\Owlangs-win.exe` or `launcher\OwlangsLauncher.exe`.  
3. With `-Installer`, confirm the expected `.exe` under `build\installer\`.  
4. On failure, trace back to the first failing step (Flutter, PyInstaller, Inno, etc.) and fix upstream.
