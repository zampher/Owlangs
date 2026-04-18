"""
Compare layout extraction results from PyMuPDF and MinerU.

This script compares bbox coordinates, block counts, and page dimensions
between PyMuPDF and MinerU layout extraction outputs.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_pymupdf_blocks(pymupdf_data: Dict[str, Any], page_index: int) -> List[Dict[str, Any]]:
    """Extract blocks from PyMuPDF output for a specific page."""
    for page in pymupdf_data.get("pages", []):
        if page.get("page_index") == page_index:
            return page.get("blocks", [])
    return []


def extract_mineru_blocks(mineru_data: Dict[str, Any], page_index: int) -> List[Dict[str, Any]]:
    """Extract blocks from MinerU layout.json for a specific page."""
    pdf_info = mineru_data.get("pdf_info", [])
    if page_index < len(pdf_info):
        page_data = pdf_info[page_index]
        # Combine para_blocks and discarded_blocks
        para_blocks = page_data.get("para_blocks", [])
        discarded_blocks = page_data.get("discarded_blocks", [])
        return para_blocks + discarded_blocks
    return []


def normalize_bbox(bbox: List[float] | Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    """Normalize bbox to (x0, y0, x1, y1) format."""
    if len(bbox) == 4:
        return tuple(float(x) for x in bbox)
    return (0.0, 0.0, 0.0, 0.0)


def get_block_text(block: Dict[str, Any]) -> str:
    """Extract text from a block (MinerU or PyMuPDF format)."""
    # PyMuPDF format
    if "text" in block:
        return block["text"].strip()
    
    # MinerU format - extract from lines -> spans -> content
    text_parts = []
    lines = block.get("lines", [])
    for line in lines:
        if not isinstance(line, dict):
            continue
        spans = line.get("spans", [])
        for span in spans:
            if not isinstance(span, dict):
                continue
            content = span.get("content")
            if content:
                text_parts.append(str(content))
            elif span.get("type") == "text":
                text = span.get("text")
                if text:
                    text_parts.append(str(text))
    
    return " ".join(text_parts).strip()


def compare_page(
    pymupdf_blocks: List[Dict[str, Any]],
    mineru_blocks: List[Dict[str, Any]],
    page_index: int,
    pymupdf_page: Dict[str, Any],
    mineru_page: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare blocks from PyMuPDF and MinerU for a single page."""
    result = {
        "page_index": page_index,
        "pymupdf_page_size": {
            "width": pymupdf_page.get("width"),
            "height": pymupdf_page.get("height")
        },
        "mineru_page_size": {
            "width": mineru_page.get("page_size", [None, None])[0],
            "height": mineru_page.get("page_size", [None, None])[1]
        },
        "pymupdf_block_count": len(pymupdf_blocks),
        "mineru_block_count": len(mineru_blocks),
        "comparisons": []
    }
    
    # Compare page dimensions
    pymupdf_w = pymupdf_page.get("width")
    pymupdf_h = pymupdf_page.get("height")
    mineru_size = mineru_page.get("page_size", [])
    mineru_w = mineru_size[0] if len(mineru_size) > 0 else None
    mineru_h = mineru_size[1] if len(mineru_size) > 1 else None
    
    if pymupdf_w and mineru_w:
        w_diff = abs(pymupdf_w - mineru_w)
        result["page_width_diff"] = w_diff
        result["page_width_diff_percent"] = (w_diff / mineru_w * 100) if mineru_w > 0 else 0
    
    if pymupdf_h and mineru_h:
        h_diff = abs(pymupdf_h - mineru_h)
        result["page_height_diff"] = h_diff
        result["page_height_diff_percent"] = (h_diff / mineru_h * 100) if mineru_h > 0 else 0
    
    # Try to match blocks by text content and position
    # For each MinerU block, find the closest PyMuPDF block
    for mu_idx, mu_block in enumerate(mineru_blocks):
        mu_bbox = normalize_bbox(mu_block.get("bbox", []))
        mu_text = get_block_text(mu_block)
        mu_type = mu_block.get("type", "unknown")
        
        # Find closest PyMuPDF block by bbox overlap
        best_match = None
        best_overlap = 0.0
        best_distance = float("inf")
        
        for pm_idx, pm_block in enumerate(pymupdf_blocks):
            pm_bbox = normalize_bbox(pm_block.get("bbox", []))
            pm_text = get_block_text(pm_block)
            
            # Calculate bbox overlap (IoU - Intersection over Union)
            x0_overlap = max(mu_bbox[0], pm_bbox[0])
            y0_overlap = max(mu_bbox[1], pm_bbox[1])
            x1_overlap = min(mu_bbox[2], pm_bbox[2])
            y1_overlap = min(mu_bbox[3], pm_bbox[3])
            
            if x0_overlap < x1_overlap and y0_overlap < y1_overlap:
                overlap_area = (x1_overlap - x0_overlap) * (y1_overlap - y0_overlap)
                mu_area = (mu_bbox[2] - mu_bbox[0]) * (mu_bbox[3] - mu_bbox[1])
                pm_area = (pm_bbox[2] - pm_bbox[0]) * (pm_bbox[3] - pm_bbox[1])
                union_area = mu_area + pm_area - overlap_area
                
                if union_area > 0:
                    iou = overlap_area / union_area
                    if iou > best_overlap:
                        best_overlap = iou
                        best_match = {
                            "pymupdf_index": pm_idx,
                            "pymupdf_bbox": pm_bbox,
                            "pymupdf_text": pm_text[:100],  # Truncate for display
                            "iou": iou
                        }
            
            # Also calculate center distance as fallback
            mu_center_x = (mu_bbox[0] + mu_bbox[2]) / 2
            mu_center_y = (mu_bbox[1] + mu_bbox[3]) / 2
            pm_center_x = (pm_bbox[0] + pm_bbox[2]) / 2
            pm_center_y = (pm_bbox[1] + pm_bbox[3]) / 2
            
            distance = ((mu_center_x - pm_center_x) ** 2 + (mu_center_y - pm_center_y) ** 2) ** 0.5
            if distance < best_distance and best_match is None:
                best_distance = distance
                best_match = {
                    "pymupdf_index": pm_idx,
                    "pymupdf_bbox": pm_bbox,
                    "pymupdf_text": pm_text[:100],
                    "distance": distance
                }
        
        # Calculate bbox differences
        bbox_diff = {
            "x0_diff": 0.0,
            "y0_diff": 0.0,
            "x1_diff": 0.0,
            "y1_diff": 0.0,
            "width_diff": 0.0,
            "height_diff": 0.0
        }
        
        if best_match:
            pm_bbox = best_match["pymupdf_bbox"]
            bbox_diff["x0_diff"] = mu_bbox[0] - pm_bbox[0]
            bbox_diff["y0_diff"] = mu_bbox[1] - pm_bbox[1]
            bbox_diff["x1_diff"] = mu_bbox[2] - pm_bbox[2]
            bbox_diff["y1_diff"] = mu_bbox[3] - pm_bbox[3]
            bbox_diff["width_diff"] = (mu_bbox[2] - mu_bbox[0]) - (pm_bbox[2] - pm_bbox[0])
            bbox_diff["height_diff"] = (mu_bbox[3] - mu_bbox[1]) - (pm_bbox[3] - pm_bbox[1])
        
        comparison = {
            "mineru_index": mu_idx,
            "mineru_type": mu_type,
            "mineru_bbox": list(mu_bbox),
            "mineru_text": mu_text[:100],  # Truncate
            "match": best_match,
            "bbox_differences": bbox_diff
        }
        
        result["comparisons"].append(comparison)
    
    return result


def main():
    """Main comparison function."""
    base_path = Path("test-doc/mineru_sample")
    pymupdf_path = base_path / "c9097029-cced-46f0-b8e9-413728ea1f81_origin_pymupdf_layout.json"
    mineru_path = base_path / "layout.json"
    
    print("Loading layout files...")
    pymupdf_data = load_json(pymupdf_path)
    mineru_data = load_json(mineru_path)
    
    print(f"PyMuPDF: {pymupdf_data.get('page_count')} pages")
    print(f"MinerU: {len(mineru_data.get('pdf_info', []))} pages")
    
    # Compare each page
    all_results = []
    for page_idx in range(min(pymupdf_data.get("page_count", 0), len(mineru_data.get("pdf_info", [])))):
        print(f"\n{'='*80}")
        print(f"Comparing Page {page_idx}")
        print(f"{'='*80}")
        
        pymupdf_blocks = extract_pymupdf_blocks(pymupdf_data, page_idx)
        mineru_blocks = extract_mineru_blocks(mineru_data, page_idx)
        
        pymupdf_page = pymupdf_data["pages"][page_idx]
        mineru_page = mineru_data["pdf_info"][page_idx]
        
        result = compare_page(pymupdf_blocks, mineru_blocks, page_idx, pymupdf_page, mineru_page)
        all_results.append(result)
        
        # Print summary
        print(f"Page Size:")
        print(f"  PyMuPDF: {result['pymupdf_page_size']['width']:.2f} x {result['pymupdf_page_size']['height']:.2f}")
        print(f"  MinerU:   {result['mineru_page_size']['width']:.2f} x {result['mineru_page_size']['height']:.2f}")
        if "page_width_diff" in result:
            print(f"  Width diff:  {result['page_width_diff']:.2f} ({result['page_width_diff_percent']:.2f}%)")
        if "page_height_diff" in result:
            print(f"  Height diff: {result['page_height_diff']:.2f} ({result['page_height_diff_percent']:.2f}%)")
        
        print(f"\nBlock Counts:")
        print(f"  PyMuPDF: {result['pymupdf_block_count']} blocks")
        print(f"  MinerU:  {result['mineru_block_count']} blocks")
        
        # Show first few comparisons
        print(f"\nFirst 5 Block Comparisons:")
        for comp in result["comparisons"][:5]:
            print(f"\n  MinerU Block {comp['mineru_index']} ({comp['mineru_type']}):")
            print(f"    BBox: {comp['mineru_bbox']}")
            if comp["match"]:
                print(f"    Matched with PyMuPDF Block {comp['match']['pymupdf_index']}:")
                print(f"      PyMuPDF BBox: {comp['match']['pymupdf_bbox']}")
                if "iou" in comp["match"]:
                    print(f"      IoU: {comp['match']['iou']:.3f}")
                bbox_diff = comp["bbox_differences"]
                print(f"      BBox Differences:")
                print(f"        x0: {bbox_diff['x0_diff']:+.2f}, y0: {bbox_diff['y0_diff']:+.2f}")
                print(f"        x1: {bbox_diff['x1_diff']:+.2f}, y1: {bbox_diff['y1_diff']:+.2f}")
                print(f"        width: {bbox_diff['width_diff']:+.2f}, height: {bbox_diff['height_diff']:+.2f}")
            else:
                print(f"    No match found")
    
    # Save detailed comparison to file
    output_path = base_path / "layout_comparison.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n\nDetailed comparison saved to: {output_path}")


if __name__ == "__main__":
    main()

