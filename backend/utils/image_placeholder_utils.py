# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Image placeholder replacement utilities for markdown content."""

import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from logger import unified_logger as logger
from logger.logger import LogModule

# Support placeholder IDs with path characters (e.g., "mobi7/Images/image00044.jpeg")
# Characters allowed: letters, numbers, underscore, dot, slash, hyphen
PLACEHOLDER_PATTERN = re.compile(r"<ph-([a-zA-Z0-9_./-]+)>")


def _replace_placeholders_with_images(
    markdown_content: str, 
    image_data_map: Dict[str, Dict[str, str]], 
    output_dir: Optional[Path] = None,
    update_image_data_map: bool = False
) -> Tuple[str, List[Path]]:
    """
    Replace placeholder tags (<ph-xxxx>) with actual Markdown image syntax using stored image data.
    
    If output_dir is provided, images will be saved as files and markdown will reference file paths.
    Otherwise, images will be embedded as data URIs.
    
    Args:
        markdown_content: Markdown content with placeholders
        image_data_map: Dictionary mapping placeholder IDs to image data
        output_dir: Optional output directory for saving image files
        
    Returns:
        Tuple of (modified_markdown_content, list_of_saved_image_paths)
    """
    if not markdown_content or not image_data_map:
        return markdown_content, []

    saved_image_paths: List[Path] = []
    image_folder_name = "images"
    # Per-invocation counter so every saved image gets a unique filename (avoids overwrite when refs collide)
    _save_counter: List[int] = [0]

    # Create images folder if output_dir is provided
    images_dir: Optional[Path] = None
    if output_dir:
        images_dir = output_dir / image_folder_name
        images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(LogModule.TRANS, f"Created images directory: {images_dir}")

    def _replacement(match: re.Match) -> str:
        # Use module-level logger (closure will capture it)
        placeholder_id = match.group(1)
        image_entry = image_data_map.get(placeholder_id)
        if not image_entry:
            logger.debug(LogModule.RESTOR,f"Placeholder {placeholder_id} not found in image_data_map (available keys: {list(image_data_map.keys())[:5]})")
            return match.group(0)

        data_uri = image_entry.get("data")
        if not data_uri:
            return match.group(0)

        # Use empty alt so path/placeholder_id is not shown next to image in ebooks
        alt_text = image_entry.get("alt") if image_entry.get("alt") is not None else ""
        
        # Determine if this is a formula or table image for size control
        is_formula_or_table = "equation" in alt_text.lower() or "table" in alt_text.lower()
        max_width = "70%" if is_formula_or_table else "90%"
        
        # If output_dir is provided, save image as file
        if output_dir and images_dir and data_uri.startswith("data:image/"):
            try:
                import base64
                import hashlib
                import mimetypes
                
                # Parse data URI: data:image/type;base64,base64data
                if "," in data_uri:
                    header, base64_data = data_uri.split(",", 1)
                    # Extract MIME type from header
                    mime_type = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
                    # Determine file extension
                    extension = mimetypes.guess_extension(mime_type) or ".png"
                    # Unique filename: counter + hash(placeholder_id + data prefix) so no overwrite across images
                    n = _save_counter[0]
                    _save_counter[0] += 1
                    hash_input = (placeholder_id + base64_data[:80]).encode("utf-8")
                    image_id = hashlib.md5(hash_input).hexdigest()[:8]
                    image_filename = f"image_{n:04d}_{image_id}{extension}"
                    logger.debug(LogModule.RESTOR,f"Generated image filename: {image_filename} for placeholder_id: {placeholder_id}")
                    image_path = images_dir / image_filename
                    
                    # Decode and save image
                    image_bytes = base64.b64decode(base64_data)
                    image_path.write_bytes(image_bytes)
                    saved_image_paths.append(image_path)
                    
                    # Return markdown with relative file path
                    # For MD format, keep markdown syntax (not HTML) to ensure compatibility
                    # Images will be rendered at original size by markdown renderers
                    relative_path = f"./{image_folder_name}/{image_filename}"
                    logger.debug(LogModule.RESTOR,f"Saved image to {image_path}, using path {relative_path} in markdown")
                    
                    # If update_image_data_map is True, add entry for the saved file path
                    # This allows MD2DOCXExporter to find the image by file path
                    if update_image_data_map:
                        image_data_map[relative_path] = image_entry.copy()
                        # Also add entry for filename only (without path)
                        image_data_map[image_filename] = image_entry.copy()
                        # Also add entry for filename with images/ prefix
                        image_data_map[f"{image_folder_name}/{image_filename}"] = image_entry.copy()
                        logger.debug(LogModule.RESTOR,f"Updated image_data_map with key: {relative_path} (placeholder_id={placeholder_id})")
                    
                    return f"![{alt_text}]({relative_path})"
            except Exception as e:
                logger.warning(LogModule.RESTOR,f"Failed to save image for placeholder {placeholder_id}: {e}, using data URI instead")
        
        # Fallback: use data URI with markdown syntax
        # Many viewers (e.g. Milkup, some WebViews) limit URL/data-URI length; large images may fail to load
        if len(data_uri) > 100_000:
            logger.warning(
                LogModule.RESTOR,
                f"Embedding large data URI (length={len(data_uri)}) for placeholder {placeholder_id}; "
                "some Markdown viewers may fail to load. Prefer exporting MD with images in folder (ZIP)."
            )
        return f"![{alt_text}]({data_uri})"

    # First, replace <ph-xxx> placeholders
    # Count placeholders before replacement for debugging
    placeholder_matches = list(PLACEHOLDER_PATTERN.finditer(markdown_content))
    logger.debug(LogModule.RESTOR,f"Found {len(placeholder_matches)} image placeholders in markdown content")
    for i, match in enumerate(placeholder_matches):
        placeholder_id = match.group(1)
        logger.debug(LogModule.RESTOR,f"Placeholder {i+1}/{len(placeholder_matches)}: {placeholder_id}, found in image_data_map: {placeholder_id in image_data_map}")
    
    modified_content = PLACEHOLDER_PATTERN.sub(_replacement, markdown_content)
    
    # Count image references after replacement
    image_refs_after = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', modified_content)
    logger.debug(LogModule.RESTOR, f"After replacement: Found {len(image_refs_after)} image references in markdown")
    logger.trace(LogModule.RESTOR, f"After replacement: image references in markdown: {image_refs_after}")
    
    # Then, replace markdown image syntax ![alt](filename.jpg) or ![alt](placeholder_id) with data URIs or file paths
    # This handles equations and tables that are rendered as images
    # Tables use placeholder_id format: ![Table](layoutimg0)
    # Equations use filename format: ![Equation](hash.jpg)
    def _replace_markdown_image(match: re.Match) -> str:
        # Use module-level logger (closure will capture it). Empty alt to avoid visible caption in ebooks.
        alt_text = match.group(1) or ""
        image_ref = match.group(2)  # Can be filename.jpg or placeholder_id (e.g., layoutimg0) or data:image/...;base64,...
        
        # When output_dir is set (e.g. ZIP export): extract data URI images to files so the images folder is populated
        if image_ref.strip().startswith("data:image/") and output_dir and images_dir:
            try:
                import base64
                import hashlib
                import mimetypes
                if "," in image_ref:
                    header, base64_data = image_ref.split(",", 1)
                    mime_type = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
                    extension = mimetypes.guess_extension(mime_type) or ".png"
                    n = _save_counter[0]
                    _save_counter[0] += 1
                    filename_hash = hashlib.md5((image_ref[:200] + base64_data[:100]).encode()).hexdigest()[:8]
                    image_filename_saved = f"image_{n:04d}_{filename_hash}{extension}"
                    image_path = images_dir / image_filename_saved
                    image_bytes = base64.b64decode(base64_data)
                    image_path.write_bytes(image_bytes)
                    saved_image_paths.append(image_path)
                    relative_path = f"./{image_folder_name}/{image_filename_saved}"
                    logger.debug(LogModule.RESTOR, f"Extracted data URI image to {image_path}, using path {relative_path} in markdown")
                    return f"![{alt_text}]({relative_path})"
            except Exception as e:
                logger.warning(LogModule.RESTOR, f"Failed to extract data URI image to file: {e}, keeping data URI in markdown")
        
        # Initialize filename_key for potential use later (for saving images)
        filename_key = None
        
        # First, try direct match (for placeholder IDs like layoutimg0, or exact filename matches)
        image_entry = image_data_map.get(image_ref)
        
        if not image_entry:
            # Try as filename: normalize filename (remove leading ./ or ../, and extract basename)
            normalized_filename = image_ref.lstrip('./').lstrip('../')
            # Try to find image data by filename (basename only, without path)
            filename_key = normalized_filename.split('/')[-1].split('\\')[-1] if '/' in normalized_filename or '\\' in normalized_filename else normalized_filename
            
            # Try exact match first (basename)
            image_entry = image_data_map.get(filename_key)
            if not image_entry:
                # Try matching with normalized filename (without leading ./ or ../)
                image_entry = image_data_map.get(normalized_filename)
            if not image_entry:
                # Try matching with original filename (including path)
                image_entry = image_data_map.get(image_ref)
            
            # If still not found, try case-insensitive matching (some systems may have case differences)
            if not image_entry:
                filename_key_lower = filename_key.lower()
                for key, value in image_data_map.items():
                    if isinstance(key, str):
                        key_basename = key.split('/')[-1].split('\\')[-1] if '/' in key or '\\' in key else key
                        if key_basename.lower() == filename_key_lower or key.lower() == filename_key_lower:
                            image_entry = value
                            logger.debug(LogModule.RESTOR,f"Found image data with case-insensitive match: {key} -> {filename_key}")
                            break
        
        if not image_entry:
            # Log available keys for debugging (first 10 keys)
            available_keys = list(image_data_map.keys())[:10]
            logger.debug(LogModule.RESTOR,f"Image data not found for reference: {image_ref}. Available keys (first 10): {available_keys}")
            return match.group(0)  # Return original if not found
        
        data_uri = image_entry.get("data")
        if not data_uri:
            logger.debug(LogModule.RESTOR,f"Image data URI not found for reference: {image_ref} (entry exists but no data)")
            return match.group(0)  # Return original if no data URI
        
        logger.debug(LogModule.RESTOR,f"Replacing markdown image: {image_ref} -> data URI (length: {len(data_uri)})")
        
        # If output_dir is provided, save image as file
        if output_dir and images_dir and data_uri.startswith("data:image/"):
            try:
                import base64
                import hashlib
                import mimetypes
                
                # Parse data URI: data:image/type;base64,base64data
                if "," in data_uri:
                    header, base64_data = data_uri.split(",", 1)
                    # Extract MIME type from header
                    mime_type = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
                    # Determine file extension
                    extension = mimetypes.guess_extension(mime_type) or ".png"
                    # Unique filename: counter + hash(ref + data) so multiple refs to same path still get distinct files
                    n = _save_counter[0]
                    _save_counter[0] += 1
                    ref_for_hash = filename_key if filename_key is not None else image_ref
                    filename_hash = hashlib.md5((ref_for_hash + base64_data[:100]).encode()).hexdigest()[:8]
                    image_filename_saved = f"image_{n:04d}_{filename_hash}{extension}"
                    image_path = images_dir / image_filename_saved
                    
                    # Decode and save image
                    image_bytes = base64.b64decode(base64_data)
                    image_path.write_bytes(image_bytes)
                    saved_image_paths.append(image_path)
                    
                    # Log image dimensions for debugging
                    try:
                        from PIL import Image
                        import io
                        pil_image = Image.open(io.BytesIO(image_bytes))
                        original_width, original_height = pil_image.size
                        logger.info(LogModule.RESTOR, f"[IMAGE-SIZE] Saved image {image_filename_saved}: original size={original_width}x{original_height} pixels, file_size={len(image_bytes)} bytes")
                    except Exception as img_err:
                        logger.debug(LogModule.RESTOR, f"[IMAGE-SIZE] Failed to get image dimensions for {image_filename_saved}: {img_err}")
                    
                    # Return markdown with relative file path; add to map so later lookups (e.g. Pandoc export) resolve
                    relative_path = f"./{image_folder_name}/{image_filename_saved}"
                    logger.debug(LogModule.RESTOR,f"Saved markdown image to {image_path}, using path {relative_path} in markdown")
                    if update_image_data_map:
                        image_data_map[relative_path] = image_entry.copy()
                        image_data_map[image_filename_saved] = image_entry.copy()
                        image_data_map[f"{image_folder_name}/{image_filename_saved}"] = image_entry.copy()
                    return f"![{alt_text}]({relative_path})"
            except Exception as e:
                logger.warning(LogModule.RESTOR,f"Failed to save markdown image for {image_ref}: {e}, using data URI instead")
        
        # Fallback: use data URI with markdown syntax
        if len(data_uri) > 100_000:
            logger.warning(
                LogModule.RESTOR,
                f"Embedding large data URI (length={len(data_uri)}) for image ref {image_ref}; "
                "some Markdown viewers may fail to load. Prefer exporting MD with images in folder (ZIP)."
            )
        return f"![{alt_text}]({data_uri})"
    
    # Pattern to match markdown image syntax: ![alt](filename.jpg) or ![alt](placeholder_id)
    # This handles equations and tables rendered as images
    # Tables use placeholder_id format: ![Table](layoutimg0)
    # Equations use filename format: ![Equation](hash.jpg)
    # We need to match both formats
    markdown_image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    modified_content = markdown_image_pattern.sub(_replace_markdown_image, modified_content)
    
    return modified_content, saved_image_paths
