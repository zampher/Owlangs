# Icon Regeneration Guide

This guide explains how to regenerate all platform icons from the updated SVG source file.

## Quick Start

Simply run the regeneration script:

```bash
cd frontend
python tools/regenerate_all_icons.py
```

This script will:
1. Check if SVG source exists (`assets/owlangs_owl_solid.svg`)
2. Convert SVG to PNG (1024x1024) if needed, or use existing PNG
3. Copy PNG to macOS icon directory
4. Generate all platform icons (Web, Android, iOS, macOS, Linux, Windows)

## What Gets Generated

### Source Files
- `assets/owlangs_owl_solid.svg` - Source SVG file
- `assets/owlangs_owl_solid.png` - Source PNG file (1024x1024, auto-generated from SVG)

### Generated Icons

#### Web Icons
- `web/icons/Icon-192.png` (192x192)
- `web/icons/Icon-512.png` (512x512)
- `web/icons/Icon-maskable-192.png` (192x192)
- `web/icons/Icon-maskable-512.png` (512x512)
- `web/favicon.ico`

#### Android Icons
- `android/app/src/main/res/mipmap-*/ic_launcher.png` (48x48, 72x72, 96x96, 144x144, 192x192)

#### iOS Icons
- `ios/Runner/Assets.xcassets/AppIcon.appiconset/Icon-App-*.png` (various sizes)

#### macOS Icons
- `macos/Runner/Assets.xcassets/AppIcon.appiconset/app_icon_*.png` (various sizes)

#### Linux Icons
- `linux/owlangs.png` (512x512)

#### Windows Icons
- `windows/runner/resources/app_icon.ico`

## SVG to PNG Conversion

The script attempts multiple methods to convert SVG to PNG:

1. **cairosvg** (Python library)
   ```bash
   pip install cairosvg
   ```

2. **svglib** (Python library)
   ```bash
   pip install svglib reportlab
   ```

3. **Inkscape** (command line tool)
   - Must be installed and in PATH
   - Command: `inkscape input.svg --export-width=1024 --export-height=1024 --export-filename=output.png`

If automatic conversion fails, the script will provide manual conversion instructions.

### Manual Conversion Methods

#### Method 1: Online Tool (Easiest)
1. Visit: https://cloudconvert.com/svg-to-png
2. Upload: `assets/owlangs_owl_solid.svg`
3. Set size: 1024x1024
4. Download and save as: `assets/owlangs_owl_solid.png`

#### Method 2: Inkscape (if installed)
```bash
inkscape assets/owlangs_owl_solid.svg --export-width=1024 --export-height=1024 --export-filename=assets/owlangs_owl_solid.png
```

#### Method 3: ImageMagick (if installed)
```bash
magick assets/owlangs_owl_solid.svg -resize 1024x1024 assets/owlangs_owl_solid.png
```

## Troubleshooting

### PNG Already Exists
If `assets/owlangs_owl_solid.png` already exists but is smaller than 1024x1024, the script will automatically regenerate it from SVG.

To force regeneration, delete the PNG file and run the script again.

### Conversion Fails
If all automatic conversion methods fail:
1. Follow the manual conversion instructions provided by the script
2. Place the converted PNG at `assets/owlangs_owl_solid.png`
3. Run the script again

### Missing Dependencies
If you see import errors, install the required Python packages:
```bash
pip install Pillow
```

For SVG conversion (optional):
```bash
pip install cairosvg
# or
pip install svglib reportlab
```

## Workflow

1. **Update SVG**: Edit `assets/owlangs_owl_solid.svg` as needed
2. **Run Script**: Execute `python tools/regenerate_all_icons.py`
3. **Verify**: Check that all icons were generated successfully
4. **Commit**: Commit the updated icons to version control

## Notes

- The script preserves existing PNG files if they are 1024x1024 or larger
- All icons are generated from a single source PNG (1024x1024)
- The script handles Windows console encoding issues automatically
- All platform icons are generated in a single run

