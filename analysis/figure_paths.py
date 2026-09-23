#!/usr/bin/env python3
"""Resolve figure / sidecar paths into category subfolders under ``figures/``.

Layout::

    analysis/figures/
      drought_final/          # condensed drought story-deck selection
      pumping_final/          # condensed pumping story (catalog / 1e-6)
      comparison/             # drought vs matched-pumping contrasts
      psa_final/              # Potomac sensitivity attribution manuscript figures
      drought_exploratory/
      pumping_exploratory/
      decks/                  # *.pptx
      _data/                  # *.json, *.csv next to analyses
      _reports/               # *.html / *.pdf summaries
      _cache/                 # slim 219h / zone caches
      _scratch/               # _tmp_* diagnostics

Writers should use ``FIG_DIR / "name.png"`` (this module's ``FIG_DIR``) or
``fig_path("name.png")``. Readers / slide builders should use
``resolve_figure("name.png")`` so files are found after migration.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
FIG_ROOT = ROOT / "analysis" / "figures"
CATEGORIES_YAML = ROOT / "analysis" / "FIGURE_CATEGORIES.yaml"

CATEGORIES = (
    "drought_final",
    "pumping_final",
    "comparison",
    "psa_final",
    "drought_exploratory",
    "pumping_exploratory",
)

_IMAGE_EXTS = {".png", ".pdf", ".svg"}
_DATA_EXTS = {".json", ".csv"}
_REPORT_EXTS = {".html", ".pdf"}  # pdf reports live in _reports; plot pdfs rare
_DECK_EXTS = {".pptx"}

_COMPARE_PREFIXES = (
    "compare_",
    "matched_deficit_",
)
_PUMP_PREFIXES = (
    "pumping_",
    "ten_year_pumping_",
    "wolf_pumping_",
    "flow_barrier_pumping_",
    "story_mid_pump_",
    "story_pumping_",
)
_DROUGHT_PREFIXES = (
    "drought_",
    "ten_year_drought_",
    "fifty_year_",
    "three_year_drought_",
    "shallow_deep_",
    "story_",
    "budyko_",
    "wtd_threshold_",
    "average_year_usgs_",
    "drought_year_usgs_",
    "usgs_",
    "potomac",
    "wolf2_",
    "baseflow_",
    "outlet_flow_",
)


def _load_explicit() -> dict[str, str]:
    """basename → category from YAML (finals + optional overrides)."""
    mapping: dict[str, str] = {}
    if not CATEGORIES_YAML.exists():
        return mapping
    with CATEGORIES_YAML.open() as f:
        data = yaml.safe_load(f) or {}
    for cat in CATEGORIES:
        for name in data.get(cat) or []:
            mapping[str(name)] = cat
    return mapping


EXPLICIT: dict[str, str] = _load_explicit()


def reload_categories() -> None:
    """Re-read YAML (tests / after editing membership)."""
    global EXPLICIT
    EXPLICIT = _load_explicit()


def infer_category(name: str) -> str:
    """Classify an unlisted basename into an exploratory (or reserved) folder."""
    base = Path(name).name
    if base in EXPLICIT:
        return EXPLICIT[base]

    # Scratch / tmp diagnostics
    if base.startswith("_tmp") or base.startswith("tmp_"):
        return "_scratch"

    # Comparison before pumping so matched_deficit_* / compare_* win
    for p in _COMPARE_PREFIXES:
        if base.startswith(p):
            return "comparison"
    # Pumping before drought so story_pumping_* win
    for p in _PUMP_PREFIXES:
        if base.startswith(p):
            return "pumping_exploratory"
    for p in _DROUGHT_PREFIXES:
        if base.startswith(p):
            return "drought_exploratory"

    # Default: drought exploratory (legacy domain plots, etc.)
    return "drought_exploratory"


def category_for(name: str) -> str:
    base = Path(name).name
    return EXPLICIT.get(base, infer_category(base))


def _sidecar_dir(name: str) -> Path:
    ext = Path(name).suffix.lower()
    if ext in _DECK_EXTS:
        return FIG_ROOT / "decks"
    if ext in _DATA_EXTS:
        return FIG_ROOT / "_data"
    if ext == ".html" or (ext == ".pdf" and not name.endswith(".png")):
        # Treat standalone html/pdf as reports; image-like pdfs still rare
        if ext == ".pdf" and any(
            Path(name).name.startswith(p)
            for p in ("drought_", "pumping_", "budyko_", "shallow_", "usgs_", "wolf_")
        ):
            return FIG_ROOT / "_reports"
        if ext == ".html":
            return FIG_ROOT / "_reports"
    return FIG_ROOT / "_data"


def fig_path(name: str | Path, *, mkdir: bool = True) -> Path:
    """Write destination for a figure or sidecar basename."""
    base = Path(name).name
    ext = Path(base).suffix.lower()

    if ext in _DECK_EXTS or ext in _DATA_EXTS or ext == ".html":
        out = _sidecar_dir(base) / base
    elif ext == ".pdf":
        out = FIG_ROOT / "_reports" / base
    elif ext == ".png" or ext in _IMAGE_EXTS:
        cat = category_for(base)
        out = (
            FIG_ROOT / "_scratch" / base
            if cat == "_scratch"
            else FIG_ROOT / cat / base
        )
    else:
        out = FIG_ROOT / "_data" / base

    if mkdir:
        out.parent.mkdir(parents=True, exist_ok=True)
    return out


def resolve_figure(name: str | Path) -> Path:
    """Locate an existing figure by basename (any category or legacy root)."""
    base = Path(name).name
    candidates = [
        fig_path(base, mkdir=False),
        FIG_ROOT / base,
        *[FIG_ROOT / cat / base for cat in CATEGORIES],
        FIG_ROOT / "_scratch" / base,
        FIG_ROOT / "decks" / base,
        FIG_ROOT / "_data" / base,
        FIG_ROOT / "_reports" / base,
    ]
    # de-dupe while preserving order
    seen: set[Path] = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if p.exists():
            return p
    return candidates[0]


def fig_md_link(name: str, *, label: str | None = None) -> str:
    """Markdown link relative to ``analysis/`` (for summary files)."""
    base = Path(name).name
    path = resolve_figure(base)
    try:
        rel = path.relative_to(ROOT / "analysis")
    except ValueError:
        rel = path
    text = label or base
    return f"[{text}]({rel.as_posix()})"


def ensure_category_dirs() -> None:
    for cat in CATEGORIES:
        (FIG_ROOT / cat).mkdir(parents=True, exist_ok=True)
    for sub in ("decks", "_data", "_reports", "_cache", "_scratch"):
        (FIG_ROOT / sub).mkdir(parents=True, exist_ok=True)
    # Placeholder so pumping_final is visible before membership is chosen
    keep = FIG_ROOT / "pumping_final" / ".gitkeep"
    if not keep.exists():
        keep.write_text(
            "# Reserved for condensed pumping story-deck figures.\n"
            "# Add basenames under pumping_final in FIGURE_CATEGORIES.yaml.\n"
        )


class _FigDir:
    """Drop-in for ``Path(.../figures)`` that routes basenames into categories."""

    def __truediv__(self, other):
        name = str(other)
        # Subdirectory / relative path with separators: keep under FIG_ROOT
        if "/" in name or name in {
            "decks",
            "_data",
            "_reports",
            "_cache",
            "_scratch",
            "no50",
        }:
            return FIG_ROOT / name
        if name.startswith("_") and Path(name).suffix == "":
            # Cache dirs: figures/_cache/<name>
            return FIG_ROOT / "_cache" / name
        return fig_path(name)

    def __str__(self) -> str:
        return str(FIG_ROOT)

    def __fspath__(self) -> str:
        return str(FIG_ROOT)

    def __repr__(self) -> str:
        return f"FigDir({FIG_ROOT!s})"

    def mkdir(self, *a, **k):
        ensure_category_dirs()
        return FIG_ROOT.mkdir(*a, **k)

    @property
    def parent(self):
        return FIG_ROOT.parent


FIG_DIR = _FigDir()


if __name__ == "__main__":
    ensure_category_dirs()
    for n in (
        "ten_year_drought_streamflow_storage.png",
        "pumping_course_streamflow_storage.png",
        "ten_year_pumping_streamflow_storage.png",
        "story_mid_pump_regen_10yr.png",
        "pumping_annualized_q.json",
        "drought_story_slides.pptx",
    ):
        print(f"{n:50s} → {fig_path(n, mkdir=False).relative_to(FIG_ROOT)}")
