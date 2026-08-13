#!/usr/bin/env python3
"""Does thresholded WTD beat overland for temp/persist? Does a combo win?

Compares monotonic (Spearman), single-threshold step models, quantile-binned
nonlinear skill, and 2-D WTD×overland bins — same cells/masks as Budyko analysis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path("/glade/derecho/scratch/bwest/drought-ensemble")
sys.path.insert(0, str(ROOT))

from analysis.budyko_temp_persistent import (  # noqa: E402
    DOMAIN_LABELS,
    DOMAINS,
    FIG_DIR,
    LABEL_FS,
    LEGEND_FS,
    baseline_fields,
    distance_to_stream_km,
    spearmanr,
)
from analysis.redo_recovery_with_50yr import storage_deficit_pair  # noqa: E402

FOCUS_L = 10
N_BINS = 12
TOP_FRAC = 0.20  # enrichment of top 20% persistent cells / mass
OUT_PREFIX = "wtd_threshold_vs_overland"


def load_bundle_lean(domain_name: str, L: int = FOCUS_L) -> dict:
    """Baseline predictors + one drought length — skip climate Budyko fields."""
    print(f"Building baseline for {domain_name}…", flush=True)
    base = baseline_fields(domain_name)
    dist = distance_to_stream_km(base["streams"], base["active"])
    print(f"  storage deficits {domain_name} {L}-yr…", flush=True)
    pair = storage_deficit_pair(domain_name, L)
    active = base["active"]
    temp = np.asarray(pair["temporary"].values, dtype=np.float64)
    pers = np.asarray(pair["persistent"].values, dtype=np.float64)
    tot = temp + pers
    f_temp = np.full_like(tot, np.nan)
    ok = np.isfinite(tot) & (tot > 1e-6)
    f_temp[ok] = temp[ok] / tot[ok]
    return {
        **base,
        "dist_km": dist,
        "deficits": {
            L: {
                "temporary": np.where(active, temp, np.nan),
                "persistent": np.where(active, pers, np.nan),
                "f_temp": np.where(active, f_temp, np.nan),
                "total": np.where(active, tot, np.nan),
            }
        },
    }


def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
    y = np.asarray(y, dtype=np.float64)
    yhat = np.asarray(yhat, dtype=np.float64)
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    if ss_tot <= 0:
        return np.nan
    return float(1.0 - ss_res / ss_tot)


def optimal_threshold(
    x: np.ndarray, y: np.ndarray, *, higher_means_more: bool | None = None
) -> dict:
    """Best single-step predictor: yhat = a if x>t else b (fit means).

    Searches interior percentiles of x. Returns R², Spearman(yhat,y), threshold.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    qs = np.linspace(5, 95, 37)
    cands = np.unique(np.percentile(x, qs))
    best = {"r2": -np.inf, "thr": np.nan, "rho": np.nan, "delta": np.nan, "n_hi": 0}
    for t in cands:
        hi = x > t
        lo = ~hi
        if hi.sum() < 20 or lo.sum() < 20:
            continue
        yhat = np.where(hi, y[hi].mean(), y[lo].mean())
        r2 = _r2(y, yhat)
        if r2 > best["r2"]:
            rho, _ = spearmanr(yhat, y)
            best = {
                "r2": r2,
                "thr": float(t),
                "rho": rho,
                "delta": float(y[hi].mean() - y[lo].mean()),
                "n_hi": int(hi.sum()),
                "mean_hi": float(y[hi].mean()),
                "mean_lo": float(y[lo].mean()),
            }
    return best


def quantile_bin_skill(x: np.ndarray, y: np.ndarray, n_bins: int = N_BINS) -> dict:
    """Predict y by leave-in bin means (in-sample nonlinear skill upper bound)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    # equal-count bins
    edges = np.unique(np.percentile(x, np.linspace(0, 100, n_bins + 1)))
    if edges.size < 3:
        return {"r2": np.nan, "rho": np.nan, "n_bins": 0}
    # digitize
    idx = np.digitize(x, edges[1:-1], right=False)
    yhat = np.empty_like(y)
    for b in range(edges.size - 1):
        m = idx == b
        if m.any():
            yhat[m] = y[m].mean()
    rho, _ = spearmanr(yhat, y)
    return {"r2": _r2(y, yhat), "rho": rho, "n_bins": int(edges.size - 1)}


def two_d_bin_skill(
    x1: np.ndarray, x2: np.ndarray, y: np.ndarray, n_bins: int = 6
) -> dict:
    """n×n equal-count bins on (x1,x2); in-sample bin-mean R² / Spearman."""
    x1 = np.asarray(x1, dtype=np.float64)
    x2 = np.asarray(x2, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    e1 = np.unique(np.percentile(x1, np.linspace(0, 100, n_bins + 1)))
    e2 = np.unique(np.percentile(x2, np.linspace(0, 100, n_bins + 1)))
    if e1.size < 3 or e2.size < 3:
        return {"r2": np.nan, "rho": np.nan}
    i1 = np.digitize(x1, e1[1:-1], right=False)
    i2 = np.digitize(x2, e2[1:-1], right=False)
    yhat = np.full_like(y, y.mean())
    for a in range(e1.size - 1):
        for b in range(e2.size - 1):
            m = (i1 == a) & (i2 == b)
            if m.any():
                yhat[m] = y[m].mean()
    rho, _ = spearmanr(yhat, y)
    return {"r2": _r2(y, yhat), "rho": rho, "n_bins_each": int(min(e1.size, e2.size) - 1)}


def dual_threshold_skill(
    x1: np.ndarray, x2: np.ndarray, y: np.ndarray
) -> dict:
    """Search two thresholds; 4-regime means as predictor (coarse interaction)."""
    x1 = np.asarray(x1, dtype=np.float64)
    x2 = np.asarray(x2, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    qs = np.linspace(15, 85, 8)
    c1 = np.unique(np.percentile(x1, qs))
    c2 = np.unique(np.percentile(x2, qs))
    best = {"r2": -np.inf, "thr1": np.nan, "thr2": np.nan, "rho": np.nan}
    for t1 in c1:
        for t2 in c2:
            g = (x1 > t1).astype(np.int8) * 2 + (x2 > t2).astype(np.int8)
            yhat = np.empty_like(y)
            ok = True
            for k in range(4):
                m = g == k
                if m.sum() < 15:
                    ok = False
                    break
                yhat[m] = y[m].mean()
            if not ok:
                continue
            r2 = _r2(y, yhat)
            if r2 > best["r2"]:
                rho, _ = spearmanr(yhat, y)
                best = {
                    "r2": r2,
                    "thr1": float(t1),
                    "thr2": float(t2),
                    "rho": rho,
                }
    return best


def enrichment_top(
    x: np.ndarray,
    y: np.ndarray,
    *,
    low_x_selects: bool,
    mass: np.ndarray | None = None,
    top_frac: float = TOP_FRAC,
) -> dict:
    """Among lowest/highest top_frac of x, enrichment of top_frac y cells and mass."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = x.size
    k = max(int(round(top_frac * n)), 1)
    order_x = np.argsort(x)
    sel = order_x[:k] if low_x_selects else order_x[-k:]
    y_thr = np.percentile(y, 100 * (1 - top_frac))
    top_y = y >= y_thr
    base_rate = top_y.mean()
    hit = top_y[sel].mean() / base_rate if base_rate > 0 else np.nan
    out = {"cell_enrichment": float(hit), "n_sel": int(k)}
    if mass is not None:
        mass = np.asarray(mass, dtype=np.float64)
        tot = mass.sum()
        out["mass_fraction"] = float(mass[sel].sum() / tot) if tot > 0 else np.nan
    return out


def binned_curve(x: np.ndarray, y: np.ndarray, n_bins: int = N_BINS):
    edges = np.unique(np.percentile(x, np.linspace(0, 100, n_bins + 1)))
    idx = np.digitize(x, edges[1:-1], right=False)
    xc, yc, n = [], [], []
    for b in range(edges.size - 1):
        m = idx == b
        if m.sum() < 5:
            continue
        xc.append(np.median(x[m]))
        yc.append(np.mean(y[m]))
        n.append(int(m.sum()))
    return np.asarray(xc), np.asarray(yc), np.asarray(n)


def cell_table(bundle: dict, L: int = FOCUS_L) -> dict[str, np.ndarray]:
    active = bundle["active"]
    streams = bundle["streams"]
    mask = active & ~streams
    flow = bundle["flow"]
    log_flow = np.log10(np.maximum(flow, 1e-6))
    wtd = bundle["wtd"]
    dist = bundle["dist_km"]
    part = bundle["participation"]
    pers = bundle["deficits"][L]["persistent"]
    temp = bundle["deficits"][L]["temporary"]
    f_temp = bundle["deficits"][L]["f_temp"]
    tot = bundle["deficits"][L]["total"]
    m = (
        mask
        & np.isfinite(log_flow)
        & np.isfinite(wtd)
        & np.isfinite(dist)
        & np.isfinite(part)
        & np.isfinite(pers)
        & np.isfinite(f_temp)
        & (tot > 1e-6)
    )
    return {
        "log_flow": log_flow[m],
        "flow": flow[m],
        "participation": part[m],
        "wtd": wtd[m],
        "dist_km": dist[m],
        "persistent": pers[m],
        "temporary": temp[m],
        "f_temp": f_temp[m],
        "total": tot[m],
        "n": int(m.sum()),
    }


def analyze_domain(name: str, bundle: dict) -> dict:
    t = cell_table(bundle)
    predictors = {
        "log_overland": ("log_flow", True),  # low → more persist
        "participation": ("participation", True),
        "wtd": ("wtd", False),  # high → more persist / lower f_temp
        "dist_km": ("dist_km", False),
    }
    responses = ["persistent", "f_temp"]
    rows = []
    for resp in responses:
        y = t[resp]
        mass = t["persistent"] if resp == "persistent" else None
        for plab, (pkey, low_selects_for_persist) in predictors.items():
            x = t[pkey]
            rho, _ = spearmanr(x, y)
            step = optimal_threshold(x, y)
            bins = quantile_bin_skill(x, y)
            # enrichment: for persistent, select the side expected to hold persist
            if resp == "persistent":
                low_x = low_selects_for_persist
            else:
                # f_temp: opposite of persist for most predictors
                low_x = not low_selects_for_persist
            enr = enrichment_top(x, y if resp == "persistent" else t["persistent"], low_x_selects=low_x, mass=t["persistent"])
            rows.append(
                {
                    "domain": name,
                    "response": resp,
                    "predictor": plab,
                    "spearman": rho,
                    "step_r2": step["r2"],
                    "step_thr": step["thr"],
                    "step_delta": step.get("delta", np.nan),
                    "bin_r2": bins["r2"],
                    "bin_rho": bins["rho"],
                    "top20_cell_enrichment": enr["cell_enrichment"],
                    "top20_mass_fraction": enr.get("mass_fraction", np.nan),
                }
            )

        # combinations
        combos = {
            "wtd+log_overland": ("wtd", "log_flow"),
            "wtd+participation": ("wtd", "participation"),
            "log_overland+dist": ("log_flow", "dist_km"),
        }
        for clab, (a, b) in combos.items():
            twod = two_d_bin_skill(t[a], t[b], y, n_bins=6)
            dual = dual_threshold_skill(t[a], t[b], y)
            rows.append(
                {
                    "domain": name,
                    "response": resp,
                    "predictor": clab,
                    "spearman": np.nan,
                    "step_r2": dual["r2"],
                    "step_thr": np.nan,
                    "step_delta": np.nan,
                    "bin_r2": twod["r2"],
                    "bin_rho": twod["rho"],
                    "top20_cell_enrichment": np.nan,
                    "top20_mass_fraction": np.nan,
                    "dual_thr1": dual.get("thr1"),
                    "dual_thr2": dual.get("thr2"),
                }
            )
    return {"n": t["n"], "rows": rows, "table": t}


def fig_binned_means(results: dict):
    """Mean persistent & f_temp vs WTD / log-overland / distance (equal-count bins)."""
    preds = [
        ("wtd", "Baseline WTD (m)"),
        ("log_flow", r"log$_{10}$ overland (m³/h)"),
        ("dist_km", "Distance to stream (km)"),
    ]
    fig, axes = plt.subplots(
        2, 6, figsize=(14.5, 6.2), sharey="row", constrained_layout=True
    )
    colmap = [(d, p) for d in DOMAINS for p in preds]

    for col, (domain, (pkey, xlab)) in enumerate(colmap):
        t = results[domain]["table"]
        x = t[pkey]
        for row, resp, ylab in [
            (0, "persistent", "Mean persistent (m)"),
            (1, "f_temp", r"Mean $f_\mathrm{temp}$ (-)"),
        ]:
            ax = axes[row, col]
            xc, yc, _ = binned_curve(x, t[resp])
            color = "#4A2410" if resp == "persistent" else "#B86B2B"
            ax.plot(xc, yc, "o-", color=color, ms=4, lw=1.4)
            if row == 1:
                ax.set_xlabel(xlab, fontsize=9)
            if col == 0:
                ax.set_ylabel(ylab, fontsize=LABEL_FS)
            ax.grid(True, alpha=0.3)

    for i, d in enumerate(DOMAINS):
        axes[0, i * 3 + 1].set_title(DOMAIN_LABELS[d], fontsize=LABEL_FS + 1)

    out = FIG_DIR / f"{OUT_PREFIX}_binned_means.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_skill_bars(results: dict):
    """Compare Spearman |ρ|, step R², bin R², combo bin R² for persistent & f_temp."""
    order_single = ["log_overland", "participation", "wtd", "dist_km"]
    order_combo = ["wtd+log_overland", "wtd+participation", "log_overland+dist"]
    labels = {
        "log_overland": r"log$_{10}$ overland",
        "participation": "OL participation",
        "wtd": "WTD",
        "dist_km": "Dist. stream",
        "wtd+log_overland": "WTD × log OL",
        "wtd+participation": "WTD × partic.",
        "log_overland+dist": "log OL × dist",
    }

    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.0), constrained_layout=True)
    for col, domain in enumerate(DOMAINS):
        rows = results[domain]["rows"]
        for row, resp, title in [
            (0, "persistent", "Persistent deficit"),
            (1, "f_temp", r"Temporary fraction $f_\mathrm{temp}$"),
        ]:
            ax = axes[row, col]
            lookup = {
                r["predictor"]: r for r in rows if r["response"] == resp
            }
            names = order_single + order_combo
            x = np.arange(len(names))
            spear = [abs(lookup[n]["spearman"]) if np.isfinite(lookup[n]["spearman"]) else 0 for n in names]
            step = [lookup[n]["step_r2"] if np.isfinite(lookup[n]["step_r2"]) else 0 for n in names]
            bins = [lookup[n]["bin_r2"] if np.isfinite(lookup[n]["bin_r2"]) else 0 for n in names]
            w = 0.25
            ax.bar(x - w, spear, w, label=r"|Spearman ρ|", color="#D4A574")
            ax.bar(x, step, w, label=r"Step / dual-thr $R^2$", color="#B86B2B")
            ax.bar(x + w, bins, w, label=r"Quantile-bin $R^2$", color="#4A2410")
            ax.set_xticks(x)
            ax.set_xticklabels([labels[n] for n in names], rotation=35, ha="right", fontsize=9)
            ax.set_ylim(0, 1.05)
            ax.grid(True, axis="y", alpha=0.3)
            if col == 0:
                ax.set_ylabel("Skill (-)", fontsize=LABEL_FS)
            if row == 0:
                ax.set_title(f"{DOMAIN_LABELS[domain]} — {title}", fontsize=LABEL_FS)
            else:
                ax.set_title(title, fontsize=LABEL_FS)
            # separator between single and combo
            ax.axvline(len(order_single) - 0.5, color="0.5", ls="--", lw=0.8)

    handles, labs = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labs,
        loc="outside upper center",
        ncol=3,
        fontsize=LEGEND_FS,
        frameon=False,
    )
    out = FIG_DIR / f"{OUT_PREFIX}_skill.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def fig_2d_heatmap(results: dict):
    """Mean persistent in WTD × log-overland quantile bins."""
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4), constrained_layout=True)
    n = 6
    for ax, domain in zip(axes, DOMAINS):
        t = results[domain]["table"]
        x1, x2, y = t["wtd"], t["log_flow"], t["persistent"]
        e1 = np.percentile(x1, np.linspace(0, 100, n + 1))
        e2 = np.percentile(x2, np.linspace(0, 100, n + 1))
        # force unique by tiny jitter on edges if needed
        e1 = np.maximum.accumulate(e1 + np.arange(len(e1)) * 1e-9)
        e2 = np.maximum.accumulate(e2 + np.arange(len(e2)) * 1e-9)
        mat = np.full((n, n), np.nan)
        for i in range(n):
            for j in range(n):
                m = (
                    (x1 >= e1[i])
                    & (x1 < e1[i + 1] if i < n - 1 else x1 <= e1[i + 1])
                    & (x2 >= e2[j])
                    & (x2 < e2[j + 1] if j < n - 1 else x2 <= e2[j + 1])
                )
                if m.sum() >= 5:
                    mat[i, j] = y[m].mean()
        im = ax.imshow(
            mat,
            origin="lower",
            aspect="auto",
            cmap="YlOrBr",
            extent=[0, n, 0, n],
        )
        ax.set_xticks(np.arange(n) + 0.5)
        ax.set_yticks(np.arange(n) + 0.5)
        ax.set_xticklabels([f"Q{j+1}" for j in range(n)], fontsize=9)
        ax.set_yticklabels([f"Q{i+1}" for i in range(n)], fontsize=9)
        ax.set_xlabel(r"log$_{10}$ overland quantile →", fontsize=LABEL_FS)
        ax.set_ylabel(r"WTD quantile → (deeper)", fontsize=LABEL_FS)
        ax.set_title(DOMAIN_LABELS[domain], fontsize=LABEL_FS)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Mean persistent (m)", fontsize=10)
    out = FIG_DIR / f"{OUT_PREFIX}_2d_bins.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def main():
    results = {}
    summary = {"L": FOCUS_L, "domains": {}}
    for d in DOMAINS:
        print(f"=== {d} ===", flush=True)
        b = load_bundle_lean(d, FOCUS_L)
        results[d] = analyze_domain(d, b)
        summary["domains"][d] = {
            "n": results[d]["n"],
            "rows": [
                {k: (None if isinstance(v, float) and not np.isfinite(v) else v)
                 for k, v in r.items()}
                for r in results[d]["rows"]
            ],
        }
        print(f"  n={results[d]['n']}", flush=True)
        for r in results[d]["rows"]:
            if r["response"] != "persistent":
                continue
            print(
                f"  persist|{r['predictor']:22s} "
                f"ρ={r['spearman'] if np.isfinite(r['spearman']) else float('nan'):+.3f}  "
                f"stepR²={r['step_r2']:.3f}  binR²={r['bin_r2']:.3f}  "
                f"mass20={r.get('top20_mass_fraction', float('nan'))}",
                flush=True,
            )

    fig_binned_means(results)
    fig_skill_bars(results)
    fig_2d_heatmap(results)

    out_json = FIG_DIR / f"{OUT_PREFIX}_summary.json"
    out_json.write_text(json.dumps(summary, indent=2, default=float))
    print("wrote", out_json)

    # concise markdown verdict
    lines = [
        f"# WTD thresholding vs overland ( {FOCUS_L}-yr )",
        "",
        "Question: does baseline WTD explain temporary vs persistent better once",
        "we allow a threshold / nonlinear map — and does WTD×overland beat both?",
        "",
        "Skill metrics (non-stream cells with deficit):",
        "- **|Spearman ρ|**: monotonic / nearly-linear-in-ranks",
        "- **Step / dual-thr R²**: best single threshold (or 2-D dual thresholds for combos)",
        "- **Quantile-bin R²**: equal-count bin means (flexible nonlinear upper bound, in-sample)",
        "",
    ]
    for d in DOMAINS:
        lines.append(f"## {DOMAIN_LABELS[d]} (n={results[d]['n']})")
        lines.append("")
        lines.append(
            "| Response | Predictor | \|ρ\| | step/dual R² | bin R² | top-20% persist mass |"
        )
        lines.append("|----------|-----------|----:|-------------:|-------:|---------------------:|")
        for r in results[d]["rows"]:
            rho = abs(r["spearman"]) if np.isfinite(r["spearman"]) else float("nan")
            mass = r.get("top20_mass_fraction", float("nan"))
            mass_s = f"{mass:.2f}" if isinstance(mass, float) and np.isfinite(mass) else "—"
            rho_s = f"{rho:.3f}" if np.isfinite(rho) else "—"
            lines.append(
                f"| {r['response']} | {r['predictor']} | {rho_s} | "
                f"{r['step_r2']:.3f} | {r['bin_r2']:.3f} | {mass_s} |"
            )
        lines.append("")
    md = FIG_DIR.parent / "wtd_threshold_vs_overland_summary.md"
    # put next to other summaries
    md.write_text("\n".join(lines) + "\n")
    print("wrote", md)


if __name__ == "__main__":
    main()
