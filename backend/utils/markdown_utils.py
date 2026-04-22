# SPDX-FileCopyrightText: 2026 Zampherssss
# SPDX-License-Identifier: MPL-2.0
import base64
import hashlib
import io
import mimetypes
import os
import re
import threading
import uuid
import zipfile
from pathlib import Path
import tempfile


class MaskDict:
    def __init__(self):
        self._dict = {}
        self._lock = threading.Lock()

    def create_id(self):
        with self._lock:
            while True:
                id = uuid.uuid1().hex[:6]
                if id not in self._dict:
                    return id

    def get(self, key):
        with self._lock:
            return self._dict.get(key)

    def set(self, key, value):
        with self._lock:
            self._dict[key] = value

    def delete(self, key):
        with self._lock:
            if key in self._dict:
                del self._dict[key]

    def __contains__(self, item):
        with self._lock:
            return item in self._dict


# def uris2placeholder(markdown:str, mask_dict:MaskDict):
## Replace entire URI
#     def uri2placeholder(match: re.Match):
#         id = mask_dict.create_id()
#         mask_dict.set(id, match.group())
#         return f"<ph-{id}>"
#
#     uri_pattern = r'!?\[.*?\]\(.*?\)'
#     markdown = re.sub(uri_pattern, uri2placeholder, markdown)
#     return markdown

def uris2placeholder(markdown: str, mask_dict: MaskDict):
    ## Only replace the link part in URI, keep the title
    def uri2placeholder(match: re.Match):
        id = mask_dict.create_id()
        # Only replace base64 data
        # mask_dict.set(id, match.group(2))
        # return f"{match.group(1)}(<ph-{id}>)"

        # Replace entire image with placeholder
        mask_dict.set(id, match.group())
        return f"<ph-{id}>"

    uri_pattern = r'(!\[.*?\])\((.*?)\)'
    markdown = re.sub(uri_pattern, uri2placeholder, markdown)
    return markdown


def placeholder2uris(markdown: str, mask_dict: MaskDict):
    def placeholder2uri(match: re.Match):
        id = match.group(1)
        uri = mask_dict.get(id)
        if uri is None:
            return match.group()
        return uri

    ph_pattern = r"<ph-([a-zA-Z0-9]+)>"
    markdown = re.sub(ph_pattern, placeholder2uri, markdown)
    return markdown


def find_markdown_in_zip(zip_bytes: bytes):
    zip_file_bytes = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(zip_file_bytes, 'r') as zip_ref:
        # Get all file names in ZIP
        all_files = zip_ref.namelist()
        # Filter out .md files
        md_files = [f for f in all_files if f.lower().endswith('.md')]

        if len(md_files) == 1:
            return md_files[0]
        elif len(md_files) > 1:
            raise ValueError("ZIP contains multiple Markdown files")
        else:
            raise ValueError("No Markdown files found in ZIP")


def embed_inline_image_from_zip(zip_bytes: bytes, filename_in_zip: str, encoding="utf-8"):
    zip_file_bytes = io.BytesIO(zip_bytes)

    print(f"Attempting to open ZIP archive in memory...")
    with zipfile.ZipFile(zip_file_bytes, 'r') as archive:
        print(f"ZIP archive opened. Looking for file '{filename_in_zip}'...")

        if filename_in_zip not in archive.namelist():
            available_files = archive.namelist()
            error_msg = (
                f"MinerU parsing failed: Required file '{filename_in_zip}' not found in ZIP archive.\n"
                f"Available files in archive: {available_files}\n"
                f"This usually indicates a MinerU API parsing error. Please check the MinerU API response."
            )
            print(f"Error: {error_msg}")
            raise FileNotFoundError(error_msg)

        md_content_bytes = archive.read(filename_in_zip)
        print(f"File '{filename_in_zip}' found and read.")
        # Robust decoding with fallback encodings
        try:
            md_content_text = md_content_bytes.decode(encoding)
        except UnicodeDecodeError:
            # Try UTF-8 with BOM
            try:
                md_content_text = md_content_bytes.decode('utf-8-sig')
                print(f"File content successfully decoded using 'utf-8-sig' encoding (fallback).")
            except UnicodeDecodeError:
                # Try common encodings
                for fallback_encoding in ['gbk', 'gb2312', 'latin-1', 'cp1252']:
                    try:
                        md_content_text = md_content_bytes.decode(fallback_encoding)
                        print(f"File content successfully decoded using '{fallback_encoding}' encoding (fallback).")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # Final fallback: UTF-8 with error replacement
                    md_content_text = md_content_bytes.decode('utf-8', errors='replace')
                    print(f"File content decoded using 'utf-8' with error replacement (fallback).")
        else:
            print(f"File content successfully decoded using '{encoding}' encoding.")

        # --- New: Process images ---
        print("Starting to process images in Markdown...")
        # Get the base directory of the Markdown file within the ZIP package for parsing relative image paths
        # For example, if filename_in_zip is "docs/guide/full.md", base_md_path_in_zip is "docs/guide"
        # If filename_in_zip is "full.md", base_md_path_in_zip is ""
        base_md_path_in_zip = os.path.dirname(filename_in_zip)

        def replace_image_with_base64(match):
            alt_text = match.group(1)
            original_image_path = match.group(2)

            # Check if it's an external link or already a data URI
            if original_image_path.startswith(('http://', 'https://', 'data:')):
                print(f"  Skipping external or already inline image: {original_image_path}")
                return match.group(0)  # Return original match

            # Build absolute path of image in ZIP file
            # os.path.join will correctly handle the case where base_md_path_in_zip is an empty string
            image_path_in_zip = os.path.join(base_md_path_in_zip, original_image_path)
            # zipfile uses forward slashes and paths are relative to zip root, os.path.normpath ensures correct path format
            image_path_in_zip = os.path.normpath(image_path_in_zip).replace(os.sep, '/')

            # Ensure path doesn't start with './', if filename_in_zip is in root directory and image path is also relative
            if image_path_in_zip.startswith('./'):
                image_path_in_zip = image_path_in_zip[2:]

            # print(f"  Attempting to inline image: '{original_image_path}' (resolved to ZIP path: '{image_path_in_zip}')")

            try:
                image_bytes = archive.read(image_path_in_zip)

                # Guess MIME type
                mime_type, _ = mimetypes.guess_type(image_path_in_zip)
                if not mime_type:
                    # Fallback: manually determine some common types based on extension
                    ext = os.path.splitext(image_path_in_zip)[1].lower()
                    if ext == '.png':
                        mime_type = 'image/png'
                    elif ext in ['.jpg', '.jpeg']:
                        mime_type = 'image/jpeg'
                    elif ext == '.gif':
                        mime_type = 'image/gif'
                    elif ext == '.svg':
                        mime_type = 'image/svg+xml'
                    elif ext == '.webp':
                        mime_type = 'image/webp'
                    else:
                        print(f"    Warning: Unable to determine MIME type for image '{image_path_in_zip}'. Skipping inline.")
                        return match.group(0)  # Return original match

                base64_encoded_data = base64.b64encode(image_bytes).decode('utf-8')
                new_image_tag = f"![{alt_text}](data:{mime_type};base64,{base64_encoded_data})"
                # print(f"    Successfully inlined image: {original_image_path} -> data:{mime_type[:20]}...")
                return new_image_tag
            except KeyError:
                print(f"    Warning: Image '{image_path_in_zip}' not found in ZIP archive. Original link will be preserved.")
                return match.group(0)  # Image not in zip, return original match
            except Exception as e_img:
                print(f"    Error: Error occurred while processing image '{image_path_in_zip}': {e_img}. Original link will be preserved.")
                return match.group(0)

        # Regular expression to find Markdown images: ![alt text](path/to/image.ext)
        # Modified regex to non-greedily match alt text and paths
        image_regex = r"!\[(.*?)\]\((.*?)\)"
        modified_md_content = re.sub(image_regex, replace_image_with_base64, md_content_text)

        # Ensure consistent newline format (use Unix-style \n)
        modified_md_content = modified_md_content.replace('\r\n', '\n')

        print("Image processing completed.")
        return modified_md_content


def embed_inline_image_from_dir(extracted_dir: str, filename_in_dir: str, encoding="utf-8"):
    """
    Embed images from a directory extracted from a ZIP file into a Markdown file as inline base64 data.
    
    Args:
        extracted_dir: Path to the directory where the ZIP file was extracted
        filename_in_dir: Path to the Markdown file within the extracted directory
        encoding: Encoding to use when reading the Markdown file
    """
    print(f"Attempting to read Markdown from extracted directory: {extracted_dir}...")
    
    # Construct the full path to the Markdown file
    md_file_path = os.path.join(extracted_dir, filename_in_dir)
    print(f"Looking for Markdown file at: {md_file_path}...")
    
    if not os.path.exists(md_file_path):
        # Fallback: scan the extracted directory for the first .md file
        md_candidates = []
        for root, dirs, files in os.walk(extracted_dir):
            for file in files:
                if file.lower().endswith('.md'):
                    rel_path = os.path.relpath(os.path.join(root, file), extracted_dir)
                    md_candidates.append(rel_path)
        if md_candidates:
            # Prefer 'full.md' if it exists somewhere in the tree, otherwise first .md
            filename_in_dir = next(
                (c for c in md_candidates if os.path.basename(c).lower() == 'full.md'),
                md_candidates[0]
            )
            md_file_path = os.path.join(extracted_dir, filename_in_dir)
            print(f"[FALLBACK] '{filename_in_dir}' not found at root; using scanned markdown file: {md_file_path}")
        else:
            error_msg = (
                f"MinerU parsing failed: No markdown file found in extracted directory.\n"
                f"Full path checked: {md_file_path}\n"
                f"Scanned files: {md_candidates}\n"
                f"This usually indicates a MinerU API parsing error or extraction issue."
            )
            print(f"Error: {error_msg}")
            raise FileNotFoundError(error_msg)
    
    # Read the Markdown file
    with open(md_file_path, 'rb') as f:
        md_content_bytes = f.read()
    print(f"File '{filename_in_dir}' found and read.")
    # Robust decoding with fallback encodings
    try:
        md_content_text = md_content_bytes.decode(encoding)
    except UnicodeDecodeError:
        # Try UTF-8 with BOM
        try:
            md_content_text = md_content_bytes.decode('utf-8-sig')
            print(f"File content successfully decoded using 'utf-8-sig' encoding (fallback).")
        except UnicodeDecodeError:
            # Try common encodings
            for fallback_encoding in ['gbk', 'gb2312', 'latin-1', 'cp1252']:
                try:
                    md_content_text = md_content_bytes.decode(fallback_encoding)
                    print(f"File content successfully decoded using '{fallback_encoding}' encoding (fallback).")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Final fallback: UTF-8 with error replacement
                md_content_text = md_content_bytes.decode('utf-8', errors='replace')
                print(f"File content decoded using 'utf-8' with error replacement (fallback).")
    else:
        print(f"File content successfully decoded using '{encoding}' encoding.")
    
    # --- Process images ---
    print("Starting to process images in Markdown...")
    # Get the base directory of the Markdown file within the extracted directory
    base_md_path = os.path.dirname(filename_in_dir)
    
    def replace_image_with_base64_from_dir(match):
        alt_text = match.group(1)
        original_image_path = match.group(2)
        
        # Check if it's an external link or already a data URI
        if original_image_path.startswith(('http://', 'https://', 'data:')):
            print(f"  Skipping external or already inline image: {original_image_path}")
            return match.group(0)  # Return original match
        
        # Build absolute path of image in extracted directory
        image_path = os.path.join(base_md_path, original_image_path)
        image_path = os.path.normpath(image_path)
        # Remove any leading './' if present
        if image_path.startswith('./'):
            image_path = image_path[2:]
        
        full_image_path = os.path.join(extracted_dir, image_path)
        # print(f"  Attempting to inline image: '{original_image_path}' (resolved to: '{full_image_path}')")
        
        try:
            # Read image file
            with open(full_image_path, 'rb') as img_file:
                image_bytes = img_file.read()
            
            # Guess MIME type
            mime_type, _ = mimetypes.guess_type(full_image_path)
            if not mime_type:
                # Fallback: manually determine some common types based on extension
                ext = os.path.splitext(full_image_path)[1].lower()
                if ext == '.png':
                    mime_type = 'image/png'
                elif ext in ['.jpg', '.jpeg']:
                    mime_type = 'image/jpeg'
                elif ext == '.gif':
                    mime_type = 'image/gif'
                elif ext == '.svg':
                    mime_type = 'image/svg+xml'
                elif ext == '.webp':
                    mime_type = 'image/webp'
                else:
                    print(f"    Warning: Unable to determine MIME type for image '{full_image_path}'. Skipping inline.")
                    return match.group(0)  # Return original match
            
            base64_encoded_data = base64.b64encode(image_bytes).decode('utf-8')
            new_image_tag = f"![{alt_text}](data:{mime_type};base64,{base64_encoded_data})"
            # print(f"    Successfully inlined image: {original_image_path} -> data:{mime_type[:20]}...")
            return new_image_tag
        except (FileNotFoundError, PermissionError) as e:
            print(f"    Warning: Image '{full_image_path}' not found or cannot be read: {e}. Original link will be preserved.")
            return match.group(0)  # Return original match
    
    # Process all image links in Markdown content
    md_content_with_inline_images = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image_with_base64_from_dir, md_content_text)
    
    # Ensure consistent newline format (use Unix-style \n)
    md_content_with_inline_images = md_content_with_inline_images.replace('\r\n', '\n')
    
    _img_ref_count = len(re.findall(r'!\[(.*?)\]\((.*?)\)', md_content_text))
    print(f"Inline image processing completed. Found and processed {_img_ref_count} image references.")
    
    return md_content_with_inline_images


def unembed_base64_images_to_zip(markdown:str,markdown_name:str,image_folder_name="images")->bytes:
    with tempfile.TemporaryDirectory() as temp_dir:
        image_folder=os.path.join(temp_dir,image_folder_name)
        os.makedirs(image_folder,exist_ok=True)
        pattern=r"!\[(.*?)\]\(data:(.*?);.*base64,(.*)\)"
        def unembed_base64_images(match:re.Match)->str:
            b64data = match.group(3)
            extension=mimetypes.guess_extension(match.group(2))
            image_id=hashlib.md5(b64data.encode()).hexdigest()[:8]
            image_name=f"{image_id}{extension}"
            url=f"./{image_folder_name}/{image_name}"
            # Create corresponding image file
            with open(os.path.join(image_folder,image_name),"wb") as f:
                f.write(base64.b64decode(b64data))
            return f"![{match.group(1)}]({url})"
        modified_md_content = re.sub(pattern, unembed_base64_images,markdown)
        with open(os.path.join(temp_dir,f"{markdown_name}"),"w",encoding="utf-8") as f:
            f.write(modified_md_content)
        zip_buffer=io.BytesIO()
        folder_path=Path(temp_dir)
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in folder_path.rglob('*'):
                if file.is_file():
                    zipf.write(file, file.relative_to(folder_path))
    return zip_buffer.getvalue()


# Placeholder marker format: Use a complex format to avoid conflicts with original text
# Format: __OWLANGS_IMAGE_PLACEHOLDER_START__{id}__OWLANGS_IMAGE_PLACEHOLDER_END__
PLACEHOLDER_START_MARKER = "__OWLANGS_IMAGE_PLACEHOLDER_START__"
PLACEHOLDER_END_MARKER = "__OWLANGS_IMAGE_PLACEHOLDER_END__"
PLACEHOLDER_PATTERN = re.compile(
    rf"{re.escape(PLACEHOLDER_START_MARKER)}([a-zA-Z0-9]+){re.escape(PLACEHOLDER_END_MARKER)}"
)


class PlaceholderTracker:
    """Track placeholder positions in text for restoration after translation"""
    def __init__(self):
        self.placeholders = []  # List of (placeholder_id, original_placeholder_text, position_in_text)
        self.chunk_placeholders = {}  # {chunk_index: [(placeholder_id, position_in_chunk), ...]}
    
    def record(self, placeholder_id: str, original_placeholder: str, position: int, chunk_index: int = -1):
        """Record a placeholder position"""
        self.placeholders.append((placeholder_id, original_placeholder, position))
        if chunk_index >= 0:
            if chunk_index not in self.chunk_placeholders:
                self.chunk_placeholders[chunk_index] = []
            self.chunk_placeholders[chunk_index].append((placeholder_id, position))


def wrap_placeholder_with_marker(placeholder_id: str) -> str:
    """Wrap placeholder ID with markers for translation"""
    return f"{PLACEHOLDER_START_MARKER}{placeholder_id}{PLACEHOLDER_END_MARKER}"


def unwrap_placeholder_marker(marked_text: str) -> str:
    """Extract placeholder ID from marked text"""
    match = PLACEHOLDER_PATTERN.match(marked_text)
    if match:
        return match.group(1)
    return None


def replace_placeholders_with_markers(text: str, mask_dict: MaskDict) -> tuple[str, PlaceholderTracker]:
    """
    Replace <ph-xxx> placeholders with marked placeholders for translation
    
    Args:
        text: Text containing <ph-xxx> placeholders
        mask_dict: Dictionary mapping placeholder IDs to original image tags
    
    Returns:
        (marked_text, tracker): Text with marked placeholders and tracker
    """
    tracker = PlaceholderTracker()
    ph_pattern = r"<ph-([a-zA-Z0-9]+)>"
    
    def replace_with_marker(match: re.Match):
        placeholder_id = match.group(1)
        original_placeholder = match.group(0)
        start_pos = match.start()
        
        # Record placeholder
        tracker.record(placeholder_id, original_placeholder, start_pos)
        
        # Replace with marked placeholder
        return wrap_placeholder_with_marker(placeholder_id)
    
    marked_text = re.sub(ph_pattern, replace_with_marker, text)
    return marked_text, tracker


def remove_placeholders_for_translation(text: str, tracker: PlaceholderTracker = None) -> tuple[str, PlaceholderTracker]:
    """
    Remove marked placeholders from text before translation
    
    Args:
        text: Text with marked placeholders
        tracker: Optional existing tracker (will create new if None)
    
    Returns:
        (clean_text, tracker): Text without placeholders and tracker with positions
    """
    if tracker is None:
        tracker = PlaceholderTracker()
    
    # Find all marked placeholders
    matches = list(PLACEHOLDER_PATTERN.finditer(text))
    
    # Record positions before removal
    for match in matches:
        placeholder_id = unwrap_placeholder_marker(match.group(0))
        if placeholder_id:
            start_pos = match.start()
            tracker.record(placeholder_id, match.group(0), start_pos)
    
    # Remove marked placeholders
    clean_text = PLACEHOLDER_PATTERN.sub("", text)
    
    return clean_text, tracker


def restore_placeholders_after_translation(
    translated_text: str,
    original_text: str,
    tracker: PlaceholderTracker,
    mask_dict: MaskDict
) -> str:
    """
    Restore placeholders to translated text using intelligent context matching.
    
    Strategy: Since placeholders are removed before translation, we need to find
    where they should be inserted in the translated text. We use the context
    (text before and after the placeholder in the original marked text) to
    locate insertion points in the translated text.
    
    Args:
        translated_text: Translated text without placeholders
        original_text: Original text with marked placeholders (for reference)
        tracker: Placeholder tracker with position information
        mask_dict: Dictionary mapping placeholder IDs to original image tags
    
    Returns:
        Text with restored <ph-xxx> placeholders
    """
    if not tracker.placeholders:
        return translated_text
    
    # Find marked placeholders in original text
    original_matches = list(PLACEHOLDER_PATTERN.finditer(original_text))
    
    if not original_matches:
        return translated_text
    
    result = translated_text
    
    # Sort placeholders by position in original text (reverse order for safe insertion)
    sorted_placeholders = sorted(tracker.placeholders, key=lambda x: x[2], reverse=True)
    
    for placeholder_id, original_marked, original_pos in sorted_placeholders:
        # Get original image tag from mask_dict
        original_image_tag = mask_dict.get(placeholder_id)
        if not original_image_tag:
            continue
        
        # Find the marked placeholder in original text
        marked_placeholder = wrap_placeholder_with_marker(placeholder_id)
        marked_pos = original_text.find(marked_placeholder)
        
        if marked_pos == -1:
            continue
        
        # Extract context: text before and after the placeholder
        # Use more context for better matching (up to 100 chars each side)
        context_before_start = max(0, marked_pos - 100)
        context_before = original_text[context_before_start:marked_pos].strip()
        context_after_end = marked_pos + len(marked_placeholder) + 100
        context_after = original_text[marked_pos + len(marked_placeholder):context_after_end].strip()
        
        # Remove any marked placeholders from context (they won't be in translated text)
        context_before_clean = PLACEHOLDER_PATTERN.sub("", context_before)
        context_after_clean = PLACEHOLDER_PATTERN.sub("", context_after)
        
        # Try to find insertion position using context matching
        insert_pos = -1
        
        # Strategy 1: Find context_before in translated text (prefer end of match)
        if context_before_clean:
            # Use last 30-50 chars for matching (more reliable than full context)
            search_text = context_before_clean[-50:] if len(context_before_clean) > 50 else context_before_clean
            # Try to find this text in translated text
            pos = result.rfind(search_text)
            if pos != -1:
                insert_pos = pos + len(search_text)
        
        # Strategy 2: If context_before didn't work, try context_after
        if insert_pos == -1 and context_after_clean:
            search_text = context_after_clean[:50] if len(context_after_clean) > 50 else context_after_clean
            pos = result.find(search_text)
            if pos != -1:
                insert_pos = pos
        
        # Strategy 3: If still no match, try to find by relative position
        # (e.g., if placeholder was at 30% of original text, insert at 30% of translated text)
        if insert_pos == -1:
            # Calculate relative position in original text
            if len(original_text) > 0:
                relative_pos = marked_pos / len(original_text)
                insert_pos = int(len(result) * relative_pos)
            else:
                insert_pos = len(result)
        
        # Insert placeholder
        placeholder_tag = f"<ph-{placeholder_id}>"
        result = result[:insert_pos] + placeholder_tag + result[insert_pos:]
    
    return result


if __name__ == '__main__':
    pass

