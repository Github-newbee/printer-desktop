from __future__ import annotations

from typing import Final


DEFAULT_PAPER_SIZE = "A4"
PAPER_SPECS: Final[dict[str, dict[str, object]]] = {
    "A4": {"code": "A4", "label": "A4", "width_mm": 210, "height_mm": 297},
    "A5": {"code": "A5", "label": "A5", "width_mm": 148, "height_mm": 210},
}


def normalize_paper_size(paper_size: str | None) -> str:
    value = (paper_size or DEFAULT_PAPER_SIZE).strip().upper()
    if value not in PAPER_SPECS:
        raise ValueError("纸张大小无效")
    return value


def get_paper_size_options() -> list[dict[str, object]]:
    return [
        {
            "code": code,
            "label": str(spec["label"]),
            "width_mm": int(spec["width_mm"]),
            "height_mm": int(spec["height_mm"]),
        }
        for code, spec in PAPER_SPECS.items()
    ]


def get_sumatra_paper_setting(paper_size: str | None) -> str:
    normalized_paper_size = normalize_paper_size(paper_size)
    return f"paper={normalized_paper_size}"
