#!/bin/bash
# Download fonts script for Linux/Mac
# Downloads Chinese, Korean, and Emoji fonts from Google Fonts

OUTPUT_DIR="${1:-frontend/assets/fonts}"

echo "=== Font Download Script ==="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed. Please install Node.js first."
    echo "Download from: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "Node.js version: $NODE_VERSION"

# Check if npx is available
if ! command -v npx &> /dev/null; then
    echo "Error: npx is not available. Please ensure Node.js is properly installed."
    exit 1
fi

NPX_VERSION=$(npx --version)
echo "npx version: $NPX_VERSION"
echo ""

# Create output directory if it doesn't exist
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Creating output directory: $OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR"
fi

# Get absolute path
ABSOLUTE_OUTPUT_DIR=$(cd "$OUTPUT_DIR" && pwd)
echo "Output directory: $ABSOLUTE_OUTPUT_DIR"
echo ""

# Download fonts using google-font-downloader
echo "Downloading fonts..."
echo "  - Roboto: 300, 400, 500, 700, 400i"
echo "  - Noto Sans SC (Chinese Simplified): 400"
echo "  - Noto Sans KR (Korean): 400"
echo "  - Noto Sans JP (Japanese): 400"
echo "  - Noto Sans: 400"
echo "  - Noto Color Emoji: 400"
echo ""

# Build Google Fonts API URL
# Format: https://fonts.googleapis.com/css?family=Font1:weights&family=Font2:weights
# We download all required fonts: Roboto, Noto Sans SC/KR/JP, Noto Sans, Noto Color Emoji
FONT_URL="https://fonts.googleapis.com/css?family=Roboto:300,400,500,700,400i&family=Noto+Sans+SC:400&family=Noto+Sans+KR:400&family=Noto+Sans+JP:400&family=Noto+Sans:400&family=Noto+Color+Emoji:400"

echo "Using font URL: $FONT_URL"
echo ""

# Download fonts by parsing CSS and downloading files directly
echo "Fetching font CSS..."
# Use modern browser User-Agent to get WOFF2 format (if available)
# Google Fonts returns different formats based on User-Agent
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CSS_CONTENT=$(curl -s -H "User-Agent: $USER_AGENT" "$FONT_URL")

if [ -z "$CSS_CONTENT" ]; then
    echo "✗ Error: Failed to fetch font CSS"
    exit 1
fi

# Extract font file URLs from CSS - prioritize WOFF2, then TTF
# Pattern: url(https://fonts.gstatic.com/...)
# We want both WOFF2 (for Web) and TTF (for desktop/mobile)
WOFF2_URLS=$(echo "$CSS_CONTENT" | grep -oP 'url\(https://fonts\.gstatic\.com/[^)]+\.woff2\)' | sed 's/url(//;s/)//')
TTF_URLS=$(echo "$CSS_CONTENT" | grep -oP 'url\(https://fonts\.gstatic\.com/[^)]+\.ttf\)' | sed 's/url(//;s/)//')

# Combine URLs, prioritizing WOFF2
FONT_URLS=""
if [ -n "$WOFF2_URLS" ]; then
    FONT_URLS="$WOFF2_URLS"$'\n'
fi
if [ -n "$TTF_URLS" ]; then
    FONT_URLS="$FONT_URLS$TTF_URLS"
fi

if [ -z "$FONT_URLS" ]; then
    echo "✗ Error: No font URLs found in CSS"
    exit 1
fi

WOFF2_COUNT=$(echo "$WOFF2_URLS" | grep -c . || echo "0")
TTF_COUNT=$(echo "$TTF_URLS" | grep -c . || echo "0")
FONT_COUNT=$((WOFF2_COUNT + TTF_COUNT))

echo "Found $FONT_COUNT font files to download"
echo "  - WOFF2 files: $WOFF2_COUNT (Web optimized)"
echo "  - TTF files: $TTF_COUNT (Universal format)"
echo ""

DOWNLOADED_COUNT=0
SKIPPED_COUNT=0

# Download each font file
echo "$FONT_URLS" | while read -r font_url; do
    if [ -z "$font_url" ]; then
        continue
    fi
    
    # Extract filename from URL
    filename=$(basename "$font_url" | sed 's/?.*//')
    
    # Filter out dynamic subset fonts (Flutter doesn't need them)
    # These are typically:
    # - Files with hash-like names starting with 'KF' (Google Fonts dynamic subsets)
    #   Pattern: KF followed by 30+ alphanumeric/underscore/hyphen characters
    # - Files with very short names or unusual patterns
    # - Files that are subsets for specific unicode ranges
    if echo "$filename" | grep -qE '^KF[A-Z0-9_-]{30,}\.ttf$' || \
       echo "$filename" | grep -qE '^[A-Z0-9]{30,}\.[0-9]+\.woff2$' || \
       echo "$filename" | grep -qE '\.(118|117|107|95|84|2)\.woff2$'; then
        echo "  ⊘ Skipped (dynamic subset, not needed): $filename"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    
    # Skip if file already exists
    dest_path="$ABSOLUTE_OUTPUT_DIR/$filename"
    if [ -f "$dest_path" ]; then
        echo "  ⊘ Skipped (exists): $filename"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    
    # Download font file
    echo "  ↓ Downloading: $filename"
    if curl -s -L "$font_url" -o "$dest_path"; then
        echo "    ✓ Downloaded: $filename"
        DOWNLOADED_COUNT=$((DOWNLOADED_COUNT + 1))
    else
        echo "    ✗ Failed: $filename"
        [ -f "$dest_path" ] && rm -f "$dest_path"
    fi
done

echo ""
echo "Download summary:"
echo "  ✓ Downloaded: $DOWNLOADED_COUNT files"
if [ $SKIPPED_COUNT -gt 0 ]; then
    echo "  ⊘ Skipped: $SKIPPED_COUNT files (already exist or dynamic subsets)"
fi

if [ $DOWNLOADED_COUNT -eq 0 ] && [ $SKIPPED_COUNT -eq 0 ]; then
    echo "✗ Error: No fonts were downloaded"
    exit 1
fi

echo ""
echo "✓ Fonts downloaded successfully!"
echo ""
echo "Downloaded fonts:"
echo "  WOFF2 files:"
find "$ABSOLUTE_OUTPUT_DIR" -maxdepth 1 -name "*.woff2" -type f | sort | while read -r file; do
    size_kb=$(du -h "$file" | cut -f1)
    echo "    - $(basename "$file") ($size_kb)"
done
echo "  TTF files:"
find "$ABSOLUTE_OUTPUT_DIR" -maxdepth 1 -name "*.ttf" -type f | sort | while read -r file; do
    size_kb=$(du -h "$file" | cut -f1)
    echo "    - $(basename "$file") ($size_kb)"
done

echo ""
echo "=== Download Complete ==="

