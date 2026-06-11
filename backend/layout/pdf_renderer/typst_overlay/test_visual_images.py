# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for Typst overlay visual image placement."""

import unittest
from types import SimpleNamespace

from layout.pdf_renderer.typst_overlay.visual_images import (
    collect_visual_image_placements,
    lookup_image_bytes,
)


class TestVisualImagePlacements(unittest.TestCase):
    def test_lookup_image_bytes_by_basename(self):
        image_map = {"images/abc123.jpg": b"payload"}
        self.assertEqual(lookup_image_bytes(image_map, "abc123.jpg"), b"payload")

    def test_collect_chart_placements_when_format_image(self):
        chart_block = SimpleNamespace(
            type="chart",
            index=82,
            bbox=(110.0, 441.0, 302.0, 610.0),
            image_path=None,
            raw={
                "blocks": [
                    {
                        "type": "chart_body",
                        "bbox": [110.0, 441.0, 302.0, 610.0],
                        "lines": [
                            {
                                "spans": [
                                    {
                                        "type": "chart",
                                        "image_path": "394134b7dae435ee.jpg",
                                    }
                                ]
                            }
                        ],
                    }
                ]
            },
        )
        page = SimpleNamespace(page_index=5, blocks=[chart_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {"394134b7dae435ee.jpg": b"chart-bytes"}

        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format="image",
            table_body_format="html",
            image_data_map=image_map,
        )

        self.assertEqual(len(placements), 1)
        self.assertEqual(placements[0].block_index, 82)
        self.assertEqual(placements[0].block_type, "chart")
        self.assertEqual(placements[0].page_index, 5)

    def test_skip_chart_placements_when_format_html(self):
        chart_block = SimpleNamespace(
            type="chart",
            index=82,
            bbox=(110.0, 441.0, 302.0, 610.0),
            image_path="394134b7dae435ee.jpg",
            raw={"blocks": []},
        )
        page = SimpleNamespace(page_index=5, blocks=[chart_block])
        layout_doc = SimpleNamespace(pages=[page])
        image_map = {"394134b7dae435ee.jpg": b"chart-bytes"}

        placements = collect_visual_image_placements(
            layout_doc,
            chart_body_format="html",
            table_body_format="html",
            image_data_map=image_map,
        )

        self.assertEqual(placements, [])


if __name__ == "__main__":
    unittest.main()
