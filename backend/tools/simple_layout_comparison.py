"""Simple layout comparison script."""
import json
from pathlib import Path

# Load files
pymupdf_path = Path("test-doc/mineru_sample/c9097029-cced-46f0-b8e9-413728ea1f81_origin_pymupdf_layout.json")
mineru_path = Path("test-doc/mineru_sample/layout.json")

print("Loading files...")
with open(pymupdf_path, "r", encoding="utf-8") as f:
    pymupdf = json.load(f)

with open(mineru_path, "r", encoding="utf-8") as f:
    mineru = json.load(f)

# Compare first page
page_idx = 0
pymupdf_page = pymupdf["pages"][page_idx]
mineru_page = mineru["pdf_info"][page_idx]

print(f"\n{'='*80}")
print(f"Page {page_idx} Comparison")
print(f"{'='*80}")

# Page dimensions
print(f"\nPage Dimensions:")
print(f"  PyMuPDF: {pymupdf_page['width']:.2f} x {pymupdf_page['height']:.2f}")
mineru_size = mineru_page.get("page_size", [])
print(f"  MinerU:   {mineru_size[0]:.2f} x {mineru_size[1]:.2f}")
print(f"  Difference: {abs(pymupdf_page['width'] - mineru_size[0]):.2f} x {abs(pymupdf_page['height'] - mineru_size[1]):.2f}")

# Block counts
pymupdf_blocks = pymupdf_page.get("blocks", [])
mineru_blocks = mineru_page.get("para_blocks", []) + mineru_page.get("discarded_blocks", [])

print(f"\nBlock Counts:")
print(f"  PyMuPDF: {len(pymupdf_blocks)} blocks")
print(f"  MinerU:  {len(mineru_blocks)} blocks")

# Show first few blocks from each
print(f"\nFirst 5 PyMuPDF Blocks:")
for i, block in enumerate(pymupdf_blocks[:5]):
    bbox = block.get("bbox", [])
    text = block.get("text", "")[:50].replace("\n", " ")
    print(f"  Block {i}: bbox={bbox}, text='{text}...'")

print(f"\nFirst 5 MinerU Blocks:")
for i, block in enumerate(mineru_blocks[:5]):
    bbox = block.get("bbox", [])
    block_type = block.get("type", "unknown")
    # Extract text from MinerU format
    text_parts = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if span.get("type") == "text":
                text_parts.append(span.get("content", ""))
    text = " ".join(text_parts)[:50]
    print(f"  Block {i} ({block_type}): bbox={bbox}, text='{text}...'")

# Compare specific blocks
print(f"\n{'='*80}")
print("BBox Coordinate Comparison (first matching blocks)")
print(f"{'='*80}")

# Try to match by position
for mu_idx, mu_block in enumerate(mineru_blocks[:10]):
    mu_bbox = mu_block.get("bbox", [])
    if len(mu_bbox) != 4:
        continue
    
    # Find closest PyMuPDF block
    best_match = None
    best_dist = float("inf")
    
    for pm_idx, pm_block in enumerate(pymupdf_blocks):
        pm_bbox = pm_block.get("bbox", [])
        if len(pm_bbox) != 4:
            continue
        
        # Calculate center distance
        mu_center = ((mu_bbox[0] + mu_bbox[2]) / 2, (mu_bbox[1] + mu_bbox[3]) / 2)
        pm_center = ((pm_bbox[0] + pm_bbox[2]) / 2, (pm_bbox[1] + pm_bbox[3]) / 2)
        dist = ((mu_center[0] - pm_center[0])**2 + (mu_center[1] - pm_center[1])**2)**0.5
        
        if dist < best_dist:
            best_dist = dist
            best_match = (pm_idx, pm_bbox)
    
    if best_match and best_dist < 50:  # Only show if reasonably close
        pm_idx, pm_bbox = best_match
        print(f"\nMinerU Block {mu_idx} vs PyMuPDF Block {pm_idx} (distance: {best_dist:.2f}):")
        print(f"  MinerU:  [{mu_bbox[0]:7.2f}, {mu_bbox[1]:7.2f}, {mu_bbox[2]:7.2f}, {mu_bbox[3]:7.2f}]")
        print(f"  PyMuPDF: [{pm_bbox[0]:7.2f}, {pm_bbox[1]:7.2f}, {pm_bbox[2]:7.2f}, {pm_bbox[3]:7.2f}]")
        print(f"  Diff:    [{mu_bbox[0]-pm_bbox[0]:+7.2f}, {mu_bbox[1]-pm_bbox[1]:+7.2f}, {mu_bbox[2]-pm_bbox[2]:+7.2f}, {mu_bbox[3]-pm_bbox[3]:+7.2f}]")

print("\n" + "="*80)

