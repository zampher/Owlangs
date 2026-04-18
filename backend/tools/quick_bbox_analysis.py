"""Quick bbox deviation analysis."""
import json
from pathlib import Path

comparison_file = Path("test-doc/mineru_sample/verification/c9097029-cced-46f0-b8e9-413728ea1f81_origin_comparison.json")
with open(comparison_file, "r", encoding="utf-8") as f:
    data = json.load(f)

x0_diffs = []
y0_diffs = []
x1_diffs = []
y1_diffs = []
width_diffs = []
height_diffs = []

for page in data["pages"]:
    for block in page["block_comparisons"]:
        if "bbox_differences" in block:
            diff = block["bbox_differences"]
            orig = block["original_bbox"]
            rend = block["rendered_bbox"]
            
            x0_diffs.append(diff["x0"])
            y0_diffs.append(diff["y0"])
            x1_diffs.append(diff["x1"])
            y1_diffs.append(diff["y1"])
            
            orig_w = orig[2] - orig[0]
            orig_h = orig[3] - orig[1]
            rend_w = rend[2] - rend[0]
            rend_h = rend[3] - rend[1]
            
            width_diffs.append(rend_w - orig_w)
            height_diffs.append(rend_h - orig_h)

print(f"Total matched blocks: {len(x0_diffs)}")
print(f"\nX0 (left edge): mean={sum(x0_diffs)/len(x0_diffs):.2f}, abs_mean={sum(abs(x) for x in x0_diffs)/len(x0_diffs):.2f}")
print(f"Y0 (top edge): mean={sum(y0_diffs)/len(y0_diffs):.2f}, abs_mean={sum(abs(y) for y in y0_diffs)/len(y0_diffs):.2f}")
print(f"X1 (right edge): mean={sum(x1_diffs)/len(x1_diffs):.2f}, abs_mean={sum(abs(x) for x in x1_diffs)/len(x1_diffs):.2f}")
print(f"Y1 (bottom edge): mean={sum(y1_diffs)/len(y1_diffs):.2f}, abs_mean={sum(abs(y) for y in y1_diffs)/len(y1_diffs):.2f}")
print(f"Width: mean={sum(width_diffs)/len(width_diffs):.2f}, abs_mean={sum(abs(w) for w in width_diffs)/len(width_diffs):.2f}")
print(f"Height: mean={sum(height_diffs)/len(height_diffs):.2f}, abs_mean={sum(abs(h) for h in height_diffs)/len(height_diffs):.2f}")

