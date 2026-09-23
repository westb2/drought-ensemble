#!/usr/bin/env python3
"""Build the condensed drought storage-memory deck (seven story figures).

Most slides reuse canonical figures unchanged; merged figures come from
``make_story_figures.py``. The long version (35 slides) stays in
``make_drought_narrative_slides.py`` / ``drought_narrative_slides.pptx``.
"""
from __future__ import annotations

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches

from make_drought_narrative_slides import (
    ACCENT,
    FIG,
    H,
    MUTED,
    W,
    _set_run,
    blank_slide,
    fig_path,
    resolve_figure,
    slide_figure,
)

OUT = fig_path("drought_story_slides.pptx")

SLIDES = [
    (
        "A 10-year drought draws storage down for the whole drought",
        "ten_year_drought_streamflow_storage.png",
    ),
    (
        "Recovery is two-phase; near-stream cells recover, uplands stay dry",
        "story_recovery_storage_and_wtd_maps.png",
    ),
    (
        "Streamflow returns within a year; pumping stays depressed after shutoff",
        "story_recovery_flow_anomaly_combined.png",
    ),
    (
        "The persistent deficit sits where overland flow is low",
        "story_overland_controls_persistence.png",
    ),
    (
        "Temporary saturates, persistent grows — and persistent is deep",
        "shallow_deep_temp_persist_partition.png",
    ),
    (
        "Near-surface regenerates through the drought; deep ratchets down "
        "and only partly refills",
        "story_mid_drought_regen_10yr.png",
    ),
    (
        "After pumping: little returns in year 1; near-stream cells recover first",
        "story_pumping_recovery_storage_and_wtd_maps.png",
    ),
]


def slide_title(prs: Presentation):
    slide = blank_slide(prs)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.4), W - Inches(1.6), Inches(1.4))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _set_run(p.add_run(), "Drought storage memory", size=36, bold=True, color=ACCENT)

    box2 = slide.shapes.add_textbox(Inches(0.8), Inches(3.8), W - Inches(1.6), Inches(1.4))
    tf2 = box2.text_frame
    tf2.clear()
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.CENTER
    _set_run(
        p2.add_run(),
        "Temporary deficits recover in a year; persistent deficits are deep, "
        "poorly connected, and grow with drought length",
        size=16,
        color=MUTED,
    )
    p3 = tf2.add_paragraph()
    p3.alignment = PP_ALIGN.CENTER
    _set_run(
        p3.add_run(), "Potomac & Wolf · 1 / 3 / 10 / 50-year droughts", size=14, color=MUTED
    )
    return slide


def main():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H

    slide_title(prs)
    for title, filename in SLIDES:
        path = resolve_figure(filename)
        if not path.exists():
            raise FileNotFoundError(
                f"{filename} missing — run analysis/make_story_figures.py first"
            )
        slide_figure(prs, title, filename)

    prs.save(OUT)
    print("wrote", OUT, f"({OUT.stat().st_size / 1024:.0f} KB, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
