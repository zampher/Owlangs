"""
Analyze bbox deviations to identify where the errors occur in the rendering pipeline.

Pipeline stages:
1. Original PDF -> PyMuPDF extraction (original_layout)
2. Original layout -> ReportLab rendering (rendered.pdf)
3. Rendered PDF -> PyMuPDF extraction (rendered_layout)
4. Comparison between original and rendered layouts

This script analyzes bbox differences to identify which stage introduces errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
import statistics

def analyze_bbox_deviations(comparison_file: Path) -> Dict[str, Any]:
    """
    Analyze bbox deviations from comparison results.
    
    Returns:
        Dictionary with detailed analysis
    """
    with open(comparison_file, "r", encoding="utf-8") as f:
        comparison = json.load(f)
    
    # Collect all bbox differences
    x0_diffs = []
    y0_diffs = []
    x1_diffs = []
    y1_diffs = []
    width_diffs = []
    height_diffs = []
    
    matched_blocks = []
    
    for page_data in comparison.get("pages", []):
        for block_comp in page_data.get("block_comparisons", []):
            # Matched blocks have bbox_differences, unmatched have status="unmatched"
            if "bbox_differences" in block_comp:
                diff = block_comp["bbox_differences"]
                orig_bbox = block_comp["original_bbox"]
                rend_bbox = block_comp["rendered_bbox"]
                
                x0_diffs.append(diff["x0"])
                y0_diffs.append(diff["y0"])
                x1_diffs.append(diff["x1"])
                y1_diffs.append(diff["y1"])
                
                # Calculate width and height differences
                orig_width = orig_bbox[2] - orig_bbox[0]
                orig_height = orig_bbox[3] - orig_bbox[1]
                rend_width = rend_bbox[2] - rend_bbox[0]
                rend_height = rend_bbox[3] - rend_bbox[1]
                
                width_diffs.append(rend_width - orig_width)
                height_diffs.append(rend_height - orig_height)
                
                matched_blocks.append({
                    "page": page_data["page_index"],
                    "original": orig_bbox,
                    "rendered": rend_bbox,
                    "differences": diff,
                    "width_diff": rend_width - orig_width,
                    "height_diff": rend_height - orig_height,
                    "text_similarity": block_comp.get("text_similarity", 0),
                })
    
    # Statistical analysis
    def calc_stats(values: List[float]) -> Dict[str, float]:
        if not values:
            return {}
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "abs_mean": statistics.mean([abs(v) for v in values]),
            "abs_max": max([abs(v) for v in values]),
        }
    
    analysis = {
        "summary": {
            "total_matched_blocks": len(matched_blocks),
            "x0": calc_stats(x0_diffs),
            "y0": calc_stats(y0_diffs),
            "x1": calc_stats(x1_diffs),
            "y1": calc_stats(y1_diffs),
            "width": calc_stats(width_diffs),
            "height": calc_stats(height_diffs),
        },
        "pattern_analysis": {},
        "sample_blocks": matched_blocks[:20],  # First 20 for inspection
    }
    
    # Pattern analysis: Check for systematic biases
    # 1. Check if x0 is consistently offset (rendering position issue)
    x0_mean = statistics.mean(x0_diffs) if x0_diffs else 0
    x0_abs_mean = statistics.mean([abs(v) for v in x0_diffs]) if x0_diffs else 0
    
    # 2. Check if y0 is consistently offset (coordinate system conversion issue)
    y0_mean = statistics.mean(y0_diffs) if y0_diffs else 0
    y0_abs_mean = statistics.mean([abs(v) for v in y0_diffs]) if y0_diffs else 0
    
    # 3. Check if width is consistently different (text wrapping issue)
    width_mean = statistics.mean(width_diffs) if width_diffs else 0
    
    # 4. Check if height is consistently different (line height issue)
    height_mean = statistics.mean(height_diffs) if height_diffs else 0
    
    analysis["pattern_analysis"] = {
        "x0_bias": {
            "mean_offset": x0_mean,
            "abs_mean_offset": x0_abs_mean,
            "interpretation": "Systematic x0 offset suggests rendering position error" if abs(x0_mean) > 1 else "No significant x0 bias",
        },
        "y0_bias": {
            "mean_offset": y0_mean,
            "abs_mean_offset": y0_abs_mean,
            "interpretation": "Systematic y0 offset suggests coordinate conversion error" if abs(y0_mean) > 1 else "No significant y0 bias",
        },
        "width_bias": {
            "mean_diff": width_mean,
            "interpretation": "Negative mean suggests text is narrower (wrapping), positive suggests wider" if abs(width_mean) > 5 else "No significant width bias",
        },
        "height_bias": {
            "mean_diff": height_mean,
            "interpretation": "Positive mean suggests more lines (wrapping), negative suggests fewer lines" if abs(height_mean) > 5 else "No significant height bias",
        },
    }
    
    # Find blocks with largest deviations
    def get_deviation(block: Dict[str, Any]) -> float:
        diff = block["differences"]
        return (abs(diff["x0"]) + abs(diff["y0"]) + abs(diff["x1"]) + abs(diff["y1"])) / 4
    
    matched_blocks.sort(key=get_deviation, reverse=True)
    analysis["largest_deviations"] = matched_blocks[:10]
    
    return analysis


def print_analysis(analysis: Dict[str, Any]) -> None:
    """Print analysis results in a readable format."""
    print("=" * 80)
    print("BBox Deviation Analysis")
    print("=" * 80)
    print()
    
    summary = analysis["summary"]
    print(f"Total matched blocks: {summary['total_matched_blocks']}")
    print()
    
    # Print statistics for each dimension
    for dim in ["x0", "y0", "x1", "y1", "width", "height"]:
        stats = summary[dim]
        if not stats:
            continue
        print(f"{dim.upper()} Statistics:")
        print(f"  Count: {stats['count']}")
        print(f"  Mean: {stats['mean']:.2f} points")
        print(f"  Median: {stats['median']:.2f} points")
        print(f"  Std Dev: {stats['stdev']:.2f} points")
        print(f"  Range: [{stats['min']:.2f}, {stats['max']:.2f}] points")
        print(f"  Mean Absolute: {stats['abs_mean']:.2f} points")
        print(f"  Max Absolute: {stats['abs_max']:.2f} points")
        print()
    
    # Pattern analysis
    print("Pattern Analysis:")
    print("-" * 80)
    patterns = analysis["pattern_analysis"]
    for key, pattern in patterns.items():
        print(f"{key}:")
        for k, v in pattern.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")
        print()
    
    # Largest deviations
    print("Top 10 Blocks with Largest Deviations:")
    print("-" * 80)
    for i, block in enumerate(analysis["largest_deviations"], 1):
        print(f"{i}. Page {block['page']}, Text similarity: {block['text_similarity']:.2f}")
        print(f"   Original bbox: {[f'{v:.1f}' for v in block['original']]}")
        print(f"   Rendered bbox: {[f'{v:.1f}' for v in block['rendered']]}")
        print(f"   Differences: x0={block['differences']['x0']:.1f}, y0={block['differences']['y0']:.1f}, "
              f"x1={block['differences']['x1']:.1f}, y1={block['differences']['y1']:.1f}")
        print(f"   Width diff: {block['width_diff']:.1f}, Height diff: {block['height_diff']:.1f}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze bbox deviations from ReportLab rendering verification."
    )
    parser.add_argument(
        "--comparison",
        type=str,
        required=True,
        help="Path to comparison JSON file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save analysis results (JSON). If not provided, only prints to stdout.",
    )
    args = parser.parse_args()
    
    comparison_file = Path(args.comparison)
    if not comparison_file.exists():
        print(f"ERROR: Comparison file not found: {comparison_file}", file=sys.stderr)
        sys.exit(1)
    
    # Analyze
    analysis = analyze_bbox_deviations(comparison_file)
    
    # Print to stdout
    print_analysis(analysis)
    
    # Save to file if requested
    if args.output:
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"Analysis saved to: {output_file}")


if __name__ == "__main__":
    main()

