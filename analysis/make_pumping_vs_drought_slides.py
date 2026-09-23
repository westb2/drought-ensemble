#!/usr/bin/env python3
"""Preliminary PowerPoint: how pumping storage losses differ from droughts.

Uses drought shallow/deep shielding figures + early pumping proxies
(no recovery years yet). Source analysis: pumping_shallow_deep_proxies_summary.md
and the prior early-pumping chat.
"""
from __future__ import annotations

from pathlib import Path
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis.figure_paths import FIG_ROOT, fig_path, resolve_figure  # noqa: E402

FIG = FIG_ROOT
OUT = fig_path("pumping_vs_drought_storage_slides.pptx")

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
    add_picture_fit(slide, resolve_figure(filename))
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
        "Pumping course (spinup → 3 yr pump → 10 yr recovery)",
        "pumping_course_streamflow_storage.png",
    )
    slide_figure(
        prs,
        "Recovery after pumping: storage & flow by rate",
        "pumping_recovery_totals_and_anomalies.png",
    )
    slide_figure(
        prs,
        "Fraction of end-pump storage deficit remaining",
        "pumping_recovery_fractional_storage.png",
    )
    slide_figure(
        prs,
        "Temporary vs persistent (recovery year 1 on ΔS)",
        "pumping_temp_persist_definition.png",
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
        "Outlet Q / baseline (219 h mean, during pumping)",
        [
            "Low rates (1e-7): Q ≈ baseline in both domains",
            "Potomac 1e-5: yr1=0.97 → yr3=0.80; 1e-4 collapses to yr3=0.23 (p50≈0)",
            "Wolf 1e-5: yr1=0.98 → yr3=0.91; 1e-4 → yr3=0.76",
            "Unlike mid-drought, mean Q keeps falling as deep ΔS grows — capture couples storage to flow",
            "219 h ratios overweight dry windows; annualized (yearly volume) is milder — next slides",
        ],
    )
    slide_figure(
        prs,
        "Annualized Q through pumping + 10-yr recovery",
        "pumping_annualized_q_course.png",
    )
    slide_figure(
        prs,
        "Annualized Q / baseline, origin at recovery start",
        "pumping_annualized_q_ratio_recovery.png",
    )
    slide_figure(
        prs,
        "Annualized Q / baseline at pump and recovery milestones",
        "pumping_annualized_q_milestones.png",
    )
    slide_bullets(
        prs,
        "Annualized Q / baseline (yearly volume)",
        [
            "Potomac 1e-5: pump 0.99→0.89; rec yr1=0.86 then 0.92 / 0.95 at yr5 / yr10 — slow partial rebound",
            "Potomac 1e-4: pump yr3=0.54; rec yr1–yr10 stays ~0.49 — no Q recovery in 10 years",
            "Wolf 1e-5: 0.99→0.98 then back to 0.99 by yr10; 1e-4 residual ~0.94 through recovery",
            "Q nadir is rec yr1, not pump-end — capture keeps biting after wells shut off",
            "Wolf annualized Q is much more buffered than Potomac at the same domain-avg rate",
        ],
        footer="See pumping_annualized_q_summary.md",
    )

    # ----- Deficit type contrast -----
    slide_section(
        prs,
        "7. No drought-style temporary pool",
        "Same 3-year stress; temporary = recovered in recovery year 1",
    )
    slide_figure(
        prs,
        "Temporary vs persistent volume, and temporary fraction",
        "pumping_vs_drought_temp_persist_bars.png",
    )
    slide_figure(
        prs,
        "Fraction of end-stress deficit remaining in recovery",
        "pumping_vs_drought_fractional_recovery.png",
    )
    slide_figure(
        prs,
        "ΔS through recovery: drought rebounds in year 1; pumping does not",
        "pumping_vs_drought_ds_recovery.png",
    )
    slide_figure(
        prs,
        "Where the deficit sits: drought near-surface temporary vs pumping deep persistent",
        "pumping_vs_drought_depth_partition.png",
    )
    slide_bullets(
        prs,
        "Pumping deficits are not drought deficits",
        [
            "Drought has a large year-1 temporary limb (Wolf f_temp=0.82; Potomac 0.59)",
            "Pumping 1e-5 f_temp=0.12 in both domains — little of the loss comes back in year 1",
            "Drought deficit drops in recovery yr1 then plateaus; pumping stays near the end-stress deficit",
            "Drought temporary mass is the top 2 m (esp. Wolf); pumping leftover is deep (layer-2 extraction)",
            "Higher rates make this worse: 1e-4 leaves f_temp≈0.05",
        ],
        footer="See pumping_vs_drought_deficits_summary.md",
    )
    slide_figure(
        prs,
        "Persistent mass vs overland rank: drought concentrates, pumping does not",
        "pumping_drainage_deficit_concentration.png",
    )
    slide_figure(
        prs,
        "Pumping 1e-5: mean persist vs log overland and vs stream distance",
        "pumping_drainage_threshold_bins.png",
    )
    slide_figure(
        prs,
        "Mean persist vs log overland, scaled by domain mean",
        "pumping_vs_drought_mean_persist_overland.png",
    )
    slide_bullets(
        prs,
        "Overland no longer locates the persistent mass",
        [
            "Drought: lowest-flow 20% of cells hold 60% (Potomac) / 40% (Wolf) of persist mass",
            "Pumping 1e-5: those same cells hold 23% / 29% — near uniform (20%)",
            "Potomac pumping persist even leans slightly toward higher-flow cells (ρ=+0.10)",
            "Wolf keeps a weak low-flow slope, but the mass is not stacked in dry uplands the way drought is",
            "Layer-2 extraction writes memory off the overland ranking that organizes drought persistence",
        ],
        footer="See pumping_overland_persist_summary.md",
    )

    # ----- Takeaways -----
    slide_section(prs, "8. Takeaways", "What differs — storage type, depth, and Q")
    slide_bullets(
        prs,
        "Preliminary conclusions",
        [
            "Pumping has no drought-style temporary pool: year-1 recovery is a thin sliver",
            "Pumping persist is not the drought overland pattern: near-uniform in flow rank",
            "Losses sit deep (layer 2) even in cells that would pay drought with a near-surface skin",
            "Unlike drought, outlet Q declines as deep storage builds — capture couples S to Q",
            "After shutoff: Potomac 1e-5 slowly rebounds; 1e-4 Q stays ~half of baseline for 10 yr",
            "Wolf annualized Q is weakly affected; storage memory is still mostly persistent",
        ],
        footer="Scripts: pumping_vs_drought_deficits.py · pumping_annualized_q.py · pumping_shallow_deep_proxies.py",
    )

    prs.save(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
