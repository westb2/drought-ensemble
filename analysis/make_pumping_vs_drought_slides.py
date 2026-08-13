#!/usr/bin/env python3
"""Preliminary PowerPoint: how pumping storage losses differ from droughts.

Uses drought shallow/deep shielding figures + early pumping proxies
(no recovery years yet). Source analysis: pumping_shallow_deep_proxies_summary.md
and the prior early-pumping chat.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

FIG = Path("/glade/derecho/scratch/bwest/drought-ensemble/analysis/figures")
OUT = FIG / "pumping_vs_drought_storage_slides.pptx"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.4)
TITLE_H = Inches(0.55)

ACCENT = RGBColor(0x4A, 0x24, 0x10)
MUTED = RGBColor(0x55, 0x55, 0x55)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SECTION_BG = RGBColor(0x4A, 0x24, 0x10)
BULLET = RGBColor(0x2A, 0x2A, 0x2A)


def _set_run(run, text, *, size=18, bold=False, color=None):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "Calibri"
    if color is not None:
        run.font.color.rgb = color


def blank_slide(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_title_bar(slide, text: str):
    box = slide.shapes.add_textbox(MARGIN, Inches(0.2), W - 2 * MARGIN, TITLE_H)
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    _set_run(p.add_run(), text, size=22, bold=True, color=ACCENT)


def add_picture_fit(slide, path: Path, top=Inches(0.85), bottom_margin=Inches(0.35)):
    if not path.exists():
        box = slide.shapes.add_textbox(MARGIN, top, W - 2 * MARGIN, Inches(1))
        _set_run(
            box.text_frame.paragraphs[0].add_run(),
            f"Missing: {path.name}",
            size=14,
            color=MUTED,
        )
        return
    max_w = W - 2 * MARGIN
    max_h = H - top - bottom_margin
    try:
        from PIL import Image

        with Image.open(path) as im:
            iw, ih = im.size
        aspect = iw / ih
        if max_w / max_h > aspect:
            h = max_h
            w = h * aspect
        else:
            w = max_w
            h = w / aspect
    except Exception:
        w, h = max_w, max_h
    left = (W - w) / 2
    slide.shapes.add_picture(str(path), left, top, width=w, height=h)


def slide_figure(prs, title: str, filename: str):
    slide = blank_slide(prs)
    add_title_bar(slide, title)
    add_picture_fit(slide, FIG / filename)
    return slide


def slide_section(prs, section: str, subtitle: str = ""):
    slide = blank_slide(prs)
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), W, H)
    shape.fill.solid()
    shape.fill.fore_color.rgb = SECTION_BG
    shape.line.fill.background()

    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.6), W - Inches(1.6), Inches(1.2))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _set_run(p.add_run(), section, size=36, bold=True, color=WHITE)

    if subtitle:
        box2 = slide.shapes.add_textbox(
            Inches(0.8), Inches(3.9), W - Inches(1.6), Inches(0.8)
        )
        tf2 = box2.text_frame
        tf2.clear()
        p2 = tf2.paragraphs[0]
        p2.alignment = PP_ALIGN.CENTER
        _set_run(p2.add_run(), subtitle, size=18, color=RGBColor(0xE8, 0xC3, 0x9E))
    return slide


def slide_bullets(prs, title: str, bullets: list[str], footer: str = ""):
    slide = blank_slide(prs)
    add_title_bar(slide, title)
    box = slide.shapes.add_textbox(
        Inches(0.8), Inches(1.0), W - Inches(1.6), Inches(5.5)
    )
    tf = box.text_frame
    tf.word_wrap = True
    tf.clear()
    for i, line in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(14)
        _set_run(p.add_run(), "•  " + line, size=18, color=BULLET)
    if footer:
        foot = slide.shapes.add_textbox(
            Inches(0.8), Inches(6.7), W - Inches(1.6), Inches(0.5)
        )
        tf2 = foot.text_frame
        tf2.clear()
        _set_run(tf2.paragraphs[0].add_run(), footer, size=12, color=MUTED)
    return slide


def slide_two_column_bullets(
    prs, title: str, left_title: str, left: list[str], right_title: str, right: list[str]
):
    slide = blank_slide(prs)
    add_title_bar(slide, title)

    for col_left, col_title, items in (
        (Inches(0.6), left_title, left),
        (Inches(6.9), right_title, right),
    ):
        h = slide.shapes.add_textbox(col_left, Inches(0.95), Inches(5.6), Inches(0.45))
        tf = h.text_frame
        tf.clear()
        _set_run(tf.paragraphs[0].add_run(), col_title, size=18, bold=True, color=ACCENT)

        box = slide.shapes.add_textbox(col_left, Inches(1.45), Inches(5.6), Inches(5.4))
        tf = box.text_frame
        tf.word_wrap = True
        tf.clear()
        for i, line in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(12)
            _set_run(p.add_run(), "•  " + line, size=16, color=BULLET)
    return slide


def slide_title(prs):
    slide = blank_slide(prs)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.2), W - Inches(1.6), Inches(1.4))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _set_run(
        p.add_run(),
        "Pumping vs drought storage losses",
        size=34,
        bold=True,
        color=ACCENT,
    )

    box2 = slide.shapes.add_textbox(Inches(0.8), Inches(3.7), W - Inches(1.6), Inches(1.4))
    tf2 = box2.text_frame
    tf2.clear()
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.CENTER
    _set_run(
        p2.add_run(),
        "Preliminary: depth partition & mid-stress regen proxies\n"
        "(no pumping recovery years yet)",
        size=16,
        color=MUTED,
    )
    p3 = tf2.add_paragraph()
    p3.alignment = PP_ALIGN.CENTER
    _set_run(p3.add_run(), "Potomac & Wolf · 3-year pumping tests · August 2026", size=14, color=MUTED)
    return slide


def main():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H

    slide_title(prs)

    # ----- Framing -----
    slide_section(
        prs,
        "1. Framing",
        "Why drought temporary/persistent proxies should change under pumping",
    )
    slide_two_column_bullets(
        prs,
        "Ensemble contrast",
        "Droughts",
        [
            "Stress = duration (1 / 3 / 10 / 50 yr)",
            "Losses begin at the water table / near surface",
            "Recovery years define temporary vs persistent",
            "Temporary ≈ near-surface (top 2 m); persistent ≈ deep",
            "High-overland cells regenerate a near-surface skin",
        ],
        "Pumping (3-year tests)",
        [
            "Stress = rate (1e-7 … 1e-4 m/h domain-avg)",
            "Extraction at layer 2 (deep), including wet cells",
            "Ends while still pumping — no recovery on disk yet",
            "Proxies: early (yr1) vs buildup (yr2–3); NS rebound vs deep ratchet",
            "Expect deep memory even where drought would stay temporary",
        ],
    )
    slide_bullets(
        prs,
        "Proxies used here (until recovery exists)",
        [
            "Near-surface vs deep deficit: split at 2 m (z≥6 vs z<6), same as drought shielding",
            "Mid-pump regen: near-surface ΔS pulses with average-year P; deep ΔS ratchets",
            "Fast / temp proxy: mean mid-year near-surface rebound (max − year-start)",
            "Persist-like proxy: mean deep net loss per pump year",
            "Drought-style onset spike ≈ 0 under pumping — deficit grows from ~0",
        ],
        footer="See pumping_shallow_deep_proxies_summary.md",
    )

    # ----- Drought reminder -----
    slide_section(
        prs,
        "2. Drought reminder",
        "Temporary ≈ near-surface regenerating skin; persistent ≈ deep",
    )
    slide_figure(
        prs,
        "Drought: temporary ≈ near-surface; persistent ≈ deep",
        "shallow_deep_temp_persist_partition.png",
    )
    slide_figure(
        prs,
        "Drought: mid-stress near-surface regenerates, deep ratchets",
        "shallow_deep_mid_drought_regen.png",
    )
    slide_figure(
        prs,
        "Drought year pulse: storage tracks precip only near the surface",
        "shallow_deep_mid_drought_year_pulse.png",
    )

    # ----- Pumping response -----
    slide_section(
        prs,
        "3. Pumping response",
        "Rates during 3-year pumping (early vs buildup)",
    )
    slide_figure(
        prs,
        "During pumping: storage & flow by rate",
        "pumping_during_totals_and_anomalies.png",
    )
    slide_figure(
        prs,
        "Pumping course (spinup → 3 yr pump)",
        "pumping_course_streamflow_storage.png",
    )
    slide_figure(
        prs,
        "Early (yr1) vs buildup (yr2–3) storage deficits",
        "pumping_early_buildup_deficit_bars.png",
    )
    slide_figure(
        prs,
        "Early vs buildup storage deficit maps",
        "pumping_early_buildup_storage_deficit_maps.png",
    )
    slide_figure(
        prs,
        "WTD anomaly maps through pumping",
        "pumping_wtd_anomaly_maps.png",
    )

    # ----- Depth contrast -----
    slide_section(
        prs,
        "4. Depth contrast",
        "Under pumping, end-of-stress deficit is almost all deep",
    )
    slide_figure(
        prs,
        "Pumping: end yr1 / yr3 deficit near-surface vs deep",
        "pumping_shallow_deep_end_deficit_partition.png",
    )
    slide_figure(
        prs,
        "Pumping spatial end-yr3 (1e-5): deep dominates the map",
        "pumping_shallow_deep_spatial_end_yr3.png",
    )
    slide_bullets(
        prs,
        "End-of-pump % of deficit in deep",
        [
            "Potomac: 80→91% (1e-7) … 100% (1e-4) by end of year 3",
            "Wolf: 71→86% (1e-7) … 99% (1e-4) by end of year 3",
            "At ≥1e-5, both domains are 97–100% deep by year 3",
            "Contrast drought temporary volume: ~80–100% near-surface",
            "Layer-2 extraction writes memory deep even in high water-availability cells",
        ],
    )

    # ----- Mid-stress regen -----
    slide_section(
        prs,
        "5. Mid-stress regen",
        "Near-surface still pulses — but it is a thin skin beside the deep ratchet",
    )
    slide_figure(
        prs,
        "Mid-pump: near-surface regenerates, deep ratchets (by rate)",
        "pumping_shallow_deep_mid_pump_regen.png",
    )
    slide_figure(
        prs,
        "One pump year: NS tracks P; deep has no pulse response",
        "pumping_shallow_deep_mid_pump_year_pulse.png",
    )
    slide_figure(
        prs,
        "Fast proxy vs persist-like: NS rebound ≪ deep net loss / yr",
        "pumping_fast_regen_vs_deep_drawdown.png",
    )
    slide_bullets(
        prs,
        "Mid-pump wet-window ΔS (1e-5 m/h)",
        [
            "Potomac: near-surface +0.4×10⁶ m³ vs deep −7.1×10⁶ m³ (ρ(P,ns)=0.62, ρ(P,deep)≈0)",
            "Wolf: near-surface +0.3×10⁶ m³ vs deep −2.7×10⁶ m³ (ρ(P,ns)=0.28, ρ(P,deep)≈0)",
            "Potomac mean NS mid-year rebound 5.5 vs deep net loss 276 ×10⁶ m³/yr",
            "Wolf mean NS mid-year rebound 4.2 vs deep net loss 103 ×10⁶ m³/yr",
            "Same qualitative split as drought — different volume balance under deep extraction",
        ],
    )

    # ----- Streamflow -----
    slide_section(
        prs,
        "6. Streamflow",
        "Outlet Q vs baseline — does deep pumping couple to flow?",
    )
    slide_bullets(
        prs,
        "Contrast with drought Q",
        [
            "50-yr drought: deep storage grew for decades while outlet Q stepped down then plateaued",
            "Here precip forcing stays average-year — any Q drop is capture / storage coupling",
            "Ask: does mean Q keep falling as ΔS builds (yr1→yr3), or stay flat?",
            "Caveat: outlet p10≈0 on baseline — classical baseflow ratios still undefined",
        ],
        footer="See pumping_streamflow_impact_summary.md · persistent_storage_vs_streamflow_50yr.md",
    )
    slide_figure(
        prs,
        "Outlet Q / baseline and ΔQ during pumping",
        "pumping_streamflow_q_ratio.png",
    )
    slide_figure(
        prs,
        "Mean Q ratio declines across pump years (not a mid-drought plateau)",
        "pumping_streamflow_q_ratio_by_year.png",
    )
    slide_figure(
        prs,
        "Year 1 vs year 3: mean / p50 / p90 Q ratios by rate",
        "pumping_streamflow_q_ratio_bars.png",
    )
    slide_figure(
        prs,
        "ΔQ vs ΔS: pulsed flow hits while storage ratchets down",
        "pumping_streamflow_dq_vs_ds.png",
    )
    slide_bullets(
        prs,
        "Outlet Q / baseline (mean)",
        [
            "Low rates (1e-7): Q ≈ baseline in both domains",
            "Potomac 1e-5: yr1=0.97 → yr3=0.80; 1e-4 collapses to yr3=0.23 (p50≈0)",
            "Wolf 1e-5: yr1=0.98 → yr3=0.91; 1e-4 → yr3=0.76",
            "Unlike mid-drought, mean Q keeps falling as deep ΔS grows — capture couples storage to flow",
            "Suppression is strongest on the body/high flows (p90 still near 1 at 1e-5); peaks are hit harder at 1e-4",
        ],
    )

    # ----- Takeaways -----
    slide_section(prs, "7. Takeaways", "What differs — and what to check with recovery")
    slide_bullets(
        prs,
        "Preliminary conclusions",
        [
            "Pumping storage losses sit deep (≈86–100% by yr3) — opposite of drought temporary losses",
            "Near-surface still regenerates on precip pulses; that pool is tiny vs the deep ratchet",
            "Unlike drought, outlet Q keeps declining as deep storage builds (esp. Potomac ≥1e-5)",
            "Shielding / Q–storage decoupling weakens when extraction is at layer 2",
            "Next: recovery years (and layer-4 tests) for true temporary/persistent and Q rebound",
        ],
        footer="Scripts: pumping_streamflow_impact.py · pumping_shallow_deep_proxies.py · redo_pumping_recovery_analogues.py",
    )

    prs.save(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
