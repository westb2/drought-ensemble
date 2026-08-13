#!/usr/bin/env python3
"""Render analysis/*_summary.md to PDF (+ self-contained HTML) with figures embedded."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from fpdf import FPDF
from PIL import Image

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble/analysis")
FIG = ROOT / "figures"
FONT = Path("/usr/share/fonts/truetype/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/DejaVuSans-Bold.ttf")

REPLACEMENTS = {
    "×": "x",
    "ρ": "rho",
    "Δ": "d",
    "φ": "phi",
    "ϕ": "phi",
    "≈": "~",
    "≪": "<<",
    "—": "-",
    "–": "-",
    "“": '"',
    "”": '"',
    "’": "'",
    "→": "->",
    "↔": "<->",
    "≤": "<=",
    "≥": ">=",
    "⁶": "6",
    "³": "3",
    "²": "2",
    "¹": "1",
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "ₙ": "n",
    "ₛ": "s",
    "±": "+/-",
    "·": ".",
    "…": "...",
}


def asciiize(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\\\((.+?)\\\)", r"\1", s)
    for a, b in REPLACEMENTS.items():
        s = s.replace(a, b)
    return s


def resolve_fig(path_str: str) -> Path | None:
    p = path_str.strip()
    p = p.replace("drought-ensemble/analysis/figures/", "figures/")
    p = p.replace("analysis/figures/", "figures/")
    if p.startswith("figures/"):
        cand = ROOT / p
    else:
        cand = Path(p)
        if not cand.is_absolute():
            cand = ROOT / p
    return cand if cand.exists() else None


def expand_figure_refs(md_text: str, stem: str) -> str:
    """Turn link-style figure refs into ![alt](figures/...) embeds; expand globs."""
    lines_out: list[str] = []
    for line in md_text.splitlines():
        # Already an image embed
        if re.match(r"^\s*!\[", line):
            # normalize path
            def _norm(m):
                alt, path = m.group(1), m.group(2)
                path = path.replace("drought-ensemble/analysis/figures/", "figures/")
                path = path.replace("analysis/figures/", "figures/")
                return f"![{alt}]({path})"

            lines_out.append(re.sub(r"!\[(.*?)\]\((.*?)\)", _norm, line))
            continue

        # Bullet / inline markdown links to png/svg
        m = re.match(r"^(\s*[-*]?\s*)\[([^\]]+)\]\((figures/[^)]+\.(?:png|svg))\)(.*)$", line)
        if m:
            prefix, label, path, rest = m.groups()
            lines_out.append(f"{prefix}{label}{rest}".rstrip())
            lines_out.append(f"![{label}]({path})")
            continue

        # Glob mention like budyko_*.png or average_year_usgs_*.png
        glob_bits = re.findall(
            r"`?(?:analysis/)?figures/([A-Za-z0-9_.*-]+\.png)`?", line
        )
        glob_bits += re.findall(
            r"\(([A-Za-z0-9_*]+(?:_year_usgs)?[A-Za-z0-9_.*-]*\.png)\)", line
        )
        # Special-case known summary figure sets
        if "budyko_*.png" in line or "budyko_*" in line:
            files = sorted(FIG.glob("budyko_*.png"))
            lines_out.append(line)
            for f in files:
                lines_out.append(f"![{f.stem}](figures/{f.name})")
            continue
        if "average_year_usgs_" in line or "drought_year_usgs_" in line:
            lines_out.append(line)
            files = sorted(FIG.glob("average_year_usgs_*.png")) + sorted(
                FIG.glob("drought_year_usgs_*.png")
            )
            # de-dupe
            seen = set()
            for f in files:
                if f.name in seen:
                    continue
                seen.add(f.name)
                lines_out.append(f"![{f.stem}](figures/{f.name})")
            continue

        lines_out.append(line)
    return "\n".join(lines_out)


class PDF(FPDF):
    body_font = "Body"

    def footer(self):
        self.set_y(-12)
        self.set_font(self.body_font, "I", 8)
        self.set_text_color(120)
        self.cell(0, 8, f"{self.page_no()}", align="C")


def render_pdf(md_text: str, out_pdf: Path, title: str) -> None:
    pdf = PDF(orientation="P", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_margins(16, 16, 16)
    pdf.add_font("Body", "", str(FONT))
    pdf.add_font("Body", "B", str(FONT_BOLD if FONT_BOLD.exists() else FONT))
    pdf.add_font("Body", "I", str(FONT))
    pdf.body_font = "Body"

    def set_font(style="", size=11):
        pdf.set_font(pdf.body_font, style if style in ("", "B", "I") else "", size)

    def add_wrapped(txt, size=11, style="", color=(20, 20, 20), after=3):
        set_font(style, size)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, size * 0.42 + 2.0, asciiize(txt))
        pdf.ln(after)

    def add_image(rel: str):
        p = resolve_fig(rel)
        if p is None:
            add_wrapped(f"[missing figure: {rel}]", size=9, color=(180, 40, 40))
            return
        # skip non-images
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
            add_wrapped(f"[attachment: {p.name}]", size=9, color=(80, 80, 80))
            return
        if p.suffix.lower() == ".svg":
            add_wrapped(f"[svg skipped: {p.name}]", size=9, color=(80, 80, 80))
            return
        page_w = pdf.w - pdf.l_margin - pdf.r_margin
        with Image.open(p) as im:
            w_px, h_px = im.size
        aspect = h_px / max(w_px, 1)
        w = page_w
        h = w * aspect
        max_h = pdf.h - pdf.t_margin - pdf.b_margin - 24
        if h > max_h:
            h = max_h
            w = h / aspect
        if pdf.get_y() + h > pdf.h - pdf.b_margin:
            pdf.add_page()
        x = pdf.l_margin + (page_w - w) / 2
        pdf.image(str(p), x=x, w=w)
        pdf.ln(4)

    lines = md_text.splitlines()
    i = 0
    table_rows: list[str] = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        rows = [r for r in table_rows if not re.match(r"^\|?\s*---", r)]
        parsed = []
        for r in rows:
            cells = [asciiize(c.strip()) for c in r.strip().strip("|").split("|")]
            parsed.append(cells)
        table_rows = []
        if not parsed:
            return
        ncols = max(len(r) for r in parsed)
        page_w = pdf.w - pdf.l_margin - pdf.r_margin
        col_w = page_w / ncols
        for ri, row in enumerate(parsed):
            y0 = pdf.get_y()
            x0 = pdf.l_margin
            cell_texts = [(row[ci] if ci < len(row) else "") for ci in range(ncols)]
            line_h = 4.0
            set_font("B" if ri == 0 else "", 8)
            heights = []
            for cell in cell_texts:
                nlines = max(1, int(pdf.get_string_width(cell) / max(col_w - 2, 1)) + 1)
                heights.append(nlines * line_h + 1)
            row_h = max(heights)
            if y0 + row_h > pdf.h - pdf.b_margin:
                pdf.add_page()
                y0 = pdf.get_y()
            for ci, cell in enumerate(cell_texts):
                pdf.set_xy(x0 + ci * col_w, y0)
                set_font("B" if ri == 0 else "", 8)
                if ri == 0:
                    pdf.set_fill_color(240, 240, 240)
                    pdf.rect(x0 + ci * col_w, y0, col_w, row_h, style="F")
                pdf.rect(x0 + ci * col_w, y0, col_w, row_h)
                pdf.set_xy(x0 + ci * col_w + 1, y0 + 0.8)
                pdf.multi_cell(col_w - 2, line_h, cell)
            pdf.set_y(y0 + row_h)
        pdf.ln(3)

    add_wrapped(title, size=14, style="B", after=4)

    while i < len(lines):
        line = lines[i]
        img = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if img:
            flush_table()
            add_image(img.group(2))
            i += 1
            continue
        if line.strip().startswith("|"):
            table_rows.append(line.strip())
            i += 1
            continue
        flush_table()
        if not line.strip():
            pdf.ln(2)
            i += 1
            continue
        if line.startswith("# "):
            # skip duplicate title if same as filename title
            add_wrapped(line[2:], size=16, style="B", after=4)
        elif line.startswith("## "):
            pdf.ln(2)
            add_wrapped(line[3:], size=13, style="B", after=3)
        elif line.startswith("### "):
            add_wrapped(line[4:], size=12, style="B", after=2)
        elif line.startswith("- ") or line.startswith("* "):
            add_wrapped("- " + line[2:], size=10, after=1)
        else:
            add_wrapped(line, size=10, after=2)
        i += 1
    flush_table()
    pdf.output(str(out_pdf))


def render_html(md_for_pandoc: Path, out_html: Path, title: str) -> None:
    subprocess.run(
        [
            "pandoc",
            str(md_for_pandoc),
            "-o",
            str(out_html),
            "--standalone",
            "--embed-resources",
            "-f",
            "markdown",
            "-t",
            "html5",
            "--metadata",
            f"title={title}",
        ],
        check=True,
    )


def process(md_path: Path) -> None:
    stem = md_path.stem  # e.g. budyko_temp_persistent_summary
    title = stem.replace("_", " ")
    raw = md_path.read_text()
    expanded = expand_figure_refs(raw, stem)

    tmp = ROOT / f"._render_{stem}.md"
    tmp.write_text(expanded)

    out_pdf = FIG / f"{stem}.pdf"
    out_html = FIG / f"{stem}.html"
    print(f"Rendering {md_path.name} …", flush=True)
    render_pdf(expanded, out_pdf, title)
    print(f"  wrote {out_pdf} ({out_pdf.stat().st_size/1024:.0f} KB)", flush=True)
    render_html(tmp, out_html, title)
    print(f"  wrote {out_html} ({out_html.stat().st_size/1024:.0f} KB)", flush=True)
    tmp.unlink(missing_ok=True)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1:
        paths = [Path(a) for a in sys.argv[1:]]
    else:
        # all analysis summaries except ones already requested individually
        paths = sorted(ROOT.glob("*_summary.md"))
    for p in paths:
        if not p.is_file():
            print("skip missing", p)
            continue
        process(p.resolve() if p.is_absolute() else (ROOT / p.name).resolve())


if __name__ == "__main__":
    main()
