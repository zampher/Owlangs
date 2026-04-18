"""Sync configs/platforms.json into platforms.json.template with safe placeholders."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg_dir = root / "configs"
    src = cfg_dir / "platforms.json"
    dst = cfg_dir / "platforms.json.template"

    with open(src, encoding="utf-8") as f:
        live = json.load(f)

    tmpl = json.loads(json.dumps(live))

    platforms = tmpl.get("platforms") or {}
    if "ollama" in platforms:
        platforms["ollama"]["url"] = "http://localhost:11434"
    if "mineru_local" in platforms:
        platforms["mineru_local"]["url"] = "http://localhost:8920"

    tmpl["default_platform"] = "deepseek"

    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        json.dump(tmpl, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {dst} ({len(platforms)} platforms)")


if __name__ == "__main__":
    main()
