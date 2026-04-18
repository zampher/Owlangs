#!/usr/bin/env python3
"""
Generate ICO file from SVG or PNG logo.
Multiple sizes for Windows shell / taskbar (16–256, includes 24).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print(
        'ERROR: Pillow is required.\nInstall: python -m pip install "Pillow>=10.0.0"',
        file=sys.stderr,
    )
    sys.exit(1)


def composite_centered_on_square(
    img: Image.Image, canvas_size: int, fill_ratio: float
) -> Image.Image:
    """Place artwork on a transparent square canvas with margin so small icons keep shape readable.
    
    Preserves alpha channel for rounded corner transparency.
    """
    if fill_ratio <= 0 or fill_ratio > 1.0:
        raise ValueError("fill_ratio must be in (0, 1]")
    inner = max(1, int(round(canvas_size * fill_ratio)))
    
    # Ensure image is in RGBA mode to preserve transparency
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    
    # Resize to target inner size with transparency preserved
    scaled = img.resize((inner, inner), Image.Resampling.LANCZOS)
    
    # Create transparent background (RGBA with alpha=0)
    out = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    off = (canvas_size - inner) // 2
    out.paste(scaled, (off, off), scaled)  # Use scaled as mask for alpha
    return out


def svg_to_png(svg_path: Path, png_path: Path, size: int) -> bool:
    """Rasterize SVG to PNG at specified size (square)."""
    try:
        import cairosvg
    except ImportError:
        print(
            'ERROR: cairosvg is required for SVG input.\n'
            'Install: python -m pip install "cairosvg>=2.7.0"',
            file=sys.stderr,
        )
        return False
    try:
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            output_width=size,
            output_height=size,
        )
        return True
    except Exception as e:
        print(f"Error converting SVG to PNG ({size}x{size}): {e}")
        return False


def create_ico_from_images(images: list, output_path: Path) -> bool:
    """Write multi-size ICO with transparency preserved (Windows-friendly ordering)."""
    processed: list[Image.Image] = []
    for im in images:
        # Ensure image is RGBA to preserve transparency for rounded corners
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        processed.append(im)

    if not processed:
        print("No valid images to create ICO")
        return False

    ordered = sorted(processed, key=lambda i: i.size[0], reverse=True)
    sizes = [(i.size[0], i.size[1]) for i in ordered]
    first, rest = ordered[0], ordered[1:]
    try:
        save_kw: dict = {"format": "ICO", "sizes": sizes}
        if rest:
            save_kw["append_images"] = rest
        first.save(output_path, **save_kw)
        print(f"OK Created ICO file: {output_path}")
        print(f"  Sizes (largest first): {', '.join(f'{w}x{h}' for w, h in sizes)}")
        return True
    except Exception as e:
        print(f"Error creating ICO: {e}")
        return False


def generate_ico_from_svg(
    svg_path: Path,
    output_path: Path | None = None,
    sizes: list | None = None,
    fill_ratio: float = 0.88,
) -> bool:
    """Generate ICO from SVG; optional inset so rounded logos read at 16x16."""
    if sizes is None:
        sizes = [16, 24, 32, 48, 64, 128, 256]

    if output_path is None:
        output_path = svg_path.parent / f"{svg_path.stem}.ico"

    temp_dir = svg_path.parent / "temp_ico"
    temp_dir.mkdir(exist_ok=True)
    png_paths: list[Path] = []

    def size_from_path(p: Path) -> int:
        parts = p.stem.split("_")
        for part in reversed(parts):
            if "x" in part:
                try:
                    return int(part.split("x")[0])
                except ValueError:
                    pass
        return 0

    try:
        for size in sizes:
            png_path = temp_dir / f"{svg_path.stem}_{size}x{size}.png"
            if not svg_to_png(svg_path, png_path, size):
                continue
            try:
                raw = Image.open(png_path)
            except Exception as e:
                print(f"Error opening PNG {png_path}: {e}")
                continue
            try:
                framed = composite_centered_on_square(raw, size, fill_ratio)
                framed.save(png_path)
                png_paths.append(png_path)
            except Exception as e:
                print(f"Error framing PNG {png_path}: {e}")
            finally:
                raw.close()

        if not png_paths:
            print("Failed to generate any PNG files")
            return False

        png_paths.sort(key=size_from_path, reverse=True)
        images: list[Image.Image] = []
        for p in png_paths:
            images.append(Image.open(p))
        try:
            return create_ico_from_images(images, output_path)
        finally:
            for im in images:
                im.close()
    finally:
        for png_path in png_paths:
            try:
                png_path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def generate_ico_from_png(
    png_path: Path,
    output_path: Path | None = None,
    sizes: list | None = None,
    fill_ratio: float = 1.0,
) -> bool:
    """Generate ICO from PNG (resize to multiple sizes), preserving transparency."""
    if sizes is None:
        sizes = [16, 24, 32, 48, 64, 128, 256]

    if output_path is None:
        output_path = png_path.parent / f"{png_path.stem}.ico"

    try:
        base_img = Image.open(png_path)
        # Keep RGBA mode to preserve transparency for rounded corners
        if base_img.mode != "RGBA":
            base_img = base_img.convert("RGBA")
    except Exception as e:
        print(f"Error loading PNG: {e}")
        return False

    images: list[Image.Image] = []
    for size in sizes:
        resized = base_img.resize((size, size), Image.Resampling.LANCZOS)
        if fill_ratio < 1.0:
            resized = composite_centered_on_square(resized, size, fill_ratio)
        images.append(resized)

    return create_ico_from_images(images, output_path)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_PNG = PROJECT_ROOT / "assets" / "owlangs_owl_solid_frontend.png"
FRONTEND_SVG = PROJECT_ROOT / "assets" / "owlangs_owl_solid_frontend.svg"
FRONTEND_WEB_ICO = PROJECT_ROOT / "frontend" / "web" / "favicon.ico"
FRONTEND_WINDOWS_ICO = (
    PROJECT_ROOT / "frontend" / "windows" / "runner" / "resources" / "app_icon.ico"
)
ROOT_FAVICON_ICO = PROJECT_ROOT / "favicon.ico"
LAUNCHER_ICON_ICO = PROJECT_ROOT / "launcher" / "Resources" / "icon.ico"


def generate_frontend_icons(fill_ratio: float = 0.88) -> bool:
    """Build canonical Windows ICO and mirror to web, repo root, launcher (NSIS / PyInstaller).
    
    Uses PNG source by default; falls back to SVG only when PNG is missing.
    """
    FRONTEND_WINDOWS_ICO.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_WEB_ICO.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHER_ICON_ICO.parent.mkdir(parents=True, exist_ok=True)

    source = FRONTEND_PNG if FRONTEND_PNG.exists() else FRONTEND_SVG
    if not source.exists():
        print(f"Error: Frontend icon source not found: {FRONTEND_PNG} (or {FRONTEND_SVG})")
        return False

    print(f"Generating frontend ICO from: {source.name}")

    if source.suffix.lower() == ".png":
        ok = generate_ico_from_png(source, FRONTEND_WINDOWS_ICO, fill_ratio=fill_ratio)
    else:
        ok = generate_ico_from_svg(source, FRONTEND_WINDOWS_ICO, fill_ratio=fill_ratio)

    if not ok:
        return False

    for dest in (FRONTEND_WEB_ICO, ROOT_FAVICON_ICO, LAUNCHER_ICON_ICO):
        shutil.copy2(FRONTEND_WINDOWS_ICO, dest)
        print(f"OK Copied ICO to: {dest}")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Owlangs ICO assets from SVG/PNG.")
    parser.add_argument(
        "--frontend",
        "-f",
        action="store_true",
        help="Generate frontend + Windows installer icons from assets/owlangs_owl_solid_frontend.png (falls back to .svg)",
    )
    parser.add_argument(
        "--fill-ratio",
        type=float,
        default=0.88,
        help="Scale factor inside each square (0-1); default 0.88 improves small-icon readability",
    )
    parser.add_argument("input_path", nargs="?", help="Input .svg or .png")
    parser.add_argument("output_path", nargs="?", help="Output .ico path")
    args = parser.parse_args()

    if args.frontend:
        return 0 if generate_frontend_icons(fill_ratio=args.fill_ratio) else 1

    if not args.input_path:
        parser.print_help()
        return 1

    input_path = Path(args.input_path)
    if not input_path.is_absolute():
        input_path = (PROJECT_ROOT / input_path).resolve()
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return 1

    output_path = Path(args.output_path).resolve() if args.output_path else None
    if output_path and not output_path.is_absolute():
        output_path = (PROJECT_ROOT / output_path).resolve()

    if input_path.suffix.lower() == ".svg":
        ok = generate_ico_from_svg(
            input_path, output_path, fill_ratio=args.fill_ratio
        )
    elif input_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        ok = generate_ico_from_png(
            input_path, output_path, fill_ratio=args.fill_ratio
        )
    else:
        print(f"Error: Unsupported file format: {input_path.suffix}")
        return 1

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
