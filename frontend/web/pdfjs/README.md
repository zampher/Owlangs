# Vendored pdf.js (pdfjs-dist)

Local copy of [pdfjs-dist](https://www.npmjs.com/package/pdfjs-dist) **4.6.82** for offline / air-gapped PDF preview in Flutter Web (`pdfx`).

Do **not** load these files from jsDelivr or other CDNs.

## Layout

- `build/pdf.min.mjs` — main library (`globalThis.pdfjsLib`)
- `build/pdf.worker.min.mjs` — worker
- `cmaps/` — CMap data for CJK and other encodings
- `standard_fonts/` — standard font data (optional for pdfx; kept for offline completeness)

## Update

From repo root (needs network once):

```powershell
powershell -File tools/download_pdfjs.ps1
```

Keep the version aligned with `pdfx` (`flutter pub run pdfx:install_web` pins **4.6.82**).
